"""Command history for undo/redo operations.

This module provides the CommandHistory class that manages undo/redo stacks
and coordinates with GUI components via callbacks.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Protocol

from .coalesce import DEFAULT_COALESCE_WINDOW_MS, CoalesceBuffer, CoalesceBufferSnapshot
from .history_event import HistoryEvent, HistoryState, RedoResult, UndoResult

logger = logging.getLogger(__name__)

# Maximum number of history entries (HIS.01.01.G01.S01)
HISTORY_MAX = 100


@dataclass(frozen=True, slots=True)
class _HistoryMutationSnapshot:
    """Complete stack state restored when an atomic recording scope aborts."""

    undo_stack: tuple[HistoryEvent, ...]
    redo_stack: tuple[HistoryEvent, ...]
    coalesce: CoalesceBufferSnapshot
    notification_pending: bool


class HistoryApplier(Protocol):
    """Protocol for objects that apply history events.

    GUI layer implements this protocol to handle the actual state changes
    when undo/redo is executed.
    """

    def apply_history_event(self, event: HistoryEvent, *, is_undo: bool) -> bool:
        """Apply a history event.

        Args:
            event: The event to apply.
            is_undo: True for undo, False for redo.

        Returns:
            True if applied successfully, False on failure.
        """
        ...


# Type alias for state change callbacks
StateChangeCallback = Callable[[HistoryState], None]


class HistoryOwnerThreadError(RuntimeError):
    """Raised when history state is accessed outside its owning GUI thread."""

    def __init__(self, operation: str, *, owner_thread_id: int, current_thread_id: int) -> None:
        """Initialize one typed single-owner contract violation."""
        super().__init__(
            f"Cannot {operation} history from thread {current_thread_id}; "
            f"owner thread is {owner_thread_id}."
        )
        self.operation = operation
        self.owner_thread_id = owner_thread_id
        self.current_thread_id = current_thread_id


class CommandHistory:
    """Qt-independent command history for undo/redo operations.

    Manages undo/redo stacks and provides push/undo/redo operations.
    GUI integration is done via callbacks, not Qt signals.

    Every public operation belongs to the thread that creates this instance.
    This single-owner contract prevents OS scheduler timing from interleaving
    stack recording or queries with an active scientific Undo/Redo transition.
    The transition lock additionally rejects same-thread re-entrant transitions.

    Features:
        - Maximum 100 entries (oldest discarded on overflow)
        - Redo stack cleared on new push (HIS.01.01.G01.S04)
        - Coalesce support for high-frequency operations
        - Recording suppression for undo/redo execution
        - No-op detection (before == after)

    Example:
        history = CommandHistory()
        history.set_applier(my_applier)
        history.subscribe(on_state_change)

        # Push an event
        event = HistoryEvent(command=range_command)
        history.push(event)

        # Undo
        result = history.undo()
        if result.success:
            show_status(f"Undone: {result.operation_name}")
    """

    def __init__(
        self,
        *,
        max_history: int = HISTORY_MAX,
        coalesce_window_ms: int = DEFAULT_COALESCE_WINDOW_MS,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        """Initialize command history.

        Args:
            max_history: Maximum number of entries in each stack.
            coalesce_window_ms: Coalesce window in milliseconds.
            time_provider: Function returning current time in seconds (for testing).
        """
        self._max_history = max_history
        self._undo_stack: deque[HistoryEvent] = deque(maxlen=max_history)
        self._redo_stack: deque[HistoryEvent] = deque(maxlen=max_history)

        # Coalesce buffer
        self._coalesce = CoalesceBuffer(
            window_ms=coalesce_window_ms, time_provider=time_provider or time.monotonic
        )

        # Recording suppression (counter for nesting support)
        self._suppress_count = 0

        # Applier (set by GUI layer)
        self._applier: HistoryApplier | None = None

        # State change subscribers
        self._subscribers: list[StateChangeCallback] = []

        # Atomic recording defers observer updates until the outermost commit.
        self._atomic_recording_depth = 0
        self._notification_pending = False

        # Applying one event must finish before another stack transition starts.
        self._stack_transition_lock = threading.Lock()
        self._owner_thread_id = threading.get_ident()

    # ----------------------------------------------------------------
    # Applier configuration
    # ----------------------------------------------------------------

    def set_applier(self, applier: HistoryApplier | None) -> None:
        """Set the history applier.

        Args:
            applier: Object that implements HistoryApplier protocol.
        """
        self._assert_owner_thread("configure")
        self._applier = applier

    # ----------------------------------------------------------------
    # Stack operations
    # ----------------------------------------------------------------

    def push(self, event: HistoryEvent, *, coalesce: bool = False) -> bool:
        """Push a history event onto the undo stack.

        Args:
            event: The event to push.
            coalesce: If True, try to coalesce with pending event.

        Returns:
            True if recorded, False if suppressed or no-op.
        """
        self._assert_owner_thread("push to")

        # Check suppression
        if self._suppress_count > 0:
            logger.debug("History recording suppressed, skipping: %s", event.operation_id)
            return False

        if self._is_noop(event):
            logger.debug("No-op event skipped: %s", event.operation_id)
            return False

        # Handle coalesce
        if coalesce:
            merged = self._coalesce.try_coalesce(event)
            if merged is not None:
                # Successfully coalesced - replace the last entry in stack
                if self._undo_stack:
                    self._undo_stack.pop()

                # Check if merged result is a no-op (before == after)
                if self._is_noop(merged):
                    # Merged to no-op: clear pending and don't record
                    self._coalesce.commit()
                    logger.debug("Coalesced to no-op, removed: %s", merged.full_operation_id)
                    self._redo_stack.clear()  # HIS.01.01.G01.S04
                    self._notify_state_change()
                    return False

                self._undo_stack.append(merged)
                self._redo_stack.clear()  # HIS.01.01.G01.S04
                logger.debug("Coalesced event: %s", event.full_operation_id)
                self._notify_state_change()
                return True
            # Coalesce failed - commit any pending and start new sequence
            self._commit_pending()
            self._coalesce.start(event)
        else:
            # Non-coalescable operation - commit any pending first
            self._commit_pending()

        # Push new event
        self._undo_stack.append(event)
        self._redo_stack.clear()  # HIS.01.01.G01.S04

        logger.info("History pushed: %s", event.full_operation_id)
        self._notify_state_change()
        return True

    def undo(self) -> UndoResult:
        """Execute undo operation.

        Returns:
            UndoResult with success status and operation name.
        """
        self._assert_owner_thread("undo")
        with self._exclusive_stack_transition("Undo"):
            return self._undo_once()

    def _undo_once(self) -> UndoResult:
        """Execute one Undo while holding the stack transition guard."""
        snapshot = self._capture_mutation_snapshot()

        # Commit any pending coalesce only inside the restorable transition.
        self._commit_pending()

        if not self._undo_stack:
            self._restore_mutation_snapshot(snapshot)
            logger.debug("Nothing to undo")
            return UndoResult(success=False, operation_name="", error_reason="Nothing to undo")

        event = self._undo_stack[-1]
        operation_name = event.full_operation_id

        try:
            success = self._apply_event(event, is_undo=True)
        except Exception:
            self._restore_failed_history_apply(snapshot)
            raise

        if not success:
            self._restore_failed_history_apply(snapshot)
            logger.warning("Undo failed: %s", event.full_operation_id)
            return UndoResult(
                success=False, operation_name=operation_name, error_reason="Failed to apply undo"
            )

        self._transfer_applied_event(
            source=self._undo_stack,
            destination=self._redo_stack,
            expected_event=event,
            snapshot=snapshot,
        )
        logger.info("Undo completed: %s", event.full_operation_id)
        self._notify_state_change(isolate_errors=True)
        return UndoResult(success=True, operation_name=operation_name)

    def redo(self) -> RedoResult:
        """Execute redo operation.

        Returns:
            RedoResult with success status and operation name.
        """
        self._assert_owner_thread("redo")
        with self._exclusive_stack_transition("Redo"):
            return self._redo_once()

    def _redo_once(self) -> RedoResult:
        """Execute one Redo while holding the stack transition guard."""
        snapshot = self._capture_mutation_snapshot()

        if not self._redo_stack:
            logger.debug("Nothing to redo")
            return RedoResult(success=False, operation_name="", error_reason="Nothing to redo")

        event = self._redo_stack[-1]
        operation_name = event.full_operation_id

        try:
            success = self._apply_event(event, is_undo=False)
        except Exception:
            self._restore_failed_history_apply(snapshot)
            raise

        if not success:
            self._restore_failed_history_apply(snapshot)
            logger.warning("Redo failed: %s", event.full_operation_id)
            return RedoResult(
                success=False, operation_name=operation_name, error_reason="Failed to apply redo"
            )

        self._transfer_applied_event(
            source=self._redo_stack,
            destination=self._undo_stack,
            expected_event=event,
            snapshot=snapshot,
        )
        logger.info("Redo completed: %s", event.full_operation_id)
        self._notify_state_change(isolate_errors=True)
        return RedoResult(success=True, operation_name=operation_name)

    def clear(self) -> None:
        """Clear both stacks (for session boundary).

        Called when project is switched (HIS.01.01.G01.S05).
        """
        self._assert_owner_thread("clear")
        with self._exclusive_stack_transition("Clear"):
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._coalesce.commit()  # Discard any pending
            logger.info("History cleared")
            self._notify_state_change()

    # ----------------------------------------------------------------
    # Recording suppression (re-entrant)
    # ----------------------------------------------------------------

    @contextlib.contextmanager
    def suppress_recording(self) -> Iterator[None]:
        """Context manager to temporarily suppress history recording.

        Used during undo/redo execution to prevent recursive recording.
        Supports nesting (counter-based).

        Example:
            with history.suppress_recording():
                # State changes here won't be recorded
                apply_state_change()
        """
        self._assert_owner_thread("suppress recording for")
        self._suppress_count += 1
        try:
            yield
        finally:
            self._suppress_count -= 1

    @contextlib.contextmanager
    def atomic_recording(self) -> Iterator[None]:
        """Rollback stack and coalescing state if a recording collaborator fails.

        Project mutations remain the responsibility of the caller. This scope only
        guarantees that a failed compound operation cannot leave an Undo entry or
        destroy a pre-existing Redo stack.
        """
        self._assert_owner_thread("start atomic recording for")
        snapshot = self._capture_mutation_snapshot()
        self._atomic_recording_depth += 1
        try:
            yield
        except Exception:
            self._restore_mutation_snapshot(snapshot)
            raise
        finally:
            self._atomic_recording_depth -= 1

        if self._atomic_recording_depth == 0 and self._notification_pending:
            self._notification_pending = False
            self._dispatch_state_change(isolate_errors=True)

    @property
    def is_suppressed(self) -> bool:
        """Return whether recording is currently suppressed."""
        self._assert_owner_thread("query")
        return self._suppress_count > 0

    # ----------------------------------------------------------------
    # State query
    # ----------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        """Return whether undo is available."""
        self._assert_owner_thread("query")
        return bool(self._undo_stack) or self._coalesce.has_pending

    @property
    def can_redo(self) -> bool:
        """Return whether redo is available."""
        self._assert_owner_thread("query")
        return bool(self._redo_stack)

    def get_state(self) -> HistoryState:
        """Get current history state snapshot.

        Returns:
            HistoryState with current stack information.
        """
        self._assert_owner_thread("query")

        # Pending event is already in stack (added on coalesce start),
        # so just count stack entries
        undo_count = len(self._undo_stack)

        # Get next undo operation ID (prefer pending for most up-to-date coalesced state)
        next_undo = None
        if self._coalesce.has_pending:
            pending = self._coalesce.pending_event
            if pending:
                next_undo = pending.full_operation_id
        elif self._undo_stack:
            last = self._undo_stack[-1]
            next_undo = last.full_operation_id

        # Get next redo operation ID
        next_redo = None
        if self._redo_stack:
            last = self._redo_stack[-1]
            next_redo = last.full_operation_id

        return HistoryState(
            can_undo=self.can_undo,
            can_redo=self.can_redo,
            undo_count=undo_count,
            redo_count=len(self._redo_stack),
            next_undo_operation_id=next_undo,
            next_redo_operation_id=next_redo,
        )

    # ----------------------------------------------------------------
    # Subscription (observer pattern)
    # ----------------------------------------------------------------

    def subscribe(self, callback: StateChangeCallback) -> None:
        """Subscribe to state change notifications.

        Args:
            callback: Function called with HistoryState on each change.
        """
        self._assert_owner_thread("subscribe to")
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: StateChangeCallback) -> None:
        """Unsubscribe from state change notifications.

        Args:
            callback: Previously subscribed callback to remove.
        """
        self._assert_owner_thread("unsubscribe from")
        self._subscribers.remove(callback)

    # ----------------------------------------------------------------
    # Internal methods
    # ----------------------------------------------------------------

    def _apply_event(self, event: HistoryEvent, *, is_undo: bool) -> bool:
        """Apply a history event with suppression.

        Args:
            event: The event to apply.
            is_undo: True for undo, False for redo.

        Returns:
            True if successful, False on failure.
        """
        if self._applier is None:
            msg = "History applier is required before applying history events."
            raise RuntimeError(msg)

        with self.suppress_recording():
            return self._applier.apply_history_event(event, is_undo=is_undo)

    @contextlib.contextmanager
    def _exclusive_stack_transition(self, operation: str) -> Iterator[None]:
        """Fail fast when an Undo/Redo/Clear transition is already active."""
        if not self._stack_transition_lock.acquire(blocking=False):
            msg = f"Cannot start {operation}: a history stack transition is already active."
            raise RuntimeError(msg)
        try:
            yield
        finally:
            self._stack_transition_lock.release()

    def _assert_owner_thread(self, operation: str) -> None:
        """Require every history API call to originate from its owner thread."""
        current_thread_id = threading.get_ident()
        if current_thread_id != self._owner_thread_id:
            raise HistoryOwnerThreadError(
                operation,
                owner_thread_id=self._owner_thread_id,
                current_thread_id=current_thread_id,
            )

    def _is_noop(self, event: HistoryEvent) -> bool:
        """Check if event is a no-op.

        Args:
            event: The event to check.

        Returns:
            True if the command reports no state change.
        """
        return event.is_noop()

    def _commit_pending(self) -> None:
        """Commit any pending coalesce event to the stack."""
        self._coalesce.commit()

    def _capture_mutation_snapshot(self) -> _HistoryMutationSnapshot:
        """Capture every mutable fact owned by the history stacks."""
        return _HistoryMutationSnapshot(
            undo_stack=tuple(self._undo_stack),
            redo_stack=tuple(self._redo_stack),
            coalesce=self._coalesce.snapshot(),
            notification_pending=self._notification_pending,
        )

    def _restore_mutation_snapshot(self, snapshot: _HistoryMutationSnapshot) -> None:
        """Restore stacks, coalescing state, and deferred notification state."""
        self._undo_stack = deque(snapshot.undo_stack, maxlen=self._max_history)
        self._redo_stack = deque(snapshot.redo_stack, maxlen=self._max_history)
        self._coalesce.restore(snapshot.coalesce)
        self._notification_pending = snapshot.notification_pending

    def _restore_failed_history_apply(self, snapshot: _HistoryMutationSnapshot) -> None:
        """Restore one failed apply and safely report its unchanged state."""
        self._restore_mutation_snapshot(snapshot)
        if self._atomic_recording_depth == 0:
            self._dispatch_state_change(isolate_errors=True)

    def _transfer_applied_event(
        self,
        *,
        source: deque[HistoryEvent],
        destination: deque[HistoryEvent],
        expected_event: HistoryEvent,
        snapshot: _HistoryMutationSnapshot,
    ) -> None:
        """Move an applied event between stacks after its mutation succeeds."""
        if not source or source[-1] is not expected_event:
            self._restore_failed_history_apply(snapshot)
            msg = "History stacks changed while applying an Undo/Redo event."
            raise RuntimeError(msg)
        source.pop()
        destination.append(expected_event)

    def _notify_state_change(self, *, isolate_errors: bool = False) -> None:
        """Notify all subscribers of state change."""
        if self._atomic_recording_depth > 0:
            self._notification_pending = True
            return
        self._dispatch_state_change(isolate_errors=isolate_errors)

    def _dispatch_state_change(self, *, isolate_errors: bool) -> None:
        """Dispatch a committed history state to every subscriber."""
        state = self.get_state()
        for callback in tuple(self._subscribers):
            if not isolate_errors:
                callback(state)
                continue
            try:
                callback(state)
            except Exception:
                logger.exception("History state subscriber failed during isolated notification")
