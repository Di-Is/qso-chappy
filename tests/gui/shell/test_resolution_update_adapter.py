"""Tests for resolution update adapter."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from chappy.application.analysis_artifacts import (
    AnalysisArtifactStoreUseCase,
    AnalysisMutationOutcome,
    GlobalAnalysisMutationUseCase,
)
from chappy.application.spectrum import ResolutionUpdateUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisRevision, FitSummary
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.shell.resolution_update_adapter import ResolutionUpdateAdapter

if TYPE_CHECKING:
    from collections.abc import Iterator

    from chappy.application.history import ResolutionStateSnapshot


class _ResolutionHistoryRecorder:
    """Rollback-capable recorder double for forward resolution tests."""

    def __init__(self, *, fail_recording: bool = False) -> None:
        """Initialize recorded transitions and optional failure injection."""
        self.events: list[tuple[ResolutionStateSnapshot, ResolutionStateSnapshot]] = []
        self.fail_recording = fail_recording

    @contextmanager
    def atomic_recording(self) -> Iterator[None]:
        """Restore the exact event list after a transaction failure."""
        before = list(self.events)
        try:
            yield
        except Exception:
            self.events = before
            raise

    def record_resolution_change(
        self, before: ResolutionStateSnapshot, after: ResolutionStateSnapshot
    ) -> None:
        """Record one transition or inject a history failure."""
        self.events.append((before, after))
        if self.fail_recording:
            raise RuntimeError("injected history failure")


class _ResolutionNotifier:
    """Test notifier that records resolution change calls."""

    def __init__(self) -> None:
        """Initialize call tracking."""
        self.call_count = 0

    def notify_resolution_changed(self) -> None:
        """Record a notification call."""
        self.call_count += 1


def _add_region(project: SpectroscopyProject, region_id: str) -> None:
    """Add one analysis-capable region."""
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


def test_apply_resolution_updates_project_and_notifies() -> None:
    """Resolution adapter should mutate the project and notify consumers."""
    project = SpectroscopyProject()
    _add_region(project, "region-1")
    _add_region(project, "region-2")
    AnalysisArtifactStoreUseCase().record_artifact(
        project, "region-1", FitSummary(chi_squared=1.0)
    )
    notifier = _ResolutionNotifier()
    history = _ResolutionHistoryRecorder()
    adapter = ResolutionUpdateAdapter(ResolutionUpdateUseCase())

    result = adapter.apply_resolution(
        project, value=48000.0, enabled=True, notifier=notifier, history_recorder=history
    )

    assert result.value == 48000.0
    assert result.enabled is True
    assert project.resolution_state.value == 48000.0
    assert project.resolution_state.enabled is True
    assert result.impact.affected_region_ids == ("region-1", "region-2")
    assert all(
        state.current_revision == AnalysisRevision(1) for state in project.region_analysis_states()
    )
    assert all(line.needs_optimization for line in project.absorption_lines.values())
    region_1_state = project.region_analysis_state("region-1")
    assert region_1_state is not None
    assert region_1_state.artifact is not None
    assert region_1_state.artifact.source_revision == AnalysisRevision(0)
    assert notifier.call_count == 1
    assert len(history.events) == 1
    before, after = history.events[0]
    assert before.value == 36000.0
    assert before.enabled is False
    assert after.value == 48000.0
    assert after.enabled is True


def test_identical_resolution_is_no_change() -> None:
    """Submitting identical resolution state must not invalidate analysis."""
    project = SpectroscopyProject()
    _add_region(project, "region-1")
    notifier = _ResolutionNotifier()
    state = project.resolution_state

    result = ResolutionUpdateUseCase().apply_resolution(
        project,
        value=state.value,
        enabled=state.enabled,
        notifier=notifier,
        history_recorder=(history := _ResolutionHistoryRecorder()),
    )

    region_state = project.region_analysis_state("region-1")
    assert region_state is not None
    assert result.impact.outcome is AnalysisMutationOutcome.NO_CHANGE
    assert region_state.current_revision == AnalysisRevision(0)
    assert project.absorption_lines["line-region-1"].needs_optimization is False
    assert notifier.call_count == 0
    assert history.events == []


class _FailAfterInvalidation(AnalysisArtifactStoreUseCase):
    """Artifact service that fails after applying its normal transition."""

    def invalidate_all_analysis_capable(self, store: SpectroscopyProject) -> tuple[str, ...]:
        """Apply invalidation and inject a failure before commit."""
        super().invalidate_all_analysis_capable(store)
        raise RuntimeError("injected invalidation failure")


def test_resolution_rolls_back_when_invalidation_fails() -> None:
    """Resolution and prior artifact freshness must roll back together."""
    project = SpectroscopyProject()
    _add_region(project, "region-1")
    AnalysisArtifactStoreUseCase().record_artifact(
        project, "region-1", FitSummary(chi_squared=1.0)
    )
    resolution_before = project.resolution_state
    state_before = project.region_analysis_state("region-1")
    flags_before = {
        line_id: line.needs_optimization for line_id, line in project.absorption_lines.items()
    }
    modified_before = project.modified
    usecase = ResolutionUpdateUseCase(
        mutations=GlobalAnalysisMutationUseCase(artifacts=_FailAfterInvalidation())
    )

    with pytest.raises(RuntimeError, match="injected invalidation failure"):
        usecase.apply_resolution(
            project,
            value=48000.0,
            enabled=True,
            notifier=None,
            history_recorder=(history := _ResolutionHistoryRecorder()),
        )

    assert project.resolution_state == resolution_before
    assert project.region_analysis_state("region-1") == state_before
    assert {
        line_id: line.needs_optimization for line_id, line in project.absorption_lines.items()
    } == flags_before
    assert project.modified == modified_before
    assert history.events == []


def test_resolution_rolls_back_when_history_recording_fails() -> None:
    """Scientific and history owners must roll back as one forward command."""
    project = SpectroscopyProject()
    _add_region(project, "region-1")
    AnalysisArtifactStoreUseCase().record_artifact(
        project, "region-1", FitSummary(chi_squared=1.0)
    )
    resolution_before = project.resolution_state
    state_before = project.region_analysis_state("region-1")
    modified_before = project.modified
    history = _ResolutionHistoryRecorder(fail_recording=True)

    with pytest.raises(RuntimeError, match="injected history failure"):
        ResolutionUpdateUseCase().apply_resolution(
            project, value=48000.0, enabled=True, notifier=None, history_recorder=history
        )

    assert project.resolution_state == resolution_before
    assert project.region_analysis_state("region-1") == state_before
    assert project.absorption_lines["line-region-1"].needs_optimization is False
    assert project.modified == modified_before
    assert history.events == []


class _FailingNotifier:
    """Observer that fails after a committed resolution mutation."""

    def notify_resolution_changed(self) -> None:
        """Inject an observer failure."""
        raise RuntimeError("injected observer failure")


def test_notifier_failure_does_not_roll_back_committed_resolution() -> None:
    """Post-commit observer errors must not revert scientific state."""
    project = SpectroscopyProject()
    _add_region(project, "region-1")

    ResolutionUpdateUseCase().apply_resolution(
        project,
        value=48000.0,
        enabled=True,
        notifier=_FailingNotifier(),
        history_recorder=_ResolutionHistoryRecorder(),
    )

    state = project.region_analysis_state("region-1")
    assert state is not None
    assert project.resolution_state.value == 48000.0
    assert project.resolution_state.enabled is True
    assert state.current_revision == AnalysisRevision(1)
    assert project.absorption_lines["line-region-1"].needs_optimization is True
