"""Matplotlib overlay helpers for spectrum plotting."""

from __future__ import annotations

from chappy.plotting.overlays.absorber_markers import (
    AbsorberMarkerOverlay,
    AbsorptionMarkerPayload,
)
from chappy.plotting.overlays.detection_regions import DetectionRegionOverlay
from chappy.plotting.overlays.identify_preview import (
    IdentifyPreviewEntry,
    IdentifyPreviewOverlay,
    IdentifyPreviewPayload,
)
from chappy.plotting.overlays.line_regions import AbsorptionLineRegion, LineRegionOverlay
from chappy.plotting.overlays.mask_regions import MaskRegionOverlay
from chappy.plotting.overlays.mask_selection import MaskSelectionOverlay

__all__ = [
    "AbsorberMarkerOverlay",
    "AbsorptionLineRegion",
    "AbsorptionMarkerPayload",
    "DetectionRegionOverlay",
    "IdentifyPreviewEntry",
    "IdentifyPreviewOverlay",
    "IdentifyPreviewPayload",
    "LineRegionOverlay",
    "MaskRegionOverlay",
    "MaskSelectionOverlay",
]
