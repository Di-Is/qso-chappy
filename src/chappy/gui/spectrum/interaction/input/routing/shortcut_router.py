"""Route keyboard shortcuts to typed spectrum interaction commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from chappy.presentation.interaction.interaction_contracts import InteractionChannel

if TYPE_CHECKING:
    from chappy.gui.protocols.intent_types import SpectrumInteractionIntent
    from chappy.gui.spectrum.interaction.input.mapping.qt_input_mapper import KeyMouseIntentMapper


@dataclass(frozen=True, slots=True)
class EmitShortcutIntent:
    """Command to emit a typed spectrum interaction intent."""

    intent: SpectrumInteractionIntent


@dataclass(frozen=True, slots=True)
class CancelRectZoom:
    """Command to cancel rectangle zoom before another shortcut proceeds."""

    reason: str


@dataclass(frozen=True, slots=True)
class RouteModeVelocityShortcut:
    """Command to route a raw velocity shortcut to the active mode owner."""


type ShortcutCommand = EmitShortcutIntent | CancelRectZoom | RouteModeVelocityShortcut


@dataclass(frozen=True, slots=True)
class KeyRouteState:
    """State required to route a keyboard shortcut."""

    identify_velocity_shortcut_enabled: bool
    mode_velocity_shortcut_enabled: bool
    active_channel: InteractionChannel | None


@dataclass(frozen=True, slots=True)
class KeyRouteResult:
    """Result of routing a keyboard shortcut."""

    handled: bool
    commands: tuple[ShortcutCommand, ...] = ()


class SpectrumShortcutRouter:
    """Translate key inputs and interaction state to typed commands."""

    def __init__(
        self, *, mapper: KeyMouseIntentMapper, zoom_modifiers: tuple[Qt.KeyboardModifier, ...]
    ) -> None:
        """Initialize the router.

        Args:
            mapper: Low-level Qt key mapper.
            zoom_modifiers: Modifiers accepted for zoom shortcuts.
        """
        self._mapper = mapper
        self._zoom_modifiers = zoom_modifiers

    def route_key(
        self, *, key: int, modifiers: Qt.KeyboardModifier, state: KeyRouteState
    ) -> KeyRouteResult:
        """Route a key event to commands."""
        zoom_intent = self._mapper.zoom_key_intent(key, modifiers, self._zoom_modifiers)
        if zoom_intent is not None:
            return KeyRouteResult(True, (EmitShortcutIntent(zoom_intent),))

        if state.identify_velocity_shortcut_enabled and key == Qt.Key.Key_V:
            return self._route_identify_velocity_key(state=state)

        if (
            state.mode_velocity_shortcut_enabled
            and key == Qt.Key.Key_V
            and modifiers == Qt.KeyboardModifier.NoModifier
        ):
            if state.active_channel is not None:
                return KeyRouteResult(False)
            return KeyRouteResult(True, (RouteModeVelocityShortcut(),))

        if modifiers == Qt.KeyboardModifier.ControlModifier and key in (
            Qt.Key.Key_A,
            Qt.Key.Key_D,
        ):
            return KeyRouteResult(False)

        intent = self._mapper.navigation_key_intent(key)
        if intent is None:
            return KeyRouteResult(False)
        return KeyRouteResult(True, (EmitShortcutIntent(intent),))

    def _route_identify_velocity_key(self, *, state: KeyRouteState) -> KeyRouteResult:
        """Route the identify-mode velocity shortcut."""
        commands: list[ShortcutCommand] = []
        if state.active_channel is InteractionChannel.RECT_ZOOM:
            commands.append(CancelRectZoom(reason="velocity-toggle"))
        elif state.active_channel is not None:
            return KeyRouteResult(True)

        commands.append(RouteModeVelocityShortcut())

        return KeyRouteResult(True, tuple(commands))
