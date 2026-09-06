"""Atomic transaction boundary for Identify temporary-line registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.application.structure import (
    AtomicStructureMutationExecutor,
    AtomicStructureProjectPort,
    StructureInvalidationScope,
    StructureMutationOutcome,
    StructureMutationResult,
    StructureRegionDelta,
    StructureTopologyProjectPort,
    StructureTopologySnapshot,
    StructureTopologySnapshotService,
)
from chappy.core.change_set import ChangeSet

from .models import (
    ExistingRegionSnapshot,
    IdentifyRegistrationPlan,
    RegistrationOutcome,
    TemporaryLineSnapshot,
)
from .registration_impact import (
    IdentifyRegistrationImpactPreviewUseCase,
    IdentifyRegistrationImpactRequest,
)
from .registration_usecase import (
    IdentifyProjectMutationPort,
    RegisterSelectedLinesRequest,
    RegisterSelectedLinesResult,
    RegisterSelectedLinesUseCase,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from contextlib import AbstractContextManager

    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.identify_state import TemporaryLine
    from chappy.core.velocity_ranges import MultipletGroupingVelocityTolerance


class AtomicIdentifyRegistrationProjectPort(
    IdentifyProjectMutationPort, AtomicStructureProjectPort, StructureTopologyProjectPort, Protocol
):
    """Complete project storage required by atomic Identify registration."""

    def list_absorption_lines(self) -> list[AbsorptionLine]:
        """Return current absorption lines in storage order."""
        ...


class AtomicIdentifyRegistrationSessionPort(Protocol):
    """Temporary-line session storage participating in registration rollback."""

    @property
    def temporary_lines(self) -> Sequence[TemporaryLine]:
        """Return current temporary lines in storage order."""
        ...

    def remove_temporary_lines(self, temporary_line_ids: Iterable[str]) -> list[str]:
        """Remove processed temporary lines."""
        ...

    def snapshot_temporary_lines_for_transaction(self) -> tuple[TemporaryLine, ...]:
        """Capture exact temporary-line object identity and order."""
        ...

    def replace_temporary_lines_for_transaction(
        self, temporary_lines: Sequence[TemporaryLine]
    ) -> None:
        """Restore exact temporary-line object identity and order."""
        ...


type RegistrationHistoryCallback = Callable[[RegistrationOutcome], None]
type RegistrationHistoryScope = Callable[[], AbstractContextManager[None]]


@dataclass(frozen=True, slots=True)
class AtomicRegisterSelectedLinesRequest:
    """Exact runtime inputs for one atomic Identify registration command."""

    project: AtomicIdentifyRegistrationProjectPort
    session: AtomicIdentifyRegistrationSessionPort
    temporary_lines: tuple[TemporaryLineSnapshot, ...]
    existing_regions: tuple[ExistingRegionSnapshot, ...]
    region_line_memberships: tuple[tuple[str, tuple[str, ...]], ...]
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance
    unknown_label: str
    record_history: RegistrationHistoryCallback | None = None
    history_scope: RegistrationHistoryScope | None = None


@dataclass(frozen=True, slots=True)
class AtomicRegisterSelectedLinesResult:
    """Typed registration outcome and committed region impact."""

    mutation_outcome: StructureMutationOutcome
    outcome: RegistrationOutcome | None = None
    mode_sync_line_ids: tuple[str, ...] = ()
    region_delta: StructureRegionDelta | None = None

    def __post_init__(self) -> None:
        """Require registration evidence and impact exactly for Changed."""
        if self.mutation_outcome is StructureMutationOutcome.CHANGED:
            if self.outcome is None or self.region_delta is None:
                msg = "Changed Identify registration requires outcome and region impact."
                raise ValueError(msg)
        elif self.outcome is not None or self.mode_sync_line_ids or self.region_delta is not None:
            msg = "NoChange Identify registration cannot carry committed evidence."
            raise ValueError(msg)

    @property
    def changed(self) -> bool:
        """Return whether scientific registration state changed."""
        return self.mutation_outcome is StructureMutationOutcome.CHANGED


@dataclass(frozen=True, slots=True)
class _RegistrationRuntimeSnapshot:
    """Project topology and Identify session state restored after an abort."""

    topology: StructureTopologySnapshot
    temporary_lines: tuple[TemporaryLine, ...]


class AtomicIdentifyRegistrationUseCase:
    """Register temporary lines, invalidate analysis, and record history atomically."""

    def __init__(
        self,
        mutation: RegisterSelectedLinesUseCase | None = None,
        *,
        executor: AtomicStructureMutationExecutor | None = None,
        topology: StructureTopologySnapshotService | None = None,
        impact_preview: IdentifyRegistrationImpactPreviewUseCase | None = None,
    ) -> None:
        """Initialize the transaction with injectable pure services."""
        self._mutation = mutation or RegisterSelectedLinesUseCase()
        self._executor = executor or AtomicStructureMutationExecutor()
        self._topology = topology or StructureTopologySnapshotService()
        self._impact_preview = impact_preview or IdentifyRegistrationImpactPreviewUseCase()

    def register(
        self, request: AtomicRegisterSelectedLinesRequest
    ) -> AtomicRegisterSelectedLinesResult:
        """Execute one exact-preflighted registration transaction."""
        before_region_ids: tuple[str, ...] = ()
        before_memberships: dict[str, tuple[str, ...]] = {}
        plan: IdentifyRegistrationPlan | None = None

        def preflight() -> StructureMutationOutcome:
            nonlocal plan
            plan = self._impact_preview.preview(self._impact_request(request))
            return plan.impact.mutation_outcome

        def capture_runtime() -> _RegistrationRuntimeSnapshot:
            nonlocal before_region_ids, before_memberships
            before_region_ids = tuple(request.project.absorption_regions)
            before_memberships = {
                region_id: tuple(region.line_ids)
                for region_id, region in request.project.absorption_regions.items()
            }
            return _RegistrationRuntimeSnapshot(
                topology=self._topology.capture(request.project),
                temporary_lines=request.session.snapshot_temporary_lines_for_transaction(),
            )

        def mutate() -> StructureMutationResult[RegisterSelectedLinesResult]:
            if (
                plan is None
                or plan.impact.mutation_outcome is not StructureMutationOutcome.CHANGED
            ):
                msg = "Changed Identify registration preflight did not retain its plan."
                raise RuntimeError(msg)
            result = self._mutation.register(
                RegisterSelectedLinesRequest(
                    project=request.project, session=request.session, plan=plan
                )
            )
            if result.outcome is None:
                msg = "Changed Identify registration produced no registered lines."
                raise RuntimeError(msg)
            region_delta = self._region_delta(
                request.project,
                before_region_ids=before_region_ids,
                before_memberships=before_memberships,
            )
            self._require_committed_impact_matches_plan(plan, result.outcome, region_delta)
            return StructureMutationResult.changed_result(result, region_delta)

        def restore_runtime(snapshot: _RegistrationRuntimeSnapshot) -> None:
            self._topology.restore(request.project, snapshot.topology)
            request.session.replace_temporary_lines_for_transaction(snapshot.temporary_lines)

        def record_history(result: StructureMutationResult[RegisterSelectedLinesResult]) -> None:
            if request.record_history is None:
                return
            if result.value is None or result.value.outcome is None:
                msg = "Committed Identify registration has no history outcome."
                raise RuntimeError(msg)
            request.record_history(result.value.outcome)

        execution = self._executor.execute(
            request.project,
            preflight=preflight,
            capture_runtime=capture_runtime,
            mutate=mutate,
            restore_runtime=restore_runtime,
            notification_scope=request.project.model.suppress_scientific_notifications,
            rebuild_derived=ChangeSet.empty,
            record_history=record_history if request.record_history is not None else None,
            history_scope=request.history_scope,
        )
        if not execution.result.changed:
            return AtomicRegisterSelectedLinesResult(
                mutation_outcome=StructureMutationOutcome.NO_CHANGE
            )
        if execution.result.value is None:
            msg = "Committed Identify registration did not return a result."
            raise RuntimeError(msg)
        if execution.result.delta is None or execution.result.value.outcome is None:
            msg = "Committed Identify registration did not return typed impact."
            raise RuntimeError(msg)

        run_postcommit_actions_isolated(
            lambda: request.project.model.publish_storage_changes(execution.postcommit_changes)
        )
        return AtomicRegisterSelectedLinesResult(
            mutation_outcome=execution.result.outcome,
            outcome=execution.result.value.outcome,
            mode_sync_line_ids=execution.result.value.mode_sync_line_ids,
            region_delta=execution.result.delta,
        )

    @staticmethod
    def _impact_request(
        request: AtomicRegisterSelectedLinesRequest,
    ) -> IdentifyRegistrationImpactRequest:
        """Project the command request onto the read-only impact boundary."""
        return IdentifyRegistrationImpactRequest(
            project=request.project,
            session=request.session,
            temporary_lines=request.temporary_lines,
            existing_regions=request.existing_regions,
            region_line_memberships=request.region_line_memberships,
            multiplet_grouping_tolerance=request.multiplet_grouping_tolerance,
            unknown_label=request.unknown_label,
        )

    @staticmethod
    def _require_committed_impact_matches_plan(
        plan: IdentifyRegistrationPlan,
        outcome: RegistrationOutcome,
        region_delta: StructureRegionDelta,
    ) -> None:
        """Require the materialized topology delta to equal the previewed plan."""
        impact = plan.impact
        if len(outcome.created_line_ids) != impact.created_line_count:
            msg = "Identify registration created-line delta does not match its preview."
            raise RuntimeError(msg)
        if len(region_delta.created_region_ids) != impact.created_region_count:
            msg = "Identify registration created-region delta does not match its preview."
            raise RuntimeError(msg)
        if region_delta.affected_surviving_region_ids != impact.affected_existing_region_ids:
            msg = "Identify registration existing-region delta does not match its preview."
            raise RuntimeError(msg)
        if outcome.appended_region_ids != impact.affected_existing_region_ids:
            msg = "Identify registration outcome regions do not match its preview."
            raise RuntimeError(msg)
        if outcome.failed_count != len(impact.rejected_temporary_line_ids):
            msg = "Identify registration rejected lines do not match its preview."
            raise RuntimeError(msg)
        if outcome.processed_temporary_line_ids != (
            *impact.registerable_temporary_line_ids,
            *impact.rejected_temporary_line_ids,
        ):
            msg = "Identify registration processed lines do not match its preview."
            raise RuntimeError(msg)
        if outcome.multi_overlap_warning is not impact.multi_overlap_warning:
            msg = "Identify registration overlap warning does not match its preview."
            raise RuntimeError(msg)

    @staticmethod
    def _region_delta(
        project: AtomicIdentifyRegistrationProjectPort,
        *,
        before_region_ids: tuple[str, ...],
        before_memberships: dict[str, tuple[str, ...]],
    ) -> StructureRegionDelta:
        """Derive created and affected identities from final registration topology."""
        before = set(before_region_ids)
        after_region_ids = tuple(project.absorption_regions)
        after = set(after_region_ids)
        affected = tuple(
            region_id
            for region_id in after_region_ids
            if region_id in before
            and before_memberships[region_id]
            != tuple(project.absorption_regions[region_id].line_ids)
        )
        return StructureRegionDelta(
            invalidation_scope=StructureInvalidationScope.LOCAL_SURVIVORS,
            affected_surviving_region_ids=affected,
            created_region_ids=tuple(
                region_id for region_id in after_region_ids if region_id not in before
            ),
            removed_region_ids=tuple(
                region_id for region_id in before_region_ids if region_id not in after
            ),
        )


__all__ = [
    "AtomicIdentifyRegistrationProjectPort",
    "AtomicIdentifyRegistrationSessionPort",
    "AtomicIdentifyRegistrationUseCase",
    "AtomicRegisterSelectedLinesRequest",
    "AtomicRegisterSelectedLinesResult",
    "RegistrationHistoryCallback",
    "RegistrationHistoryScope",
]
