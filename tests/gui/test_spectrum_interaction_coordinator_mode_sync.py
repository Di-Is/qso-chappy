"""Presenter and ModeShellCoordinator snapshot synchronisation tests."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from chappy.core.editing_mode import EditingMode
from chappy.gui.shell.mode_shell_coordinator import ModeShellCoordinator
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    InteractionChannel,
    InteractionId,
    InteractionPhase,
    InteractionStateSnapshot,
    RectZoomContext,
)

if TYPE_CHECKING:
    from chappy.gui.spectrum.policy import SpectrumPolicy


class _StubSpectrumView:
    """Minimal spectrum view that exposes the presenter and reset hook."""

    def __init__(self, presenter: _PresenterStub) -> None:
        self.coordinator = presenter
        self.plot_host = None
        self.reset_cleared = False
        self.start_mode_active = False
        self.current_policy: SpectrumPolicy | None = None
        self.policy_applied = _StubSignal()

    def apply_policy(self, policy: SpectrumPolicy) -> None:
        """Apply transition cleanup, then publish the committed policy."""
        if policy.transition_cleanup.clear_interaction_mode:
            self.coordinator.set_interaction_mode(None)
        if policy.transition_cleanup.clear_reset_ranges:
            self.clear_reset_ranges()
        self.current_policy = policy
        self.policy_applied.emit(policy)

    def clear_reset_ranges(self) -> None:
        """Record that reset ranges are cleared during tests."""
        self.reset_cleared = True

    def set_start_mode_active(self, active: bool) -> None:
        """Record start-mode activation requests."""
        self.start_mode_active = active

    def set_absorption_line_regions(self, regions: list[object]) -> None:
        """Accept line overlay updates required by mode lifecycle tests."""
        return None


class _StubViewHost:
    """Expose a spectrum view and match the real API surface."""

    def __init__(self, presenter: _PresenterStub) -> None:
        self.spectrum_view = _StubSpectrumView(presenter)
        self._mode_state_store = None

    def attach_mode_state_store(self, mode_state_store: _StubModeStateStore) -> None:
        """Store the provided mode state store for completeness."""
        self._mode_state_store = mode_state_store

    def detach_mode_state_store(self) -> None:
        """Clear the provided mode state store for completeness."""
        self._mode_state_store = None


class _StubContinuumCoordinator:
    """Minimal continuum coordinator accepted by continuum lifecycle ports."""

    def set_continuum_visible(self, visible: bool) -> None:
        """Accept semantic continuum visibility updates."""
        return None


class _StubIdentifyModeCoordinator:
    """Minimal identify coordinator accepted by identify lifecycle ports."""

    def build_line_overlay_payload(self, *, include_temporary: bool) -> list[object]:
        """Return no temporary line overlays for lifecycle tests."""
        return []

    def on_mode_changed(self, mode: EditingMode) -> None:
        """Accept identify workflow mode updates."""
        return None


class _StubMainWindow:
    """Provide the minimal attributes required by ModeShellCoordinator."""

    def __init__(self, presenter: _PresenterStub) -> None:
        self.view_stack = _StubViewHost(presenter)
        self.mode_context_bar = None
        self.action_factory = None
        self.continuum_coordinator = _StubContinuumCoordinator()
        self.continuum_editor = None
        self.identify_coordinator = _StubIdentifyModeCoordinator()
        self.status_controller = None
        self.dock_coordinator = None
        self.data_control_panel = None
        self.range_dock = None
        self.current_project = None
        self.identify_velocity_runtime = _IdentifyVelocityRuntime()

    @property
    def confirmed_line_overlay_region_id(self) -> str | None:
        """Keep confirmed overlays unscoped in generic mode-sync tests."""
        return None


class _IdentifyVelocityRuntime:
    """Minimal identify runtime accepted by shell tests."""

    def hide_velocity_plot(self) -> None:
        """Accept velocity overlay hide requests."""
        return None


class _RectZoomInteractorStub:
    """Simple stub that tracks rectangle zoom enable state for tests."""

    def __init__(self) -> None:
        self.enabled = False

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Record the requested rectangle zoom mode."""
        self.enabled = bool(enabled)

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return whether rectangle zoom mode is currently active."""
        return self.enabled

    def set_selected_line_absorbers(self, _absorber_ids: set[str] | None) -> None:
        """Accept selected absorber updates."""


class _StubSignal:
    """Small signal fake."""

    def __init__(self) -> None:
        """Initialize the signal."""
        self._callbacks: list[Callable[..., None]] = []
        self.emissions: list[tuple[object, ...]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Record a callback."""
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., None]) -> None:
        """Remove a previously registered callback."""
        with contextlib.suppress(ValueError):
            self._callbacks.remove(callback)

    def emit(self, *args: object) -> None:
        """Emit a payload to connected callbacks."""
        self.emissions.append(args)
        for callback in list(self._callbacks):
            callback(*args)


class _StubDataBridge:
    """Small data bridge fake."""

    def __init__(self) -> None:
        """Initialize the bridge."""
        self.project = None
        self.project_changed = _StubSignal()
        self.data_updated = _StubSignal()
        self.range_changed = _StubSignal()


class _StubRangeInput:
    """Small range input fake."""

    def __init__(self) -> None:
        """Initialize the input."""
        self.wavelength_range_changed = _StubSignal()


class _StubModeStateStore:
    """Minimal mode-state-store stub for shell coordinator tests."""

    def __init__(self, current_mode: EditingMode = EditingMode.START) -> None:
        self.current_mode = current_mode
        self.mode_changed = _StubSignal()

    def switch_mode(self, mode: EditingMode) -> None:
        """Update the current mode and emit the corresponding signal."""
        self.current_mode = mode
        self.mode_changed.emit(mode)

    def set_project(self, project: object) -> None:
        """Accept project updates required by the coordinator API."""
        _ = project


class _PresenterStub:
    """Presenter test double that records applied interaction modes."""

    def __init__(self) -> None:
        self.mode_command_requested = _StubSignal()
        self.interaction_snapshot_applied = _StubSignal()
        self.interactor = _RectZoomInteractorStub()
        self.applied_modes: list[str | None] = []
        self._latest_interaction_snapshot: InteractionStateSnapshot[object] | None = None

    def set_interaction_mode(self, mode_name: str | None) -> None:
        """Record the final interaction mode request."""
        self.interactor.set_rect_zoom_mode(mode_name == "rect_zoom")
        self.applied_modes.append(mode_name)

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return whether rect zoom is currently enabled."""
        return self.interactor.is_rect_zoom_mode_enabled()

    def apply_interaction_state_snapshot(self, snapshot: InteractionStateSnapshot[object]) -> None:
        """Store and emit a snapshot."""
        self._latest_interaction_snapshot = snapshot
        self.interaction_snapshot_applied.emit(snapshot)


@pytest.fixture
def presenter() -> _PresenterStub:
    """Create a minimal presenter test double."""
    return _PresenterStub()


def _make_rect_zoom_snapshot(phase: InteractionPhase) -> InteractionStateSnapshot[RectZoomContext]:
    """Build a deterministic rect zoom snapshot for testing."""
    return InteractionStateSnapshot(
        interaction_id=InteractionId(f"rect-zoom-{phase.value.lower()}"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=phase,
        context=RectZoomContext(
            start=(4100.0, 0.2), current=(4200.0, 0.25), end=None, bounds=None
        ),
    )


def _attach_mode_state_store(coordinator: ModeShellCoordinator) -> None:
    """Attach a real mode state store and enter optimize mode for mode-transition tests."""
    coordinator.mode_state_store = _StubModeStateStore()
    coordinator._require_spectrum_view().policy_applied.connect(
        coordinator._on_spectrum_policy_applied
    )
    coordinator.mode_state_store.mode_changed.connect(coordinator._on_mode_changed)
    coordinator.switch_mode(EditingMode.ANALYSIS)


def test_snapshot_roundtrip_keeps_modes_in_sync(
    presenter: _PresenterStub, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure snapshots emitted by the presenter reach the coordinator and sync correctly."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)

    coordinator._connect_presenter_signals()

    caplog.set_level(logging.WARNING, logger="chappy.gui.shell.mode_shell_coordinator")

    active_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom-sync"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ACTIVE,
        context=RectZoomContext(
            start=(4100.0, 0.2), current=(4200.0, 0.25), end=None, bounds=None
        ),
    )

    presenter.apply_interaction_state_snapshot(active_snapshot)

    assert presenter.interaction_snapshot_applied.emissions == [(active_snapshot,)]
    assert coordinator._latest_interaction_snapshot == active_snapshot
    assert presenter._latest_interaction_snapshot == active_snapshot
    assert not caplog.records

    caplog.clear()

    idle_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom-sync"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.IDLE,
        context=RectZoomContext(
            start=(4100.0, 0.2), current=(4300.0, 0.3), end=(4300.0, 0.3), bounds=None
        ),
    )

    presenter.apply_interaction_state_snapshot(idle_snapshot)

    assert presenter.interaction_snapshot_applied.emissions[-1] == (idle_snapshot,)
    assert len(presenter.interaction_snapshot_applied.emissions) == 2
    assert coordinator._latest_interaction_snapshot == idle_snapshot
    assert presenter._latest_interaction_snapshot == idle_snapshot
    assert not caplog.records


def test_mode_shell_coordinator_double_update_prevention(
    presenter: _PresenterStub, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that applying the same snapshot multiple times does not cause duplicate updates."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)

    coordinator._connect_presenter_signals()

    caplog.set_level(logging.WARNING, logger="chappy.gui.shell.mode_shell_coordinator")

    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom-double"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ACTIVE,
        context=RectZoomContext(
            start=(4100.0, 0.2), current=(4200.0, 0.25), end=None, bounds=None
        ),
    )

    # Apply the same snapshot twice
    presenter.apply_interaction_state_snapshot(snapshot)
    assert len(presenter.interaction_snapshot_applied.emissions) == 1
    assert coordinator._latest_interaction_snapshot == snapshot

    presenter.apply_interaction_state_snapshot(snapshot)
    assert len(presenter.interaction_snapshot_applied.emissions) == 2
    assert coordinator._latest_interaction_snapshot == snapshot

    # No warnings should be logged for duplicate snapshots
    assert not caplog.records


def test_snapshot_fallback_detection(
    presenter: _PresenterStub, caplog: pytest.LogCaptureFixture
) -> None:
    """Absorber drag snapshots are applied and forwarded without fallback warnings."""
    drag_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("absorber-drag-fallback"),
        channel=InteractionChannel.ABSORBER_DRAG,
        phase=InteractionPhase.ARMED,
        context=AbsorberDragContext(
            absorber_id="abs-1",
            start=(5000.0, 0.2),
            current=None,
            end=None,
            modifiers=0,
            cancel_reason=None,
        ),
    )

    caplog.set_level(
        logging.WARNING, logger="chappy.gui.spectrum.spectrum_interaction_coordinator"
    )
    presenter.apply_interaction_state_snapshot(drag_snapshot)

    assert presenter.interaction_snapshot_applied.emissions == [(drag_snapshot,)]
    assert not caplog.records


def test_cancelled_snapshot_returns_none_mode(presenter: _PresenterStub) -> None:
    """Ensure cancelled snapshots no longer report an active legacy mode."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    snapshot = _make_rect_zoom_snapshot(InteractionPhase.CANCELLED)

    assert coordinator._interaction_mode_coordinator._get_mode_name_from_snapshot(snapshot) is None


def test_presenter_reconnection_skips_cancelled_snapshots(presenter: _PresenterStub) -> None:
    """Verify presenter reconnect does not reapply rect zoom after cancellation."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    coordinator.mode_state_store = _StubModeStateStore()
    coordinator._connect_presenter_signals()
    presenter.apply_interaction_state_snapshot(
        _make_rect_zoom_snapshot(InteractionPhase.CANCELLED)
    )

    reconnected_presenter = _PresenterStub()
    main_window.view_stack.spectrum_view = _StubSpectrumView(reconnected_presenter)
    coordinator._connect_presenter_signals()

    assert reconnected_presenter.applied_modes == [None]
    assert not reconnected_presenter.is_rect_zoom_mode_enabled()


def test_mode_change_clears_active_snapshots(presenter: _PresenterStub) -> None:
    """Confirm leaving OPTIMIZE clears active snapshots to avoid stale restarts."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    _attach_mode_state_store(coordinator)
    coordinator._connect_presenter_signals()
    presenter.apply_interaction_state_snapshot(_make_rect_zoom_snapshot(InteractionPhase.ACTIVE))

    coordinator.switch_mode(EditingMode.ANALYSIS)

    assert coordinator._latest_interaction_snapshot is None


def test_set_interaction_mode_none_clears_snapshot(presenter: _PresenterStub) -> None:
    """Ensure manual teardown of interaction mode purges cached snapshots."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    coordinator.mode_state_store = _StubModeStateStore()
    coordinator._connect_presenter_signals()
    presenter.apply_interaction_state_snapshot(_make_rect_zoom_snapshot(InteractionPhase.ACTIVE))

    coordinator._interaction_mode_coordinator.handle_zoom_rect_mode(False)

    assert coordinator._latest_interaction_snapshot is None
    assert presenter.applied_modes[-1] is None
    assert not presenter.is_rect_zoom_mode_enabled()


def test_mode_change_clears_rect_zoom_without_snapshot(presenter: _PresenterStub) -> None:
    """Leaving OPTIMIZE disables rect zoom even if no snapshot has been emitted."""
    interactor = _RectZoomInteractorStub()
    presenter.interactor = interactor
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    _attach_mode_state_store(coordinator)
    coordinator._connect_presenter_signals()

    coordinator._interaction_mode_coordinator.handle_zoom_rect_mode(True)
    assert interactor.is_rect_zoom_mode_enabled()
    assert coordinator._requested_interaction_mode == "rect_zoom"

    coordinator.switch_mode(EditingMode.ANALYSIS)

    assert not interactor.is_rect_zoom_mode_enabled()
    assert presenter.applied_modes[-1] is None
    assert coordinator._requested_interaction_mode is None


def test_presenter_reconnect_uses_interactor_state_without_snapshot(
    presenter: _PresenterStub,
) -> None:
    """Reconnecting presenter reapplies rect zoom when interactor remains enabled."""
    first_interactor = _RectZoomInteractorStub()
    presenter.interactor = first_interactor
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    coordinator.mode_state_store = _StubModeStateStore()
    coordinator._connect_presenter_signals()

    coordinator._interaction_mode_coordinator.handle_zoom_rect_mode(True)
    assert first_interactor.is_rect_zoom_mode_enabled()

    new_presenter = _PresenterStub()
    second_interactor = _RectZoomInteractorStub()
    second_interactor.set_rect_zoom_mode(True)
    new_presenter.interactor = second_interactor
    main_window.view_stack.spectrum_view = _StubSpectrumView(new_presenter)

    coordinator._connect_presenter_signals()

    assert new_presenter.applied_modes == ["rect_zoom"]
    assert second_interactor.is_rect_zoom_mode_enabled()
    assert coordinator._requested_interaction_mode == "rect_zoom"


def test_requested_mode_clears_when_leaving_optimize_without_snapshot(
    presenter: _PresenterStub,
) -> None:
    """Ensure pending requests reset when switching modes before snapshots arrive."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    _attach_mode_state_store(coordinator)
    coordinator._connect_presenter_signals()

    coordinator._interaction_mode_coordinator.handle_zoom_rect_mode(True)
    assert coordinator._requested_interaction_mode == "rect_zoom"

    coordinator.switch_mode(EditingMode.ANALYSIS)

    assert coordinator._requested_interaction_mode is None
    assert presenter.applied_modes[-1] is None
    assert not presenter.is_rect_zoom_mode_enabled()


def test_presenter_reconnect_reapplies_requested_mode_without_snapshot(
    presenter: _PresenterStub,
) -> None:
    """Pending rect-zoom requests are replayed when the presenter reconnects."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)
    coordinator.mode_state_store = _StubModeStateStore()
    coordinator._connect_presenter_signals()

    coordinator._interaction_mode_coordinator.handle_zoom_rect_mode(True)
    assert coordinator._requested_interaction_mode == "rect_zoom"

    new_presenter = _PresenterStub()
    new_interactor = _RectZoomInteractorStub()
    new_presenter.interactor = new_interactor
    main_window.view_stack.spectrum_view = _StubSpectrumView(new_presenter)

    coordinator._connect_presenter_signals()

    assert new_presenter.applied_modes == ["rect_zoom"]
    assert new_interactor.is_rect_zoom_mode_enabled()
    assert coordinator._requested_interaction_mode == "rect_zoom"


def test_presenter_connect_uses_interactor_state_when_no_request(
    presenter: _PresenterStub,
) -> None:
    """First connection falls back to interactor state when no pending request exists."""
    interactor = _RectZoomInteractorStub()
    interactor.set_rect_zoom_mode(True)
    presenter.interactor = interactor

    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(main_window)

    coordinator._connect_presenter_signals()

    assert presenter.applied_modes == ["rect_zoom"]
    assert interactor.is_rect_zoom_mode_enabled()
