"""Tests for region display name generation (TDD Red Phase).

This module tests the format_region_display() function which generates
dynamic display names for AbsorptionRegion based on their content.

Format:
- Basic: "{species set} @ {wave_range} ({linked_line_count})"
- Tooltip: "{multiplet_label/transition_name} @ {wave_range} ({linked_line_count})"
"""

from __future__ import annotations

import pytest

from chappy.core.absorption.models import AbsorptionLine
from chappy.core.absorption_display import RegionDisplayInfo, format_region_display


def _make_line(
    line_id: str,
    *,
    center_z: float = 1.0,
    rest_wavelength: float = 1215.67,
    species: str = "H I",
    multiplet_ids: list[str] | None = None,
    transition_name: str = "",
    multiplet_label: str = "",
) -> AbsorptionLine:
    """Create a minimal AbsorptionLine for testing."""
    # Use species as default transition_name if not specified
    actual_transition_name = (
        transition_name if transition_name else f"{species} {rest_wavelength:.1f}"
    )
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=150.0,
        multiplet_ids=multiplet_ids if multiplet_ids is not None else [],
        model_ids=[],
        transition_name=actual_transition_name,
        multiplet_label=multiplet_label,
        oscillator_strength=0.1,
        gamma_value=1e8,
    )


class TestFormatRegionDisplayBasic:
    """Basic tests for format_region_display function."""

    def test_single_singlet_produces_correct_display(self) -> None:
        """Single singlet line produces correct display name."""
        # Given: Al I 2119.0 line (singlet, no multiplet)
        line = _make_line(
            "al_2119", species="Al I", rest_wavelength=2118.9862, transition_name="Al I 2119.0"
        )
        analysis_range = (4000.0, 4500.0)

        # When: format_region_display is called
        result = format_region_display([line], analysis_range)

        # Then: display_name contains species, range, and count
        assert isinstance(result, RegionDisplayInfo)
        assert result.display_name == "Al I @ 4000.0-4500.0 (1)"
        # Tooltip shows transition_name from AbsorptionLine
        assert "Al I 2119.0" in result.tooltip
        assert "4000.0-4500.0" in result.tooltip
        assert "(1)" in result.tooltip

    def test_doublet_produces_correct_display(self) -> None:
        """Mg II doublet produces a display name with one linked-line count."""
        # Given: Mg II 2796 + Mg II 2803 doublet (mutual multiplet_ids)
        line1 = _make_line(
            "mg2_2796",
            species="Mg II",
            rest_wavelength=2796.352,
            transition_name="Mg II 2796.4",
            multiplet_ids=["mg2_2803"],
        )
        line2 = _make_line(
            "mg2_2803",
            species="Mg II",
            rest_wavelength=2803.531,
            transition_name="Mg II 2803.5",
            multiplet_ids=["mg2_2796"],
        )
        analysis_range = (4000.0, 4200.0)

        # When: format_region_display is called
        result = format_region_display([line1, line2], analysis_range)

        # Then: display_name shows Mg II with count=1 (one linked line)
        assert result.display_name == "Mg II @ 4000.0-4200.0 (1)"
        # Tooltip shows transition_name from AbsorptionLine
        assert "Mg II" in result.tooltip
        assert "(1)" in result.tooltip


class TestFormatRegionDisplayMultipleLinkedLines:
    """Tests for multiple linked lines in a region."""

    def test_two_linked_lines_same_species_shows_count_2(self) -> None:
        """Two Mg II doublets (different redshifts) show count=2."""
        # Given: Two independent Mg II doublets
        # Linked line 1: z=1.5
        line1a = _make_line(
            "mg2_2796_z1",
            species="Mg II",
            rest_wavelength=2796.352,
            center_z=1.5,
            multiplet_ids=["mg2_2803_z1"],
        )
        line1b = _make_line(
            "mg2_2803_z1",
            species="Mg II",
            rest_wavelength=2803.531,
            center_z=1.5,
            multiplet_ids=["mg2_2796_z1"],
        )
        # Linked line 2: z=2.0
        line2a = _make_line(
            "mg2_2796_z2",
            species="Mg II",
            rest_wavelength=2796.352,
            center_z=2.0,
            multiplet_ids=["mg2_2803_z2"],
        )
        line2b = _make_line(
            "mg2_2803_z2",
            species="Mg II",
            rest_wavelength=2803.531,
            center_z=2.0,
            multiplet_ids=["mg2_2796_z2"],
        )
        analysis_range = (4000.0, 4200.0)

        # When: format_region_display is called
        lines = [line1a, line1b, line2a, line2b]
        result = format_region_display(lines, analysis_range)

        # Then: display_name shows Mg II with count=2 (two linked lines)
        assert result.display_name == "Mg II @ 4000.0-4200.0 (2)"


class TestFormatRegionDisplayMixedSpecies:
    """Tests for mixed species in a region."""

    def test_mixed_species_sorted_alphabetically(self) -> None:
        """Mixed species are sorted alphabetically and joined with |."""
        # Given: Mg II doublet + Al I singlet
        line1 = _make_line(
            "mg2_2796", species="Mg II", rest_wavelength=2796.352, multiplet_ids=["mg2_2803"]
        )
        line2 = _make_line(
            "mg2_2803", species="Mg II", rest_wavelength=2803.531, multiplet_ids=["mg2_2796"]
        )
        line3 = _make_line("al_2119", species="Al I", rest_wavelength=2118.9862)
        analysis_range = (4000.0, 4500.0)

        # When: format_region_display is called
        lines = [line1, line2, line3]
        result = format_region_display(lines, analysis_range)

        # Then: display_name shows species sorted alphabetically
        # Al I comes before Mg II, separated by |
        assert result.display_name == "Al I|Mg II @ 4000.0-4500.0 (2)"
        # Tooltip shows detailed info with | separator
        assert "|" in result.tooltip
        assert "(2)" in result.tooltip


class TestFormatRegionDisplayEdgeCases:
    """Edge case tests."""

    def test_no_analysis_range_omits_range_part(self) -> None:
        """When analysis_range is None, range part is omitted."""
        # Given: A line with no analysis_range
        line = _make_line("mg2_2796", species="Mg II", rest_wavelength=2796.352)

        # When: format_region_display is called with None range
        result = format_region_display([line], None)

        # Then: display_name omits "@ ..." part
        assert result.display_name == "Mg II (1)"
        assert "@" not in result.display_name

    def test_empty_lines_raises_error_or_returns_empty(self) -> None:
        """Empty lines list should raise an error or return sensible default."""
        # When/Then: format_region_display should handle empty case
        # Per ADR: "空の領域は作成不可"
        with pytest.raises(ValueError, match="lines"):
            format_region_display([], (4000.0, 4500.0))
