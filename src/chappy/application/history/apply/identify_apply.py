"""Identify temporary-line registration history application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.application.history import HistoryApplyError, HistoryApplyErrorCode
from chappy.application.history.snapshot_mapping import (
    absorption_line_snapshot,
    absorption_region_snapshot,
    temporary_line_snapshot,
)
from chappy.application.structure import (
    StructureInvalidationScope,
    StructureMutationOutcome,
    StructureMutationResult,
)
from chappy.core.change_set import ChangeSet as DomainChangeSet

from .structure_apply import structure_history_delta

if TYPE_CHECKING:
    from chappy.application.history import (
        HistoryApplyResult,
        HistoryCommandContext,
        IdentifyRegisterSelectedCommand,
    )
    from chappy.application.structure import (
        AtomicStructureMutationExecutor,
        StructureTopologySnapshot,
        StructureTopologySnapshotService,
    )
    from chappy.core.identify_state import IdentifySessionState, TemporaryLine
    from chappy.core.spectroscopy_project import SpectroscopyProject


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationHistorySnapshot:
    """Exact project topology and temporary-line session state for rollback."""

    topology: StructureTopologySnapshot
    temporary_lines: tuple[TemporaryLine, ...]


def validate_identify_registration_command(command: IdentifyRegisterSelectedCommand) -> None:
    """Validate complete registration identities and affected-region snapshots."""
    created_line_ids = tuple(snapshot.line_id for snapshot in command.line_snapshots)
    temporary_line_ids = tuple(
        snapshot.temporary_line_id for snapshot in command.temporary_line_snapshots
    )
    before_ids = tuple(snapshot.region_id for snapshot in command.before_affected_region_snapshots)
    after_ids = tuple(snapshot.region_id for snapshot in command.after_affected_region_snapshots)
    if (
        not command.created_line_ids
        or len(set(command.created_line_ids)) != len(command.created_line_ids)
        or set(created_line_ids) != set(command.created_line_ids)
        or len(set(created_line_ids)) != len(created_line_ids)
        or not command.removed_temporary_line_ids
        or len(set(command.removed_temporary_line_ids)) != len(command.removed_temporary_line_ids)
        or set(temporary_line_ids) != set(command.removed_temporary_line_ids)
        or len(set(temporary_line_ids)) != len(temporary_line_ids)
        or not command.affected_region_ids
        or len(set(command.affected_region_ids)) != len(command.affected_region_ids)
        or len(set(before_ids)) != len(before_ids)
        or len(set(after_ids)) != len(after_ids)
        or set(before_ids) - set(after_ids)
        or set(after_ids) != set(command.affected_region_ids)
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Identify registration history identities are inconsistent.",
        )
    after_by_id = {
        snapshot.region_id: snapshot for snapshot in command.after_affected_region_snapshots
    }
    if any(
        line.region_id not in after_by_id
        or line.line_id not in after_by_id[line.region_id].line_ids
        for line in command.line_snapshots
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Identify registration lines do not match affected region snapshots.",
        )


def require_identify_registration_temporal_state(
    project: SpectroscopyProject,
    session: IdentifySessionState,
    command: IdentifyRegisterSelectedCommand,
    *,
    before: bool,
) -> None:
    """Require exact selected temporary lines, created lines, and affected regions."""
    expected_regions = (
        command.before_affected_region_snapshots
        if before
        else command.after_affected_region_snapshots
    )
    current_regions = tuple(
        absorption_region_snapshot(project.absorption_regions[snapshot.region_id])
        for snapshot in expected_regions
        if snapshot.region_id in project.absorption_regions
    )
    if current_regions != expected_regions:
        missing = {snapshot.region_id for snapshot in expected_regions} - set(
            project.absorption_regions
        )
        code = (
            HistoryApplyErrorCode.TARGET_NOT_FOUND
            if missing
            else HistoryApplyErrorCode.INVALID_STATE
        )
        raise HistoryApplyError(
            code, "Identify registration affected region source state is not exact."
        )

    before_region_ids = {
        snapshot.region_id for snapshot in command.before_affected_region_snapshots
    }
    created_region_ids = {
        snapshot.region_id for snapshot in command.after_affected_region_snapshots
    } - before_region_ids
    if before and created_region_ids & set(project.absorption_regions):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Identify registration created region already exists in the before-state.",
        )

    current_lines = {
        line_id: project.absorption_lines.get(line_id) for line_id in command.created_line_ids
    }
    if before:
        if any(line is not None for line in current_lines.values()):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Identify registration created line already exists in the before-state.",
            )
    else:
        expected_lines = {snapshot.line_id: snapshot for snapshot in command.line_snapshots}
        if any(
            line is None or absorption_line_snapshot(line) != expected_lines[line_id]
            for line_id, line in current_lines.items()
        ):
            missing_line_ids = tuple(
                line_id for line_id, line in current_lines.items() if line is None
            )
            code = (
                HistoryApplyErrorCode.TARGET_NOT_FOUND
                if missing_line_ids
                else HistoryApplyErrorCode.INVALID_STATE
            )
            raise HistoryApplyError(code, "Identify registration created line state is not exact.")

    temporary_lines_by_id = {
        temporary_line.temporary_line_id: temporary_line
        for temporary_line in session.temporary_lines
    }
    if before:
        if any(
            (temporary_line := temporary_lines_by_id.get(snapshot.temporary_line_id)) is None
            or temporary_line_snapshot(temporary_line) != snapshot
            for snapshot in command.temporary_line_snapshots
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Identify registration temporary-line source state is not exact.",
            )
    elif any(
        temporary_line_id in temporary_lines_by_id
        for temporary_line_id in command.removed_temporary_line_ids
    ):
        raise HistoryApplyError(
            HistoryApplyErrorCode.INVALID_STATE,
            "Identify registration consumed temporary line still exists in the after-state.",
        )


class IdentifyApply:
    """Apply Identify temporary-line registration history."""

    def __init__(
        self,
        structure_executor: AtomicStructureMutationExecutor,
        structure_topology: StructureTopologySnapshotService,
    ) -> None:
        """Initialize with the shared structure executor and topology snapshot service."""
        self._structure_executor = structure_executor
        self._structure_topology = structure_topology

    def apply(
        self,
        project: SpectroscopyProject,
        session: IdentifySessionState,
        command: IdentifyRegisterSelectedCommand,
        *,
        context: HistoryCommandContext,
        is_undo: bool,
    ) -> tuple[HistoryApplyResult, DomainChangeSet]:
        """Apply Identify registration topology and temporary lines atomically."""
        source_is_before = not is_undo
        before_region_ids: tuple[str, ...] = ()
        before_memberships: dict[str, tuple[str, ...]] = {}
        before_multiplet_links: dict[str, tuple[str, ...]] = {}

        def preflight() -> StructureMutationOutcome:
            validate_identify_registration_command(command)
            require_identify_registration_temporal_state(
                project, session, command, before=source_is_before
            )
            return StructureMutationOutcome.CHANGED

        def capture_runtime() -> IdentifyRegistrationHistorySnapshot:
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
            return IdentifyRegistrationHistorySnapshot(
                topology=self._structure_topology.capture(project),
                temporary_lines=session.snapshot_temporary_lines_for_transaction(),
            )

        def mutate() -> StructureMutationResult[HistoryApplyResult]:
            result = command.undo(context) if is_undo else command.redo(context)
            if not result.success:
                error_code = result.error_code or HistoryApplyErrorCode.INVALID_STATE
                raise HistoryApplyError(
                    error_code, f"Identify registration history mutation failed: {error_code}"
                )
            require_identify_registration_temporal_state(project, session, command, before=is_undo)
            return StructureMutationResult.changed_result(
                result,
                structure_history_delta(
                    project,
                    before_region_ids=before_region_ids,
                    before_memberships=before_memberships,
                    before_multiplet_links=before_multiplet_links,
                    invalidation_scope=StructureInvalidationScope.LOCAL_SURVIVORS,
                ),
            )

        def restore_runtime(snapshot: IdentifyRegistrationHistorySnapshot) -> None:
            self._structure_topology.restore(project, snapshot.topology)
            session.replace_temporary_lines_for_transaction(snapshot.temporary_lines)

        execution = self._structure_executor.execute(
            project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=restore_runtime,
            notification_scope=project.model.suppress_scientific_notifications,
            rebuild_derived=DomainChangeSet.empty,
        )
        result = execution.result.value
        if result is None:
            msg = "Changed Identify registration history produced no application result."
            raise RuntimeError(msg)
        return result, execution.postcommit_changes


__all__ = [
    "IdentifyApply",
    "IdentifyRegistrationHistorySnapshot",
    "require_identify_registration_temporal_state",
    "validate_identify_registration_command",
]
