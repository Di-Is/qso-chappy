"""Tests for the structure linked-line unlink confirmation."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from chappy.application.structure import (
    StructureImpactOperation,
    StructureImpactPreview,
    StructureMutationOutcome,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.impact_confirmation import format_structure_impact
from chappy.gui.modes.analysis.overview.unlink_confirmation import (
    create_structure_unlink_confirmation,
)
from tests.gui.support.faithful_env import (
    assert_children_fit_at_minimum_size,
    faithful_application_environment,
)


def _line(line_id: str, region_id: str, *, related_id: str) -> AbsorptionLine:
    """Create one test absorption line linked to a multiplet companion."""
    return AbsorptionLine(
        line_id=line_id,
        species="Mg II",
        rest_wavelength=2796.35,
        center_z=1.0,
        window_kms=150.0,
        multiplet_label="Mg II",
        transition_name="Mg II 2796",
        oscillator_strength=0.6,
        gamma_value=1.0e8,
        region_id=region_id,
        multiplet_ids=[related_id],
    )


def _project() -> SpectroscopyProject:
    """Build a project with two regions linked by a materialized multiplet."""
    project = SpectroscopyProject()
    blue = _line("blue", "region-blue", related_id="red")
    red = _line("red", "region-red", related_id="blue")
    project.absorption_regions["region-blue"] = AbsorptionRegion(
        region_id="region-blue", line_ids=["blue"]
    )
    project.absorption_regions["region-red"] = AbsorptionRegion(
        region_id="region-red", line_ids=["red"]
    )
    project.absorption_lines["blue"] = blue
    project.absorption_lines["red"] = red
    return project


def _preview() -> StructureImpactPreview:
    """Return a realistic non-destructive unlink impact."""
    return StructureImpactPreview(
        operation=StructureImpactOperation.UNLINK,
        outcome=StructureMutationOutcome.CHANGED,
        changed_region_ids=("region-blue", "region-red"),
        expanded_request_line_ids=("blue", "red"),
        changed_line_ids=("blue", "red"),
    )


def test_unlink_reuses_typed_impact_display_without_destructive_wording(qtbot: QtBot) -> None:
    """Unlink shows the shared impact but uses a non-destructive action contract."""
    parent = QWidget()
    qtbot.addWidget(parent)
    project = _project()

    dialog, unlink_button = create_structure_unlink_confirmation(parent, _preview(), project)
    qtbot.addWidget(dialog)

    assert dialog.informativeText() == format_structure_impact(_preview(), project)
    assert "blue" not in dialog.informativeText()
    assert "Mg II 2796.35 (z=1)" in dialog.informativeText()
    assert dialog.icon() == QMessageBox.Icon.Question
    assert "delete" not in dialog.text().casefold()
    assert unlink_button.property("variant") == "primary"


@pytest.mark.parametrize("language", ["ja", "en"])
def test_unlink_confirmation_children_fit_at_translated_minimum_size(
    qtbot: QtBot, language: str
) -> None:
    """The translated unlink impact and buttons fit at minimum size."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    parent = QWidget()
    qtbot.addWidget(parent)

    with faithful_application_environment(app, language):
        dialog, _unlink_button = create_structure_unlink_confirmation(
            parent, _preview(), _project()
        )
        qtbot.addWidget(dialog)
        dialog.show()
        app.processEvents()
        assert_children_fit_at_minimum_size(dialog)
