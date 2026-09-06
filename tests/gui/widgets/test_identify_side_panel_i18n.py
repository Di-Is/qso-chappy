"""Tests for IdentifySidePanel Qt translation sources."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
from chappy.gui.modes.identify.panel.panel_models import (
    TemporaryLineRow,
    CandidateRow,
    ConfirmedLineRow,
    ConfirmedRegionRow,
    LineListItem,
)
from chappy.i18n.qt_translator import QtTranslatorInstaller
from scripts.i18n_lupdate import run_lupdate

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


IDENTIFY_SIDE_PANEL_QT_SOURCES = {
    "Preset",
    "Manage⚙",
    "Reference line",
    "Detection Candidates ({count})",
    "No detection candidates. Lower the σ threshold to find more.",
    "σ threshold",
    " σ",
    (
        "Double-click a candidate to move there. "
        "Then hold Shift to preview, Shift+click to add, or press V to verify"
    ),
    "λ range [Å]",
    "σ",
    "Status",
    "Registered",
    "Tentative",
    "Unassigned",
    "Matched to a line in a confirmed region.",
    "A temporary line is placed. Not final until registered.",
    "A dip not yet matched to any line.",
    "To register: {groups} / {lines}",
    "{count} group",
    "{count} groups",
    "{count} line",
    "{count} lines",
    "Added temporary lines appear here, grouped by registration destination.",
    "Delete",
    "More actions",
    "Clear All",
    "Register all ({groups})",
    "Register selected ({groups})",
    "No temporary lines. Shift+click on the spectrum to add them.",
    "New region: {species} {start:.1f}–{end:.1f} Å ({count})",
    "→ Add to {region} ({count})",
    "{count} lines grouped",
    "Confirmed Regions",
    "Registered regions appear here.",
    "0 regions · Shown after registration",
    "{count} region",
    "{count} regions",
    "{regions} · {label}",
    "{regions} · {label} · {species} z={redshift:.4f}",
    "Unknown",
}


def _ts_sources(ts_path: Path) -> set[str]:
    """Return source texts extracted into a Qt TS file.

    Args:
        ts_path: Generated TS catalog path.

    Returns:
        Source texts found in the catalog.
    """
    root = ET.parse(ts_path).getroot()
    return {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }


def test_identify_side_panel_uses_qt_source_text(qtbot: "QtBot") -> None:
    """Verify identify side panel labels use plain Qt source text.

    Args:
        qtbot: Qt test helper managing widget lifetime.
    """
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)

    panel.set_candidates(
        [
            CandidateRow(
                identifier="candidate-a",
                lambda_start=1215.0,
                lambda_end=1216.0,
                sigma=4.0,
                status="identified",
            )
        ]
    )
    panel.set_temporary_lines(
        [
            TemporaryLineRow(
                temporary_line_ids=("line-a", "line-b", "line-c"),
                species="Mg II",
                lambda_start=2796.0,
                lambda_end=2803.0,
                creation_method="manual",
                transition_name="Mg II 2796/2803",
                redshift=1.2345,
            )
        ]
    )

    preset_section = panel._preset_section
    candidate_section = panel._candidate_section
    temporary_section = panel._temporary_section
    confirmed_section = panel._confirmed_section
    candidate_headers = [
        candidate_section._candidate_table.horizontalHeaderItem(column) for column in range(3)
    ]
    candidate_status = candidate_section._candidate_table.item(0, 2)
    temporary_item = temporary_section._temporary_tree.topLevelItem(0)
    assert all(header is not None for header in candidate_headers)

    assert preset_section._preset_label.text() == "Preset"
    assert preset_section._manage_preset_button.text() == "Manage⚙"
    assert preset_section._reference_label.text() == "Reference line"
    assert preset_section._reference_combo.accessibleName() == "Reference line"
    assert candidate_section._candidate_section_label.text() == "Detection Candidates (1)"
    assert (
        candidate_section._candidate_placeholder.text()
        == "No detection candidates. Lower the σ threshold to find more."
    )
    assert candidate_section._sigma_label.text() == "σ threshold"
    assert candidate_section._sigma_spin.suffix() == " σ"
    assert not candidate_section._sigma_slider.isHidden()
    assert candidate_section._hint_label.text() == (
        "Double-click a candidate to move there. "
        "Then hold Shift to preview, Shift+click to add, or press V to verify"
    )
    assert [header.text() for header in candidate_headers if header is not None] == [
        "λ range [Å]",
        "σ",
        "Status",
    ]
    assert candidate_status is not None
    assert candidate_status.text() == "Registered"
    assert candidate_status.toolTip() == "Matched to a line in a confirmed region."
    assert temporary_section._temporary_label.text() == "To register: 1 group / 3 lines"
    assert (
        temporary_section._temporary_placeholder.text()
        == "Added temporary lines appear here, grouped by registration destination."
    )
    assert temporary_section._delete_button.text() == "Delete"
    assert temporary_section._more_button.text() == "⋯"
    assert temporary_section._more_button.toolTip() == "More actions"
    assert temporary_section._clear_action.text() == "Clear All"
    assert temporary_section._register_button.text() == "Register all (1 group)"
    assert panel._confirmed_collapsible._header_button._title_label.text() == "Confirmed Regions"
    assert panel._confirmed_collapsible._summary_label.full_text.startswith("0 regions")
    assert temporary_item is not None
    assert temporary_item.toolTip(0) == "3 lines grouped"


def test_lupdate_extracts_identify_side_panel_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts identify side panel source text.

    Args:
        tmp_path: Temporary directory for the generated TS file.
    """
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "identify_side_panel.ts"
    run_lupdate(
        source_dirs=[
            Path("src/chappy/gui/modes/identify/panel/panel.py"),
            Path("src/chappy/gui/modes/identify/panel/preset_lines_section.py"),
            Path("src/chappy/gui/modes/identify/panel/candidate_section.py"),
            Path("src/chappy/gui/modes/identify/panel/temporary_section.py"),
            Path("src/chappy/gui/modes/identify/panel/confirmed_section.py"),
        ],
        ts_output=ts_path,
    )

    sources = _ts_sources(ts_path)
    assert IDENTIFY_SIDE_PANEL_QT_SOURCES <= sources
    assert not any("GUI__" in source for source in sources)


@pytest.mark.parametrize("width", [320, 420])
def test_language_change_keeps_reference_and_disclosures_visible(
    qtbot: "QtBot", qapp: QApplication, width: int
) -> None:
    """Japanese retranslation keeps compact summaries and disclosures readable."""
    installer = QtTranslatorInstaller()
    installer.install_language("en")
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)
    panel.resize(width, 700)
    panel.set_presets([("preset-1", "A very long metal-doublet preset name")])
    panel.set_line_items(
        [
            LineListItem(
                identifier="line-1",
                reference="C IV λ1548",
                name="C IV λ1548",
                wavelength=1548.204,
                oscillator_strength=0.190,
                is_reference=True,
            )
        ]
    )
    panel.set_temporary_lines(
        [
            TemporaryLineRow(
                temporary_line_ids=("temporary-1", "temporary-2"),
                species="C IV",
                lambda_start=3544.8,
                lambda_end=3546.3,
                creation_method="manual",
                transition_name="C IV doublet",
                redshift=1.292,
            )
        ]
    )
    panel.set_confirmed_regions(
        [
            ConfirmedRegionRow(
                group_id="confirmed-1",
                label="Region 1",
                lines=[
                    ConfirmedLineRow(
                        line_id="confirmed-line-1",
                        species="C IV",
                        redshift=1.292,
                        lambda_start=3544.8,
                        lambda_end=3546.3,
                    )
                ],
                is_expanded=False,
            )
        ]
    )
    panel.show()
    QApplication.processEvents()
    try:
        installer.install_language("ja")
        QApplication.processEvents()

        preset_section = panel._preset_section
        candidate = panel._candidate_section
        temporary = panel._temporary_section
        confirmed = panel._confirmed_collapsible
        assert preset_section._reference_label.text() == "基準線"
        assert preset_section._reference_combo.currentText() == "C IV λ1548 1548.204"
        assert candidate._sigma_label.text() == "σしきい値"
        assert candidate._sigma_slider.isVisible()
        assert temporary._temporary_label.text() == "登録待ち: 1組 / 2線"
        assert temporary._more_button.toolTip() == "その他の操作"
        assert temporary._register_button.text() == "すべて登録 (1組)"
        assert confirmed._header_button._title_label.text() == "確定領域"
        assert confirmed._summary_label.full_text.startswith("1件 · Region 1")
    finally:
        installer.remove_translators()
