"""History event recording helpers for the GUI layer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from chappy.application.history.continuum_commands import (
    ContinuumAddComponentCommand,
    ContinuumAddPointCommand,
    ContinuumDeletePointCommand,
    ContinuumMovePointCommand,
    ContinuumResetCommand,
)
from chappy.application.history.identify_commands import (
    IdentifyAddTemporaryLineCommand,
    IdentifyClearTemporaryLinesCommand,
    IdentifyRegisterSelectedCommand,
    IdentifyRemoveTemporaryLineCommand,
)
from chappy.application.history.model_commands import (
    LineAnalysisHalfWidthHistoryCommand,
    ModelComponentHistoryCommand,
    ModelOptimizeApplyCommand,
    ModelParameterEditCommand,
)
from chappy.application.history.ports import (
    AbsorptionLineSnapshot,
    AbsorptionRegionSnapshot,
    ComponentParameterState,
    ContinuumPointSnapshot,
    LineAnalysisHalfWidthStateSnapshot,
    LineOptimizationStateSnapshot,
    MaskDefinitionSnapshot,
    RangeSnapshot,
    StructureDeleteModelHistorySnapshot,
    StructureMoveHistoryPayload,
    StructureStateSnapshot,
    StructureUnlinkHistoryPayload,
    TieSetSnapshot,
)
from chappy.application.history.range_commands import RangeHistoryCommand
from chappy.application.history.resolution_commands import (
    ResolutionHistoryCommand,
    ResolutionStateSnapshot,
)
from chappy.application.history.snapshot_builders import continuum_component_snapshot
from chappy.application.history.snapshot_mapping import (
    ModelLink,
    absorber_component_snapshot,
    absorption_line_snapshot,
    absorption_region_snapshot,
    model_link_snapshots,
    temporary_line_snapshots_for_ids,
    tie_set_snapshots,
)
from chappy.application.history.structure_commands import (
    MaskHistoryCommand,
    StructureDeleteCommand,
    StructureMergeCommand,
    StructureMoveLinkedLinesCommand,
    StructureSplitCommand,
    StructureUnlinkLinkedLinesCommand,
)
from chappy.application.history.tie_set_commands import TieSetEditCommand
from chappy.core.history import CommandHistory, HistoryEvent, OperationId

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from chappy.application.identify import TemporaryLineSnapshot
    from chappy.application.optimize import MaskMutationKind, ModelDeletionHistorySnapshot
    from chappy.core.components.absorber import AbsorberComponent
    from chappy.core.components.continuum import ContinuumComponent
    from chappy.core.components.tie_set import ParameterTieSet
    from chappy.core.identify_state import IdentifySessionState
    from chappy.core.spectroscopy_project import SpectroscopyProject

logger = logging.getLogger(__name__)


class HistoryRecorder:
    """Record typed history events into the core command history.

    Args:
        command_history: Core command history that receives events.
        project_provider: Callback returning the current project.
    """

    def __init__(
        self,
        command_history: CommandHistory,
        project_provider: Callable[[], SpectroscopyProject | None],
    ) -> None:
        """Initialize the recorder.

        Args:
            command_history: Core command history that receives events.
            project_provider: Callback returning the current project.
        """
        self._command_history = command_history
        self._project_provider = project_provider

    def atomic_recording(self) -> AbstractContextManager[None]:
        """Return a rollback scope for one multi-owner scientific command."""
        return self._command_history.atomic_recording()

    def suppress_recording(self) -> AbstractContextManager[None]:
        """Return a context suppressing nested history records."""
        return self._command_history.suppress_recording()

    def record_resolution_change(
        self, before: ResolutionStateSnapshot, after: ResolutionStateSnapshot
    ) -> None:
        """Record one exact spectral-resolution transition."""
        if self._command_history.is_suppressed or before == after:
            return
        self._command_history.push(
            HistoryEvent(command=ResolutionHistoryCommand(before=before, after=after))
        )

    def record_range_change(
        self,
        old_wave_range: tuple[float, float],
        new_wave_range: tuple[float, float],
        old_flux_range: tuple[float, float] | None,
        new_flux_range: tuple[float, float] | None,
        source: str,
    ) -> None:
        """Record a spectrum wavelength/flux range change to history."""
        event = HistoryEvent(
            command=RangeHistoryCommand(
                before=RangeSnapshot(wavelength_range=old_wave_range, flux_range=old_flux_range),
                after=RangeSnapshot(wavelength_range=new_wave_range, flux_range=new_flux_range),
                qualifier=source,
            )
        )
        self._command_history.push(event, coalesce=source in {"interactor", "intent"})

    def record_cont_add_point(
        self,
        continuum: ContinuumComponent,
        before_points: list[tuple[float, float]],
        after_points: list[tuple[float, float]],
    ) -> None:
        """Record continuum point addition to history.

        Args:
            continuum: The continuum component.
            before_points: Complete point order before the addition.
            after_points: Complete point order after the addition.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=ContinuumAddPointCommand(
                    continuum_id=continuum.id,
                    before=self._continuum_points(before_points),
                    after=self._continuum_points(after_points),
                )
            )
        )

    def record_cont_add_component(self, continuum: ContinuumComponent) -> None:
        """Record continuum component creation to history."""
        if self._command_history.is_suppressed:
            return
        project = self._project_provider()
        if project is None:
            msg = "Continuum component history recording requires an active project."
            raise RuntimeError(msg)
        self._command_history.push(
            HistoryEvent(
                command=ContinuumAddComponentCommand(
                    snapshot=continuum_component_snapshot(continuum),
                    component_index=project.model.components.index(continuum),
                )
            )
        )

    def record_cont_delete_point(
        self,
        continuum: ContinuumComponent,
        before_points: list[tuple[float, float]],
        after_points: list[tuple[float, float]],
    ) -> None:
        """Record continuum point deletion to history.

        Args:
            continuum: The continuum component.
            before_points: Complete point order before the deletion.
            after_points: Complete point order after the deletion.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=ContinuumDeletePointCommand(
                    continuum_id=continuum.id,
                    before=self._continuum_points(before_points),
                    after=self._continuum_points(after_points),
                )
            )
        )

    def record_cont_move_point(
        self,
        continuum: ContinuumComponent,
        before_points: list[tuple[float, float]],
        after_points: list[tuple[float, float]],
    ) -> None:
        """Record continuum point move to history.

        Args:
            continuum: The continuum component.
            before_points: Complete point order before the move.
            after_points: Complete point order after the move.
        """
        if self._command_history.is_suppressed or before_points == after_points:
            return
        self._command_history.push(
            HistoryEvent(
                command=ContinuumMovePointCommand(
                    continuum_id=continuum.id,
                    before=self._continuum_points(before_points),
                    after=self._continuum_points(after_points),
                )
            )
        )

    def record_cont_reset(
        self,
        continuum: ContinuumComponent,
        old_points: list[tuple[float, float]],
        new_points: list[tuple[float, float]],
    ) -> None:
        """Record continuum reset to history.

        Args:
            continuum: The continuum component.
            old_points: Points before reset.
            new_points: Points after reset.
        """
        if self._command_history.is_suppressed or old_points == new_points:
            return
        self._command_history.push(
            HistoryEvent(
                command=ContinuumResetCommand(
                    continuum_id=continuum.id,
                    before=self._continuum_points(old_points),
                    after=self._continuum_points(new_points),
                )
            )
        )

    @staticmethod
    def _continuum_points(points: list[tuple[float, float]]) -> tuple[ContinuumPointSnapshot, ...]:
        """Convert one exact ordered point collection to immutable snapshots."""
        return tuple(ContinuumPointSnapshot.from_position(point) for point in points)

    def record_structure_move_linked_lines(self, payload: StructureMoveHistoryPayload) -> None:
        """Record one complete structure move payload."""
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(command=StructureMoveLinkedLinesCommand(payload=payload))
        )
        logger.info(
            "Recorded group move: %d lines to %s",
            len(payload.expanded_line_ids),
            payload.destination_region_id,
        )

    def record_structure_split(
        self,
        expanded_line_ids: tuple[str, ...],
        source_region_id: str,
        new_region_id: str,
        before: StructureStateSnapshot,
        after: StructureStateSnapshot,
    ) -> None:
        """Record group split operation to history.

        Args:
            expanded_line_ids: Line IDs moved to the new region.
            source_region_id: Source region ID.
            new_region_id: New region ID.
            before: Exact topology before the split.
            after: Exact topology after the split.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=StructureSplitCommand(
                    expanded_line_ids=expanded_line_ids,
                    source_region_id=source_region_id,
                    new_region_id=new_region_id,
                    before=before,
                    after=after,
                )
            )
        )
        logger.info(
            "Recorded group split: %d lines from %s to %s",
            len(expanded_line_ids),
            source_region_id,
            new_region_id,
        )

    def record_structure_merge(
        self,
        primary_region_id: str,
        secondary_region_ids: tuple[str, ...],
        before: StructureStateSnapshot,
        after: StructureStateSnapshot,
    ) -> None:
        """Record group merge operation to history.

        Args:
            primary_region_id: Target region ID.
            secondary_region_ids: Merged region IDs.
            before: Exact topology before the merge.
            after: Exact topology after the merge.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=StructureMergeCommand(
                    primary_region_id=primary_region_id,
                    secondary_region_ids=secondary_region_ids,
                    before=before,
                    after=after,
                )
            )
        )
        logger.info(
            "Recorded group merge: %s absorbed %d regions",
            primary_region_id,
            len(secondary_region_ids),
        )

    def record_structure_delete(
        self,
        target_region_ids: tuple[str, ...],
        target_line_ids: tuple[str, ...],
        deleted_lines: tuple[AbsorptionLineSnapshot, ...],
        before: StructureStateSnapshot,
        after: StructureStateSnapshot,
        deleted_model_history: StructureDeleteModelHistorySnapshot | None,
    ) -> None:
        """Record group delete operation to history.

        Args:
            target_region_ids: Deleted region IDs.
            target_line_ids: Deleted line IDs.
            deleted_lines: Deleted line snapshots.
            before: Exact topology before deletion.
            after: Exact topology after deletion.
            deleted_model_history: Model topology deleted with the lines, if any.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=StructureDeleteCommand(
                    target_region_ids=target_region_ids,
                    target_line_ids=target_line_ids,
                    deleted_lines=deleted_lines,
                    before=before,
                    after=after,
                    model_command=self._structure_delete_model_command(deleted_model_history),
                )
            )
        )
        logger.info(
            "Recorded group delete: %d regions, %d lines",
            len(target_region_ids),
            len(target_line_ids),
        )

    def record_structure_unlink(self, payload: StructureUnlinkHistoryPayload) -> None:
        """Record one exact materialized linked-line unlink."""
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(command=StructureUnlinkLinkedLinesCommand(payload=payload))
        )
        logger.info("Recorded group unlink: %d lines", len(payload.line_ids))

    def _structure_delete_model_command(
        self, snapshot: StructureDeleteModelHistorySnapshot | None
    ) -> ModelComponentHistoryCommand | None:
        """Build the nested exact model transition for an structure delete."""
        if snapshot is None:
            return None
        project = self._project_provider()
        if project is None:
            msg = "Structure delete model history requires an active project."
            raise RuntimeError(msg)
        affected_uids = {tie_set.uid for tie_set in snapshot.tie_sets}
        tie_sets_after = tuple(
            tie_set for tie_set in project.model.iter_tie_sets() if tie_set.uid in affected_uids
        )
        ordered_tie_sets_after = tuple(project.model.iter_tie_sets())
        if snapshot.tie_sets:
            op_id = OperationId.MODEL_BULK_DELETE_MULTIPLET
        elif len(snapshot.components) > 1:
            op_id = OperationId.MODEL_BULK_DELETE
        else:
            op_id = OperationId.MODEL_DELETE
        return ModelComponentHistoryCommand(
            op_id=op_id,
            components=snapshot.components,
            component_indices=snapshot.component_indices,
            links=snapshot.links,
            tie_sets_before=snapshot.tie_sets,
            tie_set_indices_before=snapshot.tie_set_indices,
            tie_sets_after=tie_set_snapshots(tie_sets_after),
            tie_set_indices_after=tuple(
                ordered_tie_sets_after.index(tie_set) for tie_set in tie_sets_after
            ),
        )

    def record_ident_add_temporary_line(
        self, session: IdentifySessionState, added_temporary_line_ids: list[str]
    ) -> None:
        """Record temporary line addition.

        Args:
            session: Identify session state.
            added_temporary_line_ids: Added temporary line IDs.
        """
        if self._command_history.is_suppressed:
            return
        snapshots = temporary_line_snapshots_for_ids(session, tuple(added_temporary_line_ids))
        if not snapshots:
            return
        self._command_history.push(
            HistoryEvent(command=IdentifyAddTemporaryLineCommand(snapshots=snapshots))
        )
        logger.info(
            "Recorded ident.add_temporary_line: %d temporary lines", len(added_temporary_line_ids)
        )

    def record_ident_remove_temporary_line(
        self, removed_temporary_line_ids: list[str], snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> None:
        """Record temporary line removal.

        Args:
            removed_temporary_line_ids: Removed temporary line IDs.
            snapshots: Snapshots captured before removal.
        """
        if self._command_history.is_suppressed or not snapshots:
            return
        self._command_history.push(
            HistoryEvent(
                command=IdentifyRemoveTemporaryLineCommand(
                    temporary_line_ids=tuple(sorted(removed_temporary_line_ids)),
                    snapshots=snapshots,
                )
            )
        )
        logger.info(
            "Recorded ident.remove_temporary_line: %d temporary lines",
            len(removed_temporary_line_ids),
        )

    def record_ident_clear_temporary_lines(
        self, snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> None:
        """Record clearing all identify temporary lines.

        Args:
            snapshots: Snapshots captured before clearing.
        """
        if self._command_history.is_suppressed or not snapshots:
            return
        self._command_history.push(
            HistoryEvent(command=IdentifyClearTemporaryLinesCommand(snapshots=snapshots))
        )
        logger.info("Recorded ident.clear_temporary_lines: %d temporary lines", len(snapshots))

    def record_ident_register_selected(
        self,
        project: SpectroscopyProject,
        created_line_ids: list[str],
        created_region_ids: list[str],
        removed_temporary_line_ids: list[str],
        temporary_line_snapshots: tuple[TemporaryLineSnapshot, ...],
        affected_region_ids: list[str],
        before_affected_region_snapshots: tuple[AbsorptionRegionSnapshot, ...],
    ) -> None:
        """Record grouping confirmation.

        Args:
            project: Current project.
            created_line_ids: Created line IDs.
            created_region_ids: Created region IDs.
            removed_temporary_line_ids: Consumed temporary line IDs.
            temporary_line_snapshots: Temporary-line snapshots before confirmation.
            affected_region_ids: Region IDs needing range refresh.
            before_affected_region_snapshots: Exact existing-region state before commit.
        """
        if self._command_history.is_suppressed:
            return
        line_snapshots = tuple(
            absorption_line_snapshot(line)
            for line_id in created_line_ids
            if (line := project.absorption_lines.get(line_id)) is not None
        )
        after_affected_region_snapshots = tuple(
            absorption_region_snapshot(region)
            for region_id in affected_region_ids
            if (region := project.absorption_regions.get(region_id)) is not None
        )
        self._command_history.push(
            HistoryEvent(
                command=IdentifyRegisterSelectedCommand(
                    created_line_ids=tuple(sorted(created_line_ids)),
                    removed_temporary_line_ids=tuple(sorted(removed_temporary_line_ids)),
                    temporary_line_snapshots=temporary_line_snapshots,
                    affected_region_ids=tuple(sorted(affected_region_ids)),
                    line_snapshots=line_snapshots,
                    before_affected_region_snapshots=before_affected_region_snapshots,
                    after_affected_region_snapshots=after_affected_region_snapshots,
                )
            )
        )
        logger.info(
            "Recorded ident.register_selected: %d lines, %d regions",
            len(created_line_ids),
            len(created_region_ids),
        )

    def record_model_add(
        self, components: dict[str, AbsorberComponent], tie_sets: tuple[ParameterTieSet, ...]
    ) -> None:
        """Record single or multiplet component addition.

        Args:
            components: Mapping of line ID to added component.
            tie_sets: Parameter tie sets created alongside the components.
        """
        if self._command_history.is_suppressed:
            return
        links = self._links_for_added_components(components)
        has_multiplet = len(tie_sets) > 0
        is_bulk = len(components) > 1
        if has_multiplet:
            op_id = OperationId.MODEL_BULK_ADD_MULTIPLET
        elif is_bulk:
            op_id = OperationId.MODEL_BULK_ADD
        else:
            op_id = OperationId.MODEL_ADD
        project = self._project_provider()
        if project is None:
            msg = "Model component history recording requires an active project."
            raise RuntimeError(msg)
        component_values = tuple(components.values())
        ordered_tie_sets = tuple(project.model.iter_tie_sets())
        self._command_history.push(
            HistoryEvent(
                command=ModelComponentHistoryCommand(
                    op_id=op_id,
                    components=tuple(
                        absorber_component_snapshot(component) for component in component_values
                    ),
                    component_indices=tuple(
                        project.model.components.index(component) for component in component_values
                    ),
                    links=model_link_snapshots(links),
                    tie_sets_before=(),
                    tie_set_indices_before=(),
                    tie_sets_after=tie_set_snapshots(tie_sets),
                    tie_set_indices_after=tuple(
                        ordered_tie_sets.index(tie_set) for tie_set in tie_sets
                    ),
                )
            )
        )
        logger.info("Recorded model add: %d components", len(components))

    def record_model_delete_snapshot(self, snapshot: ModelDeletionHistorySnapshot) -> None:
        """Record component deletion from immutable pre-mutation state."""
        if self._command_history.is_suppressed:
            return
        has_multiplet = bool(snapshot.tie_sets)
        is_bulk = len(snapshot.components) > 1
        if has_multiplet:
            op_id = OperationId.MODEL_BULK_DELETE_MULTIPLET
        elif is_bulk:
            op_id = OperationId.MODEL_BULK_DELETE
        else:
            op_id = OperationId.MODEL_DELETE
        project = self._project_provider()
        if project is None:
            msg = "Model deletion history recording requires an active project."
            raise RuntimeError(msg)
        affected_uids = {tie_set.uid for tie_set in snapshot.tie_sets}
        tie_sets_after = tuple(
            tie_set for tie_set in project.model.iter_tie_sets() if tie_set.uid in affected_uids
        )
        ordered_tie_sets_after = tuple(project.model.iter_tie_sets())
        self._command_history.push(
            HistoryEvent(
                command=ModelComponentHistoryCommand(
                    op_id=op_id,
                    components=snapshot.components,
                    component_indices=snapshot.component_indices,
                    links=snapshot.links,
                    tie_sets_before=snapshot.tie_sets,
                    tie_set_indices_before=snapshot.tie_set_indices,
                    tie_sets_after=tie_set_snapshots(tie_sets_after),
                    tie_set_indices_after=tuple(
                        ordered_tie_sets_after.index(tie_set) for tie_set in tie_sets_after
                    ),
                )
            )
        )
        logger.info("Recorded model delete: %d components", len(snapshot.components))

    def record_model_edit_params(
        self,
        component_ids: list[str],
        param_name: str,
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        region_id: str | None,
    ) -> None:
        """Record parameter edit.

        Args:
            component_ids: Affected component IDs.
            param_name: Edited parameter name.
            before_states: Parameter snapshots before edit.
            after_states: Parameter snapshots after edit.
            region_id: Optional region ID for targeted refresh.
        """
        if self._command_history.is_suppressed or before_states == after_states:
            return
        self._command_history.push(
            HistoryEvent(
                command=ModelParameterEditCommand(
                    param_name=param_name,
                    component_ids=tuple(component_ids),
                    before=before_states,
                    after=after_states,
                    region_id=region_id,
                )
            )
        )
        logger.info(
            "Recorded model edit params: %s for %d components", param_name, len(component_ids)
        )

    def record_model_optimize_apply(
        self,
        target_component_ids: list[str],
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        region_id: str | None,
        needs_optimization_before: tuple[LineOptimizationStateSnapshot, ...],
    ) -> None:
        """Record optimization result application.

        Args:
            target_component_ids: Affected component IDs.
            before_states: Parameter snapshots before fit.
            after_states: Parameter snapshots after fit.
            region_id: Region ID for UI refresh.
            needs_optimization_before: Previous optimization flags by line ID.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=ModelOptimizeApplyCommand(
                    component_ids=tuple(target_component_ids),
                    before=before_states,
                    after=after_states,
                    region_id=region_id,
                    needs_optimization_before=needs_optimization_before,
                )
            )
        )
        logger.info("Recorded model optimize: %d components", len(target_component_ids))

    def record_tie_set_create(
        self,
        uid: str,
        before_component_states: tuple[ComponentParameterState, ...],
        after_tie_set: TieSetSnapshot,
        after_tie_set_index: int,
    ) -> None:
        """Record parameter tie set creation.

        Args:
            uid: Unique identifier of the created tie set.
            before_component_states: Individual component states before binding.
            after_tie_set: Snapshot of the created tie set.
            after_tie_set_index: Exact storage index after creation.
        """
        if self._command_history.is_suppressed:
            return
        self._command_history.push(
            HistoryEvent(
                command=TieSetEditCommand(
                    op_id=OperationId.MODEL_TIE_SET_CREATE,
                    uids=(uid,),
                    before_tie_sets=(),
                    before_tie_set_indices=(),
                    after_tie_sets=(after_tie_set,),
                    after_tie_set_indices=(after_tie_set_index,),
                    before_component_states=before_component_states,
                    after_component_states=(),
                )
            )
        )
        logger.info("Recorded model.tie_set_create: %s", uid)

    def record_tie_set_remove(
        self,
        uids: tuple[str, ...],
        before_tie_sets: tuple[TieSetSnapshot, ...],
        before_tie_set_indices: tuple[int, ...],
        after_tie_sets: tuple[TieSetSnapshot, ...],
        after_tie_set_indices: tuple[int, ...],
        after_component_states: tuple[ComponentParameterState, ...],
    ) -> None:
        """Record parameter tie set member removal or dissolution.

        Args:
            uids: Tie set uids affected by the removal.
            before_tie_sets: Snapshots of affected tie sets before removal.
            before_tie_set_indices: Exact storage indices before removal.
            after_tie_sets: Snapshots of tie sets that survived the removal.
            after_tie_set_indices: Exact storage indices after removal.
            after_component_states: Individual states of unbound components.
        """
        if self._command_history.is_suppressed or not before_tie_sets:
            return
        op_id = (
            OperationId.MODEL_TIE_SET_DISSOLVE
            if not after_tie_sets
            else OperationId.MODEL_TIE_SET_REMOVE
        )
        self._command_history.push(
            HistoryEvent(
                command=TieSetEditCommand(
                    op_id=op_id,
                    uids=uids,
                    before_tie_sets=before_tie_sets,
                    before_tie_set_indices=before_tie_set_indices,
                    after_tie_sets=after_tie_sets,
                    after_tie_set_indices=after_tie_set_indices,
                    before_component_states=(),
                    after_component_states=after_component_states,
                )
            )
        )
        logger.info("Recorded %s: %d tie sets", op_id, len(uids))

    def record_mask_mutation(
        self,
        *,
        kind: MaskMutationKind,
        mask_id: str,
        before: MaskDefinitionSnapshot | None,
        after: MaskDefinitionSnapshot | None,
        before_index: int | None,
        after_index: int | None,
        affected_region_ids: tuple[str, ...],
    ) -> None:
        """Record one typed mask create, update, or remove."""
        if self._command_history.is_suppressed or (
            before == after and before_index == after_index
        ):
            return
        operation_ids = {
            "create": OperationId.MASK_CREATE,
            "update": OperationId.MASK_EDIT,
            "remove": OperationId.MASK_DELETE,
        }
        try:
            operation_id = operation_ids[kind.value]
        except KeyError as error:
            msg = f"Unsupported mask mutation kind: {kind}"
            raise ValueError(msg) from error
        self._command_history.push(
            HistoryEvent(
                command=MaskHistoryCommand(
                    op_id=operation_id,
                    mask_id=mask_id,
                    before=before,
                    after=after,
                    before_index=before_index,
                    after_index=after_index,
                    affected_region_ids=tuple(dict.fromkeys(affected_region_ids)),
                )
            )
        )
        logger.info("Recorded %s: mask=%s", operation_id, mask_id)

    def record_line_analysis_half_width_change(
        self,
        affected_line_ids: tuple[str, ...],
        before_states: tuple[LineAnalysisHalfWidthStateSnapshot, ...],
        after_states: tuple[LineAnalysisHalfWidthStateSnapshot, ...],
        region_id: str,
    ) -> None:
        """Record one Optimize scientific range edit."""
        if self._command_history.is_suppressed or before_states == after_states:
            return
        self._command_history.push(
            HistoryEvent(
                command=LineAnalysisHalfWidthHistoryCommand(
                    affected_line_ids=affected_line_ids,
                    before=before_states,
                    after=after_states,
                    region_id=region_id,
                )
            )
        )
        logger.info(
            "Recorded line analysis half-width change: region=%s, affected=%d lines",
            region_id,
            len(affected_line_ids),
        )

    def _links_for_added_components(
        self, components: dict[str, AbsorberComponent]
    ) -> list[ModelLink]:
        """Build line-component links for added components.

        Args:
            components: Mapping of line ID to added component.

        Returns:
            Link snapshots with stable positions.
        """
        project = self._project_provider()
        links: list[ModelLink] = []
        for line_id, component in components.items():
            line = project.absorption_lines.get(line_id) if project is not None else None
            index = (
                line.model_ids.index(component.id)
                if line and component.id in line.model_ids
                else -1
            )
            links.append({"line_id": line_id, "component_id": component.id, "index": index})
        return links
