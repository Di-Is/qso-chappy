"""Component coordination and integration for spectrum view.

This module handles coordination between different spectrum view
components and manages their lifecycle.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from PySide6.QtCore import QObject, Qt, Signal

from chappy.gui.protocols.optimize_spectrum import (
    OptimizeCursorMode,
    OptimizeLineInfo,
    SpectrumModeIntegrationPort,
)
from chappy.gui.spectrum.interaction_controller_factory import SpectrumInteractionControllerFactory
from chappy.gui.spectrum.interaction_state_coordinator import (
    SpectrumInteractionSnapshot,
    SpectrumInteractionStateCoordinator,
)
from chappy.gui.spectrum.policy import SpectrumPolicyCleanupError
from chappy.gui.spectrum.project_data_refresh_controller import (
    SpectrumProjectDataRefreshController,
)
from chappy.presentation.interaction.interaction_contracts import (
    InteractionChannel,
    InteractionPhase,
    InteractionStateSnapshot,
    MaskSelectionRequest,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QWidget

    from chappy.core.components.absorber import AbsorberComponent
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.protocols.context_menu import (
        ContextMenuActionDescriptor,
        ContextMenuActionIntent,
    )
    from chappy.gui.protocols.intent_types import ShowContextMenuIntent
    from chappy.gui.protocols.spectrum_intents import IdentifyModeIntent, SpectrumModeIntentSink
    from chappy.gui.spectrum.absorber_interaction_controller import (
        AbsorberIntent,
        AbsorberModelMutationPort,
    )
    from chappy.gui.spectrum.context_menu_controller import (
        ContextMenuActionProvider,
        SharedContextMenuActionProvider,
    )
    from chappy.gui.spectrum.interaction.input.ports import SpectrumInputFacadePort
    from chappy.gui.spectrum.interaction_controller_factory import (
        SpectrumInteractionControllerFactory,
    )
    from chappy.gui.spectrum.navigation_controller import (
        SpectrumNavigationControllerFactory,
        SpectrumNavigationIntent,
    )
    from chappy.gui.spectrum.policy import SpectrumInputCapabilities, SpectrumPolicy
    from chappy.gui.spectrum.range_coordinator import RangeHistoryRecorder
    from chappy.gui.spectrum.range_input_controls import SpectrumRangeInputControls
    from chappy.gui.spectrum.spectrum_plot import SpectrumPlotSurfaceProtocol
    from chappy.gui.spectrum.spectrum_view import SpectrumView
    from chappy.gui.spectrum.spectrum_view_components import SpectrumViewComponents
    from chappy.presentation.velocity import VelocityOverlayInfo

logger = logging.getLogger(__name__)


type LogExtraScalar = str | int | float | bool | None
type LogExtraValue = (
    LogExtraScalar
    | list[float]
    | tuple[float | None, float | None]
    | dict[str, LogExtraScalar | tuple[float, float] | None]
)


@runtime_checkable
class ModeAwareComponent(Protocol):
    """Component that can receive mode-derived input capabilities."""

    def set_mode_capabilities(self, capabilities: SpectrumInputCapabilities) -> None:
        """Set active input capabilities."""
        ...


@runtime_checkable
class VelocityOverlayInfoProvider(Protocol):
    """View-like endpoint exposing active velocity overlay metadata."""

    def get_velocity_overlay_info(self) -> VelocityOverlayInfo | None:
        """Return velocity overlay metadata when visible."""
        ...


@runtime_checkable
class CursorTarget(Protocol):
    """Widget-like endpoint that accepts cursor updates."""

    def setCursor(self, cursor: Qt.CursorShape) -> None:  # noqa: N802
        """Set the cursor shape."""
        ...


@runtime_checkable
class PlotWidgetOwner(Protocol):
    """Plot host that exposes the active plot widget."""

    plot_widget: SpectrumPlotSurfaceProtocol | None


@runtime_checkable
class CanvasWidgetOwner(Protocol):
    """Object that exposes a QWidget canvas."""

    canvas: QWidget


class SpectrumInteractionCoordinator(QObject):
    """Presents spectrum logic and coordinates components (MVP-Lite pattern).

    Responsibilities:
    - Component lifecycle management
    - Event coordination between components
    - State synchronization
    - Mode management integration
    """

    # Signals
    mode_command_requested = Signal(str)
    interaction_snapshot_applied = Signal(InteractionStateSnapshot)

    def __init__(
        self,
        view: SpectrumView,
        navigation_controller_factory: SpectrumNavigationControllerFactory,
        interaction_controller_factory: SpectrumInteractionControllerFactory,
        components: SpectrumViewComponents,
    ) -> None:
        """Initialize the coordinator with optional dependency injection.

        Args:
            view: The spectrum view to coordinate
            navigation_controller_factory: Factory for navigation controller creation.
            interaction_controller_factory: Factory for interaction controller creation.
            components: Required spectrum view components.
        """
        super().__init__()

        self.view = view
        self.data_bridge = components.data_bridge
        self._current_policy: SpectrumPolicy | None = None
        self._connected_signals: set[str] = set()

        # Optimize mode integration
        self._optimize_integration: SpectrumModeIntegrationPort | None = None
        self._mode_intent_sink: SpectrumModeIntentSink | None = None
        self._absorber_model_mutation_owner: AbsorberModelMutationPort | None = None

        # Cached strongly typed component references
        self.plot_host = components.plot_host
        self.range_input_controls = components.range_input_controls
        self.interactor = components.interactor

        # History integration
        self._history_recorder: RangeHistoryRecorder | None = None
        self._range_coordinator = interaction_controller_factory.create_range_coordinator(
            data_bridge_provider=lambda: self.data_bridge,
            plot_host_provider=lambda: self.plot_host,
            range_input_provider=lambda: self.range_input_controls,
            history_recorder_provider=lambda: self._history_recorder,
            flux_range_override_provider=view.get_velocity_plot_y_range,
        )
        self._navigation_controller = navigation_controller_factory.create(
            current_range_provider=self._get_navigation_current_wavelength_range,
            data_bounds_provider=self._get_data_wavelength_bounds,
            coordinate_range_update=self._coordinate_navigation_range_update,
            disable_auto_adjust_y=self.disable_auto_adjust_y,
            active_interaction_channel_provider=self._active_interaction_channel,
            mode_command_emitter=self.mode_command_requested.emit,
        )
        self._absorber_drag_coordinator = (
            interaction_controller_factory.create_absorber_drag_coordinator(
                absorber_provider=self._resolve_absorber_for_drag,
                velocity_overlay_provider=self._velocity_overlay_info,
                plot_widget_provider=self._plot_widget,
                drag_apply_callback=lambda component_id, new_redshift, before_states: (
                    self._require_absorber_model_mutation_owner().apply_drag(
                        component_id, new_redshift, before_states
                    )
                ),
                cursor_reset_callback=self._reset_cursor_after_drag,
            )
        )
        self._absorber_interaction_controller = (
            interaction_controller_factory.create_absorber_interaction_controller(
                mutation_provider=lambda: self._absorber_model_mutation_owner,
                selection_callback=self._emit_absorber_selected,
                drag_coordinator=self._absorber_drag_coordinator,
            )
        )
        self._mask_interaction_controller = (
            interaction_controller_factory.create_mask_interaction_controller(
                interactor_provider=lambda: self.interactor,
                plot_host_provider=lambda: self.plot_host,
                integration_provider=lambda: self._optimize_integration,
                snapshot_callback=self._publish_interaction_snapshot,
            )
        )
        self._interaction_state_coordinator = SpectrumInteractionStateCoordinator(
            snapshot_publisher=self._publish_interaction_snapshot,
            mask_controller=self._mask_interaction_controller,
        )
        self._context_menu_controller = (
            interaction_controller_factory.create_context_menu_controller(
                view_provider=lambda: self.view,
                action_provider=self._empty_context_menu_actions,
                intent_handler=self.coordinate_context_menu_intent,
                parent=self,
            )
        )
        self._project_data_refresh_controller = SpectrumProjectDataRefreshController(
            data_bridge_provider=lambda: self.data_bridge,
            components_provider=self._project_data_refresh_components,
            range_changed_callback=self._range_coordinator.handle_data_bridge_range_changed,
            auto_scale_callback=self._range_coordinator.auto_scale,
        )
        self._connect_data_bridge_signals()
        self._setup_range_component(self.range_input_controls)
        self._connect_interactor_signals(self.interactor)

        logger.debug("SpectrumInteractionCoordinator initialized with DI support")

    def _get_line_info_for_component(
        self, component: AbsorberComponent
    ) -> OptimizeLineInfo | None:
        """Get line information for a component.

        Args:
            component: The absorber component

        Returns:
            Dict with line info (rest_wavelength, lambda_range) or None
        """
        # Try to get line info through optimize integration if available
        if self._optimize_integration:
            return self._optimize_integration.get_line_info_for_component(component)

        # Fallback: extract basic info from component itself
        return OptimizeLineInfo(rest_wavelength=float(component.wavelength), lambda_range=None)

    def line_info_for_component(self, component: AbsorberComponent) -> OptimizeLineInfo | None:
        """Return optimize line information for a component."""
        return self._get_line_info_for_component(component)

    def _plot_widget(self) -> SpectrumPlotSurfaceProtocol | None:
        """Return the active plot widget from the typed plot host."""
        plot_host = self.plot_host
        if not isinstance(plot_host, PlotWidgetOwner):
            return None
        return plot_host.plot_widget

    def _current_project(self) -> SpectroscopyProject | None:
        """Return the active project through the data bridge boundary."""
        if self.data_bridge is None:
            return None
        return self.data_bridge.project

    def _emit_data_updated(self) -> None:
        """Notify data-bridge observers that model data changed."""
        if self.data_bridge is None:
            return
        self.data_bridge.data_updated.emit()

    def emit_data_updated(self) -> None:
        """Notify data-bridge observers that model data changed."""
        self._emit_data_updated()

    def _refresh_optimize_tree_view(self) -> None:
        """Refresh optimize model tree state when available."""
        if self._optimize_integration:
            self._optimize_integration.update_tree_view()

    def refresh_optimize_tree_view(self) -> None:
        """Refresh optimize model tree state when available."""
        self._refresh_optimize_tree_view()

    def _focus_optimize_component(self, component_id: str) -> None:
        """Focus an optimize component row when optimize integration is available."""
        if self._optimize_integration:
            self._optimize_integration.focus_component(component_id)

    def focus_optimize_component(self, component_id: str) -> None:
        """Focus an optimize component row when optimize integration is available."""
        self._focus_optimize_component(component_id)

    def plot_widget(self) -> SpectrumPlotSurfaceProtocol | None:
        """Return the active plot widget from the coordinated plot host."""
        return self._plot_widget()

    def set_history_recorder(self, recorder: RangeHistoryRecorder) -> None:
        """Set the history recorder for range-change undo/redo support.

        Args:
            recorder: The history recorder instance.
        """
        self._history_recorder = recorder
        logger.debug("History recorder connected to SpectrumInteractionCoordinator")

    # ========== Component Management ==========

    def attach_optimize_integration(self, integration: SpectrumModeIntegrationPort) -> None:
        """Attach the optimize mode integration handler.

        Args:
            integration: Optimize spectrum integration port.
        """
        if integration is None:
            msg = "Optimize integration is required."
            raise TypeError(msg)
        self._optimize_integration = integration

    def detach_optimize_integration(self) -> None:
        """Detach the optimize mode integration handler."""
        self._optimize_integration = None

    def attach_absorber_model_mutation_owner(self, owner: AbsorberModelMutationPort) -> None:
        """Attach the shell-owned absorber mutation owner."""
        if owner is None:
            msg = "Absorber model mutation owner is required."
            raise TypeError(msg)
        self._absorber_model_mutation_owner = owner

    def detach_absorber_model_mutation_owner(self) -> None:
        """Detach the shell-owned absorber mutation owner."""
        self._absorber_model_mutation_owner = None

    def _require_absorber_model_mutation_owner(self) -> AbsorberModelMutationPort:
        """Return the attached absorber mutation owner or fail fast."""
        if self._absorber_model_mutation_owner is None:
            msg = "Absorber model mutation owner is required."
            raise RuntimeError(msg)
        return self._absorber_model_mutation_owner

    def _resolve_absorber_for_drag(self, absorber_id: str) -> AbsorberComponent | None:
        """Resolve an absorber for drag overlays when a mutation owner is attached."""
        if self._absorber_model_mutation_owner is None:
            return None
        return self._absorber_model_mutation_owner.resolve_absorber(absorber_id)

    def attach_mode_intent_sink(self, sink: SpectrumModeIntentSink) -> None:
        """Attach the shell-owned mode intent sink."""
        if sink is None:
            msg = "Mode intent sink is required."
            raise TypeError(msg)
        self._mode_intent_sink = sink

    def detach_mode_intent_sink(self) -> None:
        """Detach the shell-owned mode intent sink."""
        self._mode_intent_sink = None

    def _require_mode_intent_sink(self) -> SpectrumModeIntentSink:
        """Return the attached mode intent sink or fail fast."""
        if self._mode_intent_sink is None:
            msg = "Mode intent sink is required for mode-specific spectrum intents."
            raise RuntimeError(msg)
        return self._mode_intent_sink

    def set_absorber_drag_candidates(self, absorber_ids: set[str] | None) -> None:
        """Set absorber IDs available for drag operations."""
        interactor = self.interactor
        if interactor is None:
            msg = "Spectrum interactor is required to set absorber drag candidates."
            raise RuntimeError(msg)
        interactor.set_selected_line_absorbers(absorber_ids)

    def set_context_menu_action_provider(self, provider: ContextMenuActionProvider) -> None:
        """Set the context menu action provider for raw menu requests."""
        self._context_menu_controller.set_action_provider(provider)

    def set_context_menu_shared_actions(self, provider: SharedContextMenuActionProvider) -> None:
        """Set the mode-independent actions appended to every spectrum context menu."""
        self._context_menu_controller.set_shared_actions(provider)

    def _empty_context_menu_actions(
        self, _intent: ShowContextMenuIntent
    ) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return no context menu actions when no shell provider is connected."""
        return ()

    def apply_optimize_cursor_mode(self, cursor_mode: OptimizeCursorMode) -> None:
        """Apply optimize cursor feedback to the spectrum plot surface."""
        plot_widget = self._plot_widget()
        if plot_widget is None:
            return

        widgets_to_update: list[CursorTarget] = []
        if isinstance(plot_widget, CursorTarget):
            widgets_to_update.append(plot_widget)
        if isinstance(plot_widget, CanvasWidgetOwner):
            widgets_to_update.append(plot_widget.canvas)

        def _set_cursor(shape: Qt.CursorShape) -> None:
            for widget in widgets_to_update:
                widget.setCursor(shape)

        if cursor_mode == "crosshair":
            _set_cursor(Qt.CursorShape.CrossCursor)
        elif cursor_mode == "not-allowed":
            _set_cursor(Qt.CursorShape.ForbiddenCursor)
        else:
            _set_cursor(Qt.CursorShape.ArrowCursor)

    def reset_optimize_cursor(self) -> None:
        """Restore the default cursor for the spectrum plot."""
        plot_widget = self._plot_widget()
        if plot_widget is None:
            return

        widgets: list[CursorTarget] = []
        if isinstance(plot_widget, CursorTarget):
            widgets.append(plot_widget)
        if isinstance(plot_widget, CanvasWidgetOwner):
            widgets.append(plot_widget.canvas)

        for widget in widgets:
            widget.setCursor(Qt.CursorShape.ArrowCursor)

    def _setup_range_component(self, component: SpectrumRangeInputControls) -> None:
        """Setup range input component.

        Args:
            component: Range input component.
        """
        logger.debug("Connecting range input signals")
        component.wavelength_range_changed.connect(
            lambda min_w, max_w: self.coordinate_range_update("range_input", min_w, max_w)
        )

        # Connect auto flux range request to presenter handler

    def _connect_interactor_signals(self, interactor: SpectrumInputFacadePort) -> None:
        """Connect interactor signals required by the presenter.

        Args:
            interactor: Spectrum interactor instance providing interaction signals.
        """
        interactor_key = id(interactor)
        snapshot_key = f"interactor:{interactor_key}:snapshots"
        if snapshot_key not in self._connected_signals:
            logger.debug("🔗 Connecting interactor snapshot signal")
            interactor.sig_interaction_snapshot.connect(self.apply_interaction_state_snapshot)
            self._connected_signals.add(snapshot_key)

        optimize_cursor_key = f"interactor:{interactor_key}:optimize_cursor"
        if optimize_cursor_key not in self._connected_signals:
            interactor.sig_cursor_position_changed.connect(self._on_interactor_cursor_position)
            self._connected_signals.add(optimize_cursor_key)

    def _on_interactor_cursor_position(
        self, wavelength: float, _flux: float, modifiers: int
    ) -> None:
        """Route typed interactor cursor events to optimize integration."""
        if self._current_policy is None or not self._current_policy.cursor_enabled:
            self.apply_optimize_cursor_mode("default")
            return

        integration = self._optimize_integration
        if integration is None:
            self.apply_optimize_cursor_mode("default")
            return

        shift_value = Qt.KeyboardModifier.ShiftModifier.value
        if not isinstance(shift_value, int):
            msg = f"Qt Shift modifier value must be int, got {type(shift_value).__name__}."
            raise TypeError(msg)
        integration.handle_cursor_position(wavelength, bool(modifiers & shift_value))

    def _velocity_overlay_info(self) -> VelocityOverlayInfo | None:
        """Return active velocity overlay metadata when the view exposes it."""
        if isinstance(self.view, VelocityOverlayInfoProvider):
            return self.view.get_velocity_overlay_info()
        return None

    def _project_data_refresh_components(self) -> tuple[object, ...]:
        """Return components observed by the project/data refresh controller."""
        return (self.plot_host, self.range_input_controls, self.interactor)

    def set_interaction_mode(self, mode_name: str | None) -> None:
        """Apply interaction sub-mode settings across components."""
        interactor = self.interactor
        if interactor:
            interactor.set_rect_zoom_mode(mode_name == "rect_zoom")

        logger.debug("Interaction mode set to: %s", mode_name or "none")

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return True when the interactor currently tracks rect zoom mode."""
        interactor = self.interactor
        if interactor:
            return bool(interactor.is_rect_zoom_mode_enabled())
        return False

    def apply_interaction_state_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Apply an interaction state snapshot emitted by the interactor."""
        self._interaction_state_coordinator.apply_interaction_state_snapshot(snapshot)

    def _publish_interaction_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Publish an interaction snapshot to Qt observers."""
        self.interaction_snapshot_applied.emit(snapshot)

    @property
    def _latest_interaction_snapshot(self) -> SpectrumInteractionSnapshot | None:
        """Return the latest interaction snapshot cached by the state coordinator."""
        return self._interaction_state_coordinator.latest_snapshot

    def coordinate_range_update(
        self,
        source: str,
        min_wave: float,
        max_wave: float,
        *,
        flux_range: tuple[float, float] | None = None,
        record_history: bool = True,
        old_wave_range: tuple[float, float] | None = None,
        old_flux_range: tuple[float, float] | None = None,
    ) -> None:
        """Coordinate wavelength range updates between components.

        This is the single entry point for all range changes that should be
        recorded in history. All zoom/pan/reset operations should go through
        this method.

        Args:
            source: Name of component initiating the update
            min_wave: Minimum wavelength
            max_wave: Maximum wavelength
            flux_range: Optional (min_flux, max_flux) tuple. If provided,
                flux range is also updated and included in history.
            record_history: If True, record to undo history (default True).
                Set to False during undo/redo application.
            old_wave_range: Optional previous wavelength range for history.
                If not provided, current range is captured automatically.
            old_flux_range: Optional previous flux range for history.
                If not provided, current range is captured automatically.
        """
        self._range_coordinator.coordinate_range_update(
            source,
            min_wave,
            max_wave,
            flux_range=flux_range,
            record_history=record_history,
            old_wave_range=old_wave_range,
            old_flux_range=old_flux_range,
        )

    def handle_auto_flux_range_request(self) -> None:
        """Handle auto flux range requests and enable auto-adjust mode."""
        self._range_coordinator.handle_auto_flux_range_request()

    def disable_auto_adjust_y(self) -> None:
        """Disable auto-adjust Y mode."""
        self._range_coordinator.disable_auto_adjust_y()

    def _coordinate_navigation_range_update(
        self,
        source: str,
        min_wave: float,
        max_wave: float,
        *,
        flux_range: tuple[float, float] | None = None,
    ) -> None:
        """Apply a range update requested by the navigation controller."""
        self.coordinate_range_update(source, min_wave, max_wave, flux_range=flux_range)

    def _active_interaction_channel(self) -> InteractionChannel | None:
        """Return the active interaction channel if a snapshot is available."""
        if self._latest_interaction_snapshot is None:
            return None
        return self._latest_interaction_snapshot.channel

    def _reset_cursor_after_drag(self) -> None:
        """Restore the default cursor after absorber drag cancellation."""
        self.view.setCursor(Qt.CursorShape.ArrowCursor)

    def _emit_absorber_selected(self, absorber_id: str) -> None:
        """Emit absorber selection through the coordinated view."""
        self.view.absorber_selected.emit(absorber_id)

    def request_mask_selection_interaction(self, request: MaskSelectionRequest) -> bool:
        """Route mask selection request to the spectrum interactor."""
        return self._mask_interaction_controller.request_mask_selection_interaction(request)

    def highlight_mask(self, mask_id: str | None) -> None:
        """Highlight mask overlay on spectrum plot."""
        self._mask_interaction_controller.highlight_mask(mask_id)

    def cancel_mask_selection(self) -> None:
        """Cancel any active mask selection on the spectrum plot component."""
        self._mask_interaction_controller.cancel_mask_selection()

    def set_active_mask_group(self, group_id: str | None) -> None:
        """Update the mask group that should be emphasised in the plot.

        Args:
            group_id: Identifier of the group to display, or ``None`` to clear.
        """
        self._mask_interaction_controller.set_active_mask_group(group_id)

    def set_selected_component_id(self, component_id: str | None) -> None:
        """Emphasise one absorber component's marker label on the coordinated view.

        Args:
            component_id: Identifier of the component to emphasise, or ``None`` to clear.
        """
        self.view.set_selected_component_id(component_id)

    def _connect_data_bridge_signals(self) -> None:
        """Connect data bridge signals."""
        self._project_data_refresh_controller.connect_data_bridge_signals(self.data_bridge)

    def preflight_policy(self, policy: SpectrumPolicy) -> None:
        """Validate required policy consumers before irreversible cleanup."""
        _ = policy
        if not isinstance(self.interactor, ModeAwareComponent):
            msg = "Spectrum input facade must accept neutral policy capabilities."
            raise TypeError(msg)

    def cleanup_for_policy(self, policy: SpectrumPolicy) -> None:
        """Best-effort every irreversible cleanup stage in deterministic order."""
        cleanup = policy.transition_cleanup
        errors: list[Exception] = []

        def attempt(operation: Callable[[], object]) -> None:
            try:
                operation()
            except Exception as error:  # noqa: BLE001 - aggregate cleanup failures
                errors.append(error)

        if cleanup.cancel_mask_selection:
            attempt(self.cancel_mask_selection)
        if cleanup.cancel_absorber_drag:
            attempt(self.cancel_active_drags)
        if (
            cleanup.clear_interaction_mode
            and self._latest_interaction_snapshot is not None
            and not self._is_terminal_phase(self._latest_interaction_snapshot.phase)
        ):
            attempt(lambda: self.set_interaction_mode(None))
        if errors:
            raise SpectrumPolicyCleanupError(tuple(errors))

    def commit_policy(self, policy: SpectrumPolicy) -> None:
        """Commit reversible interaction capabilities after cleanup succeeds."""
        interactor = self.interactor
        if not isinstance(interactor, ModeAwareComponent):
            msg = "Spectrum input facade must accept neutral policy capabilities."
            raise TypeError(msg)
        interactor.set_mode_capabilities(policy.input_capabilities)
        self._current_policy = policy

    def invalidate_policy(self) -> None:
        """Mark capabilities unknown after rollback itself fails."""
        self._current_policy = None

    def _is_terminal_phase(self, phase: InteractionPhase) -> bool:
        """Check if the phase represents a terminal state.

        Terminal phases (IDLE, CANCELLED) indicate the interaction has concluded
        and should not be reapplied or trigger automatic mode clearing.

        Args:
            phase: Interaction phase to check

        Returns:
            True if the phase is terminal (IDLE or CANCELLED), False otherwise
        """
        return phase in (InteractionPhase.IDLE, InteractionPhase.CANCELLED)

    def reset_view_ranges(
        self,
        *,
        wavelength_range: tuple[float, float] | None = None,
        flux_range: tuple[float, float] | None = None,
    ) -> None:
        """Reset coordinated spectrum ranges using explicit bounds when provided.

        Args:
            wavelength_range: Optional wavelength bounds to restore.
            flux_range: Optional flux bounds paired with the wavelength range.
        """
        self._range_coordinator.reset_view_ranges(
            wavelength_range=wavelength_range, flux_range=flux_range
        )

    def update_absorber_param(self, absorber_name: str, param_name: str, value: float) -> None:
        """Public API for updating absorber parameters.

        Args:
            absorber_name: Name of the absorber
            param_name: Parameter name to update
            value: New parameter value
        """
        self._absorber_interaction_controller.update_parameter(absorber_name, param_name, value)

    def _refresh_plot_display(self) -> None:
        """Refresh plot display after model changes."""
        if not self.data_bridge or not self.data_bridge.project:
            return

        plot = self.plot_host
        if plot:
            plot.update_from_project(self.data_bridge.project)

    # ========== Intent Handling Methods (MVP-Lite Pattern) ==========

    # ========== Unified Navigation Intent Handler ==========

    def handle_navigation_intent(self, intent: SpectrumNavigationIntent) -> None:
        """Handle all navigation-related intents."""
        self._navigation_controller.handle_navigation_intent(intent)

    def _get_navigation_current_wavelength_range(self) -> tuple[float, float] | None:
        """Return current wavelength range when navigation has loaded spectrum data."""
        if not self.data_bridge or not self.data_bridge.project:
            return None
        return self._range_coordinator.get_current_wavelength_range()

    def _get_data_wavelength_bounds(self) -> tuple[float, float] | None:
        """Return wavelength bounds derived from the observed spectrum."""
        if not self.data_bridge or not self.data_bridge.project:
            return None

        spectrum = self.data_bridge.project.model.observed_spectrum
        if spectrum is None:
            return None

        data_min = float(spectrum.wavelength.min())
        data_max = float(spectrum.wavelength.max())
        if data_max <= data_min:
            return None
        return data_min, data_max

    def coordinate_absorber_intent(self, intent: AbsorberIntent) -> None:
        """Handle absorber-related intents.

        Args:
            intent: Absorber intent (SelectAbsorberIntent, ModifyAbsorberIntent, etc.)
        """
        self._absorber_interaction_controller.coordinate_absorber_intent(intent)

    def coordinate_mode_click(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Route a raw spectrum click to the active mode owner."""
        self._require_mode_intent_sink().handle_mode_click(wavelength, flux, modifiers)

    def coordinate_mode_velocity_shortcut(self) -> None:
        """Route a raw velocity shortcut to the active mode owner."""
        self._require_mode_intent_sink().handle_mode_velocity_shortcut()

    def cancel_active_drags(self) -> bool:
        """Cancel all active absorber drag operations.

        Returns:
            True when any drag state was cleared.
        """
        return self._absorber_interaction_controller.cancel_active_drags()

    def coordinate_context_menu(self, intent: ShowContextMenuIntent) -> None:
        """Handle context menu display intent.

        Args:
            intent: ShowContextMenuIntent
        """
        self._context_menu_controller.show(intent)

    def coordinate_context_menu_intent(self, intent: ContextMenuActionIntent) -> None:
        """Route typed context menu intents to the active workflow owner."""
        self._require_mode_intent_sink().handle_context_menu_intent(intent)

    def coordinate_continuum_intent(self, intent: ContextMenuActionIntent) -> None:
        """Handle continuum-mode context menu intents."""
        self._require_mode_intent_sink().handle_continuum_intent(intent)

    def coordinate_identify_intent(self, intent: IdentifyModeIntent) -> None:
        """Handle identify-mode specific intents."""
        self._require_mode_intent_sink().handle_identify_intent(intent)
