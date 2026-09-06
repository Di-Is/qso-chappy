"""Spectral resolution update use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.application.analysis_artifacts import (
    GlobalAnalysisMutationUseCase,
    run_postcommit_actions_isolated,
)
from chappy.application.history.resolution_commands import ResolutionStateSnapshot
from chappy.application.spectrum.models import ResolutionUpdateResult

if TYPE_CHECKING:
    from chappy.application.history.resolution_commands import ResolutionHistoryRecorder
    from chappy.application.spectrum.ports import ResolutionChangeNotifier, ResolutionProjectPort


class ResolutionUpdateUseCase:
    """Apply spectral resolution changes to a project."""

    def __init__(self, *, mutations: GlobalAnalysisMutationUseCase | None = None) -> None:
        """Initialize with the global scientific mutation transaction."""
        self._mutations = mutations or GlobalAnalysisMutationUseCase()

    def apply_resolution(
        self,
        project: ResolutionProjectPort,
        *,
        value: float,
        enabled: bool,
        notifier: ResolutionChangeNotifier | None,
        history_recorder: ResolutionHistoryRecorder,
    ) -> ResolutionUpdateResult:
        """Apply a spectral resolution value and notify interested consumers."""
        before = ResolutionStateSnapshot.from_state(project.resolution_state)
        after = ResolutionStateSnapshot(value=float(value), enabled=enabled)
        impact = self._mutations.execute(
            project,
            mutate=lambda: self._apply_if_changed(project, after=after, changed=before != after),
            rollback=lambda: project.set_resolution(before.value, before.enabled),
            record_history=lambda: history_recorder.record_resolution_change(before, after),
            history_scope=history_recorder.atomic_recording,
        )
        if impact.changed and notifier is not None:
            run_postcommit_actions_isolated(notifier.notify_resolution_changed)
        return ResolutionUpdateResult(value=after.value, enabled=after.enabled, impact=impact)

    @staticmethod
    def _apply_if_changed(
        project: ResolutionProjectPort, *, after: ResolutionStateSnapshot, changed: bool
    ) -> bool:
        """Apply a preflighted resolution change and report its outcome."""
        if not changed:
            return False
        project.set_resolution(after.value, after.enabled)
        return True


__all__ = ["ResolutionUpdateUseCase"]
