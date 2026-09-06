"""Typed history commands for structure operations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from chappy.core.history.operation_id import OperationId

from .models import (
    ChangeSet,
    HistoryApplyError,
    HistoryApplyResult,
    HistoryRefreshTarget,
    recoverable_history_apply_failure,
)
from .ports import (
    LineRegionAssignment,
    StructureMoveHistoryPayload,
    StructureStateSnapshot,
    StructureUnlinkHistoryPayload,
)

if TYPE_CHECKING:
    from .model_commands import ModelComponentHistoryCommand
    from .ports import (
        AbsorptionLineSnapshot,
        AbsorptionRegionSnapshot,
        HistoryCommandContext,
        MaskDefinitionSnapshot,
        MultipletLinkSnapshot,
        StructureHistoryPort,
    )


@dataclass(frozen=True, slots=True)
class StructureMoveLinkedLinesCommand:
    """History command for moving structure linked lines between regions."""

    payload: StructureMoveHistoryPayload

    @property
    def operation_id(self) -> OperationId:
        """Return the structure move operation identifier."""
        return OperationId.STRUCTURE_MOVE_LINKED_LINES

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Move lines to the destination region."""
        structure_port = context.require_structure_port()
        try:
            if self.payload.created_new_region:
                structure_port.ensure_absorption_region(
                    self.payload.destination_region_id, color=self.payload.new_region_color
                )
            change_set = structure_port.apply_line_region_assignments(
                self.payload.destination_assignments
            )
            structure_port.apply_absorption_region_states_exact(self.payload.destination_regions)
            structure_port.replace_masks_exact(self.payload.destination_masks)
            structure_port.apply_absorber_component_groups(
                self.payload.destination_component_groups
            )
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _structure_result(change_set)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore previous line assignments and auto-deleted objects."""
        structure_port = context.require_structure_port()
        try:
            structure_port.restore_absorption_regions(self.payload.auto_deleted_regions)
            change_set = structure_port.apply_line_region_assignments(
                self.payload.source_assignments
            )
            structure_port.apply_absorption_region_states_exact(self.payload.source_regions)
            structure_port.replace_masks_exact(self.payload.source_masks)
            structure_port.apply_absorber_component_groups(self.payload.source_component_groups)
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _structure_result(change_set)

    def is_noop(self) -> bool:
        """Return whether source and destination assignments are equal."""
        return self.payload.source_assignments == self.payload.destination_assignments

    def coalesced_with(
        self, next_command: StructureMoveLinkedLinesCommand
    ) -> StructureMoveLinkedLinesCommand | None:
        """Structure moves are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class StructureSplitCommand:
    """History command for splitting selected structure linked lines into a new region."""

    expanded_line_ids: tuple[str, ...]
    source_region_id: str
    new_region_id: str
    before: StructureStateSnapshot
    after: StructureStateSnapshot

    @property
    def operation_id(self) -> OperationId:
        """Return the structure split operation identifier."""
        return OperationId.STRUCTURE_SPLIT

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Move selected lines into the split region."""
        return _apply_structure_transition(context, source=self.before, target=self.after)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Move selected lines back to the source region."""
        return _apply_structure_transition(context, source=self.after, target=self.before)

    def is_noop(self) -> bool:
        """Return whether the command changes no lines."""
        return not self.expanded_line_ids

    def coalesced_with(self, next_command: StructureSplitCommand) -> StructureSplitCommand | None:
        """Structure splits are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class StructureMergeCommand:
    """History command for merging structure regions."""

    primary_region_id: str
    secondary_region_ids: tuple[str, ...]
    before: StructureStateSnapshot
    after: StructureStateSnapshot

    @property
    def operation_id(self) -> OperationId:
        """Return the structure merge operation identifier."""
        return OperationId.STRUCTURE_MERGE

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Move secondary contents into the primary region."""
        return _apply_structure_transition(context, source=self.before, target=self.after)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore secondary regions and original assignments."""
        return _apply_structure_transition(context, source=self.after, target=self.before)

    def is_noop(self) -> bool:
        """Return whether there are no secondary regions."""
        return not self.secondary_region_ids

    def coalesced_with(self, next_command: StructureMergeCommand) -> StructureMergeCommand | None:
        """Structure merges are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class StructureDeleteCommand:
    """History command for deleting structure regions or linked lines."""

    target_region_ids: tuple[str, ...]
    target_line_ids: tuple[str, ...]
    deleted_lines: tuple[AbsorptionLineSnapshot, ...]
    before: StructureStateSnapshot
    after: StructureStateSnapshot
    model_command: ModelComponentHistoryCommand | None = None

    @property
    def operation_id(self) -> OperationId:
        """Return the structure delete operation identifier."""
        return OperationId.STRUCTURE_DELETE

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Delete target lines and regions again."""
        structure_port = context.require_structure_port()
        try:
            if self.model_command is not None:
                model_result = self.model_command.redo(context)
                if not model_result.success:
                    return model_result
            deleted_line_ids = tuple(snapshot.line_id for snapshot in self.deleted_lines)
            structure_port.remove_absorption_lines(deleted_line_ids, delete_models=False)
            structure_port.remove_absorption_regions(
                _removed_region_ids(self.before, self.after), delete_models=False
            )
            change_set = _apply_structure_fields(structure_port, self.after)
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _structure_result(change_set)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore deleted structure data."""
        structure_port = context.require_structure_port()
        try:
            structure_port.restore_absorption_regions(
                _created_region_snapshots(self.after, self.before)
            )
            restored_lines = self.deleted_lines
            if self.model_command is not None:
                restored_lines = tuple(
                    replace(snapshot, model_ids=()) for snapshot in self.deleted_lines
                )
            structure_port.restore_absorption_lines(restored_lines, restore_multiplet_links=True)
            if self.model_command is not None:
                model_result = self.model_command.undo(context)
                if not model_result.success:
                    return model_result
            change_set = _apply_structure_fields(structure_port, self.before)
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _structure_result(change_set)

    def is_noop(self) -> bool:
        """Return whether there is nothing to delete."""
        return not self.target_region_ids and not self.target_line_ids

    def coalesced_with(
        self, next_command: StructureDeleteCommand
    ) -> StructureDeleteCommand | None:
        """Structure deletes are not coalesced."""
        _ = next_command
        return None


@dataclass(frozen=True, slots=True)
class StructureUnlinkLinkedLinesCommand:
    """History command for removing one materialized linked-line group."""

    payload: StructureUnlinkHistoryPayload

    @property
    def operation_id(self) -> OperationId:
        """Return the structure unlink operation identifier."""
        return OperationId.STRUCTURE_UNLINK_LINKED_LINES

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Apply the unlinked line topology."""
        return self._apply(context, self.payload.after_links)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore the linked line topology."""
        return self._apply(context, self.payload.before_links)

    def is_noop(self) -> bool:
        """Return whether link topology is unchanged."""
        return self.payload.before_links == self.payload.after_links

    def coalesced_with(
        self, next_command: StructureUnlinkLinkedLinesCommand
    ) -> StructureUnlinkLinkedLinesCommand | None:
        """Structure unlink commands are not coalesced."""
        _ = next_command
        return None

    def _apply(
        self, context: HistoryCommandContext, snapshots: tuple[MultipletLinkSnapshot, ...]
    ) -> HistoryApplyResult:
        """Apply one exact link state through the structure port."""
        structure_port = context.require_structure_port()
        try:
            change_set = structure_port.apply_multiplet_links_exact(
                self.payload.line_ids, snapshots
            )
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return _structure_result(change_set)


@dataclass(frozen=True, slots=True)
class MaskHistoryCommand:
    """History command for one forward mask create, update, or remove."""

    op_id: OperationId
    mask_id: str
    before: MaskDefinitionSnapshot | None
    after: MaskDefinitionSnapshot | None
    before_index: int | None
    after_index: int | None
    affected_region_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require one of the dedicated user-visible mask operation IDs."""
        if not self.mask_id:
            msg = "Mask history requires a stable mask identity."
            raise ValueError(msg)
        allowed = {OperationId.MASK_CREATE, OperationId.MASK_EDIT, OperationId.MASK_DELETE}
        if self.op_id not in allowed:
            msg = f"Unsupported mask history operation: {self.op_id}"
            raise ValueError(msg)
        expected_presence = {
            OperationId.MASK_CREATE: (False, True),
            OperationId.MASK_EDIT: (True, True),
            OperationId.MASK_DELETE: (True, False),
        }
        before_present, after_present = expected_presence[self.op_id]
        if (self.before is not None, self.after is not None) != (before_present, after_present):
            msg = f"Mask history states do not match operation: {self.op_id}"
            raise ValueError(msg)
        for label, snapshot, index in (
            ("before", self.before, self.before_index),
            ("after", self.after, self.after_index),
        ):
            if (snapshot is None) != (index is None):
                msg = f"Mask history {label} snapshot and index must have equal presence."
                raise ValueError(msg)
            if index is not None and index < 0:
                msg = f"Mask history {label} index cannot be negative."
                raise ValueError(msg)
            if snapshot is not None and snapshot.identifier != self.mask_id:
                msg = f"Mask history {label} snapshot identity does not match mask_id."
                raise ValueError(msg)
        normalized_region_ids = tuple(dict.fromkeys(self.affected_region_ids))
        snapshot_region_ids = tuple(
            dict.fromkeys(
                snapshot.group_id
                for snapshot in (self.before, self.after)
                if snapshot is not None and snapshot.group_id is not None
            )
        )
        if (
            not normalized_region_ids
            or any(not region_id for region_id in normalized_region_ids)
            or set(normalized_region_ids) != set(snapshot_region_ids)
        ):
            msg = "Mask history affected regions must exactly match its before/after groups."
            raise ValueError(msg)
        object.__setattr__(self, "affected_region_ids", normalized_region_ids)

    @property
    def operation_id(self) -> OperationId:
        """Return the dedicated create, edit, or delete operation identifier."""
        return self.op_id

    @property
    def qualifier(self) -> str | None:
        """Return no operation qualifier."""
        return None

    def redo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Apply the mask after-state."""
        return self._apply(context, self.after, self.after_index)

    def undo(self, context: HistoryCommandContext) -> HistoryApplyResult:
        """Restore the mask before-state."""
        return self._apply(context, self.before, self.before_index)

    def is_noop(self) -> bool:
        """Return whether the mask snapshot did not change."""
        return self.before == self.after and self.before_index == self.after_index

    def coalesced_with(self, next_command: MaskHistoryCommand) -> MaskHistoryCommand | None:
        """Mask edits are not coalesced."""
        _ = next_command
        return None

    def _apply(
        self,
        context: HistoryCommandContext,
        snapshot: MaskDefinitionSnapshot | None,
        index: int | None,
    ) -> HistoryApplyResult:
        """Apply one mask state through the structure history boundary."""
        structure_port = context.require_structure_port()
        try:
            change_set = structure_port.restore_mask_state(self.mask_id, snapshot, index=index)
        except HistoryApplyError as error:
            return recoverable_history_apply_failure(error)
        return HistoryApplyResult.ok(
            change_set=change_set, refresh_targets=(HistoryRefreshTarget.OPTIMIZE_PANEL,)
        )


def _apply_structure_transition(
    context: HistoryCommandContext,
    *,
    source: StructureStateSnapshot,
    target: StructureStateSnapshot,
) -> HistoryApplyResult:
    """Apply one exact split or merge temporal state."""
    structure_port = context.require_structure_port()
    try:
        structure_port.restore_absorption_regions(_created_region_snapshots(source, target))
        assignments = _changed_line_assignments(source, target)
        if assignments:
            structure_port.apply_line_region_assignments(assignments)
        for region_id in _removed_region_ids(source, target):
            structure_port.remove_empty_absorption_region(region_id)
        change_set = _apply_structure_fields(structure_port, target)
    except HistoryApplyError as error:
        return recoverable_history_apply_failure(error)
    return _structure_result(change_set)


def _apply_structure_fields(
    structure_port: StructureHistoryPort, state: StructureStateSnapshot
) -> ChangeSet:
    """Apply exact ordered structure fields after identities and memberships match."""
    # The object is obtained from HistoryCommandContext.require_structure_port(); keeping
    # the helper local avoids exposing a second broad public history port.
    structure_port.apply_absorption_line_order_exact(
        tuple(snapshot.line_id for snapshot in state.lines)
    )
    structure_port.apply_absorption_region_states_exact(state.regions)
    structure_port.replace_masks_exact(state.masks)
    return structure_port.apply_absorber_component_groups(state.component_groups)


def _created_region_snapshots(
    source: StructureStateSnapshot, target: StructureStateSnapshot
) -> tuple[AbsorptionRegionSnapshot, ...]:
    """Return target regions absent from the source topology."""
    source_ids = {snapshot.region_id for snapshot in source.regions}
    return tuple(snapshot for snapshot in target.regions if snapshot.region_id not in source_ids)


def _removed_region_ids(
    source: StructureStateSnapshot, target: StructureStateSnapshot
) -> tuple[str, ...]:
    """Return source region identities absent from the target topology."""
    target_ids = {snapshot.region_id for snapshot in target.regions}
    return tuple(
        snapshot.region_id for snapshot in source.regions if snapshot.region_id not in target_ids
    )


def _changed_line_assignments(
    source: StructureStateSnapshot, target: StructureStateSnapshot
) -> tuple[LineRegionAssignment, ...]:
    """Derive exact changed line assignments from two complete region snapshots."""
    source_regions = {
        line_id: region.region_id for region in source.regions for line_id in region.line_ids
    }
    target_regions = {
        line_id: region.region_id for region in target.regions for line_id in region.line_ids
    }
    return tuple(
        LineRegionAssignment(line_id=line_id, region_id=target_region_id)
        for line_id, target_region_id in target_regions.items()
        if source_regions.get(line_id) != target_region_id
    )


def _structure_result(change_set: ChangeSet) -> HistoryApplyResult:
    """Return a standard successful structure command result."""
    return HistoryApplyResult.ok(change_set=change_set)
