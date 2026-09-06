"""History event data structure.

This module defines the HistoryEvent dataclass that represents a single
undoable operation in the history stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .commands import HistoryCommand
    from .operation_id import OperationId


@dataclass(frozen=True, slots=True)
class HistoryEvent:
    """Immutable history event representing a single undoable operation.

    Attributes:
        command: Typed command that applies redo and undo states.
        created_at: Timestamp when the event was created.
    """

    command: HistoryCommand
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def operation_id(self) -> OperationId:
        """Return the command operation identifier."""
        return self.command.operation_id

    @property
    def qualifier(self) -> str | None:
        """Return the command qualifier."""
        return self.command.qualifier

    @property
    def full_operation_id(self) -> str:
        """Return the full operation ID including qualifier.

        Format: namespace.action[.qualifier]

        Examples:
            - "draw.range_change"
            - "draw.range_change.nav"
            - "ident.add_temporary_line"
        """
        base = self.operation_id.value
        if self.qualifier:
            return f"{base}.{self.qualifier}"
        return base

    def is_noop(self) -> bool:
        """Return whether this command represents no state change."""
        return self.command.is_noop()

    def coalesced_with(self, next_event: HistoryEvent) -> HistoryEvent | None:
        """Return a new event merged with the next event, if possible.

        Args:
            next_event: Event to merge into this event.

        Returns:
            Merged event preserving the original timestamp, or None.
        """
        merged_command = self.command.coalesced_with(next_event.command)
        if merged_command is None:
            return None
        return HistoryEvent(command=merged_command, created_at=self.created_at)


@dataclass(frozen=True, slots=True)
class UndoResult:
    """Result of an undo operation.

    Attributes:
        success: Whether the operation succeeded.
        operation_name: Human-readable name for status bar display.
        error_reason: Error message if failed.
    """

    success: bool
    operation_name: str
    error_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RedoResult:
    """Result of a redo operation.

    Attributes:
        success: Whether the operation succeeded.
        operation_name: Human-readable name for status bar display.
        error_reason: Error message if failed.
    """

    success: bool
    operation_name: str
    error_reason: str | None = None


@dataclass(frozen=True, slots=True)
class HistoryState:
    """Snapshot of history stack state for UI updates.

    Attributes:
        can_undo: Whether undo is available.
        can_redo: Whether redo is available.
        undo_count: Number of entries in undo stack.
        redo_count: Number of entries in redo stack.
        next_undo_operation_id: Operation ID of next undo operation (for translation).
        next_redo_operation_id: Operation ID of next redo operation (for translation).
    """

    can_undo: bool
    can_redo: bool
    undo_count: int
    redo_count: int
    next_undo_operation_id: str | None
    next_redo_operation_id: str | None
