"""Tests for channel-specific interaction state controller flows."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    AbsorberDragPayload,
    InteractionChannel,
    InteractionEvent,
    InteractionEventKind,
    InteractionPhase,
    InteractionStateSnapshot,
    RectZoomContext,
)
from chappy.gui.spectrum.interaction.channels.absorber_drag.interaction_controller import (
    AbsorberDragInteractionController,
)
from chappy.gui.spectrum.interaction.channels.absorber_drag.state_controller import (
    AbsorberDragStateController,
)
from chappy.gui.spectrum.interaction.support.errors import InteractionStateError
from chappy.gui.spectrum.interaction.support.logging import InteractionLogEmitter
from chappy.gui.spectrum.interaction.channels.rect_zoom.interaction_controller import (
    RectZoomInteractionController,
)
from chappy.gui.spectrum.interaction.channels.rect_zoom.state_controller import (
    RectZoomStateController,
)
from chappy.gui.protocols.intent_types import (
    EndAbsorberDragIntent,
    StartAbsorberDragIntent,
    UpdateAbsorberDragIntent,
    ZoomRectIntent,
)


class _OverlaySpy:
    """Simple overlay spy recording draw and clear operations."""

    def __init__(self) -> None:
        self.draw_calls: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self.clear_count = 0
        self.absorber_drag_calls: list[tuple[str, str, float]] = []

    # RectZoomOverlayProtocol and AbsorberDragOverlayProtocol methods
    def update_rect_zoom(self, start: tuple[float, float], current: tuple[float, float]) -> None:
        """Update the rectangle zoom overlay."""
        self.draw_calls.append((start, current))

    def clear_rect_zoom(self) -> None:
        """Clear the rectangle zoom overlay."""
        self.clear_count += 1

    def begin_absorber_drag(self, absorber_id: str, initial_wavelength: float) -> None:
        """Begin an absorber drag interaction."""
        self.absorber_drag_calls.append((absorber_id, "begin", initial_wavelength))

    def finish_absorber_drag(self, absorber_id: str) -> None:
        """Finish an absorber drag interaction."""
        self.absorber_drag_calls.append((absorber_id, "finish", 0.0))


def _build_controller() -> tuple[
    RectZoomStateController,
    _OverlaySpy,
    list[InteractionStateSnapshot[RectZoomContext]],
    list[ZoomRectIntent],
]:
    overlay = _OverlaySpy()
    overlay_provider: Callable[[], _OverlaySpy] = lambda: overlay
    log_emitter = InteractionLogEmitter(channel=InteractionChannel.RECT_ZOOM)
    rect_controller = RectZoomInteractionController(
        overlay_provider=overlay_provider, log_emitter=log_emitter
    )
    snapshots: list[InteractionStateSnapshot[RectZoomContext]] = []
    intents: list[ZoomRectIntent] = []
    controller = RectZoomStateController(
        snapshot_consumer=lambda snapshot: snapshots.append(snapshot),
        rect_zoom_interaction_controller=rect_controller,
        zoom_intent_emitter=intents.append,
    )
    return controller, overlay, snapshots, intents


def test_rect_zoom_lifecycle_emits_snapshots_and_intent() -> None:
    """Verify that begin/update/complete flows produce snapshots and zoom intent."""
    controller, overlay, snapshots, intents = _build_controller()

    begin_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM,
        kind=InteractionEventKind.RECT_ZOOM_BEGIN,
        position=(4100.0, 0.2),
    )
    update_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM,
        kind=InteractionEventKind.RECT_ZOOM_UPDATE,
        position=(4200.0, 0.25),
    )
    complete_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM,
        kind=InteractionEventKind.RECT_ZOOM_COMPLETE,
        position=(4300.0, 0.3),
    )

    assert controller.process_event(begin_event)
    assert controller.phase is InteractionPhase.ARMED

    assert controller.process_event(update_event)
    assert controller.phase is InteractionPhase.ACTIVE
    assert overlay.draw_calls

    assert controller.process_event(complete_event)
    assert controller.phase is InteractionPhase.IDLE

    assert overlay.clear_count == 1
    assert len(intents) == 1
    zoom_intent = intents[0]
    assert isinstance(zoom_intent, ZoomRectIntent)
    assert zoom_intent.min_wavelength == pytest.approx(4100.0)
    assert zoom_intent.max_wavelength == pytest.approx(4300.0)

    assert len(snapshots) >= 3
    phases = [snapshot.phase for snapshot in snapshots]
    assert phases[-1] is InteractionPhase.IDLE


def test_cancel_without_active_returns_false() -> None:
    """Cancelling with no active interaction should be a no-op."""
    controller, _overlay, snapshots, intents = _build_controller()

    assert not controller.cancel_interaction(reason="noop")
    assert snapshots == []
    assert intents == []


def test_cancel_after_begin_emits_cancel_snapshot() -> None:
    """Cancelling after begin should emit a CANCELLED snapshot."""
    controller, overlay, snapshots, _intents = _build_controller()

    begin_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM,
        kind=InteractionEventKind.RECT_ZOOM_BEGIN,
        position=(4000.0, 0.2),
    )

    controller.process_event(begin_event)
    controller.cancel_interaction(reason="test-cancel")

    assert overlay.clear_count == 1
    assert snapshots[-1].phase is InteractionPhase.CANCELLED


def _build_absorber_controller() -> tuple[
    AbsorberDragStateController, list[InteractionStateSnapshot[AbsorberDragContext]], list[object]
]:
    """Construct an absorber drag controller with spy callbacks."""
    log_emitter = InteractionLogEmitter(channel=InteractionChannel.ABSORBER_DRAG)
    drag_controller = AbsorberDragInteractionController(log_emitter=log_emitter)
    snapshots: list[InteractionStateSnapshot[AbsorberDragContext]] = []
    intents: list[object] = []
    controller = AbsorberDragStateController(
        snapshot_consumer=snapshots.append,
        absorber_drag_interaction_controller=drag_controller,
        absorber_drag_intent_emitter=intents.append,
        absorber_drag_state_tracker=lambda _identifier: None,
    )
    return controller, snapshots, intents


def test_absorber_drag_lifecycle_emits_snapshots_and_intents() -> None:
    """Verify absorber drag begin/update/complete flow."""
    controller, snapshots, intents = _build_absorber_controller()

    begin_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_BEGIN,
        position=(5200.0, 0.2),
        payload=AbsorberDragPayload(absorber_id="abs-1"),
    )
    update_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_UPDATE,
        position=(5210.0, 0.22),
    )
    complete_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_COMPLETE,
        position=(5225.0, 0.25),
    )

    assert controller.process_event(begin_event)
    assert controller.phase is InteractionPhase.ARMED
    assert isinstance(intents[0], StartAbsorberDragIntent)

    assert controller.process_event(update_event)
    assert controller.phase is InteractionPhase.ACTIVE
    assert isinstance(intents[1], UpdateAbsorberDragIntent)

    assert controller.process_event(complete_event)
    assert controller.phase is InteractionPhase.IDLE
    assert isinstance(intents[-1], EndAbsorberDragIntent)

    assert len(snapshots) >= 3
    assert snapshots[-1].phase is InteractionPhase.IDLE
    context = snapshots[-1].context
    assert isinstance(context, AbsorberDragContext)
    assert context.end == (5225.0, 0.25)


def test_absorber_drag_begin_requires_absorber_context() -> None:
    """A drag begin event without a target absorber is an interaction invariant error."""
    controller, _snapshots, _intents = _build_absorber_controller()

    begin_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_BEGIN,
        position=(5200.0, 0.2),
        payload=AbsorberDragPayload(),
    )

    with pytest.raises(InteractionStateError, match="requires an absorber id"):
        controller.process_event(begin_event)


def test_absorber_drag_cancel_emits_cancel_snapshot() -> None:
    """Ensure absorber drag cancellation emits a cancelled snapshot."""
    controller, snapshots, intents = _build_absorber_controller()

    begin_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_BEGIN,
        position=(5300.0, 0.18),
        payload=AbsorberDragPayload(absorber_id="abs-2"),
    )

    controller.process_event(begin_event)
    controller.cancel_interaction(reason="user-cancel")

    assert len(intents) == 1  # Start intent only
    cancel_snapshot = snapshots[-1]
    assert cancel_snapshot.phase is InteractionPhase.CANCELLED
    cancel_context = cancel_snapshot.context
    assert isinstance(cancel_context, AbsorberDragContext)
    assert cancel_context.cancel_reason == "user-cancel"


def test_absorber_drag_cancel_event_uses_reason() -> None:
    """Cancel events should propagate payload reasons."""
    controller, snapshots, _intents = _build_absorber_controller()

    begin_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_BEGIN,
        position=(5400.0, 0.12),
        payload=AbsorberDragPayload(absorber_id="abs-3"),
    )
    controller.process_event(begin_event)

    cancel_event = InteractionEvent(
        channel=InteractionChannel.ABSORBER_DRAG,
        kind=InteractionEventKind.ABSORBER_DRAG_CANCEL,
        payload=AbsorberDragPayload(reason="missing-coordinate"),
    )

    controller.process_event(cancel_event)

    assert snapshots[-1].phase is InteractionPhase.CANCELLED
    assert snapshots[-1].context.cancel_reason == "missing-coordinate"


def test_rect_zoom_cancel_event() -> None:
    """RECT_ZOOM_CANCEL event should cancel active rectangle zoom."""
    controller, overlay, snapshots, intents = _build_controller()

    # Start a rectangle zoom
    begin_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM,
        kind=InteractionEventKind.RECT_ZOOM_BEGIN,
        position=(4100.0, 0.2),
    )
    assert controller.process_event(begin_event)
    assert controller.phase is InteractionPhase.ARMED

    # Cancel with RECT_ZOOM_CANCEL event
    cancel_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM, kind=InteractionEventKind.RECT_ZOOM_CANCEL
    )
    assert controller.process_event(cancel_event)
    assert controller.phase is InteractionPhase.CANCELLED
    assert overlay.clear_count == 1
    assert len(snapshots) >= 2
    assert snapshots[-1].phase is InteractionPhase.CANCELLED


def test_unsupported_event_raises() -> None:
    """Processing an unsupported event kind should fail fast."""
    controller, _overlay, snapshots, _intents = _build_controller()

    # Create an event with an unsupported kind for RECT_ZOOM channel
    # (using a mask selection event kind on rect zoom channel)
    unsupported_event = InteractionEvent(
        channel=InteractionChannel.RECT_ZOOM,
        kind=InteractionEventKind.MASK_SELECTION_BEGIN,
        position=(4100.0, 0.2),
        modifiers=0,
    )

    with pytest.raises(InteractionStateError, match="Unsupported rect zoom interaction event"):
        controller.process_event(unsupported_event)
    assert controller.phase is InteractionPhase.IDLE
    # No snapshots should be emitted for unsupported events
    assert len(snapshots) == 0
