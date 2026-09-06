"""Focused tests for InteractionModeCoordinator."""

from __future__ import annotations

from collections.abc import Callable

from chappy.core.editing_mode import EditingMode
from chappy.gui.shell.interaction_mode_coordinator import InteractionModeCoordinator
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.presentation.interaction.interaction_contracts import (
    ContinuumContext,
    ContinuumOperationType,
    InteractionChannel,
    InteractionId,
    InteractionPhase,
    InteractionStateSnapshot,
    MaskSelectionContext,
    RectZoomContext,
)


class _Signal:
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., None]) -> None:
        self._callbacks.remove(callback)

    def emit(self, *args: object) -> None:
        for callback in list(self._callbacks):
            callback(*args)


class _Presenter:
    def __init__(self) -> None:
        self.mode_command_requested = _Signal()
        self.interaction_snapshot_applied = _Signal()
        self.interaction_modes: list[str | None] = []

    def is_rect_zoom_mode_enabled(self) -> bool:
        return self.interaction_modes[-1] == "rect_zoom" if self.interaction_modes else False

    def set_interaction_mode(self, mode_name: str | None) -> None:
        self.interaction_modes.append(mode_name)


class _SpectrumView:
    def __init__(self, presenter: _Presenter) -> None:
        self.coordinator = presenter
        self.policies: list[object] = []

    def apply_policy(self, policy: object) -> None:
        self.policies.append(policy)


def test_interaction_mode_coordinator_tracks_rect_zoom_snapshots() -> None:
    """Rect-zoom snapshots should update zoom UI state and presenter mode."""
    presenter = _Presenter()
    spectrum_view = _SpectrumView(presenter)
    zoom_states: list[bool] = []
    display_modes: list[EditingMode] = []
    coordinator = InteractionModeCoordinator(
        spectrum_view_provider=lambda: spectrum_view,
        current_mode_provider=lambda: EditingMode.ANALYSIS,
        zoom_button_callback=zoom_states.append,
        mode_display_callback=display_modes.append,
    )
    coordinator.connect_presenter()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ARMED,
        context=RectZoomContext(start=(1.0, 2.0), current=None, end=None, bounds=None),
    )

    coordinator.handle_interaction_snapshot(snapshot)
    coordinator.handle_zoom_rect_mode(False)

    assert zoom_states == [True, False]
    assert presenter.interaction_modes[-1] is None
    assert display_modes[-1] == EditingMode.ANALYSIS


def test_interaction_mode_coordinator_rejects_mismatched_snapshot_context() -> None:
    """Snapshot context types should match their declared interaction channel."""
    presenter = _Presenter()
    spectrum_view = _SpectrumView(presenter)
    coordinator = InteractionModeCoordinator(
        spectrum_view_provider=lambda: spectrum_view,
        current_mode_provider=lambda: EditingMode.ANALYSIS,
        zoom_button_callback=lambda _checked: None,
        mode_display_callback=lambda _mode: None,
    )
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("bad-snapshot"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ARMED,
        context=ContinuumContext(
            operation_type=ContinuumOperationType.MOVE,
            point_index=1,
            start_position=(4100.0, 1.0),
            current_position=(4200.0, 1.1),
            end_position=None,
            validation_result=None,
            cancel_reason=None,
        ),
    )

    try:
        coordinator.handle_interaction_snapshot(snapshot)
    except TypeError as exc:
        assert "Snapshot context for rect_zoom" in str(exc)
    else:
        raise AssertionError("TypeError was not raised for mismatched snapshot context")


def test_interaction_mode_coordinator_accepts_mode_owned_snapshots_from_signal() -> None:
    """Mode-owned spectrum snapshots should remain valid on the shared observer signal."""
    presenter = _Presenter()
    spectrum_view = _SpectrumView(presenter)
    zoom_states: list[bool] = []
    coordinator = InteractionModeCoordinator(
        spectrum_view_provider=lambda: spectrum_view,
        current_mode_provider=lambda: EditingMode.ANALYSIS,
        zoom_button_callback=zoom_states.append,
        mode_display_callback=lambda _mode: None,
    )
    coordinator.connect_presenter()
    mask_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("mask-selection"),
        channel=InteractionChannel.MASK_SELECTION,
        phase=InteractionPhase.ACTIVE,
        context=MaskSelectionContext(
            selection_mode="create",
            mask_id=None,
            group_id="region-1",
            start_pos=4100.0,
            current_pos=4200.0,
            end_pos=None,
            initial_range=None,
            excluded_ranges=None,
            result_mask=None,
            cancel_reason=None,
        ),
    )
    continuum_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("continuum-move"),
        channel=InteractionChannel.CONTINUUM,
        phase=InteractionPhase.ACTIVE,
        context=ContinuumContext(
            operation_type=ContinuumOperationType.MOVE,
            point_index=1,
            start_position=(4100.0, 1.0),
            current_position=(4200.0, 1.1),
            end_position=None,
            validation_result=None,
            cancel_reason=None,
        ),
    )

    presenter.interaction_snapshot_applied.emit(mask_snapshot)
    assert coordinator.latest_interaction_snapshot == mask_snapshot

    presenter.interaction_snapshot_applied.emit(continuum_snapshot)

    assert coordinator.latest_interaction_snapshot == continuum_snapshot
    assert coordinator.requested_interaction_mode is None
    assert zoom_states == []


def test_interaction_mode_coordinator_applies_plot_policy() -> None:
    """Mode policy application should target the current spectrum view."""
    presenter = _Presenter()
    spectrum_view = _SpectrumView(presenter)
    coordinator = InteractionModeCoordinator(
        spectrum_view_provider=lambda: spectrum_view,
        current_mode_provider=lambda: EditingMode.ANALYSIS,
        zoom_button_callback=lambda _checked: None,
        mode_display_callback=lambda _mode: None,
    )

    policy = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)
    coordinator.apply_policy(policy)

    assert spectrum_view.policies == [policy]
