"""Tests for spectrum input command routers."""

from __future__ import annotations

from PySide6.QtCore import Qt

from chappy.gui.spectrum.interaction.input.mapping.qt_input_mapper import KeyMouseIntentMapper
from chappy.gui.spectrum.interaction.input.routing.click_router import (
    ClickRouteState,
    RouteModeClick,
    SpectrumClickRouter,
)
from chappy.gui.spectrum.interaction.input.routing.shortcut_router import (
    KeyRouteState,
    RouteModeVelocityShortcut,
    SpectrumShortcutRouter,
)
from chappy.presentation.interaction.interaction_contracts import InteractionChannel


def test_shortcut_router_uses_identify_velocity_capability() -> None:
    """Identify velocity shortcut behavior should not require editing mode state."""
    router = SpectrumShortcutRouter(
        mapper=KeyMouseIntentMapper(), zoom_modifiers=(Qt.KeyboardModifier.ControlModifier,)
    )

    result = router.route_key(
        key=int(Qt.Key.Key_V),
        modifiers=Qt.KeyboardModifier.NoModifier,
        state=KeyRouteState(
            identify_velocity_shortcut_enabled=True,
            mode_velocity_shortcut_enabled=False,
            active_channel=None,
        ),
    )

    assert result.handled is True
    assert result.commands == (RouteModeVelocityShortcut(),)


def test_shortcut_router_uses_mode_velocity_capability() -> None:
    """Mode-owned velocity shortcut should be controlled by capability state."""
    router = SpectrumShortcutRouter(
        mapper=KeyMouseIntentMapper(), zoom_modifiers=(Qt.KeyboardModifier.ControlModifier,)
    )

    result = router.route_key(
        key=int(Qt.Key.Key_V),
        modifiers=Qt.KeyboardModifier.NoModifier,
        state=KeyRouteState(
            identify_velocity_shortcut_enabled=False,
            mode_velocity_shortcut_enabled=True,
            active_channel=None,
        ),
    )

    assert result.handled is True
    assert result.commands == (RouteModeVelocityShortcut(),)


def test_click_router_uses_mode_click_capabilities() -> None:
    """Mode click routing should be selected by explicit capability flags."""
    router = SpectrumClickRouter()
    shift_mask = KeyMouseIntentMapper.modifier_mask(Qt.KeyboardModifier.ShiftModifier)

    identify_result = router.route_click(
        position=(1215.0, 0.8),
        button="left",
        modifiers=0,
        state=ClickRouteState(
            identify_click_enabled=True, optimize_shift_click_enabled=False, active_channel=None
        ),
    )
    optimize_result = router.route_click(
        position=(1215.0, 0.8),
        button="left",
        modifiers=shift_mask,
        state=ClickRouteState(
            identify_click_enabled=False, optimize_shift_click_enabled=True, active_channel=None
        ),
    )
    blocked_result = router.route_click(
        position=(1215.0, 0.8),
        button="left",
        modifiers=shift_mask,
        state=ClickRouteState(
            identify_click_enabled=False,
            optimize_shift_click_enabled=True,
            active_channel=InteractionChannel.RECT_ZOOM,
        ),
    )

    assert any(isinstance(command, RouteModeClick) for command in identify_result.commands)
    assert any(isinstance(command, RouteModeClick) for command in optimize_result.commands)
    assert blocked_result.handled is True
    assert not any(isinstance(command, RouteModeClick) for command in blocked_result.commands)
