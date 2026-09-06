"""Application use case for project creation, loading, saving, and error merge."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from chappy.application.project_mapper import (
    ProjectLoadResult,
    create_project_from_spectrum,
    project_from_document,
    project_to_document,
)
from chappy.application.project_schema import PROJECT_SCHEMA_VERSION

if TYPE_CHECKING:
    from chappy.application.ports.project_io import ProjectRepository, SpectrumReader
    from chappy.core.spectroscopy_project import SpectroscopyProject

logger = logging.getLogger(__name__)

PROJECT_EXTENSIONS = {".h5", ".hdf5"}
WAVELENGTH_TOLERANCE_ANGSTROMS = 0.01


class ProjectIOUseCase:
    """Application use case coordinating project file operations."""

    def __init__(
        self, *, spectrum_reader: SpectrumReader, project_repository: ProjectRepository
    ) -> None:
        """Initialize the use case.

        Args:
            spectrum_reader: Reader used for observed spectra.
            project_repository: Repository used for project persistence.
        """
        self._spectrum_reader = spectrum_reader
        self._project_repository = project_repository

    def create_from_fits(
        self, path: str, *, name: str | None = None, error_path: str | None = None
    ) -> SpectroscopyProject:
        """Create a project from a FITS spectrum.

        Args:
            path: FITS spectrum path.
            name: Optional project name.
            error_path: Optional FITS error spectrum path.

        Returns:
            Project initialized from the FITS spectrum.
        """
        project_name = name or Path(path).stem
        logger.info("Creating project from FITS file: %s", path)
        spectrum = self._spectrum_reader.read_spectrum(path)
        project = create_project_from_spectrum(spectrum, name=project_name, spectrum_filename=path)
        if error_path:
            self.merge_error_data(project, error_path)
        return project

    def merge_error_data(self, project: SpectroscopyProject, error_path: str) -> None:
        """Merge FITS error data into a project spectrum.

        Args:
            project: Project receiving error data.
            error_path: Error spectrum path.

        Raises:
            FileNotFoundError: If the error file does not exist.
            ValueError: If no project spectrum is loaded or wavelengths differ.
            OSError: If the error file cannot be read.
        """
        resolved_path = Path(error_path).resolve()
        if not resolved_path.exists():
            msg = f"Error file not found: {error_path}"
            raise FileNotFoundError(msg)
        if not resolved_path.is_file():
            msg = f"Error path is not a file: {error_path}"
            raise ValueError(msg)

        main_spectrum = project.model.observed_spectrum
        if main_spectrum is None:
            msg = "No spectrum loaded in project. Please load a main spectrum first."
            raise ValueError(msg)

        try:
            error_spectrum = self._spectrum_reader.read_spectrum(str(resolved_path))
        except (OSError, ValueError) as exc:
            msg = f"Failed to read error file {error_path}: {exc}"
            logger.warning(msg)
            raise OSError(msg) from exc

        if len(error_spectrum.wavelength) != len(main_spectrum.wavelength):
            msg = (
                f"Error file wavelength array length ({len(error_spectrum.wavelength)}) "
                f"doesn't match main spectrum ({len(main_spectrum.wavelength)})"
            )
            raise ValueError(msg)

        wavelength_diff = np.abs(error_spectrum.wavelength - main_spectrum.wavelength)
        max_diff = float(np.max(wavelength_diff))
        if max_diff > WAVELENGTH_TOLERANCE_ANGSTROMS:
            msg = (
                "Error file wavelength array differs from main spectrum by up to "
                f"{max_diff:.3f} Angstroms "
                f"(tolerance: {WAVELENGTH_TOLERANCE_ANGSTROMS:.3f})"
            )
            raise ValueError(msg)

        main_spectrum.assign_error(error_spectrum.flux)
        project.modified = datetime.now(UTC)

    def validate_fits_spectrum(self, path: str) -> tuple[bool, list[str]]:
        """Validate whether a FITS file can be used as a spectrum.

        Args:
            path: FITS file path.

        Returns:
            Pair of validity flag and validation issue messages.
        """
        return self._spectrum_reader.validate_spectrum(path)

    def get_fits_info(self, path: str) -> dict[str, object]:
        """Return FITS metadata for GUI inspection.

        Args:
            path: FITS file path.

        Returns:
            FITS metadata keyed by stable display field names.
        """
        return self._spectrum_reader.get_spectrum_info(path)

    def load_project(self, path: str) -> ProjectLoadResult:
        """Load a project from a repository path.

        Args:
            path: Project file path.

        Returns:
            Loaded project and any automatic topology repairs.
        """
        self._validate_project_extension(path)
        document = self._project_repository.load(path)
        return project_from_document(document)

    def save_project(self, project: SpectroscopyProject, path: str) -> None:
        """Save a project through the configured repository.

        Args:
            project: Project to persist.
            path: Destination path.

        Raises:
            ValueError: If the extension is unsupported.
        """
        self._validate_project_extension(path)

        now = datetime.now(UTC)
        project.metadata["version"] = project.metadata.get("version", "2.0")
        project.metadata["modified_date"] = now.isoformat()
        project.metadata["schema_version"] = PROJECT_SCHEMA_VERSION
        project.modified = now

        document = project_to_document(project)
        self._project_repository.save(document, path)
        logger.info("Project saved successfully: %s", path)

    def _validate_project_extension(self, path: str) -> None:
        suffix = Path(path).suffix.lower()
        if suffix not in PROJECT_EXTENSIONS:
            msg = f"Unsupported project file extension '{suffix}'. Expected .h5 or .hdf5"
            raise ValueError(msg)
