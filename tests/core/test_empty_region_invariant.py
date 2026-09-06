"""Tests for empty region invariant enforcement."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from chappy.application.project_io_usecase import ProjectIOUseCase
from chappy.application.structure.region_line_topology import (
    RegionLineTopologyIssueKind,
    find_region_line_topology_issues,
)
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.infrastructure.project_io_factory import create_default_project_io_usecase


@pytest.fixture
def project_with_spectrum() -> SpectroscopyProject:
    """Create a project with a minimal observed spectrum."""
    project = SpectroscopyProject(name="Test Project")
    wavelength = np.linspace(1000.0, 2000.0, 100, dtype=float)
    flux = np.ones(100, dtype=float)
    error = np.full(100, 0.05, dtype=float)
    project.model.set_observed_spectrum(Spectrum(wavelength=wavelength, flux=flux, error=error))
    return project


@pytest.fixture
def project_io() -> ProjectIOUseCase:
    """Create the default project I/O use case."""
    return create_default_project_io_usecase()


class TestCreateRegionWithLines:
    """Tests for SpectroscopyProject.create_region_with_lines."""

    def test_empty_list_raises_value_error(
        self, project_with_spectrum: SpectroscopyProject
    ) -> None:
        """Passing an empty line_ids list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot create region without lines"):
            project_with_spectrum.create_region_with_lines([])

    def test_valid_lines_creates_region(self, project_with_spectrum: SpectroscopyProject) -> None:
        """Creating a region with valid lines assigns them correctly."""
        project = project_with_spectrum

        line1 = project.add_absorption_line(
            species="C IV",
            rest_wavelength=1548.195,
            center_z=0.5,
            window_kms=150.0,
            multiplet_label="C IV 1548/C IV 1551",
            transition_name="C IV 1548",
            oscillator_strength=0.19,
            gamma_value=2.65e8,
            lambda_range=(1500.0, 1600.0),
        )
        line2 = project.add_absorption_line(
            species="C IV",
            rest_wavelength=1550.77,
            center_z=0.5,
            window_kms=150.0,
            multiplet_label="C IV 1548/C IV 1551",
            transition_name="C IV 1551",
            oscillator_strength=0.095,
            gamma_value=2.64e8,
            lambda_range=(1500.0, 1600.0),
        )

        region = project.create_region_with_lines([line1.line_id, line2.line_id])

        assert line1.line_id in region.line_ids
        assert line2.line_id in region.line_ids
        assert project.absorption_lines[line1.line_id].region_id == region.region_id
        assert project.absorption_lines[line2.line_id].region_id == region.region_id


class TestPruneEmptyAbsorptionRegions:
    """Tests for SpectroscopyProject._prune_empty_absorption_regions."""

    def test_removes_empty_regions(self, project_with_spectrum: SpectroscopyProject) -> None:
        """Empty non-UNASSIGNED regions are removed."""
        project = project_with_spectrum

        # Create an empty region directly (bypassing invariant)
        empty_region = project.create_absorption_region()
        assert empty_region.region_id in project.absorption_regions

        project.prune_empty_absorption_regions()

        assert empty_region.region_id not in project.absorption_regions

    def test_preserves_unassigned_region(self, project_with_spectrum: SpectroscopyProject) -> None:
        """UNASSIGNED region is never removed even if empty."""
        project = project_with_spectrum

        # Ensure UNASSIGNED region exists (it's lazily created)
        project.ensure_absorption_unassigned_region()

        assert len(project.absorption_regions[UNASSIGNED_REGION_ID].line_ids) == 0

        project.prune_empty_absorption_regions()

        # UNASSIGNED should still exist
        assert UNASSIGNED_REGION_ID in project.absorption_regions

    def test_preserves_non_empty_regions(self, project_with_spectrum: SpectroscopyProject) -> None:
        """Regions with lines are preserved."""
        project = project_with_spectrum

        line = project.add_absorption_line(
            species="H I",
            rest_wavelength=1215.67,
            center_z=0.2,
            window_kms=100.0,
            multiplet_label="",
            transition_name="Ly-α",
            oscillator_strength=0.416,
            gamma_value=6.27e8,
            lambda_range=(1200.0, 1250.0),
        )
        region = project.create_region_with_lines([line.line_id])

        project.prune_empty_absorption_regions()

        assert region.region_id in project.absorption_regions


class TestPersistence:
    """Tests for persistence behavior with empty region invariant."""

    def test_hdf5_load_prunes_empty_regions(
        self, project_io: ProjectIOUseCase, project_with_spectrum: SpectroscopyProject
    ) -> None:
        """Loading from HDF5 removes empty regions."""
        project = project_with_spectrum

        # Create a region with a line
        line = project.add_absorption_line(
            species="C IV",
            rest_wavelength=1548.195,
            center_z=0.5,
            window_kms=150.0,
            multiplet_label="C IV 1548/C IV 1551",
            transition_name="C IV 1548",
            oscillator_strength=0.19,
            gamma_value=2.65e8,
            lambda_range=(1500.0, 1600.0),
        )
        non_empty_region = project.create_region_with_lines([line.line_id])

        # Create an empty region directly
        empty_region = project.create_absorption_region()

        with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            project_io.save_project(project, str(tmp_path))

            # Load the project - prune should be called
            loaded = project_io.load_project(str(tmp_path)).project

            # Empty region should be removed
            assert empty_region.region_id not in loaded.absorption_regions
            # Non-empty region should be preserved
            assert non_empty_region.region_id in loaded.absorption_regions
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_roundtrip_preserves_region_line_consistency(
        self, project_io: ProjectIOUseCase, project_with_spectrum: SpectroscopyProject
    ) -> None:
        """Save/load preserves region-line bidirectional references."""
        project = project_with_spectrum

        line1 = project.add_absorption_line(
            species="C IV",
            rest_wavelength=1548.195,
            center_z=0.5,
            window_kms=150.0,
            multiplet_label="C IV 1548/C IV 1551",
            transition_name="C IV 1548",
            oscillator_strength=0.19,
            gamma_value=2.65e8,
            lambda_range=(1500.0, 1600.0),
        )
        line2 = project.add_absorption_line(
            species="C IV",
            rest_wavelength=1550.77,
            center_z=0.5,
            window_kms=150.0,
            multiplet_label="C IV 1548/C IV 1551",
            transition_name="C IV 1551",
            oscillator_strength=0.095,
            gamma_value=2.64e8,
            lambda_range=(1500.0, 1600.0),
        )
        region = project.create_region_with_lines([line1.line_id, line2.line_id])

        with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            project_io.save_project(project, str(tmp_path))
            loaded = project_io.load_project(str(tmp_path)).project

            # Region should have both line_ids
            loaded_region = loaded.absorption_regions[region.region_id]
            assert line1.line_id in loaded_region.line_ids
            assert line2.line_id in loaded_region.line_ids

            # Lines should reference the region
            assert loaded.absorption_lines[line1.line_id].region_id == region.region_id
            assert loaded.absorption_lines[line2.line_id].region_id == region.region_id
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_hdf5_roundtrip_repairs_mismatched_region_reference(
        self, project_io: ProjectIOUseCase, project_with_spectrum: SpectroscopyProject
    ) -> None:
        """Loading a persisted mismatch repairs it without editing HDF5 directly."""
        line = project_with_spectrum.add_absorption_line(
            species="C IV",
            rest_wavelength=1548.195,
            center_z=0.5,
            window_kms=150.0,
            multiplet_label="C IV",
            transition_name="1548",
            oscillator_strength=0.19,
            gamma_value=2.65e8,
            lambda_range=(1500.0, 1600.0),
        )
        region = project_with_spectrum.create_region_with_lines([line.line_id])
        line.region_id = "missing-region"

        with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            project_io.save_project(project_with_spectrum, str(tmp_path))

            result = project_io.load_project(str(tmp_path))

            assert result.project.absorption_lines[line.line_id].region_id == region.region_id
            assert [action.kind for action in result.repair_report.actions] == [
                RegionLineTopologyIssueKind.REGION_LINE_MISMATCH
            ]
            assert (
                find_region_line_topology_issues(
                    result.project.absorption_regions, result.project.absorption_lines
                )
                == ()
            )
        finally:
            tmp_path.unlink(missing_ok=True)
