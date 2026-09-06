"""Spectrum interactor using Intent pattern (MVP-Lite).

This module provides a simplified spectrum interaction adapter
that uses Intent types to decouple event handling from action execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal

# Use protocol's intent types for consistency
from chappy.gui.protocols.intent_types import (
    AbsorberIntent,
    CenterOnWavelengthIntent,
    IdentifyIntent,
    PanIntent,
    SelectRangeIntent,
    ShowContextMenuIntent,
    SpectrumInteractionIntent,
    ZoomIntent,
)
from chappy.gui.spectrum.interaction.channels.factory import InteractionControllerFactoryPorts
from chappy.gui.spectrum.interaction.input.intent_emitter import SpectrumIntentEmitter
from chappy.gui.spectrum.interaction.input.routing.click_router import ClickRouteState
from chappy.gui.spectrum.interaction.input.routing.shortcut_router import KeyRouteState
from chappy.gui.spectrum.interaction.input.spectrum_input_channel_session import (
    SpectrumInputChannelSession,
)
from chappy.gui.spectrum.interaction.input.spectrum_input_composition import (
    SpectrumInputCompositionCallbacks,
    build_spectrum_input_composition,
)
from chappy.gui.spectrum.interaction.input.spectrum_input_context import SpectrumInputContext
from chappy.gui.spectrum.interaction.input.spectrum_input_mode_session import (
    SpectrumInputModeSession,
)
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumContext,
    InteractionChannel,
    InteractionEvent,
    InteractionStateSnapshot,
    MaskSelectionContext,
    MaskSelectionRequest,
    RectZoomContext,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
    from PySide6.QtWidgets import QWidget

    from chappy.gui.protocols.interaction_overlay import InteractionOverlayProtocol
    from chappy.gui.spectrum.interaction.channels.ports import (
        ContinuumChannelControllerPort,
        InteractionChannelControllerPort,
    )
    from chappy.gui.spectrum.interaction.input.ports import (
        SpectrumInputAdapterViewPort,
        SpectrumPlotWidgetPort,
        VelocityDragSignalPort,
    )
    from chappy.gui.spectrum.policy import SpectrumInputCapabilities
    from chappy.gui.utils.plot_coordinate_transform import PlotCoordinateTransform

logger = logging.getLogger(__name__)


class SpectrumInputAdapter(QObject):
    """Simplified spectrum interaction adapter using Intent pattern.

    This class generates Intents from user events and coordinates
    with execution ports. Follows MVP-Lite + Interactor pattern.
    """

    sig_zoom_requested = Signal(ZoomIntent)
    sig_pan_requested = Signal(PanIntent)
    sig_range_selected = Signal(SelectRangeIntent)
    sig_absorber_action = Signal(AbsorberIntent)
    sig_context_menu_requested = Signal(ShowContextMenuIntent)
    sig_identify_action = Signal(IdentifyIntent)
    sig_cursor_position_changed = Signal(float, float, int)  # wavelength, flux, modifiers
    sig_mode_click_requested = Signal(float, float, int)  # wavelength, flux, modifiers
    sig_cursor_left = Signal()
    sig_identify_preview_shift_released = Signal()
    sig_interaction_snapshot = Signal(InteractionStateSnapshot)
    sig_mode_velocity_shortcut_requested = Signal()
    sig_center_requested = Signal(CenterOnWavelengthIntent)

    def __init__(
        self, view: SpectrumInputAdapterViewPort, parent_view: QWidget | None = None
    ) -> None:
        """Initialize the interactor.

        Args:
            view: The spectrum view (forward reference to avoid circular import)
            parent_view: Optional parent widget for hierarchy
        """
        super().__init__()

        self._intent_emitter = SpectrumIntentEmitter(
            zoom_requested=self.sig_zoom_requested,
            pan_requested=self.sig_pan_requested,
            range_selected=self.sig_range_selected,
            absorber_action=self.sig_absorber_action,
            context_menu_requested=self.sig_context_menu_requested,
            identify_action=self.sig_identify_action,
            center_requested=self.sig_center_requested,
        )
        self.view = view  # Will be type: SpectrumView
        self.parent_view = parent_view

        self._input_context = SpectrumInputContext()
        self._mode_session = SpectrumInputModeSession()

        composition = build_spectrum_input_composition(
            owner=self,
            callbacks=SpectrumInputCompositionCallbacks(
                controller_ports=InteractionControllerFactoryPorts(
                    snapshot_consumer=self._emit_interaction_snapshot,
                    overlay_provider=self._resolve_rect_zoom_overlay,
                    zoom_intent_emitter=self.sig_zoom_requested.emit,
                    absorber_drag_intent_emitter=self.sig_absorber_action.emit,
                    absorber_drag_state_tracker=self._sync_absorber_drag_state,
                ),
                transform_provider=self._current_coordinate_transform,
                plot_widget_provider=self._current_plot_widget,
                intent_emitter=self._emit_intent,
                mode_velocity_shortcut_emitter=self.sig_mode_velocity_shortcut_requested.emit,
                mode_click_emitter=self._emit_mode_click_signal,
                cursor_position_emitter=self.sig_cursor_position_changed.emit,
                cursor_left_emitter=self.sig_cursor_left.emit,
                center_requested_emitter=self.sig_center_requested.emit,
                velocity_shortcut_mode_capabilities=self._mode_session,
            ),
            logger=logger,
        )
        self._plot_input_binding = composition.plot_input_binding
        self._event_mapper = composition.event_mapper
        self._coordinate_mapper = composition.coordinate_mapper
        self._shortcut_router = composition.shortcut_router
        self._click_router = composition.click_router
        self._wheel_router = composition.wheel_router
        self._rect_zoom_input_controller = composition.rect_zoom_input_controller
        self._absorber_drag_input_controller = composition.absorber_drag_input_controller
        self._interaction_controller: InteractionChannelControllerPort = (
            composition.rect_zoom_state_controller
        )
        self._absorber_state_controller: InteractionChannelControllerPort = (
            composition.absorber_state_controller
        )
        self._velocity_drag_adapter = composition.velocity_drag_adapter
        self._velocity_shortcut_input_controller = composition.velocity_shortcut_input_controller
        self._cursor_wavelength_input_controller = composition.cursor_wavelength_input_controller
        self._mask_state_controller: InteractionChannelControllerPort | None = (
            composition.mask_state_controller
        )
        self._mask_selection_input_controller = composition.mask_selection_input_controller
        self._pointer_input_controller = composition.pointer_input_controller
        self._interaction_runtime = composition.interaction_runtime
        self._command_executor = composition.command_executor
        self._continuum_state_controller: ContinuumChannelControllerPort | None = None
        self._channel_session = SpectrumInputChannelSession(
            coordinator=composition.channel_coordinator, context=self._input_context
        )

        logger.debug("SpectrumInputAdapter initialized with type-safe signals")

    def active_interaction_channel(self) -> InteractionChannel | None:
        """Return the channel currently owning pointer interaction state."""
        return self._channel_session.active_channel()

    def dragging_absorber_id(self) -> str | None:
        """Return the absorber currently being dragged, if any."""
        return self._input_context.dragging_absorber_id

    def absorber_drag_enabled(self) -> bool:
        """Return whether absorber drag is enabled in the current mode."""
        return self._mode_session.absorber_drag_enabled()

    def set_absorber_drag_state_controller(
        self, controller: InteractionChannelControllerPort
    ) -> None:
        """Replace the absorber drag state controller dependency."""
        self._absorber_state_controller = controller
        self._sync_velocity_drag_adapter_controller()

    def set_continuum_interaction_controller(
        self, controller: ContinuumChannelControllerPort
    ) -> None:
        """Inject the continuum-mode owned interaction controller."""
        self._continuum_state_controller = controller

    @property
    def coord_transform(self) -> PlotCoordinateTransform | None:
        """Return the current plot coordinate transform."""
        return self._plot_input_binding.coord_transform

    @coord_transform.setter
    def coord_transform(self, transform: PlotCoordinateTransform | None) -> None:
        """Replace the current plot coordinate transform."""
        self._plot_input_binding.coord_transform = transform

    def _require_absorber_state_controller(self) -> InteractionChannelControllerPort:
        """Return the absorber drag controller or fail on broken wiring."""
        controller = self._absorber_state_controller
        if controller is None:
            msg = "Absorber drag state controller is required for absorber interactions."
            raise RuntimeError(msg)
        return controller

    def require_absorber_drag_controller(self) -> InteractionChannelControllerPort:
        """Return the absorber drag controller for input-side collaborators."""
        return self._require_absorber_state_controller()

    def _sync_velocity_drag_adapter_controller(self) -> None:
        """Synchronize velocity drag adapter with the current absorber controller."""
        self._velocity_drag_adapter.set_absorber_drag_controller(
            self._require_absorber_state_controller()
        )

    def _require_mask_state_controller(self) -> InteractionChannelControllerPort:
        """Return the mask selection controller or fail on broken wiring."""
        controller = self._mask_state_controller
        if controller is None:
            msg = "Mask selection state controller is required for mask selection interactions."
            raise RuntimeError(msg)
        return controller

    def require_mask_selection_controller(self) -> InteractionChannelControllerPort:
        """Return the mask selection controller for input-side collaborators."""
        return self._require_mask_state_controller()

    def require_rect_zoom_controller(self) -> InteractionChannelControllerPort:
        """Return the rectangle zoom controller for input-side collaborators."""
        return self._interaction_controller

    def _current_coordinate_transform(self) -> PlotCoordinateTransform | None:
        """Return the current plot coordinate transform."""
        return self.coord_transform

    def _current_plot_widget(self) -> SpectrumPlotWidgetPort | None:
        """Return the current plot widget."""
        return self._plot_input_binding.plot_widget

    def _resolve_rect_zoom_overlay(self) -> InteractionOverlayProtocol | None:
        """Return the plot overlay implementation if available."""
        return self._plot_input_binding.interaction_overlay()

    def interaction_overlay(self) -> InteractionOverlayProtocol | None:
        """Return the plot overlay implementation for external channel owners."""
        return self._resolve_rect_zoom_overlay()

    def consume_interaction_snapshot(
        self,
        snapshot: InteractionStateSnapshot[
            RectZoomContext | AbsorberDragContext | MaskSelectionContext | ContinuumContext
        ],
    ) -> None:
        """Consume an externally owned interaction snapshot."""
        self._emit_interaction_snapshot(snapshot)

    def current_continuum_points(self) -> list[tuple[float, float]]:
        """Return the current list of continuum points from the attached plot."""
        return self._plot_input_binding.continuum_points()

    def _emit_interaction_snapshot(
        self,
        snapshot: InteractionStateSnapshot[
            RectZoomContext | AbsorberDragContext | MaskSelectionContext | ContinuumContext
        ],
    ) -> None:
        """Emit interaction state snapshots through the dedicated Qt signal."""
        self._channel_session.apply_snapshot(snapshot)

        self.sig_interaction_snapshot.emit(snapshot)

    def _sync_absorber_drag_state(self, absorber_id: str | None) -> None:
        """Synchronise legacy absorber drag fields with the state controller.

        Args:
            absorber_id: Identifier of the absorber currently being dragged, or None.
        """
        self._channel_session.sync_absorber_drag_state(absorber_id)

    def can_start_absorber_drag(self) -> bool:
        """Return whether an absorber drag interaction can start."""
        return self._channel_session.can_start(InteractionChannel.ABSORBER_DRAG)

    def active_absorber_drag_id(self) -> str | None:
        """Return the active absorber drag id, if any."""
        return self._channel_session.active_absorber_drag_id()

    def acquire_absorber_drag(self, absorber_id: str) -> None:
        """Acquire absorber drag channel ownership for an absorber."""
        self._channel_session.acquire_absorber_drag(absorber_id)

    def clear_absorber_drag(self) -> None:
        """Clear absorber drag channel ownership."""
        self._channel_session.clear_absorber_drag()

    def can_start_mask_selection(self) -> bool:
        """Return whether mask selection can start."""
        return self._channel_session.can_start(InteractionChannel.MASK_SELECTION)

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the current active input channel."""
        return self._channel_session.active_channel()

    def acquire_rect_zoom(self) -> None:
        """Acquire rectangle zoom channel ownership."""
        self._channel_session.acquire_rect_zoom()

    def clear_rect_zoom(self) -> None:
        """Clear rectangle zoom channel ownership."""
        self._channel_session.clear_rect_zoom()

    def set_rect_zoom_cursor(self, active: bool) -> None:
        """Apply cursor feedback while rectangle zoom mode is active."""
        self._plot_input_binding.set_cursor(active)

    def acquire_mask_selection(self) -> None:
        """Acquire mask selection channel ownership."""
        self._channel_session.acquire_mask_selection()

    def clear_mask_selection(self) -> None:
        """Clear mask selection channel ownership."""
        self._channel_session.clear_mask_selection()

    def set_mask_selection_cursor(self, active: bool) -> None:
        """Apply cursor feedback while mask selection mode is active."""
        self._plot_input_binding.set_cursor(active)

    def _cancel_rect_zoom_interaction(self, *, reason: str) -> bool:
        """Cancel active rectangle zoom interaction.

        Args:
            reason: Cancellation reason propagated to the interaction controller.

        Returns:
            True when rectangle zoom was active and cancellation occurred.
        """
        return self._rect_zoom_input_controller.cancel_interaction(reason=reason)

    def cancel_active_absorber_drag(self, *, reason: str | None = None) -> bool:
        """Cancel the active absorber drag interaction, if any.

        Args:
            reason: Optional cancellation reason recorded on the interaction snapshot.

        Returns:
            True when an active absorber drag was cancelled.
        """
        return self._absorber_drag_input_controller.cancel_active_drag(reason=reason)

    def handle_key_event(self, event: QKeyEvent) -> bool:
        """Convert key event to intent.

        Args:
            event: Key event

        Returns:
            True if handled
        """
        if (
            event.key() == Qt.Key.Key_Escape
            and self.active_input_channel() is InteractionChannel.MASK_SELECTION
        ):
            self.cancel_mask_selection_interaction(reason="escape-key")
            return True

        result = self._shortcut_router.route_key(
            key=self._event_mapper.key_code(event),
            modifiers=event.modifiers(),
            state=KeyRouteState(
                identify_velocity_shortcut_enabled=(
                    self._mode_session.identify_velocity_shortcut_enabled()
                ),
                mode_velocity_shortcut_enabled=(
                    self._mode_session.detail_velocity_shortcut_enabled()
                ),
                active_channel=self.active_input_channel(),
            ),
        )
        self._command_executor.execute_shortcut_commands(result.commands)
        return result.handled

    def handle_key_release_event(self, event: QKeyEvent) -> bool:
        """Notify Identify when Shift preview input is released."""
        if event.key() != Qt.Key.Key_Shift or not self._mode_session.identify_click_enabled():
            return False
        self.sig_identify_preview_shift_released.emit()
        return True

    def trigger_velocity_shortcut(self) -> bool:
        """Route a global velocity shortcut through the active mode.

        Returns:
            True when the request was handled.
        """
        return self._velocity_shortcut_input_controller.trigger_velocity_shortcut()

    def wavelength_under_cursor(self) -> float | None:
        """Return the spectrum wavelength under the pointer."""
        return self._cursor_wavelength_input_controller.wavelength_under_cursor()

    def handle_mouse_click(
        self, pos: tuple[float, float], button: str, modifiers: int = 0
    ) -> bool:
        """Convert mouse click to intent.

        Args:
            pos: Click position (wavelength, flux)
            button: Mouse button ('left', 'right', 'middle')
            modifiers: Keyboard modifiers active during click

        Returns:
            True if handled
        """
        result = self._click_router.route_click(
            position=pos,
            button=button,
            modifiers=modifiers,
            state=ClickRouteState(
                identify_click_enabled=self._mode_session.identify_click_enabled(),
                optimize_shift_click_enabled=self._mode_session.optimize_shift_click_enabled(),
                active_channel=self.active_input_channel(),
            ),
        )
        self._command_executor.execute_click_commands(result.commands)
        return result.handled

    def handle_wheel(
        self,
        pos: tuple[float, float],
        delta: float | QPoint | QPointF | tuple[int | float, int | float],
    ) -> bool:
        """Convert wheel event to zoom/pan intents.

        Args:
            pos: Mouse position (wavelength, flux)
            delta: Wheel delta. ``int`` preserves legacy zoom-only calls while
                ``QPoint``/``tuple`` allows horizontal+vertical gestures.

        Returns:
            True if handled
        """
        current_range: tuple[float, float] | None = None
        try:
            current_range = self.view.get_wavelength_range()
        except (TypeError, ValueError):
            current_range = None

        result = self._wheel_router.route_wheel(
            position=pos, delta=delta, current_range=current_range
        )
        self._command_executor.execute_wheel_commands(result.commands)
        return result.handled

    def _emit_intent(self, intent: SpectrumInteractionIntent) -> None:
        """Emit the Qt signal for a typed interaction intent."""
        self._intent_emitter.emit(intent)

    def _emit_mode_click_signal(self, position: tuple[float, float], modifiers: int) -> None:
        """Emit the raw mode click signal."""
        self.sig_mode_click_requested.emit(position[0], position[1], modifiers)

    def emit_interaction_intent(self, intent: SpectrumInteractionIntent) -> None:
        """Emit a typed interaction intent for command executors."""
        self._interaction_runtime.emit_interaction_intent(intent)

    def cancel_rect_zoom_interaction(self, *, reason: str) -> bool:
        """Cancel rectangle zoom for command executors."""
        return self._interaction_runtime.cancel_rect_zoom_interaction(reason=reason)

    def emit_mode_velocity_shortcut(self) -> None:
        """Route a velocity shortcut to the active mode owner."""
        self._interaction_runtime.emit_mode_velocity_shortcut()

    def emit_mode_click(self, position: tuple[float, float], modifiers: int) -> None:
        """Route a raw mode click to the active mode owner."""
        self._interaction_runtime.emit_mode_click(position, modifiers)

    def cancel_mask_selection(self, *, reason: str) -> bool:
        """Cancel mask selection for command executors."""
        return self._interaction_runtime.cancel_mask_selection(reason=reason)

    def begin_rect_zoom_interaction(self, position: tuple[float, float], modifiers: int) -> None:
        """Begin rectangle zoom for command executors."""
        self._interaction_runtime.begin_rect_zoom_interaction(position, modifiers)

    def show_context_menu(self, position: tuple[float, float]) -> bool:
        """Show the spectrum context menu for command executors."""
        return self._interaction_runtime.show_context_menu(position)

    def set_mode_capabilities(self, capabilities: SpectrumInputCapabilities) -> None:
        """Apply mode-derived input capabilities."""
        self._mode_session.set_capabilities(capabilities)

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Set rectangle zoom mode.

        Args:
            enabled: Whether to enable rectangle zoom mode.
        """
        self._rect_zoom_input_controller.set_mode_enabled(enabled)

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return True when rectangle zoom mode is active."""
        return self._rect_zoom_input_controller.is_mode_enabled()

    def can_process_continuum_event(self) -> bool:
        """Check if continuum events can be processed.

        Returns:
            True if no other interaction channel is active, False otherwise.
        """
        return self._channel_session.can_start(InteractionChannel.CONTINUUM)

    def process_continuum_interaction_event(self, event: InteractionEvent) -> bool:
        """Process a continuum interaction event through the continuum controller."""
        if event.channel is not InteractionChannel.CONTINUUM:
            msg = f"Expected CONTINUUM interaction event, got {event.channel!r}."
            raise ValueError(msg)

        controller = self._continuum_state_controller
        if controller is None:
            msg = "Continuum state controller is required for continuum interaction events."
            raise RuntimeError(msg)

        if not self._channel_session.can_start(InteractionChannel.CONTINUUM):
            return False

        return controller.process_event(event)

    def cancel_continuum_interaction(self, *, reason: str | None = None) -> bool:
        """Cancel the active continuum interaction, if one is running."""
        controller = self._continuum_state_controller
        if controller is None:
            msg = "Continuum state controller is required to cancel continuum interaction."
            raise RuntimeError(msg)
        return controller.cancel_interaction(reason=reason)

    def begin_mask_selection_interaction(self, request: MaskSelectionRequest) -> bool:
        """Prime the mask selection controller using the provided request."""
        return self._mask_selection_input_controller.begin_interaction(request)

    def cancel_mask_selection_interaction(self, *, reason: str | None = None) -> bool:
        """Cancel the active mask selection interaction if present."""
        return self._mask_selection_input_controller.cancel_interaction(reason=reason)

    def _reset_mask_selection_state(self) -> None:
        """Clear mask selection tracking fields."""
        self._mask_selection_input_controller.reset()

    def _set_mask_cursor(self, active: bool) -> None:
        """Apply cursor feedback while mask selection mode is active."""
        self.set_mask_selection_cursor(active)

    def handle_mouse_move_event(self, event: QMouseEvent) -> bool:
        """Handle mouse move events.

        Args:
            event: Mouse move event

        Returns:
            True if handled
        """
        return self._pointer_input_controller.handle_mouse_move_event(event)

    def handle_mouse_release_event(self, event: QMouseEvent) -> bool:
        """Handle mouse release events.

        Args:
            event: Mouse release event

        Returns:
            True if handled
        """
        return self._pointer_input_controller.handle_mouse_release_event(event)

    def handle_mouse_leave(self) -> None:
        """Notify listeners that the cursor left the plot region."""
        self._pointer_input_controller.handle_mouse_leave()

    def handle_double_click_center(self, wavelength: float) -> None:
        """Handle double-click to center spectrum on wavelength.

        Args:
            wavelength: Wavelength to center on
        """
        self._pointer_input_controller.handle_double_click_center(wavelength)

    def handle_mouse_press_event(self, event: QMouseEvent) -> bool:
        """Handle mouse press events (matplotlib bridge compatible).

        Args:
            event: Mouse press event

        Returns:
            True if handled
        """
        return self._pointer_input_controller.handle_mouse_press_event(event)

    def attach_plot_widget(self, plot_widget: SpectrumPlotWidgetPort) -> None:
        """Attach a required plot widget and initialize coordinate transform."""
        self._plot_input_binding.attach_plot_widget(plot_widget, event_sink=self)
        logger.debug("PlotCoordinateTransform initialized")

    def detach_plot_widget(self) -> None:
        """Detach the current plot widget and clear coordinate transform."""
        self._plot_input_binding.detach_plot_widget()

    def process_mouse_event(self, event: QMouseEvent | QWheelEvent) -> None:
        """Process Qt mouse event and generate intents.

        Args:
            event: Qt mouse or wheel event
        """
        self._pointer_input_controller.process_mouse_event(event)

    def process_key_event(self, event: QKeyEvent) -> None:
        """Process Qt key event and generate intents.

        Args:
            event: Qt key event
        """
        self.handle_key_event(event)

    def process_key_release_event(self, event: QKeyEvent) -> None:
        """Process a Qt key-release event for transient mode input."""
        self.handle_key_release_event(event)

    def _detect_absorber_at_position(self, wavelength: float) -> str | None:
        """Detect absorber at given wavelength position.

        Args:
            wavelength: Wavelength to check

        Returns:
            Absorber ID if found, None otherwise
        """
        return self.absorber_at_wavelength(wavelength)

    def absorber_at_wavelength(self, wavelength: float) -> str | None:
        """Return the absorber at a wavelength, if any."""
        return self._plot_input_binding.absorber_at_wavelength(wavelength)

    def _can_drag_absorber(self, absorber_id: str) -> bool:
        """Check if an absorber can be dragged based on current mode and selection.

        Args:
            absorber_id: ID of the absorber to check

        Returns:
            True if the absorber can be dragged, False otherwise
        """
        return self._absorber_drag_input_controller.can_drag_absorber(absorber_id)

    def set_selected_line_absorbers(self, absorber_ids: set[str] | None) -> None:
        """Set the absorbers that belong to the selected line in OPTIMIZE mode.

        Args:
            absorber_ids: Set of absorber IDs that can be dragged, or None to allow all
        """
        self._absorber_drag_input_controller.set_selected_line_absorbers(absorber_ids)

    def connect_velocity_view(self, velocity_view: VelocityDragSignalPort) -> None:
        """Connect velocity view signals for D&D handling.

        Args:
            velocity_view: The velocity view to connect
        """
        self._sync_velocity_drag_adapter_controller()
        self._velocity_drag_adapter.connect_velocity_view(velocity_view)
