"""Spectrum plotting using Matplotlib.

This is the Matplotlib-based spectrum plotting implementation that uses modular
components for maintainability and performance.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast, runtime_checkable

from matplotlib.backend_bases import NavigationToolbar2, cursors

from chappy.core.masking import DEFAULT_MASK_COLOR, MaskDefinition
from chappy.plotting.component_labels import DEFAULT_COMPONENT_LABEL_BAND_TOP
from chappy.plotting.components.continuum_display import ContinuumDisplayOwner
from chappy.plotting.components.continuum_editor import (
    ContinuumInteractionPort,
    MatplotlibContinuumEditor,
)
from chappy.plotting.components.selection_handler import MatplotlibSelectionHandler
from chappy.plotting.core.plot_config import PlotConfig
from chappy.plotting.core.spectrum_data_store import SpectrumPlotDataStore
from chappy.plotting.overlays import (
    AbsorberMarkerOverlay,
    AbsorptionLineRegion,
    AbsorptionMarkerPayload,
    DetectionRegionOverlay,
    IdentifyPreviewOverlay,
    IdentifyPreviewPayload,
    LineRegionOverlay,
    MaskRegionOverlay,
    MaskSelectionOverlay,
)
from chappy.plotting.overlays.payload_validation import (
    require_marker_float,
    validate_absorption_line_regions,
    validate_absorption_marker_input,
)
from chappy.plotting.renderers import (
    AxisConfig,
    CurveDisplayResolutionOwner,
    MatplotlibRenderer,
    ObservedRangePolicy,
    SpectrumCurveOwner,
    get_style_registry,
)
from chappy.plotting.utils.absorber_hit_testing import resolve_absorber_hit_tolerance
from chappy.plotting.utils.validators import validate_spectrum_data
from chappy.plotting.zoom_overlay_handle import ZoomOverlayHandle
from chappy.presentation.spectrum import (
    AbsorptionMarkerInput,
    SpectrumComponentCurve,
    SpectrumPlotDisplayCommand,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    import numpy as np
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.widgets import LockDraw
    from numpy.typing import NDArray

    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.plotting.components.continuum_display import ContinuumCurveRenderer
    from chappy.presentation.identify import DetectionOverlayPayload


@runtime_checkable
class CanvasWithWidgetLock(Protocol):
    """Protocol for matplotlib canvas with widget lock."""

    widgetlock: LockDraw


@runtime_checkable
class CanvasWithToolbar(Protocol):
    """Protocol for matplotlib canvas with toolbar."""

    toolbar: NavigationToolbar2 | None


@runtime_checkable
class ToolbarWithActive(Protocol):
    """Protocol for matplotlib toolbar with active tool."""

    _active: str | None


@runtime_checkable
class MatplotlibMouseEventBridge(Protocol):
    """Protocol for the event bridge used by this plot."""

    def connect(self) -> None:
        """Connect bridge callbacks."""

    def disconnect(self) -> None:
        """Disconnect bridge callbacks."""

    def handle_mouse_press(self, event: object) -> None:
        """Handle press events."""

    def handle_mouse_release(self, event: object) -> None:
        """Handle release events."""

    def handle_mouse_motion(self, event: object) -> None:
        """Handle move events."""

    def handle_axes_leave(self, event: object) -> None:
        """Handle axes-leave events."""

    def handle_double_click_centering(self, event: object) -> None:
        """Handle double-click centering."""

    def forward_mouse_event(
        self, event: object, event_type: Literal["press", "release", "move"]
    ) -> None:
        """Forward a mouse event."""


class MatplotlibMouseEventBridgeFactory(Protocol):
    """Factory for creating an injected mouse event bridge."""

    def __call__(
        self,
        *,
        figure: Figure,
        axes: Axes,
        canvas: object,
        get_interactor: Callable[[], SpectrumMouseInputPort],
        should_forward: Callable[[], bool],
    ) -> MatplotlibMouseEventBridge:
        """Create a mouse event bridge."""
        ...


class MatplotlibContinuumEditorFactory(Protocol):
    """Factory for creating an injected continuum editor with GUI behaviour."""

    def __call__(
        self, *, axes: Axes, figure: Figure, translate: Callable[[str], str]
    ) -> MatplotlibContinuumEditor:
        """Create a continuum editor."""
        ...


class MatplotlibRendererFactory(Protocol):
    """Factory for creating the injected Matplotlib renderer."""

    def __call__(self) -> MatplotlibRenderer:
        """Create a configured renderer."""
        ...


@dataclass(frozen=True, slots=True)
class MatplotlibSpectrumPlotCallbacks:
    """Concrete owner callbacks required by the shared plot core."""

    attach_canvas: Callable[[], None]
    translate_text: Callable[[str], str]
    notify_range_changed: Callable[[float, float, float, float], None]
    notify_selection_changed: Callable[[float, float], None]
    should_forward_mouse_events_to_interactor: Callable[[], bool]
    set_tooltip: Callable[[str], None] = lambda _text: None


@runtime_checkable
class SpectrumMouseInputPort(Protocol):
    """Mouse-input interface used by plot event forwarding."""

    def process_mouse_event(self, event: object) -> None:
        """Process mouse or wheel events forwarded from the plot."""

    def handle_mouse_leave(self) -> None:
        """Handle cursor-leave events."""

    def handle_double_click_center(self, wavelength: float) -> None:
        """Center the viewport on a wavelength."""

    def handle_mouse_press_event(self, event: object) -> bool:
        """Handle a converted Qt mouse press event."""

    def handle_mouse_release_event(self, event: object) -> bool:
        """Handle a converted Qt mouse release event."""

    def handle_mouse_move_event(self, event: object) -> bool:
        """Handle a converted Qt mouse move event."""


logger = logging.getLogger(__name__)

MIN_MASK_WIDTH = 0.01
MASK_REGION_COLOR = DEFAULT_MASK_COLOR
_COMPONENT_LABEL_BAND_MARGIN = 0.01
_MIN_COMPONENT_LABEL_BAND_TOP = 0.30


class MatplotlibSpectrumPlotFacade:
    """Matplotlib spectrum plot implementation without Qt widget ownership."""

    _updating_limits: bool = False  # Flag to prevent recursive limit updates

    def __init__(
        self,
        *,
        mouse_event_bridge_factory: MatplotlibMouseEventBridgeFactory | None = None,
        continuum_editor_factory: MatplotlibContinuumEditorFactory | None = None,
        renderer_factory: MatplotlibRendererFactory | None = None,
        callbacks: MatplotlibSpectrumPlotCallbacks | None = None,
        observed_data_validator: Callable[
            [NDArray[np.float64] | None, NDArray[np.float64] | None, NDArray[np.float64] | None],
            bool,
        ] = validate_spectrum_data,
        show_axis_labels: bool = True,
    ) -> None:
        """Initialize the matplotlib spectrum plot.

        Args:
            mouse_event_bridge_factory: Optional GUI-owned mouse event bridge factory.
            continuum_editor_factory: Optional GUI-owned continuum editor factory.
            renderer_factory: Optional GUI-owned renderer factory.
            callbacks: Concrete owner callbacks for attachment, translation, and notifications.
            observed_data_validator: Plot-owned validator for observed spectrum arrays.
            show_axis_labels: Whether the plot renders its own axis labels.
        """
        self._show_axis_labels = show_axis_labels
        self.config = PlotConfig()
        self.data_store = SpectrumPlotDataStore()
        self.renderer = (
            renderer_factory() if renderer_factory is not None else MatplotlibRenderer()
        )
        self.canvas = self.renderer.create_plot_widget()
        self._figure = self.renderer.require_figure()
        self._axes = self.renderer.require_axes()
        self._zoom_overlay_handle = ZoomOverlayHandle(axes=self._axes, canvas=self.canvas)

        # Style registry
        self.style_registry = get_style_registry()
        self._observed_range_policy = ObservedRangePolicy()
        self._display_resolution = CurveDisplayResolutionOwner(
            sink=self.renderer, target_bins_provider=self._display_target_bins
        )
        self._curve_owner = SpectrumCurveOwner(
            renderer=self.renderer,
            data_store=self.data_store,
            style_registry=self.style_registry,
            config=self.config,
            display_resolution=self._display_resolution,
        )

        self._observed_data_validator = observed_data_validator

        self._display_command = SpectrumPlotDisplayCommand(
            use_normalized_observed=False, render_absorption_line_labels=True
        )
        self._show_absorber_markers = True

        self._mouse_interactor: SpectrumMouseInputPort | None = None
        self._mouse_event_bridge_factory = mouse_event_bridge_factory
        self._mouse_event_bridge = self._create_mouse_event_bridge()
        self._continuum_editor_factory = continuum_editor_factory
        self._callbacks = callbacks or MatplotlibSpectrumPlotCallbacks(
            attach_canvas=lambda: None,
            translate_text=lambda text: text,
            notify_range_changed=lambda _x_min, _x_max, _y_min, _y_max: None,
            notify_selection_changed=lambda _x_min, _x_max: None,
            should_forward_mouse_events_to_interactor=lambda: True,
            set_tooltip=lambda _text: None,
        )
        self._mask_region_prefix = "mask_region_"
        self._mask_region_overlay = MaskRegionOverlay(
            renderer=self.renderer,
            canvas=self.canvas,
            prefix=self._mask_region_prefix,
            color=MASK_REGION_COLOR,
        )
        self._mask_selection_overlay = MaskSelectionOverlay(
            axes=self._axes, canvas=self.canvas, color=MASK_REGION_COLOR
        )
        self._identify_preview_overlay = IdentifyPreviewOverlay(
            axes=self._axes, canvas=self.canvas
        )
        self._detection_region_prefix = "detect_region_"
        self._detection_region_overlay = DetectionRegionOverlay(
            renderer=self.renderer, canvas=self.canvas, prefix=self._detection_region_prefix
        )
        self._callbacks.attach_canvas()
        self._init_components()
        self._setup_plot()
        self._connect_signals()
        self._line_region_prefix = "line_region_"
        self._line_region_overlay = LineRegionOverlay(
            renderer=self.renderer,
            axes=self._axes,
            canvas=self.canvas,
            prefix=self._line_region_prefix,
        )

    def set_input_ports(
        self, *, mouse: SpectrumMouseInputPort | None, continuum: ContinuumInteractionPort | None
    ) -> None:
        """Atomically set the independent mouse and continuum input ports.

        Args:
            mouse: Mouse input port used by the Matplotlib and Qt event bridges.
            continuum: Continuum interaction port used by the continuum editor.
        """
        if (mouse is None) is not (continuum is None):
            msg = "Mouse and continuum input ports must be attached or detached together."
            raise ValueError(msg)

        self.continuum_editor.set_interactor(continuum)
        self._mouse_interactor = mouse
        if mouse is None:
            self._mouse_event_bridge.disconnect()
        else:
            self._mouse_event_bridge.connect()

    def continuum_points(self) -> list[tuple[float, float]]:
        """Return current continuum control points."""
        return list(self.continuum_editor.points)

    @property
    def absorption_markers(self) -> dict[str, AbsorptionMarkerPayload]:
        """Expose absorber marker state for existing callers and tests."""
        return self._absorber_marker_overlay.markers

    def set_project(self, _project: SpectroscopyProject | None) -> None:
        """Set the current project for model curve generation.

        Args:
            _project: The SpectroscopyProject instance, accepted for plot facade API consistency.
        """
        if self.data_store.get_model_data() is not None:
            self._update_model_plot()

    def dispose(self) -> None:
        """Release Matplotlib callbacks and figure resources."""
        self.set_input_ports(mouse=None, continuum=None)
        self.continuum_editor.set_enabled(enabled=False)
        if isinstance(self.renderer, MatplotlibRenderer):
            self.renderer.dispose()

    def _init_components(self) -> None:
        """Initialize all components."""
        self._absorber_marker_overlay = AbsorberMarkerOverlay(
            renderer=self.renderer,
            canvas=self.canvas,
            axes=self._axes,
            band_top_provider=self._component_label_band_top,
        )
        self.continuum_editor = self._create_continuum_editor()
        self._continuum_display_owner = ContinuumDisplayOwner(
            renderer=cast("ContinuumCurveRenderer", self.renderer),
            canvas=self.canvas,
            continuum_editor=self.continuum_editor,
            style_registry=self.style_registry,
        )
        self.selection_handler = MatplotlibSelectionHandler(self._axes, self._figure)
        self._disable_matplotlib_interactions()

    def _setup_plot(self) -> None:
        """Setup the plot with initial configuration."""
        x_label, y_label = self._translated_axis_labels()
        self.renderer.set_axis_config(
            "x", AxisConfig(label=x_label, units="", grid=True, grid_alpha=0.3)
        )
        self.renderer.set_axis_config(
            "y", AxisConfig(label=y_label, units="", grid=True, grid_alpha=0.3)
        )

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._axes.callbacks.connect("xlim_changed", self._on_xlim_changed)
        self._axes.callbacks.connect("ylim_changed", self._on_ylim_changed)

    def _translated_axis_labels(self) -> tuple[str, str]:
        """Return translated axis labels, or empty labels when suppressed."""
        if not self._show_axis_labels:
            return "", ""
        return (
            self._callbacks.translate_text("Wavelength [Å]"),
            self._callbacks.translate_text("Flux"),
        )

    def refresh_translated_text(self) -> None:
        """Refresh translated plot-owned text through the concrete adapter."""
        x_label, y_label = self._translated_axis_labels()
        self._axes.set_xlabel(x_label)
        self._axes.set_ylabel(y_label)
        self._continuum_display_owner.refresh_reference_label(
            self._callbacks.translate_text("Continuum Reference")
        )
        self.canvas.draw_idle()

    def set_observed_spectrum(
        self,
        wavelength: NDArray[np.float64],
        flux: NDArray[np.float64],
        error: NDArray[np.float64] | None = None,
    ) -> None:
        """Set observed spectrum data.

        Args:
            wavelength: Wavelength array
            flux: Flux array
            error: Optional error array
        """
        if not self._observed_data_validator(wavelength, flux, error):
            msg = "Invalid spectrum data"
            raise ValueError(msg)

        self.data_store.set_observed_data(wavelength, flux, error)
        self._update_observed_plot()

    def set_model_spectrum(
        self, wavelength: NDArray[np.float64], flux: NDArray[np.float64]
    ) -> None:
        """Set model spectrum data.

        Args:
            wavelength: Wavelength array
            flux: Flux array
        """
        self.data_store.set_model_data(wavelength, flux)
        self._update_model_plot()

    def _update_observed_plot(self) -> None:
        """Update the observed spectrum plot."""
        self._updating_limits = True
        try:
            self._curve_owner.render_observed(
                display_command=self._display_command,
                show_error_bars=self._display_command.show_error_spectrum,
            )
        finally:
            self._updating_limits = False
        self._resync_display_resolution()

    def _update_model_plot(self) -> None:
        """Update the model spectrum plot."""
        self._updating_limits = True
        try:
            self._curve_owner.render_model()
        finally:
            self._updating_limits = False
        self._resync_display_resolution()

    def _resync_display_resolution(self) -> None:
        """Re-decimate registered curves for the current viewport after a render.

        Registration resets the cached view window, so without this step a
        render while zoomed would leave full-extent envelopes on screen until
        the next axis-limit change.
        """
        x_min, x_max = self._axes.get_xlim()
        if self._display_resolution.update_view(x_min, x_max):
            self.canvas.draw_idle()

    def add_absorption_marker(self, marker: AbsorptionMarkerInput) -> str:
        """Add an absorption line marker.

        Args:
            marker: Typed absorption marker payload.

        Returns:
            The component ID (either provided or generated)
        """
        validated = validate_absorption_marker_input(marker)
        component_id = validated.component_id
        if component_id is None:
            component_id = str(uuid.uuid4())

        self._absorber_marker_overlay.add_marker(
            AbsorptionMarkerInput(
                name=validated.name,
                rest_wavelength=validated.rest_wavelength,
                redshift=validated.redshift,
                column_density=validated.column_density,
                b_parameter=validated.b_parameter,
                oscillator_strength=validated.oscillator_strength,
                gamma=validated.gamma,
                component_id=component_id,
                tie_label=validated.tie_label,
                color=validated.color,
            ),
            component_id=component_id,
        )

        return component_id

    def update_absorption_marker_redshift(self, component_id: str, redshift: float) -> None:
        """Update an existing absorption marker after a model redshift edit.

        Args:
            component_id: Absorber component identifier.
            redshift: New absorber redshift.
        """
        redshift = require_marker_float(redshift, "redshift")
        self._absorber_marker_overlay.update_redshift(component_id, redshift)

    def set_detection_regions(self, regions: Sequence[DetectionOverlayPayload]) -> None:
        """Display detection regions as subtle overlays."""
        if not regions:
            self._detection_region_overlay.clear()
            return

        self._detection_region_overlay.set_regions(list(regions))

    def cancel_mask_selection(self) -> None:
        """Abort the active mask selection session and clear previews."""
        self.selection_handler.set_enabled(False)
        self.selection_handler.set_min_span(MIN_MASK_WIDTH)
        self.clear_mask_selection()
        self._clear_mask_selection_tooltip()

    def set_mask_regions(self, masks: Iterable[MaskDefinition]) -> None:
        """Display wavelength masks as shaded bands."""
        self._mask_region_overlay.set_regions(masks)

    def set_active_mask(self, mask_id: str | None) -> None:
        """Highlight the mask with identifier ``mask_id``."""
        self._mask_region_overlay.set_active(mask_id)

    def _apply_mask_selection_overlay(self, start: float, end: float) -> None:
        """Render mask overlay patch and preview for the provided bounds."""
        self._mask_selection_overlay.update(start, end)

    def _set_mask_selection_tooltip(self) -> None:
        """Show tooltip guidance for an armed mask-selection workflow."""
        hint = self._callbacks.translate_text("Drag to select a masked range")
        self._callbacks.set_tooltip(hint)

    def _clear_mask_selection_tooltip(self) -> None:
        """Clear mask-selection tooltip guidance."""
        self._callbacks.set_tooltip("")

    def set_absorption_line_regions(self, regions: Sequence[AbsorptionLineRegion]) -> None:
        """Display identified absorption lines as wavelength overlays."""
        render_labels = self._display_command.render_absorption_line_labels

        if not regions:
            self._line_region_overlay.clear()
            self._absorber_marker_overlay.refresh_component_labels()
            return

        validate_absorption_line_regions(regions)

        self._line_region_overlay.set_regions(regions, render_labels=render_labels)
        self._absorber_marker_overlay.refresh_component_labels()

    def _component_label_band_top(self) -> float:
        """Return the axes fraction component labels hang from, clear of the line labels."""
        band_bottom = self._line_region_overlay.label_band_bottom()
        if band_bottom is None:
            return DEFAULT_COMPONENT_LABEL_BAND_TOP
        return max(band_bottom - _COMPONENT_LABEL_BAND_MARGIN, _MIN_COMPONENT_LABEL_BAND_TOP)

    def _clear_line_region_labels(self) -> None:
        """Remove previously drawn absorption line text labels."""
        self._line_region_overlay.clear_labels()

    def set_identify_preview(self, preview: IdentifyPreviewPayload | None) -> None:
        """Render identify-mode ghost overlays driven by cursor position."""
        self._identify_preview_overlay.set_preview(preview)

    def _clear_identify_preview(self) -> None:
        """Remove previously rendered identify-mode overlays."""
        self._identify_preview_overlay.clear()

    def enable_continuum_editing(self, enabled: bool = True) -> None:
        """Enable/disable continuum editing mode.

        Args:
            enabled: Whether to enable continuum editing
        """
        self.continuum_editor.set_enabled(enabled=enabled)

    def apply_display_command(self, command: SpectrumPlotDisplayCommand) -> None:
        """Apply caller-owned display policy and refresh observed rendering.

        An unchanged command is a no-op: callers re-apply the current command
        after every data refresh, and re-rendering the observed curve twice per
        update is pure waste.
        """
        if command == self._display_command:
            return
        self._display_command = command
        self._update_observed_plot()

    def clear_plot(self) -> None:
        """Clear all plot elements."""
        self.renderer.clear()
        # Axes.clear() discards the callback registry, so the xlim/ylim
        # subscriptions must be re-established for re-decimation and range
        # notifications to survive a plot clear.
        self._connect_signals()
        self._display_resolution.clear()
        self.data_store.clear_all_data()
        self._continuum_display_owner.reset_after_renderer_clear()
        self._absorber_marker_overlay.clear()
        self._detection_region_overlay.clear()
        self._clear_line_region_labels()
        self._clear_identify_preview()

    def _on_xlim_changed(self, ax: Axes) -> None:
        """Handle x-axis limit change."""
        if self._updating_limits:
            return
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        if self._display_resolution.update_view(x_min, x_max):
            self.canvas.draw_idle()
        self._absorber_marker_overlay.refresh_component_labels()
        self._callbacks.notify_range_changed(x_min, x_max, y_min, y_max)

    def _display_target_bins(self) -> int:
        """Return the envelope bin count from the current canvas pixel width."""
        width, _height = self.canvas.get_width_height()
        return max(int(width), 256)

    def _on_ylim_changed(self, ax: Axes) -> None:
        """Handle y-axis limit change."""
        if self._updating_limits:
            return
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        self._callbacks.notify_range_changed(x_min, x_max, y_min, y_max)

    def _emit_range_changed(self) -> None:
        """Emit range changed signal."""
        x_min, x_max = self._axes.get_xlim()
        y_min, y_max = self._axes.get_ylim()
        self._callbacks.notify_range_changed(x_min, x_max, y_min, y_max)

    def get_absorber_at_position(
        self, wavelength: float, tolerance: float | None = None
    ) -> str | None:
        """Get absorber ID at given wavelength position.

        Args:
            wavelength: Wavelength to check
            tolerance: Detection tolerance in Angstroms. If None, calculated based on zoom level.

        Returns:
            Absorber component ID if found, None otherwise
        """
        x_min, x_max = self._axes.get_xlim()
        tolerance = resolve_absorber_hit_tolerance(x_min=x_min, x_max=x_max, tolerance=tolerance)
        return self._absorber_marker_overlay.absorber_at_position(wavelength, tolerance)

    def update_dragging_absorber_position(self, component_id: str, new_wavelength: float) -> None:
        """Update visual position of dragging absorber.

        Args:
            component_id: Absorber component ID
            new_wavelength: New wavelength position
        """
        self._absorber_marker_overlay.update_drag(component_id, new_wavelength)

    def finish_absorber_drag(self, component_id: str) -> None:
        """Clean up after absorber drag is complete.

        Args:
            component_id: Absorber component ID
        """
        self._absorber_marker_overlay.finish_drag(component_id)

    def update_rect_zoom(self, start: tuple[float, float], current: tuple[float, float]) -> None:
        """Update the rectangle zoom overlay.

        Args:
            start: Starting position in data coordinates (wavelength, flux).
            current: Current cursor position in data coordinates (wavelength, flux).
        """
        self._zoom_overlay_handle.update(start, current)

    def clear_rect_zoom(self) -> None:
        """Clear the rectangle zoom overlay and redraw the plot."""
        self._zoom_overlay_handle.clear()

    def begin_absorber_drag(self, absorber_id: str, initial_wavelength: float) -> None:
        """Begin an absorber drag interaction.

        Args:
            absorber_id: Unique identifier for the absorber being dragged.
            initial_wavelength: Initial wavelength position of the absorber.
        """
        self._absorber_marker_overlay.begin_drag(absorber_id, initial_wavelength)

    def begin_mask_selection(self, start: float) -> None:
        """Begin a mask selection overlay anchored at ``start``."""
        self.clear_mask_selection()
        self._set_mask_selection_tooltip()
        start_f = float(start)
        self._apply_mask_selection_overlay(start_f, start_f)

    def update_mask_selection(self, start: float, current: float) -> None:
        """Update the mask selection overlay bounds."""
        start_f = float(start)
        current_f = float(current)
        self._apply_mask_selection_overlay(start_f, current_f)

    def clear_mask_selection(self) -> None:
        """Clear the mask selection overlay and preview text."""
        self._mask_selection_overlay.clear()
        self._clear_mask_selection_tooltip()

    def set_wavelength_range(self, min_wave: float, max_wave: float) -> None:
        """Set the wavelength display range.

        Args:
            min_wave: Minimum wavelength
            max_wave: Maximum wavelength
        """
        # Set X-axis range
        self.renderer.set_range(x_min=min_wave, x_max=max_wave)
        self._emit_range_changed()

    def set_flux_range(self, min_flux: float, max_flux: float) -> None:
        """Set the flux display range.

        Args:
            min_flux: Minimum flux
            max_flux: Maximum flux
        """
        self.renderer.set_range(y_min=min_flux, y_max=max_flux)
        self._emit_range_changed()

    def set_plot_range(
        self, min_wave: float, max_wave: float, min_flux: float, max_flux: float
    ) -> None:
        """Set both wavelength and flux ranges simultaneously.

        Args:
            min_wave: Minimum wavelength
            max_wave: Maximum wavelength
            min_flux: Minimum flux
            max_flux: Maximum flux
        """
        # Set both ranges at once to avoid intermediate auto-scaling
        self.renderer.set_range(x_min=min_wave, x_max=max_wave, y_min=min_flux, y_max=max_flux)
        self._emit_range_changed()

    def set_residual_data(
        self, wavelength: NDArray[np.float64], residual: NDArray[np.float64]
    ) -> None:
        """Set residual data.

        Args:
            wavelength: Wavelength array
            residual: Residual array
        """
        self._curve_owner.set_residual_data(wavelength, residual)
        self._resync_display_resolution()

    def clear_residual(self) -> None:
        """Clear residual curve and data.

        Removes the residual curve from the renderer if present,
        and clears residual data from the data store.
        """
        self._curve_owner.clear_residual()

    def clear_model(self) -> None:
        """Clear model curve, component curves, and data."""
        self._curve_owner.clear_model()

    def set_component_profile_spectra(self, curves: tuple[SpectrumComponentCurve, ...]) -> None:
        """Render per-component profile curves alongside the composite model."""
        self._curve_owner.render_component_profiles(curves)
        self._resync_display_resolution()

    def clear_component_profiles(self) -> None:
        """Remove every per-component profile curve."""
        self._curve_owner.clear_component_profiles()

    def auto_range_all(self) -> None:
        """Auto-range both axes to fit all data."""
        self.renderer.auto_range()
        self.auto_range_y()

    def get_observed_y_range(self) -> tuple[float, float] | None:
        """Get Y range from observed data only.

        Returns:
            Tuple of (y_min, y_max) or None if no valid data.
        """
        observed = self._display_resolution.source("observed")
        if observed is None:
            return None
        return self._observed_range_policy.observed_y_range(observed[1])

    def auto_range_y(self) -> None:
        """Auto-range Y-axis to fit visible data in current X range."""
        if self.renderer is None:
            msg = "Renderer is required for Y-axis auto-range."
            raise RuntimeError(msg)
        x_min, x_max, _, _ = self.renderer.get_range()
        observed = self._display_resolution.source("observed")
        if observed is None:
            return
        bounds = self._observed_range_policy.auto_range_y_bounds(
            observed[0], observed[1], x_min=x_min, x_max=x_max
        )
        if bounds is None:
            return

        self.renderer.set_range(x_min, x_max, bounds.y_min, bounds.y_max)
        self._emit_range_changed()

    @property
    def show_absorber_markers(self) -> bool:
        """Whether to show absorber markers."""
        return self._show_absorber_markers

    @show_absorber_markers.setter
    def show_absorber_markers(self, value: bool) -> None:
        """Set whether to show absorber markers."""
        self._show_absorber_markers = value

    def toggle_absorption_line_markers(self, show: bool = True) -> None:
        """Toggle absorption line marker visibility.

        Args:
            show: Whether to show markers
        """
        self.show_absorber_markers = show
        self._absorber_marker_overlay.toggle(show)

    def clear_absorption_line_markers(self) -> None:
        """Clear all absorption line markers."""
        self._absorber_marker_overlay.clear()

    def refresh_absorption_marker_labels(self) -> None:
        """Re-place component name labels for the current absorption marker set."""
        self._absorber_marker_overlay.refresh_component_labels()

    def set_selected_component_id(self, component_id: str | None) -> None:
        """Emphasise one absorber component's marker label and model curve."""
        self._absorber_marker_overlay.set_selected_component_id(component_id)
        self._curve_owner.set_emphasized_component_id(component_id)

    def refresh(self) -> None:
        """Refresh the plot display."""
        self.canvas.draw_idle()

    def repaint(self, *_args: object) -> None:
        """Repaint the plot display.

        Args:
            *_args: Optional Qt repaint arguments (ignored)
        """
        self.canvas.draw()

    def set_continuum_data(
        self,
        wavelength: NDArray[np.float64],
        continuum_flux: NDArray[np.float64],
        anchor_points: list[tuple[float, float]],
    ) -> None:
        """Set continuum data and anchor points for display.

        Args:
            wavelength: Wavelength array for continuum curve
            continuum_flux: Flux array for continuum curve
            anchor_points: List of (wavelength, flux) tuples for anchor points
        """
        if len(wavelength) > 0 and len(continuum_flux) > 0:
            self.data_store.set_continuum_data(wavelength, continuum_flux)
        self._continuum_display_owner.set_data(
            wavelength=wavelength, continuum_flux=continuum_flux, anchor_points=anchor_points
        )

        if self._display_command.use_normalized_observed:
            self._update_observed_plot()

    def hide_continuum_display(self) -> None:
        """Remove continuum visuals while preserving stored data."""
        self._continuum_display_owner.hide_display()

        if self._display_command.use_normalized_observed:
            self._update_observed_plot()

    def update_continuum_preview(
        self, wavelength: NDArray[np.float64], preview_flux: NDArray[np.float64]
    ) -> None:
        """Update the visible continuum curve during an in-progress point drag."""
        self._continuum_display_owner.update_preview(wavelength, preview_flux)

    def clear_continuum_reference_line(self) -> None:
        """Remove the flux=1.0 continuum reference line if present."""
        self._continuum_display_owner.clear_reference_line()

    def ensure_continuum_reference_line(self) -> None:
        """Ensure the continuum reference line at flux=1.0 is displayed."""
        self._continuum_display_owner.ensure_reference_line(
            self._callbacks.translate_text("Continuum Reference")
        )

    def _create_mouse_event_bridge(self) -> MatplotlibMouseEventBridge:
        """Instantiate the injected mouse event bridge."""
        if self._mouse_event_bridge_factory is None:
            msg = "MatplotlibSpectrumPlotFacade requires a mouse event bridge factory."
            raise RuntimeError(msg)
        return self._mouse_event_bridge_factory(
            figure=self._figure,
            axes=self._axes,
            canvas=self.canvas,
            get_interactor=self._require_interactor,
            should_forward=self._should_forward_mouse_event_to_interactor,
        )

    def _create_continuum_editor(self) -> MatplotlibContinuumEditor:
        """Instantiate the injected continuum editor."""
        if self._continuum_editor_factory is None:
            return MatplotlibContinuumEditor(
                self._axes, self._figure, translate=self._callbacks.translate_text
            )
        return self._continuum_editor_factory(
            axes=self._axes, figure=self._figure, translate=self._callbacks.translate_text
        )

    def handle_mouse_press(self, event: object) -> None:
        """Forward a Matplotlib mouse-press event to the bridge."""
        self._mouse_event_bridge.handle_mouse_press(event)

    def handle_mouse_release(self, event: object) -> None:
        """Forward a Matplotlib mouse-release event to the bridge."""
        self._mouse_event_bridge.handle_mouse_release(event)

    def handle_mouse_motion(self, event: object) -> None:
        """Forward a Matplotlib mouse-motion event to the bridge."""
        self._mouse_event_bridge.handle_mouse_motion(event)

    def handle_axes_leave(self, event: object) -> None:
        """Notify interactor when cursor leaves the primary axes."""
        self._mouse_event_bridge.handle_axes_leave(event)

    def handle_double_click_centering(self, event: object) -> None:
        """Handle Matplotlib double-click centering through the bridge."""
        self._mouse_event_bridge.handle_double_click_centering(event)

    def forward_mouse_event(
        self, event: object, event_type: Literal["press", "release", "move"]
    ) -> None:
        """Forward mouse event to the event bridge for interactor processing.

        Args:
            event: Matplotlib mouse event
            event_type: "press", "release", or "move"
        """
        self._mouse_event_bridge.forward_mouse_event(event, event_type)

    def _should_forward_mouse_event_to_interactor(self) -> bool:
        """Return whether mouse events should be forwarded to the shared interactor."""
        return self._callbacks.should_forward_mouse_events_to_interactor()

    def _require_interactor(self) -> SpectrumMouseInputPort:
        """Return the configured spectrum interactor event sink."""
        if self._mouse_interactor is None:
            msg = "MatplotlibSpectrumPlot requires a mouse input port"
            raise RuntimeError(msg)
        return self._mouse_interactor

    def _disable_matplotlib_interactions(self) -> None:
        """Disable matplotlib's default interaction modes and cursor changes."""
        canvas = self.canvas
        canvas.set_cursor(cursors.POINTER)

        if isinstance(canvas, CanvasWithWidgetLock):
            canvas.widgetlock.release(canvas)
        if isinstance(canvas, CanvasWithToolbar) and canvas.toolbar:
            canvas.toolbar.pan()
            canvas.toolbar.zoom()
            if isinstance(canvas.toolbar, ToolbarWithActive):
                canvas.toolbar._active = None
