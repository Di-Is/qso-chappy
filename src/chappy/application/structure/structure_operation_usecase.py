"""Structure-mode project mutation use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.application.history import (
    AbsorberComponentGroupAssignment,
    AbsorptionLineSnapshot,
    AbsorptionRegionSnapshot,
    LineRegionAssignment,
    MaskDefinitionSnapshot,
    ModelComponentLinkSnapshot,
    MultipletLinkSnapshot,
    StructureDeleteModelHistorySnapshot,
    StructureLineTopologySnapshot,
    StructureMoveHistoryPayload,
    StructureStateSnapshot,
    StructureUnlinkHistoryPayload,
)
from chappy.application.history.snapshot_mapping import (
    absorber_component_snapshot,
    tie_set_snapshots,
)
from chappy.application.structure import (
    AtomicStructureMutationExecutor,
    AtomicStructureProjectPort,
    DeleteStructureRequest,
    MergeStructureRequest,
    MoveStructureRequest,
    SplitStructureRequest,
    StructureImpactPreviewUseCase,
    StructureInvalidationScope,
    StructureMutationOutcome,
    StructureMutationResult,
    StructureRegionDelta,
    StructureTopologySnapshot,
    StructureTopologySnapshotService,
    UnlinkStructureRequest,
)
from chappy.application.structure.models import (
    StructureDeleteResult,
    StructureMergeResult,
    StructureMoveResult,
    StructureSplitResult,
    StructureUnlinkResult,
)
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.absorption_display import group_lines_by_multiplet
from chappy.core.change_set import ChangeSet
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.events import (
    ComponentAdded,
    ComponentChanged,
    ComponentRemoved,
    DomainEvent,
    MasksChanged,
)

if TYPE_CHECKING:
    from chappy.application.structure.ports import (
        StructureHistoryRecorder,
        StructureMoveHistoryRecorder,
        StructureProjectPort,
    )
    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.masking import MaskDefinition


@dataclass(frozen=True, slots=True)
class _StructureBeforeState:
    """Serializable scientific facts captured only after a changed preflight."""

    region_ids: tuple[str, ...]
    memberships: tuple[tuple[str, tuple[str, ...]], ...]
    line_multiplet_links: tuple[tuple[str, tuple[str, ...]], ...]
    regions: tuple[AbsorptionRegionSnapshot, ...]
    lines: tuple[StructureLineTopologySnapshot, ...]
    masks: tuple[MaskDefinitionSnapshot, ...]
    component_groups: tuple[AbsorberComponentGroupAssignment, ...]


class StructureOperationUseCase:
    """Apply structure project mutations and record matching history events."""

    def __init__(
        self,
        *,
        structure_executor: AtomicStructureMutationExecutor | None = None,
        topology: StructureTopologySnapshotService | None = None,
        impact_previewer: StructureImpactPreviewUseCase | None = None,
    ) -> None:
        """Initialize the shared structure transaction dependencies."""
        self._structure_executor = structure_executor or AtomicStructureMutationExecutor()
        self._topology = topology or StructureTopologySnapshotService()
        self._impact_previewer = impact_previewer or StructureImpactPreviewUseCase()

    def move_lines(
        self,
        project: StructureProjectPort,
        *,
        line_ids: list[str],
        target_region_id: str | None,
        history_recorder: StructureMoveHistoryRecorder | None,
    ) -> StructureMoveResult | None:
        """Move selected lines through one atomic scientific structure transaction."""
        requested_line_ids = tuple(line_ids)
        expanded_line_ids: list[str] = []
        source_assignments: tuple[LineRegionAssignment, ...] = ()

        before_state: _StructureBeforeState | None = None
        history_payload: StructureMoveHistoryPayload | None = None

        def preflight() -> StructureMutationOutcome:
            nonlocal expanded_line_ids, source_assignments
            preview = self._impact_previewer.preview_move(
                project,
                MoveStructureRequest(
                    line_ids=requested_line_ids, target_region_id=target_region_id
                ),
            )
            if not preview.changed:
                return preview.outcome
            expanded_line_ids = list(preview.expanded_request_line_ids)
            source_assignments = _source_assignments(project, expanded_line_ids)
            return preview.outcome

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_state
            before_state = _capture_structure_before(project, project)
            return self._topology.capture(project)

        def mutate() -> StructureMutationResult[StructureMoveResult]:
            nonlocal history_payload
            if before_state is None:
                msg = "Changed structure move has no captured before state."
                raise RuntimeError(msg)
            destination_id = project.move_absorption_lines(
                list(requested_line_ids), target_region_id=target_region_id
            )
            if destination_id is None:
                msg = "A changed structure move did not produce a destination region."
                raise RuntimeError(msg)

            delta = _structure_region_delta(project, before_state)

            destination = project.absorption_regions.get(destination_id)
            destination_assignments = tuple(
                LineRegionAssignment(line_id=line_id, region_id=destination_id)
                for line_id in expanded_line_ids
            )
            history_payload = StructureMoveHistoryPayload(
                expanded_line_ids=tuple(expanded_line_ids),
                source_assignments=source_assignments,
                destination_assignments=destination_assignments,
                source_regions=before_state.regions,
                destination_regions=_all_region_snapshots(project),
                source_masks=before_state.masks,
                destination_masks=_all_mask_snapshots(project),
                source_component_groups=before_state.component_groups,
                destination_component_groups=_component_group_assignments(project),
            )

            moved_lines = [project.absorption_lines[line_id] for line_id in requested_line_ids]
            moved_linked_line_count = (
                len(group_lines_by_multiplet(moved_lines)) if moved_lines else 0
            )
            return StructureMutationResult.changed_result(
                StructureMoveResult(
                    destination_id=destination_id,
                    moved_linked_line_count=moved_linked_line_count,
                    destination_region=destination,
                ),
                delta,
            )

        def record_history(_result: StructureMutationResult[StructureMoveResult]) -> None:
            if history_recorder is None:
                return
            if history_payload is None:
                msg = "Committed structure move has no history payload."
                raise RuntimeError(msg)
            history_recorder.record_structure_move_linked_lines(history_payload)

        def rebuild() -> ChangeSet:
            if before_state is None:
                msg = "Changed structure move has no captured before state."
                raise RuntimeError(msg)
            return _rebuild_structure_changes(project, before_state)

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=rebuild,
            record_history=record_history if history_recorder is not None else None,
            history_scope=(
                history_recorder.atomic_recording if history_recorder is not None else None
            ),
        )
        if not execution.result.changed:
            return None
        run_postcommit_actions_isolated(
            lambda: project.model.publish_storage_changes(execution.postcommit_changes)
        )
        return execution.result.value

    def merge_regions(
        self,
        project: StructureProjectPort,
        *,
        group_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureMergeResult | None:
        """Merge selected regions through one atomic scientific transaction."""
        requested_region_ids = tuple(group_ids)
        before_state: _StructureBeforeState | None = None
        primary_region_id = ""
        secondary_region_ids: tuple[str, ...] = ()
        line_movements: tuple[LineRegionAssignment, ...] = ()
        mask_reassignments: tuple[MaskDefinitionSnapshot, ...] = ()
        deleted_region_snapshots: tuple[AbsorptionRegionSnapshot, ...] = ()

        def preflight() -> StructureMutationOutcome:
            nonlocal primary_region_id, secondary_region_ids
            nonlocal line_movements, mask_reassignments, deleted_region_snapshots
            preview = self._impact_previewer.preview_merge(
                project, MergeStructureRequest(region_ids=requested_region_ids)
            )
            if not preview.changed:
                return preview.outcome
            primary_region_id = requested_region_ids[0]
            secondary_region_ids = preview.removed_region_ids
            line_movements = _line_movements(project, list(secondary_region_ids))
            mask_reassignments = _mask_snapshots(project, list(secondary_region_ids))
            deleted_region_snapshots = tuple(
                _region_snapshots(project, list(secondary_region_ids)).values()
            )
            return preview.outcome

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_state
            before_state = _capture_structure_before(project, project)
            return self._topology.capture(project)

        def mutate() -> StructureMutationResult[StructureMergeResult]:
            if before_state is None:
                msg = "Changed structure merge has no captured before state."
                raise RuntimeError(msg)
            merged_region = project.merge_absorption_regions(list(requested_region_ids))
            if merged_region is None or merged_region.region_id != primary_region_id:
                msg = "A changed structure merge did not preserve its primary region."
                raise RuntimeError(msg)
            return StructureMutationResult.changed_result(
                StructureMergeResult(merged_region=merged_region),
                _structure_region_delta(project, before_state),
            )

        def record_history(_result: StructureMutationResult[StructureMergeResult]) -> None:
            if history_recorder is None:
                return
            if before_state is None:
                msg = "Committed structure merge has no captured before state."
                raise RuntimeError(msg)
            history_recorder.record_structure_merge(
                primary_region_id=primary_region_id,
                secondary_region_ids=secondary_region_ids,
                before=_structure_state_snapshot(before_state),
                after=_capture_structure_state(project, project),
            )

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=lambda: _require_rebuild_before_state(project, before_state),
            record_history=record_history if history_recorder is not None else None,
            history_scope=(
                history_recorder.atomic_recording if history_recorder is not None else None
            ),
        )
        if not execution.result.changed:
            return None
        run_postcommit_actions_isolated(
            lambda: project.model.publish_storage_changes(execution.postcommit_changes)
        )
        return execution.result.value

    def split_lines(
        self,
        project: StructureProjectPort,
        *,
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureSplitResult | None:
        """Split selected lines through one atomic scientific transaction."""
        requested_linked_line_ids = tuple(linked_line_ids)
        before_state: _StructureBeforeState | None = None
        expanded_line_ids: tuple[str, ...] = ()
        source_region_id = ""
        source_region_snapshot: AbsorptionRegionSnapshot | None = None
        source_masks_snapshot: tuple[MaskDefinitionSnapshot, ...] = ()
        destination_id = ""
        source_auto_deleted = False
        new_region_color = ""

        def preflight() -> StructureMutationOutcome:
            nonlocal expanded_line_ids, source_region_id
            nonlocal source_region_snapshot, source_masks_snapshot
            preview = self._impact_previewer.preview_split(
                project, SplitStructureRequest(line_ids=requested_linked_line_ids)
            )
            if not preview.changed:
                return preview.outcome
            expanded_line_ids = preview.expanded_request_line_ids
            source_region_id = (
                project.absorption_lines[expanded_line_ids[0]].region_id or UNASSIGNED_REGION_ID
            )
            source_region = project.absorption_regions[source_region_id]
            source_region_snapshot = _region_snapshot(source_region)
            source_masks_snapshot = _mask_snapshots(project, [source_region_id])
            return preview.outcome

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_state
            before_state = _capture_structure_before(project, project)
            return self._topology.capture(project)

        def mutate() -> StructureMutationResult[StructureSplitResult]:
            nonlocal destination_id, source_auto_deleted, new_region_color
            if before_state is None:
                msg = "Changed structure split has no captured before state."
                raise RuntimeError(msg)
            destination = project.move_absorption_lines(
                list(requested_linked_line_ids), target_region_id=None
            )
            if destination is None:
                msg = "A changed structure split did not create a destination region."
                raise RuntimeError(msg)
            destination_id = destination
            new_region = project.absorption_regions.get(destination_id)
            if new_region is None:
                msg = "A changed structure split destination disappeared before commit."
                raise RuntimeError(msg)
            source_auto_deleted = source_region_id not in project.absorption_regions
            new_region_color = new_region.display_color
            return StructureMutationResult.changed_result(
                StructureSplitResult(new_region=new_region),
                _structure_region_delta(project, before_state),
            )

        def record_history(_result: StructureMutationResult[StructureSplitResult]) -> None:
            if history_recorder is None:
                return
            if before_state is None:
                msg = "Committed structure split has no captured before state."
                raise RuntimeError(msg)
            history_recorder.record_structure_split(
                expanded_line_ids=expanded_line_ids,
                source_region_id=source_region_id,
                new_region_id=destination_id,
                before=_structure_state_snapshot(before_state),
                after=_capture_structure_state(project, project),
            )

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=lambda: _require_rebuild_before_state(project, before_state),
            record_history=record_history if history_recorder is not None else None,
            history_scope=(
                history_recorder.atomic_recording if history_recorder is not None else None
            ),
        )
        if not execution.result.changed:
            return None
        run_postcommit_actions_isolated(
            lambda: project.model.publish_storage_changes(execution.postcommit_changes)
        )
        return execution.result.value

    def unlink_linked_lines(
        self,
        project: StructureProjectPort,
        *,
        line_id: str,
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureUnlinkResult | None:
        """Unlink one materialized linked-line group in an atomic scientific transaction."""
        before_state: _StructureBeforeState | None = None
        expanded_line_ids: tuple[str, ...] = ()
        affected_region_ids: tuple[str, ...] = ()
        before_links: tuple[MultipletLinkSnapshot, ...] = ()
        after_links: tuple[MultipletLinkSnapshot, ...] = ()

        def preflight() -> StructureMutationOutcome:
            nonlocal expanded_line_ids, affected_region_ids, before_links
            preview = self._impact_previewer.preview_unlink(
                project, UnlinkStructureRequest(line_id=line_id)
            )
            if not preview.changed:
                return preview.outcome
            expanded_line_ids = preview.expanded_request_line_ids
            affected_region_ids = preview.changed_region_ids
            before_links = _multiplet_link_snapshots(project, expanded_line_ids)
            return preview.outcome

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_state
            before_state = _capture_structure_before(project, project)
            return self._topology.capture(project)

        def mutate() -> StructureMutationResult[StructureUnlinkResult]:
            nonlocal after_links
            if before_state is None:
                msg = "Changed structure unlink has no captured before state."
                raise RuntimeError(msg)
            changed_line_ids = project.unlink_linked_lines(line_id)
            if changed_line_ids != expanded_line_ids:
                msg = "A changed structure unlink did not mutate its preflighted linked lines."
                raise RuntimeError(msg)
            after_links = _multiplet_link_snapshots(project, expanded_line_ids)
            if any(snapshot.related_line_ids for snapshot in after_links):
                msg = "A changed structure unlink left materialized links behind."
                raise RuntimeError(msg)
            return StructureMutationResult.changed_result(
                StructureUnlinkResult(unlinked_line_ids=changed_line_ids),
                _structure_region_delta(project, before_state),
            )

        def record_history(_result: StructureMutationResult[StructureUnlinkResult]) -> None:
            if history_recorder is None:
                return
            history_recorder.record_structure_unlink(
                StructureUnlinkHistoryPayload(
                    line_ids=expanded_line_ids,
                    affected_region_ids=affected_region_ids,
                    before_links=before_links,
                    after_links=after_links,
                )
            )

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=ChangeSet.empty,
            record_history=record_history if history_recorder is not None else None,
            history_scope=(
                history_recorder.atomic_recording if history_recorder is not None else None
            ),
        )
        if not execution.result.changed:
            return None
        run_postcommit_actions_isolated(
            lambda: project.model.publish_storage_changes(execution.postcommit_changes)
        )
        return execution.result.value

    def delete_selection(
        self,
        project: StructureProjectPort,
        *,
        group_ids: list[str],
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureDeleteResult | None:
        """Delete selected regions and linked lines in one atomic scientific transaction."""
        requested_region_ids = tuple(group_ids)
        requested_linked_line_ids = tuple(linked_line_ids)
        before_state: _StructureBeforeState | None = None
        target_region_ids: tuple[str, ...] = ()
        target_line_ids: tuple[str, ...] = ()
        deleted_lines: tuple[AbsorptionLineSnapshot, ...] = ()
        deleted_model_history: StructureDeleteModelHistorySnapshot | None = None

        def preflight() -> StructureMutationOutcome:
            nonlocal target_region_ids, target_line_ids
            nonlocal deleted_lines, deleted_model_history
            preview = self._impact_previewer.preview_delete(
                project,
                DeleteStructureRequest(
                    region_ids=requested_region_ids, line_ids=requested_linked_line_ids
                ),
            )
            if not preview.changed:
                return preview.outcome
            target_region_ids = tuple(sorted(requested_region_ids))
            target_line_ids = preview.expanded_request_line_ids
            deleted_lines = tuple(
                _line_snapshot(project.absorption_lines[line_id])
                for line_id in preview.removed_line_ids
            )
            deleted_model_history = _deleted_model_history_snapshot(
                project, project, preview.removed_line_ids
            )
            return preview.outcome

        def capture_runtime() -> StructureTopologySnapshot:
            nonlocal before_state
            before_state = _capture_structure_before(project, project)
            return self._topology.capture(project)

        def mutate() -> StructureMutationResult[StructureDeleteResult]:
            if before_state is None:
                msg = "Changed structure delete has no captured before state."
                raise RuntimeError(msg)
            groups_removed = 0
            lines_removed = 0
            for region_id in requested_region_ids:
                removed_from_region = project.remove_absorption_region(
                    region_id, delete_models=True
                )
                if region_id not in project.absorption_regions:
                    groups_removed += 1
                    lines_removed += removed_from_region

            remaining_line_ids = [
                line_id for line_id in target_line_ids if line_id in project.absorption_lines
            ]
            if remaining_line_ids:
                lines_removed += project.remove_absorption_lines_with_multiplet(
                    remaining_line_ids, delete_models=True
                )
            if groups_removed == 0 and lines_removed == 0:
                msg = "A changed structure delete removed no scientific structure."
                raise RuntimeError(msg)

            model_ids_before = {
                assignment.component_id for assignment in before_state.component_groups
            }
            model_ids_after = {
                component.id
                for component in project.model.components
                if isinstance(component, AbsorberComponent)
            }
            invalidation_scope = (
                StructureInvalidationScope.ALL_ANALYSIS_CAPABLE_SURVIVORS
                if model_ids_before != model_ids_after
                else StructureInvalidationScope.LOCAL_SURVIVORS
            )
            return StructureMutationResult.changed_result(
                StructureDeleteResult(groups_removed=groups_removed, lines_removed=lines_removed),
                _structure_region_delta(
                    project, before_state, invalidation_scope=invalidation_scope
                ),
            )

        def record_history(_result: StructureMutationResult[StructureDeleteResult]) -> None:
            if history_recorder is None:
                return
            if before_state is None:
                msg = "Committed structure delete has no captured before state."
                raise RuntimeError(msg)
            history_recorder.record_structure_delete(
                target_region_ids=target_region_ids,
                target_line_ids=target_line_ids,
                deleted_lines=deleted_lines,
                before=_structure_state_snapshot(before_state),
                after=_capture_structure_state(project, project),
                deleted_model_history=deleted_model_history,
            )

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=lambda snapshot: self._topology.restore(project, snapshot),
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=lambda: _require_rebuild_before_state(project, before_state),
            record_history=record_history if history_recorder is not None else None,
            history_scope=(
                history_recorder.atomic_recording if history_recorder is not None else None
            ),
        )
        if not execution.result.changed:
            return None
        run_postcommit_actions_isolated(
            lambda: project.model.publish_storage_changes(execution.postcommit_changes)
        )
        return execution.result.value


def _capture_structure_before(
    project: StructureProjectPort, atomic_project: AtomicStructureProjectPort
) -> _StructureBeforeState:
    """Capture exact facts needed for delta validation, history, and notifications."""
    return _StructureBeforeState(
        region_ids=tuple(project.absorption_regions),
        memberships=tuple(
            (region_id, tuple(region.line_ids))
            for region_id, region in project.absorption_regions.items()
        ),
        line_multiplet_links=tuple(
            (line_id, tuple(line.multiplet_ids))
            for line_id, line in project.absorption_lines.items()
        ),
        regions=_all_region_snapshots(project),
        lines=_all_line_topology_snapshots(project),
        masks=_all_mask_snapshots(project),
        component_groups=_component_group_assignments(atomic_project),
    )


def _structure_state_snapshot(before: _StructureBeforeState) -> StructureStateSnapshot:
    """Convert a captured forward pre-state into one immutable history state."""
    return StructureStateSnapshot(
        regions=before.regions,
        lines=before.lines,
        masks=before.masks,
        component_groups=before.component_groups,
    )


def _capture_structure_state(
    project: StructureProjectPort, atomic_project: AtomicStructureProjectPort
) -> StructureStateSnapshot:
    """Capture the exact serializable topology after a structure mutation."""
    return StructureStateSnapshot(
        regions=_all_region_snapshots(project),
        lines=_all_line_topology_snapshots(project),
        masks=_all_mask_snapshots(project),
        component_groups=_component_group_assignments(atomic_project),
    )


def _deleted_model_history_snapshot(
    project: StructureProjectPort,
    atomic_project: AtomicStructureProjectPort,
    deleted_line_ids: tuple[str, ...],
) -> StructureDeleteModelHistorySnapshot | None:
    """Capture every model object and link removed by an structure delete."""
    component_ids = {
        component_id
        for line_id in deleted_line_ids
        for component_id in project.absorption_lines[line_id].model_ids
    }
    components = tuple(
        component
        for component in atomic_project.model.components
        if isinstance(component, AbsorberComponent) and component.id in component_ids
    )
    if not components:
        return None

    links = tuple(
        ModelComponentLinkSnapshot(line_id=line.line_id, component_id=component_id, index=index)
        for line in project.absorption_lines.values()
        for index, component_id in enumerate(line.model_ids)
        if component_id in component_ids
    )
    ordered_tie_sets = tuple(atomic_project.model.iter_tie_sets())
    affected_tie_sets = atomic_project.model.tie_sets_for_components(list(component_ids))
    return StructureDeleteModelHistorySnapshot(
        components=tuple(absorber_component_snapshot(component) for component in components),
        component_indices=tuple(
            atomic_project.model.components.index(component) for component in components
        ),
        links=links,
        tie_sets=tie_set_snapshots(affected_tie_sets),
        tie_set_indices=tuple(ordered_tie_sets.index(tie_set) for tie_set in affected_tie_sets),
    )


def _structure_region_delta(
    project: StructureProjectPort,
    before: _StructureBeforeState,
    *,
    invalidation_scope: StructureInvalidationScope = StructureInvalidationScope.LOCAL_SURVIVORS,
) -> StructureRegionDelta:
    """Derive exact created, removed, and membership-changed region identities."""
    region_ids_after = tuple(project.absorption_regions)
    regions_after = set(region_ids_after)
    regions_before = set(before.region_ids)
    memberships_before = dict(before.memberships)
    surviving = regions_before & regions_after
    membership_changed_regions = {
        region_id
        for region_id in region_ids_after
        if region_id in surviving
        and memberships_before[region_id] != tuple(project.absorption_regions[region_id].line_ids)
    }
    links_before = dict(before.line_multiplet_links)
    changed_surviving_line_ids = tuple(
        line_id
        for line_id, line in project.absorption_lines.items()
        if line_id in links_before and links_before[line_id] != tuple(line.multiplet_ids)
    )
    link_changed_regions = {
        project.absorption_lines[line_id].region_id
        for line_id in changed_surviving_line_ids
        if project.absorption_lines[line_id].region_id in surviving
    }
    affected_region_ids = tuple(
        region_id
        for region_id in region_ids_after
        if region_id in membership_changed_regions | link_changed_regions
    )
    return StructureRegionDelta(
        invalidation_scope=invalidation_scope,
        affected_surviving_region_ids=(
            affected_region_ids
            if invalidation_scope is StructureInvalidationScope.LOCAL_SURVIVORS
            else ()
        ),
        created_region_ids=tuple(
            region_id for region_id in region_ids_after if region_id not in regions_before
        ),
        removed_region_ids=tuple(
            region_id for region_id in before.region_ids if region_id not in regions_after
        ),
        changed_surviving_line_ids=changed_surviving_line_ids,
    )


def _require_rebuild_before_state(
    project: AtomicStructureProjectPort, before: _StructureBeforeState | None
) -> ChangeSet:
    """Rebuild derived state after requiring a captured transaction snapshot."""
    if before is None:
        msg = "Changed structure structure command has no captured before state."
        raise RuntimeError(msg)
    return _rebuild_structure_changes(project, before)


def _rebuild_structure_changes(
    project: AtomicStructureProjectPort, before: _StructureBeforeState
) -> ChangeSet:
    """Build exact component and mask events, then rebuild derived model state."""
    source_groups = {
        assignment.component_id: assignment.group_id for assignment in before.component_groups
    }
    destination_groups = {
        assignment.component_id: assignment.group_id
        for assignment in _component_group_assignments(project)
    }
    source_ids = set(source_groups)
    destination_ids = set(destination_groups)
    events: list[DomainEvent] = [
        *(
            ComponentRemoved(component_id=component_id)
            for component_id in source_ids - destination_ids
        ),
        *(
            ComponentAdded(component_id=component_id)
            for component_id in destination_ids - source_ids
        ),
        *(
            ComponentChanged(component_id=component_id)
            for component_id in source_ids & destination_ids
            if source_groups[component_id] != destination_groups[component_id]
        ),
    ]
    if before.masks != _all_mask_snapshots(project):
        events.append(MasksChanged())
    return ChangeSet.of(*events).extend(project.model.rebuild_model_storage())


def _source_assignments(
    project: StructureProjectPort, expanded_line_ids: list[str]
) -> tuple[LineRegionAssignment, ...]:
    """Return exact source assignments for preflight-validated line IDs."""
    assignments: list[LineRegionAssignment] = []
    for line_id in expanded_line_ids:
        line = project.find_absorption_line(line_id)
        if line is None:
            msg = f"Expanded move line not found: {line_id}"
            raise ValueError(msg)
        region_id = line.region_id or UNASSIGNED_REGION_ID
        assignments.append(LineRegionAssignment(line_id=line_id, region_id=region_id))
    return tuple(assignments)


def _region_snapshots(
    project: StructureProjectPort, region_ids: set[str] | list[str]
) -> dict[str, AbsorptionRegionSnapshot]:
    """Return available region snapshots by region ID."""
    snapshots: dict[str, AbsorptionRegionSnapshot] = {}
    for region_id in region_ids:
        region = project.find_absorption_region(region_id)
        if region is not None:
            snapshots[region_id] = _region_snapshot(region)
    return snapshots


def _region_snapshot(region: AbsorptionRegion) -> AbsorptionRegionSnapshot:
    """Build a typed region snapshot."""
    return AbsorptionRegionSnapshot(
        region_id=region.region_id,
        line_ids=tuple(region.line_ids),
        display_color=region.display_color,
        analysis_range=region.analysis_range,
        created_at=region.created_at,
    )


def _all_region_snapshots(project: StructureProjectPort) -> tuple[AbsorptionRegionSnapshot, ...]:
    """Capture every region in exact mapping order."""
    return tuple(_region_snapshot(region) for region in project.absorption_regions.values())


def _all_line_topology_snapshots(
    project: StructureProjectPort,
) -> tuple[StructureLineTopologySnapshot, ...]:
    """Capture exact ordered line topology without user-facing freshness state."""
    return tuple(
        StructureLineTopologySnapshot(
            line_id=line.line_id,
            region_id=line.region_id,
            multiplet_ids=tuple(line.multiplet_ids),
            model_ids=tuple(line.model_ids),
        )
        for line in project.absorption_lines.values()
    )


def _all_mask_snapshots(project: AtomicStructureProjectPort) -> tuple[MaskDefinitionSnapshot, ...]:
    """Capture every mask in exact storage order."""
    return tuple(_mask_snapshot(mask) for mask in project.model.mask_definitions)


def _component_group_assignments(
    project: AtomicStructureProjectPort,
) -> tuple[AbsorberComponentGroupAssignment, ...]:
    """Capture every absorber component group in exact model order."""
    return tuple(
        AbsorberComponentGroupAssignment(component_id=component.id, group_id=component.group_id)
        for component in project.model.components
        if isinstance(component, AbsorberComponent)
    )


def _mask_snapshots(
    project: StructureProjectPort, region_ids: list[str]
) -> tuple[MaskDefinitionSnapshot, ...]:
    """Return mask snapshots for the selected regions."""
    region_id_set = set(region_ids)
    return tuple(
        _mask_snapshot(mask)
        for mask in project.model.mask_definitions
        if mask.group_id in region_id_set
    )


def _mask_snapshot(mask: MaskDefinition) -> MaskDefinitionSnapshot:
    """Build a typed mask snapshot."""
    return MaskDefinitionSnapshot(
        identifier=mask.identifier,
        label=mask.label,
        mode=mask.mode.value,
        start_wavelength=mask.start_wavelength,
        end_wavelength=mask.end_wavelength,
        center=mask.center,
        half_width=mask.half_width,
        note=mask.note,
        color=mask.color,
        enabled=mask.enabled,
        group_id=mask.group_id,
    )


def _line_movements(
    project: StructureProjectPort, region_ids: list[str]
) -> tuple[LineRegionAssignment, ...]:
    """Return line origin assignments for merged regions."""
    assignments: list[LineRegionAssignment] = []
    for region_id in region_ids:
        region = project.find_absorption_region(region_id)
        if region is None:
            continue
        assignments.extend(
            LineRegionAssignment(line_id=line_id, region_id=region_id)
            for line_id in region.line_ids
        )
    return tuple(assignments)


def _multiplet_link_snapshots(
    project: StructureProjectPort, line_ids: tuple[str, ...]
) -> tuple[MultipletLinkSnapshot, ...]:
    """Capture exact multiplet links for preflight-validated line identities."""
    return tuple(
        MultipletLinkSnapshot(
            line_id=line_id,
            related_line_ids=tuple(project.absorption_lines[line_id].multiplet_ids),
        )
        for line_id in line_ids
    )


def _line_snapshot(line: AbsorptionLine) -> AbsorptionLineSnapshot:
    """Build a typed absorption line snapshot."""
    return AbsorptionLineSnapshot(
        line_id=line.line_id,
        species=line.species,
        rest_wavelength=line.rest_wavelength,
        center_z=line.center_z,
        window_kms=line.window_kms,
        multiplet_label=line.multiplet_label,
        transition_name=line.transition_name,
        oscillator_strength=line.oscillator_strength,
        gamma_value=line.gamma_value,
        lambda_range=line.lambda_range,
        region_id=line.region_id,
        multiplet_ids=tuple(line.multiplet_ids),
        model_ids=tuple(line.model_ids),
        needs_optimization=line.needs_optimization,
        created_by=line.created_by,
        created_at=line.created_at,
    )


__all__ = ["StructureOperationUseCase"]
