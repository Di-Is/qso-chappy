"""Tests for confirmed line multiplet grouping in IdentifyModeCoordinator.

TDD Red phase: These tests define the expected behavior for confirmed line
multiplet grouping in _refresh_workflow.
"""

from __future__ import annotations

from dataclasses import fields

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.atomic_data import AtomicLineData
from chappy.core.absorption_display import group_lines_by_multiplet
from chappy.core.velocity_ranges import MultipletGroupingVelocityTolerance
from chappy.gui.modes.identify.panel.panel_models import ConfirmedLineRow
from chappy.gui.modes.identify.panel.workflow_view_model_builder import (
    IdentifyWorkflowBuilderInput,
    IdentifyWorkflowMethodLabels,
    IdentifyWorkflowViewModelBuilder,
)
from chappy.infrastructure.atomic_lines import get_atomic_data

if TYPE_CHECKING:
    from chappy.core.atomic_data import AtomicLine


def _find_mg2_doublet(atomic_data: AtomicLineData) -> tuple[AtomicLine, AtomicLine]:
    """Find Mg II 2796 and 2803 lines from atomic database."""
    mg2_2796 = atomic_data.get_line_by_id("d85a4a9d4dfb3235")
    mg2_2803 = atomic_data.get_line_by_id("380d715c908636f5")
    assert mg2_2796 is not None, "Mg II 2796 not found in atomic database"
    assert mg2_2803 is not None, "Mg II 2803 not found in atomic database"
    return mg2_2796, mg2_2803


def _find_civ_doublet(atomic_data: AtomicLineData) -> tuple[AtomicLine, AtomicLine]:
    """Find C IV 1548 and 1550 lines from atomic database."""
    civ_lines = [
        ln
        for ln in atomic_data.lines
        if ln.species == "C IV" and 1548 < ln.wavelength_angstrom < 1552
    ]
    if len(civ_lines) < 2:
        pytest.skip("C IV doublet not found in atomic database")
    civ_lines = sorted(civ_lines, key=lambda x: x.wavelength_angstrom)
    return civ_lines[0], civ_lines[1]


def _make_absorption_line(
    line_id: str,
    *,
    species: str = "Unknown",
    rest_wavelength: float = 5000.0,
    center_z: float = 0.0,
    window_kms: float = 100.0,
    lambda_range: tuple[float, float] | None = None,
    multiplet_ids: list[str] | None = None,
    transition_name: str | None = None,
) -> AbsorptionLine:
    """Create an AbsorptionLine for testing."""
    if lambda_range is None:
        obs_wl = rest_wavelength * (1 + center_z)
        lambda_range = (obs_wl - 5, obs_wl + 5)
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=window_kms,
        multiplet_label="",
        transition_name=transition_name or f"{species} {rest_wavelength:.1f}",
        oscillator_strength=0.1,
        gamma_value=1e8,
        lambda_range=lambda_range,
        multiplet_ids=multiplet_ids or [],
    )


@pytest.fixture
def atomic_data() -> AtomicLineData:
    """Create AtomicLineData instance."""
    return get_atomic_data()


class TestConfirmedMultipletGrouping:
    """Tests for confirmed line multiplet grouping using group_lines_by_multiplet."""

    def test_single_line_not_grouped(self) -> None:
        """Single line should remain as single group."""
        lines = [
            _make_absorption_line("line1", species="H I", rest_wavelength=1215.67, center_z=2.0)
        ]

        groups = group_lines_by_multiplet(lines)

        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert groups[0][0].line_id == "line1"

    def test_doublet_grouped_as_single_group(self, atomic_data: AtomicLineData) -> None:
        """Mg II 2796/2803 with cross-references should be grouped together."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)
        redshift = 1.5

        # Create lines with cross-references (simulating setup_multiplet_cross_references)
        line_2796 = _make_absorption_line(
            "mg2_2796",
            species=mg2_2796.species,
            rest_wavelength=mg2_2796.wavelength_angstrom,
            center_z=redshift,
            multiplet_ids=["mg2_2803"],  # Cross-reference
            transition_name=f"{mg2_2796.species} {mg2_2796.wavelength_angstrom:.1f}",
        )
        line_2803 = _make_absorption_line(
            "mg2_2803",
            species=mg2_2803.species,
            rest_wavelength=mg2_2803.wavelength_angstrom,
            center_z=redshift,
            multiplet_ids=["mg2_2796"],  # Cross-reference
            transition_name=f"{mg2_2803.species} {mg2_2803.wavelength_angstrom:.1f}",
        )

        groups = group_lines_by_multiplet([line_2796, line_2803])

        assert len(groups) == 1, "Doublet should form a single group"
        assert len(groups[0]) == 2, "Group should contain both lines"
        # Lines within group are sorted by rest_wavelength
        assert groups[0][0].line_id == "mg2_2796"
        assert groups[0][1].line_id == "mg2_2803"

    def test_different_multiplets_separate(self, atomic_data: AtomicLineData) -> None:
        """Different multiplets (MgII + CIV) should form separate groups."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)
        civ_1548, civ_1550 = _find_civ_doublet(atomic_data)
        redshift = 2.0

        # Mg II doublet
        line_mg2_2796 = _make_absorption_line(
            "mg2_2796",
            species=mg2_2796.species,
            rest_wavelength=mg2_2796.wavelength_angstrom,
            center_z=redshift,
            multiplet_ids=["mg2_2803"],
        )
        line_mg2_2803 = _make_absorption_line(
            "mg2_2803",
            species=mg2_2803.species,
            rest_wavelength=mg2_2803.wavelength_angstrom,
            center_z=redshift,
            multiplet_ids=["mg2_2796"],
        )

        # C IV doublet
        line_civ_1548 = _make_absorption_line(
            "civ_1548",
            species=civ_1548.species,
            rest_wavelength=civ_1548.wavelength_angstrom,
            center_z=redshift,
            multiplet_ids=["civ_1550"],
        )
        line_civ_1550 = _make_absorption_line(
            "civ_1550",
            species=civ_1550.species,
            rest_wavelength=civ_1550.wavelength_angstrom,
            center_z=redshift,
            multiplet_ids=["civ_1548"],
        )

        # Input order: alternating to test grouping correctness
        lines = [line_mg2_2796, line_civ_1548, line_mg2_2803, line_civ_1550]
        groups = group_lines_by_multiplet(lines)

        assert len(groups) == 2, "Should have 2 separate multiplet groups"
        # Each group has 2 lines
        assert all(len(g) == 2 for g in groups)
        # Verify grouping by species
        group_species = [{line.species for line in group} for group in groups]
        assert {"Mg II"} in group_species
        assert {"C IV"} in group_species

    def test_combined_wavelength_range(self) -> None:
        """Multiplet row should have combined min/max wavelength range."""
        redshift = 1.5
        # Create doublet with known wavelength ranges
        line_2796 = _make_absorption_line(
            "mg2_2796",
            species="Mg II",
            rest_wavelength=2796.4,
            center_z=redshift,
            lambda_range=(6990.0, 7000.0),
            multiplet_ids=["mg2_2803"],
        )
        line_2803 = _make_absorption_line(
            "mg2_2803",
            species="Mg II",
            rest_wavelength=2803.5,
            center_z=redshift,
            lambda_range=(7005.0, 7015.0),
            multiplet_ids=["mg2_2796"],
        )

        groups = group_lines_by_multiplet([line_2796, line_2803])

        assert len(groups) == 1
        group = groups[0]

        # Calculate combined wavelength range
        combined_lambda_start = min(line.lambda_range[0] for line in group if line.lambda_range)
        combined_lambda_end = max(line.lambda_range[1] for line in group if line.lambda_range)

        assert combined_lambda_start == 6990.0
        assert combined_lambda_end == 7015.0


class TestConfirmedLineRowDataStructure:
    """Tests for ConfirmedLineRow data structure after field removal."""

    def test_confirmed_line_row_has_no_is_multiplet(self) -> None:
        """ConfirmedLineRow should not have is_multiplet field after refactoring."""
        row = ConfirmedLineRow(
            line_id="test_id",
            species="Mg II 2796/2803",
            redshift=1.5,
            lambda_start=6990.0,
            lambda_end=7015.0,
            transition_name="Mg II 2796/2803",
        )
        # After refactoring, these fields should not exist
        field_names = {field.name for field in fields(row)}
        assert "is_multiplet" not in field_names
        assert "is_component" not in field_names
        assert "parent_id" not in field_names

    def test_confirmed_line_row_basic_fields(self) -> None:
        """ConfirmedLineRow should have basic required fields."""
        row = ConfirmedLineRow(
            line_id="test_id",
            species="Mg II 2796/2803",
            redshift=1.5,
            lambda_start=6990.0,
            lambda_end=7015.0,
            transition_name="Mg II 2796/2803",
        )
        assert row.line_id == "test_id"
        assert row.species == "Mg II 2796/2803"
        assert row.redshift == 1.5
        assert row.lambda_start == 6990.0
        assert row.lambda_end == 7015.0
        assert row.transition_name == "Mg II 2796/2803"


class TestConfirmedLineViewModelInvariants:
    """Tests for confirmed line fail-fast invariants."""

    def test_confirmed_line_without_lambda_range_fails_fast(self) -> None:
        """Confirmed lines must not display a fabricated zero-width wavelength range."""
        line = _confirmed_line(_make_absorption_line("line-no-range", lambda_range=None))
        line = replace(line, lambda_range=None)

        with pytest.raises(ValueError, match="no wavelength range"):
            _build_confirmed_view_model([line])

    def test_confirmed_line_with_invalid_redshift_fails_fast(self) -> None:
        """Confirmed lines must not display missing redshift as zero."""
        line = _confirmed_line(
            _make_absorption_line("line-invalid-redshift", center_z=float("nan"))
        )

        with pytest.raises(ValueError, match="invalid redshift"):
            _build_confirmed_view_model([line])


def _build_confirmed_view_model(lines: list[AbsorptionLine]) -> None:
    """Build confirmed workflow rows for invariant tests."""
    builder = IdentifyWorkflowViewModelBuilder()
    builder.build(
        IdentifyWorkflowBuilderInput(
            temporary_lines=[],
            region_previews=[],
            absorption_lines=lines,
            absorption_regions=[
                AbsorptionRegion(
                    region_id="region-1",
                    line_ids=[line.line_id for line in lines],
                    analysis_range=(4000.0, 5000.0),
                )
            ],
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(100.0),
            atomic_data_available=True,
            method_labels=IdentifyWorkflowMethodLabels(
                candidate_table="Candidate", manual="Manual", velocity_plot="Velocity"
            ),
        )
    )


def _confirmed_line(line: AbsorptionLine) -> AbsorptionLine:
    """Return a line assigned to the confirmed test region."""
    return replace(line, region_id="region-1")
