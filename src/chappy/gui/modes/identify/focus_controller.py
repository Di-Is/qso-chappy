"""Spectrum focus controller for identify mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.application.spectrum.range_usecase import (
    MIN_WAVELENGTH_DISPLAY_SPAN,
    enforce_min_wavelength_span,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from chappy.gui.modes.identify.panel.panel_models import CandidateRow


class IdentifyFocusRangeCoordinatorPort(Protocol):
    """Spectrum range operations required by identify focus routing."""

    def coordinate_range_update(
        self, source: str, x_min: float, x_max: float, *, record_history: bool = True
    ) -> None:
        """Apply a wavelength range update."""
        ...

    def handle_auto_flux_range_request(self) -> None:
        """Apply automatic flux range adjustment."""
        ...


class IdentifyFocusSpectrumViewPort(Protocol):
    """Spectrum view operations required by identify focus routing."""

    @property
    def coordinator(self) -> IdentifyFocusRangeCoordinatorPort:
        """Return the spectrum range coordinator."""
        ...

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the displayed wavelength range."""
        ...


@dataclass(frozen=True, slots=True)
class IdentifyFocusMessages:
    """Translated messages emitted by identify focus workflows."""

    candidate_template: str
    group_template: str
    line_template: str


@dataclass(frozen=True, slots=True)
class IdentifyFocusPorts:
    """External state and callbacks required by identify focus workflows."""

    candidate_rows_provider: Callable[[], Sequence[CandidateRow]]
    spectrum_view_provider: Callable[[], IdentifyFocusSpectrumViewPort | None]
    data_bounds_provider: Callable[[], tuple[float, float] | None]
    status_callback: Callable[[str], None]
    messages_provider: Callable[[], IdentifyFocusMessages]


class IdentifySpectrumFocusController:
    """Coordinate spectrum focusing for identify candidate and workflow rows."""

    GROUP_FOCUS_PADDING_FRACTION = 0.10
    GROUP_FOCUS_MIN_PADDING = 0.5
    LINE_FOCUS_PADDING_FRACTION = 0.05
    LINE_FOCUS_MIN_PADDING = 0.2

    def __init__(self, ports: IdentifyFocusPorts) -> None:
        """Initialize the controller."""
        self._ports = ports

    def focus_candidate(self, candidate_id: str) -> None:
        """Focus the spectrum view on a detected candidate row."""
        row = self._find_candidate_by_id(candidate_id)
        if row is None:
            return

        min_wave = min(row.lambda_start, row.lambda_end)
        max_wave = max(row.lambda_start, row.lambda_end)
        spectrum_view = self._ports.spectrum_view_provider()
        if spectrum_view is not None:
            new_min, new_max = self._calculate_candidate_focus_range(
                min_wave,
                max_wave,
                current_range=spectrum_view.get_wavelength_range(),
                data_bounds=self._ports.data_bounds_provider(),
            )

            spectrum_view.coordinator.coordinate_range_update(
                "identify-candidate-focus", new_min, new_max, record_history=False
            )
            spectrum_view.coordinator.handle_auto_flux_range_request()

        message = self._ports.messages_provider().candidate_template.format(
            start=min_wave, end=max_wave
        )
        self._ports.status_callback(message)

    def focus_group(self, min_wave: float, max_wave: float) -> None:
        """Focus the spectrum view on a confirmed or preview region range."""
        padded_min, padded_max = self._expand_range(
            min_wave,
            max_wave,
            fraction=self.GROUP_FOCUS_PADDING_FRACTION,
            minimum=self.GROUP_FOCUS_MIN_PADDING,
        )
        focused_range = self._focus_spectrum_range(padded_min, padded_max)
        if focused_range is None:
            return
        actual_min, actual_max = focused_range
        self._ports.status_callback(
            self._ports.messages_provider().group_template.format(start=actual_min, end=actual_max)
        )

    def focus_line(self, min_wave: float, max_wave: float) -> None:
        """Focus the spectrum view on a confirmed line range."""
        padded_min, padded_max = self._expand_range(
            min_wave,
            max_wave,
            fraction=self.LINE_FOCUS_PADDING_FRACTION,
            minimum=self.LINE_FOCUS_MIN_PADDING,
        )
        focused_range = self._focus_spectrum_range(padded_min, padded_max)
        if focused_range is None:
            return
        actual_min, actual_max = focused_range
        self._ports.status_callback(
            self._ports.messages_provider().line_template.format(start=actual_min, end=actual_max)
        )

    def _find_candidate_by_id(self, candidate_id: str) -> CandidateRow | None:
        """Return the matching candidate row when it is currently displayed."""
        for row in self._ports.candidate_rows_provider():
            if row.identifier == candidate_id:
                return row
        return None

    def _focus_spectrum_range(
        self, min_wave: float, max_wave: float
    ) -> tuple[float, float] | None:
        """Apply a focused spectrum range and return the enforced range."""
        spectrum_view = self._ports.spectrum_view_provider()
        if spectrum_view is None:
            return None

        enforced_min, enforced_max = enforce_min_wavelength_span(
            float(min_wave), float(max_wave), bounds=self._ports.data_bounds_provider()
        )

        spectrum_view.coordinator.coordinate_range_update(
            "identify-focus", enforced_min, enforced_max, record_history=False
        )
        spectrum_view.coordinator.handle_auto_flux_range_request()

        return enforced_min, enforced_max

    @staticmethod
    def _calculate_candidate_focus_range(
        lambda_start: float,
        lambda_end: float,
        *,
        current_range: tuple[float, float] | None,
        data_bounds: tuple[float, float] | None,
    ) -> tuple[float, float]:
        """Return wavelength limits with ±200% padding and minimum span."""
        candidate_min = min(lambda_start, lambda_end)
        candidate_max = max(lambda_start, lambda_end)
        span = candidate_max - candidate_min

        if span > 0:
            target_width = span * 5.0
            center = (candidate_min + candidate_max) / 2.0
        else:
            center = candidate_min
            target_width = 0.0
            if current_range and current_range[1] > current_range[0]:
                target_width = current_range[1] - current_range[0]
            if target_width <= 0 and data_bounds and data_bounds[1] > data_bounds[0]:
                target_width = data_bounds[1] - data_bounds[0]
            if target_width <= 0:
                target_width = MIN_WAVELENGTH_DISPLAY_SPAN

        target_width = max(target_width, MIN_WAVELENGTH_DISPLAY_SPAN)

        half_span = target_width / 2.0
        new_min = center - half_span
        new_max = center + half_span

        if data_bounds:
            data_min, data_max = data_bounds
            if data_max <= data_min:
                return float(data_min), float(data_max)

            total_span = data_max - data_min
            if target_width >= total_span:
                return float(data_min), float(data_max)

            if new_min < data_min:
                shift = data_min - new_min
                new_min = data_min
                new_max = min(data_max, new_max + shift)

            if new_max > data_max:
                shift = new_max - data_max
                new_max = data_max
                new_min = max(data_min, new_min - shift)

            new_min = max(new_min, data_min)
            new_max = min(new_max, data_max)

            if new_max <= new_min:
                return float(data_min), float(data_max)

        enforced_min, enforced_max = enforce_min_wavelength_span(
            float(new_min), float(new_max), bounds=data_bounds
        )

        return enforced_min, enforced_max

    @staticmethod
    def _expand_range(
        min_wave: float, max_wave: float, *, fraction: float, minimum: float
    ) -> tuple[float, float]:
        """Return a padded wavelength range."""
        if max_wave < min_wave:
            min_wave, max_wave = max_wave, min_wave

        span = max_wave - min_wave
        padding = max(span * fraction, minimum) if span > 0 else minimum

        return min_wave - padding, max_wave + padding
