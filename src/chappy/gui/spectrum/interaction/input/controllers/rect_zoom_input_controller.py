"""Input-side controller for rectangle zoom gestures."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from chappy.presentation.interaction.interaction_contracts import (
    InteractionChannel,
    InteractionEvent,
    InteractionEventKind,
)

if TYPE_CHECKING:
    from chappy.gui.spectrum.interaction.input.owner_ports import RectZoomInputOwnerPort

logger = logging.getLogger(__name__)


class RectZoomInputController:
    """Convert rectangle zoom input phases into interaction events."""

    def __init__(self, *, owner: RectZoomInputOwnerPort) -> None:
        """Initialize the controller."""
        self._owner = owner

    def set_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable rectangle zoom input mode."""
        active_channel = self._owner.active_input_channel()
        if enabled and active_channel not in (None, InteractionChannel.RECT_ZOOM):
            logger.warning("Rectangle zoom ignored because channel %s is active", active_channel)
            return

        if enabled:
            self._owner.acquire_rect_zoom()
            self._owner.set_rect_zoom_cursor(True)
            return

        self.cancel_interaction(reason="mode-switch")

    def is_mode_enabled(self) -> bool:
        """Return whether rectangle zoom input mode owns the active channel."""
        return self._owner.active_input_channel() is InteractionChannel.RECT_ZOOM

    def begin_interaction(self, position: tuple[float, float], modifiers: int) -> bool:
        """Begin a rectangle zoom drag."""
        event = InteractionEvent(
            channel=InteractionChannel.RECT_ZOOM,
            kind=InteractionEventKind.RECT_ZOOM_BEGIN,
            position=position,
            modifiers=modifiers,
        )
        return self._owner.require_rect_zoom_controller().process_event(event)

    def update_interaction(self, position: tuple[float, float], modifiers: int) -> bool:
        """Update the active rectangle zoom drag."""
        event = InteractionEvent(
            channel=InteractionChannel.RECT_ZOOM,
            kind=InteractionEventKind.RECT_ZOOM_UPDATE,
            position=position,
            modifiers=modifiers,
        )
        return self._owner.require_rect_zoom_controller().process_event(event)

    def complete_interaction(self, position: tuple[float, float], modifiers: int) -> bool:
        """Complete the active rectangle zoom drag."""
        event = InteractionEvent(
            channel=InteractionChannel.RECT_ZOOM,
            kind=InteractionEventKind.RECT_ZOOM_COMPLETE,
            position=position,
            modifiers=modifiers,
        )
        return self._owner.require_rect_zoom_controller().process_event(event)

    def cancel_interaction(self, *, reason: str) -> bool:
        """Cancel rectangle zoom input mode or an active rectangle zoom drag."""
        if self._owner.active_input_channel() is not InteractionChannel.RECT_ZOOM:
            return False

        self._owner.clear_rect_zoom()
        handled = self._owner.require_rect_zoom_controller().cancel_interaction(reason=reason)
        self._owner.set_rect_zoom_cursor(False)

        logger.debug("Rectangle zoom cancelled", extra={"reason": reason, "handled": handled})
        return True

    def cancel_unresolved_drag(self, *, reason: str) -> bool:
        """Cancel a drag when release coordinates cannot be resolved."""
        return self.cancel_interaction(reason=reason)
