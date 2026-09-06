"""Behavior tests for SpectrumInputAdapter channel mutual exclusion."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import cast

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt

from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.modes.continuum.controllers.interaction_controller import (
    ContinuumInteractionController,
)
from chappy.gui.modes.continuum.controllers.interaction_state_controller import (
    ContinuumStateController,
)
from chappy.gui.spectrum.interaction.support.logging import InteractionLogEmitter
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumPointPayload,
    ContinuumContext,
    InteractionChannel,
    InteractionEvent,
    InteractionEventKind,
    InteractionPhase,
    InteractionStateSnapshot,
    MaskSelectionContext,
    MaskSelectionRequest,
    RectZoomContext,
)
from chappy.gui.spectrum.interaction.input.ports import (
    ContinuumInteractionEventSink,
    SpectrumInputAdapterEventSink,
    SpectrumInputAdapterViewPort,
    VelocityDragSignalPort,
)
from chappy.gui.spectrum.interaction.input.spectrum_input_adapter import SpectrumInputAdapter
from chappy.presentation.velocity import VelocityDragComplete, VelocityDragRequest

Snapshot = InteractionStateSnapshot[
    RectZoomContext | AbsorberDragContext | MaskSelectionContext | ContinuumContext
]


class _Signal:
    """Small callback signal used by velocity view fakes."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[[object], None]] = []

    def connect(self, callback: Callable[[object], None]) -> object:
        """Register a callback."""
        self._callbacks.append(callback)
        return None

    def emit(self, payload: object) -> None:
        """Notify all registered callbacks."""
        for callback in list(self._callbacks):
            callback(payload)


class _VelocityView:
    """Velocity view fake exposing only drag signals."""

    def __init__(self) -> None:
        self.sig_velocity_drag_requested = _Signal()
        self.sig_velocity_drag_update = _Signal()
        self.sig_velocity_drag_complete = _Signal()


class _SpectrumPlot:
    """Record cursor updates requested by the interactor."""

    def __init__(self) -> None:
        self.cursor: Qt.CursorShape | None = None
        self.canvas = _Canvas()
        self.renderer = _Renderer()
        self.mouse_input: SpectrumInputAdapterEventSink | None = None
        self.continuum_input: ContinuumInteractionEventSink | None = None
        self._continuum_points: list[tuple[float, float]] = []

    def setCursor(self, cursor: Qt.CursorShape) -> None:
        """Record the latest cursor shape."""
        self.cursor = cursor

    def set_input_ports(
        self,
        *,
        mouse: SpectrumInputAdapterEventSink | None,
        continuum: ContinuumInteractionEventSink | None,
    ) -> None:
        """Record the attached input ports."""
        self.mouse_input = mouse
        self.continuum_input = continuum

    def continuum_points(self) -> list[tuple[float, float]]:
        """Return configured continuum points."""
        return list(self._continuum_points)

    def set_continuum_points(self, points: list[tuple[float, float]]) -> None:
        """Configure continuum points returned by the plot."""
        self._continuum_points = points

    def get_absorber_at_position(self, _wavelength: float) -> str | None:
        """Return no absorber by default."""
        return None

    def mapFromGlobal(self, _position: QPoint) -> QPointF:  # noqa: N802
        """Map global cursor position to a deterministic local coordinate."""
        return QPointF(10.0, 20.0)


class _Canvas:
    """Small canvas surface for coordinate transforms."""

    def devicePixelRatio(self) -> float:  # noqa: N802
        """Return a stable device pixel ratio."""
        return 1.0

    def height(self) -> int:
        """Return a stable canvas height."""
        return 100

    def width(self) -> int:
        """Return a stable canvas width."""
        return 100


class _Transform:
    """Identity transform for plot test coordinates."""

    def transform(self, position: tuple[float, float]) -> tuple[float, float]:
        """Return the display coordinate as a data coordinate."""
        return position


class _InvertedTransform:
    """Transform provider matching the matplotlib API shape."""

    def inverted(self) -> _Transform:
        """Return a transform object."""
        return _Transform()


class _Axes:
    """Axes fake exposing transData."""

    transData = _InvertedTransform()


class _Renderer:
    """Renderer fake exposing axes."""

    axes = _Axes()


class _SpectrumView:
    """Minimal typed view double for SpectrumInputAdapter."""

    def __init__(self) -> None:
        self.coordinator: object | None = None
        self.spectrum_plot = _SpectrumPlot()

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return a stable wavelength range."""
        return (4000.0, 5000.0)


@dataclass
class _SnapshotRecorder:
    """Collect interaction snapshots emitted by SpectrumInputAdapter."""

    snapshots: list[Snapshot] = field(default_factory=list)

    def append(self, snapshot: Snapshot) -> None:
        """Store an emitted snapshot."""
        self.snapshots.append(snapshot)

    def phases_for(self, channel: InteractionChannel) -> list[InteractionPhase]:
        """Return phases emitted for a channel."""
        return [snapshot.phase for snapshot in self.snapshots if snapshot.channel is channel]


@dataclass
class _InteractorHarness:
    """Interactor plus observable collaborators used by channel tests."""

    interactor: SpectrumInputAdapter
    view: _SpectrumView
    velocity_view: _VelocityView
    snapshots: _SnapshotRecorder


@pytest.fixture
def harness() -> Iterator[_InteractorHarness]:
    """Create a SpectrumInputAdapter wired to typed fakes."""
    view = _SpectrumView()
    interactor = SpectrumInputAdapter(view=cast(SpectrumInputAdapterViewPort, view))
    interactor.set_mode_capabilities(
        analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
    )
    velocity_view = _VelocityView()
    interactor.connect_velocity_view(cast(VelocityDragSignalPort, velocity_view))
    continuum_controller = ContinuumInteractionController(
        log_emitter=InteractionLogEmitter(channel=InteractionChannel.CONTINUUM),
        current_points=interactor.current_continuum_points,
    )
    interactor.set_continuum_interaction_controller(
        ContinuumStateController(
            snapshot_consumer=interactor.consume_interaction_snapshot,
            continuum_interaction_controller=continuum_controller,
        )
    )
    snapshots = _SnapshotRecorder()
    interactor.sig_interaction_snapshot.connect(snapshots.append)

    yield _InteractorHarness(
        interactor=interactor, view=view, velocity_view=velocity_view, snapshots=snapshots
    )


def _mask_request() -> MaskSelectionRequest:
    """Create a mask selection request."""
    return MaskSelectionRequest(
        selection_mode="create",
        group_id="test_group",
        mask_id=None,
        initial_range=None,
        existing_mask=None,
    )


def _continuum_move_begin() -> InteractionEvent:
    """Create a continuum move-begin event that remains cancellable."""
    return InteractionEvent(
        channel=InteractionChannel.CONTINUUM,
        kind=InteractionEventKind.CONTINUUM_MOVE_BEGIN,
        position=(4500.0, 0.5),
        payload=ContinuumPointPayload(point_index=0),
    )


def _send_continuum_event(harness: _InteractorHarness, event: InteractionEvent) -> bool:
    """Send a continuum interaction event through channel-guarded controller routing."""
    if not harness.interactor.can_process_continuum_event():
        return False

    return harness.interactor.process_continuum_interaction_event(event)


def _attach_plot(harness: _InteractorHarness) -> _SpectrumPlot:
    """Attach the spectrum plot through the public interactor boundary."""
    harness.interactor.attach_plot_widget(harness.view.spectrum_plot)
    return harness.view.spectrum_plot


def _cancel_continuum_event(harness: _InteractorHarness, reason: str | None = None) -> bool:
    """Cancel an active continuum interaction through the registered controller."""
    return harness.interactor.cancel_continuum_interaction(reason=reason)


def _begin_absorber_drag(harness: _InteractorHarness) -> None:
    """Start an absorber drag through connected velocity-view signals."""
    harness.velocity_view.sig_velocity_drag_requested.emit(
        VelocityDragRequest("test_absorber", 0.0, 1215.67, 0.5, 1.0)
    )


def _complete_absorber_drag(harness: _InteractorHarness) -> None:
    """Complete an absorber drag through connected velocity-view signals."""
    harness.velocity_view.sig_velocity_drag_complete.emit(
        VelocityDragComplete("test_absorber", 25.0, 1215.67, 0.5, 1.0)
    )


def test_current_continuum_points_require_attached_plot(harness: _InteractorHarness) -> None:
    """Continuum point lookup should fail fast before plot widget attachment."""
    with pytest.raises(RuntimeError, match="Plot widget is required"):
        harness.interactor.current_continuum_points()


def test_current_continuum_points_use_typed_plot_provider(harness: _InteractorHarness) -> None:
    """Continuum point lookup should use the plot provider instead of dynamic attrs."""
    points = [(4000.0, 1.0), (4500.0, 0.9)]
    plot = _attach_plot(harness)
    plot.set_continuum_points(points)

    assert harness.interactor.current_continuum_points() == points


def test_mask_selection_requires_state_controller(harness: _InteractorHarness) -> None:
    """Mask selection should fail fast when the state controller is missing."""
    harness.interactor._mask_state_controller = None  # noqa: SLF001 - invariant test

    with pytest.raises(RuntimeError, match="Mask selection state controller is required"):
        harness.interactor.begin_mask_selection_interaction(_mask_request())


def test_mask_selection_cancel_requires_state_controller(harness: _InteractorHarness) -> None:
    """Mask selection cancellation should fail fast when the state controller is missing."""
    harness.interactor._mask_state_controller = None  # noqa: SLF001 - invariant test

    with pytest.raises(RuntimeError, match="Mask selection state controller is required"):
        harness.interactor.cancel_mask_selection_interaction(reason="test")


class TestActiveChannelBlocksCompetingStarts:
    """Active interactions reject competing channel starts."""

    def test_mask_selection_keeps_rect_zoom_and_absorber_drag_inactive(
        self, harness: _InteractorHarness
    ) -> None:
        """Mask selection blocks rectangle zoom and absorber drag starts."""
        assert harness.interactor.begin_mask_selection_interaction(_mask_request()) is True

        harness.interactor.set_rect_zoom_mode(True)
        _begin_absorber_drag(harness)

        assert not harness.interactor.is_rect_zoom_mode_enabled()
        assert InteractionChannel.ABSORBER_DRAG not in {
            snapshot.channel for snapshot in harness.snapshots.snapshots
        }
        assert harness.interactor.can_process_continuum_event() is False

    def test_rect_zoom_keeps_mask_absorber_and_continuum_inactive(
        self, harness: _InteractorHarness
    ) -> None:
        """Rectangle zoom blocks mask selection, absorber drag, and continuum starts."""
        harness.interactor.set_rect_zoom_mode(True)

        mask_started = harness.interactor.begin_mask_selection_interaction(_mask_request())
        _begin_absorber_drag(harness)
        continuum_started = _send_continuum_event(harness, _continuum_move_begin())

        assert harness.interactor.is_rect_zoom_mode_enabled()
        assert mask_started is False
        assert continuum_started is False
        assert InteractionChannel.ABSORBER_DRAG not in {
            snapshot.channel for snapshot in harness.snapshots.snapshots
        }

    def test_absorber_drag_keeps_mask_rect_zoom_and_continuum_inactive(
        self, harness: _InteractorHarness
    ) -> None:
        """Absorber drag blocks mask selection, rectangle zoom, and continuum starts."""
        _begin_absorber_drag(harness)

        mask_started = harness.interactor.begin_mask_selection_interaction(_mask_request())
        harness.interactor.set_rect_zoom_mode(True)
        continuum_started = _send_continuum_event(harness, _continuum_move_begin())

        assert InteractionPhase.ARMED in harness.snapshots.phases_for(
            InteractionChannel.ABSORBER_DRAG
        )
        assert mask_started is False
        assert not harness.interactor.is_rect_zoom_mode_enabled()
        assert continuum_started is False

    def test_continuum_keeps_rect_zoom_mask_and_absorber_drag_inactive(
        self, harness: _InteractorHarness
    ) -> None:
        """Continuum editing blocks rectangle zoom, mask selection, and absorber drag starts."""
        assert _send_continuum_event(harness, _continuum_move_begin())

        harness.interactor.set_rect_zoom_mode(True)
        mask_started = harness.interactor.begin_mask_selection_interaction(_mask_request())
        _begin_absorber_drag(harness)

        assert InteractionPhase.ARMED in harness.snapshots.phases_for(InteractionChannel.CONTINUUM)
        assert not harness.interactor.is_rect_zoom_mode_enabled()
        assert mask_started is False
        assert InteractionChannel.ABSORBER_DRAG not in {
            snapshot.channel for snapshot in harness.snapshots.snapshots
        }


class TestCompletionAllowsNewChannel:
    """Completed or cancelled interactions release the channel."""

    def test_cancelled_mask_selection_allows_rect_zoom(self, harness: _InteractorHarness) -> None:
        """Cancelling mask selection lets rectangle zoom start."""
        _attach_plot(harness)
        assert harness.interactor.begin_mask_selection_interaction(_mask_request()) is True

        harness.interactor.cancel_mask_selection_interaction(reason="test")
        harness.interactor.set_rect_zoom_mode(True)

        assert harness.interactor.is_rect_zoom_mode_enabled()
        assert harness.view.spectrum_plot.cursor is Qt.CursorShape.CrossCursor

    def test_disabled_rect_zoom_allows_mask_selection(self, harness: _InteractorHarness) -> None:
        """Disabling rectangle zoom lets mask selection start."""
        _attach_plot(harness)
        harness.interactor.set_rect_zoom_mode(True)
        harness.interactor.set_rect_zoom_mode(False)

        assert harness.interactor.begin_mask_selection_interaction(_mask_request()) is True
        assert not harness.interactor.is_rect_zoom_mode_enabled()
        assert harness.view.spectrum_plot.cursor is Qt.CursorShape.CrossCursor

    def test_completed_absorber_drag_allows_mask_selection(
        self, harness: _InteractorHarness
    ) -> None:
        """Completing absorber drag lets mask selection start."""
        _begin_absorber_drag(harness)
        _complete_absorber_drag(harness)

        assert InteractionPhase.IDLE in harness.snapshots.phases_for(
            InteractionChannel.ABSORBER_DRAG
        )
        assert harness.interactor.begin_mask_selection_interaction(_mask_request()) is True

    def test_cancelled_continuum_allows_rect_zoom(self, harness: _InteractorHarness) -> None:
        """Cancelling continuum editing lets rectangle zoom start."""
        assert _send_continuum_event(harness, _continuum_move_begin())

        assert _cancel_continuum_event(harness, reason="test")
        harness.interactor.set_rect_zoom_mode(True)

        assert InteractionPhase.CANCELLED in harness.snapshots.phases_for(
            InteractionChannel.CONTINUUM
        )
        assert harness.interactor.is_rect_zoom_mode_enabled()


class TestSameChannelReentry:
    """Same-channel repeated starts are idempotent where supported."""

    def test_mask_selection_can_be_reentered(self, harness: _InteractorHarness) -> None:
        """Starting mask selection twice keeps mask selection available."""
        assert harness.interactor.begin_mask_selection_interaction(_mask_request()) is True
        assert harness.interactor.begin_mask_selection_interaction(_mask_request()) is True

        harness.interactor.set_rect_zoom_mode(True)

        assert not harness.interactor.is_rect_zoom_mode_enabled()

    def test_rect_zoom_can_be_enabled_repeatedly(self, harness: _InteractorHarness) -> None:
        """Enabling rectangle zoom twice remains active without side effects."""
        _attach_plot(harness)
        harness.interactor.set_rect_zoom_mode(True)
        harness.interactor.set_rect_zoom_mode(True)

        assert harness.interactor.is_rect_zoom_mode_enabled()
        assert harness.view.spectrum_plot.cursor is Qt.CursorShape.CrossCursor

    def test_absorber_drag_reentry_does_not_start_a_second_drag(
        self, harness: _InteractorHarness
    ) -> None:
        """Starting absorber drag twice keeps the original drag lifecycle."""
        _begin_absorber_drag(harness)
        _begin_absorber_drag(harness)

        assert (
            harness.snapshots.phases_for(InteractionChannel.ABSORBER_DRAG).count(
                InteractionPhase.ARMED
            )
            == 1
        )
