"""Identify-mode handling for shared spectrum surface intents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from chappy.gui.modes.identify import IdentifyContextMenuController, IdentifyContextMenuRequest
from chappy.gui.protocols.intent_types import (
    AddIdentifyTemporaryLineIntent,
    ToggleIdentifyPreviewLockIntent,
    ToggleVelocityPlotIntent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.protocols.context_menu import (
        ContextMenuActionDescriptor,
        ContextMenuActionIntent,
    )
    from chappy.gui.protocols.intent_types import ShowContextMenuIntent
    from chappy.gui.protocols.spectrum_intents import IdentifyModeIntent


class IdentifySharedSurfaceWorkflowPort(Protocol):
    """Identify workflow operations used by shared surface intents."""

    def handle_manual_temporary_line(
        self, *, observed_wavelength: float, modifiers: int, source: str
    ) -> None:
        """Place manual identify temporary lines at the observed wavelength."""
        ...

    def set_preview_always_on(self, enabled: bool) -> None:
        """Toggle identify preview lock state."""
        ...

    def preview_always_on(self) -> bool:
        """Return whether identify preview lock is active."""
        ...

    def baseline_line_selected(self) -> bool:
        """Return whether the active preset defines a baseline line."""
        ...

    def clear_cursor_preview(self) -> None:
        """Clear the current cursor preview and its transient guidance."""
        ...


class IdentifySharedSurfaceIntentController:
    """Route shared spectrum surface actions to identify-mode workflow."""

    def __init__(
        self,
        *,
        workflow_provider: Callable[[], IdentifySharedSurfaceWorkflowPort | None],
        velocity_toggle_callback: Callable[[float | None], None],
        cursor_wavelength_provider: Callable[[], float | None],
        action_provider: IdentifyContextMenuController | None = None,
    ) -> None:
        """Initialize the controller."""
        self._workflow_provider = workflow_provider
        self._velocity_toggle_callback = velocity_toggle_callback
        self._cursor_wavelength_provider = cursor_wavelength_provider
        self._action_provider = action_provider or IdentifyContextMenuController()

    def handle_mode_click(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Handle a mode-specific spectrum click."""
        _ = flux
        self._required_workflow("manual temporary-line requests").handle_manual_temporary_line(
            observed_wavelength=float(wavelength), modifiers=int(modifiers), source="click"
        )

    def handle_mode_velocity_shortcut(self) -> None:
        """Toggle the velocity plot at the wavelength under the cursor."""
        self.handle_intent(ToggleVelocityPlotIntent(wavelength=self._cursor_wavelength_provider()))

    def handle_click(self, wavelength: float, modifiers: int) -> None:
        """Backward-compatible alias for identify click handling."""
        self.handle_mode_click(wavelength, 0.0, modifiers)

    def handle_intent(self, intent: IdentifyModeIntent) -> None:
        """Handle an identify-mode intent."""
        if isinstance(intent, ToggleVelocityPlotIntent):
            self._required_workflow("velocity plot requests").clear_cursor_preview()
            self._velocity_toggle_callback(intent.wavelength)
            return

        if isinstance(intent, ToggleIdentifyPreviewLockIntent):
            self._required_workflow("preview lock intents").set_preview_always_on(intent.enabled)
            return

        if isinstance(intent, AddIdentifyTemporaryLineIntent):
            self._required_workflow("manual temporary-line intents").handle_manual_temporary_line(
                observed_wavelength=float(intent.wavelength),
                modifiers=int(intent.modifiers),
                source=intent.source,
            )

    def handle_identify_intent(self, intent: IdentifyModeIntent) -> None:
        """Handle an identify-mode intent routed by the shell."""
        self.handle_intent(intent)

    def handle_context_menu_intent(self, intent: ContextMenuActionIntent) -> None:
        """Handle a context-menu intent for identify mode."""
        self.handle_intent(intent)

    def context_menu_actions(
        self, request: ShowContextMenuIntent
    ) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return identify context-menu actions for the active workflow."""
        workflow = self._workflow_provider()
        preview_lock_state = workflow.preview_always_on() if workflow is not None else False
        preview_lock_available = workflow is not None
        baseline_line_selected = workflow is not None and workflow.baseline_line_selected()
        return self._action_provider.actions_for_request(
            IdentifyContextMenuRequest(
                wavelength=float(request.wavelength),
                preview_lock_enabled=preview_lock_state,
                preview_lock_available=preview_lock_available,
                baseline_line_selected=baseline_line_selected,
            )
        )

    def _required_workflow(self, purpose: str) -> IdentifySharedSurfaceWorkflowPort:
        """Return identify workflow or raise for a missing owner."""
        workflow = self._workflow_provider()
        if workflow is None:
            msg = f"Identify coordinator is required for {purpose}."
            raise RuntimeError(msg)
        return workflow
