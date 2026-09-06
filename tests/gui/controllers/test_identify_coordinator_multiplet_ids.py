"""Tests for multiplet_ids cross-reference setup in IdentifyModeCoordinator."""

from __future__ import annotations

import pytest

from chappy.core.absorption.models import AbsorptionLine
from chappy.core.absorption.multiplet_service import setup_multiplet_cross_references
from chappy.core.atomic_data import AtomicLineData
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.infrastructure.atomic_lines import get_atomic_data


def _find_mg2_doublet(atomic_data: AtomicLineData) -> tuple[object, object]:
    """Find Mg II 2796 and 2803 lines from atomic database."""
    mg2_2796 = atomic_data.get_line_by_id("d85a4a9d4dfb3235")
    mg2_2803 = atomic_data.get_line_by_id("380d715c908636f5")
    assert mg2_2796 is not None, "Mg II 2796 not found in atomic database"
    assert mg2_2803 is not None, "Mg II 2803 not found in atomic database"
    return mg2_2796, mg2_2803


def _as_group_mapping(
    atomic_to_absorption: dict[str, AbsorptionLine],
) -> dict[str, list[AbsorptionLine]]:
    """Convert selected absorption lines into one declared tie group."""
    return {"preset:test:group": list(atomic_to_absorption.values())}


@pytest.fixture
def project() -> SpectroscopyProject:
    """Create a SpectroscopyProject instance."""
    return SpectroscopyProject()


@pytest.fixture
def atomic_data() -> AtomicLineData:
    """Create AtomicLineData instance."""
    return get_atomic_data()


class TestMultipletIdsCrossReference:
    """Tests for multiplet_ids cross-reference setup."""

    def test_mg2_doublet_shares_multiplet_id_in_atomic_db(
        self, atomic_data: AtomicLineData
    ) -> None:
        """Verify Mg II 2796 and 2803 share the same multiplet_id in atomic database."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)

        # Both should have the same multiplet_id
        assert mg2_2796.multiplet_id == mg2_2803.multiplet_id
        assert mg2_2796.multiplet_id != ""

    def test_doublet_lines_have_cross_references_after_setup(
        self, project: SpectroscopyProject, atomic_data: AtomicLineData
    ) -> None:
        """After setup_multiplet_cross_references, doublet lines should reference each other."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)
        redshift = 2.0

        # Create two absorption lines (simulating what _materialize_temporary_line does)
        line_2796 = project.add_absorption_line(
            species=mg2_2796.species,
            transition_name=mg2_2796.transition_name,
            rest_wavelength=mg2_2796.wavelength_angstrom,
            center_z=redshift,
            window_kms=100.0,
            lambda_range=(8384, 8394),
            multiplet_ids=[],  # Initially empty (this is what we want after fix)
            multiplet_label="",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        line_2803 = project.add_absorption_line(
            species=mg2_2803.species,
            transition_name=mg2_2803.transition_name,
            rest_wavelength=mg2_2803.wavelength_angstrom,
            center_z=redshift,
            window_kms=100.0,
            lambda_range=(8405, 8415),
            multiplet_ids=[],  # Initially empty
            multiplet_label="",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )

        # Map from atomic line ID to absorption line
        atomic_to_absorption: dict[str, AbsorptionLine] = {
            mg2_2796.line_id: line_2796,
            mg2_2803.line_id: line_2803,
        }

        setup_multiplet_cross_references(grouped_lines=_as_group_mapping(atomic_to_absorption))

        # Verify cross-references are set
        assert line_2803.line_id in line_2796.multiplet_ids, (
            f"Line 2796 should reference line 2803. multiplet_ids={line_2796.multiplet_ids}"
        )
        assert line_2796.line_id in line_2803.multiplet_ids, (
            f"Line 2803 should reference line 2796. multiplet_ids={line_2803.multiplet_ids}"
        )

    def test_single_line_has_empty_multiplet_ids_after_setup(
        self, project: SpectroscopyProject, atomic_data: AtomicLineData
    ) -> None:
        """Single line without multiplet partner should have empty multiplet_ids."""
        # Find H I Lyman alpha (no multiplet siblings)
        h1_lines = [
            ln
            for ln in atomic_data.lines
            if ln.species == "H I" and 1215 < ln.wavelength_angstrom < 1217
        ]
        if not h1_lines:
            pytest.skip("H I Lyman alpha not found in atomic database")

        h1_lya = h1_lines[0]
        redshift = 2.0

        # Create single absorption line
        line = project.add_absorption_line(
            species=h1_lya.species,
            transition_name=h1_lya.transition_name,
            rest_wavelength=h1_lya.wavelength_angstrom,
            center_z=redshift,
            window_kms=100.0,
            lambda_range=(3640, 3650),
            multiplet_ids=[],
            multiplet_label="",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )

        atomic_to_absorption: dict[str, AbsorptionLine] = {h1_lya.line_id: line}

        setup_multiplet_cross_references(grouped_lines=_as_group_mapping(atomic_to_absorption))

        # Single line should still have empty multiplet_ids
        assert line.multiplet_ids == [], (
            f"Single line should have empty multiplet_ids: {line.multiplet_ids}"
        )

    def test_triplet_lines_have_mutual_cross_references_after_setup(
        self, project: SpectroscopyProject, atomic_data: AtomicLineData
    ) -> None:
        """Triplet lines should all cross-reference each other."""
        # Find a triplet in the atomic database
        multiplet_groups: dict[str, list[object]] = {}
        for line in atomic_data.lines:
            if line.multiplet_id:
                multiplet_groups.setdefault(line.multiplet_id, []).append(line)

        # Find a triplet (3+ lines with same multiplet_id)
        triplet_lines: list[object] | None = None
        for lines in multiplet_groups.values():
            if len(lines) >= 3:
                triplet_lines = sorted(lines, key=lambda x: x.wavelength_angstrom)[:3]
                break

        if triplet_lines is None:
            pytest.skip("No triplet found in atomic database")

        redshift = 1.5
        atomic_to_absorption: dict[str, AbsorptionLine] = {}

        # Create absorption lines for triplet
        for atomic_line in triplet_lines:
            obs_wl = atomic_line.wavelength_angstrom * (1 + redshift)
            line = project.add_absorption_line(
                species=atomic_line.species,
                transition_name=atomic_line.transition_name,
                rest_wavelength=atomic_line.wavelength_angstrom,
                center_z=redshift,
                window_kms=100.0,
                lambda_range=(obs_wl - 5, obs_wl + 5),
                multiplet_ids=[],
                multiplet_label="",
                oscillator_strength=0.1,
                gamma_value=1e8,
            )
            atomic_to_absorption[atomic_line.line_id] = line

        setup_multiplet_cross_references(grouped_lines=_as_group_mapping(atomic_to_absorption))

        # Each line should reference the other two
        abs_lines = list(atomic_to_absorption.values())
        line_ids = {ln.line_id for ln in abs_lines}

        for line in abs_lines:
            other_ids = line_ids - {line.line_id}
            for other_id in other_ids:
                assert other_id in line.multiplet_ids, (
                    f"Line {line.line_id} should reference {other_id}. "
                    f"multiplet_ids={line.multiplet_ids}"
                )

    def test_different_multiplets_not_cross_referenced(
        self, project: SpectroscopyProject, atomic_data: AtomicLineData
    ) -> None:
        """Lines from different multiplets should not cross-reference each other."""
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)

        # Find a different line (H I Lyman alpha)
        h1_lines = [
            ln
            for ln in atomic_data.lines
            if ln.species == "H I" and 1215 < ln.wavelength_angstrom < 1217
        ]
        if not h1_lines:
            pytest.skip("H I Lyman alpha not found in atomic database")

        h1_lya = h1_lines[0]
        redshift = 2.0

        # Create absorption lines
        line_mg2 = project.add_absorption_line(
            species=mg2_2796.species,
            transition_name=mg2_2796.transition_name,
            rest_wavelength=mg2_2796.wavelength_angstrom,
            center_z=redshift,
            window_kms=100.0,
            lambda_range=(8384, 8394),
            multiplet_ids=[],
            multiplet_label="",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        line_h1 = project.add_absorption_line(
            species=h1_lya.species,
            transition_name=h1_lya.transition_name,
            rest_wavelength=h1_lya.wavelength_angstrom,
            center_z=redshift,
            window_kms=100.0,
            lambda_range=(3640, 3650),
            multiplet_ids=[],
            multiplet_label="",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )

        atomic_to_absorption: dict[str, AbsorptionLine] = {
            mg2_2796.line_id: line_mg2,
            h1_lya.line_id: line_h1,
        }

        setup_multiplet_cross_references(
            grouped_lines={"preset:test:mg": [line_mg2], "preset:test:h": [line_h1]}
        )

        # H I should not reference Mg II and vice versa
        assert line_mg2.line_id not in line_h1.multiplet_ids
        assert line_h1.line_id not in line_mg2.multiplet_ids

    def test_multiple_doublets_at_different_redshifts(
        self, project: SpectroscopyProject, atomic_data: AtomicLineData
    ) -> None:
        """Multiple Mg II doublets at different redshifts should each be cross-referenced separately.

        This tests the scenario where 3 Mg II doublets are identified at z=1.5, 1.7, 1.9.
        Each doublet should have its own cross-references, not cross-reference lines from
        other redshifts.

        The key issue is that atomic_line_id (from database) is the same for all Mg II 2796
        lines regardless of redshift. So the mapping needs to handle multiple absorption lines
        per atomic line ID.
        """
        mg2_2796, mg2_2803 = _find_mg2_doublet(atomic_data)

        # Create three Mg II doublets at different redshifts
        redshifts = [1.5, 1.7, 1.9]
        doublets: list[tuple[AbsorptionLine, AbsorptionLine]] = []

        for z in redshifts:
            line_2796 = project.add_absorption_line(
                species=mg2_2796.species,
                transition_name=mg2_2796.transition_name,
                rest_wavelength=mg2_2796.wavelength_angstrom,
                center_z=z,
                window_kms=100.0,
                lambda_range=(
                    mg2_2796.wavelength_angstrom * (1 + z) - 5,
                    mg2_2796.wavelength_angstrom * (1 + z) + 5,
                ),
                multiplet_ids=[],
                multiplet_label="",
                oscillator_strength=0.1,
                gamma_value=1e8,
            )
            line_2803 = project.add_absorption_line(
                species=mg2_2803.species,
                transition_name=mg2_2803.transition_name,
                rest_wavelength=mg2_2803.wavelength_angstrom,
                center_z=z,
                window_kms=100.0,
                lambda_range=(
                    mg2_2803.wavelength_angstrom * (1 + z) - 5,
                    mg2_2803.wavelength_angstrom * (1 + z) + 5,
                ),
                multiplet_ids=[],
                multiplet_label="",
                oscillator_strength=0.1,
                gamma_value=1e8,
            )
            doublets.append((line_2796, line_2803))

        # Each declaration represents one observed doublet at one redshift.
        setup_multiplet_cross_references(
            grouped_lines={
                f"preset:test:doublet:{index}": [line_2796, line_2803]
                for index, (line_2796, line_2803) in enumerate(doublets)
            }
        )

        # Each doublet should have cross-references within itself only
        for i, (line_2796, line_2803) in enumerate(doublets):
            # Lines within the same doublet should cross-reference each other
            assert line_2803.line_id in line_2796.multiplet_ids, (
                f"Doublet {i}: 2796 should reference 2803"
            )
            assert line_2796.line_id in line_2803.multiplet_ids, (
                f"Doublet {i}: 2803 should reference 2796"
            )

            # Lines should NOT reference lines from other doublets
            for j, (other_2796, other_2803) in enumerate(doublets):
                if i == j:
                    continue
                assert other_2796.line_id not in line_2796.multiplet_ids, (
                    f"Doublet {i} 2796 should not reference doublet {j} 2796"
                )
                assert other_2803.line_id not in line_2796.multiplet_ids, (
                    f"Doublet {i} 2796 should not reference doublet {j} 2803"
                )
