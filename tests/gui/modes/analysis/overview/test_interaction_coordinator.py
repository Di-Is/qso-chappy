"""Tests for structure interaction coordinator boundaries."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.interaction_coordinator import (
    StructureInteractionCoordinator,
    StructureInteractionPorts,
)
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.gui.modes.analysis.overview.adapters import StructureOperationAdapter
from chappy.gui.modes.analysis.overview import interaction_coordinator as interaction_module
from chappy.gui.modes.analysis.overview.operation_controller import StructureOperationController


@dataclass
class _Panel:
    """Record structure panel mutations after a committed operation."""

    clear_count: int = 0
    refresh_count: int = 0
    unlink_enabled: bool = False

    def clear_selection(self) -> None:
        """Record selection clearing."""
        self.clear_count += 1

    def refresh(self) -> None:
        """Record an unexpected legacy panel refresh without failing incidentally."""
        self.refresh_count += 1

    def group_entry(self, _identifier: str) -> None:
        """Return no presentation entry for this test double."""
        return None

    def set_unlink_enabled(self, enabled: bool) -> None:
        """Record unlink action availability."""
        self.unlink_enabled = enabled

    def set_structure_actions_enabled(
        self, *, merge: bool, split: bool, delete: bool, unlink: bool
    ) -> None:
        """Record the unlink member of the complete visible-action state."""
        _ = merge, split, delete
        self.unlink_enabled = unlink


@dataclass
class _ClearFailurePanel(_Panel):
    """Panel double whose selection-clear observer fails after a commit."""

    def clear_selection(self) -> None:
        """Record and inject one selection-clear failure."""
        self.clear_count += 1
        raise RuntimeError("injected panel clear failure")


@dataclass
class _MenuAction:
    """Minimal action double for structure context-menu availability."""

    text: str
    enabled: bool = True

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Record action availability."""
        self.enabled = enabled


@dataclass
class _Menu:
    """Minimal menu double that captures added actions."""

    actions: list[_MenuAction]

    def addAction(self, text: str) -> _MenuAction:  # noqa: N802
        """Add and return one action double."""
        action = _MenuAction(text)
        self.actions.append(action)
        return action

    def exec(self, _global_pos: QPoint) -> None:
        """Dismiss the menu without triggering an action."""
        return None


def _line(
    *,
    line_id: str = "line-1",
    rest_wavelength: float = 1000.0,
    center_z: float = 1.0,
    multiplet_ids: list[str] | None = None,
) -> AbsorptionLine:
    """Create a structure absorption line."""
    return AbsorptionLine(
        line_id=line_id,
        species="Mg II",
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=150.0,
        multiplet_label="Mg II",
        transition_name="Mg II 1000",
        oscillator_strength=0.6,
        gamma_value=1.0e8,
        multiplet_ids=multiplet_ids or [],
    )


def _linked_project() -> SpectroscopyProject:
    """Create one materialized two-line linked group in one region."""
    project = SpectroscopyProject()
    blue = _line(line_id="blue", multiplet_ids=["red"])
    red = _line(line_id="red", multiplet_ids=["blue"])
    blue.region_id = "region"
    red.region_id = "region"
    project.absorption_lines.update({"blue": blue, "red": red})
    project.absorption_regions["region"] = AbsorptionRegion(
        region_id="region", line_ids=["blue", "red"]
    )
    revision = AnalysisRevision(2)
    project.set_region_analysis_states(
        (
            RegionAnalysisState(
                region_id="region",
                current_revision=revision,
                artifact=AnalysisArtifact(
                    region_id="region",
                    source_revision=revision,
                    fit_summary=FitSummary(chi_squared=2.0),
                ),
            ),
        )
    )
    return project


def _coordinator(
    qtbot: QtBot,
    project_provider: Callable[[], SpectroscopyProject | None],
    focus_calls: list[tuple[float, float]],
) -> StructureInteractionCoordinator:
    """Create a structure interaction coordinator with captured focus calls."""
    parent = QWidget()
    qtbot.addWidget(parent)
    ports = StructureInteractionPorts(
        project_provider=project_provider,
        history_recorder_provider=lambda: None,
        focus_range_callback=lambda start, end: focus_calls.append((start, end)),
        status_callback=lambda _message, _timeout, _undo_hint: None,
        delete_confirmation=lambda _impact, _project: True,
        unlink_confirmation=lambda _impact, _project: True,
        context_menu_parent=parent,
    )
    return StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=ports,
    )


def test_line_activation_without_project_is_user_recovery(qtbot: QtBot) -> None:
    """No project should skip focusing instead of failing."""
    focus_calls: list[tuple[float, float]] = []
    coordinator = _coordinator(qtbot, lambda: None, focus_calls)

    coordinator.handle_line_activated("line-1")

    assert focus_calls == []


def test_line_activation_missing_line_is_user_recovery(qtbot: QtBot) -> None:
    """A stale line id should skip focusing instead of failing."""
    project = SpectroscopyProject()
    focus_calls: list[tuple[float, float]] = []
    coordinator = _coordinator(qtbot, lambda: project, focus_calls)

    coordinator.handle_line_activated("missing")

    assert focus_calls == []


def test_line_activation_focuses_valid_line(qtbot: QtBot) -> None:
    """A valid line should focus around its observed wavelength."""
    project = SpectroscopyProject()
    project.absorption_lines["line-1"] = _line(rest_wavelength=1000.0, center_z=1.0)
    focus_calls: list[tuple[float, float]] = []
    coordinator = _coordinator(qtbot, lambda: project, focus_calls)

    coordinator.handle_line_activated("line-1")

    assert focus_calls == [(1996.0, 2004.0)]


def test_line_activation_rejects_invalid_line_physics(qtbot: QtBot) -> None:
    """Invalid required line fields should fail fast."""
    project = SpectroscopyProject()
    project.absorption_lines["line-1"] = _line(rest_wavelength=math.nan)
    focus_calls: list[tuple[float, float]] = []
    coordinator = _coordinator(qtbot, lambda: project, focus_calls)

    with pytest.raises(ValueError, match="rest_wavelength"):
        coordinator.handle_line_activated("line-1")

    assert focus_calls == []


def test_context_menu_exposes_topology_gated_unlink_action(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Context-menu unlink uses the same linked-line eligibility as the visible button."""
    project = _linked_project()
    project.absorption_lines["single"] = _line(line_id="single")
    project.absorption_lines["single"].region_id = "region"
    project.absorption_regions["region"].line_ids.append("single")
    focus_calls: list[tuple[float, float]] = []
    coordinator = _coordinator(qtbot, lambda: project, focus_calls)
    menus: list[_Menu] = []

    def create_menu(_parent: QWidget, _title: str) -> _Menu:
        menu = _Menu([])
        menus.append(menu)
        return menu

    monkeypatch.setattr(interaction_module, "create_styled_menu", create_menu)

    coordinator.handle_context_menu(QPoint(), [], ["blue"])
    coordinator.handle_context_menu(QPoint(), [], ["single"])

    linked_action = next(
        action for action in menus[0].actions if action.text == "Unlink these linked lines"
    )
    independent_action = next(
        action for action in menus[1].actions if action.text == "Unlink these linked lines"
    )
    assert linked_action.enabled is True
    assert independent_action.enabled is False


def test_delete_confirmation_cancel_preserves_all_scientific_and_ui_state(qtbot: QtBot) -> None:
    """Cancel after preview leaves project, history, selection, and analysis unchanged."""
    project = SpectroscopyProject()
    line = _line()
    line.region_id = "region"
    project.absorption_lines[line.line_id] = line
    project.absorption_regions["region"] = AbsorptionRegion(
        region_id="region", line_ids=[line.line_id]
    )
    revision = AnalysisRevision(2)
    project.set_region_analysis_states(
        (
            RegionAnalysisState(
                region_id="region",
                current_revision=revision,
                artifact=AnalysisArtifact(
                    region_id="region",
                    source_revision=revision,
                    fit_summary=FitSummary(chi_squared=2.0),
                ),
            ),
        )
    )
    before = (
        project.modified,
        tuple(project.absorption_regions),
        tuple(project.absorption_lines),
        project.stored_region_analysis_states_for_transaction(),
        line.needs_optimization,
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    confirmed_impacts: list[object] = []
    history_provider_calls: list[None] = []
    ports = StructureInteractionPorts(
        project_provider=lambda: project,
        history_recorder_provider=lambda: history_provider_calls.append(None),
        focus_range_callback=lambda _start, _end: None,
        status_callback=lambda _message, _timeout, _undo_hint: None,
        delete_confirmation=lambda impact, _project: confirmed_impacts.append(impact) or False,
        unlink_confirmation=lambda _impact, _project: True,
        context_menu_parent=parent,
    )
    coordinator = StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=ports,
    )
    panel = _Panel()
    coordinator.set_panel(panel)
    coordinator.handle_selection(["region"], [])

    assert coordinator.execute_delete() is False

    assert len(confirmed_impacts) == 1
    impact = confirmed_impacts[0]
    assert getattr(impact, "removed_region_ids") == ("region",)
    assert getattr(impact, "removed_line_ids") == ("line-1",)
    assert history_provider_calls == []
    assert coordinator.selection == (["region"], [])
    assert panel.clear_count == 0
    assert (
        project.modified,
        tuple(project.absorption_regions),
        tuple(project.absorption_lines),
        project.stored_region_analysis_states_for_transaction(),
        line.needs_optimization,
    ) == before


def test_unlink_confirmation_cancel_preserves_all_scientific_and_ui_state(qtbot: QtBot) -> None:
    """Cancel after unlink preview leaves topology, evidence, history, and UI untouched."""
    project = _linked_project()
    before = (
        project.modified,
        tuple(
            (line_id, tuple(line.multiplet_ids), line.needs_optimization)
            for line_id, line in project.absorption_lines.items()
        ),
        project.stored_region_analysis_states_for_transaction(),
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    confirmed_impacts: list[object] = []
    history_provider_calls: list[None] = []
    ports = StructureInteractionPorts(
        project_provider=lambda: project,
        history_recorder_provider=lambda: history_provider_calls.append(None),
        focus_range_callback=lambda _start, _end: None,
        status_callback=lambda _message, _timeout, _undo_hint: None,
        delete_confirmation=lambda _impact, _project: True,
        unlink_confirmation=lambda impact, _project: confirmed_impacts.append(impact) or False,
        context_menu_parent=parent,
    )
    coordinator = StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=ports,
    )
    panel = _Panel()
    coordinator.set_panel(panel)
    coordinator.handle_selection([], ["blue"])

    assert panel.unlink_enabled is True
    assert coordinator.execute_unlink() is False
    assert len(confirmed_impacts) == 1
    assert getattr(confirmed_impacts[0], "changed_line_ids") == ("blue", "red")
    assert history_provider_calls == []
    assert coordinator.selection == ([], ["blue"])
    assert panel.clear_count == 0
    assert (
        project.modified,
        tuple(
            (line_id, tuple(line.multiplet_ids), line.needs_optimization)
            for line_id, line in project.absorption_lines.items()
        ),
        project.stored_region_analysis_states_for_transaction(),
    ) == before


def test_unlink_no_change_stops_before_confirmation_and_history(qtbot: QtBot) -> None:
    """An independent line produces no confirmation, history, or UI mutation."""
    project = SpectroscopyProject()
    line = _line()
    line.region_id = "region"
    project.absorption_lines[line.line_id] = line
    project.absorption_regions["region"] = AbsorptionRegion(
        region_id="region", line_ids=[line.line_id]
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    confirmation_calls: list[None] = []
    history_provider_calls: list[None] = []
    ports = StructureInteractionPorts(
        project_provider=lambda: project,
        history_recorder_provider=lambda: history_provider_calls.append(None),
        focus_range_callback=lambda _start, _end: None,
        status_callback=lambda _message, _timeout, _undo_hint: None,
        delete_confirmation=lambda _impact, _project: True,
        unlink_confirmation=lambda _impact, _project: confirmation_calls.append(None) or True,
        context_menu_parent=parent,
    )
    coordinator = StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=ports,
    )
    panel = _Panel()
    coordinator.set_panel(panel)
    coordinator.handle_selection([], [line.line_id])

    assert coordinator.execute_unlink() is False
    assert panel.unlink_enabled is False
    assert confirmation_calls == []
    assert history_provider_calls == []
    assert panel.clear_count == 0


def test_confirmed_unlink_commits_and_clears_interaction_state(qtbot: QtBot) -> None:
    """Confirmed unlink leaves refresh to topology observers and clears interaction state."""
    project = _linked_project()
    parent = QWidget()
    qtbot.addWidget(parent)
    ports = StructureInteractionPorts(
        project_provider=lambda: project,
        history_recorder_provider=lambda: None,
        focus_range_callback=lambda _start, _end: None,
        status_callback=lambda _message, _timeout, _undo_hint: None,
        delete_confirmation=lambda _impact, _project: True,
        unlink_confirmation=lambda _impact, _project: True,
        context_menu_parent=parent,
    )
    coordinator = StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=ports,
    )
    panel = _Panel()
    coordinator.set_panel(panel)
    coordinator.handle_selection([], ["blue"])

    assert coordinator.execute_unlink() is True
    assert project.absorption_lines["blue"].multiplet_ids == []
    assert project.absorption_lines["red"].multiplet_ids == []
    assert coordinator.selection == ([], [])
    assert panel.clear_count == 1
    assert panel.unlink_enabled is False


def test_postcommit_clear_failure_does_not_skip_other_observers(qtbot: QtBot) -> None:
    """A broken selection clear cannot suppress state and status observers after commit."""
    project = _linked_project()
    parent = QWidget()
    qtbot.addWidget(parent)
    status_messages: list[str] = []
    ports = StructureInteractionPorts(
        project_provider=lambda: project,
        history_recorder_provider=lambda: None,
        focus_range_callback=lambda _start, _end: None,
        status_callback=lambda message, _timeout, _undo_hint: status_messages.append(message),
        delete_confirmation=lambda _impact, _project: True,
        unlink_confirmation=lambda _impact, _project: True,
        context_menu_parent=parent,
    )
    coordinator = StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=ports,
    )
    panel = _ClearFailurePanel()
    coordinator.set_panel(panel)
    coordinator.handle_selection([], ["blue"])

    assert coordinator.execute_unlink() is True

    assert project.absorption_lines["blue"].multiplet_ids == []
    assert project.absorption_lines["red"].multiplet_ids == []
    assert coordinator.selection == ([], [])
    assert panel.clear_count == 1
    assert status_messages[-1] == "Unlinked 2 linked lines."
