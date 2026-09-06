"""StructureSidePanel empty-state behavior tests."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QPushButton, QTableView, QTreeWidget, QTreeWidgetItem

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from chappy.gui.modes.analysis.overview.review_widget import AnalysisOverviewReviewWidget
from chappy.presentation.analysis.structure.tree_presenter import StructureRegionEntry
from scripts.i18n_lupdate import run_lupdate


if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


ORGANIZE_SIDE_PANEL_QT_SOURCES = {
    "Edit regions",
    "Back to Overview",
    "Return to Analysis Overview (Alt+Left)",
    "Load absorber data to manage regions and lines here.",
    "Observed range: {minimum:.2f} – {maximum:.2f} Å",
    "Unknown",
    "{species} {wavelengths} [z={redshift}, ±{window} km/s]",
    "(λ: {range_text} Å)",
    "(1 line)",
    "({count} lines)",
    "Drop here to create a new region",
    "Drag lines here to create a new region.",
}


def _two_region_project() -> SpectroscopyProject:
    """Create two single-line regions selectable in the structure tree."""
    project = SpectroscopyProject(name="structure-side-panel-refresh")
    for region_id, line_id, rest_wavelength in (
        ("region-1", "line-1", 1215.67),
        ("region-2", "line-2", 1548.2),
    ):
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=[line_id]
        )
        project.absorption_lines[line_id] = AbsorptionLine(
            line_id=line_id,
            species="H I",
            rest_wavelength=rest_wavelength,
            center_z=1.0,
            window_kms=150.0,
            region_id=region_id,
            multiplet_label="",
            transition_name=f"H I {rest_wavelength:.1f}",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
    return project


def test_refresh_keeps_the_tree_selection_across_repeated_rebuilds(qtbot: "QtBot") -> None:
    """Refreshing twice must leave the structure selection untouched."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)
    panel.set_project(_two_region_project())
    panel.set_structure_editor_visible(True)
    panel.show()
    qtbot.waitUntil(panel.isVisible)
    panel.restore_selection(["region-2"], [])
    assert panel.get_selection() == (["region-2"], [])

    panel.refresh()
    panel.refresh()

    assert panel.get_selection() == (["region-2"], [])


def test_review_stays_visible_and_structure_editor_starts_closed(qtbot: "QtBot") -> None:
    """Overview remains primary while the existing structure editor is session-local."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)

    panel.show()
    qtbot.waitUntil(panel.isVisible)

    panel.refresh()

    tree = panel.findChild(QTreeWidget, "analysisStructureTree")
    review = panel.findChild(QTableView, "analysisOverviewReviewTable")
    placeholder = panel.findChild(QLabel, "structureSidePanelEmptyState")

    assert review is not None and review.isVisible()
    assert tree is not None and not tree.isVisible()
    assert placeholder is not None and not placeholder.isVisible()

    assert tree.topLevelItemCount() >= 1
    placeholder_item = tree.topLevelItem(tree.topLevelItemCount() - 1)
    assert placeholder_item is not None
    payload = placeholder_item.data(0, Qt.ItemDataRole.UserRole)
    assert isinstance(payload, dict)
    assert payload.get("type") == "new_group"


def test_panel_re_emits_review_region_delete_request(qtbot: "QtBot") -> None:
    """The panel forwards the review delete intent unchanged to the shell."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)
    review = panel.findChild(AnalysisOverviewReviewWidget)
    assert review is not None

    spy = QSignalSpy(panel.region_delete_requested)
    review.region_delete_requested.emit("region-1")

    assert spy.count() == 1
    assert spy.at(0)[0] == "region-1"


def test_back_button_emits_back_requested(qtbot: "QtBot") -> None:
    """The region editor page exposes an explicit way back to the Overview."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)
    back_button = panel.findChild(QPushButton, "structureSidePanelBackButton")
    assert back_button is not None

    spy = QSignalSpy(panel.back_requested)
    back_button.click()

    assert spy.count() == 1


def test_group_item_carries_full_text_tooltip_with_warning_explanation(qtbot: "QtBot") -> None:
    """Narrow widths keep label, range, count, and the ⚠ meaning reachable."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)
    entry = StructureRegionEntry(
        identifier="region-1",
        label="Region 1",
        wavelength_min=4000.0,
        wavelength_max=4100.0,
        components=[],
        linked_line_count=2,
        needs_optimization=True,
        shows_badges=True,
    )
    item = QTreeWidgetItem()

    panel._render_group_item_text(item, entry)

    tooltip = item.toolTip(0)
    assert "Region 1" in tooltip
    assert "4000-4100" in tooltip
    assert "2 lines" in tooltip
    assert "re-optimization" in tooltip
    assert "⚠️" in item.text(0)


def test_structure_action_buttons_use_short_labels_with_full_tooltips(qtbot: "QtBot") -> None:
    """Merge/Split/Delete/Unlink stay short at width 220 and explain via tooltips."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)

    buttons = {
        "analysisOverviewMergeButton": "Merge",
        "analysisOverviewSplitButton": "Split",
        "analysisOverviewDeleteButton": "Delete",
        "structureUnlinkLinkedLinesButton": "Unlink linked lines",
    }
    for object_name, label in buttons.items():
        button = panel.findChild(QPushButton, object_name)
        assert button is not None, object_name
        assert button.text() == label
        assert button.toolTip(), object_name


def test_structure_side_panel_migrated_gui_text_uses_qt_sources(qtbot: "QtBot") -> None:
    """Verify migrated structure GUI text is plain Qt source text."""
    panel = StructureSidePanel()
    qtbot.addWidget(panel)

    panel.refresh()

    header = panel.findChild(QLabel, "structureSidePanelHeader")
    placeholder = panel.findChild(QLabel, "structureSidePanelEmptyState")
    tree = panel.findChild(QTreeWidget, "analysisStructureTree")

    assert header is not None
    assert header.text() == "Edit regions"
    assert placeholder is not None
    assert placeholder.text() == "Load absorber data to manage regions and lines here."
    assert tree is not None

    placeholder_item = tree.topLevelItem(tree.topLevelItemCount() - 1)
    assert placeholder_item is not None
    assert placeholder_item.text(0) == "Drop here to create a new region"
    assert placeholder_item.toolTip(0) == "Drag lines here to create a new region."


def test_lupdate_extracts_structure_side_panel_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated StructureSidePanel sources without old keys."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "chappy_ja.ts"
    run_lupdate(
        source_dirs=[Path("src/chappy/gui/modes/analysis/overview/panel.py")], ts_output=ts_path
    )

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    assert ORGANIZE_SIDE_PANEL_QT_SOURCES <= sources
    assert not any("GUI__" in source for source in sources)
