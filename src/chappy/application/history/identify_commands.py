"""Typed history commands for identify operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.core.history.operation_id import OperationId

from .models import (
    ChangeSet,
    HistoryApplyError,
    HistoryApplyResult,
    HistoryRefreshTarget,
    recoverable_history_apply_failure,
)

if TYPE_CHECKING:
    from chappy.application.identify import TemporaryLineSnapshot

    from .ports import AbsorptionLineSnapshot, AbsorptionRegionSnapshot, HistoryCommandContext


@dataclass(frozen=True, slots=True)
class IdentifyAddTemporaryLineCommand:
    """History command for adding identify temporary lines."""

    snapshots: tuple[TemporaryLineSnapshot, ...]

    @property
    def operation_id(self) -> OperationId:
        """Return the identify temporary-line add operation identifier."""
        return OperationId.IDENT_ADD_TEMPORARY_LINE

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore added identify temporary lines."""
        return _restore_temporary_lines(context, self.snapshots)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Remove added identify temporary lines."""
        return _remove_temporary_lines(context, _temporary_line_ids(self.snapshots))

    def is_noop(self) -> bool:
        """Return whether the command has no temporary-line snapshots."""
        return not self.snapshots

    def coalesced_with(
        self, next_command: IdentifyAddTemporaryLineCommand
    ) -> IdentifyAddTemporaryLineCommand | None:
        """Identify temporary-line additions are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class IdentifyRemoveTemporaryLineCommand:
    """History command for removing identify temporary lines."""

    temporary_line_ids: tuple[str, ...]
    snapshots: tuple[TemporaryLineSnapshot, ...]

    @property
    def operation_id(self) -> OperationId:
        """Return the identify temporary-line remove operation identifier."""
        return OperationId.IDENT_REMOVE_TEMPORARY_LINE

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Remove identify temporary lines."""
        return _remove_temporary_lines(context, self.temporary_line_ids)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore removed identify temporary lines."""
        return _restore_temporary_lines(context, self.snapshots)

    def is_noop(self) -> bool:
        """Return whether the command has no temporary-line snapshots."""
        return not self.snapshots

    def coalesced_with(
        self, next_command: IdentifyRemoveTemporaryLineCommand
    ) -> IdentifyRemoveTemporaryLineCommand | None:
        """Identify temporary-line removals are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class IdentifyClearTemporaryLinesCommand:
    """History command for clearing identify temporary lines."""

    snapshots: tuple[TemporaryLineSnapshot, ...]

    @property
    def operation_id(self) -> OperationId:
        """Return the identify temporary-line clear operation identifier."""
        return OperationId.IDENT_CLEAR_TEMPORARY_LINES

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Clear identify temporary lines."""
        identify_port = context.require_identify_port()
        try:
            change_set = identify_port.clear_identify_temporary_lines()
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _identify_result(change_set)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore cleared identify temporary lines."""
        return _restore_temporary_lines(context, self.snapshots)

    def is_noop(self) -> bool:
        """Return whether the command has no temporary-line snapshots."""
        return not self.snapshots

    def coalesced_with(
        self, next_command: IdentifyClearTemporaryLinesCommand
    ) -> IdentifyClearTemporaryLinesCommand | None:
        """Identify temporary-line clears are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class IdentifyRegisterSelectedCommand:
    """History command for registering selected identify temporary lines."""

    created_line_ids: tuple[str, ...]
    removed_temporary_line_ids: tuple[str, ...]
    temporary_line_snapshots: tuple[TemporaryLineSnapshot, ...]
    affected_region_ids: tuple[str, ...]
    line_snapshots: tuple[AbsorptionLineSnapshot, ...]
    before_affected_region_snapshots: tuple[AbsorptionRegionSnapshot, ...]
    after_affected_region_snapshots: tuple[AbsorptionRegionSnapshot, ...]

    @property
    def operation_id(self) -> OperationId:
        """Return the identify register operation identifier."""
        return OperationId.IDENT_REGISTER_SELECTED

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Reapply temporary-line registration."""
        identify_port = context.require_identify_port()
        structure_port = context.require_structure_port()
        try:
            temporary_line_changes = identify_port.remove_identify_temporary_lines(
                self.removed_temporary_line_ids
            )
            before_ids = {snapshot.region_id for snapshot in self.before_affected_region_snapshots}
            created_regions = tuple(
                snapshot
                for snapshot in self.after_affected_region_snapshots
                if snapshot.region_id not in before_ids
            )
            region_changes = structure_port.restore_absorption_regions(created_regions)
            line_changes = structure_port.restore_absorption_lines(
                self.line_snapshots, restore_multiplet_links=True
            )
            analysis_changes = structure_port.apply_absorption_region_states_partial_exact(
                self.after_affected_region_snapshots
            )
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _registration_result(
            _merge_change_sets(
                temporary_line_changes, region_changes, line_changes, analysis_changes
            )
        )

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Revert temporary-line registration."""
        identify_port = context.require_identify_port()
        structure_port = context.require_structure_port()
        try:
            line_changes = structure_port.remove_absorption_lines(
                self.created_line_ids, delete_models=False
            )
            temporary_line_changes = identify_port.restore_identify_temporary_lines(
                self.temporary_line_snapshots
            )
            analysis_changes = structure_port.apply_absorption_region_states_partial_exact(
                self.before_affected_region_snapshots
            )
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _registration_result(
            _merge_change_sets(line_changes, temporary_line_changes, analysis_changes)
        )

    def is_noop(self) -> bool:
        """Return whether the command has no created or temporary lines."""
        return not self.created_line_ids and not self.temporary_line_snapshots

    def coalesced_with(
        self, next_command: IdentifyRegisterSelectedCommand
    ) -> IdentifyRegisterSelectedCommand | None:
        """Identify registration commands are not coalesced."""
        _ = next_command
        return None


def _temporary_line_ids(snapshots: tuple[TemporaryLineSnapshot, ...]) -> tuple[str, ...]:
    """Return temporary-line IDs from snapshots."""
    return tuple(snapshot.temporary_line_id for snapshot in snapshots)


def _restore_temporary_lines(
    context: HistoryCommandContext, snapshots: tuple[TemporaryLineSnapshot, ...]
) -> HistoryApplyResult:
    """Restore identify temporary lines through the identify port."""
    identify_port = context.require_identify_port()
    try:
        change_set = identify_port.restore_identify_temporary_lines(snapshots)
    except HistoryApplyError as error:
        return recoverable_history_apply_failure(error)
    return _identify_result(change_set)


def _remove_temporary_lines(
    context: HistoryCommandContext, temporary_line_ids: tuple[str, ...]
) -> HistoryApplyResult:
    """Remove identify temporary lines through the identify port."""
    identify_port = context.require_identify_port()
    try:
        change_set = identify_port.remove_identify_temporary_lines(temporary_line_ids)
    except HistoryApplyError as error:
        return recoverable_history_apply_failure(error)
    return _identify_result(change_set)


def _identify_result(change_set: ChangeSet) -> HistoryApplyResult:
    """Return an identify-panel refresh result."""
    return HistoryApplyResult.ok(
        change_set=change_set, refresh_targets=(HistoryRefreshTarget.IDENTIFY_PANEL,)
    )


def _registration_result(change_set: ChangeSet) -> HistoryApplyResult:
    """Return an identify registration refresh result."""
    return HistoryApplyResult.ok(
        change_set=change_set, refresh_targets=(HistoryRefreshTarget.IDENTIFY_PANEL,)
    )


def _merge_change_sets(*change_sets: ChangeSet) -> ChangeSet:
    """Merge change sets while preserving first-seen order."""
    component_ids: list[str] = []
    line_ids: list[str] = []
    region_ids: list[str] = []
    temporary_line_ids: list[str] = []
    continuum_ids: list[str] = []
    for change_set in change_sets:
        _extend_unique(component_ids, change_set.changed_component_ids)
        _extend_unique(line_ids, change_set.changed_line_ids)
        _extend_unique(region_ids, change_set.changed_region_ids)
        _extend_unique(temporary_line_ids, change_set.changed_temporary_line_ids)
        _extend_unique(continuum_ids, change_set.changed_continuum_ids)
    return ChangeSet(
        changed_component_ids=tuple(component_ids),
        changed_line_ids=tuple(line_ids),
        changed_region_ids=tuple(region_ids),
        changed_temporary_line_ids=tuple(temporary_line_ids),
        changed_continuum_ids=tuple(continuum_ids),
    )


def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
    """Append values not already present in the target list."""
    for value in values:
        if value not in target:
            target.append(value)
