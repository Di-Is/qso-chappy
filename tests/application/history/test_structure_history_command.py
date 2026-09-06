"""Tests for typed structure history commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from chappy.application.history import (
    AbsorberComponentGroupAssignment,
    AbsorptionLineSnapshot,
    AbsorptionRegionSnapshot,
    StructureDeleteCommand,
    StructureMergeCommand,
    StructureLineTopologySnapshot,
    StructureMoveHistoryPayload,
    StructureMoveLinkedLinesCommand,
    StructureSplitCommand,
    StructureStateSnapshot,
    StructureUnlinkHistoryPayload,
    StructureUnlinkLinkedLinesCommand,
    ChangeSet,
    HistoryCommandContext,
    LineRegionAssignment,
    MaskHistoryCommand,
    MaskDefinitionSnapshot,
    MultipletLinkSnapshot,
)
from chappy.core.history import OperationId


@dataclass(slots=True)
class _StructurePort:
    """Structure history port test double."""

    restored_regions: list[tuple[AbsorptionRegionSnapshot, ...]] = field(default_factory=list)
    restored_lines: list[tuple[AbsorptionLineSnapshot, ...]] = field(default_factory=list)
    exact_line_orders: list[tuple[str, ...]] = field(default_factory=list)
    restored_masks: list[tuple[MaskDefinitionSnapshot, ...]] = field(default_factory=list)
    exact_regions: list[tuple[AbsorptionRegionSnapshot, ...]] = field(default_factory=list)
    exact_masks: list[tuple[MaskDefinitionSnapshot, ...]] = field(default_factory=list)
    exact_groups: list[tuple[AbsorberComponentGroupAssignment, ...]] = field(default_factory=list)
    restored_mask_states: list[tuple[str, MaskDefinitionSnapshot | None, int | None]] = field(
        default_factory=list
    )
    ensured_regions: list[tuple[str, str | None]] = field(default_factory=list)
    assignments: list[tuple[LineRegionAssignment, ...]] = field(default_factory=list)
    empty_removed: list[str] = field(default_factory=list)
    removed_lines: list[tuple[str, ...]] = field(default_factory=list)
    removed_regions: list[tuple[str, ...]] = field(default_factory=list)
    restored_links: list[tuple[MultipletLinkSnapshot, ...]] = field(default_factory=list)
    exact_links: list[tuple[tuple[str, ...], tuple[MultipletLinkSnapshot, ...]]] = field(
        default_factory=list
    )

    def restore_absorption_regions(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Record restored regions."""
        self.restored_regions.append(snapshots)
        return ChangeSet(changed_region_ids=tuple(snapshot.region_id for snapshot in snapshots))

    def restore_absorption_lines(
        self, snapshots: tuple[AbsorptionLineSnapshot, ...], *, restore_multiplet_links: bool
    ) -> ChangeSet:
        """Record restored lines."""
        _ = restore_multiplet_links
        self.restored_lines.append(snapshots)
        return ChangeSet(changed_line_ids=tuple(snapshot.line_id for snapshot in snapshots))

    def apply_absorption_region_states_exact(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Record exact region state application."""
        self.exact_regions.append(snapshots)
        return ChangeSet.empty()

    def apply_absorption_line_order_exact(self, line_ids: tuple[str, ...]) -> ChangeSet:
        """Record exact line order application."""
        self.exact_line_orders.append(line_ids)
        return ChangeSet(changed_line_ids=line_ids)

    def restore_masks(self, snapshots: tuple[MaskDefinitionSnapshot, ...]) -> ChangeSet:
        """Record restored masks."""
        self.restored_masks.append(snapshots)
        return ChangeSet.empty()

    def replace_masks_exact(self, snapshots: tuple[MaskDefinitionSnapshot, ...]) -> ChangeSet:
        """Record exact mask replacement."""
        self.exact_masks.append(snapshots)
        return ChangeSet.empty()

    def apply_absorber_component_groups(
        self, assignments: tuple[AbsorberComponentGroupAssignment, ...]
    ) -> ChangeSet:
        """Record exact component group application."""
        self.exact_groups.append(assignments)
        return ChangeSet.empty()

    def restore_mask_state(
        self, mask_id: str, snapshot: MaskDefinitionSnapshot | None, *, index: int | None
    ) -> ChangeSet:
        """Record one restored or removed mask state."""
        self.restored_mask_states.append((mask_id, snapshot, index))
        region_ids = (
            (snapshot.group_id,) if snapshot is not None and snapshot.group_id is not None else ()
        )
        return ChangeSet(changed_region_ids=region_ids)

    def ensure_absorption_region(self, region_id: str, *, color: str | None) -> ChangeSet:
        """Record ensured region."""
        self.ensured_regions.append((region_id, color))
        return ChangeSet(changed_region_ids=(region_id,))

    def apply_line_region_assignments(
        self, assignments: tuple[LineRegionAssignment, ...]
    ) -> ChangeSet:
        """Record line assignments."""
        self.assignments.append(assignments)
        return ChangeSet(changed_line_ids=tuple(item.line_id for item in assignments))

    def remove_empty_absorption_region(self, region_id: str) -> ChangeSet:
        """Record empty region removal."""
        self.empty_removed.append(region_id)
        return ChangeSet(changed_region_ids=(region_id,))

    def remove_absorption_lines(
        self, line_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        """Record line removal."""
        _ = delete_models
        self.removed_lines.append(line_ids)
        return ChangeSet(changed_line_ids=line_ids)

    def remove_absorption_regions(
        self, region_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        """Record region removal."""
        _ = delete_models
        self.removed_regions.append(region_ids)
        return ChangeSet(changed_region_ids=region_ids)

    def restore_multiplet_links(self, snapshots: tuple[MultipletLinkSnapshot, ...]) -> ChangeSet:
        """Record restored multiplet links."""
        self.restored_links.append(snapshots)
        return ChangeSet(changed_line_ids=tuple(snapshot.line_id for snapshot in snapshots))

    def apply_multiplet_links_exact(
        self, line_ids: tuple[str, ...], snapshots: tuple[MultipletLinkSnapshot, ...]
    ) -> ChangeSet:
        """Record one exact multiplet link state."""
        self.exact_links.append((line_ids, snapshots))
        return ChangeSet(changed_line_ids=line_ids)


def _region_snapshot(region_id: str) -> AbsorptionRegionSnapshot:
    """Create one region snapshot."""
    return AbsorptionRegionSnapshot(
        region_id=region_id,
        line_ids=("line-1",),
        display_color="#123456",
        analysis_range=(1000.0, 1010.0),
        created_at=datetime.now(UTC),
    )


def _line_snapshot(line_id: str) -> AbsorptionLineSnapshot:
    """Create one line snapshot."""
    return AbsorptionLineSnapshot(
        line_id=line_id,
        species="C IV",
        rest_wavelength=1548.2,
        center_z=2.0,
        window_kms=120.0,
        multiplet_label="C IV",
        transition_name="C IV 1548",
        oscillator_strength=0.19,
        gamma_value=1.0e8,
        lambda_range=(4640.0, 4660.0),
        region_id="region-1",
        multiplet_ids=(),
        model_ids=(),
        needs_optimization=True,
        created_by="test",
        created_at=datetime.now(UTC),
    )


def _mask_snapshot(mask_id: str, group_id: str) -> MaskDefinitionSnapshot:
    """Create one mask snapshot."""
    return MaskDefinitionSnapshot(
        identifier=mask_id,
        label="mask",
        mode="range",
        start_wavelength=1000.0,
        end_wavelength=1010.0,
        center=1005.0,
        half_width=5.0,
        note="",
        color="#abcdef",
        enabled=True,
        group_id=group_id,
    )


def test_structure_move_command_redo_and_undo_use_typed_assignments() -> None:
    """Structure move command should apply destination and source assignments."""
    port = _StructurePort()
    context = HistoryCommandContext(structure_port=port)
    source = (LineRegionAssignment("line-1", "source"),)
    destination = (LineRegionAssignment("line-1", "target"),)
    auto_deleted_region = (_region_snapshot("source"),)
    auto_deleted_mask = (_mask_snapshot("mask-1", "source"),)
    command = StructureMoveLinkedLinesCommand(
        payload=StructureMoveHistoryPayload(
            expanded_line_ids=("line-1",),
            source_assignments=source,
            destination_assignments=destination,
            source_regions=auto_deleted_region,
            destination_regions=(_region_snapshot("target"),),
            source_masks=auto_deleted_mask,
            destination_masks=(),
            source_component_groups=(),
            destination_component_groups=(),
        )
    )

    assert command.redo(context).success
    assert command.undo(context).success

    assert port.ensured_regions == [("target", "#123456")]
    assert port.assignments == [destination, source]
    assert port.restored_regions == [auto_deleted_region]
    assert port.exact_masks == [(), auto_deleted_mask]


def test_mask_history_command_preserves_distinct_operation_and_typed_states() -> None:
    """Mask create/edit/delete commands expose distinct operation names and states."""
    port = _StructurePort()
    context = HistoryCommandContext(structure_port=port)
    before = _mask_snapshot("mask-1", "region-1")
    after = _mask_snapshot("mask-1", "region-2")
    commands = (
        MaskHistoryCommand(
            op_id=OperationId.MASK_CREATE,
            mask_id="mask-1",
            before=None,
            after=before,
            before_index=None,
            after_index=0,
            affected_region_ids=("region-1",),
        ),
        MaskHistoryCommand(
            op_id=OperationId.MASK_EDIT,
            mask_id="mask-1",
            before=before,
            after=after,
            before_index=0,
            after_index=0,
            affected_region_ids=("region-1", "region-2"),
        ),
        MaskHistoryCommand(
            op_id=OperationId.MASK_DELETE,
            mask_id="mask-1",
            before=after,
            after=None,
            before_index=0,
            after_index=None,
            affected_region_ids=("region-2",),
        ),
    )

    for command in commands:
        assert command.redo(context).success
        assert command.undo(context).success

    assert tuple(command.operation_id for command in commands) == (
        OperationId.MASK_CREATE,
        OperationId.MASK_EDIT,
        OperationId.MASK_DELETE,
    )
    assert port.restored_mask_states == [
        ("mask-1", before, 0),
        ("mask-1", None, None),
        ("mask-1", after, 0),
        ("mask-1", before, 0),
        ("mask-1", None, None),
        ("mask-1", after, 0),
    ]


def test_structure_split_merge_delete_commands_route_to_structure_port() -> None:
    """Structure split, merge, and delete commands should use typed structure port calls."""
    port = _StructurePort()
    context = HistoryCommandContext(structure_port=port)
    source_state = StructureStateSnapshot(
        regions=(_region_snapshot("source"),),
        lines=(StructureLineTopologySnapshot("line-1", "source", (), ()),),
        masks=(_mask_snapshot("mask-1", "source"),),
        component_groups=(),
    )
    split_state = StructureStateSnapshot(
        regions=(_region_snapshot("new"),),
        lines=(StructureLineTopologySnapshot("line-1", "new", (), ()),),
        masks=(),
        component_groups=(),
    )
    split = StructureSplitCommand(
        expanded_line_ids=("line-1",),
        source_region_id="source",
        new_region_id="new",
        before=source_state,
        after=split_state,
    )
    merge_before = StructureStateSnapshot(
        regions=(_region_snapshot("primary"), _region_snapshot("secondary")),
        lines=(StructureLineTopologySnapshot("line-1", "secondary", (), ()),),
        masks=(_mask_snapshot("mask-2", "secondary"),),
        component_groups=(),
    )
    merge_after = StructureStateSnapshot(
        regions=(_region_snapshot("primary"),),
        lines=(StructureLineTopologySnapshot("line-1", "primary", (), ()),),
        masks=(_mask_snapshot("mask-2", "primary"),),
        component_groups=(),
    )
    merge = StructureMergeCommand(
        primary_region_id="primary",
        secondary_region_ids=("secondary",),
        before=merge_before,
        after=merge_after,
    )
    delete_before = StructureStateSnapshot(
        regions=(_region_snapshot("region-1"),),
        lines=(StructureLineTopologySnapshot("line-1", "region-1", (), ()),),
        masks=(_mask_snapshot("mask-3", "region-1"),),
        component_groups=(),
    )
    delete_after = StructureStateSnapshot(regions=(), lines=(), masks=(), component_groups=())
    delete = StructureDeleteCommand(
        target_region_ids=("region-1",),
        target_line_ids=("line-1",),
        deleted_lines=(_line_snapshot("line-1"),),
        before=delete_before,
        after=delete_after,
    )

    assert split.redo(context).success
    assert split.undo(context).success
    assert merge.redo(context).success
    assert merge.undo(context).success
    assert delete.redo(context).success
    assert delete.undo(context).success

    assert port.empty_removed == ["source", "new", "secondary"]
    assert port.removed_regions == [("region-1",)]
    assert port.removed_lines == [("line-1",)]
    assert [snapshot.line_id for snapshot in port.restored_lines[0]] == ["line-1"]


def test_structure_unlink_command_applies_exact_before_and_after_links() -> None:
    """Unlink history should preserve the closed ordered link topology."""
    port = _StructurePort()
    context = HistoryCommandContext(structure_port=port)
    before = (
        MultipletLinkSnapshot("line-1", ("line-2",)),
        MultipletLinkSnapshot("line-2", ("line-1",)),
    )
    after = (MultipletLinkSnapshot("line-1", ()), MultipletLinkSnapshot("line-2", ()))
    command = StructureUnlinkLinkedLinesCommand(
        StructureUnlinkHistoryPayload(
            line_ids=("line-1", "line-2"),
            affected_region_ids=("region-1",),
            before_links=before,
            after_links=after,
        )
    )

    assert command.redo(context).success
    assert command.undo(context).success
    assert port.exact_links == [(("line-1", "line-2"), after), (("line-1", "line-2"), before)]
