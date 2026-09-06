"""Own spectrum viewport focus policy for selected absorption regions."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from chappy.core.constants import LIGHT_SPEED_KMS

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.spectrum.spectrum_view import SpectrumView

LAMBDA_RANGE_SIZE = 2


class SpectrumRegionFocusController:
    """Compute and apply viewport focus for a selected absorption region."""

    def __init__(
        self,
        *,
        project_provider: Callable[[], SpectroscopyProject | None],
        spectrum_view_provider: Callable[[], SpectrumView | None],
    ) -> None:
        """Store focus policy dependencies."""
        self._project_provider = project_provider
        self._spectrum_view_provider = spectrum_view_provider

    def focus_region(self, absorption_region: AbsorptionRegion) -> None:
        """Focus the spectrum viewport on the provided region."""
        project = self._project_provider()
        spectrum_view = self._spectrum_view_provider()
        if project is None or spectrum_view is None:
            return

        # The plot host renders model/residual only for the selected region;
        # focusing a region is the single place that selection is decided.
        spectrum_view.plot_host.set_selected_absorption_region(absorption_region)

        bounds = [
            self._line_wavelength_bounds(project.absorption_lines.get(line_id))
            for line_id in absorption_region.line_ids
        ]
        valid_bounds = [bound for bound in bounds if bound is not None]
        if not valid_bounds:
            return

        min_wave = min(bound[0] for bound in valid_bounds)
        max_wave = max(bound[1] for bound in valid_bounds)
        if max_wave <= min_wave:
            return

        span = max_wave - min_wave
        padding = max(10.0, span * 0.1) if span > 0 else 10.0
        display_min = min_wave - padding
        display_max = max_wave + padding

        flux_range = self._compute_flux_range(project, display_min, display_max)
        spectrum_view.coordinator.coordinate_range_update(
            "group-selection", display_min, display_max, flux_range=flux_range
        )

        resolved_wavelength_range = spectrum_view.get_wavelength_range()
        resolved_flux_range = spectrum_view.get_flux_range()
        spectrum_view.set_reset_ranges(resolved_wavelength_range, resolved_flux_range)

    @staticmethod
    def _line_wavelength_bounds(line: AbsorptionLine | None) -> tuple[float, float] | None:
        """Return wavelength bounds for a line."""
        if line is None:
            return None

        if line.lambda_range and len(line.lambda_range) == LAMBDA_RANGE_SIZE:
            lower, upper = line.lambda_range
            if lower < upper:
                return float(lower), float(upper)

        observed = line.observed_wavelength()
        window = line.window_kms
        if (
            not math.isfinite(observed)
            or not math.isfinite(window)
            or observed <= 0.0
            or window <= 0.0
        ):
            msg = (
                f"Invalid absorption line wavelength bounds for {line.line_id}: "
                f"observed={observed}, window_kms={window}."
            )
            raise ValueError(msg)

        delta = observed * window / LIGHT_SPEED_KMS
        lower = observed - delta
        upper = observed + delta
        if lower >= upper:
            return None
        return float(lower), float(upper)

    @staticmethod
    def _compute_flux_range(
        project: SpectroscopyProject, min_wave: float, max_wave: float
    ) -> tuple[float, float] | None:
        """Return a display-oriented flux range for the requested wavelength span."""
        if not math.isfinite(min_wave) or not math.isfinite(max_wave) or min_wave >= max_wave:
            msg = f"Invalid wavelength bounds for flux range: {min_wave}, {max_wave}."
            raise ValueError(msg)

        spectrum = project.model.observed_spectrum
        if spectrum is None:
            return None

        wave_array = np.asarray(spectrum.wavelength)
        flux_array = np.asarray(spectrum.flux)
        if wave_array.size == 0 or flux_array.size == 0:
            return None
        if wave_array.shape != flux_array.shape:
            msg = (
                "Observed spectrum wavelength and flux arrays must have matching shape. "
                f"Got {wave_array.shape} and {flux_array.shape}."
            )
            raise ValueError(msg)

        mask = (wave_array >= min_wave) & (wave_array <= max_wave)
        if not np.any(mask):
            return None

        finite_flux = flux_array[mask][np.isfinite(flux_array[mask])]
        if finite_flux.size == 0:
            return None

        flux_min = float(np.min(finite_flux))
        flux_max = float(np.max(finite_flux))
        flux_span = flux_max - flux_min
        padding = flux_span * 0.1
        adjusted_min = min(-0.1, flux_min - padding)
        adjusted_max = max(1.1, flux_max + 0.1)
        if adjusted_min >= adjusted_max:
            adjusted_max = adjusted_min + 0.1
        return adjusted_min, adjusted_max


__all__ = ["SpectrumRegionFocusController"]
