"""Tests for the shared structure structure deletion confirmation contract."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from chappy.application.structure import (
    StructureImpactOperation,
    StructureImpactPreview,
    StructureMutationOutcome,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.masking import MaskDefinition
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.delete_confirmation import (
    create_structure_delete_confirmation,
)
from chappy.gui.modes.analysis.overview.impact_confirmation import format_structure_impact
from tests.gui.support.faithful_env import (
    assert_children_fit_at_minimum_size,
    faithful_application_environment,
)


def _line(
    line_id: str,
    region_id: str,
    *,
    species: str,
    rest_wavelength: float,
    model_ids: tuple[str, ...],
) -> AbsorptionLine:
    """Create one test absorption line."""
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=2.0761,
        window_kms=150.0,
        multiplet_label=species,
        transition_name=species,
        oscillator_strength=0.6,
        gamma_value=1.0e8,
        region_id=region_id,
        model_ids=list(model_ids),
    )


def _project() -> SpectroscopyProject:
    """Build a project with a surviving region and a fully-deleted region."""
    project = SpectroscopyProject()
    surviving_line = _line(
        "line-surviving",
        "region-surviving",
        species="Mg II",
        rest_wavelength=2796.35,
        model_ids=(),
    )
    deleted_line = _line(
        "line-deleted",
        "region-deleted",
        species="C IV",
        rest_wavelength=1548.20,
        model_ids=("model-deleted",),
    )
    project.absorption_regions["region-surviving"] = AbsorptionRegion(
        region_id="region-surviving", line_ids=["line-surviving"]
    )
    project.absorption_regions["region-deleted"] = AbsorptionRegion(
        region_id="region-deleted", line_ids=["line-deleted"]
    )
    project.absorption_lines["line-surviving"] = surviving_line
    project.absorption_lines["line-deleted"] = deleted_line
    project.model.add_component(
        AbsorberComponent(name="Absorber", component_id="model-deleted", group_id="region-deleted")
    )
    project.model.add_mask_definition(
        MaskDefinition.from_range(1547.0, 1549.0, identifier="mask-deleted").with_group_id(
            "region-deleted"
        )
    )
    return project


def _preview() -> StructureImpactPreview:
    """Return a realistic destructive impact spanning a surviving and a deleted region."""
    return StructureImpactPreview(
        operation=StructureImpactOperation.DELETE,
        outcome=StructureMutationOutcome.CHANGED,
        changed_region_ids=("region-surviving",),
        removed_region_ids=("region-deleted",),
        removed_line_ids=("line-deleted",),
        removed_model_ids=("model-deleted",),
        removed_mask_ids=("mask-deleted",),
    )


def test_confirmation_text_displays_human_readable_identities_for_every_impact_kind() -> None:
    """The common confirmation shows display labels instead of raw identities."""
    preview = _preview()
    project = _project()

    text = format_structure_impact(preview, project)

    assert "region-deleted" not in text
    assert "line-deleted" not in text
    assert "model-deleted" not in text
    assert "mask-deleted" not in text
    assert "C IV 1548.20 (z=2.0761)" in text
    assert "Absorber c1" in text
    assert "Mask 1" in text


@pytest.mark.parametrize("language", ["ja", "en"])
def test_confirmation_children_fit_at_translated_minimum_size(qtbot: QtBot, language: str) -> None:
    """The impact and translated destructive buttons fit at the minimum size."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    parent = QWidget()
    qtbot.addWidget(parent)

    with faithful_application_environment(app, language):
        dialog, _delete_button = create_structure_delete_confirmation(
            parent, _preview(), _project(), undo_shortcut="Ctrl+Z"
        )
        qtbot.addWidget(dialog)
        dialog.show()
        app.processEvents()
        assert_children_fit_at_minimum_size(dialog)
