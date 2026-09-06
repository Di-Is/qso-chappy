"""Input-side controller for velocity shortcut requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.presentation.interaction.interaction_contracts import InteractionChannel

if TYPE_CHECKING:
    import logging

    from chappy.gui.spectrum.interaction.input.owner_ports import (
        VelocityShortcutModeCapabilities,
        VelocityShortcutOwnerPort,
    )


class VelocityShortcutInputController:
    """Handle global velocity shortcut requests using input capabilities."""

    def __init__(
        self,
        *,
        owner: VelocityShortcutOwnerPort,
        mode_capabilities: VelocityShortcutModeCapabilities,
        logger: logging.Logger,
    ) -> None:
        """Initialize the controller."""
        self._owner = owner
        self._mode_capabilities = mode_capabilities
        self._logger = logger

    def trigger_velocity_shortcut(self) -> bool:
        """Route a velocity request according to active mode and channel ownership."""
        if self._mode_capabilities.detail_velocity_shortcut_enabled():
            return self._trigger_mode_velocity_shortcut()

        if not self._mode_capabilities.identify_velocity_shortcut_enabled():
            self._logger.debug("Velocity shortcut ignored outside identify/optimize mode")
            return False

        return self._trigger_identify_velocity_shortcut()

    def _trigger_mode_velocity_shortcut(self) -> bool:
        """Route the shortcut to a mode owner when channel state allows it."""
        active_channel = self._owner.active_input_channel()
        if active_channel is not None:
            self._logger.debug(
                "Velocity shortcut ignored due to active channel (OPTIMIZE mode)",
                extra={"channel": active_channel},
            )
            return False
        self._owner.emit_mode_velocity_shortcut()
        return True

    def _trigger_identify_velocity_shortcut(self) -> bool:
        """Route Identify velocity after enforcing shared channel ownership."""
        active_channel = self._owner.active_input_channel()
        if active_channel is InteractionChannel.RECT_ZOOM:
            self._owner.cancel_rect_zoom_interaction(reason="velocity-shortcut")
        elif active_channel is not None:
            self._logger.debug(
                "Velocity shortcut ignored due to active channel",
                extra={"channel": active_channel},
            )
            return False

        self._owner.emit_mode_velocity_shortcut()
        return True
