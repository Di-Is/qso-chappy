"""Structure move/split/merge/delete/unlink structure history application."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.application.history import (
    AbsorberComponentGroupAssignment,
    AbsorptionRegionSnapshot,
    HistoryApplyError,
    HistoryApplyErrorCode,
    LineRegionAssignment,
    MaskDefinitionSnapshot,
    MultipletLinkSnapshot,
    StructureDeleteCommand,
    StructureMergeCommand,
    StructureMoveLinkedLinesCommand,
    StructureSplitCommand,
    StructureStateSnapshot,
    StructureUnlinkHistoryPayload,
)
from chappy.application.history.apply.model_apply import model_component_temporal_state_matches
from chappy.application.history.snapshot_mapping import (
    absorption_region_snapshot,
    mask_definition_snapshot,
)
from chappy.application.structure import (
    StructureInvalidationScope,
    StructureMutationOutcome,
    StructureMutationResult,
    StructureRegionDelta,
    StructureTopologySnapshot,
)
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.change_set import ChangeSet as DomainChangeSet
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.events import (
    ComponentAdded,
    ComponentChanged,
    ComponentRemoved,
    DomainEvent,
    MasksChanged,
)

if TYPE_CHECKING:
    from chappy.application.history import (
        HistoryApplyResult,
        HistoryCommandContext,
        StructureUnlinkLinkedLinesCommand,
    )
    from chappy.application.structure import (
        AtomicStructureMutationExecutor,
        StructureTopologySnapshotService,
    )
    from chappy.core.spectroscopy_project import SpectroscopyProject


def structure_history_delta(
    project: SpectroscopyProject,
    *,
    before_region_ids: tuple[str, ...],
    before_memberships: dict[str, tuple[str, ...]],
    before_multiplet_links: dict[str, tuple[str, ...]],
    invalidation_scope: StructureInvalidationScope,
) -> StructureRegionDelta:
    """Derive exact history topology delta from captured runtime state."""
    after_region_ids = tuple(project.absorption_regions)
    before = set(before_region_ids)
    after = set(after_region_ids)
    surviving = before & after
    membership_changed = {
        region_id
        for region_id in after_region_ids
        if region_id in surviving
        and before_memberships[region_id] != tuple(project.absorption_regions[region_id].line_ids)
    }
    changed_surviving_line_ids = tuple(
        line_id
        for line_id, line in project.absorption_lines.items()
        if line_id in before_multiplet_links
        and before_multiplet_links[line_id] != tuple(line.multiplet_ids)
    )
    link_changed_regions = {
        project.absorption_lines[line_id].region_id
        for line_id in changed_surviving_line_ids
        if project.absorption_lines[line_id].region_id in surviving
    }
    affected = tuple(
        region_id
        for region_id in after_region_ids
        if region_id in membership_changed | link_changed_regions
    )
    return StructureRegionDelta(
        invalidation_scope=invalidation_scope,
        affected_surviving_region_ids=(
            affected if invalidation_scope is StructureInvalidationScope.LOCAL_SURVIVORS else ()
        ),
        created_region_ids=tuple(
            region_id for region_id in after_region_ids if region_id not in before
        ),
        removed_region_ids=tuple(
            region_id for region_id in before_region_ids if region_id not in after
        ),
        changed_surviving_line_ids=changed_surviving_line_ids,
    )


def validate_structure_move_payload(
    project: SpectroscopyProject, command: StructureMoveLinkedLinesCommand
) -> None:
    """Validate complete move command identities and before/after topology payloads."""
    payload = command.payload
    expanded = payload.expanded_line_ids
    if not expanded or len(set(expanded)) != len(expanded):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move line identities must be non-empty and unique.",
        )
    for label, assignments in (
        ("source", payload.source_assignments),
        ("destination", payload.destination_assignments),
    ):
        if tuple(assignment.line_id for assignment in assignments) != expanded:
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Structure move {label} assignments do not cover command lines exactly.",
            )
    destination_region_ids = {
        assignment.region_id for assignment in payload.destination_assignments
    }
    if len(destination_region_ids) != 1 or None in destination_region_ids:
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move destination assignments do not encode one region.",
        )
    destination_region_id = next(
        region_id for region_id in destination_region_ids if region_id is not None
    )

    source_ids = require_unique_region_snapshot_ids(payload.source_regions, "source")
    destination_ids = require_unique_region_snapshot_ids(
        payload.destination_regions, "destination"
    )
    created_ids = set(destination_ids) - set(source_ids)
    expected_created = (
        {destination_region_id} if destination_region_id not in source_ids else set()
    )
    if created_ids != expected_created:
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move created-region payload is inconsistent.",
        )
    removed_ids = set(source_ids) - set(destination_ids)
    if payload.destination_masks != tuple(
        snapshot for snapshot in payload.source_masks if snapshot.group_id not in removed_ids
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move destination masks do not match region deletion effects.",
        )
    require_unique_snapshot_ids(payload.source_masks, "source mask")
    require_unique_snapshot_ids(payload.destination_masks, "destination mask")

    source_component_ids = tuple(
        assignment.component_id for assignment in payload.source_component_groups
    )
    destination_component_ids = tuple(
        assignment.component_id for assignment in payload.destination_component_groups
    )
    if (
        len(set(source_component_ids)) != len(source_component_ids)
        or source_component_ids != destination_component_ids
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move component group payloads must cover identical unique components.",
        )
    expected_destination_groups = {
        assignment.component_id: assignment.group_id
        for assignment in payload.source_component_groups
    }
    for component_id, group_id in tuple(expected_destination_groups.items()):
        if group_id in removed_ids:
            expected_destination_groups[component_id] = None
    for line_id in expanded:
        line = project.absorption_lines.get(line_id)
        if line is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Structure move payload line not found: {line_id}",
            )
        for component_id in line.model_ids:
            if component_id not in expected_destination_groups:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Structure move linked component not found: {component_id}",
                )
            expected_destination_groups[component_id] = destination_region_id
    if tuple(expected_destination_groups.items()) != tuple(
        (assignment.component_id, assignment.group_id)
        for assignment in payload.destination_component_groups
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move destination component groups do not match line movement effects.",
        )


def require_unique_region_snapshot_ids(
    snapshots: tuple[AbsorptionRegionSnapshot, ...], label: str
) -> tuple[str, ...]:
    """Return non-duplicated region snapshot IDs or fail the command."""
    region_ids = tuple(snapshot.region_id for snapshot in snapshots)
    if len(set(region_ids)) != len(region_ids):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure move {label} region snapshots contain duplicate identities.",
        )
    return region_ids


def require_unique_snapshot_ids(snapshots: tuple[MaskDefinitionSnapshot, ...], label: str) -> None:
    """Require one occurrence of each mask identity."""
    identities = tuple(snapshot.identifier for snapshot in snapshots)
    if len(set(identities)) != len(identities):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure move {label} snapshots contain duplicate identities.",
        )


def require_structure_move_temporal_state(
    project: SpectroscopyProject,
    *,
    regions: tuple[AbsorptionRegionSnapshot, ...],
    masks: tuple[MaskDefinitionSnapshot, ...],
    component_groups: tuple[AbsorberComponentGroupAssignment, ...],
    assignments: tuple[LineRegionAssignment, ...],
) -> None:
    """Require current runtime structure to equal one command temporal state."""
    current_regions = tuple(
        absorption_region_snapshot(region) for region in project.absorption_regions.values()
    )
    if current_regions != regions:
        expected_ids = {snapshot.region_id for snapshot in regions}
        missing = expected_ids - set(project.absorption_regions)
        code = (
            HistoryApplyErrorCode.TARGET_NOT_FOUND
            if missing
            else HistoryApplyErrorCode.INVALID_STATE
        )
        raise HistoryApplyError(code, "Structure move region source state is not exact.")

    listed_line_ids: set[str] = set()
    for region in regions:
        for line_id in region.line_ids:
            line = project.absorption_lines.get(line_id)
            if line is None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Structure move region line not found: {line_id}",
                )
            if line.region_id != region.region_id or line_id in listed_line_ids:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    f"Structure move line assignment is corrupt: {line_id}",
                )
            listed_line_ids.add(line_id)
    if listed_line_ids != set(project.absorption_lines):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure move regions do not cover current lines exactly.",
        )
    for assignment in assignments:
        line = project.absorption_lines.get(assignment.line_id)
        if line is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Structure move command line not found: {assignment.line_id}",
            )
        if line.region_id != assignment.region_id:
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Structure move command line has an unexpected source: {assignment.line_id}",
            )

    current_masks = tuple(
        mask_definition_snapshot(mask) for mask in project.model.mask_definitions
    )
    if current_masks != masks:
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE, "Structure move mask source state is not exact."
        )
    current_groups = tuple(
        AbsorberComponentGroupAssignment(component.id, component.group_id)
        for component in project.model.components
        if isinstance(component, AbsorberComponent)
    )
    if current_groups != component_groups:
        expected_ids = {assignment.component_id for assignment in component_groups}
        current_ids = {assignment.component_id for assignment in current_groups}
        code = (
            HistoryApplyErrorCode.TARGET_NOT_FOUND
            if expected_ids - current_ids
            else HistoryApplyErrorCode.INVALID_STATE
        )
        raise HistoryApplyError(
            code, "Structure move absorber component group source state is not exact."
        )


def validate_structure_structure_state(
    state: StructureStateSnapshot, *, label: str
) -> dict[str, str]:
    """Validate and return exact line-to-region membership for one state."""
    region_ids = tuple(snapshot.region_id for snapshot in state.regions)
    if any(not region_id for region_id in region_ids) or len(set(region_ids)) != len(region_ids):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure structure {label} regions are not unique.",
        )
    line_regions: dict[str, str] = {}
    for region in state.regions:
        if len(set(region.line_ids)) != len(region.line_ids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Structure structure {label} region has duplicate lines: {region.region_id}",
            )
        for line_id in region.line_ids:
            if not line_id or line_id in line_regions:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    f"Structure structure {label} line membership is not unique: {line_id}",
                )
            line_regions[line_id] = region.region_id
    line_ids = tuple(snapshot.line_id for snapshot in state.lines)
    if len(set(line_ids)) != len(line_ids) or set(line_ids) != set(line_regions):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure structure {label} line topology is not exact.",
        )
    line_topology = {snapshot.line_id: snapshot for snapshot in state.lines}
    if any(
        snapshot.region_id != line_regions[snapshot.line_id]
        or len(set(snapshot.multiplet_ids)) != len(snapshot.multiplet_ids)
        or len(set(snapshot.model_ids)) != len(snapshot.model_ids)
        or any(
            related_id not in line_topology
            or snapshot.line_id not in line_topology[related_id].multiplet_ids
            for related_id in snapshot.multiplet_ids
        )
        for snapshot in state.lines
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure structure {label} line references are inconsistent.",
        )
    mask_ids = tuple(snapshot.identifier for snapshot in state.masks)
    group_ids = tuple(assignment.component_id for assignment in state.component_groups)
    if len(set(mask_ids)) != len(mask_ids) or len(set(group_ids)) != len(group_ids):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure structure {label} mask or component identities are not unique.",
        )
    component_id_set = set(group_ids)
    if any(
        component_id not in component_id_set
        for snapshot in state.lines
        for component_id in snapshot.model_ids
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure structure {label} line references a missing component.",
        )
    known_regions = set(region_ids)
    if any(
        snapshot.group_id is not None and snapshot.group_id not in known_regions
        for snapshot in state.masks
    ) or any(
        assignment.group_id is not None and assignment.group_id not in known_regions
        for assignment in state.component_groups
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            f"Structure structure {label} group association references a missing region.",
        )
    return line_regions


def validate_structure_structure_command(
    command: StructureSplitCommand | StructureMergeCommand | StructureDeleteCommand,
) -> None:
    """Validate one command's complete before/after topology contract."""
    before_lines = validate_structure_structure_state(command.before, label="before")
    after_lines = validate_structure_structure_state(command.after, label="after")
    before_region_ids = {snapshot.region_id for snapshot in command.before.regions}
    after_region_ids = {snapshot.region_id for snapshot in command.after.regions}
    created = after_region_ids - before_region_ids
    removed = before_region_ids - after_region_ids

    if isinstance(command, StructureSplitCommand):
        if (
            not command.expanded_line_ids
            or len(set(command.expanded_line_ids)) != len(command.expanded_line_ids)
            or set(before_lines) != set(after_lines)
            or created != {command.new_region_id}
            or not removed.issubset({command.source_region_id})
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Structure split topology identities are inconsistent.",
            )
        changed = {
            line_id for line_id in before_lines if before_lines[line_id] != after_lines[line_id]
        }
        if changed != set(command.expanded_line_ids) or any(
            before_lines[line_id] != command.source_region_id
            or after_lines[line_id] != command.new_region_id
            for line_id in command.expanded_line_ids
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Structure split line movements are not exact.",
            )
    elif isinstance(command, StructureMergeCommand):
        secondary_ids = set(command.secondary_region_ids)
        if (
            not command.primary_region_id
            or not secondary_ids
            or len(secondary_ids) != len(command.secondary_region_ids)
            or created
            or removed != secondary_ids
            or command.primary_region_id not in before_region_ids & after_region_ids
            or set(before_lines) != set(after_lines)
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Structure merge topology identities are inconsistent.",
            )
        changed = {
            line_id for line_id in before_lines if before_lines[line_id] != after_lines[line_id]
        }
        expected = {
            line_id for line_id, region_id in before_lines.items() if region_id in secondary_ids
        }
        if changed != expected or any(
            after_lines[line_id] != command.primary_region_id for line_id in expected
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Structure merge line movements are not exact.",
            )
    else:
        deleted_ids = tuple(snapshot.line_id for snapshot in command.deleted_lines)
        actual_deleted = set(before_lines) - set(after_lines)
        if (
            created
            or len(set(deleted_ids)) != len(deleted_ids)
            or set(deleted_ids) != actual_deleted
            or not set(command.target_line_ids).issubset(actual_deleted)
            or not set(command.target_region_ids).issubset(removed)
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Structure delete topology identities are inconsistent.",
            )
        for snapshot in command.deleted_lines:
            if snapshot.region_id != before_lines[snapshot.line_id]:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    f"Structure delete line source is inconsistent: {snapshot.line_id}",
                )
        removed_component_ids = {
            assignment.component_id for assignment in command.before.component_groups
        } - {assignment.component_id for assignment in command.after.component_groups}
        declared_component_ids = (
            set()
            if command.model_command is None
            else {snapshot.component_id for snapshot in command.model_command.components}
        )
        if removed_component_ids != declared_component_ids:
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Structure delete model topology is inconsistent.",
            )


def require_structure_structure_temporal_state(
    project: SpectroscopyProject, state: StructureStateSnapshot
) -> None:
    """Require current runtime to equal one complete structure history state."""
    require_structure_move_temporal_state(
        project,
        regions=state.regions,
        masks=state.masks,
        component_groups=state.component_groups,
        assignments=(),
    )
    current_lines = tuple(
        (line.line_id, line.region_id, tuple(line.multiplet_ids), tuple(line.model_ids))
        for line in project.absorption_lines.values()
    )
    expected_lines = tuple(
        (snapshot.line_id, snapshot.region_id, snapshot.multiplet_ids, snapshot.model_ids)
        for snapshot in state.lines
    )
    if current_lines != expected_lines:
        expected_ids = {snapshot.line_id for snapshot in state.lines}
        missing = expected_ids - set(project.absorption_lines)
        code = (
            HistoryApplyErrorCode.TARGET_NOT_FOUND
            if missing
            else HistoryApplyErrorCode.INVALID_STATE
        )
        raise HistoryApplyError(code, "Structure structure line source state is not exact.")


def rebuild_structure_structure_history(
    project: SpectroscopyProject, source: StructureStateSnapshot
) -> DomainChangeSet:
    """Rebuild derived state and describe exact component and mask changes."""
    source_groups = {
        assignment.component_id: assignment.group_id for assignment in source.component_groups
    }
    destination_groups = {
        component.id: component.group_id
        for component in project.model.components
        if isinstance(component, AbsorberComponent)
    }
    source_ids = set(source_groups)
    destination_ids = set(destination_groups)
    events: list[DomainEvent] = [
        *(ComponentRemoved(component_id=item) for item in source_ids - destination_ids),
        *(ComponentAdded(component_id=item) for item in destination_ids - source_ids),
        *(
            ComponentChanged(component_id=item)
            for item in source_ids & destination_ids
            if source_groups[item] != destination_groups[item]
        ),
    ]
    current_masks = tuple(
        mask_definition_snapshot(mask) for mask in project.model.mask_definitions
    )
    if source.masks != current_masks:
        events.append(MasksChanged())
    return DomainChangeSet.of(*events).extend(project.model.rebuild_model_storage())


def validate_structure_unlink_payload(
    project: SpectroscopyProject, payload: StructureUnlinkHistoryPayload
) -> None:
    """Validate exact closed before/after multiplet link topology."""
    if (
        not payload.line_ids
        or len(set(payload.line_ids)) != len(payload.line_ids)
        or not payload.affected_region_ids
        or len(set(payload.affected_region_ids)) != len(payload.affected_region_ids)
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure unlink identities must be non-empty and unique.",
        )
    for label, snapshots in (("before", payload.before_links), ("after", payload.after_links)):
        snapshot_ids = tuple(snapshot.line_id for snapshot in snapshots)
        if snapshot_ids != payload.line_ids:
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Structure unlink {label} snapshots do not cover command lines exactly.",
            )
        relations = {snapshot.line_id: snapshot.related_line_ids for snapshot in snapshots}
        if any(
            len(set(related_ids)) != len(related_ids)
            or any(
                related_id not in relations or line_id not in relations[related_id]
                for related_id in related_ids
            )
            for line_id, related_ids in relations.items()
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Structure unlink {label} links are not closed and symmetric.",
            )
    current_regions: list[str] = []
    for line_id in payload.line_ids:
        line = project.absorption_lines.get(line_id)
        if line is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Structure unlink line not found: {line_id}",
            )
        region_id = line.region_id or UNASSIGNED_REGION_ID
        if region_id not in current_regions:
            current_regions.append(region_id)
    if tuple(current_regions) != payload.affected_region_ids:
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Structure unlink affected regions do not match current line ownership.",
        )


def require_multiplet_link_state(
    project: SpectroscopyProject,
    line_ids: tuple[str, ...],
    snapshots: tuple[MultipletLinkSnapshot, ...],
) -> None:
    """Require exact ordered multiplet links for every command line."""
    expected = {snapshot.line_id: snapshot.related_line_ids for snapshot in snapshots}
    for line_id in line_ids:
        line = project.absorption_lines.get(line_id)
        if line is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Structure unlink line not found: {line_id}",
            )
        if tuple(line.multiplet_ids) != expected.get(line_id):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Structure unlink source link state is not exact: {line_id}",
            )


class StructureApply:
    """Apply structure move/split/merge/delete/unlink structure history."""

    def __init__(
        self,
        structure_executor: AtomicStructureMutationExecutor,
        structure_topology: StructureTopologySnapshotService,
    ) -> None:
        """Initialize with the shared structure executor and topology snapshot service."""
        self._structure_executor = structure_executor
        self._structure_topology = structure_topology

    def apply_move(
        self,
        project: SpectroscopyProject,
        command: StructureMoveLinkedLinesCommand,
        *,
        context: HistoryCommandContext,
        is_undo: bool,
    ) -> tuple[HistoryApplyResult, DomainChangeSet]:
        """Apply one structure move direction through the structure transaction."""
        payload = command.payload
        before_region_ids: tuple[str, ...] = ()
        before_memberships: dict[str, tuple[str, ...]] = {}
        before_multiplet_links: dict[str, tuple[str, ...]] = {}

        def preflight() -> StructureMutationOutcome:
            validate_structure_move_payload(project, command)
            expected_regions = payload.destination_regions if is_undo else payload.source_regions
            expected_masks = payload.destination_masks if is_undo else payload.source_masks
            expected_groups = (
                payload.destination_component_groups
                if is_undo
                else payload.source_component_groups
            )
            expected_assignments = (
                payload.destination_assignments if is_undo else payload.source_assignments
            )
            require_structure_move_temporal_state(
                project,
                regions=expected_regions,
                masks=expected_masks,
                component_groups=expected_groups,
                assignments=expected_assignments,
            )
            return StructureMutationOutcome.CHANGED

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_region_ids, before_memberships, before_multiplet_links
            before_region_ids = tuple(project.absorption_regions)
            before_memberships = {
                region_id: tuple(region.line_ids)
                for region_id, region in project.absorption_regions.items()
            }
            before_multiplet_links = {
                line_id: tuple(line.multiplet_ids)
                for line_id, line in project.absorption_lines.items()
            }
            return self._structure_topology.capture(project)

        def mutate() -> StructureMutationResult[HistoryApplyResult]:
            result = command.undo(context) if is_undo else command.redo(context)
            if not result.success:
                error_code = result.error_code or HistoryApplyErrorCode.INVALID_STATE
                raise HistoryApplyError(
                    error_code, f"Structure move history mutation failed: {error_code}"
                )
            target_regions = payload.source_regions if is_undo else payload.destination_regions
            target_masks = payload.source_masks if is_undo else payload.destination_masks
            target_groups = (
                payload.source_component_groups
                if is_undo
                else payload.destination_component_groups
            )
            target_assignments = (
                payload.source_assignments if is_undo else payload.destination_assignments
            )
            require_structure_move_temporal_state(
                project,
                regions=target_regions,
                masks=target_masks,
                component_groups=target_groups,
                assignments=target_assignments,
            )
            delta = structure_history_delta(
                project,
                before_region_ids=before_region_ids,
                before_memberships=before_memberships,
                before_multiplet_links=before_multiplet_links,
                invalidation_scope=StructureInvalidationScope.LOCAL_SURVIVORS,
            )
            return StructureMutationResult.changed_result(result, delta)

        def rebuild() -> DomainChangeSet:
            source_groups = {
                assignment.component_id: assignment.group_id
                for assignment in payload.source_component_groups
            }
            destination_groups = {
                assignment.component_id: assignment.group_id
                for assignment in payload.destination_component_groups
            }
            events: list[DomainEvent] = [
                ComponentChanged(component_id=component_id)
                for component_id in source_groups
                if source_groups[component_id] != destination_groups[component_id]
            ]
            if payload.source_masks != payload.destination_masks:
                events.append(MasksChanged())
            return DomainChangeSet.of(*events).extend(project.model.rebuild_model_storage())

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._structure_topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=rebuild,
        )
        result = execution.result.value
        if result is None:
            msg = "Changed structure move history produced no application result."
            raise RuntimeError(msg)
        return result, execution.postcommit_changes

    def apply_structure(
        self,
        project: SpectroscopyProject,
        command: StructureSplitCommand | StructureMergeCommand | StructureDeleteCommand,
        *,
        context: HistoryCommandContext,
        is_undo: bool,
    ) -> tuple[HistoryApplyResult, DomainChangeSet]:
        """Apply split, merge, or delete through the shared structure transaction."""
        source = command.after if is_undo else command.before
        target = command.before if is_undo else command.after
        before_region_ids: tuple[str, ...] = ()
        before_memberships: dict[str, tuple[str, ...]] = {}
        before_multiplet_links: dict[str, tuple[str, ...]] = {}

        def preflight() -> StructureMutationOutcome:
            validate_structure_structure_command(command)
            require_structure_structure_temporal_state(project, source)
            if isinstance(command, StructureDeleteCommand) and command.model_command is not None:
                source_is_before = not is_undo
                if not model_component_temporal_state_matches(
                    project, command.model_command, before=source_is_before
                ):
                    raise HistoryApplyError(
                        HistoryApplyErrorCode.INVALID_STATE,
                        "Structure delete model source topology is not exact.",
                    )
            return StructureMutationOutcome.CHANGED

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_region_ids, before_memberships, before_multiplet_links
            before_region_ids = tuple(project.absorption_regions)
            before_memberships = {
                region_id: tuple(region.line_ids)
                for region_id, region in project.absorption_regions.items()
            }
            before_multiplet_links = {
                line_id: tuple(line.multiplet_ids)
                for line_id, line in project.absorption_lines.items()
            }
            return self._structure_topology.capture(project)

        def mutate() -> StructureMutationResult[HistoryApplyResult]:
            result = command.undo(context) if is_undo else command.redo(context)
            if not result.success:
                error_code = result.error_code or HistoryApplyErrorCode.INVALID_STATE
                raise HistoryApplyError(
                    error_code, f"Structure structure history mutation failed: {error_code}"
                )
            require_structure_structure_temporal_state(project, target)
            if (
                isinstance(command, StructureDeleteCommand)
                and command.model_command is not None
                and not model_component_temporal_state_matches(
                    project, command.model_command, before=is_undo
                )
            ):
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    "Structure delete model mutation did not reach its exact target.",
                )
            invalidation_scope = (
                StructureInvalidationScope.ALL_ANALYSIS_CAPABLE_SURVIVORS
                if isinstance(command, StructureDeleteCommand)
                and command.model_command is not None
                else StructureInvalidationScope.LOCAL_SURVIVORS
            )
            return StructureMutationResult.changed_result(
                result,
                structure_history_delta(
                    project,
                    before_region_ids=before_region_ids,
                    before_memberships=before_memberships,
                    before_multiplet_links=before_multiplet_links,
                    invalidation_scope=invalidation_scope,
                ),
            )

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._structure_topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=lambda: rebuild_structure_structure_history(project, source),
        )
        result = execution.result.value
        if result is None:
            msg = "Changed structure structure history produced no application result."
            raise RuntimeError(msg)
        return result, execution.postcommit_changes

    def apply_unlink(
        self,
        project: SpectroscopyProject,
        command: StructureUnlinkLinkedLinesCommand,
        *,
        context: HistoryCommandContext,
        is_undo: bool,
    ) -> tuple[HistoryApplyResult, DomainChangeSet]:
        """Apply one exact multiplet unlink state through the structure transaction."""
        payload = command.payload
        source = payload.after_links if is_undo else payload.before_links
        target = payload.before_links if is_undo else payload.after_links

        def preflight() -> StructureMutationOutcome:
            validate_structure_unlink_payload(project, payload)
            require_multiplet_link_state(project, payload.line_ids, source)
            return StructureMutationOutcome.CHANGED

        def mutate() -> StructureMutationResult[HistoryApplyResult]:
            result = command.undo(context) if is_undo else command.redo(context)
            if not result.success:
                error_code = result.error_code or HistoryApplyErrorCode.INVALID_STATE
                raise HistoryApplyError(
                    error_code, f"Structure unlink history mutation failed: {error_code}"
                )
            require_multiplet_link_state(project, payload.line_ids, target)
            return StructureMutationResult.changed_result(
                result,
                StructureRegionDelta(
                    invalidation_scope=StructureInvalidationScope.LOCAL_SURVIVORS,
                    affected_surviving_region_ids=payload.affected_region_ids,
                    changed_surviving_line_ids=payload.line_ids,
                ),
            )

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=lambda: self._structure_topology.capture(project),
            mutate=mutate,
            restore_runtime=lambda snapshot: self._structure_topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=DomainChangeSet.empty,
        )
        result = execution.result.value
        if result is None:
            msg = "Changed structure unlink history produced no application result."
            raise RuntimeError(msg)
        return result, execution.postcommit_changes


__all__ = [
    "StructureApply",
    "rebuild_structure_structure_history",
    "require_multiplet_link_state",
    "require_structure_move_temporal_state",
    "require_structure_structure_temporal_state",
    "require_unique_region_snapshot_ids",
    "require_unique_snapshot_ids",
    "structure_history_delta",
    "validate_structure_move_payload",
    "validate_structure_structure_command",
    "validate_structure_structure_state",
    "validate_structure_unlink_payload",
]
