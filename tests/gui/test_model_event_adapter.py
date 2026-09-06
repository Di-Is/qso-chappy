"""Tests for Qt domain event adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtTest import QSignalSpy

from chappy.application.history import ChangeSet as HistoryChangeSet
from chappy.application.history import HistoryRecorder
from chappy.application.history.apply.usecase import HistoryApplyUseCase
from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    AtomicRegisterSelectedLinesRequest,
    TemporaryLineSnapshot,
)
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.change_set import ChangeSet
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.events import RegionTopologyChanged
from chappy.core.history import CommandHistory
from chappy.core.identify_state import TemporaryLineContext
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum_model import SpectrumModel
from chappy.core.velocity_ranges import (
    DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
    LineAnalysisHalfWidth,
)
from chappy.gui.adapters.model_event_adapter import SpectrumModelEventAdapter

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


class _FailingModelEventAdapter(SpectrumModelEventAdapter):
    """GUI listener that fails before adapting a committed change set."""

    def apply(self, change_set: ChangeSet) -> None:
        """Raise deterministically to exercise dispatcher isolation."""
        _ = change_set
        raise RuntimeError("injected GUI listener failure")


class _NoOpRangeHistoryPort:
    """Unused range-history dependency for structure undo/redo tests."""

    def apply_range(self, _snapshot: object, *, source: str) -> HistoryChangeSet:
        """Return an inert application change set."""
        _ = source
        return HistoryChangeSet.empty()


class _NoOpHistoryRefreshPort:
    """Ignore legacy GUI refresh targets after history application."""

    def refresh(self, _target: object, _change_set: HistoryChangeSet) -> None:
        """Accept a refresh request without side effects."""


def test_spectrum_model_adapter_emits_component_added(qtbot: QtBot) -> None:
    """Adapter should re-emit component add events as Qt signals."""
    model = SpectrumModel()
    adapter = SpectrumModelEventAdapter(model)
    spy = QSignalSpy(adapter.component_added)

    component = AbsorberComponent(component_id="absorber-1")
    model.add_component(component)
    qtbot.wait(0)

    assert spy.count() == 1
    assert spy.at(0)[0] is component
    adapter.close()


def test_spectrum_model_adapter_emits_region_topology_change(qtbot: QtBot) -> None:
    """Adapter should carry the complete committed topology event unchanged."""
    model = SpectrumModel()
    adapter = SpectrumModelEventAdapter(model)
    spy = QSignalSpy(adapter.region_topology_changed)
    event = RegionTopologyChanged(
        created_region_ids=("created",),
        removed_region_ids=("removed",),
        impacted_surviving_region_ids=("survivor",),
        changed_surviving_line_ids=("line",),
    )

    model.publish_storage_changes(ChangeSet.of(event))
    qtbot.wait(0)

    assert spy.count() == 1
    assert spy.at(0)[0] == event
    adapter.close()


def test_failing_gui_event_listener_does_not_block_later_listener(qtbot: QtBot) -> None:
    """A broken GUI adapter must not prevent another adapter from observing a commit."""
    model = SpectrumModel()
    failing = _FailingModelEventAdapter(model)
    succeeding = SpectrumModelEventAdapter(model)
    spy = QSignalSpy(succeeding.region_topology_changed)

    model.publish_storage_changes(ChangeSet.of(RegionTopologyChanged()))
    qtbot.wait(0)

    assert spy.count() == 1
    failing.close()
    succeeding.close()


def test_direct_structure_commit_reaches_topology_signal(qtbot: QtBot) -> None:
    """A direct structure operation should publish through the model adapter."""
    project = _project_with_regions(("primary", "secondary"))
    adapter = SpectrumModelEventAdapter(project.model)
    spy = QSignalSpy(adapter.region_topology_changed)

    result = StructureOperationUseCase().merge_regions(
        project, group_ids=["primary", "secondary"], history_recorder=None
    )
    qtbot.wait(0)

    assert result is not None
    assert spy.count() == 1
    assert spy.at(0)[0].removed_region_ids == ("secondary",)
    adapter.close()


def test_identify_registration_commit_reaches_topology_signal(qtbot: QtBot) -> None:
    """An Identify registration should publish through the same model adapter."""
    project = SpectroscopyProject(name="identify-topology-signal")
    temporary_line = project.identify_state.add_temporary_line(
        "C IV",
        1000.0,
        1005.0,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="civ-1548",
            rest_wavelength=1000.0,
            center_z=0.0,
            multiplet_id="civ-doublet",
            multiplet_label="C IV",
            transition_name="C IV 1548",
            oscillator_strength=0.19,
            gamma_value=2.64e8,
            tie_group_key="",
        ),
    )
    request = AtomicRegisterSelectedLinesRequest(
        project=project,
        session=project.identify_state,
        temporary_lines=(
            TemporaryLineSnapshot(
                temporary_line_id=temporary_line.temporary_line_id,
                species=temporary_line.species,
                lambda_min=temporary_line.lambda_min,
                lambda_max=temporary_line.lambda_max,
                creation_method=temporary_line.creation_method,
                line_id=temporary_line.line_id,
                rest_wavelength=temporary_line.rest_wavelength,
                center_z=temporary_line.center_z,
                multiplet_id=temporary_line.multiplet_id,
                multiplet_label=temporary_line.multiplet_label,
                transition_name=temporary_line.transition_name,
                oscillator_strength=temporary_line.oscillator_strength,
                gamma_value=temporary_line.gamma_value,
                analysis_half_width=LineAnalysisHalfWidth(temporary_line.analysis_half_width_kms),
                tie_group_key=temporary_line.tie_group_key,
            ),
        ),
        existing_regions=(),
        region_line_memberships=(),
        multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
        unknown_label="Unknown",
    )
    adapter = SpectrumModelEventAdapter(project.model)
    spy = QSignalSpy(adapter.region_topology_changed)

    result = AtomicIdentifyRegistrationUseCase().register(request)
    qtbot.wait(0)

    assert result.changed
    assert result.outcome is not None
    assert spy.count() == 1
    assert set(spy.at(0)[0].created_region_ids) == set(result.outcome.created_region_ids)
    adapter.close()


def test_structure_undo_redo_each_reaches_topology_signal(qtbot: QtBot) -> None:
    """Both history directions should publish the executor-owned topology event."""
    project = _project_with_regions(("primary", "secondary"))
    history = CommandHistory()
    history.set_applier(
        HistoryApplyUseCase(
            project_provider=lambda: project,
            range_port=_NoOpRangeHistoryPort(),
            refresh_port=_NoOpHistoryRefreshPort(),
            resolution_notifier_provider=lambda: None,
        )
    )
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().merge_regions(
        project, group_ids=["primary", "secondary"], history_recorder=recorder
    )
    adapter = SpectrumModelEventAdapter(project.model)
    spy = QSignalSpy(adapter.region_topology_changed)

    assert history.undo().success
    assert history.redo().success
    qtbot.wait(0)

    assert spy.count() == 2
    assert spy.at(0)[0].created_region_ids == ("secondary",)
    assert spy.at(1)[0].removed_region_ids == ("secondary",)
    adapter.close()


def _project_with_regions(region_ids: tuple[str, ...]) -> SpectroscopyProject:
    """Build one single-line region per stable ID."""
    project = SpectroscopyProject(name="topology-signal")
    for index, region_id in enumerate(region_ids, start=1):
        line_id = f"line-{index}"
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=[line_id]
        )
        project.absorption_lines[line_id] = AbsorptionLine(
            line_id=line_id,
            species="C IV",
            rest_wavelength=1548.2 + index,
            center_z=2.0,
            window_kms=120.0,
            multiplet_label="C IV",
            transition_name=line_id,
            oscillator_strength=0.19,
            gamma_value=1e8,
            region_id=region_id,
        )
    return project
