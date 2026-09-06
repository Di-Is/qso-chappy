"""Integration tests for region display name in UI panels."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from chappy.core.absorption_display import format_region_display
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.presentation.analysis.structure.tree_presenter import StructureTreePresenter

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def _make_line(
    line_id: str,
    *,
    species: str = "Mg II",
    rest_wavelength: float = 2796.35,
    center_z: float = 1.0,
    region_id: str | None = None,
) -> AbsorptionLine:
    """Create a minimal AbsorptionLine for testing."""
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=150.0,
        region_id=region_id,
        multiplet_label="",
        transition_name=f"{species} {rest_wavelength:.1f}",
        oscillator_strength=0.1,
        gamma_value=1e8,
    )


def _make_region(
    region_id: str, line_ids: list[str], analysis_range: tuple[float, float] | None = None
) -> AbsorptionRegion:
    """Create a minimal AbsorptionRegion for testing."""
    return AbsorptionRegion(region_id=region_id, line_ids=line_ids, analysis_range=analysis_range)


class TestStructureSidePanelDynamicName:
    """Tests for dynamic region name display in StructureSidePanel."""

    def test_group_entry_label_uses_dynamic_name(self, qtbot: "QtBot") -> None:
        """_GroupEntry.label should use dynamic name from format_region_display.

        The label should be in the format:
        '{species set} @ {wave_range} ({linked_line_count})'

        This test verifies that StructureTreePresenter.build_absorption_region_entry
        generates the label using format_region_display() instead of region.name.
        """
        # Setup: Create project with a region containing Mg II doublet lines
        project = SpectroscopyProject()

        line1 = _make_line(
            "line_1", species="Mg II", rest_wavelength=2796.352, center_z=1.0, region_id="region_1"
        )
        line2 = _make_line(
            "line_2", species="Mg II", rest_wavelength=2803.531, center_z=1.0, region_id="region_1"
        )

        region = _make_region("region_1", ["line_1", "line_2"], analysis_range=(5592.0, 5608.0))

        project.absorption_lines["line_1"] = line1
        project.absorption_lines["line_2"] = line2
        project.absorption_regions[region.region_id] = region

        # Get expected label from format_region_display
        lines = [line1, line2]
        expected_info = format_region_display(lines, region.analysis_range)

        presenter = _make_presenter()
        entry = presenter.build_absorption_region_entry(
            region_id="region_1",
            region=region,
            lines=project.absorption_lines,
            component_resolver=project,
        )

        assert entry is not None
        # The label should match the dynamic name format
        assert entry.label == expected_info.display_name

    def test_group_entry_label_for_mixed_species(self, qtbot: "QtBot") -> None:
        """Dynamic name should show multiple species separated by |."""
        project = SpectroscopyProject()

        line1 = _make_line(
            "line_1", species="Mg II", rest_wavelength=2796.352, center_z=1.0, region_id="region_1"
        )
        line2 = _make_line(
            "line_2", species="Al I", rest_wavelength=2118.9862, center_z=1.0, region_id="region_1"
        )

        region = _make_region("region_1", ["line_1", "line_2"], analysis_range=(4000.0, 4500.0))

        project.absorption_lines["line_1"] = line1
        project.absorption_lines["line_2"] = line2
        project.absorption_regions[region.region_id] = region

        lines = [line1, line2]
        expected_info = format_region_display(lines, region.analysis_range)

        presenter = _make_presenter()
        entry = presenter.build_absorption_region_entry(
            region_id="region_1",
            region=region,
            lines=project.absorption_lines,
            component_resolver=project,
        )

        assert entry is not None
        # Should contain both species: "Al I|Mg II" (sorted)
        assert "Al I" in entry.label
        assert "Mg II" in entry.label
        assert entry.label == expected_info.display_name


def _make_presenter() -> StructureTreePresenter:
    """Create a structure tree presenter with stable English templates."""
    return StructureTreePresenter(
        range_tooltip_template="{minimum:.2f} - {maximum:.2f} A",
        linked_line_header_template=("{species} {wavelengths} [z={redshift}, +/-{window} km/s]"),
        unknown_label="Unknown",
    )
