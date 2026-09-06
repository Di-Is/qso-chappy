"""Protocols for spectrum velocity shortcut integration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VelocityInteractionProvider(Protocol):
    """Provide velocity shortcut handling."""

    def trigger_velocity_shortcut(self) -> bool:
        """Toggle velocity pending mode via a global shortcut.

        Returns:
            True when the request was handled.
        """
        ...
