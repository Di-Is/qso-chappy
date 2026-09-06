"""Tests for spectrum interaction state coordination."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from chappy.gui.spectrum.interaction_state_coordinator import (
    SpectrumInteractionSnapshot,
    SpectrumInteractionStateCoordinator,
)
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumContext,
    InteractionChannel,
    InteractionId,
    InteractionPhase,
    InteractionStateSnapshot,
    MaskSelectionContext,
    RectZoomContext,
)


class _MaskSnapshotController:
    """Record mask snapshots applied by the coordinator."""

    def __init__(self) -> None:
        """Initialize the controller."""
        self.snapshots: list[InteractionStateSnapshot[MaskSelectionContext]] = []

    def apply_snapshot(self, snapshot: InteractionStateSnapshot[MaskSelectionContext]) -> None:
        """Record the applied snapshot."""
        self.snapshots.append(snapshot)


def _create_coordinator() -> tuple[
    SpectrumInteractionStateCoordinator, list[SpectrumInteractionSnapshot], _MaskSnapshotController
]:
    """Create a coordinator with recording dependencies."""
    emissions: list[SpectrumInteractionSnapshot] = []
    mask_controller = _MaskSnapshotController()
    coordinator = SpectrumInteractionStateCoordinator(
        snapshot_publisher=emissions.append, mask_controller=mask_controller
    )
    return coordinator, emissions, mask_controller


def test_rect_zoom_snapshot_is_cached_and_published() -> None:
    """Rect zoom snapshots should update latest state and notify observers."""
    coordinator, emissions, mask_controller = _create_coordinator()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ACTIVE,
        context=RectZoomContext(
            start=(4100.0, 0.2), current=(4200.0, 0.25), end=None, bounds=None
        ),
    )

    coordinator.apply_interaction_state_snapshot(snapshot)

    assert coordinator.latest_snapshot == snapshot
    assert emissions == [snapshot]
    assert mask_controller.snapshots == []


def test_absorber_drag_snapshot_is_cached_and_published() -> None:
    """Absorber drag snapshots should update latest state and notify observers."""
    coordinator, emissions, _mask_controller = _create_coordinator()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("absorber"),
        channel=InteractionChannel.ABSORBER_DRAG,
        phase=InteractionPhase.ACTIVE,
        context=AbsorberDragContext(
            absorber_id="abs-1",
            start=(4200.0, 0.4),
            current=(4210.0, 0.45),
            end=None,
            modifiers=0,
            cancel_reason=None,
        ),
    )

    coordinator.apply_interaction_state_snapshot(snapshot)

    assert coordinator.latest_snapshot == snapshot
    assert emissions == [snapshot]


def test_continuum_snapshot_is_cached_and_published() -> None:
    """Continuum snapshots should update latest state and notify observers."""
    coordinator, emissions, _mask_controller = _create_coordinator()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("continuum"),
        channel=InteractionChannel.CONTINUUM,
        phase=InteractionPhase.IDLE,
        context=ContinuumContext(
            operation_type="add",
            point_index=None,
            start_position=(4200.0, 1.0),
            current_position=(4200.0, 1.0),
            end_position=(4200.0, 1.0),
            validation_result=None,
            cancel_reason=None,
        ),
    )

    coordinator.apply_interaction_state_snapshot(snapshot)

    assert coordinator.latest_snapshot == snapshot
    assert emissions == [snapshot]


def test_mask_snapshot_is_cached_and_delegated() -> None:
    """Mask snapshots should be handled by the mask controller."""
    coordinator, emissions, mask_controller = _create_coordinator()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("mask"),
        channel=InteractionChannel.MASK_SELECTION,
        phase=InteractionPhase.ACTIVE,
        context=MaskSelectionContext(
            selection_mode="create",
            mask_id=None,
            group_id="group-1",
            start_pos=4100.0,
            current_pos=4200.0,
            end_pos=None,
            initial_range=None,
            excluded_ranges=None,
            result_mask=None,
            cancel_reason=None,
        ),
    )

    coordinator.apply_interaction_state_snapshot(snapshot)

    assert coordinator.latest_snapshot == snapshot
    assert emissions == []
    assert mask_controller.snapshots == [snapshot]


def test_clear_latest_snapshot_resets_cached_state() -> None:
    """Latest snapshot cache should be explicitly clearable."""
    coordinator, _emissions, _mask_controller = _create_coordinator()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ACTIVE,
        context=RectZoomContext(start=None, current=None, end=None, bounds=None),
    )
    coordinator.apply_interaction_state_snapshot(snapshot)

    coordinator.clear_latest_snapshot()

    assert coordinator.latest_snapshot is None


@pytest.mark.parametrize(
    ("channel", "context"),
    [
        (
            InteractionChannel.RECT_ZOOM,
            AbsorberDragContext(
                absorber_id="abs",
                start=(1200.0, 0.8),
                current=(1210.0, 0.9),
                end=None,
                modifiers=0,
                cancel_reason=None,
            ),
        ),
        (
            InteractionChannel.CONTINUUM,
            RectZoomContext(start=(4100.0, 0.2), current=None, end=None, bounds=None),
        ),
    ],
)
def test_channel_context_mismatch_fails_fast(channel: InteractionChannel, context: object) -> None:
    """Mismatched channel/context pairs should fail fast."""
    coordinator, _emissions, _mask_controller = _create_coordinator()
    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("mismatch"),
        channel=channel,
        phase=InteractionPhase.ACTIVE,
        context=context,
    )

    with pytest.raises(TypeError, match="requires context type"):
        coordinator.apply_interaction_state_snapshot(cast("SpectrumInteractionSnapshot", snapshot))
