"""Execute routed spectrum interaction commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from chappy.gui.spectrum.interaction.input.routing.click_router import (
    BeginRectZoom,
    CancelMaskSelection,
    ClickCommand,
    RouteModeClick,
    ShowContextMenu,
)
from chappy.gui.spectrum.interaction.input.routing.shortcut_router import (
    CancelRectZoom,
    EmitShortcutIntent,
    RouteModeVelocityShortcut,
    ShortcutCommand,
)
from chappy.gui.spectrum.interaction.input.routing.wheel_router import (
    EmitWheelIntent,
    WheelCommand,
)

if TYPE_CHECKING:
    from chappy.gui.protocols.intent_types import SpectrumInteractionIntent


class SpectrumInteractionCommandPort(Protocol):
    """Operations required to execute routed interaction commands."""

    def emit_interaction_intent(self, intent: SpectrumInteractionIntent) -> None:
        """Emit a typed spectrum interaction intent."""
        ...

    def cancel_rect_zoom_interaction(self, *, reason: str) -> bool:
        """Cancel the rectangle zoom interaction."""
        ...

    def emit_mode_velocity_shortcut(self) -> None:
        """Route a velocity shortcut to the active mode owner."""
        ...

    def emit_mode_click(self, position: tuple[float, float], modifiers: int) -> None:
        """Route a raw mode click to the active mode owner."""
        ...

    def cancel_mask_selection(self, *, reason: str) -> bool:
        """Cancel mask selection."""
        ...

    def begin_rect_zoom_interaction(self, position: tuple[float, float], modifiers: int) -> None:
        """Begin rectangle zoom interaction."""
        ...

    def show_context_menu(self, position: tuple[float, float]) -> bool:
        """Show the spectrum context menu."""
        ...


class SpectrumInteractionCommandExecutor:
    """Execute click, shortcut, and wheel commands."""

    def __init__(self, *, port: SpectrumInteractionCommandPort) -> None:
        """Initialize the executor."""
        self._port = port

    def execute_shortcut_commands(self, commands: tuple[ShortcutCommand, ...]) -> None:
        """Execute routed keyboard shortcut commands in order."""
        for command in commands:
            if isinstance(command, EmitShortcutIntent):
                self._port.emit_interaction_intent(command.intent)
            elif isinstance(command, CancelRectZoom):
                self._port.cancel_rect_zoom_interaction(reason=command.reason)
            elif isinstance(command, RouteModeVelocityShortcut):
                self._port.emit_mode_velocity_shortcut()

    def execute_click_commands(self, commands: tuple[ClickCommand, ...]) -> None:
        """Execute routed click commands in order."""
        for command in commands:
            if isinstance(command, RouteModeClick):
                self._port.emit_mode_click(command.position, command.modifiers)
            elif isinstance(command, CancelMaskSelection):
                self._port.cancel_mask_selection(reason=command.reason)
            elif isinstance(command, BeginRectZoom):
                self._port.begin_rect_zoom_interaction(command.position, command.modifiers)
            elif isinstance(command, ShowContextMenu):
                self._port.show_context_menu(command.position)

    def execute_wheel_commands(self, commands: tuple[WheelCommand, ...]) -> None:
        """Execute routed wheel commands in order."""
        for command in commands:
            if isinstance(command, EmitWheelIntent):
                self._port.emit_interaction_intent(command.intent)
