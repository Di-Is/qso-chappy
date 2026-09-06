"""Typed models for identify application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from chappy.application.structure.models import StructureMutationOutcome

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from chappy.core.absorption.search9_detection import Search9Parameters
    from chappy.core.velocity_ranges import (
        LineAnalysisHalfWidth,
        MultipletGroupingVelocityTolerance,
        NewCandidateAnalysisHalfWidth,
    )

ApplicationRegionStatus = Literal["identified", "candidate", "unused"]


class DetectionErrorCode(StrEnum):
    """Error categories for identify detection."""

    NO_ERROR_ARRAY = "no-error-array"
    INSUFFICIENT_DATA = "insufficient-data"
    NO_CONTINUUM = "no-continuum"
    FAILED = "failed"


class RegistrationErrorCode(StrEnum):
    """Error categories for identify temporary-line registration preparation."""

    INVALID_REST_WAVELENGTH = "invalid-rest-wavelength"


class RegionAssignmentOperationKind(StrEnum):
    """Operation categories for assigning registered lines to regions."""

    ADD_TO_EXISTING = "add-to-existing"
    CREATE_REGION = "create-region"


@dataclass(frozen=True, slots=True)
class AtomicLineSnapshot:
    """Immutable atomic line data needed by identify temporary-line workflows."""

    line_id: str
    species: str
    wavelength_angstrom: float
    oscillator_strength: float
    gamma_value: float
    multiplet_id: str
    multiplet_label: str
    transition_name: str
    tie_group_key: str


@dataclass(frozen=True, slots=True)
class TemporaryLineSnapshot:
    """Immutable temporary line data used by identify application workflows."""

    temporary_line_id: str
    species: str
    lambda_min: float
    lambda_max: float
    creation_method: str
    line_id: str
    rest_wavelength: float
    center_z: float
    multiplet_id: str
    multiplet_label: str
    transition_name: str
    oscillator_strength: float
    gamma_value: float
    analysis_half_width: LineAnalysisHalfWidth
    tie_group_key: str

    @property
    def center_wavelength(self) -> float:
        """Return the midpoint of the wavelength span."""
        return (self.lambda_min + self.lambda_max) / 2.0


@dataclass(frozen=True, slots=True)
class DetectedRegionSnapshot:
    """Immutable detected region data returned by identify detection."""

    region_id: str
    lambda_start: float
    lambda_end: float
    lambda_bar: float
    sigma: float
    status: ApplicationRegionStatus


@dataclass(frozen=True, slots=True)
class RegionPreviewSnapshot:
    """Immutable registration preview data used by application workflows."""

    group_id: str
    name: str
    member_temporary_line_ids: tuple[str, ...] = ()
    overlap_warning: bool = False
    color: str | None = None
    existing_group_id: str | None = None


@dataclass(frozen=True, slots=True)
class VelocityTemporaryLineRequest:
    """Request for building identify velocity preview entries."""

    observed_wavelength: float
    baseline_line: AtomicLineSnapshot
    preset_lines: tuple[AtomicLineSnapshot, ...]
    new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth
    include_all_preview_lines: bool
    data_bounds: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class PreviewEntryModel:
    """Typed model for one identify cursor preview entry."""

    line_id: str
    lambda_min: float
    lambda_max: float
    center: float
    label: str
    original_label: str
    transition_name: str
    color: str
    is_primary: bool
    fill_alpha: float
    line_alpha: float
    line_width: float
    line_style: str
    multiplet_id: str
    multiplet_label: str
    species: str
    rest_wavelength: float
    oscillator_strength: float
    gamma_value: float
    delta_velocity: float | None
    tie_group_key: str


@dataclass(frozen=True, slots=True)
class VelocityPreview:
    """Preview-only result for identify cursor overlays."""

    entries: tuple[PreviewEntryModel, ...]
    redshift: float


@dataclass(frozen=True, slots=True)
class VelocitySliceSelection:
    """Selected velocity slice used to create identify temporary lines."""

    line_id: str | None
    label: str
    is_primary: bool
    tie_group_key: str


@dataclass(frozen=True, slots=True)
class VelocitySliceTemporaryLineRequest:
    """Request to create preview entries from selected velocity slices."""

    center_z: float
    new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth
    slices: tuple[VelocitySliceSelection, ...]


@dataclass(frozen=True, slots=True)
class TemporaryLineCreationEntry:
    """Entry used to create one identify temporary line."""

    preview_entry: PreviewEntryModel
    redshift: float
    analysis_half_width: LineAnalysisHalfWidth


@dataclass(frozen=True, slots=True)
class CreatedTemporaryLine:
    """Snapshot of a temporary line created by the application use case."""

    temporary_line_id: str
    entry: PreviewEntryModel


@dataclass(frozen=True, slots=True)
class TemporaryLineCreationResult:
    """Result of creating identify temporary lines from preview entries."""

    created: tuple[CreatedTemporaryLine, ...]
    duplicate_count: int
    limit_reached: bool


@dataclass(frozen=True, slots=True)
class DetectCandidateLinesRequest:
    """Request for Search9 candidate line detection."""

    wavelength: NDArray[np.float64]
    flux: NDArray[np.float64]
    error: NDArray[np.float64] | None
    continuum_flux: NDArray[np.float64] | None
    parameters: Search9Parameters
    existing_line_ranges: tuple[tuple[float, float], ...]
    temporary_line_ranges: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class DetectCandidateLinesResult:
    """Result of Search9 candidate line detection."""

    regions: tuple[DetectedRegionSnapshot, ...]
    error_code: DetectionErrorCode | None = None
    error_detail: str | None = None


@dataclass(frozen=True, slots=True)
class ExistingRegionSnapshot:
    """Snapshot of an existing absorption region used for preview grouping."""

    region_id: str
    display_name: str
    line_ranges: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationMultipletGroup:
    """Registerable temporary lines that will receive mutual multiplet links."""

    tie_group_key: str
    temporary_line_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require a real, normalized multiplet group."""
        if not self.tie_group_key:
            msg = "Identify registration multiplet groups require a tie-group key."
            raise ValueError(msg)
        if len(self.temporary_line_ids) < 2 or len(set(self.temporary_line_ids)) != len(
            self.temporary_line_ids
        ):
            msg = "Identify registration multiplet groups require distinct temporary lines."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationImpactPreview:
    """Side-effect-free scientific impact of one normalized registration plan."""

    mutation_outcome: StructureMutationOutcome
    normalized_temporary_line_ids: tuple[str, ...]
    registerable_temporary_line_ids: tuple[str, ...]
    rejected_temporary_line_ids: tuple[str, ...]
    affected_existing_region_ids: tuple[str, ...]
    created_region_count: int
    created_line_count: int
    affected_model_component_ids: tuple[str, ...]
    affected_mask_ids: tuple[str, ...]
    multiplet_groups: tuple[IdentifyRegistrationMultipletGroup, ...]
    multi_overlap_warning: bool

    def __post_init__(self) -> None:
        """Require normalized identities and an outcome consistent with the impact."""
        identity_fields = (
            self.normalized_temporary_line_ids,
            self.registerable_temporary_line_ids,
            self.rejected_temporary_line_ids,
            self.affected_existing_region_ids,
            self.affected_model_component_ids,
            self.affected_mask_ids,
        )
        if any(len(values) != len(set(values)) for values in identity_fields):
            msg = "Identify registration impact identities must be unique and ordered."
            raise ValueError(msg)
        normalized = set(self.normalized_temporary_line_ids)
        registerable = set(self.registerable_temporary_line_ids)
        rejected = set(self.rejected_temporary_line_ids)
        if registerable & rejected or registerable | rejected != normalized:
            msg = "Identify registration lines must be partitioned by registration outcome."
            raise ValueError(msg)
        if self.created_region_count < 0 or self.created_line_count < 0:
            msg = "Identify registration impact counts cannot be negative."
            raise ValueError(msg)
        if self.created_line_count != len(self.registerable_temporary_line_ids):
            msg = "Identify registration created-line impact must match registerable lines."
            raise ValueError(msg)
        if any(
            not set(group.temporary_line_ids).issubset(registerable)
            for group in self.multiplet_groups
        ):
            msg = "Identify registration multiplet groups must contain registerable lines."
            raise ValueError(msg)
        if self.mutation_outcome is StructureMutationOutcome.NO_CHANGE:
            if (
                self.registerable_temporary_line_ids
                or self.affected_existing_region_ids
                or self.created_region_count
                or self.created_line_count
                or self.affected_model_component_ids
                or self.affected_mask_ids
                or self.multiplet_groups
                or self.multi_overlap_warning
            ):
                msg = "NoChange Identify registration cannot carry scientific impact."
                raise ValueError(msg)
        elif not self.registerable_temporary_line_ids:
            msg = "Changed Identify registration requires a registerable temporary line."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationPlan:
    """Normalized temporary lines, grouping decisions, and their typed impact."""

    normalized_temporary_lines: tuple[TemporaryLineSnapshot, ...]
    registration_requests: tuple[AbsorptionLineRegistrationRequest, ...]
    region_previews: tuple[RegionPreviewSnapshot, ...]
    impact: IdentifyRegistrationImpactPreview

    def __post_init__(self) -> None:
        """Require plan lines to match the normalized impact identities exactly."""
        normalized_ids = tuple(
            temporary_line.temporary_line_id for temporary_line in self.normalized_temporary_lines
        )
        registerable_ids = tuple(
            request.temporary_line_id for request in self.registration_requests
        )
        if normalized_ids != self.impact.normalized_temporary_line_ids:
            msg = "Identify registration plan lines do not match normalized lines."
            raise ValueError(msg)
        if registerable_ids != self.impact.registerable_temporary_line_ids:
            msg = "Identify registration plan lines do not match registerable lines."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class BuildRegionPreviewsRequest:
    """Request for building registration preview groups."""

    temporary_lines: tuple[TemporaryLineSnapshot, ...]
    existing_regions: tuple[ExistingRegionSnapshot, ...]
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance
    unknown_label: str


@dataclass(frozen=True, slots=True)
class BuildRegionPreviewsResult:
    """Result of building registration preview groups."""

    previews: tuple[RegionPreviewSnapshot, ...]


@dataclass(frozen=True, slots=True)
class RegisteredLineReference:
    """Reference linking a temporary line ID to a created absorption line."""

    temporary_line_id: str
    line_id: str


@dataclass(frozen=True, slots=True)
class RegisteredLineState:
    """State of a registered absorption line after region assignment."""

    temporary_line_id: str
    line_id: str
    region_id: str | None


@dataclass(frozen=True, slots=True)
class BuildRegionAssignmentRequest:
    """Request for deriving region assignment operations from previews."""

    previews: tuple[RegionPreviewSnapshot, ...]
    registered_lines: tuple[RegisteredLineReference, ...]


@dataclass(frozen=True, slots=True)
class RegionAssignmentOperation:
    """Region assignment operation to apply through the project adapter."""

    kind: RegionAssignmentOperationKind
    line_ids: tuple[str, ...]
    existing_region_id: str | None = None


@dataclass(frozen=True, slots=True)
class BuildRegionAssignmentResult:
    """Result of deriving region assignment operations."""

    operations: tuple[RegionAssignmentOperation, ...]


@dataclass(frozen=True, slots=True)
class BuildRegistrationOutcomeRequest:
    """Request for deriving registration history and session outcome IDs."""

    existing_region_ids: tuple[str, ...]
    all_region_ids_after: tuple[str, ...]
    registered_lines: tuple[RegisteredLineState, ...]
    failed_temporary_line_ids: tuple[str, ...]
    multi_overlap_warning: bool


@dataclass(frozen=True, slots=True)
class RegistrationOutcome:
    """Typed registration outcome used by GUI adapters and history bridge."""

    created_line_ids: tuple[str, ...]
    created_region_ids: tuple[str, ...]
    processed_temporary_line_ids: tuple[str, ...]
    affected_region_ids: tuple[str, ...]
    appended_region_ids: tuple[str, ...]
    confirmed_count: int
    failed_count: int
    multi_overlap_warning: bool


@dataclass(frozen=True, slots=True)
class AbsorptionLineRegistrationRequest:
    """Request data required to create one absorption line from a temporary line."""

    temporary_line_id: str
    atomic_line_id: str
    species: str
    rest_wavelength: float
    center_z: float
    window_kms: float
    multiplet_label: str
    transition_name: str
    oscillator_strength: float
    gamma_value: float
    lambda_range: tuple[float, float]
    created_by: str


@dataclass(frozen=True, slots=True)
class AbsorptionLineRegistrationResult:
    """Result of preparing an absorption line registration request."""

    request: AbsorptionLineRegistrationRequest | None
    error_code: RegistrationErrorCode | None = None
