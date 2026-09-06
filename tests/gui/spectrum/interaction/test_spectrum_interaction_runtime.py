"""Tests for spectrum interaction runtime command execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from chappy.gui.protocols.intent_types import ZoomFactorIntent
from chappy.gui.spectrum.interaction.input.spectrum_interaction_runtime import (
    SpectrumInteractionRuntime,
)


@dataclass
class _RectZoomInputControllerFake:
    """Record rectangle zoom runtime calls."""

    cancel_reasons: list[str] = field(default_factory=list)
    begin_calls: list[tuple[tuple[float, float], int]] = field(default_factory=list)

    def cancel_interaction(self, *, reason: str) -> bool:
        """Record cancellation."""
        self.cancel_reasons.append(reason)
        return True

    def begin_interaction(self, position: tuple[float, float], modifiers: int) -> bool:
        """Record begin interaction."""
        self.begin_calls.append((position, modifiers))
        return True


@dataclass
class _MaskSelectionInputControllerFake:
    """Record mask selection runtime calls."""

    cancel_reasons: list[str | None] = field(default_factory=list)

    def cancel_interaction(self, *, reason: str | None = None) -> bool:
        """Record cancellation."""
        self.cancel_reasons.append(reason)
        return True


def test_runtime_delegates_command_port_operations() -> None:
    """Runtime should delegate command operations to focused collaborators."""
    emitted_intents: list[object] = []
    mode_velocity_shortcuts: list[bool] = []
    mode_clicks: list[tuple[tuple[float, float], int]] = []
    rect_zoom = _RectZoomInputControllerFake()
    mask = _MaskSelectionInputControllerFake()
    runtime = SpectrumInteractionRuntime(
        intent_emitter=emitted_intents.append,
        mode_velocity_shortcut_emitter=lambda: mode_velocity_shortcuts.append(True),
        mode_click_emitter=lambda position, modifiers: mode_clicks.append((position, modifiers)),
        rect_zoom_input_controller=rect_zoom,
        mask_selection_input_controller=mask,
    )

    runtime.emit_interaction_intent(ZoomFactorIntent(factor=1.2))
    assert runtime.cancel_rect_zoom_interaction(reason="test") is True
    runtime.emit_mode_velocity_shortcut()
    runtime.emit_mode_click((5200.0, 0.8), 2)
    assert runtime.cancel_mask_selection(reason="escape-key") is True
    runtime.begin_rect_zoom_interaction((4000.0, 0.5), 4)

    assert isinstance(emitted_intents[0], ZoomFactorIntent)
    assert rect_zoom.cancel_reasons == ["test"]
    assert rect_zoom.begin_calls == [((4000.0, 0.5), 4)]
    assert mode_velocity_shortcuts == [True]
    assert mode_clicks == [((5200.0, 0.8), 2)]
    assert mask.cancel_reasons == ["escape-key"]
