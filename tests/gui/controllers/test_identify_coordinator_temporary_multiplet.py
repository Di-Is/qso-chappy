"""Tests for temporary line multiplet grouping in IdentifyModeCoordinator.

TDD Red phase: These tests should fail until _group_temporary_lines_by_multiplet
is implemented.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import pytest

from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    BuildRegionPreviewsUseCase,
)
from chappy.core.atomic_data import AtomicLineData
from chappy.core.identify_state import TemporaryLine
from chappy.core.identify_state import IdentifySessionState
from chappy.core.velocity_ranges import MultipletGroupingVelocityTolerance
from chappy.gui.modes.identify.panel.workflow_view_model_builder import (
    group_temporary_lines_by_multiplet,
)
from chappy.gui.modes.identify.workflows.registration_workflow import (
    IdentifyRegistrationWorkflow,
    IdentifyRegistrationWorkflowMessages,
    IdentifyRegistrationWorkflowPorts,
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
    # C IV doublet line IDs (search by wavelength if needed)
    civ_lines = [
        ln
        for ln in atomic_data.lines
        if ln.species == "C IV" and 1548 < ln.wavelength_angstrom < 1552
    ]
    if len(civ_lines) < 2:
        pytest.skip("C IV doublet not found in atomic database")
    civ_lines = sorted(civ_lines, key=lambda x: x.wavelength_angstrom)
    return civ_lines[0], civ_lines[1]


def _make_temporary_line(
    temporary_line_id: str,
    *,
    species: str = "Unknown",
    lambda_min: float = 5000.0,
    lambda_max: float = 5010.0,
    center_z: float | None = None,
    analysis_half_width_kms: float = 100.0,
    line_id: str | None = None,
    rest_wavelength: float | None = None,
    multiplet_id: str = "",
    multiplet_label: str = "",
) -> TemporaryLine:
    """Create a TemporaryLine for testing."""
    return TemporaryLine(
        temporary_line_id=temporary_line_id,
        species=species,
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        creation_method="test",
        center_z=center_z,
        analysis_half_width_kms=analysis_half_width_kms,
        line_id=line_id,
        rest_wavelength=rest_wavelength,
        multiplet_id=multiplet_id,
        tie_group_key=multiplet_id,
        multiplet_label=multiplet_label,
        transition_name=f"{species} {rest_wavelength:.1f}" if rest_wavelength else species,
        oscillator_strength=0.1,
        gamma_value=1e8,
    )


@pytest.fixture
def atomic_data() -> AtomicLineData:
    """Create AtomicLineData instance."""
    return get_atomic_data()


def _group_temporary_lines_by_multiplet(
    lines: Sequence[TemporaryLine],
    atomic_data: AtomicLineData | None,
    multiplet_grouping_tolerance_kms: float = 100.0,
) -> list[list[TemporaryLine]]:
    """Group temporary lines through the workflow view-model helper."""
    return group_temporary_lines_by_multiplet(
        lines,
        atomic_data_available=atomic_data is not None,
        multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(
            multiplet_grouping_tolerance_kms
        ),
    )


def _registration_messages() -> IdentifyRegistrationWorkflowMessages:
    """Return deterministic registration workflow messages."""
    return IdentifyRegistrationWorkflowMessages(
        cannot_register_without_project="No project",
        no_temporary_lines_to_register="No candidates",
        temporary_lines_could_not_register="Failed",
        registered_template="Registered {count}",
        registered_details_template=" ({details})",
        new_regions_template="{count} new region(s)",
        appended_template="added to {region}",
        detail_separator=", ",
        multi_overlap_warning="Overlaps multiple existing regions.",
        missing_atomic_template="Missing {count}",
        undo_hint="Undo (Ctrl+Z) reverts this registration.",
        unknown="Unknown",
    )


def _expand_temporary_lines(
    primary_to_members: dict[str, tuple[str, ...]], selected_ids: Sequence[str]
) -> list[str]:
    """Expand selected IDs through the registration workflow."""
    workflow = IdentifyRegistrationWorkflow(
        IdentifyRegistrationWorkflowPorts(
            project_provider=lambda: None,
            session_provider=IdentifySessionState,
            history_recorder_provider=lambda: None,
            primary_members_provider=lambda: primary_to_members,
            messages_provider=_registration_messages,
        ),
        BuildRegionPreviewsUseCase(),
        AtomicIdentifyRegistrationUseCase(),
    )
    return workflow.expand_multiplet_temporary_lines(selected_ids)


class TestTemporaryMultipletGrouping:
    """Tests for _group_temporary_lines_by_multiplet."""

    def test_single_line_not_grouped(self, atomic_data: AtomicLineData) -> None:
        """Single line without multiplet info forms a solo group."""
        lines = [
            _make_temporary_line(
                "line1",
                species="H I",
                line_id=None,  # No atomic line reference
            )
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert groups[0][0].temporary_line_id == "line1"

    def test_doublet_grouped_together(self, atomic_data: AtomicLineData) -> None:
        """Mg II 2796/2803 with same redshift should be grouped together."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)

        redshift = 1.5
        obs_wl_2796 = mg2_2796.wavelength_angstrom * (1 + redshift)
        obs_wl_2803 = mg2_2803.wavelength_angstrom * (1 + redshift)

        lines = [
            _make_temporary_line(
                "mg2_2796",
                species=mg2_2796.species,
                lambda_min=obs_wl_2796 - 5,
                lambda_max=obs_wl_2796 + 5,
                center_z=redshift,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                multiplet_id=mg2_2796.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2803",
                species=mg2_2803.species,
                lambda_min=obs_wl_2803 - 5,
                lambda_max=obs_wl_2803 + 5,
                center_z=redshift,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                multiplet_id=mg2_2803.multiplet_id,
            ),
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        # Should be grouped together (1 group with 2 lines)
        assert len(groups) == 1, f"Expected 1 group, got {len(groups)}"
        assert len(groups[0]) == 2
        temporary_line_ids = {s.temporary_line_id for s in groups[0]}
        assert temporary_line_ids == {"mg2_2796", "mg2_2803"}

    def test_different_multiplets_separate(self, atomic_data: AtomicLineData) -> None:
        """Mg II and C IV doublets should be in separate groups."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)
        civ_1548, civ_1550 = _find_civ_doublet(atomic_data)

        redshift = 1.5

        lines = [
            _make_temporary_line(
                "mg2_2796",
                species=mg2_2796.species,
                center_z=redshift,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                multiplet_id=mg2_2796.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2803",
                species=mg2_2803.species,
                center_z=redshift,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                multiplet_id=mg2_2803.multiplet_id,
            ),
            _make_temporary_line(
                "civ_1548",
                species=civ_1548.species,
                center_z=redshift,
                line_id=civ_1548.line_id,
                rest_wavelength=civ_1548.wavelength_angstrom,
                multiplet_id=civ_1548.multiplet_id,
            ),
            _make_temporary_line(
                "civ_1550",
                species=civ_1550.species,
                center_z=redshift,
                line_id=civ_1550.line_id,
                rest_wavelength=civ_1550.wavelength_angstrom,
                multiplet_id=civ_1550.multiplet_id,
            ),
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        # Should be 2 groups: Mg II and C IV
        assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"

        # Find Mg II group and C IV group
        mg2_group = None
        civ_group = None
        for group in groups:
            species_set = {s.species for s in group}
            if "Mg II" in species_set:
                mg2_group = group
            elif "C IV" in species_set:
                civ_group = group

        assert mg2_group is not None, "Mg II group not found"
        assert civ_group is not None, "C IV group not found"
        assert len(mg2_group) == 2
        assert len(civ_group) == 2

    def test_same_multiplet_different_redshift_separate(self, atomic_data: AtomicLineData) -> None:
        """Same multiplet (Mg II) at different redshifts should be separate groups."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)

        # Two Mg II doublets at very different redshifts
        # velocity difference = |z1 - z2| * c ≈ 0.2 * 300000 = 60000 km/s >> 100 km/s
        redshift_1 = 1.5
        redshift_2 = 1.7

        lines = [
            # First doublet at z=1.5
            _make_temporary_line(
                "mg2_2796_z1",
                species=mg2_2796.species,
                center_z=redshift_1,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                analysis_half_width_kms=100.0,
                multiplet_id=mg2_2796.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2803_z1",
                species=mg2_2803.species,
                center_z=redshift_1,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                analysis_half_width_kms=100.0,
                multiplet_id=mg2_2803.multiplet_id,
            ),
            # Second doublet at z=1.7
            _make_temporary_line(
                "mg2_2796_z2",
                species=mg2_2796.species,
                center_z=redshift_2,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                analysis_half_width_kms=100.0,
                multiplet_id=mg2_2796.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2803_z2",
                species=mg2_2803.species,
                center_z=redshift_2,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                analysis_half_width_kms=100.0,
                multiplet_id=mg2_2803.multiplet_id,
            ),
        ]

        groups = _group_temporary_lines_by_multiplet(
            lines, atomic_data, multiplet_grouping_tolerance_kms=100.0
        )

        # Should be 2 groups: one for each redshift
        assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"

        # Verify each group has 2 lines with the same redshift
        for group in groups:
            assert len(group) == 2
            redshifts = {s.center_z for s in group}
            assert len(redshifts) == 1, "Each group should have same redshift"

    def test_line_id_none_single_group(self, atomic_data: AtomicLineData) -> None:
        """Lines with line_id=None should form single-element groups (Risk-9)."""
        lines = [
            _make_temporary_line(
                "line1",
                species="Unknown",
                line_id=None,  # No atomic line reference
            ),
            _make_temporary_line(
                "line2",
                species="Unknown",
                line_id=None,  # No atomic line reference
            ),
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        # Each should be its own group (no multiplet info to group by)
        assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"
        assert all(len(g) == 1 for g in groups)

    def test_atomic_data_none_skips_grouping(self) -> None:
        """When atomic_data is None, all lines form single-element groups (Risk-10)."""
        lines = [
            _make_temporary_line("line1", species="Mg II"),
            _make_temporary_line("line2", species="Mg II"),
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data=None)

        # Without atomic data, cannot determine multiplet relationships
        # Each line forms its own group
        assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"
        assert all(len(g) == 1 for g in groups)

    def test_groups_sorted_by_rest_wavelength(self, atomic_data: AtomicLineData) -> None:
        """Lines within a group should be sorted by rest_wavelength."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)

        redshift = 1.5

        # Add in reverse wavelength order
        lines = [
            _make_temporary_line(
                "mg2_2803",
                species=mg2_2803.species,
                center_z=redshift,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,  # 2803 Å
                multiplet_id=mg2_2803.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2796",
                species=mg2_2796.species,
                center_z=redshift,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,  # 2796 Å
                multiplet_id=mg2_2796.multiplet_id,
            ),
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        assert len(groups) == 1
        # First element should be 2796 (lower wavelength)
        assert groups[0][0].temporary_line_id == "mg2_2796"
        assert groups[0][1].temporary_line_id == "mg2_2803"

    def test_empty_input_returns_empty_list(self, atomic_data: AtomicLineData) -> None:
        """Empty input should return empty list."""
        groups = _group_temporary_lines_by_multiplet([], atomic_data)

        assert groups == []


class TestPrimaryToMembersMapping:
    """Tests for _primary_to_members mapping construction."""

    def test_primary_to_members_contains_all_ids(self, atomic_data: AtomicLineData) -> None:
        """_primary_to_members should map primary ID to all member IDs."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)
        redshift = 1.5

        lines = [
            _make_temporary_line(
                "mg2_2796",
                species=mg2_2796.species,
                center_z=redshift,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                multiplet_id=mg2_2796.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2803",
                species=mg2_2803.species,
                center_z=redshift,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                multiplet_id=mg2_2803.multiplet_id,
            ),
        ]

        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        # Build _primary_to_members mapping (as coordinator would do)
        primary_to_members: dict[str, tuple[str, ...]] = {}
        for group in groups:
            if len(group) > 0:
                primary_id = group[0].temporary_line_id
                member_ids = tuple(s.temporary_line_id for s in group)
                primary_to_members[primary_id] = member_ids

        # Verify mapping
        assert len(primary_to_members) == 1  # One multiplet group
        primary_id = list(primary_to_members.keys())[0]
        member_ids = primary_to_members[primary_id]

        assert len(member_ids) == 2
        assert set(member_ids) == {"mg2_2796", "mg2_2803"}


class TestMultipletDeletionExpansion:
    """Tests for _expand_multiplet_temporary_lines method."""

    def test_expand_multiplet_primary_id_to_all_members(self, atomic_data: AtomicLineData) -> None:
        """Deleting a multiplet should expand to all member IDs."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)
        redshift = 1.5

        lines = [
            _make_temporary_line(
                "mg2_2796",
                species=mg2_2796.species,
                center_z=redshift,
                line_id=mg2_2796.line_id,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                multiplet_id=mg2_2796.multiplet_id,
            ),
            _make_temporary_line(
                "mg2_2803",
                species=mg2_2803.species,
                center_z=redshift,
                line_id=mg2_2803.line_id,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                multiplet_id=mg2_2803.multiplet_id,
            ),
        ]

        # Build groups and mapping
        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        # Build _primary_to_members mapping
        primary_to_members: dict[str, tuple[str, ...]] = {}
        for group in groups:
            if len(group) > 0:
                primary_id = group[0].temporary_line_id
                member_ids = tuple(s.temporary_line_id for s in group)
                primary_to_members[primary_id] = member_ids

        # Test expansion: selecting primary ID should return all members
        expanded = _expand_temporary_lines(primary_to_members, ["mg2_2796"])

        # Should expand to both IDs
        assert set(expanded) == {"mg2_2796", "mg2_2803"}

    def test_expand_single_line_returns_same_id(self, atomic_data: AtomicLineData) -> None:
        """Single line (not multiplet) returns the same ID."""
        lines = [_make_temporary_line("single_line", species="H I", line_id=None)]

        # Build groups and mapping
        groups = _group_temporary_lines_by_multiplet(lines, atomic_data)

        # Build _primary_to_members mapping
        primary_to_members: dict[str, tuple[str, ...]] = {}
        for group in groups:
            if len(group) > 0:
                primary_id = group[0].temporary_line_id
                member_ids = tuple(s.temporary_line_id for s in group)
                primary_to_members[primary_id] = member_ids

        # Test expansion: single line should return same ID
        expanded = _expand_temporary_lines(primary_to_members, ["single_line"])

        # Should just return the same ID
        assert expanded == ["single_line"]

    def test_expand_unknown_id_passes_through(self) -> None:
        """Unknown ID not in mapping should pass through unchanged."""
        # Test expansion with unknown ID
        expanded = _expand_temporary_lines({}, ["unknown_id"])

        # Should pass through unchanged
        assert expanded == ["unknown_id"]
