"""Helper functions to construct absorption line overlay payloads."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypedDict

from chappy.core.constants import LIGHT_SPEED_KMS

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.identify_state import TemporaryLine
    from chappy.core.spectroscopy_project import SpectroscopyProject


class RegionPayload(TypedDict, total=False):
    """Overlay payload describing a shaded wavelength region."""

    id: str
    lambda_start: float
    lambda_end: float
    color: str
    alpha: float
    category: str
    label: str
    zorder: int
    line_style: str
    edge_alpha: float
    lambda_center: float
    label_weight: str
    label_y: float
    label_visible: bool


DEFAULT_CONFIRMED_COLOR = "#2ecc71"
DEFAULT_TEMP_COLORS: Mapping[str, str] = {
    "pending": "#f1c40f",
    "preview": "#9b59b6",
    "confirmed": "#3498db",
}


def _format_redshift(value: float | None) -> str:
    """Format a redshift value for overlay labels."""
    if value is None or not math.isfinite(value):
        return "z=?"
    return f"z={value:.3f}"


def _resolve_transition_name(
    transition_name: str | None,
    species: str,
    *,
    rest_wavelength: float | None = None,
    fallback: str = "Temporary Line",
) -> str:
    """Choose the most descriptive transition label available."""
    name = (transition_name or "").strip()
    species_label = (species or "").strip()

    if name and species_label and name.lower() == species_label.lower():
        name = ""

    if not name:
        if species_label and _is_finite_float(rest_wavelength):
            return f"{species_label} {_format_wavelength(rest_wavelength)}"
        if species_label:
            return species_label
        if _is_finite_float(rest_wavelength):
            return _format_wavelength(rest_wavelength)
        return fallback

    return name


def _format_wavelength(value: float | None) -> str:
    """Format wavelengths with a trailing Å unit."""
    if value is None or not math.isfinite(value):
        return "? Å"
    return f"{value:.1f} Å"


def compute_confirmed_line_regions(
    project: SpectroscopyProject | None,
    *,
    region_id: str | None = None,
    alpha: float = 0.18,
    fallback_color: str = DEFAULT_CONFIRMED_COLOR,
    zorder: int = -6,
) -> list[RegionPayload]:
    """Build overlay payloads for confirmed absorption lines."""
    if project is None:
        return []

    overlays: list[RegionPayload] = []
    region_map = project.absorption_regions

    for line in project.list_absorption_lines():
        if region_id is not None and line.region_id != region_id:
            continue
        bounds = _line_bounds(line)
        if bounds is None:
            continue

        color = _resolve_region_color(region_map, line.region_id, fallback_color)
        label = _format_confirmed_label(line)
        center = line.observed_wavelength()
        if not math.isfinite(center) or center <= 0.0:
            center = (bounds[0] + bounds[1]) / 2.0

        overlays.append(
            {
                "id": line.line_id,
                "lambda_start": bounds[0],
                "lambda_end": bounds[1],
                "color": color,
                "alpha": alpha,
                "category": "confirmed",
                "label": label,
                "zorder": zorder,
                "line_style": "-",
                "edge_alpha": 0.0,
                "lambda_center": center,
                "label_weight": "normal",
                "label_y": 0.92,
                "label_visible": True,
            }
        )

    return _sorted_overlays(overlays)


def compute_temporary_line_regions(
    lines: Sequence[TemporaryLine] | Iterable[TemporaryLine],
    *,
    alpha: float = 0.12,
    status_colors: Mapping[str, str] | None = None,
    zorder: int = -7,
) -> list[RegionPayload]:
    """Build overlay payloads for identify-mode temporary lines."""
    palette = status_colors or DEFAULT_TEMP_COLORS

    overlays: list[RegionPayload] = []
    for line in lines:
        bounds = _temporary_bounds(line)
        if bounds is None:
            continue

        color = palette.get(line.status, DEFAULT_TEMP_COLORS["pending"])
        label = _format_temporary_label(line)
        center = line.center_wavelength
        if center is None or not math.isfinite(center):
            center = (bounds[0] + bounds[1]) / 2.0

        overlays.append(
            {
                "id": line.temporary_line_id,
                "lambda_start": bounds[0],
                "lambda_end": bounds[1],
                "color": color,
                "alpha": alpha,
                "category": "temporary",
                "label": label,
                "zorder": zorder,
                "line_style": "-",
                "edge_alpha": 0.0,
                "lambda_center": center,
                "label_weight": "normal",
                "label_y": 0.955,
                "label_visible": True,
            }
        )

    return _sorted_overlays(overlays)


def merge_region_payloads(*payload_groups: Iterable[RegionPayload]) -> list[RegionPayload]:
    """Merge multiple overlay payload iterables into a sorted list."""
    merged: list[RegionPayload] = []
    for payload in payload_groups:
        merged.extend(payload)
    return _sorted_overlays(merged)


def _line_bounds(line: AbsorptionLine) -> tuple[float, float] | None:
    if line.lambda_range:
        start, end = line.lambda_range
    else:
        observed = line.observed_wavelength()
        window = abs(line.window_kms)
        if observed <= 0.0 or window <= 0.0:
            return None
        delta = observed * (window / LIGHT_SPEED_KMS)
        start, end = observed - delta, observed + delta

    return _normalize_bounds(start, end)


def _temporary_bounds(line: TemporaryLine) -> tuple[float, float] | None:
    return _normalize_bounds(line.lambda_min, line.lambda_max)


def _normalize_bounds(low: float, high: float) -> tuple[float, float] | None:
    if not (math.isfinite(low) and math.isfinite(high)):
        return None
    if low == high:
        return None
    start, end = (low, high) if low < high else (high, low)
    return start, end


def _resolve_region_color(
    region_map: Mapping[str, AbsorptionRegion], region_id: str | None, fallback: str
) -> str:
    if not region_id:
        return fallback

    region = region_map.get(region_id)
    if region is None:
        return fallback

    color = region.display_color
    if color:
        return color

    return fallback


def _format_confirmed_label(line: AbsorptionLine) -> str:
    name = _resolve_transition_name(
        line.transition_name, line.species, rest_wavelength=line.rest_wavelength
    )
    return f"{name} {_format_redshift(line.center_z)}"


def _temporary_center_redshift(line: TemporaryLine) -> float | None:
    center_z = line.center_z
    if _is_finite_float(center_z):
        return center_z

    rest = line.rest_wavelength
    center = line.center_wavelength
    if not _is_finite_float(rest) or rest <= 0.0 or not _is_finite_float(center):
        return None

    return (center / rest) - 1.0


def _format_temporary_label(line: TemporaryLine) -> str:
    name = _resolve_transition_name(
        line.transition_name,
        line.species,
        rest_wavelength=line.rest_wavelength,
        fallback="Temporary",
    )
    return f"{name} {_format_redshift(_temporary_center_redshift(line))}"


def _sorted_overlays(overlays: list[RegionPayload]) -> list[RegionPayload]:
    def _sort_key(item: RegionPayload) -> tuple[float, float]:
        start = item.get("lambda_start")
        end = item.get("lambda_end")
        start_value = start if start is not None else math.inf
        end_value = end if end is not None else math.inf
        return (start_value, end_value)

    overlays.sort(key=_sort_key)
    return overlays


def _is_finite_float(value: float | None) -> bool:
    """Return whether value is a finite float."""
    return value is not None and math.isfinite(value)
