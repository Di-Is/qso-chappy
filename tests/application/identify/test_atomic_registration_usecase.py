"""Atomicity contracts for Identify temporary line registration."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from chappy.application.history.snapshot_mapping import (
    absorption_line_snapshot,
    absorption_region_snapshot,
)
from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    AtomicRegisterSelectedLinesRequest,
    TemporaryLineSnapshot,
    ExistingRegionSnapshot,
)
from chappy.application.structure import StructureMutationOutcome
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.identify_state import TemporaryLine, TemporaryLineContext, IdentifySessionState
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.velocity_ranges import (
    DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
    LineAnalysisHalfWidth,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from _pytest.monkeypatch import MonkeyPatch

    from chappy.application.identify import RegistrationOutcome
    from chappy.core.absorption.models import AbsorptionLine


@dataclass(frozen=True, slots=True)
class _ScientificSnapshot:
    """Comparable project and session facts required to survive an abort."""

    regions: tuple[tuple[str, int, object], ...]
    lines: tuple[tuple[str, int, object], ...]
    analysis_states: tuple[RegionAnalysisState, ...]
    modified: object
    temporary_lines: tuple[tuple[str, int, TemporaryLineSnapshot], ...]


class _History:
    """Failure-injectable atomic history owner."""

    def __init__(self, *, fail_record: bool = False) -> None:
        self.entries = ["before"]
        self.depth = 0
        self.fail_record = fail_record

    @contextmanager
    def atomic_recording(self) -> Iterator[None]:
        """Restore exact entries if recording or transaction completion fails."""
        before = list(self.entries)
        self.depth += 1
        try:
            yield
        except Exception:
            self.entries = before
            raise
        finally:
            self.depth -= 1

    def record(self, outcome: RegistrationOutcome) -> None:
        """Record one outcome only while the atomic scope is active."""
        assert self.depth == 1
        self.entries.append(outcome.created_line_ids)
        if self.fail_record:
            raise RuntimeError("injected history failure")


def _add_temporary_line(
    session: IdentifySessionState,
    *,
    rest_wavelength: float = 1000.0,
    lambda_min: float = 1000.0,
    lambda_max: float = 1005.0,
) -> TemporaryLine:
    """Create one live temporary line in the requested session."""
    return session.add_temporary_line(
        "C IV",
        lambda_min,
        lambda_max,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="civ-1548",
            rest_wavelength=rest_wavelength,
            center_z=0.0,
            multiplet_id="civ-doublet",
            multiplet_label="C IV",
            transition_name="C IV 1548",
            oscillator_strength=0.19,
            gamma_value=2.64e8,
            tie_group_key="",
        ),
    )


def _temporary_line_snapshot(temporary_line: TemporaryLine) -> TemporaryLineSnapshot:
    """Build the application DTO passed by the real GUI adapter."""
    return TemporaryLineSnapshot(
        temporary_line_id=temporary_line.temporary_line_id,
        species=temporary_line.species,
        lambda_min=temporary_line.lambda_min,
        lambda_max=temporary_line.lambda_max,
        creation_method=temporary_line.creation_method,
        line_id=temporary_line.line_id,
        rest_wavelength=temporary_line.rest_wavelength,
        center_z=temporary_line.center_z,
        multiplet_id=temporary_line.multiplet_id,
        multiplet_label=temporary_line.multiplet_label,
        transition_name=temporary_line.transition_name,
        oscillator_strength=temporary_line.oscillator_strength,
        gamma_value=temporary_line.gamma_value,
        analysis_half_width=LineAnalysisHalfWidth(temporary_line.analysis_half_width_kms),
        tie_group_key=temporary_line.tie_group_key,
    )


def _existing_regions(project: SpectroscopyProject) -> tuple[ExistingRegionSnapshot, ...]:
    """Capture exact region line ranges in project storage order."""
    lines = project.list_absorption_lines()
    return tuple(
        ExistingRegionSnapshot(
            region_id=region.region_id,
            display_name=region.region_id,
            line_ranges=tuple(
                line.lambda_range
                for line in lines
                if line.region_id == region.region_id and line.lambda_range is not None
            ),
        )
        for region in project.list_absorption_regions()
    )


def _request(
    project: SpectroscopyProject,
    session: IdentifySessionState,
    temporary_line: TemporaryLine,
    *,
    history: _History | None = None,
    temporary_line_snapshot: TemporaryLineSnapshot | None = None,
    existing_regions: tuple[ExistingRegionSnapshot, ...] | None = None,
    region_line_memberships: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
) -> AtomicRegisterSelectedLinesRequest:
    """Build one production-shaped atomic request."""
    return AtomicRegisterSelectedLinesRequest(
        project=project,
        session=session,
        temporary_lines=(temporary_line_snapshot or _temporary_line_snapshot(temporary_line),),
        existing_regions=(
            _existing_regions(project) if existing_regions is None else existing_regions
        ),
        region_line_memberships=(
            tuple(
                (region.region_id, tuple(region.line_ids))
                for region in project.list_absorption_regions()
            )
            if region_line_memberships is None
            else region_line_memberships
        ),
        multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
        unknown_label="Unknown",
        record_history=history.record if history is not None else None,
        history_scope=history.atomic_recording if history is not None else None,
    )


def _existing_analyzed_project() -> tuple[SpectroscopyProject, str, AbsorptionLine]:
    """Create one existing analyzed region overlapping the test temporary line."""
    project = SpectroscopyProject()
    line = project.add_absorption_line(
        species="C IV",
        rest_wavelength=1000.0,
        center_z=0.0,
        window_kms=200.0,
        multiplet_label="C IV",
        transition_name="existing",
        oscillator_strength=0.1,
        gamma_value=1e8,
        lambda_range=(999.0, 1006.0),
    )
    region = project.create_region_with_lines((line.line_id,))
    line.needs_optimization = False
    revision = AnalysisRevision(4)
    project.set_region_analysis_state(
        RegionAnalysisState(
            region_id=region.region_id,
            current_revision=revision,
            artifact=AnalysisArtifact(
                region_id=region.region_id,
                source_revision=revision,
                fit_summary=FitSummary(chi_squared=2.5),
            ),
        )
    )
    return project, region.region_id, line


def _scientific_snapshot(
    project: SpectroscopyProject, session: IdentifySessionState
) -> _ScientificSnapshot:
    """Capture serialization facts plus exact topology/session object identity."""
    return _ScientificSnapshot(
        regions=tuple(
            (key, id(region), absorption_region_snapshot(region))
            for key, region in project.absorption_regions.items()
        ),
        lines=tuple(
            (key, id(line), absorption_line_snapshot(line))
            for key, line in project.absorption_lines.items()
        ),
        analysis_states=project.stored_region_analysis_states_for_transaction(),
        modified=project.modified,
        temporary_lines=tuple(
            (
                temporary_line.temporary_line_id,
                id(temporary_line),
                _temporary_line_snapshot(temporary_line),
            )
            for temporary_line in session.temporary_lines
        ),
    )


def test_registration_created_and_affected_revision_matrix() -> None:
    """Existing targets advance once; new regions start at revision zero without artifacts."""
    project, existing_region_id, existing_line = _existing_analyzed_project()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    history = _History()

    result = AtomicIdentifyRegistrationUseCase().register(
        _request(project, session, temporary_line, history=history)
    )

    assert result.outcome is not None
    assert result.mutation_outcome is StructureMutationOutcome.CHANGED
    assert result.changed is True
    assert result.region_delta is not None
    assert result.region_delta.affected_surviving_region_ids == (existing_region_id,)
    assert result.outcome.appended_region_ids == (existing_region_id,)
    existing_state = project.region_analysis_state(existing_region_id)
    assert existing_state is not None
    assert existing_state.current_revision == AnalysisRevision(5)
    assert existing_state.artifact is not None
    assert existing_state.artifact.source_revision == AnalysisRevision(4)
    assert existing_line.needs_optimization is True
    assert tuple(session.temporary_lines) == ()
    assert history.entries[-1] == result.outcome.created_line_ids

    new_project = SpectroscopyProject()
    new_session = new_project.identify_state
    new_temporary_line = _add_temporary_line(new_session)
    new_result = AtomicIdentifyRegistrationUseCase().register(
        _request(new_project, new_session, new_temporary_line)
    )

    assert new_result.outcome is not None
    assert new_result.mutation_outcome is StructureMutationOutcome.CHANGED
    assert new_result.region_delta is not None
    assert new_result.region_delta.affected_surviving_region_ids == ()
    assert set(new_result.region_delta.created_region_ids) == set(
        new_result.outcome.created_region_ids
    )
    assert new_result.outcome.appended_region_ids == ()
    assert len(new_result.outcome.affected_region_ids) == 1
    for region_id in new_result.outcome.created_region_ids:
        state = new_project.region_analysis_state(region_id)
        assert state is not None
        assert state.current_revision == AnalysisRevision()
        assert state.artifact is None


def test_no_change_does_not_mutate_project_session_or_history() -> None:
    """An all-invalid exact request is a true NoChange command."""
    project = SpectroscopyProject()
    session = project.identify_state
    temporary_line = _add_temporary_line(session, rest_wavelength=0.0)
    history = _History()
    before = _scientific_snapshot(project, session)

    result = AtomicIdentifyRegistrationUseCase().register(
        _request(project, session, temporary_line, history=history)
    )

    assert result.outcome is None
    assert result.mutation_outcome is StructureMutationOutcome.NO_CHANGE
    assert result.changed is False
    assert result.region_delta is None
    assert _scientific_snapshot(project, session) == before
    assert history.entries == ["before"]


def test_exact_temporary_line_and_region_preflight_rejects_stale_requests() -> None:
    """Stale source or target previews fail before any mutable owner is touched."""
    project, _region_id, _line = _existing_analyzed_project()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    before = _scientific_snapshot(project, session)

    stale_temporary_line = _temporary_line_snapshot(temporary_line)
    temporary_line.lambda_max += 1.0
    after_external_temporary_line_change = _scientific_snapshot(project, session)
    with pytest.raises(ValueError, match="temporary-line source is stale"):
        AtomicIdentifyRegistrationUseCase().register(
            _request(
                project, session, temporary_line, temporary_line_snapshot=stale_temporary_line
            )
        )
    assert after_external_temporary_line_change != before
    assert _scientific_snapshot(project, session) == after_external_temporary_line_change
    temporary_line.lambda_max -= 1.0
    before = _scientific_snapshot(project, session)

    stale_regions = list(_existing_regions(project))
    target_index = next(index for index, value in enumerate(stale_regions) if value.line_ranges)
    target = stale_regions[target_index]
    stale_regions[target_index] = ExistingRegionSnapshot(
        region_id=target.region_id, display_name=target.display_name, line_ranges=((1.0, 2.0),)
    )
    with pytest.raises(ValueError, match="region target is stale"):
        AtomicIdentifyRegistrationUseCase().register(
            _request(project, session, temporary_line, existing_regions=tuple(stale_regions))
        )
    assert _scientific_snapshot(project, session) == before

    stale_memberships = tuple(
        (region_id, (*line_ids, "missing-line"))
        for region_id, line_ids in tuple(
            (region.region_id, tuple(region.line_ids))
            for region in project.list_absorption_regions()
        )
    )
    with pytest.raises(ValueError, match="membership targets are stale"):
        AtomicIdentifyRegistrationUseCase().register(
            _request(project, session, temporary_line, region_line_memberships=stale_memberships)
        )
    assert _scientific_snapshot(project, session) == before


@pytest.mark.parametrize(
    "stage", ("materialize", "assignment", "session", "revision", "needs", "modified", "history")
)
def test_every_registration_stage_rolls_back_project_artifact_session_and_history(
    stage: str, monkeypatch: MonkeyPatch
) -> None:
    """Every mutable stage restores all owners when a later operation fails."""
    project, _region_id, _line = _existing_analyzed_project()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    history = _History(fail_record=stage == "history")
    before = _scientific_snapshot(project, session)

    def fail_after(method: Callable[..., object], label: str) -> Callable[..., object]:
        def injected(*args: object, **kwargs: object) -> object:
            result = method(*args, **kwargs)
            raise RuntimeError(f"injected {label} failure")

        return injected

    if stage == "materialize":
        monkeypatch.setattr(
            project, "add_absorption_line", fail_after(project.add_absorption_line, stage)
        )
    elif stage == "assignment":
        monkeypatch.setattr(
            project, "assign_line_to_region", fail_after(project.assign_line_to_region, stage)
        )
    elif stage == "session":
        monkeypatch.setattr(
            session, "remove_temporary_lines", fail_after(session.remove_temporary_lines, stage)
        )
    elif stage == "revision":
        monkeypatch.setattr(
            project,
            "set_region_analysis_states",
            fail_after(project.set_region_analysis_states, stage),
        )
    elif stage == "needs":
        monkeypatch.setattr(
            project,
            "mark_region_needs_optimization",
            fail_after(project.mark_region_needs_optimization, stage),
        )
    elif stage == "modified":
        monkeypatch.setattr(
            project,
            "mark_scientific_modified",
            fail_after(project.mark_scientific_modified, stage),
        )

    with pytest.raises(RuntimeError, match=f"injected {stage} failure"):
        AtomicIdentifyRegistrationUseCase().register(
            _request(project, session, temporary_line, history=history)
        )

    assert _scientific_snapshot(project, session) == before
    assert history.entries == ["before"]


def test_postcommit_observer_failure_keeps_registration_committed(
    monkeypatch: MonkeyPatch,
) -> None:
    """A model observer failure is isolated after scientific commit."""
    project, existing_region_id, _line = _existing_analyzed_project()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)

    def fail_publish(_changes: object) -> None:
        raise RuntimeError("injected observer failure")

    monkeypatch.setattr(project.model, "publish_storage_changes", fail_publish)

    result = AtomicIdentifyRegistrationUseCase().register(
        _request(project, session, temporary_line)
    )

    assert result.outcome is not None
    assert result.outcome.appended_region_ids == (existing_region_id,)
    assert tuple(session.temporary_lines) == ()
    state = project.region_analysis_state(existing_region_id)
    assert state is not None
    assert state.current_revision == AnalysisRevision(5)
