"""Side-effect-free impact preview contracts for Identify registration."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    AtomicRegisterSelectedLinesRequest,
    TemporaryLineSnapshot,
    ExistingRegionSnapshot,
    IdentifyRegistrationImpactPreviewUseCase,
    IdentifyRegistrationImpactRequest,
)
from chappy.application.structure import StructureMutationOutcome
from chappy.core.analysis import AnalysisRevision, RegionAnalysisState
from chappy.core.identify_state import TemporaryLine, TemporaryLineContext, IdentifySessionState
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.velocity_ranges import (
    DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
    LineAnalysisHalfWidth,
)


@dataclass(frozen=True, slots=True)
class _RuntimeState:
    """Comparable project/session state that preview must preserve exactly."""

    regions: tuple[tuple[str, int, tuple[str, ...]], ...]
    lines: tuple[tuple[str, int, str | None, tuple[str, ...]], ...]
    analysis_states: tuple[RegionAnalysisState, ...]
    model_components: tuple[int, ...]
    masks: tuple[int, ...]
    modified: object
    temporary_lines: tuple[tuple[str, int, TemporaryLineSnapshot], ...]


def _add_temporary_line(
    session: IdentifySessionState,
    *,
    species: str = "C IV",
    lambda_min: float = 1000.0,
    lambda_max: float = 1005.0,
    rest_wavelength: float = 1000.0,
    tie_group_key: str = "",
) -> TemporaryLine:
    """Create one live temporary line with reproducible scientific context."""
    return session.add_temporary_line(
        species,
        lambda_min,
        lambda_max,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id=f"atomic-{species}-{rest_wavelength}",
            rest_wavelength=rest_wavelength,
            center_z=0.0,
            multiplet_id=tie_group_key,
            multiplet_label=species,
            transition_name=f"{species} transition",
            oscillator_strength=0.19,
            gamma_value=2.64e8,
            tie_group_key=tie_group_key,
        ),
    )


def _temporary_line_snapshot(temporary_line: TemporaryLine) -> TemporaryLineSnapshot:
    """Build the immutable temporary line source used by application requests."""
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
    """Capture exact region ranges in project storage order."""
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


def _impact_request(
    project: SpectroscopyProject,
    session: IdentifySessionState,
    temporary_lines: tuple[TemporaryLineSnapshot, ...],
) -> IdentifyRegistrationImpactRequest:
    """Build one exact, production-shaped read-only preview request."""
    return IdentifyRegistrationImpactRequest(
        project=project,
        session=session,
        temporary_lines=temporary_lines,
        existing_regions=_existing_regions(project),
        region_line_memberships=tuple(
            (region.region_id, tuple(region.line_ids))
            for region in project.list_absorption_regions()
        ),
        multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
        unknown_label="Unknown",
    )


def _atomic_request(
    request: IdentifyRegistrationImpactRequest,
) -> AtomicRegisterSelectedLinesRequest:
    """Promote a preview request to the mutation command boundary."""
    assert isinstance(request.project, SpectroscopyProject)
    assert isinstance(request.session, IdentifySessionState)
    return AtomicRegisterSelectedLinesRequest(
        project=request.project,
        session=request.session,
        temporary_lines=request.temporary_lines,
        existing_regions=request.existing_regions,
        region_line_memberships=request.region_line_memberships,
        multiplet_grouping_tolerance=request.multiplet_grouping_tolerance,
        unknown_label=request.unknown_label,
    )


def _runtime_state(project: SpectroscopyProject, session: IdentifySessionState) -> _RuntimeState:
    """Capture state owners that a preview is forbidden to mutate."""
    return _RuntimeState(
        regions=tuple(
            (region_id, id(region), tuple(region.line_ids))
            for region_id, region in project.absorption_regions.items()
        ),
        lines=tuple(
            (line_id, id(line), line.region_id, tuple(line.multiplet_ids))
            for line_id, line in project.absorption_lines.items()
        ),
        analysis_states=project.stored_region_analysis_states_for_transaction(),
        model_components=tuple(id(component) for component in project.model.components),
        masks=tuple(id(mask) for mask in project.model.mask_definitions),
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


def _project_with_existing_region() -> tuple[SpectroscopyProject, str]:
    """Create a project with one existing region overlapping test temporary lines."""
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
    project.set_region_analysis_state(
        RegionAnalysisState(region_id=region.region_id, current_revision=AnalysisRevision(4))
    )
    return project, region.region_id


def test_existing_region_preview_is_typed_and_side_effect_free() -> None:
    """Preview reports existing-region impact without touching any runtime owner."""
    project, region_id = _project_with_existing_region()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    request = _impact_request(project, session, (_temporary_line_snapshot(temporary_line),))
    before = _runtime_state(project, session)

    plan = IdentifyRegistrationImpactPreviewUseCase().preview(request)

    assert plan.impact.mutation_outcome is StructureMutationOutcome.CHANGED
    assert plan.impact.normalized_temporary_line_ids == (temporary_line.temporary_line_id,)
    assert plan.impact.registerable_temporary_line_ids == (temporary_line.temporary_line_id,)
    assert plan.impact.rejected_temporary_line_ids == ()
    assert tuple(item.temporary_line_id for item in plan.registration_requests) == (
        temporary_line.temporary_line_id,
    )
    assert plan.impact.affected_existing_region_ids == (region_id,)
    assert plan.impact.created_region_count == 0
    assert plan.impact.created_line_count == 1
    assert plan.impact.affected_model_component_ids == ()
    assert plan.impact.affected_mask_ids == ()
    assert _runtime_state(project, session) == before


def test_new_region_preview_and_commit_have_the_same_delta() -> None:
    """A new-region preview count matches the committed topology exactly."""
    project = SpectroscopyProject()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    request = _impact_request(project, session, (_temporary_line_snapshot(temporary_line),))
    plan = IdentifyRegistrationImpactPreviewUseCase().preview(request)
    result = AtomicIdentifyRegistrationUseCase().register(_atomic_request(request))

    assert plan.impact.affected_existing_region_ids == ()
    assert plan.impact.created_region_count == 2  # analysis region plus unassigned region
    assert plan.impact.created_line_count == 1
    assert result.region_delta is not None
    assert result.outcome is not None
    assert len(result.region_delta.created_region_ids) == plan.impact.created_region_count
    assert len(result.outcome.created_line_ids) == plan.impact.created_line_count
    assert (
        result.region_delta.affected_surviving_region_ids
        == plan.impact.affected_existing_region_ids
    )


def test_multiplet_temporary_lines_are_normalized_into_one_link_group() -> None:
    """The plan exposes the exact temporary lines that will receive multiplet links."""
    project = SpectroscopyProject()
    session = project.identify_state
    first = _add_temporary_line(
        session,
        species="C IV 1548",
        lambda_min=1547.0,
        lambda_max=1549.0,
        rest_wavelength=1548.0,
        tie_group_key="civ-doublet",
    )
    second = _add_temporary_line(
        session,
        species="C IV 1550",
        lambda_min=1549.0,
        lambda_max=1551.0,
        rest_wavelength=1550.0,
        tie_group_key="civ-doublet",
    )
    request = _impact_request(
        project, session, (_temporary_line_snapshot(first), _temporary_line_snapshot(second))
    )

    plan = IdentifyRegistrationImpactPreviewUseCase().preview(request)
    result = AtomicIdentifyRegistrationUseCase().register(_atomic_request(request))

    assert len(plan.impact.multiplet_groups) == 1
    assert plan.impact.multiplet_groups[0].tie_group_key == "civ-doublet"
    assert plan.impact.multiplet_groups[0].temporary_line_ids == (
        first.temporary_line_id,
        second.temporary_line_id,
    )
    assert plan.impact.created_line_count == 2
    assert result.outcome is not None
    first_line_id, second_line_id = result.outcome.created_line_ids
    first_line = project.find_absorption_line(first_line_id)
    second_line = project.find_absorption_line(second_line_id)
    assert first_line is not None
    assert second_line is not None
    assert first_line.multiplet_ids == [second_line_id]
    assert second_line.multiplet_ids == [first_line_id]


def test_invalid_temporary_lines_produce_no_change_without_cleanup() -> None:
    """An all-invalid selection is an explicit NoChange preview and command."""
    project = SpectroscopyProject()
    session = project.identify_state
    invalid = _add_temporary_line(session, rest_wavelength=0.0)
    request = _impact_request(project, session, (_temporary_line_snapshot(invalid),))
    before = _runtime_state(project, session)

    plan = IdentifyRegistrationImpactPreviewUseCase().preview(request)
    result = AtomicIdentifyRegistrationUseCase().register(_atomic_request(request))

    assert plan.impact.mutation_outcome is StructureMutationOutcome.NO_CHANGE
    assert plan.impact.normalized_temporary_line_ids == (invalid.temporary_line_id,)
    assert plan.impact.registerable_temporary_line_ids == ()
    assert plan.impact.rejected_temporary_line_ids == (invalid.temporary_line_id,)
    assert plan.impact.created_region_count == 0
    assert plan.impact.created_line_count == 0
    assert result.mutation_outcome is StructureMutationOutcome.NO_CHANGE
    assert _runtime_state(project, session) == before


def test_preview_rejects_stale_temporary_line_without_additional_changes() -> None:
    """Temporary line drift fails exact preflight and preview changes nothing further."""
    project = SpectroscopyProject()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    request = _impact_request(project, session, (_temporary_line_snapshot(temporary_line),))
    temporary_line.lambda_max += 1.0
    before = _runtime_state(project, session)

    with pytest.raises(ValueError, match="temporary-line source is stale"):
        IdentifyRegistrationImpactPreviewUseCase().preview(request)

    assert _runtime_state(project, session) == before


def test_preview_rejects_stale_region_membership_without_additional_changes() -> None:
    """Region membership drift fails exact preflight and preview remains read-only."""
    project, _region_id = _project_with_existing_region()
    session = project.identify_state
    temporary_line = _add_temporary_line(session)
    request = _impact_request(project, session, (_temporary_line_snapshot(temporary_line),))
    project.add_absorption_line(
        species="Si IV",
        rest_wavelength=1400.0,
        center_z=0.0,
        window_kms=100.0,
        multiplet_label="Si IV",
        transition_name="external",
        oscillator_strength=0.1,
        gamma_value=1e8,
        lambda_range=(1399.0, 1401.0),
    )
    before = _runtime_state(project, session)

    with pytest.raises(ValueError, match="membership targets are stale"):
        IdentifyRegistrationImpactPreviewUseCase().preview(request)

    assert _runtime_state(project, session) == before
