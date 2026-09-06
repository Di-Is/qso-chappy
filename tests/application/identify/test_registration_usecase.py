"""Tests for identify registration preparation use cases."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pytest

from chappy.application.identify import (
    BuildAbsorptionLineRegistrationRequestUseCase,
    BuildIdentifyRegistrationPlanUseCase,
    BuildRegionAssignmentRequest,
    BuildRegionAssignmentUseCase,
    BuildRegionPreviewsRequest,
    BuildRegionPreviewsUseCase,
    BuildRegistrationOutcomeRequest,
    BuildRegistrationOutcomeUseCase,
    TemporaryLineSnapshot,
    ExistingRegionSnapshot,
    RegionAssignmentOperationKind,
    RegionPreviewSnapshot,
    RegisteredLineReference,
    RegisteredLineState,
    RegisterSelectedLinesRequest,
    RegisterSelectedLinesUseCase,
    RegistrationErrorCode,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.velocity_ranges import LineAnalysisHalfWidth, MultipletGroupingVelocityTolerance


class _FakeProject:
    """Fake project mutation port for registration tests."""

    def __init__(self) -> None:
        """Create an empty fake project."""
        self.lines: dict[str, AbsorptionLine] = {}
        self.regions: dict[str, AbsorptionRegion] = {}
        self.created_regions: list[str] = []
        self._next_line_index = 1
        self._next_region_index = 1

    def add_absorption_line(  # noqa: PLR0913 - mirrors project port
        self,
        *,
        species: str,
        rest_wavelength: float,
        center_z: float,
        window_kms: float,
        multiplet_label: str,
        transition_name: str,
        oscillator_strength: float,
        gamma_value: float,
        lambda_range: tuple[float, float] | None,
        region_id: str | None = None,
        multiplet_ids: Sequence[str] | None = None,
        created_by: str = "identify",
    ) -> AbsorptionLine:
        """Add one fake absorption line."""
        line = AbsorptionLine(
            line_id=f"line-{self._next_line_index}",
            species=species,
            rest_wavelength=rest_wavelength,
            center_z=center_z,
            window_kms=window_kms,
            multiplet_label=multiplet_label,
            transition_name=transition_name,
            oscillator_strength=oscillator_strength,
            gamma_value=gamma_value,
            lambda_range=lambda_range,
            region_id=region_id,
            multiplet_ids=list(multiplet_ids or ()),
            created_by=created_by,
        )
        self._next_line_index += 1
        self.lines[line.line_id] = line
        return line

    def find_absorption_region(self, region_id: str) -> AbsorptionRegion | None:
        """Return a fake region by ID."""
        return self.regions.get(region_id)

    def assign_line_to_region(self, line_id: str, region_id: str | None) -> None:
        """Assign a fake line to a fake region."""
        if region_id is None:
            return
        region = self.regions.setdefault(region_id, AbsorptionRegion(region_id=region_id))
        region.attach_lines([line_id])
        self.lines[line_id].region_id = region_id

    def create_region_with_lines(self, line_ids: Sequence[str]) -> AbsorptionRegion:
        """Create a fake region with lines."""
        region_id = f"region-{self._next_region_index}"
        self._next_region_index += 1
        region = AbsorptionRegion(region_id=region_id)
        self.regions[region_id] = region
        self.created_regions.append(region_id)
        for line_id in line_ids:
            self.assign_line_to_region(line_id, region_id)
        return region

    def ensure_absorption_unassigned_region(self) -> AbsorptionRegion:
        """Ensure fake unassigned region exists."""
        return self.regions.setdefault("unassigned", AbsorptionRegion(region_id="unassigned"))

    def list_absorption_regions(self) -> list[AbsorptionRegion]:
        """Return fake regions."""
        return list(self.regions.values())


class _FakeSession:
    """Fake identify session mutation port for registration tests."""

    def __init__(self) -> None:
        """Create fake session state."""
        self.removed_ids: list[str] = []

    def remove_temporary_lines(self, temporary_line_ids: Iterable[str]) -> list[str]:
        """Record removed temporary line IDs."""
        self.removed_ids = list(temporary_line_ids)
        return self.removed_ids


class _FailingAddProject(_FakeProject):
    """Fake project that fails during line materialization."""

    def add_absorption_line(  # noqa: PLR0913 - mirrors project port
        self,
        *,
        species: str,
        rest_wavelength: float,
        center_z: float,
        window_kms: float,
        multiplet_label: str,
        transition_name: str,
        oscillator_strength: float,
        gamma_value: float,
        lambda_range: tuple[float, float] | None,
        region_id: str | None = None,
        multiplet_ids: Sequence[str] | None = None,
        created_by: str = "identify",
    ) -> AbsorptionLine:
        """Raise as a project mutation invariant failure."""
        _ = (
            species,
            rest_wavelength,
            center_z,
            window_kms,
            multiplet_label,
            transition_name,
            oscillator_strength,
            gamma_value,
            lambda_range,
            region_id,
            multiplet_ids,
            created_by,
        )
        msg = "project mutation failed"
        raise ValueError(msg)


class _FailingUnassignedProject(_FakeProject):
    """Fake project that fails while ensuring the unassigned region."""

    def ensure_absorption_unassigned_region(self) -> AbsorptionRegion:
        """Raise as a required project invariant failure."""
        msg = "unassigned region unavailable"
        raise RuntimeError(msg)


def _temporary_line(
    temporary_line_id: str,
    lambda_min: float,
    lambda_max: float,
    *,
    species: str = "C IV",
    multiplet_id: str = "",
    center_z: float = 0.0,
    rest_wavelength: float = 1000.0,
    velocity_window_kms: float = 200.0,
    multiplet_label: str = "",
    transition_name: str = "",
    creation_method: str = "test",
    tie_group_key: str | None = None,
) -> TemporaryLineSnapshot:
    """Create a temporary line for tests."""
    return TemporaryLineSnapshot(
        temporary_line_id=temporary_line_id,
        species=species,
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        creation_method=creation_method,
        line_id=temporary_line_id,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        multiplet_id=multiplet_id,
        multiplet_label=multiplet_label,
        transition_name=transition_name,
        oscillator_strength=0.1,
        gamma_value=1e8,
        analysis_half_width=LineAnalysisHalfWidth(velocity_window_kms),
        tie_group_key=multiplet_id if tie_group_key is None else tie_group_key,
    )


def _register(
    project: _FakeProject,
    session: _FakeSession,
    temporary_lines: Sequence[TemporaryLineSnapshot],
    existing_regions: Sequence[ExistingRegionSnapshot] = (),
):
    """Run the registration use case with default grouping inputs."""
    return RegisterSelectedLinesUseCase().register(
        RegisterSelectedLinesRequest(
            project=project,
            session=session,
            plan=BuildIdentifyRegistrationPlanUseCase().build(
                BuildRegionPreviewsRequest(
                    temporary_lines=tuple(temporary_lines),
                    existing_regions=tuple(existing_regions),
                    multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
                    unknown_label="Unknown",
                )
            ),
        )
    )


def _existing_snapshots(project: _FakeProject) -> tuple[ExistingRegionSnapshot, ...]:
    """Build existing-region snapshots from the fake project state."""
    return tuple(
        ExistingRegionSnapshot(
            region_id=region.region_id,
            display_name=region.region_id,
            line_ranges=tuple(
                line.lambda_range
                for line in project.lines.values()
                if line.region_id == region.region_id and line.lambda_range is not None
            ),
        )
        for region in project.regions.values()
    )


def test_build_region_previews_groups_overlapping_temporary_lines() -> None:
    """Overlapping temporary lines should be grouped into one preview."""
    first = _temporary_line("a", 1000.0, 1010.0)
    second = _temporary_line("b", 1005.0, 1015.0)

    result = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(first, second),
            existing_regions=(),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )

    assert len(result.previews) == 1
    assert set(result.previews[0].member_temporary_line_ids) == {"a", "b"}
    assert result.previews[0].existing_group_id is None


def test_build_region_previews_detects_existing_region_overlap() -> None:
    """Temporary line overlapping an existing line range should target that region."""
    temporary_line = _temporary_line("candidate", 995.0, 1005.0)
    existing = ExistingRegionSnapshot(
        region_id="region-1",
        display_name="C IV @ 995.0-1005.0 (1)",
        line_ranges=((995.0, 1005.0),),
    )

    result = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(temporary_line,),
            existing_regions=(existing,),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )

    assert len(result.previews) == 1
    assert result.previews[0].existing_group_id == "region-1"
    assert result.previews[0].overlap_warning is False
    assert result.previews[0].name == "→ C IV @ 995.0-1005.0 (1)"


def test_discrete_existing_region_lines_do_not_create_continuous_overlap() -> None:
    """Temporary line between discrete existing line ranges should create a new preview."""
    temporary_line = _temporary_line("candidate", 1095.0, 1105.0)
    existing = ExistingRegionSnapshot(
        region_id="region-1",
        display_name="Test Region",
        line_ranges=((995.0, 1005.0), (1195.0, 1205.0)),
    )

    result = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(temporary_line,),
            existing_regions=(existing,),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )

    assert len(result.previews) == 1
    assert result.previews[0].existing_group_id is None


def test_build_region_previews_warns_when_overlapping_multiple_existing_regions() -> None:
    """Multi-region overlap absorbs into the first region and raises the warning."""
    temporary_line = _temporary_line("candidate", 995.0, 1010.0)
    first = ExistingRegionSnapshot(
        region_id="region-1", display_name="First", line_ranges=((994.0, 1000.0),)
    )
    second = ExistingRegionSnapshot(
        region_id="region-2", display_name="Second", line_ranges=((1005.0, 1012.0),)
    )

    result = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(temporary_line,),
            existing_regions=(first, second),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )

    assert len(result.previews) == 1
    assert result.previews[0].existing_group_id == "region-1"
    assert result.previews[0].overlap_warning is True


def test_same_multiplet_close_redshift_groups_without_wavelength_overlap() -> None:
    """Same multiplet temporary lines within velocity window should be grouped."""
    first = _temporary_line("m1", 1000.0, 1005.0, multiplet_id="M", center_z=1.0)
    second = _temporary_line("m2", 1200.0, 1205.0, multiplet_id="M", center_z=1.0001)

    result = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(first, second),
            existing_regions=(),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )

    assert len(result.previews) == 1
    assert set(result.previews[0].member_temporary_line_ids) == {"m1", "m2"}


def test_grouping_tolerance_is_independent_from_temporary_line_analysis_half_widths() -> None:
    """Temporary line scientific ranges must not leak into multiplet grouping policy."""
    narrow = _temporary_line(
        "narrow", 1000.0, 1005.0, multiplet_id="M", center_z=1.0, velocity_window_kms=10.0
    )
    wide = _temporary_line(
        "wide", 1200.0, 1205.0, multiplet_id="M", center_z=1.0005, velocity_window_kms=2000.0
    )

    grouped = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(narrow, wide),
            existing_regions=(),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )
    separated = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(narrow, wide),
            existing_regions=(),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(100.0),
            unknown_label="Unknown",
        )
    )

    assert len(grouped.previews) == 1
    assert len(separated.previews) == 2


def test_different_declared_keys_do_not_group_same_atomic_multiplet() -> None:
    """DB multiplet equality must not merge registration previews."""
    first = _temporary_line(
        "first", 1000.0, 1005.0, multiplet_id="DB-GROUP", tie_group_key="declared-a", center_z=1.0
    )
    second = _temporary_line(
        "second",
        1200.0,
        1205.0,
        multiplet_id="DB-GROUP",
        tie_group_key="declared-b",
        center_z=1.0001,
    )

    result = BuildRegionPreviewsUseCase().build(
        BuildRegionPreviewsRequest(
            temporary_lines=(first, second),
            existing_regions=(),
            multiplet_grouping_tolerance=MultipletGroupingVelocityTolerance(200.0),
            unknown_label="Unknown",
        )
    )

    assert len(result.previews) == 2


def test_build_region_assignment_creates_region_for_new_preview() -> None:
    """Preview without an existing group should create a new region operation."""
    preview = RegionPreviewSnapshot(
        group_id="preview-1", name="Preview", member_temporary_line_ids=("first", "second")
    )

    result = BuildRegionAssignmentUseCase().build(
        BuildRegionAssignmentRequest(
            previews=(preview,),
            registered_lines=(
                RegisteredLineReference(temporary_line_id="first", line_id="line-1"),
                RegisteredLineReference(temporary_line_id="second", line_id="line-2"),
            ),
        )
    )

    assert len(result.operations) == 1
    operation = result.operations[0]
    assert operation.kind is RegionAssignmentOperationKind.CREATE_REGION
    assert operation.line_ids == ("line-1", "line-2")
    assert operation.existing_region_id is None


def test_build_region_assignment_adds_to_existing_region() -> None:
    """Preview targeting an existing group should emit add operation."""
    preview = RegionPreviewSnapshot(
        group_id="add-to-region-1",
        name="Existing",
        member_temporary_line_ids=("first",),
        existing_group_id="region-1",
    )

    result = BuildRegionAssignmentUseCase().build(
        BuildRegionAssignmentRequest(
            previews=(preview,),
            registered_lines=(
                RegisteredLineReference(temporary_line_id="first", line_id="line-1"),
            ),
        )
    )

    assert len(result.operations) == 1
    operation = result.operations[0]
    assert operation.kind is RegionAssignmentOperationKind.ADD_TO_EXISTING
    assert operation.line_ids == ("line-1",)
    assert operation.existing_region_id == "region-1"


def test_build_region_assignment_ignores_previews_without_registered_members() -> None:
    """Previews with no created members should not emit operations."""
    preview = RegionPreviewSnapshot(
        group_id="preview-1", name="Preview", member_temporary_line_ids=("missing",)
    )

    result = BuildRegionAssignmentUseCase().build(
        BuildRegionAssignmentRequest(
            previews=(preview,),
            registered_lines=(
                RegisteredLineReference(temporary_line_id="first", line_id="line-1"),
            ),
        )
    )

    assert result.operations == ()


def test_build_registration_outcome_reports_history_ids() -> None:
    """Registration outcome should include created, processed, and affected IDs."""
    result = BuildRegistrationOutcomeUseCase().build(
        BuildRegistrationOutcomeRequest(
            existing_region_ids=("region-existing",),
            all_region_ids_after=("region-existing", "region-new"),
            registered_lines=(
                RegisteredLineState(
                    temporary_line_id="candidate-1", line_id="line-1", region_id="region-new"
                ),
                RegisteredLineState(
                    temporary_line_id="candidate-2", line_id="line-2", region_id="region-new"
                ),
            ),
            failed_temporary_line_ids=("candidate-3",),
            multi_overlap_warning=True,
        )
    )

    assert result.created_line_ids == ("line-1", "line-2")
    assert result.created_region_ids == ("region-new",)
    assert result.processed_temporary_line_ids == ("candidate-1", "candidate-2", "candidate-3")
    assert result.affected_region_ids == ("region-new",)
    assert result.appended_region_ids == ()
    assert result.confirmed_count == 2
    assert result.failed_count == 1
    assert result.multi_overlap_warning is True


def test_build_registration_outcome_reports_appended_existing_regions() -> None:
    """Existing regions receiving lines should be reported as appended."""
    result = BuildRegistrationOutcomeUseCase().build(
        BuildRegistrationOutcomeRequest(
            existing_region_ids=("region-existing",),
            all_region_ids_after=("region-existing",),
            registered_lines=(
                RegisteredLineState(
                    temporary_line_id="candidate-1", line_id="line-1", region_id="region-existing"
                ),
            ),
            failed_temporary_line_ids=(),
            multi_overlap_warning=False,
        )
    )

    assert result.created_region_ids == ()
    assert result.appended_region_ids == ("region-existing",)
    assert result.multi_overlap_warning is False


def test_build_registration_outcome_preserves_distinct_affected_region_order() -> None:
    """Affected region IDs should be unique in first-seen order."""
    result = BuildRegistrationOutcomeUseCase().build(
        BuildRegistrationOutcomeRequest(
            existing_region_ids=(),
            all_region_ids_after=(),
            registered_lines=(
                RegisteredLineState(temporary_line_id="a", line_id="line-a", region_id="r2"),
                RegisteredLineState(temporary_line_id="b", line_id="line-b", region_id="r1"),
                RegisteredLineState(temporary_line_id="c", line_id="line-c", region_id="r2"),
                RegisteredLineState(temporary_line_id="d", line_id="line-d", region_id=None),
            ),
            failed_temporary_line_ids=(),
            multi_overlap_warning=False,
        )
    )

    assert result.affected_region_ids == ("r2", "r1")


def test_register_selected_lines_creates_region_and_cleans_session() -> None:
    """Register use case should group internally, create lines, and clean session."""
    project = _FakeProject()
    session = _FakeSession()
    first = _temporary_line("first", 1000.0, 1010.0)
    second = _temporary_line("second", 1005.0, 1015.0)

    result = _register(project, session, (first, second))

    assert result.outcome is not None
    assert result.outcome.created_line_ids == ("line-1", "line-2")
    assert result.outcome.created_region_ids == ("region-1", "unassigned")
    assert set(result.outcome.processed_temporary_line_ids) == {"first", "second"}
    assert result.outcome.affected_region_ids == ("region-1",)
    assert result.outcome.appended_region_ids == ()
    assert result.outcome.multi_overlap_warning is False
    assert result.mode_sync_line_ids == ("line-1", "line-2")
    assert set(session.removed_ids) == {"first", "second"}


def test_register_selected_lines_materializes_declared_key_without_db_multiplet() -> None:
    """Only the explicit key creates materialized absorption-line links."""
    project = _FakeProject()
    session = _FakeSession()
    first = _temporary_line(
        "first", 1000.0, 1005.0, multiplet_id="", tie_group_key="declared-group"
    )
    second = _temporary_line(
        "second", 1200.0, 1205.0, multiplet_id="", tie_group_key="declared-group"
    )

    _register(project, session, (first, second))

    assert project.lines["line-1"].multiplet_ids == ["line-2"]
    assert project.lines["line-2"].multiplet_ids == ["line-1"]


def test_register_selected_lines_adds_to_existing_region() -> None:
    """Temporary lines overlapping an existing region should be appended to it."""
    project = _FakeProject()
    project.regions["existing"] = AbsorptionRegion(region_id="existing")
    session = _FakeSession()
    temporary_line = _temporary_line("candidate", 1000.0, 1005.0)
    existing = ExistingRegionSnapshot(
        region_id="existing", display_name="Existing", line_ranges=((1000.0, 1005.0),)
    )

    result = _register(project, session, (temporary_line,), existing_regions=(existing,))

    assert result.outcome is not None
    assert result.outcome.created_line_ids == ("line-1",)
    assert result.outcome.affected_region_ids == ("existing",)
    assert result.outcome.appended_region_ids == ("existing",)
    assert project.lines["line-1"].region_id == "existing"
    assert project.regions["existing"].line_ids == ["line-1"]


def test_register_selected_lines_includes_failed_temporary_lines_when_some_succeed() -> None:
    """Failed temporary lines should be removed only when at least one line succeeds."""
    project = _FakeProject()
    session = _FakeSession()
    valid = _temporary_line("valid", 1000.0, 1005.0)
    invalid = _temporary_line("invalid", 1006.0, 1010.0, rest_wavelength=0.0)

    result = _register(project, session, (valid, invalid))

    assert result.outcome is not None
    assert result.outcome.created_line_ids == ("line-1",)
    assert result.outcome.processed_temporary_line_ids == ("valid", "invalid")
    assert result.outcome.failed_count == 1
    assert set(session.removed_ids) == {"valid", "invalid"}


def test_register_selected_lines_propagates_project_mutation_failure() -> None:
    """Project mutation failures should not be downgraded to failed temporary lines."""
    project = _FailingAddProject()
    session = _FakeSession()
    temporary_line = _temporary_line("candidate", 1000.0, 1005.0)

    with pytest.raises(ValueError, match="project mutation failed"):
        _register(project, session, (temporary_line,))

    assert session.removed_ids == []


def test_register_selected_lines_requires_unassigned_region_invariant() -> None:
    """Unassigned-region setup errors should fail fast after successful line creation."""
    project = _FailingUnassignedProject()
    session = _FakeSession()
    temporary_line = _temporary_line("candidate", 1000.0, 1005.0)

    with pytest.raises(RuntimeError, match="unassigned region unavailable"):
        _register(project, session, (temporary_line,))

    assert session.removed_ids == []


def test_register_selected_lines_requires_existing_preview_region() -> None:
    """Existing-region snapshots must reference a region present in the project."""
    project = _FakeProject()
    session = _FakeSession()
    temporary_line = _temporary_line("candidate", 1000.0, 1005.0)
    missing = ExistingRegionSnapshot(
        region_id="missing", display_name="Missing", line_ranges=((1000.0, 1005.0),)
    )

    with pytest.raises(RuntimeError, match="Existing-region assignment target was not found"):
        _register(project, session, (temporary_line,), existing_regions=(missing,))

    assert session.removed_ids == []


def test_register_selected_lines_leaves_session_when_all_temporary_lines_fail() -> None:
    """Session should remain untouched when no absorption lines are created."""
    project = _FakeProject()
    session = _FakeSession()
    invalid = _temporary_line("invalid", 1000.0, 1005.0, rest_wavelength=0.0)

    result = _register(project, session, (invalid,))

    assert result.outcome is None
    assert result.mode_sync_line_ids == ()
    assert session.removed_ids == []


def test_register_selected_lines_reports_multi_overlap_warning() -> None:
    """Registering across multiple existing regions surfaces the outcome warning."""
    project = _FakeProject()
    project.regions["region-a"] = AbsorptionRegion(region_id="region-a")
    project.regions["region-b"] = AbsorptionRegion(region_id="region-b")
    session = _FakeSession()
    temporary_line = _temporary_line("candidate", 995.0, 1010.0)
    existing = (
        ExistingRegionSnapshot(
            region_id="region-a", display_name="A", line_ranges=((994.0, 1000.0),)
        ),
        ExistingRegionSnapshot(
            region_id="region-b", display_name="B", line_ranges=((1005.0, 1012.0),)
        ),
    )

    result = _register(project, session, (temporary_line,), existing_regions=existing)

    assert result.outcome is not None
    assert result.outcome.multi_overlap_warning is True
    assert result.outcome.appended_region_ids == ("region-a",)
    assert project.lines["line-1"].region_id == "region-a"


def test_partial_registrations_converge_to_one_shot_structure() -> None:
    """Registering temporary lines one by one yields the same regions as one shot."""
    first = _temporary_line("first", 1000.0, 1010.0)
    second = _temporary_line("second", 1005.0, 1015.0)

    one_shot_project = _FakeProject()
    _register(one_shot_project, _FakeSession(), (first, second))

    partial_project = _FakeProject()
    _register(partial_project, _FakeSession(), (first,))
    _register(
        partial_project,
        _FakeSession(),
        (second,),
        existing_regions=_existing_snapshots(partial_project),
    )

    def region_structure(project: _FakeProject) -> dict[str, set[tuple[float, float]]]:
        return {
            region_id: {
                line.lambda_range
                for line in project.lines.values()
                if line.region_id == region_id and line.lambda_range is not None
            }
            for region_id in project.regions
        }

    assert region_structure(partial_project) == region_structure(one_shot_project)


def test_build_absorption_line_registration_request_preserves_temporary_line_data() -> None:
    """Registration request should contain the temporary line's reproducible atomic data."""
    temporary_line = _temporary_line(
        "candidate",
        1547.0,
        1549.0,
        center_z=1.5,
        velocity_window_kms=123.0,
        multiplet_label="C IV doublet",
        transition_name="C IV 1548",
        creation_method="velocity",
    )

    result = BuildAbsorptionLineRegistrationRequestUseCase().build(temporary_line)

    assert result.error_code is None
    assert result.request is not None
    assert result.request.temporary_line_id == "candidate"
    assert result.request.atomic_line_id == "candidate"
    assert result.request.species == "C IV"
    assert result.request.rest_wavelength == 1000.0
    assert result.request.center_z == 1.5
    assert result.request.window_kms == 123.0
    assert result.request.multiplet_label == "C IV doublet"
    assert result.request.transition_name == "C IV 1548"
    assert result.request.oscillator_strength == 0.1
    assert result.request.gamma_value == 1e8
    assert result.request.lambda_range == (1547.0, 1549.0)
    assert result.request.created_by == "velocity"


def test_temporary_line_snapshot_rejects_zero_analysis_half_width() -> None:
    """Temporary line snapshots reject invalid scientific ranges at the typed boundary."""
    with pytest.raises(ValueError, match="between"):
        _temporary_line("candidate", 1547.0, 1549.0, velocity_window_kms=0.0)


def test_registration_request_rejects_invalid_rest_wavelength() -> None:
    """Invalid rest wavelength should produce a typed registration error."""
    temporary_line = _temporary_line("candidate", 1547.0, 1549.0, rest_wavelength=0.0)

    result = BuildAbsorptionLineRegistrationRequestUseCase().build(temporary_line)

    assert result.request is None
    assert result.error_code == RegistrationErrorCode.INVALID_REST_WAVELENGTH
