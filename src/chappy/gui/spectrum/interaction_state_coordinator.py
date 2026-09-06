"""Interaction state snapshot coordination for the spectrum surface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumContext,
    InteractionChannel,
    InteractionStateSnapshot,
    MaskSelectionContext,
    RectZoomContext,
)

if TYPE_CHECKING:
    from collections.abc import Callable

ContextT = TypeVar("ContextT")

type SpectrumInteractionSnapshot = (
    InteractionStateSnapshot[RectZoomContext]
    | InteractionStateSnapshot[AbsorberDragContext]
    | InteractionStateSnapshot[MaskSelectionContext]
    | InteractionStateSnapshot[ContinuumContext]
)


class MaskSnapshotController(Protocol):
    """Controller capable of applying mask selection snapshots."""

    def apply_snapshot(self, snapshot: InteractionStateSnapshot[MaskSelectionContext]) -> None:
        """Apply a mask selection snapshot."""
        ...


class SpectrumInteractionStateCoordinator:
    """Validate, cache, and dispatch interactor state snapshots."""

    def __init__(
        self,
        *,
        snapshot_publisher: Callable[[SpectrumInteractionSnapshot], None],
        mask_controller: MaskSnapshotController,
    ) -> None:
        """Initialize the state coordinator.

        Args:
            snapshot_publisher: Callback used for snapshots that should notify observers.
            mask_controller: Controller that owns mask snapshot side effects.
        """
        self._snapshot_publisher = snapshot_publisher
        self._mask_controller = mask_controller
        self._latest_snapshot: SpectrumInteractionSnapshot | None = None

    @property
    def latest_snapshot(self) -> SpectrumInteractionSnapshot | None:
        """Return the latest accepted interaction snapshot."""
        return self._latest_snapshot

    def clear_latest_snapshot(self) -> None:
        """Clear the cached interaction snapshot."""
        self._latest_snapshot = None

    def apply_interaction_state_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Apply an interaction state snapshot emitted by the interactor."""
        if snapshot.channel is InteractionChannel.RECT_ZOOM:
            rect_snapshot = self._coerce_interaction_snapshot_context(
                snapshot, InteractionChannel.RECT_ZOOM, RectZoomContext
            )
            self._apply_rect_zoom_snapshot(rect_snapshot)
            return

        if snapshot.channel is InteractionChannel.ABSORBER_DRAG:
            absorber_drag_snapshot = self._coerce_interaction_snapshot_context(
                snapshot, InteractionChannel.ABSORBER_DRAG, AbsorberDragContext
            )
            self._apply_absorber_drag_snapshot(absorber_drag_snapshot)
            return

        if snapshot.channel is InteractionChannel.MASK_SELECTION:
            mask_selection_snapshot = self._coerce_interaction_snapshot_context(
                snapshot, InteractionChannel.MASK_SELECTION, MaskSelectionContext
            )
            self._apply_mask_selection_snapshot(mask_selection_snapshot)
            return

        if snapshot.channel is InteractionChannel.CONTINUUM:
            continuum_snapshot = self._coerce_interaction_snapshot_context(
                snapshot, InteractionChannel.CONTINUUM, ContinuumContext
            )
            self._apply_continuum_snapshot(continuum_snapshot)
            return

        msg = f"Unsupported interaction snapshot channel: {snapshot.channel.value}"
        raise RuntimeError(msg)

    def _coerce_interaction_snapshot_context(
        self,
        snapshot: SpectrumInteractionSnapshot,
        expected_channel: InteractionChannel,
        expected_context_type: type[ContextT],
    ) -> InteractionStateSnapshot[ContextT]:
        context = snapshot.context
        if context is not None and not isinstance(context, expected_context_type):
            msg = (
                f"Interaction snapshot channel {expected_channel.value} requires "
                f"context type {expected_context_type.__name__}, got {type(context).__name__}"
            )
            raise TypeError(msg)

        return InteractionStateSnapshot(
            interaction_id=snapshot.interaction_id,
            channel=snapshot.channel,
            phase=snapshot.phase,
            context=context,
        )

    def _apply_rect_zoom_snapshot(
        self, snapshot: InteractionStateSnapshot[RectZoomContext]
    ) -> None:
        """Apply a rectangle zoom snapshot and notify observers."""
        self._publish_snapshot(snapshot)

    def _apply_absorber_drag_snapshot(
        self, snapshot: InteractionStateSnapshot[AbsorberDragContext]
    ) -> None:
        """Apply an absorber drag snapshot and notify observers."""
        self._publish_snapshot(snapshot)

    def _apply_mask_selection_snapshot(
        self, snapshot: InteractionStateSnapshot[MaskSelectionContext]
    ) -> None:
        """Apply a mask selection snapshot through the mask controller."""
        self._latest_snapshot = snapshot
        self._mask_controller.apply_snapshot(snapshot)

    def _apply_continuum_snapshot(
        self, snapshot: InteractionStateSnapshot[ContinuumContext]
    ) -> None:
        """Apply a continuum editing snapshot and notify observers."""
        self._publish_snapshot(snapshot)

    def _publish_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Cache and publish a snapshot."""
        self._latest_snapshot = snapshot
        self._snapshot_publisher(snapshot)
