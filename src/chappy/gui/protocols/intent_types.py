"""Intent type definitions for Spectrum MVP-Lite architecture.

This module defines intent types that represent user actions
without coupling to Qt or UI implementation details.
All fields are typed for complete type safety.
"""

from __future__ import annotations

from dataclasses import dataclass


# Zoom Intents
@dataclass
class ZoomIntent:
    """Base intent for zoom operations."""


@dataclass
class ZoomFactorIntent(ZoomIntent):
    """Intent to zoom by a factor."""

    factor: float
    """Zoom factor (>1 to zoom in, <1 to zoom out)."""

    center_wavelength: float | None = None
    """Optional center point for zoom."""

    cursor_relative_position: float | None = None
    """Cursor's relative position in current range (0.0-1.0) for fixed-point zoom.

    When set, the cursor position remains at the same relative position in the view
    after zooming, preventing drift. This is the standard behavior for most plotting
    tools (Matplotlib, Plotly, etc.).

    Example: If cursor is at 95% from left edge (near right edge), it stays at 95%
    after zoom, keeping the cursor over the same wavelength feature.
    """


@dataclass
class ZoomRectIntent(ZoomIntent):
    """Intent to zoom to a rectangular region."""

    min_wavelength: float
    """Minimum wavelength of zoom region."""

    max_wavelength: float
    """Maximum wavelength of zoom region."""

    min_flux: float | None = None
    """Optional minimum flux of zoom region."""

    max_flux: float | None = None
    """Optional maximum flux of zoom region."""


# Navigation Intents
@dataclass
class NavigationIntent:
    """Base intent for navigation operations."""


@dataclass
class PanIntent(NavigationIntent):
    """Intent to pan the spectrum view.

    The pan amount is specified as a fraction of the current visible range.
    This allows automatic adaptation to the current zoom level.
    """

    fraction: float
    """Fraction of visible range to pan (negative = left, positive = right).

    Example: -0.1 means pan left by 10% of visible range.
    """


@dataclass
class SelectRangeIntent(NavigationIntent):
    """Intent to select a wavelength range."""

    start_wavelength: float
    """Start wavelength of selection."""

    end_wavelength: float
    """End wavelength of selection."""


@dataclass
class CenterOnWavelengthIntent(NavigationIntent):
    """Intent to center spectrum view on a specific wavelength.

    Triggered by double-clicking on spectrum. Maintains current zoom level.
    """

    wavelength: float
    """Wavelength to center on."""


# Absorber Intents
@dataclass
class AbsorberIntent:
    """Base intent for absorber operations."""


@dataclass
class SelectAbsorberIntent(AbsorberIntent):
    """Intent to select an absorber."""

    absorber_id: str | None = None
    """Absorber ID to select."""

    direction: str | None = None
    """Direction for relative selection ('next' or 'previous')."""


@dataclass
class ModifyAbsorberIntent(AbsorberIntent):
    """Intent to modify an absorber parameter."""

    absorber_id: str
    """Absorber ID to modify."""

    parameter: str
    """Parameter name to modify."""

    value: float
    """New parameter value."""


# Continuum Intents
@dataclass
class ContinuumIntent:
    """Base intent for continuum operations."""


@dataclass
class AddContinuumPointIntent(ContinuumIntent):
    """Intent to add a continuum point."""

    wavelength: float
    """Wavelength position for continuum point."""

    flux: float
    """Flux value for continuum point."""


@dataclass
class DeleteContinuumPointIntent(ContinuumIntent):
    """Intent to delete a continuum point."""

    index: int
    """Index of the continuum point to delete."""


@dataclass
class OptimizeIntent:
    """Base intent for optimize-mode operations."""


@dataclass
class AddOptimizeComponentIntent(OptimizeIntent):
    """Intent to add an optimize component at a wavelength."""

    wavelength: float
    """Wavelength position for the new component."""


@dataclass
class ToggleOptimizeVelocityPlotIntent(OptimizeIntent):
    """Intent to toggle optimize velocity plot display."""


# Mode Intents
@dataclass
class IdentifyIntent:
    """Base intent for identify-mode operations."""


@dataclass
class ToggleVelocityPlotIntent(IdentifyIntent):
    """Intent to toggle velocity plot display in identify mode."""

    wavelength: float | None = None
    """Optional wavelength to center the velocity plot on."""


@dataclass
class ToggleIdentifyPreviewLockIntent(IdentifyIntent):
    """Intent to toggle identify cursor preview lock."""

    enabled: bool
    """Whether identify preview overlay should remain visible."""


@dataclass
class AddIdentifyTemporaryLineIntent(IdentifyIntent):
    """Intent to place identify-mode temporary lines at a wavelength."""

    wavelength: float
    """Observed wavelength where the temporary line should be placed."""

    flux: float | None = None
    """Observed flux at the placement point (optional)."""

    modifiers: int = 0
    """Keyboard modifier state recorded during the action."""

    source: str = "click"
    """Origin of the request (e.g., 'click', 'context_menu')."""


# Context Menu Intent
@dataclass
class ShowContextMenuIntent(ContinuumIntent, IdentifyIntent, OptimizeIntent):
    """Intent to show context menu at a specific position."""

    wavelength: float
    """Wavelength at menu position."""

    flux: float
    """Flux at menu position."""

    global_x: int
    """Global screen X coordinate for menu position."""

    global_y: int
    """Global screen Y coordinate for menu position."""


# Absorber Drag Intents
@dataclass
class StartAbsorberDragIntent(AbsorberIntent):
    """Intent to start dragging an absorber marker."""

    absorber_id: str
    """ID of the absorber being dragged."""

    initial_wavelength: float
    """Initial wavelength at drag start."""

    initial_position: tuple[float, float]
    """Initial position (wavelength, flux) at drag start."""

    wavelength_already_converted: bool = False
    """True if initial_wavelength is already in wavelength coordinates.

    When drag starts from VelocityView, the velocity-to-wavelength conversion
    is done by the velocity drag input adapter. This flag prevents double conversion
    in the absorber drag handler.
    """


@dataclass
class UpdateAbsorberDragIntent(AbsorberIntent):
    """Intent to update position during absorber drag."""

    absorber_id: str
    """ID of the absorber being dragged."""

    current_wavelength: float
    """Current wavelength during drag."""


@dataclass
class EndAbsorberDragIntent(AbsorberIntent):
    """Intent to finalize absorber drag."""

    absorber_id: str
    """ID of the absorber being dragged."""

    final_wavelength: float
    """Final wavelength at drag end."""

    calculate_redshift: bool = True
    """Whether to recalculate redshift from wavelength."""


type AbsorberActionIntent = (
    SelectAbsorberIntent
    | ModifyAbsorberIntent
    | StartAbsorberDragIntent
    | UpdateAbsorberDragIntent
    | EndAbsorberDragIntent
)

type SpectrumInteractionIntent = (
    ZoomRectIntent
    | ZoomFactorIntent
    | PanIntent
    | SelectRangeIntent
    | AbsorberActionIntent
    | ShowContextMenuIntent
    | ToggleVelocityPlotIntent
    | AddIdentifyTemporaryLineIntent
    | CenterOnWavelengthIntent
)
