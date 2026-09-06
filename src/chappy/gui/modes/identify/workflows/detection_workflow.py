"""Detection computation workflow for identify mode."""

from __future__ import annotations

import math
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from chappy.application.identify import (
    DetectCandidateLinesRequest,
    DetectCandidateLinesUseCase,
    DetectionErrorCode,
)
from chappy.core.absorption.search9_detection import (
    DEFAULT_BOUNDARY_SIGMA,
    DEFAULT_KERNEL_HALF_WIDTH,
    Search9Parameters,
)
from chappy.core.components.continuum import ContinuumComponent
from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.gui.modes.identify.application_adapters import detected_region_from_snapshot

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from numpy.typing import NDArray

    from chappy.core.identify_state import DetectedRegion, IdentifySessionState
    from chappy.core.spectroscopy_project import SpectroscopyProject


type DetectionErrorFormatValue = str | int | float


@dataclass(frozen=True, slots=True)
class IdentifyDetectionMessages:
    """Translated messages used by detection workflow."""

    error_spectrum_required: str
    insufficient_data: str
    no_continuum: str
    failed_template: str
    unknown: str


@dataclass(frozen=True, slots=True)
class IdentifyDetectionWorkflowPorts:
    """External state and callbacks required by detection workflow."""

    project_provider: Callable[[], SpectroscopyProject | None]
    session_provider: Callable[[], IdentifySessionState]
    sigma_threshold_provider: Callable[[], float]
    status_callback: Callable[[str], None]
    messages_provider: Callable[[], IdentifyDetectionMessages]


class IdentifyDetectionWorkflow:
    """Compute detection regions and map detection errors to status messages."""

    def __init__(
        self, ports: IdentifyDetectionWorkflowPorts, usecase: DetectCandidateLinesUseCase
    ) -> None:
        """Initialize the workflow."""
        self._ports = ports
        self._usecase = usecase
        self._last_detection_error: str | None = None

    def compute_detection_regions(self) -> list[DetectedRegion] | None:
        """Compute detected regions for the current identify session."""
        project = self._ports.project_provider()
        if project is None:
            return []

        spectrum = project.model.observed_spectrum
        if spectrum is None:
            return []

        session = self._ports.session_provider()
        result = self._usecase.detect(
            DetectCandidateLinesRequest(
                wavelength=spectrum.wavelength,
                flux=spectrum.flux,
                error=spectrum.error,
                continuum_flux=self._resolve_continuum_flux(project, spectrum.wavelength),
                parameters=self._build_detection_parameters(project),
                existing_line_ranges=tuple(self._compute_line_ranges(project)),
                temporary_line_ranges=tuple(
                    (line.lambda_min, line.lambda_max) for line in session.temporary_lines
                ),
            )
        )

        if result.error_code is not None:
            self._emit_detection_result_error(result.error_code, result.error_detail)
            return None

        self._last_detection_error = None
        return [detected_region_from_snapshot(region) for region in result.regions]

    def _build_detection_parameters(
        self, project: SpectroscopyProject | None
    ) -> Search9Parameters:
        n_sigma = max(2.0, min(100.0, self._ports.sigma_threshold_provider()))
        resolution: float | None = None
        resolution_enabled = False
        if project is not None:
            state = project.resolution_state
            resolution = float(state.value)
            resolution_enabled = state.enabled and math.isfinite(resolution) and resolution > 0

        return Search9Parameters(
            n_sigma=n_sigma,
            boundary_sigma=DEFAULT_BOUNDARY_SIGMA,
            kernel_half_width=DEFAULT_KERNEL_HALF_WIDTH,
            resolution=resolution,
            resolution_enabled=resolution_enabled,
        )

    def _resolve_continuum_flux(
        self, project: SpectroscopyProject, wavelengths: Sequence[float] | NDArray[np.float64]
    ) -> NDArray[np.float64] | None:
        continuum_component: ContinuumComponent | None = None
        fallback_component: ContinuumComponent | None = None

        for component in project.model.components:
            if not isinstance(component, ContinuumComponent):
                continue
            if not component.enabled:
                continue
            if component.is_shared_with_absorption:
                continuum_component = component
                break
            if fallback_component is None:
                fallback_component = component

        continuum_component = continuum_component or fallback_component
        if continuum_component is None:
            return None

        wavelength_array = np.asarray(wavelengths, dtype=float)
        if wavelength_array.size == 0:
            return None

        try:
            flux = continuum_component.calculate(wavelength_array)
        except (TypeError, ValueError, RuntimeError):  # pragma: no cover - defensive
            return None
        if not isinstance(flux, np.ndarray):
            return None
        if flux.size != wavelength_array.size:
            return None
        return flux.astype(float, copy=False)

    def _compute_line_ranges(self, project: SpectroscopyProject) -> list[tuple[float, float]]:
        ranges: list[tuple[float, float]] = []
        for line in project.list_absorption_lines():
            if line.lambda_range:
                start, end = line.lambda_range
            else:
                observed = line.observed_wavelength()
                if observed <= 0:
                    continue
                delta = abs(observed * (line.window_kms / LIGHT_SPEED_KMS))
                start, end = observed - delta, observed + delta
            ranges.append((start, end))
        return ranges

    def _emit_detection_result_error(
        self, error_code: DetectionErrorCode, detail: str | None
    ) -> None:
        messages = self._ports.messages_provider()
        if error_code is DetectionErrorCode.NO_ERROR_ARRAY:
            self._emit_detection_error(error_code.value, messages.error_spectrum_required)
        elif error_code is DetectionErrorCode.INSUFFICIENT_DATA:
            self._emit_detection_error(error_code.value, messages.insufficient_data)
        elif error_code is DetectionErrorCode.NO_CONTINUUM:
            self._emit_detection_error(error_code.value, messages.no_continuum)
        else:
            self._emit_detection_error(
                error_code.value,
                messages.failed_template,
                format_kwargs={"reason": detail or messages.unknown},
            )

    def _emit_detection_error(
        self,
        code: str,
        message: str,
        *,
        format_kwargs: dict[str, DetectionErrorFormatValue] | None = None,
    ) -> None:
        if self._last_detection_error == code:
            return
        self._last_detection_error = code
        if format_kwargs:
            with suppress(KeyError, ValueError):
                message = message.format(**format_kwargs)
        self._ports.status_callback(message)
