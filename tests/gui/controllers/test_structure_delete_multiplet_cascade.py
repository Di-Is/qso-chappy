"""Tests for structure delete multiplet cascade behavior.

When a consolidated multiplet row is deleted from StructureSidePanel,
all member lines should be removed together (ADR: multiplet-display-consolidation).
"""

from __future__ import annotations

import pytest

from chappy.core.absorption.models import AbsorptionLine
from chappy.core.spectroscopy_project import SpectroscopyProject


def _make_doublet(
    project: SpectroscopyProject, z: float = 1.5
) -> tuple[AbsorptionLine, AbsorptionLine]:
    """Create a Mg II doublet with proper cross-references."""
    line_2796 = AbsorptionLine(
        line_id=f"mg2_2796_z{z}",
        species="Mg II",
        rest_wavelength=2796.35,
        center_z=z,
        window_kms=150.0,
        multiplet_label="Mg II 2796/2803",
        transition_name="Mg II 2796.4",
        oscillator_strength=0.612,
        gamma_value=2.6e8,
        multiplet_ids=[],  # Will be set up below
    )
    line_2803 = AbsorptionLine(
        line_id=f"mg2_2803_z{z}",
        species="Mg II",
        rest_wavelength=2803.53,
        center_z=z,
        window_kms=150.0,
        multiplet_label="Mg II 2796/2803",
        transition_name="Mg II 2803.5",
        oscillator_strength=0.305,
        gamma_value=2.6e8,
        multiplet_ids=[],
    )

    # Set up cross-references
    line_2796.multiplet_ids.append(line_2803.line_id)
    line_2803.multiplet_ids.append(line_2796.line_id)

    # Register in project
    project.absorption_lines[line_2796.line_id] = line_2796
    project.absorption_lines[line_2803.line_id] = line_2803

    return line_2796, line_2803


class TestStructureDeleteMultipletCascade:
    """Tests for multiplet cascade deletion from structure panel."""

    def test_delete_primary_line_removes_all_multiplet_members(self) -> None:
        """Deleting primary line ID should remove all multiplet members.

        This simulates what happens when user selects a consolidated multiplet
        row in StructureSidePanel and presses Delete. The selection contains only
        the primary line_id (line_ids[0]), but all members should be removed.
        """
        project = SpectroscopyProject()
        line_2796, line_2803 = _make_doublet(project)

        # Verify both lines exist
        assert line_2796.line_id in project.absorption_lines
        assert line_2803.line_id in project.absorption_lines

        # Simulate structure delete: only primary line ID is selected
        # (This is what _execute_structure_delete receives from the consolidated row)
        selected_linked_line_ids = [line_2796.line_id]

        # Execute deletion using the multiplet-aware method
        removed_count = project.remove_absorption_lines_with_multiplet(
            selected_linked_line_ids, delete_models=True
        )

        # Both lines should be removed
        assert removed_count == 2, f"Expected 2 lines removed, got {removed_count}"
        assert line_2796.line_id not in project.absorption_lines, "Primary line should be removed"
        assert line_2803.line_id not in project.absorption_lines, (
            "Secondary line should also be removed (multiplet cascade)"
        )

    def test_delete_secondary_line_removes_all_multiplet_members(self) -> None:
        """Deleting secondary line ID should also remove all multiplet members."""
        project = SpectroscopyProject()
        line_2796, line_2803 = _make_doublet(project)

        # Select only secondary line (2803)
        selected_linked_line_ids = [line_2803.line_id]

        removed_count = project.remove_absorption_lines_with_multiplet(
            selected_linked_line_ids, delete_models=True
        )

        # Both lines should be removed
        assert removed_count == 2
        assert line_2796.line_id not in project.absorption_lines
        assert line_2803.line_id not in project.absorption_lines

    def test_delete_single_line_without_multiplet(self) -> None:
        """Single line without multiplet should be deleted alone."""
        project = SpectroscopyProject()

        single_line = AbsorptionLine(
            line_id="h1_lya",
            species="H I",
            rest_wavelength=1215.67,
            center_z=2.0,
            window_kms=150.0,
            multiplet_label="",
            transition_name="H I Ly-α",
            oscillator_strength=0.416,
            gamma_value=6.27e8,
            multiplet_ids=[],  # No multiplet
        )
        project.absorption_lines[single_line.line_id] = single_line

        selected_linked_line_ids = [single_line.line_id]
        removed_count = project.remove_absorption_lines_with_multiplet(
            selected_linked_line_ids, delete_models=True
        )

        assert removed_count == 1
        assert single_line.line_id not in project.absorption_lines

    def test_delete_multiple_independent_lines(self) -> None:
        """Multiple independent lines should each be deleted."""
        project = SpectroscopyProject()

        line1 = AbsorptionLine(
            line_id="line1",
            species="H I",
            rest_wavelength=1215.67,
            center_z=1.0,
            window_kms=150.0,
            multiplet_label="",
            transition_name="H I Ly-α",
            oscillator_strength=0.416,
            gamma_value=6.27e8,
            multiplet_ids=[],
        )
        line2 = AbsorptionLine(
            line_id="line2",
            species="C IV",
            rest_wavelength=1548.2,
            center_z=1.5,
            window_kms=150.0,
            multiplet_label="",
            transition_name="C IV 1548.2",
            oscillator_strength=0.19,
            gamma_value=2.65e8,
            multiplet_ids=[],
        )
        project.absorption_lines[line1.line_id] = line1
        project.absorption_lines[line2.line_id] = line2

        selected_linked_line_ids = [line1.line_id, line2.line_id]
        removed_count = project.remove_absorption_lines_with_multiplet(
            selected_linked_line_ids, delete_models=True
        )

        assert removed_count == 2
        assert line1.line_id not in project.absorption_lines
        assert line2.line_id not in project.absorption_lines

    def test_delete_multiplet_and_single_line_together(self) -> None:
        """Deleting multiplet + single line together should remove all."""
        project = SpectroscopyProject()

        # Create doublet
        line_2796, line_2803 = _make_doublet(project)

        # Create single line
        single_line = AbsorptionLine(
            line_id="h1_lya",
            species="H I",
            rest_wavelength=1215.67,
            center_z=2.0,
            window_kms=150.0,
            multiplet_label="",
            transition_name="H I Ly-α",
            oscillator_strength=0.416,
            gamma_value=6.27e8,
            multiplet_ids=[],
        )
        project.absorption_lines[single_line.line_id] = single_line

        # Select primary of doublet + single line
        selected_linked_line_ids = [line_2796.line_id, single_line.line_id]
        removed_count = project.remove_absorption_lines_with_multiplet(
            selected_linked_line_ids, delete_models=True
        )

        # 3 lines total: 2 from doublet + 1 single
        assert removed_count == 3
        assert line_2796.line_id not in project.absorption_lines
        assert line_2803.line_id not in project.absorption_lines
        assert single_line.line_id not in project.absorption_lines
