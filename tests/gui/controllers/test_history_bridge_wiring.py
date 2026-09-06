"""Tests for the GUI-only wiring HistoryBridge adds on top of HistoryApplyUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from chappy.application.history import (
    ChangeSet,
    ComponentParameterState,
    HistoryApplyError,
    HistoryApplyErrorCode,
    HistoryRefreshTarget,
    ModelParameterEditCommand,
    NamedParameterState,
    RangeSnapshot,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.continuum import ContinuumComponent
from chappy.core.history import CommandHistory, HistoryEvent, HistoryState
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.history.bridge import HistoryBridge
from chappy.gui.history.refresh_adapter import HistoryBridgeRefreshPort, HistoryRefreshAdapter
from chappy.gui.history.translation import translate_operation
from chappy.i18n.language_switcher import get_language_switcher

if TYPE_CHECKING:
    from pytest_qt.qtbot import QtBot  # type: ignore[import-not-found]


class _MainWindow:
    """Minimal main-window refresh surface for HistoryBridge."""

    def __init__(self) -> None:
        """Initialize refresh surface state."""
        self.identify_coordinator = None
        self.mode_shell_coordinator = None
        self._active_structure_line_id = None

    def _update_structure_velocity_input(self, line_ids: list[str]) -> None:
        """Accept structure velocity refresh requests."""

    def _refresh_optimize_velocity_input(self) -> None:
        """Accept optimize velocity refresh requests."""


def _component_state(value: float) -> ComponentParameterState:
    """Create one component parameter state."""
    return ComponentParameterState(
        component_id="comp-1",
        parameters=(
            NamedParameterState(
                name="redshift", value=value, vary=True, min_value=None, max_value=None, error=0.02
            ),
        ),
    )


def _scientific_parameter_project() -> SpectroscopyProject:
    """Build one capable region and a component at the command after-state."""
    project = SpectroscopyProject()
    component = AbsorberComponent(component_id="comp-1", redshift=2.0)
    project.model.add_component_storage(component)
    line = AbsorptionLine(
        line_id="line-1",
        species="C IV",
        rest_wavelength=1548.2,
        center_z=2.0,
        window_kms=100.0,
        multiplet_label="C IV",
        transition_name="1548",
        oscillator_strength=0.1,
        gamma_value=1e8,
        region_id="region-1",
        model_ids=[component.id],
    )
    line.needs_optimization = False
    project.load_absorption_state(
        regions={"region-1": AbsorptionRegion("region-1", line_ids=[line.line_id])},
        lines={line.line_id: line},
    )
    revision = AnalysisRevision(3)
    project.set_region_analysis_state(
        RegionAnalysisState(
            region_id="region-1",
            current_revision=revision,
            artifact=AnalysisArtifact(
                region_id="region-1",
                source_revision=revision,
                fit_summary=FitSummary(chi_squared=1.0),
            ),
        )
    )
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project


def _parameter_edit_event() -> HistoryEvent:
    """Build one committable redshift parameter edit event."""
    return HistoryEvent(
        command=ModelParameterEditCommand(
            param_name="redshift",
            component_ids=("comp-1",),
            before=(_component_state(1.0),),
            after=(_component_state(2.0),),
            region_id="region-1",
        )
    )


def test_state_changed_signal_emits_on_history_push(qtbot: QtBot) -> None:
    """Pushing a history event must emit ``state_changed`` with the new state."""
    history = CommandHistory()
    bridge = HistoryBridge(history, refresh_main_window=_MainWindow())
    emitted: list[HistoryState] = []
    bridge.state_changed.connect(emitted.append)

    with qtbot.waitSignal(bridge.state_changed, timeout=1000):
        assert history.push(_parameter_edit_event())

    assert len(emitted) == 1
    assert emitted[0] == history.get_state()
    assert emitted[0].can_undo is True


def test_undo_and_redo_return_translated_name_on_success() -> None:
    """A successful Undo/Redo reports the translated operation name."""
    history = CommandHistory()
    bridge = HistoryBridge(history, refresh_main_window=_MainWindow())
    project = _scientific_parameter_project()
    bridge.set_project(project)
    event = _parameter_edit_event()
    assert history.push(event)
    expected_name = translate_operation(event.full_operation_id, get_language_switcher())

    success, reason = bridge.undo()

    assert success is True
    assert reason == expected_name

    success, reason = bridge.redo()

    assert success is True
    assert reason == expected_name


def test_undo_returns_failure_tuple_for_target_not_found_without_raising() -> None:
    """A missing project target is reported as ``(False, message)``, not raised."""
    history = CommandHistory()
    bridge = HistoryBridge(history, refresh_main_window=_MainWindow())
    assert history.push(_parameter_edit_event())

    success, reason = bridge.undo()

    assert success is False
    assert reason
    assert history.can_undo
    assert not history.can_redo


def test_undo_re_raises_error_codes_other_than_target_not_found() -> None:
    """Non-recoverable failures must propagate rather than collapse to a tuple."""
    history = CommandHistory()
    bridge = HistoryBridge(history, refresh_main_window=_MainWindow())
    project = _scientific_parameter_project()
    bridge.set_project(project)
    invalid = ComponentParameterState(
        component_id="comp-1",
        parameters=(
            NamedParameterState(
                name="redshift", value=4.0, vary=True, min_value=0.0, max_value=3.0, error=0.1
            ),
        ),
    )
    event = HistoryEvent(
        command=ModelParameterEditCommand(
            param_name="redshift",
            component_ids=("comp-1",),
            before=(invalid,),
            after=(_component_state(2.0),),
            region_id="region-1",
        )
    )
    assert history.push(event)

    with pytest.raises(HistoryApplyError) as exc_info:
        bridge.undo()

    assert exc_info.value.error_code is HistoryApplyErrorCode.INVALID_STATE


def test_apply_range_raises_target_not_found_without_coordinator() -> None:
    """``apply_range`` requires a connected SpectrumInteractionCoordinator."""
    bridge = HistoryBridge(CommandHistory(), refresh_main_window=_MainWindow())
    snapshot = RangeSnapshot(wavelength_range=(1000.0, 2000.0))

    with pytest.raises(HistoryApplyError) as exc_info:
        bridge.apply_range(snapshot, source="history")

    assert exc_info.value.error_code is HistoryApplyErrorCode.TARGET_NOT_FOUND


def test_apply_range_raises_invalid_state_for_non_history_source() -> None:
    """``apply_range`` only accepts the ``history`` replay source."""
    bridge = HistoryBridge(CommandHistory(), refresh_main_window=_MainWindow())
    snapshot = RangeSnapshot(wavelength_range=(1000.0, 2000.0))

    with pytest.raises(HistoryApplyError) as exc_info:
        bridge.apply_range(snapshot, source="user")

    assert exc_info.value.error_code is HistoryApplyErrorCode.INVALID_STATE


def _refresh_port(
    *,
    project: SpectroscopyProject | None = None,
    continuum_editor: object | None = None,
    dock: object | None = None,
) -> tuple[HistoryBridgeRefreshPort, HistoryRefreshAdapter]:
    """Build one refresh port wired to a spy-friendly adapter."""
    adapter = HistoryRefreshAdapter(_MainWindow())
    port = HistoryBridgeRefreshPort(
        adapter,
        project_provider=lambda: project,
        continuum_editor_provider=lambda: continuum_editor,
        dock_layout_coordinator_provider=lambda: dock,
    )
    return port, adapter


def test_refresh_port_dispatches_model_and_optimize_panel_as_mutually_exclusive() -> None:
    """MODEL and OPTIMIZE_PANEL are dispatched by an if/elif, never both."""
    port, adapter = _refresh_port()
    change_set = ChangeSet(changed_region_ids=("region-1",))

    with (
        patch.object(adapter, "refresh_model") as refresh_model,
        patch.object(adapter, "refresh_optimize_panel") as refresh_optimize_panel,
    ):
        port.refresh(HistoryRefreshTarget.MODEL, change_set)

        refresh_model.assert_called_once_with(None, None, "region-1")
        refresh_optimize_panel.assert_not_called()

    with (
        patch.object(adapter, "refresh_model") as refresh_model,
        patch.object(adapter, "refresh_optimize_panel") as refresh_optimize_panel,
    ):
        port.refresh(HistoryRefreshTarget.OPTIMIZE_PANEL, change_set)

        refresh_optimize_panel.assert_called_once_with(None, "region-1")
        refresh_model.assert_not_called()


@pytest.mark.parametrize(
    ("target", "adapter_method", "expected_args"),
    [
        (HistoryRefreshTarget.IDENTIFY_PANEL, "refresh_identify", ()),
        (HistoryRefreshTarget.LINE_OVERLAYS, "refresh_velocity_window", (None, "region-1")),
        (HistoryRefreshTarget.VELOCITY_PLOT, "refresh_optimize_velocity_plot", (None,)),
        (
            HistoryRefreshTarget.OPTIMIZE_WAVELENGTH_MODEL_RESIDUAL,
            "refresh_optimize_wavelength_model_residual",
            (None, "region-1"),
        ),
    ],
)
def test_refresh_port_dispatches_target_to_its_adapter_method(
    target: HistoryRefreshTarget, adapter_method: str, expected_args: tuple[object, ...]
) -> None:
    """Every remaining refresh target reaches exactly its one adapter method."""
    port, adapter = _refresh_port()
    change_set = ChangeSet(changed_region_ids=("region-1",))

    with patch.object(adapter, adapter_method) as mocked:
        port.refresh(target, change_set)

    mocked.assert_called_once_with(*expected_args)


def test_refresh_port_dispatches_continuum_editor_target_for_project_continuum() -> None:
    """CONTINUUM_EDITOR resolves the changed continuum from the project first."""
    project = SpectroscopyProject()
    continuum = ContinuumComponent("Continuum")
    continuum.id = "continuum-1"
    project.model.add_component_storage(continuum)
    port, adapter = _refresh_port(project=project)
    change_set = ChangeSet(changed_continuum_ids=("continuum-1",))

    with patch.object(adapter, "refresh_continuum") as mocked:
        port.refresh(HistoryRefreshTarget.CONTINUUM_EDITOR, change_set)

    mocked.assert_called_once_with(None, continuum)
