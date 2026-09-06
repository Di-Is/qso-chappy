"""Tests for the Qt-free structure-impact display presenter."""

from __future__ import annotations

from dataclasses import dataclass

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.base import ModelComponent
from chappy.core.masking import MaskDefinition
from chappy.presentation.analysis.structure.impact_display_presenter import (
    build_structure_impact_display,
)


@dataclass
class _FakeModel:
    """Minimal model facts double satisfying ImpactModelFacts structurally."""

    components: list[ModelComponent]
    mask_definitions: tuple[MaskDefinition, ...]


@dataclass
class _FakeProject:
    """Minimal project facts double satisfying ImpactProjectFacts structurally."""

    absorption_regions: dict[str, AbsorptionRegion]
    absorption_lines: dict[str, AbsorptionLine]
    model: _FakeModel


def _line(
    line_id: str,
    region_id: str,
    *,
    rest_wavelength: float,
    related_id: str,
    model_ids: tuple[str, ...],
) -> AbsorptionLine:
    """Create one C IV doublet member line."""
    return AbsorptionLine(
        line_id=line_id,
        species="C IV",
        rest_wavelength=rest_wavelength,
        center_z=2.0761,
        window_kms=150.0,
        multiplet_label="C IV",
        transition_name="C IV",
        oscillator_strength=0.19,
        gamma_value=2.6e8,
        region_id=region_id,
        multiplet_ids=[related_id],
        model_ids=list(model_ids),
    )


def _doublet_project() -> _FakeProject:
    """Build a project with a linked C IV 1548/1551 doublet, one region."""
    blue = _line(
        "line-1548",
        "region-civ",
        rest_wavelength=1548.20,
        related_id="line-1551",
        model_ids=("component-1548",),
    )
    red = _line(
        "line-1551",
        "region-civ",
        rest_wavelength=1550.77,
        related_id="line-1548",
        model_ids=("component-1551",),
    )
    region = AbsorptionRegion(region_id="region-civ", line_ids=["line-1548", "line-1551"])
    components = [
        AbsorberComponent(name="Absorber", component_id="component-1548", group_id="region-civ"),
        AbsorberComponent(name="Absorber", component_id="component-1551", group_id="region-civ"),
    ]
    return _FakeProject(
        absorption_regions={"region-civ": region},
        absorption_lines={"line-1548": blue, "line-1551": red},
        model=_FakeModel(components=components, mask_definitions=()),
    )


def test_region_labels_use_species_range_and_linked_line_count() -> None:
    """Region rows show the same display name as the Overview review rows."""
    project = _doublet_project()

    display = build_structure_impact_display(
        changed_region_ids=(),
        removed_region_ids=("region-civ",),
        changed_line_ids=(),
        removed_line_ids=(),
        changed_model_ids=(),
        removed_model_ids=(),
        changed_mask_ids=(),
        removed_mask_ids=(),
        project=project,
    )

    assert display.regions.removed == ("C IV (1)",)


def test_line_labels_show_species_wavelength_and_redshift_not_raw_ids() -> None:
    """Line rows resolve to species/rest-wavelength/redshift, not raw identities."""
    project = _doublet_project()

    display = build_structure_impact_display(
        changed_region_ids=(),
        removed_region_ids=(),
        changed_line_ids=(),
        removed_line_ids=("line-1548", "line-1551"),
        changed_model_ids=(),
        removed_model_ids=(),
        changed_mask_ids=(),
        removed_mask_ids=(),
        project=project,
    )

    assert display.lines.removed == ("C IV 1548.20 (z=2.0761)", "C IV 1550.77 (z=2.0761)")


def test_component_labels_group_under_both_doublet_member_lines() -> None:
    """A CIV doublet's two tied components each read under their own member line."""
    project = _doublet_project()

    display = build_structure_impact_display(
        changed_region_ids=(),
        removed_region_ids=(),
        changed_line_ids=(),
        removed_line_ids=(),
        changed_model_ids=(),
        removed_model_ids=("component-1548", "component-1551"),
        changed_mask_ids=(),
        removed_mask_ids=(),
        project=project,
    )

    assert display.components.removed == (
        "C IV 1548.20 (z=2.0761) · Absorber c1",
        "C IV 1550.77 (z=2.0761) · Absorber c1",
    )


def test_mask_labels_prefer_user_label_then_wavelength_range() -> None:
    """Masks show their label when set, otherwise their wavelength range."""
    project = _doublet_project()
    project.model.mask_definitions = (
        MaskDefinition.from_range(1547.0, 1549.0, identifier="mask-plain"),
        MaskDefinition.from_range(1000.0, 1001.0, identifier="mask-labeled", label="sky line"),
    )

    display = build_structure_impact_display(
        changed_region_ids=(),
        removed_region_ids=(),
        changed_line_ids=(),
        removed_line_ids=(),
        changed_model_ids=(),
        removed_model_ids=(),
        changed_mask_ids=("mask-plain", "mask-labeled"),
        removed_mask_ids=(),
        project=project,
    )

    assert display.masks.changed == ("1547.0–1549.0", "sky line")


def test_missing_identity_is_skipped_rather_than_fabricated() -> None:
    """An identity absent from current project facts contributes no display row."""
    project = _doublet_project()

    display = build_structure_impact_display(
        changed_region_ids=("region-missing",),
        removed_region_ids=(),
        changed_line_ids=("line-missing",),
        removed_line_ids=(),
        changed_model_ids=("component-missing",),
        removed_model_ids=(),
        changed_mask_ids=("mask-missing",),
        removed_mask_ids=(),
        project=project,
    )

    assert display.regions.changed == ()
    assert display.lines.changed == ()
    assert display.components.changed == ()
    assert display.masks.changed == ()
