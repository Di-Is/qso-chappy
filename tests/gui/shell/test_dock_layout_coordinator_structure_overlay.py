"""Tests for structure-mode project updates coordinated by DockLayoutCoordinator."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMainWindow, QWidget

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.editing_mode import EditingMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.shell.dock_layout_coordinator import DockLayoutCoordinator
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from scripts.i18n_lupdate import run_lupdate

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from chappy.application.history import (
        AbsorptionLineSnapshot,
        StructureDeleteModelHistorySnapshot,
        StructureMoveHistoryPayload,
        StructureStateSnapshot,
        StructureUnlinkHistoryPayload,
    )
    from chappy.gui.modes.analysis.region_detail.model_addition_controller import (
        OptimizeModelAdditionUseCasePort,
    )
    from chappy.gui.modes.analysis.region_detail.ui_facade import RegionDetailUi
    from chappy.gui.shell.dependencies import RegionDetailFactory
    from pytestqt.qtbot import QtBot


def _unused_region_detail_factory(**_: object) -> "RegionDetailUi":
    """Fail if invoked; these tests never build the mode panel."""
    msg = "Region Detail factory should not be invoked in this test."
    raise AssertionError(msg)


class _StatusSignal:
    """Record status messages emitted by the coordinator."""

    def __init__(self) -> None:
        """Initialize an empty message history."""
        self.messages: list[tuple[str, int]] = []

    def emit(self, message: str, timeout_ms: int = 2500) -> None:
        """Store a status message emission."""
        self.messages.append((message, timeout_ms))


@dataclass
class _DataControlPanel:
    """Shared data-control panel placeholder."""


@dataclass
class _RecordingStructurePanel:
    """Minimal structure panel substitute that records UI refresh state."""

    clear_count: int = 0
    refresh_count: int = 0
    project: SpectroscopyProject | None = None
    restored_selection: tuple[list[str], list[str]] | None = None
    unlink_enabled: bool = False

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Record the active project assigned by the coordinator."""
        self.project = project

    def clear_selection(self) -> None:
        """Record that selection clearing was requested."""
        self.clear_count += 1

    def refresh(self) -> None:
        """Record that a visual refresh was requested."""
        self.refresh_count += 1

    def restore_selection(self, group_ids: list[str], line_ids: list[str]) -> None:
        """Record restored structure selection."""
        self.restored_selection = (list(group_ids), list(line_ids))

    def set_unlink_enabled(self, enabled: bool) -> None:
        """Record availability of the explicit linked-line unlink operation."""
        self.unlink_enabled = enabled

    def set_structure_actions_enabled(
        self, *, merge: bool, split: bool, delete: bool, unlink: bool
    ) -> None:
        """Record the unlink member of the complete visible-action state."""
        _ = merge, split, delete
        self.unlink_enabled = unlink


class _RecordingOptimizePanel:
    """Minimal optimize panel substitute recording history refresh calls."""

    def __init__(self) -> None:
        """Initialize captured calls."""
        self.history_refreshes: list[str | None] = []

    def refresh_for_history(self, region_id: str | None = None) -> None:
        """Record history refresh."""
        self.history_refreshes.append(region_id)


class _StructureHistoryRecorder:
    """Structure history recorder test double with no persisted side effects."""

    def record_structure_move_linked_lines(self, payload: "StructureMoveHistoryPayload") -> None:
        """Accept a structure move history event."""

    @contextmanager
    def atomic_recording(self) -> "Iterator[None]":
        """Provide a no-op atomic recording scope."""
        yield

    def record_structure_split(
        self,
        expanded_line_ids: tuple[str, ...],
        source_region_id: str,
        new_region_id: str,
        before: "StructureStateSnapshot",
        after: "StructureStateSnapshot",
    ) -> None:
        """Accept a structure split history event."""

    def record_structure_merge(
        self,
        primary_region_id: str,
        secondary_region_ids: tuple[str, ...],
        before: "StructureStateSnapshot",
        after: "StructureStateSnapshot",
    ) -> None:
        """Accept a structure merge history event."""

    def record_structure_delete(
        self,
        target_region_ids: tuple[str, ...],
        target_line_ids: tuple[str, ...],
        deleted_lines: tuple["AbsorptionLineSnapshot", ...],
        before: "StructureStateSnapshot",
        after: "StructureStateSnapshot",
        deleted_model_history: "StructureDeleteModelHistorySnapshot | None",
    ) -> None:
        """Accept a structure delete history event."""

    def record_structure_unlink(self, payload: "StructureUnlinkHistoryPayload") -> None:
        """Accept one linked-line unlink history event."""


@dataclass
class _StructureHarness:
    """Objects used by structure operation tests."""

    coordinator: DockLayoutCoordinator
    main_window: _MainWindow
    panel: _RecordingStructurePanel


class _MainWindow(QMainWindow):
    """Main window test double with concrete project and status state."""

    def __init__(self) -> None:
        """Create a window with the attributes used by DockLayoutCoordinator."""
        super().__init__()
        self.current_project = SpectroscopyProject()
        self._history_recorder = _StructureHistoryRecorder()
        self.status_message = _StatusSignal()
        self.data_control_panel = _DataControlPanel()


DOCK_LAYOUT_COORDINATOR_QT_SOURCES = {
    "Fitting Ranges",
    "Focused spectrum to {minimum:.1f}–{maximum:.1f} Å",
    "Press {undo_shortcut} to undo",
}

ORGANIZE_INTERACTION_COORDINATOR_QT_SOURCES = {
    "No selection",
    "Analysis Structure",
    "Merge selected regions",
    "Split line into new region",
    "Delete selection",
    "Move spectrum to selection",
    "Moved {count} lines to {destination}.",
    "Merged {count} regions into {name}.",
    'Created new region "{name}" from the selection.',
    "{count} regions",
    "{count} lines",
    "Deleted {summary}.",
    "new region",
}

ORGANIZE_OPERATION_CONTROLLER_QT_SOURCES = {
    "No project loaded.",
    "Failed to move selected lines.",
    "Select at least two regions to merge.",
    "Failed to merge the selected regions.",
    "Select exactly one line to split.",
    "Failed to split the selected line.",
    "Select regions or lines to delete.",
    "Failed to delete the selected items.",
}


def _line(line_id: str, region_id: str, *, center_z: float = 1.0) -> AbsorptionLine:
    """Create an absorption line assigned to a region."""
    return AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=1215.67,
        center_z=center_z,
        window_kms=150.0,
        multiplet_label="",
        transition_name="Ly-alpha",
        oscillator_strength=0.4164,
        gamma_value=6.265e8,
        region_id=region_id,
    )


def _add_region(project: SpectroscopyProject, region_id: str, line_ids: list[str]) -> None:
    """Add a region and matching absorption lines to a project."""
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=list(line_ids)
    )
    for index, line_id in enumerate(line_ids):
        project.absorption_lines[line_id] = _line(line_id, region_id, center_z=1.0 + index * 0.001)


def _select_for_structure(
    coordinator: DockLayoutCoordinator, group_ids: list[str], line_ids: list[str]
) -> None:
    """Set structure selection through the structure interaction coordinator."""
    coordinator._structure_interactions.handle_selection(group_ids, line_ids)


def test_refresh_structure_panel_requires_panel(qtbot: "QtBot") -> None:
    """Structure refresh requires the dock structure panel to be composed."""
    main_window = _MainWindow()
    qtbot.addWidget(main_window)
    side_panel_container = QWidget(main_window)
    qtbot.addWidget(side_panel_container)
    coordinator = DockLayoutCoordinator(
        main_window,
        side_panel_container=side_panel_container,
        optimize_model_addition_usecase=cast("OptimizeModelAdditionUseCasePort", object()),
        region_detail_factory=cast("RegionDetailFactory", _unused_region_detail_factory),
    )

    with pytest.raises(RuntimeError, match="requires a structure panel"):
        coordinator.refresh_structure_panel()


def test_refresh_optimize_panel_requires_panel(qtbot: "QtBot") -> None:
    """Optimize history refresh requires the dock optimize panel to be composed."""
    main_window = _MainWindow()
    qtbot.addWidget(main_window)
    side_panel_container = QWidget(main_window)
    qtbot.addWidget(side_panel_container)
    coordinator = DockLayoutCoordinator(
        main_window,
        side_panel_container=side_panel_container,
        optimize_model_addition_usecase=cast("OptimizeModelAdditionUseCasePort", object()),
        region_detail_factory=cast("RegionDetailFactory", _unused_region_detail_factory),
    )

    with pytest.raises(RuntimeError, match="requires an optimize panel"):
        coordinator.refresh_optimize_panel_for_history("region-1")


def test_refresh_structure_panel_restores_selection(structure_harness: _StructureHarness) -> None:
    """Structure refresh preserves the current selection."""
    _select_for_structure(structure_harness.coordinator, ["region-1"], ["line-1"])

    structure_harness.coordinator.refresh_structure_panel()

    assert structure_harness.panel.refresh_count == 1
    assert structure_harness.panel.restored_selection == (["region-1"], ["line-1"])


def test_refresh_optimize_panel_uses_required_panel(qtbot: "QtBot") -> None:
    """Optimize history refresh delegates to the required optimize panel."""
    main_window = _MainWindow()
    qtbot.addWidget(main_window)
    side_panel_container = QWidget(main_window)
    qtbot.addWidget(side_panel_container)
    coordinator = DockLayoutCoordinator(
        main_window,
        side_panel_container=side_panel_container,
        optimize_model_addition_usecase=cast("OptimizeModelAdditionUseCasePort", object()),
        region_detail_factory=cast("RegionDetailFactory", _unused_region_detail_factory),
    )
    optimize_panel = _RecordingOptimizePanel()
    coordinator._region_detail_ui = cast("RegionDetailUi", optimize_panel)

    coordinator.refresh_optimize_panel_for_history("region-1")

    assert optimize_panel.history_refreshes == ["region-1"]


def test_analysis_half_width_handler_refreshes_all_scoped_surfaces(qtbot: "QtBot") -> None:
    """Committed analysis widths should refresh wavelength, overlay, and velocity views."""
    main_window = _MainWindow()
    qtbot.addWidget(main_window)
    side_panel_container = QWidget(main_window)
    qtbot.addWidget(side_panel_container)
    coordinator = DockLayoutCoordinator(
        main_window,
        side_panel_container=side_panel_container,
        optimize_model_addition_usecase=cast("OptimizeModelAdditionUseCasePort", object()),
        region_detail_factory=cast("RegionDetailFactory", _unused_region_detail_factory),
    )

    with (
        patch.object(
            coordinator, "refresh_optimize_wavelength_model_residual", return_value=True
        ) as wavelength_refresh,
        patch.object(coordinator, "_refresh_line_overlays_for_mode") as overlay_refresh,
        patch.object(coordinator, "_refresh_visible_optimize_velocity_plot") as velocity_refresh,
    ):
        coordinator._handle_optimize_analysis_half_width_changed("region-1")

    wavelength_refresh.assert_called_once_with("region-1")
    overlay_refresh.assert_called_once_with(EditingMode.ANALYSIS)
    velocity_refresh.assert_called_once_with()


@pytest.fixture
def structure_harness(qtbot: "QtBot", monkeypatch: pytest.MonkeyPatch) -> _StructureHarness:
    """Create DockLayoutCoordinator with real project state and a recording panel."""
    monkeypatch.setattr(
        "chappy.gui.shell.dock_layout_coordinator.confirm_structure_delete",
        lambda _parent, _impact, _project, *, undo_shortcut: bool(undo_shortcut),
    )
    main_window = _MainWindow()
    qtbot.addWidget(main_window)
    side_panel_container = QWidget(main_window)
    qtbot.addWidget(side_panel_container)
    coordinator = DockLayoutCoordinator(
        main_window,
        side_panel_container=side_panel_container,
        optimize_model_addition_usecase=cast("OptimizeModelAdditionUseCasePort", object()),
        region_detail_factory=cast("RegionDetailFactory", _unused_region_detail_factory),
    )
    panel = _RecordingStructurePanel()
    coordinator.structure_panel = cast(StructureSidePanel, panel)
    return _StructureHarness(coordinator=coordinator, main_window=main_window, panel=panel)


def test_lupdate_extracts_dock_layout_coordinator_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated DockLayoutCoordinator source text."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "dock_layout_coordinator_ja.ts"
    run_lupdate(
        source_dirs=[Path("src/chappy/gui/shell/dock_layout_coordinator.py")], ts_output=ts_path
    )

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    assert DOCK_LAYOUT_COORDINATOR_QT_SOURCES <= sources
    assert not any("GUI__" in source for source in sources)


def test_lupdate_extracts_structure_operation_controller_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts structure operation controller source text."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "structure_operation_controller_ja.ts"
    run_lupdate(
        source_dirs=[Path("src/chappy/gui/modes/analysis/overview/operation_controller.py")],
        ts_output=ts_path,
    )

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    assert ORGANIZE_OPERATION_CONTROLLER_QT_SOURCES <= sources
    assert not any("GUI__" in source for source in sources)


def test_lupdate_extracts_structure_interaction_coordinator_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts structure interaction coordinator source text."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "structure_interaction_coordinator_ja.ts"
    run_lupdate(
        source_dirs=[Path("src/chappy/gui/modes/analysis/overview/interaction_coordinator.py")],
        ts_output=ts_path,
    )

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    assert ORGANIZE_INTERACTION_COORDINATOR_QT_SOURCES <= sources
    assert not any("GUI__" in source for source in sources)


class TestStructureInteractionPublication:
    """Tests that interaction state resets while topology observers own refresh."""

    def test_delete_removes_region_and_refreshes_structure_overlay(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Delete removes selected region data and emits an overlay update."""
        project = structure_harness.main_window.current_project
        _add_region(project, "region_1", ["line_1"])
        _select_for_structure(structure_harness.coordinator, ["region_1"], [])
        result = structure_harness.coordinator._execute_structure_delete()

        assert result is True
        assert "region_1" not in project.absorption_regions
        assert "line_1" not in project.absorption_lines
        assert structure_harness.panel.clear_count == 1
        assert structure_harness.panel.refresh_count == 0

    def test_delete_without_selection_preserves_project_and_does_not_emit(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Empty delete requests fail without overlay updates."""
        project = structure_harness.main_window.current_project
        _add_region(project, "region_1", ["line_1"])
        _select_for_structure(structure_harness.coordinator, [], [])
        result = structure_harness.coordinator._execute_structure_delete()

        assert result is False
        assert list(project.absorption_regions) == ["region_1"]
        assert list(project.absorption_lines) == ["line_1"]
        assert structure_harness.panel.clear_count == 0
        assert structure_harness.panel.refresh_count == 0

    def test_merge_moves_lines_into_primary_region_and_refreshes_overlay(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Merge uses the real project merge behavior and emits one update."""
        project = structure_harness.main_window.current_project
        _add_region(project, "region_1", ["line_1"])
        _add_region(project, "region_2", ["line_2"])
        _select_for_structure(structure_harness.coordinator, ["region_1", "region_2"], [])
        result = structure_harness.coordinator._execute_structure_merge()

        assert result is True
        assert list(project.absorption_regions) == ["region_1"]
        assert project.absorption_regions["region_1"].line_ids == ["line_1", "line_2"]
        assert project.absorption_lines["line_2"].region_id == "region_1"
        assert structure_harness.panel.clear_count == 1
        assert structure_harness.panel.refresh_count == 0

    def test_merge_with_single_group_preserves_project_and_does_not_emit(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Single-group merge requests fail before project mutation."""
        project = structure_harness.main_window.current_project
        _add_region(project, "region_1", ["line_1"])
        _select_for_structure(structure_harness.coordinator, ["region_1"], [])
        result = structure_harness.coordinator._execute_structure_merge()

        assert result is False
        assert list(project.absorption_regions) == ["region_1"]
        assert project.absorption_regions["region_1"].line_ids == ["line_1"]
        assert structure_harness.panel.clear_count == 0
        assert structure_harness.panel.refresh_count == 0

    def test_split_moves_selected_line_to_new_region_and_refreshes_overlay(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Split creates a new region using the real project line move behavior."""
        project = structure_harness.main_window.current_project
        _add_region(project, "source_region", ["line_1", "line_2"])
        original_region_ids = set(project.absorption_regions)
        _select_for_structure(structure_harness.coordinator, [], ["line_1"])
        result = structure_harness.coordinator._execute_structure_split()

        new_region_ids = set(project.absorption_regions) - original_region_ids
        assert result is True
        assert len(new_region_ids) == 1
        new_region_id = new_region_ids.pop()
        assert project.absorption_regions["source_region"].line_ids == ["line_2"]
        assert project.absorption_regions[new_region_id].line_ids == ["line_1"]
        assert project.absorption_lines["line_1"].region_id == new_region_id
        assert structure_harness.panel.clear_count == 1
        assert structure_harness.panel.refresh_count == 0

    def test_split_without_line_selection_preserves_project_and_does_not_emit(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Split requires exactly one selected line."""
        project = structure_harness.main_window.current_project
        _add_region(project, "source_region", ["line_1"])
        _select_for_structure(structure_harness.coordinator, [], [])
        result = structure_harness.coordinator._execute_structure_split()

        assert result is False
        assert list(project.absorption_regions) == ["source_region"]
        assert project.absorption_regions["source_region"].line_ids == ["line_1"]
        assert structure_harness.panel.clear_count == 0
        assert structure_harness.panel.refresh_count == 0

    def test_line_move_reassigns_line_to_target_region_and_refreshes_overlay(
        self, structure_harness: _StructureHarness
    ) -> None:
        """Moving a line updates project ownership and emits one overlay update."""
        project = structure_harness.main_window.current_project
        _add_region(project, "source_region", ["line_1"])
        _add_region(project, "target_region", [])
        structure_harness.coordinator._handle_structure_line_move("target_region", ["line_1"])

        assert "source_region" not in project.absorption_regions
        assert project.absorption_regions["target_region"].line_ids == ["line_1"]
        assert project.absorption_lines["line_1"].region_id == "target_region"
        assert structure_harness.panel.clear_count == 0
        assert structure_harness.panel.refresh_count == 0
