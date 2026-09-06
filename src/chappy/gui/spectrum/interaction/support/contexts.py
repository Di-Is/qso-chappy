"""Shared interaction context aliases."""

from __future__ import annotations

from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumContext,
    MaskSelectionContext,
    RectZoomContext,
)

type SnapshotContext = (
    RectZoomContext | AbsorberDragContext | MaskSelectionContext | ContinuumContext
)
