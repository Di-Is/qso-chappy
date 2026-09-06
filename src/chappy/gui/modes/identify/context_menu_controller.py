"""Identify-mode context menu action provider."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject

from chappy.gui.protocols.context_menu import (
    ContextMenuActionDescriptor,
    ContextMenuToggleAction,
    ContextMenuTriggerAction,
)
from chappy.gui.protocols.intent_types import (
    ToggleIdentifyPreviewLockIntent,
    ToggleVelocityPlotIntent,
)
from chappy.presentation.identify import (
    IdentifyContextMenuAction,
    IdentifyContextMenuActionKind,
    IdentifyContextMenuMessages,
    IdentifyContextMenuState,
    build_identify_context_menu_actions,
)


@dataclass(frozen=True, slots=True)
class IdentifyContextMenuRequest:
    """State required to build identify context menu actions."""

    wavelength: float
    preview_lock_enabled: bool
    preview_lock_available: bool
    baseline_line_selected: bool


class IdentifyContextMenuController(QObject):
    """Build identify-mode context menu action descriptors."""

    def actions_for_request(
        self, request: IdentifyContextMenuRequest
    ) -> tuple[ContextMenuActionDescriptor, ...]:
        """Build typed context menu action descriptors.

        Args:
            request: Identify context menu request state.

        Returns:
            Context menu descriptors consumed by the spectrum surface.
        """
        actions = build_identify_context_menu_actions(
            state=IdentifyContextMenuState(
                preview_lock_enabled=request.preview_lock_enabled,
                preview_lock_available=request.preview_lock_available,
                baseline_line_selected=request.baseline_line_selected,
            ),
            messages=IdentifyContextMenuMessages(
                always_show_candidate_overlay=self.tr("Always show candidate overlay"),
                show_velocity_plot=self.tr("Show Velocity Plot (V)"),
                baseline_required=self.tr(
                    "Select a baseline line before opening the velocity plot."
                ),
            ),
        )
        return tuple(
            self._to_context_menu_action(action, wavelength=request.wavelength)
            for action in actions
        )

    def _to_context_menu_action(
        self, action: IdentifyContextMenuAction, *, wavelength: float
    ) -> ContextMenuActionDescriptor:
        """Convert an identify action descriptor to a GUI context menu descriptor."""
        match action.kind:
            case IdentifyContextMenuActionKind.TOGGLE_PREVIEW_LOCK:
                return ContextMenuToggleAction(
                    label=action.label,
                    enabled=action.enabled,
                    checked=action.checked,
                    intent_when_checked=ToggleIdentifyPreviewLockIntent(enabled=True),
                    intent_when_unchecked=ToggleIdentifyPreviewLockIntent(enabled=False),
                )
            case IdentifyContextMenuActionKind.TOGGLE_VELOCITY_PLOT:
                return ContextMenuTriggerAction(
                    label=action.label,
                    enabled=action.enabled,
                    tooltip=action.tooltip,
                    intent=(
                        ToggleVelocityPlotIntent(wavelength=wavelength) if action.enabled else None
                    ),
                )
