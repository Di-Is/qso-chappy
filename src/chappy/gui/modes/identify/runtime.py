"""Identify-mode runtime owning shared surface and velocity overlay workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.gui.modes.common import (
    ModeRuntime,
    VelocityOverlayPort,
    WavelengthFieldAvailabilityPort,
)
from chappy.gui.modes.identify.shared_surface_intent_controller import (
    IdentifySharedSurfaceIntentController,
    IdentifySharedSurfaceWorkflowPort,
)
from chappy.gui.modes.identify.velocity_overlay_adapter import identify_velocity_overlay_info
from chappy.gui.modes.identify.velocity_plot_controller import (
    IdentifyVelocityPlotController,
    IdentifyVelocityPlotPorts,
    IdentifyVelocityRangePort,
    IdentifyVelocityWorkflowPort,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from chappy.core.editing_mode import EditingMode
    from chappy.gui.protocols.context_menu import (
        ContextMenuActionDescriptor,
        ContextMenuActionIntent,
    )
    from chappy.gui.protocols.intent_types import ShowContextMenuIntent
    from chappy.gui.protocols.spectrum_intents import IdentifyModeIntent
    from chappy.presentation.identify import (
        IdentifyVelocityPlotContext,
        IdentifyVelocitySelectionPort,
    )
    from chappy.presentation.velocity import VelocityOverlayInfo


class IdentifyVelocityOverlayRuntimePort(ModeRuntime):
    """Identify runtime extension used by shell collaborators."""

    def hide_velocity_plot(self) -> None:
        """Hide the identify velocity overlay."""

    def refresh_velocity_overlay(self) -> None:
        """Refresh the identify velocity overlay."""

    def confirm_velocity_plot_selection(
        self,
        overlay_info: VelocityOverlayInfo | None,
        selections: Sequence[IdentifyVelocitySelectionPort],
    ) -> None:
        """Confirm selected velocity slices."""


class IdentifyModeRuntime(IdentifyVelocityOverlayRuntimePort):
    """Own identify shared-surface routing and velocity overlay workflow."""

    def __init__(
        self,
        *,
        current_mode_provider: Callable[[], EditingMode | None],
        workflow_provider: Callable[[], IdentifySharedSurfaceWorkflowPort | None],
        velocity_workflow_provider: Callable[[], IdentifyVelocityWorkflowPort],
        velocity_range_provider: Callable[[], IdentifyVelocityRangePort | None],
        cursor_wavelength_provider: Callable[[], float | None],
        velocity_overlay_port: VelocityOverlayPort,
        wavelength_field_availability_port: WavelengthFieldAvailabilityPort,
    ) -> None:
        """Initialize the identify runtime."""
        self._velocity_overlay_port = velocity_overlay_port
        self._shared_surface_controller = IdentifySharedSurfaceIntentController(
            workflow_provider=workflow_provider,
            velocity_toggle_callback=self._toggle_velocity_plot,
            cursor_wavelength_provider=cursor_wavelength_provider,
        )
        self._velocity_plot_controller = IdentifyVelocityPlotController(
            IdentifyVelocityPlotPorts(
                current_mode_provider=current_mode_provider,
                range_provider=velocity_range_provider,
                workflow_provider=velocity_workflow_provider,
                show_velocity_plot_callback=self._show_velocity_plot,
                hide_velocity_plot_callback=self._hide_velocity_overlay,
                wavelength_fields_enabled_callback=(
                    wavelength_field_availability_port.set_wavelength_fields_enabled
                ),
            )
        )

    def handle_mode_click(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Handle an identify spectrum click."""
        self._shared_surface_controller.handle_mode_click(wavelength, flux, modifiers)

    def handle_mode_velocity_shortcut(self) -> None:
        """Toggle the identify velocity plot at the wavelength under the cursor."""
        self._shared_surface_controller.handle_mode_velocity_shortcut()

    def handle_context_menu_intent(self, intent: ContextMenuActionIntent) -> None:
        """Handle a selected context-menu intent."""
        self._shared_surface_controller.handle_context_menu_intent(intent)

    def handle_identify_intent(self, intent: IdentifyModeIntent) -> None:
        """Handle an identify-mode intent."""
        self._shared_surface_controller.handle_identify_intent(intent)

    def context_menu_actions(
        self, request: ShowContextMenuIntent
    ) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return identify context-menu actions."""
        return self._shared_surface_controller.context_menu_actions(request)

    def hide_velocity_plot(self) -> None:
        """Hide the identify velocity overlay."""
        self._velocity_plot_controller.hide()

    def refresh_velocity_overlay(self) -> None:
        """Refresh the identify velocity overlay."""
        self._velocity_plot_controller.refresh()

    def confirm_velocity_plot_selection(
        self,
        overlay_info: VelocityOverlayInfo | None,
        selections: Sequence[IdentifyVelocitySelectionPort],
    ) -> None:
        """Confirm selected identify velocity slices."""
        self._velocity_plot_controller.confirm_selection(overlay_info, selections)

    def _toggle_velocity_plot(self, wavelength: float | None) -> None:
        """Toggle the identify velocity overlay."""
        self._velocity_plot_controller.toggle(wavelength)

    def _hide_velocity_overlay(self) -> None:
        """Hide the shared identify velocity overlay surface."""
        self._velocity_overlay_port.hide_velocity_overlay(context="identify")

    def _show_velocity_plot(self, context: IdentifyVelocityPlotContext) -> None:
        """Convert identify velocity context and show the shared overlay."""
        self._velocity_overlay_port.show_velocity_overlay(
            identify_velocity_overlay_info(context), context="identify"
        )
