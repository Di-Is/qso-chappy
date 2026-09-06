"""Typed models for spectrum range use cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chappy.application.analysis_artifacts import AnalysisMutationImpact


class SpectrumRangeSource(StrEnum):
    """Source category for spectrum range updates."""

    INTENT = "intent"
    RECT_ZOOM = "rect_zoom"
    AUTO_ADJUST = "auto_adjust"
    RESET = "reset"
    RANGE = "range"
    PLOT = "plot"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class PanNavigationIntent:
    """Application intent for horizontal panning."""

    fraction: float


@dataclass(frozen=True, slots=True)
class ZoomFactorNavigationIntent:
    """Application intent for factor-based zooming."""

    factor: float
    center_wavelength: float | None = None
    cursor_relative_position: float | None = None


@dataclass(frozen=True, slots=True)
class ZoomRectNavigationIntent:
    """Application intent for rectangle zooming."""

    min_wavelength: float
    max_wavelength: float
    min_flux: float | None = None
    max_flux: float | None = None


@dataclass(frozen=True, slots=True)
class SelectRangeNavigationIntent:
    """Application intent for selecting a specific wavelength range."""

    start_wavelength: float
    end_wavelength: float


@dataclass(frozen=True, slots=True)
class CenterOnWavelengthNavigationIntent:
    """Application intent for centering on a wavelength."""

    wavelength: float


type RangeNavigationIntent = (
    PanNavigationIntent
    | ZoomFactorNavigationIntent
    | ZoomRectNavigationIntent
    | SelectRangeNavigationIntent
    | CenterOnWavelengthNavigationIntent
)


@dataclass(frozen=True, slots=True)
class RangeNavigationRequest:
    """Request for calculating a validated navigation range."""

    current_range: tuple[float, float]
    intent: RangeNavigationIntent
    data_bounds: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class RangeNavigationResult:
    """Result of range navigation calculation."""

    wavelength_range: tuple[float, float]
    flux_range: tuple[float, float] | None
    source: SpectrumRangeSource


@dataclass(frozen=True, slots=True)
class ResolutionUpdateResult:
    """Result of applying a spectral resolution value."""

    value: float
    enabled: bool
    impact: AnalysisMutationImpact
