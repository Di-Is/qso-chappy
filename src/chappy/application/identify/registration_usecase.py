"""Use cases for identify temporary-line registration preparation."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.application.identify.grouping import UnionFind
from chappy.application.identify.models import (
    AbsorptionLineRegistrationRequest,
    AbsorptionLineRegistrationResult,
    BuildRegionAssignmentRequest,
    BuildRegionAssignmentResult,
    BuildRegionPreviewsRequest,
    BuildRegionPreviewsResult,
    BuildRegistrationOutcomeRequest,
    ExistingRegionSnapshot,
    IdentifyRegistrationImpactPreview,
    IdentifyRegistrationMultipletGroup,
    IdentifyRegistrationPlan,
    RegionAssignmentOperation,
    RegionAssignmentOperationKind,
    RegionPreviewSnapshot,
    RegisteredLineReference,
    RegisteredLineState,
    RegistrationErrorCode,
    RegistrationOutcome,
    TemporaryLineSnapshot,
)
from chappy.application.structure.models import StructureMutationOutcome
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.absorption.multiplet_service import setup_multiplet_cross_references
from chappy.core.constants import LIGHT_SPEED_KMS

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.velocity_ranges import MultipletGroupingVelocityTolerance


class IdentifyProjectMutationPort(Protocol):
    """Project operations required by identify registration."""

    def add_absorption_line(  # noqa: PLR0913 - project API exposes explicit fields
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
        """Register one absorption line."""

    def find_absorption_region(self, region_id: str) -> AbsorptionRegion | None:
        """Return an absorption region by ID."""

    def assign_line_to_region(self, line_id: str, region_id: str | None) -> None:
        """Assign one line to a region."""

    def create_region_with_lines(self, line_ids: Sequence[str]) -> AbsorptionRegion:
        """Create a region with line IDs."""

    def ensure_absorption_unassigned_region(self) -> AbsorptionRegion:
        """Ensure the unassigned absorption region exists."""

    def list_absorption_regions(self) -> list[AbsorptionRegion]:
        """Return current absorption regions."""


class RegistrationSessionCleanupPort(Protocol):
    """Session operations required by identify registration."""

    def remove_temporary_lines(self, temporary_line_ids: Iterable[str]) -> list[str]:
        """Remove processed temporary lines."""


@dataclass(frozen=True, slots=True)
class RegisterSelectedLinesRequest:
    """Request for registering selected identify temporary lines."""

    project: IdentifyProjectMutationPort
    session: RegistrationSessionCleanupPort
    plan: IdentifyRegistrationPlan


@dataclass(frozen=True, slots=True)
class RegisterSelectedLinesResult:
    """Result of confirming selected identify temporary lines."""

    outcome: RegistrationOutcome | None
    mode_sync_line_ids: tuple[str, ...]


class BuildAbsorptionLineRegistrationRequestUseCase:
    """Build typed absorption line creation data from a temporary line."""

    def build(self, temporary_line: TemporaryLineSnapshot) -> AbsorptionLineRegistrationResult:
        """Build an absorption line registration request.

        Args:
            temporary_line: Temporary line selected for registration.

        Returns:
            Registration request result. The request is None when required atomic data is
            invalid.
        """
        if temporary_line.rest_wavelength <= 0:
            return AbsorptionLineRegistrationResult(
                request=None, error_code=RegistrationErrorCode.INVALID_REST_WAVELENGTH
            )

        request = AbsorptionLineRegistrationRequest(
            temporary_line_id=temporary_line.temporary_line_id,
            atomic_line_id=temporary_line.line_id,
            species=temporary_line.species,
            rest_wavelength=temporary_line.rest_wavelength,
            center_z=temporary_line.center_z,
            window_kms=temporary_line.analysis_half_width.kms,
            multiplet_label=temporary_line.multiplet_label,
            transition_name=temporary_line.transition_name,
            oscillator_strength=temporary_line.oscillator_strength,
            gamma_value=temporary_line.gamma_value,
            lambda_range=(temporary_line.lambda_min, temporary_line.lambda_max),
            created_by=temporary_line.creation_method,
        )
        return AbsorptionLineRegistrationResult(request=request)


class BuildIdentifyRegistrationPlanUseCase:
    """Normalize temporary-line registration decisions into one immutable plan."""

    def __init__(self) -> None:
        """Create pure planning dependencies."""
        self._line_request_usecase = BuildAbsorptionLineRegistrationRequestUseCase()
        self._region_preview_usecase = BuildRegionPreviewsUseCase()

    def build(self, request: BuildRegionPreviewsRequest) -> IdentifyRegistrationPlan:
        """Build a plan shared by side-effect-free preview and registration mutation."""
        normalized_temporary_lines = request.temporary_lines
        normalized_temporary_line_ids = tuple(
            temporary_line.temporary_line_id for temporary_line in normalized_temporary_lines
        )
        if len(normalized_temporary_line_ids) != len(set(normalized_temporary_line_ids)):
            msg = "Identify registration temporary-line identities must be unique."
            raise ValueError(msg)

        existing_region_ids = tuple(region.region_id for region in request.existing_regions)
        if len(existing_region_ids) != len(set(existing_region_ids)):
            msg = "Identify registration region snapshot identities must be unique."
            raise ValueError(msg)

        registerable_temporary_lines: list[TemporaryLineSnapshot] = []
        registration_requests: list[AbsorptionLineRegistrationRequest] = []
        rejected_temporary_line_ids: list[str] = []
        for temporary_line in normalized_temporary_lines:
            prepared = self._line_request_usecase.build(temporary_line)
            if prepared.request is None:
                rejected_temporary_line_ids.append(temporary_line.temporary_line_id)
            else:
                registerable_temporary_lines.append(temporary_line)
                registration_requests.append(prepared.request)

        previews = self._region_preview_usecase.build(request).previews
        registerable_temporary_line_ids = tuple(
            temporary_line.temporary_line_id for temporary_line in registerable_temporary_lines
        )
        registerable_id_set = set(registerable_temporary_line_ids)
        impactful_previews = tuple(
            preview
            for preview in previews
            if registerable_id_set.intersection(preview.member_temporary_line_ids)
        )
        affected_existing_region_id_set = {
            preview.existing_group_id
            for preview in impactful_previews
            if preview.existing_group_id is not None
        }
        affected_existing_region_ids = tuple(
            region_id
            for region_id in existing_region_ids
            if region_id in affected_existing_region_id_set
        )
        changed = bool(registerable_temporary_lines)
        created_region_count = 0
        if changed:
            created_region_count = sum(
                preview.existing_group_id is None for preview in impactful_previews
            )
            if UNASSIGNED_REGION_ID not in existing_region_ids:
                created_region_count += 1

        grouped_temporary_line_ids: dict[str, list[str]] = defaultdict(list)
        for temporary_line in registerable_temporary_lines:
            if temporary_line.tie_group_key:
                grouped_temporary_line_ids[temporary_line.tie_group_key].append(
                    temporary_line.temporary_line_id
                )
        multiplet_groups = tuple(
            IdentifyRegistrationMultipletGroup(
                tie_group_key=tie_group_key, temporary_line_ids=tuple(temporary_line_ids)
            )
            for tie_group_key, temporary_line_ids in grouped_temporary_line_ids.items()
            if len(temporary_line_ids) >= 2
        )
        impact = IdentifyRegistrationImpactPreview(
            mutation_outcome=(
                StructureMutationOutcome.CHANGED if changed else StructureMutationOutcome.NO_CHANGE
            ),
            normalized_temporary_line_ids=normalized_temporary_line_ids,
            registerable_temporary_line_ids=registerable_temporary_line_ids,
            rejected_temporary_line_ids=tuple(rejected_temporary_line_ids),
            affected_existing_region_ids=affected_existing_region_ids,
            created_region_count=created_region_count,
            created_line_count=len(registerable_temporary_lines),
            affected_model_component_ids=(),
            affected_mask_ids=(),
            multiplet_groups=multiplet_groups,
            multi_overlap_warning=(
                any(preview.overlap_warning for preview in impactful_previews)
                if changed
                else False
            ),
        )
        return IdentifyRegistrationPlan(
            normalized_temporary_lines=normalized_temporary_lines,
            registration_requests=tuple(registration_requests),
            region_previews=previews,
            impact=impact,
        )


class BuildRegionAssignmentUseCase:
    """Build region assignment operations for registered absorption lines."""

    def build(self, request: BuildRegionAssignmentRequest) -> BuildRegionAssignmentResult:
        """Build operations from previews and registered line references.

        Args:
            request: Current registration previews and created absorption line references.

        Returns:
            Ordered region assignment operations. Previews without registered members are
            ignored.
        """
        line_id_by_temporary_line_id = {
            line.temporary_line_id: line.line_id for line in request.registered_lines
        }
        operations: list[RegionAssignmentOperation] = []

        for preview in request.previews:
            member_line_ids = tuple(
                line_id_by_temporary_line_id[temporary_line_id]
                for temporary_line_id in preview.member_temporary_line_ids
                if temporary_line_id in line_id_by_temporary_line_id
            )
            if not member_line_ids:
                continue

            if preview.existing_group_id:
                operations.append(
                    RegionAssignmentOperation(
                        kind=RegionAssignmentOperationKind.ADD_TO_EXISTING,
                        line_ids=member_line_ids,
                        existing_region_id=preview.existing_group_id,
                    )
                )
            else:
                operations.append(
                    RegionAssignmentOperation(
                        kind=RegionAssignmentOperationKind.CREATE_REGION, line_ids=member_line_ids
                    )
                )

        return BuildRegionAssignmentResult(operations=tuple(operations))


class BuildRegistrationOutcomeUseCase:
    """Build typed outcome IDs after temporary-line registration."""

    def build(self, request: BuildRegistrationOutcomeRequest) -> RegistrationOutcome:
        """Build a registration outcome from before/after project snapshots.

        Args:
            request: Existing region IDs, current region IDs, registered line states, and
                failed line IDs.

        Returns:
            Typed outcome for session cleanup, history, and status messages.
        """
        existing_region_ids = set(request.existing_region_ids)
        created_region_ids = tuple(
            region_id
            for region_id in request.all_region_ids_after
            if region_id not in existing_region_ids
        )
        created_line_ids = tuple(line.line_id for line in request.registered_lines)
        failed_temporary_line_ids = tuple(request.failed_temporary_line_ids)
        processed_temporary_line_ids = (
            tuple(line.temporary_line_id for line in request.registered_lines)
            + failed_temporary_line_ids
        )
        affected_region_ids_list: list[str] = []
        seen_region_ids: set[str] = set()
        for line in request.registered_lines:
            if line.region_id is None or line.region_id in seen_region_ids:
                continue
            affected_region_ids_list.append(line.region_id)
            seen_region_ids.add(line.region_id)

        appended_region_ids = tuple(
            region_id for region_id in affected_region_ids_list if region_id in existing_region_ids
        )
        return RegistrationOutcome(
            created_line_ids=created_line_ids,
            created_region_ids=created_region_ids,
            processed_temporary_line_ids=processed_temporary_line_ids,
            affected_region_ids=tuple(affected_region_ids_list),
            appended_region_ids=appended_region_ids,
            confirmed_count=len(created_line_ids),
            failed_count=len(failed_temporary_line_ids),
            multi_overlap_warning=request.multi_overlap_warning,
        )


class RegisterSelectedLinesUseCase:
    """Register selected identify temporary lines through project and session ports."""

    def __init__(self) -> None:
        """Create registration use case dependencies."""
        self._assignment_usecase = BuildRegionAssignmentUseCase()
        self._outcome_usecase = BuildRegistrationOutcomeUseCase()

    def register(self, request: RegisterSelectedLinesRequest) -> RegisterSelectedLinesResult:
        """Group temporary lines, register them, and clean up processed session state.

        Args:
            request: Registration request containing mutation ports and grouping inputs.

        Returns:
            Registration result. The outcome is None when no lines could be created.
        """
        plan = request.plan
        if plan.impact.mutation_outcome is StructureMutationOutcome.NO_CHANGE:
            return RegisterSelectedLinesResult(outcome=None, mode_sync_line_ids=())

        existing_region_ids = tuple(
            region.region_id for region in request.project.list_absorption_regions()
        )
        created_lines: dict[str, AbsorptionLine] = {}

        for line_request in plan.registration_requests:
            registered = self._materialize_registration_request(request.project, line_request)
            created_lines[line_request.temporary_line_id] = registered

        if not created_lines:
            msg = "Changed Identify registration plan produced no registered lines."
            raise RuntimeError(msg)

        setup_multiplet_cross_references(
            grouped_lines={
                group.tie_group_key: [
                    created_lines[temporary_line_id]
                    for temporary_line_id in group.temporary_line_ids
                ]
                for group in plan.impact.multiplet_groups
            }
        )

        self._assign_groups_from_previews(
            project=request.project, previews=plan.region_previews, lines_by_id=created_lines
        )

        request.project.ensure_absorption_unassigned_region()

        outcome = self._outcome_usecase.build(
            BuildRegistrationOutcomeRequest(
                existing_region_ids=existing_region_ids,
                all_region_ids_after=tuple(
                    region.region_id for region in request.project.list_absorption_regions()
                ),
                registered_lines=tuple(
                    RegisteredLineState(
                        temporary_line_id=temporary_line_id,
                        line_id=line.line_id,
                        region_id=line.region_id,
                    )
                    for temporary_line_id, line in created_lines.items()
                ),
                failed_temporary_line_ids=plan.impact.rejected_temporary_line_ids,
                multi_overlap_warning=plan.impact.multi_overlap_warning,
            )
        )

        request.session.remove_temporary_lines(set(outcome.processed_temporary_line_ids))

        return RegisterSelectedLinesResult(
            outcome=outcome, mode_sync_line_ids=outcome.created_line_ids
        )

    @staticmethod
    def _materialize_registration_request(
        project: IdentifyProjectMutationPort, line_request: AbsorptionLineRegistrationRequest
    ) -> AbsorptionLine:
        """Create one absorption line from a normalized registration request.

        Args:
            project: Project mutation port.
            line_request: Prepared line creation data retained by the preview plan.

        Returns:
            Created absorption line.
        """
        return project.add_absorption_line(
            species=line_request.species,
            rest_wavelength=line_request.rest_wavelength,
            center_z=line_request.center_z,
            window_kms=line_request.window_kms,
            multiplet_label=line_request.multiplet_label,
            transition_name=line_request.transition_name,
            oscillator_strength=line_request.oscillator_strength,
            gamma_value=line_request.gamma_value,
            lambda_range=line_request.lambda_range,
            multiplet_ids=(),
            created_by=line_request.created_by,
        )

    def _assign_groups_from_previews(
        self,
        *,
        project: IdentifyProjectMutationPort,
        previews: tuple[RegionPreviewSnapshot, ...],
        lines_by_id: dict[str, AbsorptionLine],
    ) -> None:
        """Apply region assignment operations through the project port.

        Args:
            project: Project mutation port.
            previews: Registration previews.
            lines_by_id: Created absorption lines keyed by temporary line ID.
        """
        assignment_result = self._assignment_usecase.build(
            BuildRegionAssignmentRequest(
                previews=previews,
                registered_lines=tuple(
                    RegisteredLineReference(
                        temporary_line_id=temporary_line_id, line_id=line.line_id
                    )
                    for temporary_line_id, line in lines_by_id.items()
                ),
            )
        )
        for operation in assignment_result.operations:
            if operation.kind is RegionAssignmentOperationKind.ADD_TO_EXISTING:
                if operation.existing_region_id is None:
                    msg = "Existing-region assignment operation requires a region id."
                    raise RuntimeError(msg)
                existing_region = project.find_absorption_region(operation.existing_region_id)
                if existing_region is None:
                    msg = (
                        "Existing-region assignment target was not found: "
                        f"{operation.existing_region_id}"
                    )
                    raise RuntimeError(msg)
                for line_id in operation.line_ids:
                    project.assign_line_to_region(line_id, existing_region.region_id)
            else:
                project.create_region_with_lines(operation.line_ids)


class BuildRegionPreviewsUseCase:
    """Build registration previews from temporary lines and existing regions."""

    def build(self, request: BuildRegionPreviewsRequest) -> BuildRegionPreviewsResult:
        """Build preview groups based on wavelength overlap and multiplet proximity.

        Args:
            request: Preview grouping request.

        Returns:
            Region preview result.
        """
        lines_list = list(request.temporary_lines)
        if not lines_list:
            return BuildRegionPreviewsResult(previews=())

        uf = UnionFind(len(lines_list))
        _union_by_wavelength_overlap(uf, lines_list)
        _union_by_tie_group(uf, lines_list, request.multiplet_grouping_tolerance)
        _merge_overlapping_groups(uf, lines_list)

        groups: dict[int, list[TemporaryLineSnapshot]] = defaultdict(list)
        for index, line in enumerate(lines_list):
            groups[uf.find(index)].append(line)

        component_to_overlapping_regions: dict[int, tuple[str, ...]] = {}
        for root, group_lines in groups.items():
            component_to_overlapping_regions[root] = _overlapping_existing_region_ids(
                group_lines, request.existing_regions
            )

        region_names = {
            existing.region_id: existing.display_name for existing in request.existing_regions
        }
        previews: list[RegionPreviewSnapshot] = []
        for preview_index, (root_index, group_lines) in enumerate(groups.items(), start=1):
            species_counts = _count_species_in_group(group_lines, request.unknown_label)
            overlapping_region_ids = component_to_overlapping_regions[root_index]
            # Absorb into the first overlapping region; the warning surfaces the ambiguity.
            overlap_warning = len(overlapping_region_ids) > 1
            existing_group_id = overlapping_region_ids[0] if overlapping_region_ids else None

            if existing_group_id is not None:
                group_name = f"→ {region_names.get(existing_group_id, existing_group_id)}"
                preview_id = f"add-to-{existing_group_id}"
            else:
                lambda_min = min(line.lambda_min for line in group_lines)
                lambda_max = max(line.lambda_max for line in group_lines)
                main_species = max(species_counts.items(), key=lambda item: item[1])[0]
                group_name = f"{main_species} @ {lambda_min:.1f}-{lambda_max:.1f}Å"
                preview_id = f"preview-{preview_index}"

            previews.append(
                RegionPreviewSnapshot(
                    group_id=preview_id,
                    name=group_name,
                    member_temporary_line_ids=tuple(
                        line.temporary_line_id for line in group_lines
                    ),
                    overlap_warning=overlap_warning,
                    existing_group_id=existing_group_id,
                )
            )

        return BuildRegionPreviewsResult(previews=tuple(previews))


def _derive_redshift(line: TemporaryLineSnapshot) -> float | None:
    """Derive redshift from a temporary line.

    Args:
        line: Temporary line.

    Returns:
        Redshift or None when invalid.
    """
    if math.isfinite(line.center_z):
        return line.center_z
    if line.rest_wavelength > 0:
        center = line.center_wavelength
        if math.isfinite(center) and center > 0:
            return (center / line.rest_wavelength) - 1.0
    return None


def _should_union_by_redshift(
    left: TemporaryLineSnapshot,
    right: TemporaryLineSnapshot,
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance,
) -> bool:
    """Return whether two temporary lines should be grouped by redshift proximity."""
    left_z = _derive_redshift(left)
    right_z = _derive_redshift(right)
    if left_z is None or right_z is None:
        return False

    delta_velocity = abs(left_z - right_z) * LIGHT_SPEED_KMS
    return delta_velocity <= multiplet_grouping_tolerance.kms


def _union_by_tie_group(
    uf: UnionFind,
    lines: Sequence[TemporaryLineSnapshot],
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance,
) -> None:
    """Union temporary lines with the same declared tie group and close redshift."""
    tie_group_map: dict[str, list[int]] = defaultdict(list)
    for index, line in enumerate(lines):
        if line.tie_group_key:
            tie_group_map[line.tie_group_key].append(index)

    for indices in tie_group_map.values():
        if len(indices) < 2:
            continue
        for left_offset, left_index in enumerate(indices):
            for right_index in indices[left_offset + 1 :]:
                if _should_union_by_redshift(
                    lines[left_index], lines[right_index], multiplet_grouping_tolerance
                ):
                    uf.union(left_index, right_index)


def _has_wavelength_overlap(left: TemporaryLineSnapshot, right: TemporaryLineSnapshot) -> bool:
    """Return whether two temporary-line wavelength ranges overlap."""
    return not (left.lambda_max < right.lambda_min or right.lambda_max < left.lambda_min)


def _union_by_wavelength_overlap(uf: UnionFind, lines: Sequence[TemporaryLineSnapshot]) -> None:
    """Union temporary lines with overlapping wavelength ranges."""
    for left_index, left in enumerate(lines):
        for right_index in range(left_index + 1, len(lines)):
            if _has_wavelength_overlap(left, lines[right_index]):
                uf.union(left_index, right_index)


def _merge_overlapping_groups(uf: UnionFind, lines: Sequence[TemporaryLineSnapshot]) -> None:
    """Merge groups where any member ranges overlap across groups."""
    roots = list({uf.find(index) for index in range(len(lines))})
    for left_offset, left_root in enumerate(roots):
        for right_root in roots[left_offset + 1 :]:
            current_left = uf.find(left_root)
            current_right = uf.find(right_root)
            if current_left == current_right:
                continue
            if _groups_have_overlapping_lines(uf, lines, current_left, current_right):
                uf.union(left_root, right_root)


def _groups_have_overlapping_lines(
    uf: UnionFind, lines: Sequence[TemporaryLineSnapshot], left_root: int, right_root: int
) -> bool:
    """Return whether two temporary-line groups have overlapping member lines."""
    left_members = [line for index, line in enumerate(lines) if uf.find(index) == left_root]
    right_members = [line for index, line in enumerate(lines) if uf.find(index) == right_root]
    return any(
        _has_wavelength_overlap(left, right) for left in left_members for right in right_members
    )


def _overlapping_existing_region_ids(
    group_lines: Sequence[TemporaryLineSnapshot],
    existing_regions: tuple[ExistingRegionSnapshot, ...],
) -> tuple[str, ...]:
    """Return existing region IDs overlapping a temporary-line group, in first-found order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for temporary_line in group_lines:
        for existing in existing_regions:
            if existing.region_id in seen:
                continue
            if _has_overlap_with_any_range(temporary_line, existing.line_ranges):
                seen.add(existing.region_id)
                ordered.append(existing.region_id)
    return tuple(ordered)


def _has_overlap_with_any_range(
    temporary_line: TemporaryLineSnapshot, ranges: tuple[tuple[float, float], ...]
) -> bool:
    """Return whether a temporary line overlaps any existing line range."""
    return any(
        not (temporary_line.lambda_max < line_min or line_max < temporary_line.lambda_min)
        for line_min, line_max in ranges
    )


def _count_species_in_group(
    lines: Iterable[TemporaryLineSnapshot], unknown_label: str
) -> dict[str, int]:
    """Count temporary-line species labels in a group."""
    counts: dict[str, int] = defaultdict(int)
    for line in lines:
        species = line.species or unknown_label
        counts[species] += 1
    return counts
