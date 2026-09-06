"""Atomic transaction boundary for scientific project structure mutations."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from chappy.core.analysis import AnalysisRevision, RegionAnalysisState
from chappy.core.change_set import ChangeSet
from chappy.core.events import RegionTopologyChanged

from .models import (
    AtomicStructureMutationExecution,
    StructureInvalidationScope,
    StructureMutationOutcome,
    StructureMutationResult,
    StructureRegionDelta,
)
from .region_line_topology import find_region_line_topology_issues
from .topology import StructureTopologyProjectPort
from .topology_validation import StructureTopologyValidation, StructureTopologyValidator

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from contextlib import AbstractContextManager
    from datetime import datetime

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.spectrum_model import SpectrumModel, SpectrumModelDerivedStateSnapshot


class AtomicStructureProjectPort(StructureTopologyProjectPort, Protocol):
    """Project facts required by a scientific structure transaction."""

    modified: datetime
    absorption_lines: dict[str, AbsorptionLine]
    absorption_regions: dict[str, AbsorptionRegion]
    model: SpectrumModel

    def region_analysis_state(self, region_id: str) -> RegionAnalysisState | None:
        """Return semantic analysis state for an existing region."""
        ...

    def stored_region_analysis_states_for_transaction(self) -> tuple[RegionAnalysisState, ...]:
        """Return only explicitly stored analysis states in exact order."""
        ...

    def set_region_analysis_states(self, states: Iterable[RegionAnalysisState]) -> None:
        """Atomically update analysis states for existing regions."""
        ...

    def replace_region_analysis_states_for_transaction(
        self, states: Iterable[RegionAnalysisState]
    ) -> None:
        """Replace exact stored analysis state without changing modified time."""
        ...

    def prune_region_analysis_states_for_transaction(self) -> None:
        """Remove stored states whose regions no longer exist."""
        ...

    def reset_region_analysis_states_for_transaction(self, region_ids: Iterable[str]) -> None:
        """Reset existing regions to implicit revision-zero state."""
        ...

    def is_region_analysis_capable(self, region_id: str) -> bool:
        """Return whether one current region supports scientific analysis."""
        ...

    def mark_region_needs_optimization(self, region_id: str) -> int:
        """Mark every line in one current region as requiring analysis."""
        ...

    def mark_scientific_modified(self) -> None:
        """Record a committed scientific mutation."""
        ...


@dataclass(frozen=True, slots=True)
class _StructureProjectSnapshot:
    """Project-owned facts restored after any transaction failure."""

    modified: datetime
    stored_analysis_states: tuple[RegionAnalysisState, ...]
    semantic_analysis_states: tuple[RegionAnalysisState, ...]
    region_line_memberships: tuple[tuple[str, tuple[str, ...]], ...]
    line_multiplet_links: tuple[tuple[str, tuple[str, ...]], ...]
    optimization_flags: tuple[tuple[str, bool], ...]
    derived_state: SpectrumModelDerivedStateSnapshot
    topology_validation: StructureTopologyValidation


class AtomicStructureMutationExecutor:
    """Commit structure, freshness invalidation, and history as one unit.

    Runtime topology is deliberately opaque and caller-owned. The executor owns
    analysis states, line freshness flags, derived caches, modified time, and the
    ordering of rollback stages. Domain and GUI notifications are returned to the
    caller and must be published only after this method succeeds.
    """

    def __init__(self, topology_validator: StructureTopologyValidator | None = None) -> None:
        self._topology_validator = topology_validator or StructureTopologyValidator()

    def execute[TValue, TRuntime](  # noqa: PLR0913 - transaction seams are explicit
        self,
        project: AtomicStructureProjectPort,
        *,
        preflight: Callable[[], StructureMutationOutcome],
        capture_runtime: Callable[[], TRuntime],
        mutate: Callable[[], StructureMutationResult[TValue]],
        restore_runtime: Callable[[TRuntime], None],
        notification_scope: Callable[[], AbstractContextManager[None]],
        rebuild_derived: Callable[[], ChangeSet],
        record_history: Callable[[StructureMutationResult[TValue]], None] | None = None,
        history_scope: Callable[[], AbstractContextManager[None]] | None = None,
    ) -> AtomicStructureMutationExecution[TValue]:
        """Execute one preflighted structure mutation with exact rollback."""
        if record_history is not None and history_scope is None:
            msg = "Atomic structure history recording requires a rollback scope."
            raise ValueError(msg)

        outcome = preflight()
        if outcome is StructureMutationOutcome.NO_CHANGE:
            return AtomicStructureMutationExecution(
                result=StructureMutationResult.no_change(), postcommit_changes=ChangeSet.empty()
            )

        before_region_ids = tuple(project.absorption_regions)
        snapshot = self._snapshot_project(project, before_region_ids)
        runtime_snapshot = capture_runtime()
        history_context = history_scope() if history_scope is not None else nullcontext()

        try:
            with history_context, notification_scope():
                result = mutate()
                declared_delta = self._require_changed_result(result)

                after_region_ids = tuple(project.absorption_regions)
                self._validate_after_topology(project)
                self._topology_validator.require_no_regressions(
                    project, snapshot.topology_validation
                )
                effective_delta = self._validate_and_resolve_delta(
                    project,
                    declared_delta,
                    before_region_ids=before_region_ids,
                    before_region_line_memberships=snapshot.region_line_memberships,
                    before_line_multiplet_links=snapshot.line_multiplet_links,
                    after_region_ids=after_region_ids,
                )
                self._validate_surviving_analysis_states(project, snapshot, effective_delta)
                self._validate_surviving_line_flags(project, snapshot)

                postcommit_changes = rebuild_derived()
                project.prune_region_analysis_states_for_transaction()
                self._invalidate_surviving_regions(project, snapshot, effective_delta)
                project.reset_region_analysis_states_for_transaction(
                    effective_delta.created_region_ids
                )
                self._require_created_region_defaults(project, effective_delta.created_region_ids)
                for region_id in dict.fromkeys(
                    (
                        *effective_delta.affected_surviving_region_ids,
                        *effective_delta.created_region_ids,
                    )
                ):
                    project.mark_region_needs_optimization(region_id)
                project.mark_scientific_modified()

                committed_result = replace(result, delta=effective_delta)
                if record_history is not None:
                    record_history(committed_result)
        except Exception as original_error:
            failure = original_error

            def rollback() -> None:
                with notification_scope():
                    self._rollback(
                        project,
                        failure,
                        runtime_snapshot=runtime_snapshot,
                        restore_runtime=restore_runtime,
                        snapshot=snapshot,
                    )

            self._attempt_restore(
                failure, "notification-suppressed structure transaction rollback", rollback
            )
            raise

        postcommit_changes = postcommit_changes.extend(
            RegionTopologyChanged(
                created_region_ids=effective_delta.created_region_ids,
                removed_region_ids=effective_delta.removed_region_ids,
                impacted_surviving_region_ids=effective_delta.affected_surviving_region_ids,
                changed_surviving_line_ids=effective_delta.changed_surviving_line_ids,
            )
        )
        return AtomicStructureMutationExecution(
            result=committed_result, postcommit_changes=postcommit_changes
        )

    @staticmethod
    def _require_changed_result[TValue](
        result: StructureMutationResult[TValue],
    ) -> StructureRegionDelta:
        """Require a changed result after a changed preflight."""
        if result.outcome is not StructureMutationOutcome.CHANGED or result.delta is None:
            msg = "A changed structure preflight must produce a changed mutation result."
            raise RuntimeError(msg)
        return result.delta

    def _snapshot_project(
        self, project: AtomicStructureProjectPort, region_ids: tuple[str, ...]
    ) -> _StructureProjectSnapshot:
        """Capture every executor-owned project fact before mutation."""
        semantic_states: list[RegionAnalysisState] = []
        for region_id in region_ids:
            state = project.region_analysis_state(region_id)
            if state is None:
                msg = f"Structure snapshot region has no analysis state: {region_id}"
                raise RuntimeError(msg)
            semantic_states.append(state)
        return _StructureProjectSnapshot(
            modified=project.modified,
            stored_analysis_states=project.stored_region_analysis_states_for_transaction(),
            semantic_analysis_states=tuple(semantic_states),
            region_line_memberships=tuple(
                (region_id, tuple(project.absorption_regions[region_id].line_ids))
                for region_id in region_ids
            ),
            line_multiplet_links=tuple(
                (line_id, tuple(line.multiplet_ids))
                for line_id, line in project.absorption_lines.items()
            ),
            optimization_flags=tuple(
                (line_id, line.needs_optimization)
                for line_id, line in project.absorption_lines.items()
            ),
            derived_state=project.model.snapshot_derived_state_for_transaction(),
            topology_validation=self._topology_validator.capture(project),
        )

    @staticmethod
    def _validate_after_topology(project: AtomicStructureProjectPort) -> None:
        """Require every current line to have one consistent region assignment."""
        issues = find_region_line_topology_issues(
            project.absorption_regions, project.absorption_lines
        )
        if issues:
            issue = issues[0]
            msg = (
                "Invalid region-line topology after structure mutation: "
                f"{issue.kind.value} ({issue.region_id}/{issue.line_id})"
            )
            raise ValueError(msg)

    @staticmethod
    def _validate_and_resolve_delta(
        project: AtomicStructureProjectPort,
        delta: StructureRegionDelta,
        *,
        before_region_ids: tuple[str, ...],
        before_region_line_memberships: tuple[tuple[str, tuple[str, ...]], ...],
        before_line_multiplet_links: tuple[tuple[str, tuple[str, ...]], ...],
        after_region_ids: tuple[str, ...],
    ) -> StructureRegionDelta:
        """Compare declared identities with actual before/after topology."""
        before = set(before_region_ids)
        after = set(after_region_ids)
        actual_created = after - before
        actual_removed = before - after
        if set(delta.created_region_ids) != actual_created:
            msg = "Declared created regions do not match the actual structure topology."
            raise ValueError(msg)
        if set(delta.removed_region_ids) != actual_removed:
            msg = "Declared removed regions do not match the actual structure topology."
            raise ValueError(msg)

        surviving = before & after
        before_memberships = dict(before_region_line_memberships)
        actual_membership_changed = {
            region_id
            for region_id in surviving
            if before_memberships[region_id]
            != tuple(project.absorption_regions[region_id].line_ids)
        }
        before_multiplet_links = dict(before_line_multiplet_links)
        actual_surviving_line_links_changed = {
            line_id
            for line_id, line in project.absorption_lines.items()
            if line_id in before_multiplet_links
            and before_multiplet_links[line_id] != tuple(line.multiplet_ids)
        }
        if set(delta.changed_surviving_line_ids) != actual_surviving_line_links_changed:
            msg = "Declared changed lines do not match actual surviving multiplet topology."
            raise ValueError(msg)
        if (
            delta.invalidation_scope is StructureInvalidationScope.ALL_ANALYSIS_CAPABLE_SURVIVORS
            and delta.affected_surviving_region_ids
        ):
            msg = "Global structure mutations must let the executor resolve affected regions."
            raise ValueError(msg)
        if (
            not actual_created
            and not actual_removed
            and not actual_membership_changed
            and not actual_surviving_line_links_changed
        ):
            msg = (
                "A changed structure mutation must change region identities or line membership, "
                "or multiplet links."
            )
            raise ValueError(msg)

        if delta.invalidation_scope is StructureInvalidationScope.LOCAL_SURVIVORS:
            affected = delta.affected_surviving_region_ids
            link_changed_regions = {
                project.absorption_lines[line_id].region_id
                for line_id in actual_surviving_line_links_changed
                if project.absorption_lines[line_id].region_id in surviving
            }
            actual_affected_regions = actual_membership_changed | link_changed_regions
            if set(affected) != actual_affected_regions:
                msg = (
                    "Locally affected structure regions must exactly match actual surviving "
                    "line-membership changes or multiplet-link changes."
                )
                raise ValueError(msg)
            return delta

        affected = tuple(
            region_id
            for region_id in after_region_ids
            if region_id in surviving and project.is_region_analysis_capable(region_id)
        )
        return replace(delta, affected_surviving_region_ids=affected)

    @staticmethod
    def _validate_surviving_analysis_states(
        project: AtomicStructureProjectPort,
        snapshot: _StructureProjectSnapshot,
        delta: StructureRegionDelta,
    ) -> None:
        """Reject mutations that bypass executor-owned analysis state."""
        removed = set(delta.removed_region_ids)
        created = set(delta.created_region_ids)
        before_explicit = tuple(
            state for state in snapshot.stored_analysis_states if state.region_id not in removed
        )
        current_explicit = tuple(
            state
            for state in project.stored_region_analysis_states_for_transaction()
            if state.region_id not in created and state.region_id not in removed
        )
        if current_explicit != before_explicit:
            msg = "Structure mutation changed surviving analysis state outside the executor."
            raise ValueError(msg)

    @staticmethod
    def _validate_surviving_line_flags(
        project: AtomicStructureProjectPort, snapshot: _StructureProjectSnapshot
    ) -> None:
        """Reject mutations that alter freshness on surviving pre-existing lines."""
        for line_id, expected in snapshot.optimization_flags:
            line = project.absorption_lines.get(line_id)
            if line is not None and line.needs_optimization is not expected:
                msg = f"Structure mutation changed line freshness before invalidation: {line_id}"
                raise ValueError(msg)

    @staticmethod
    def _invalidate_surviving_regions(
        project: AtomicStructureProjectPort,
        snapshot: _StructureProjectSnapshot,
        delta: StructureRegionDelta,
    ) -> None:
        """Advance each affected survivor once while retaining stale artifacts."""
        before_states = {state.region_id: state for state in snapshot.semantic_analysis_states}
        replacements: list[RegionAnalysisState] = []
        for region_id in delta.affected_surviving_region_ids:
            state = before_states.get(region_id)
            if state is None:
                msg = f"Affected surviving region was absent before mutation: {region_id}"
                raise RuntimeError(msg)
            replacements.append(
                RegionAnalysisState(
                    region_id=region_id,
                    current_revision=AnalysisRevision(state.current_revision.value + 1),
                    artifact=state.artifact,
                )
            )
        project.set_region_analysis_states(replacements)

    @staticmethod
    def _require_created_region_defaults(
        project: AtomicStructureProjectPort, region_ids: tuple[str, ...]
    ) -> None:
        """Require every created region to start without revision history or evidence."""
        for region_id in region_ids:
            state = project.region_analysis_state(region_id)
            if state is None:
                msg = f"Created structure region disappeared before commit: {region_id}"
                raise RuntimeError(msg)
            if state.current_revision != AnalysisRevision() or state.artifact is not None:
                msg = f"Created structure region did not reset to revision zero: {region_id}"
                raise RuntimeError(msg)

    def _rollback[TRuntime](
        self,
        project: AtomicStructureProjectPort,
        original_error: Exception,
        *,
        runtime_snapshot: TRuntime,
        restore_runtime: Callable[[TRuntime], None],
        snapshot: _StructureProjectSnapshot,
    ) -> None:
        """Restore runtime, analysis, flags, caches, and modified time in order."""
        self._attempt_restore(
            original_error, "structure runtime", lambda: restore_runtime(runtime_snapshot)
        )
        self._attempt_restore(
            original_error,
            "stored analysis states",
            lambda: project.replace_region_analysis_states_for_transaction(
                snapshot.stored_analysis_states
            ),
        )
        self._attempt_restore(
            original_error,
            "line optimization flags",
            lambda: self._restore_optimization_flags(project, snapshot.optimization_flags),
        )
        self._attempt_restore(
            original_error,
            "derived model cache",
            lambda: project.model.restore_derived_state_for_transaction(snapshot.derived_state),
        )
        self._attempt_restore(
            original_error,
            "project modified timestamp",
            lambda: setattr(project, "modified", snapshot.modified),
        )

    @staticmethod
    def _restore_optimization_flags(
        project: AtomicStructureProjectPort, flags: tuple[tuple[str, bool], ...]
    ) -> None:
        """Restore every pre-existing line freshness flag exactly."""
        for line_id, needs_optimization in flags:
            line = project.absorption_lines.get(line_id)
            if line is None:
                msg = f"Structure rollback line not found: {line_id}"
                raise RuntimeError(msg)
            line.needs_optimization = needs_optimization

    @staticmethod
    def _attempt_restore(
        original_error: Exception, label: str, restore: Callable[[], None]
    ) -> None:
        """Attempt one rollback stage without replacing the triggering error."""
        try:
            restore()
        except Exception as rollback_error:  # noqa: BLE001 - preserve original failure
            original_error.add_note(
                f"Failed to restore {label}: {type(rollback_error).__name__}: {rollback_error}"
            )


__all__ = ["AtomicStructureMutationExecutor", "AtomicStructureProjectPort"]
