"""Typed interaction contracts shared between state components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType, TypeVar

if TYPE_CHECKING:
    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.masking import MaskDefinition

# Shared coordinate alias for data-space positions.
Coordinate = tuple[float, float]

# Unique identifier for an interaction lifecycle.
InteractionId = NewType("InteractionId", str)


class InteractionChannel(StrEnum):
    """Interaction channels recognised by the state controller."""

    RECT_ZOOM = "rect_zoom"
    ABSORBER_DRAG = "absorber_drag"
    MASK_SELECTION = "mask_selection"
    CONTINUUM = "continuum"


class InteractionPhase(StrEnum):
    """High-level interaction phases used for logging and snapshots."""

    IDLE = "idle"
    ARMED = "armed"
    ACTIVE = "active"
    CANCELLED = "cancelled"


class InteractionEventKind(StrEnum):
    """Kinds of interaction events routed to the state controller."""

    RECT_ZOOM_BEGIN = "rect_zoom_begin"
    RECT_ZOOM_UPDATE = "rect_zoom_update"
    RECT_ZOOM_COMPLETE = "rect_zoom_complete"
    RECT_ZOOM_CANCEL = "rect_zoom_cancel"
    ABSORBER_DRAG_BEGIN = "absorber_drag_begin"
    ABSORBER_DRAG_UPDATE = "absorber_drag_update"
    ABSORBER_DRAG_COMPLETE = "absorber_drag_complete"
    ABSORBER_DRAG_CANCEL = "absorber_drag_cancel"
    MASK_SELECTION_BEGIN = "mask_selection_begin"
    MASK_SELECTION_UPDATE = "mask_selection_update"
    MASK_SELECTION_COMPLETE = "mask_selection_complete"
    MASK_SELECTION_CANCEL = "mask_selection_cancel"
    CONTINUUM_ADD_BEGIN = "continuum_add_begin"
    CONTINUUM_ADD_COMPLETE = "continuum_add_complete"
    CONTINUUM_MOVE_BEGIN = "continuum_move_begin"
    CONTINUUM_MOVE_UPDATE = "continuum_move_update"
    CONTINUUM_MOVE_COMPLETE = "continuum_move_complete"
    CONTINUUM_DELETE_BEGIN = "continuum_delete_begin"
    CONTINUUM_DELETE_COMPLETE = "continuum_delete_complete"
    CONTINUUM_SELECT = "continuum_select"
    CONTINUUM_CANCEL = "continuum_cancel"


class ContinuumOperationType(StrEnum):
    """Types of continuum editing operations."""

    ADD = "add"
    MOVE = "move"
    DELETE = "delete"
    SELECT = "select"


@dataclass(frozen=True)
class AbsorberDragPayload:
    """Typed payload for absorber drag events."""

    absorber_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MaskSelectionBeginPayload:
    """Typed payload for mask selection begin events."""

    start_pos: float
    selection_mode: str
    group_id: str | None
    mask_id: str | None
    initial_range: tuple[float, float] | None
    existing_mask: MaskDefinition | None


@dataclass(frozen=True)
class MaskSelectionPositionPayload:
    """Typed payload for mask selection update and completion events."""

    position: float


@dataclass(frozen=True)
class ContinuumPointPayload:
    """Typed payload for continuum point-index events."""

    point_index: int | None


type InteractionPayload = (
    AbsorberDragPayload
    | MaskSelectionBeginPayload
    | MaskSelectionPositionPayload
    | ContinuumPointPayload
)


@dataclass(frozen=True)
class InteractionEvent:
    """Interaction event emitted by Qt adaptation layers.

    Args:
        channel: Interaction channel target.
        kind: Event classification consumed by the state controller.
        position: Data-space coordinate associated with the event when available.
        modifiers: Active keyboard modifiers captured with the event.
        interaction_id: Existing interaction identifier for follow-up events.
        payload: Optional metadata describing the event.
    """

    channel: InteractionChannel
    kind: InteractionEventKind
    position: Coordinate | None = None
    modifiers: int | None = None
    interaction_id: InteractionId | None = None
    payload: InteractionPayload | None = None


@dataclass(frozen=True)
class RectZoomBounds:
    """Rectangle bounds calculated during zoom completion.

    Args:
        min_wavelength: Smallest wavelength in the zoom rectangle.
        max_wavelength: Largest wavelength in the zoom rectangle.
        min_flux: Smallest flux value in the rectangle.
        max_flux: Largest flux value in the rectangle.
    """

    min_wavelength: float
    max_wavelength: float
    min_flux: float
    max_flux: float


@dataclass(frozen=True)
class RectZoomContext:
    """Context payload attached to rectangle zoom interactions.

    Args:
        start: Drag starting coordinate.
        current: Most recent coordinate observed during drag.
        end: Final coordinate after completion.
        bounds: Calculated rectangle bounds when available.
    """

    start: Coordinate | None
    current: Coordinate | None
    end: Coordinate | None
    bounds: RectZoomBounds | None


@dataclass(frozen=True)
class AbsorberDragContext:
    """Context payload attached to absorber drag interactions.

    Args:
        absorber_id: Identifier of the absorber being dragged.
        start: Drag starting coordinate captured at the beginning of the interaction.
        current: Latest coordinate observed during the drag gesture.
        end: Final coordinate recorded when completing the drag.
        modifiers: Keyboard modifier mask captured alongside the event when available.
        cancel_reason: Optional textual reason recorded when the interaction is cancelled.
    """

    absorber_id: str | None
    start: Coordinate | None
    current: Coordinate | None
    end: Coordinate | None
    modifiers: int | None
    cancel_reason: str | None


@dataclass(frozen=True)
class OptimizeLineSelectionChange:
    """Line selection change emitted by optimize mode UI."""

    line: AbsorptionLine | None
    component_id: str | None


@dataclass(frozen=True)
class OptimizeMaskFocusChange:
    """Mask focus change emitted by optimize mode UI."""

    mask_id: str | None


@dataclass(frozen=True)
class OptimizeMaskGroupChange:
    """Active mask group change emitted by optimize mode UI."""

    group_id: str | None


@dataclass(frozen=True)
class MaskSelectionContext:
    """Context payload attached to mask selection interactions.

    Args:
        selection_mode: Operation mode ("create" for new mask, "edit" for existing mask).
        mask_id: Identifier of the mask being edited (None for create mode).
            group_id: Identifier of the fitting group associated with the mask.
        start_pos: Starting wavelength position of the selection.
        current_pos: Current wavelength position during drag.
        end_pos: Final wavelength position after completion.
        initial_range: Initial wavelength range for edit mode (None for create mode).
        excluded_ranges: List of wavelength ranges already excluded (for validation).
        result_mask: MaskDefinition created or updated by the controller (available after completion).
        cancel_reason: Optional textual reason recorded when the interaction is cancelled.
    """

    selection_mode: str | None  # "create" | "edit"
    mask_id: str | None
    group_id: str | None
    start_pos: float | None
    current_pos: float | None
    end_pos: float | None
    initial_range: tuple[float, float] | None
    excluded_ranges: list[tuple[float, float]] | None
    result_mask: MaskDefinition | None
    cancel_reason: str | None


@dataclass(frozen=True)
class ValidationError:
    """Validation error result for continuum operations.

    Args:
        reason: Validation failure reason code.
        message: Human-readable error message.
        metadata: Optional additional metadata for the error.
    """

    reason: str
    message: str
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class ContinuumContext:
    """Context payload attached to continuum editing interactions.

    Args:
        operation_type: Type of operation.
        point_index: Index of the point being operated on (None for add operation).
        start_position: Starting coordinate captured at the beginning of the interaction.
        current_position: Latest coordinate observed during the interaction.
        end_position: Final coordinate recorded when completing the interaction.
        validation_result: Optional validation error if validation failed.
        cancel_reason: Optional textual reason recorded when the interaction is cancelled.
    """

    operation_type: ContinuumOperationType | None
    point_index: int | None
    start_position: Coordinate | None
    current_position: Coordinate | None
    end_position: Coordinate | None
    validation_result: ValidationError | None
    cancel_reason: str | None


@dataclass(frozen=True)
class MaskSelectionRequest:
    """Request payload used to initiate a mask selection interaction.

    Args:
        selection_mode: Operation mode (``"create"`` or ``"edit"``).
            group_id: Identifier of the fitting group to associate with the mask.
        mask_id: Identifier of the mask being edited when in edit mode.
        initial_range: Optional wavelength range used to prepopulate the overlay.
        existing_mask: Full mask definition referenced during edit operations.
    """

    selection_mode: str
    group_id: str | None
    mask_id: str | None
    initial_range: tuple[float, float] | None
    existing_mask: MaskDefinition | None

    def build_begin_payload(self, start_pos: float) -> MaskSelectionBeginPayload:
        """Return controller payload for a begin event.

        Args:
            start_pos: Wavelength coordinate chosen as the anchor point.
        """
        return MaskSelectionBeginPayload(
            start_pos=float(start_pos),
            selection_mode=self.selection_mode,
            group_id=self.group_id,
            mask_id=self.mask_id,
            initial_range=self.initial_range,
            existing_mask=self.existing_mask,
        )

    def build_update_payload(self, current_pos: float) -> MaskSelectionPositionPayload:
        """Return controller payload for an update event."""
        return MaskSelectionPositionPayload(position=float(current_pos))

    def build_complete_payload(self, end_pos: float) -> MaskSelectionPositionPayload:
        """Return controller payload for a completion event."""
        return MaskSelectionPositionPayload(position=float(end_pos))


ContextT = TypeVar("ContextT")


@dataclass(frozen=True)
class InteractionOutcome[ContextT]:
    """Outcome produced by processing an interaction event.

    Args:
        channel: Interaction channel that produced the outcome.
        phase: Resulting high-level phase after processing.
        context: Context payload carrying channel-specific data.
        interaction_id: Identifier associated with the interaction lifecycle.
    """

    channel: InteractionChannel
    phase: InteractionPhase
    context: ContextT
    interaction_id: InteractionId


@dataclass(frozen=True)
class InteractionStateSnapshot[ContextT]:
    """Snapshot representing the observable interaction state.

    Args:
        interaction_id: Identifier associated with the interaction lifecycle.
        channel: Interaction channel represented by the snapshot.
        phase: Current phase reflected by the snapshot.
        context: Context payload providing channel-specific details.
    """

    interaction_id: InteractionId
    channel: InteractionChannel
    phase: InteractionPhase
    context: ContextT | None
