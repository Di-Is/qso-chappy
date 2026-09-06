"""Atomic forward, Undo, and Redo tests for spectral resolution."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from chappy.application.analysis_artifacts import AnalysisArtifactStoreUseCase
from chappy.application.history import (
    HistoryApplyError,
    HistoryRecorder,
    HistoryRefreshTarget,
    ResolutionHistoryCommand,
    ResolutionStateSnapshot,
    ScientificHistoryApplyExecutor,
)
from chappy.application.spectrum import ResolutionUpdateUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisRevision, FitSummary
from chappy.core.history import CommandHistory, HistoryEvent
from chappy.core.spectroscopy_project import SpectroscopyProject

from history_apply_fakes import FakeHistoryRefreshPort, build_usecase

if TYPE_CHECKING:
    from collections.abc import Iterable

    from chappy.application.analysis_artifacts import AnalysisArtifactStorePort
    from chappy.application.history.apply.usecase import HistoryApplyUseCase


class _ResolutionNotifier:
    """Resolution notifier with optional post-call failure injection."""

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize call tracking."""
        self.call_count = 0
        self.fail = fail

    def notify_resolution_changed(self) -> None:
        """Record one notification and optionally fail."""
        self.call_count += 1
        if self.fail:
            raise RuntimeError("injected notifier failure")


class _FailAfterInvalidation(AnalysisArtifactStoreUseCase):
    """Artifact transition that fails after mutating revision state."""

    def invalidate_regions(
        self, store: AnalysisArtifactStorePort, region_ids: Iterable[str]
    ) -> tuple[str, ...]:
        """Apply normal invalidation and then inject a transaction failure."""
        super().invalidate_regions(store, region_ids)
        raise RuntimeError("injected history invalidation failure")


def _project() -> SpectroscopyProject:
    """Build two analysis-capable regions with fresh artifacts."""
    project = SpectroscopyProject()
    for region_id in ("region-1", "region-2"):
        line_id = f"line-{region_id}"
        project.absorption_lines[line_id] = AbsorptionLine(
            line_id=line_id,
            species="H I",
            rest_wavelength=1215.67,
            center_z=2.0,
            window_kms=100.0,
            multiplet_label="Ly alpha",
            transition_name="Ly alpha",
            oscillator_strength=0.4,
            gamma_value=1e8,
            region_id=region_id,
            needs_optimization=False,
        )
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=[line_id]
        )
        AnalysisArtifactStoreUseCase().record_artifact(
            project, region_id, FitSummary(chi_squared=1.0)
        )
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project


def _command() -> ResolutionHistoryCommand:
    """Build the canonical default-to-enabled resolution transition."""
    return ResolutionHistoryCommand(
        before=ResolutionStateSnapshot(value=36_000.0, enabled=False),
        after=ResolutionStateSnapshot(value=48_000.0, enabled=True),
    )


def _usecase(
    project: SpectroscopyProject,
    notifier: _ResolutionNotifier | None = None,
    refresh_port: FakeHistoryRefreshPort | None = None,
) -> HistoryApplyUseCase:
    """Build and connect one resolution history use case."""
    return build_usecase(
        project_provider=lambda: project,
        refresh_port=refresh_port,
        resolution_notifier_provider=lambda: notifier,
    )


def _assert_revisions(project: SpectroscopyProject, expected: int) -> None:
    """Assert every capable region has one expected revision."""
    assert {
        state.region_id: state.current_revision for state in project.region_analysis_states()
    } == {"region-1": AnalysisRevision(expected), "region-2": AnalysisRevision(expected)}


def test_forward_undo_redo_share_one_atomic_resolution_contract() -> None:
    """Every direction must update all science owners and notify exactly once."""
    project = _project()
    history = CommandHistory()
    notifier = _ResolutionNotifier()
    refresh_port = FakeHistoryRefreshPort()
    usecase = _usecase(project, notifier, refresh_port)
    history.set_applier(usecase)
    recorder = HistoryRecorder(history, lambda: project)

    forward = ResolutionUpdateUseCase().apply_resolution(
        project, value=48_000.0, enabled=True, notifier=notifier, history_recorder=recorder
    )

    assert forward.impact.affected_region_ids == ("region-1", "region-2")
    assert history.can_undo and not history.can_redo
    assert notifier.call_count == 1
    _assert_revisions(project, 1)
    assert all(line.needs_optimization for line in project.absorption_lines.values())

    notifier.call_count = 0
    assert history.undo().success
    assert project.resolution_state.value == 36_000.0
    assert project.resolution_state.enabled is False
    assert notifier.call_count == 1
    _assert_revisions(project, 2)
    assert history.can_redo and not history.can_undo

    notifier.call_count = 0
    assert history.redo().success
    assert project.resolution_state.value == 48_000.0
    assert project.resolution_state.enabled is True
    assert notifier.call_count == 1
    _assert_revisions(project, 3)
    assert history.can_undo and not history.can_redo
    for state in project.region_analysis_states():
        assert state.artifact is not None
        assert state.artifact.source_revision == AnalysisRevision(0)
    assert refresh_port.region_ids_for(HistoryRefreshTarget.MODEL) == [None, None]


def test_resolution_history_no_change_advances_stack_without_scientific_churn() -> None:
    """An already-applied target must not invalidate, notify, or refresh."""
    project = _project()
    history = CommandHistory()
    notifier = _ResolutionNotifier()
    refresh_port = FakeHistoryRefreshPort()
    usecase = _usecase(project, notifier, refresh_port)
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=_command()))
    before_states = project.stored_region_analysis_states_for_transaction()
    before_modified = project.modified

    assert history.undo().success

    assert project.stored_region_analysis_states_for_transaction() == before_states
    assert project.modified == before_modified
    assert notifier.call_count == 0
    assert refresh_port.region_ids_for(HistoryRefreshTarget.MODEL) == []
    assert history.can_redo and not history.can_undo


def test_resolution_history_stale_source_fails_before_mutation_and_keeps_stack() -> None:
    """A temporal mismatch must preserve project and history exactly."""
    project = _project()
    project.set_resolution(42_000.0, True)
    history = CommandHistory()
    notifier = _ResolutionNotifier()
    usecase = _usecase(project, notifier)
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=_command()))
    before_resolution = ResolutionStateSnapshot.from_state(project.resolution_state)
    before_states = project.stored_region_analysis_states_for_transaction()
    before_history = history.get_state()

    with pytest.raises(HistoryApplyError, match="source state"):
        history.undo()

    assert ResolutionStateSnapshot.from_state(project.resolution_state) == before_resolution
    assert project.stored_region_analysis_states_for_transaction() == before_states
    assert history.get_state() == before_history
    assert notifier.call_count == 0


@pytest.mark.parametrize(
    "failure_stage", ("mutation", "rebuild", "invalidation", "flags", "modified")
)
def test_resolution_history_failure_matrix_rolls_back_every_owner(failure_stage: str) -> None:
    """Derived or artifact failures must restore science, freshness, and history."""
    project = _project()
    project.set_resolution(48_000.0, True)
    history = CommandHistory()
    notifier = _ResolutionNotifier()
    refresh_port = FakeHistoryRefreshPort()
    usecase = _usecase(project, notifier, refresh_port)
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=_command()))
    before_resolution = ResolutionStateSnapshot.from_state(project.resolution_state)
    before_states = project.stored_region_analysis_states_for_transaction()
    before_derived = project.model.snapshot_derived_state_for_transaction()
    before_flags = {
        line_id: line.needs_optimization for line_id, line in project.absorption_lines.items()
    }
    before_modified = project.modified
    before_history = history.get_state()

    if failure_stage == "mutation":
        original_set_resolution = project.set_resolution
        mutation_calls = 0

        def fail_after_resolution_mutation(value: float, enabled: bool) -> None:
            nonlocal mutation_calls
            mutation_calls += 1
            original_set_resolution(value, enabled)
            if mutation_calls == 1:
                raise RuntimeError("injected history mutation failure")

        failure_context = patch.object(
            project, "set_resolution", side_effect=fail_after_resolution_mutation
        )
        failure_match = "injected history mutation failure"
    elif failure_stage == "rebuild":
        failure_context = patch.object(
            project.model,
            "rebuild_model_storage",
            side_effect=RuntimeError("injected history rebuild failure"),
        )
        failure_match = "injected history rebuild failure"
    elif failure_stage == "invalidation":
        usecase._resolution_apply._scientific_executor = ScientificHistoryApplyExecutor(
            artifacts=_FailAfterInvalidation()
        )
        failure_context = nullcontext()
        failure_match = "injected history invalidation failure"
    elif failure_stage == "flags":
        original_mark_region = project.mark_region_needs_optimization

        def fail_after_flag_mutation(region_id: str) -> int:
            _ = original_mark_region(region_id)
            raise RuntimeError("injected history flag failure")

        failure_context = patch.object(
            project, "mark_region_needs_optimization", side_effect=fail_after_flag_mutation
        )
        failure_match = "injected history flag failure"
    else:
        failure_context = patch.object(
            project,
            "mark_scientific_modified",
            side_effect=RuntimeError("injected history modified failure"),
        )
        failure_match = "injected history modified failure"

    with failure_context, pytest.raises(RuntimeError, match=failure_match):
        history.undo()

    assert ResolutionStateSnapshot.from_state(project.resolution_state) == before_resolution
    assert project.stored_region_analysis_states_for_transaction() == before_states
    assert project.model.snapshot_derived_state_for_transaction() == before_derived
    assert {
        line_id: line.needs_optimization for line_id, line in project.absorption_lines.items()
    } == before_flags
    assert project.modified == before_modified
    assert history.get_state() == before_history
    assert notifier.call_count == 0
    assert refresh_port.region_ids_for(HistoryRefreshTarget.MODEL) == []


def test_resolution_history_notifier_failure_keeps_committed_science_and_stack() -> None:
    """A post-commit notifier exception must not masquerade as an Undo failure."""
    project = _project()
    project.set_resolution(48_000.0, True)
    history = CommandHistory()
    notifier = _ResolutionNotifier(fail=True)
    refresh_port = FakeHistoryRefreshPort()
    usecase = _usecase(project, notifier, refresh_port)
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=_command()))

    assert history.undo().success

    assert project.resolution_state.value == 36_000.0
    assert project.resolution_state.enabled is False
    _assert_revisions(project, 1)
    assert notifier.call_count == 1
    assert history.can_redo and not history.can_undo
    assert refresh_port.region_ids_for(HistoryRefreshTarget.MODEL) == [None]


def test_resolution_history_gui_observer_failure_keeps_commit() -> None:
    """A post-commit refresh exception must preserve science and history."""
    project = _project()
    project.set_resolution(48_000.0, True)
    history = CommandHistory()
    notifier = _ResolutionNotifier()
    refresh_port = FakeHistoryRefreshPort(fail_targets=frozenset({HistoryRefreshTarget.MODEL}))
    usecase = _usecase(project, notifier, refresh_port)
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=_command()))

    assert history.undo().success

    assert project.resolution_state.value == 36_000.0
    _assert_revisions(project, 1)
    assert notifier.call_count == 1
    assert history.can_redo and not history.can_undo
