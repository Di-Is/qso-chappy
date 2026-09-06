"""Tests for rectangle zoom input orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from chappy.gui.spectrum.interaction.input.controllers.rect_zoom_input_controller import (
    RectZoomInputController,
)
from chappy.presentation.interaction.interaction_contracts import (
    InteractionChannel,
    InteractionEvent,
    InteractionEventKind,
    InteractionPhase,
)


@dataclass
class _RectZoomStateControllerFake:
    """Record rectangle zoom interaction events."""

    processed_events: list[InteractionEvent] = field(default_factory=list)
    cancel_reasons: list[str | None] = field(default_factory=list)
    cancel_result: bool = True

    @property
    def phase(self) -> InteractionPhase:
        """Return a stable phase for the controller port."""
        return InteractionPhase.IDLE

    def process_event(self, event: InteractionEvent) -> bool:
        """Record a processed interaction event."""
        self.processed_events.append(event)
        return True

    def cancel_interaction(self, *, reason: str | None) -> bool:
        """Record a cancellation request."""
        self.cancel_reasons.append(reason)
        return self.cancel_result


@dataclass
class _RectZoomOwnerFake:
    """Owner fake for rectangle zoom input tests."""

    controller: _RectZoomStateControllerFake = field(default_factory=_RectZoomStateControllerFake)
    active_channel: InteractionChannel | None = None
    cursor_states: list[bool] = field(default_factory=list)
    acquired_count: int = 0
    cleared_count: int = 0

    def require_rect_zoom_controller(self) -> _RectZoomStateControllerFake:
        """Return the rectangle zoom state controller."""
        return self.controller

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the currently active channel."""
        return self.active_channel

    def acquire_rect_zoom(self) -> None:
        """Acquire rectangle zoom ownership."""
        self.active_channel = InteractionChannel.RECT_ZOOM
        self.acquired_count += 1

    def clear_rect_zoom(self) -> None:
        """Clear rectangle zoom ownership if it is active."""
        if self.active_channel is InteractionChannel.RECT_ZOOM:
            self.active_channel = None
        self.cleared_count += 1

    def set_rect_zoom_cursor(self, active: bool) -> None:
        """Record cursor feedback."""
        self.cursor_states.append(active)


def test_enable_acquires_channel_and_crosshair_cursor() -> None:
    """Enable should arm rectangle zoom input without starting a drag."""
    owner = _RectZoomOwnerFake()
    controller = RectZoomInputController(owner=owner)

    controller.set_mode_enabled(True)

    assert owner.active_channel is InteractionChannel.RECT_ZOOM
    assert owner.acquired_count == 1
    assert owner.cursor_states == [True]
    assert owner.controller.processed_events == []


def test_enable_is_ignored_when_another_channel_is_active() -> None:
    """Enable should not replace another active input channel."""
    owner = _RectZoomOwnerFake(active_channel=InteractionChannel.MASK_SELECTION)
    controller = RectZoomInputController(owner=owner)

    controller.set_mode_enabled(True)

    assert owner.active_channel is InteractionChannel.MASK_SELECTION
    assert owner.acquired_count == 0
    assert owner.cursor_states == []


def test_disable_cancels_only_when_rect_zoom_is_active() -> None:
    """Disable should preserve unrelated active channels."""
    owner = _RectZoomOwnerFake(active_channel=InteractionChannel.MASK_SELECTION)
    controller = RectZoomInputController(owner=owner)

    handled = controller.cancel_interaction(reason="mode-switch")

    assert handled is False
    assert owner.active_channel is InteractionChannel.MASK_SELECTION
    assert owner.controller.cancel_reasons == []
    assert owner.cursor_states == []


def test_cancel_clears_rect_zoom_and_restores_cursor() -> None:
    """Cancel should clear rect zoom ownership and restore the cursor."""
    owner = _RectZoomOwnerFake(active_channel=InteractionChannel.RECT_ZOOM)
    controller = RectZoomInputController(owner=owner)

    handled = controller.cancel_interaction(reason="mode-switch")

    assert handled is True
    assert owner.active_channel is None
    assert owner.cleared_count == 1
    assert owner.controller.cancel_reasons == ["mode-switch"]
    assert owner.cursor_states == [False]


def test_begin_update_complete_emit_rect_zoom_events() -> None:
    """Gesture methods should send typed rectangle zoom events."""
    owner = _RectZoomOwnerFake(active_channel=InteractionChannel.RECT_ZOOM)
    controller = RectZoomInputController(owner=owner)

    assert controller.begin_interaction((4000.0, 0.5), 0) is True
    assert controller.update_interaction((4500.0, 0.6), 1) is True
    assert controller.complete_interaction((5000.0, 0.7), 2) is True

    events = owner.controller.processed_events
    assert [event.kind for event in events] == [
        InteractionEventKind.RECT_ZOOM_BEGIN,
        InteractionEventKind.RECT_ZOOM_UPDATE,
        InteractionEventKind.RECT_ZOOM_COMPLETE,
    ]
    assert [event.position for event in events] == [(4000.0, 0.5), (4500.0, 0.6), (5000.0, 0.7)]
    assert [event.modifiers for event in events] == [0, 1, 2]
