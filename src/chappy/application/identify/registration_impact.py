"""Side-effect-free impact preview for Identify temporary-line registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.core.velocity_ranges import LineAnalysisHalfWidth

from .models import (
    BuildRegionPreviewsRequest,
    ExistingRegionSnapshot,
    IdentifyRegistrationPlan,
    TemporaryLineSnapshot,
)
from .registration_usecase import BuildIdentifyRegistrationPlanUseCase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.identify_state import TemporaryLine
    from chappy.core.velocity_ranges import MultipletGroupingVelocityTolerance


class IdentifyRegistrationImpactProjectPort(Protocol):
    """Read-only project state required for exact registration impact preview."""

    def list_absorption_regions(self) -> list[AbsorptionRegion]:
        """Return current regions in storage order."""
        ...

    def list_absorption_lines(self) -> list[AbsorptionLine]:
        """Return current absorption lines in storage order."""
        ...


class IdentifyRegistrationImpactSessionPort(Protocol):
    """Read-only Identify session state required for exact impact preview."""

    @property
    def temporary_lines(self) -> Sequence[TemporaryLine]:
        """Return current temporary lines in storage order."""
        ...


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationImpactRequest:
    """Exact sources and targets for one side-effect-free registration preview."""

    project: IdentifyRegistrationImpactProjectPort
    session: IdentifyRegistrationImpactSessionPort
    temporary_lines: tuple[TemporaryLineSnapshot, ...]
    existing_regions: tuple[ExistingRegionSnapshot, ...]
    region_line_memberships: tuple[tuple[str, tuple[str, ...]], ...]
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance
    unknown_label: str


class IdentifyRegistrationImpactPreviewUseCase:
    """Validate live sources and return their immutable normalized registration plan."""

    def __init__(self, planner: BuildIdentifyRegistrationPlanUseCase | None = None) -> None:
        """Initialize the preview with its pure planner."""
        self._planner = planner or BuildIdentifyRegistrationPlanUseCase()

    def preview(self, request: IdentifyRegistrationImpactRequest) -> IdentifyRegistrationPlan:
        """Return an exact plan without changing project, session, history, or revisions."""
        self._require_exact_sources(request)
        self._require_exact_region_targets(request)
        return self._planner.build(
            BuildRegionPreviewsRequest(
                temporary_lines=request.temporary_lines,
                existing_regions=request.existing_regions,
                multiplet_grouping_tolerance=request.multiplet_grouping_tolerance,
                unknown_label=request.unknown_label,
            )
        )

    @staticmethod
    def _require_exact_sources(request: IdentifyRegistrationImpactRequest) -> None:
        """Require unique requested lines to equal current session objects."""
        requested_ids = tuple(
            temporary_line.temporary_line_id for temporary_line in request.temporary_lines
        )
        if len(set(requested_ids)) != len(requested_ids):
            msg = "Identify registration temporary-line identities must be unique."
            raise ValueError(msg)

        session_temporary_lines = {
            temporary_line.temporary_line_id: _temporary_line_snapshot(temporary_line)
            for temporary_line in request.session.temporary_lines
        }
        for temporary_line in request.temporary_lines:
            current = session_temporary_lines.get(temporary_line.temporary_line_id)
            if current is None:
                msg = f"Identify registration temporary line is no longer present: {temporary_line.temporary_line_id}"
                raise ValueError(msg)
            if current != temporary_line:
                msg = f"Identify registration temporary-line source is stale: {temporary_line.temporary_line_id}"
                raise ValueError(msg)

    @staticmethod
    def _require_exact_region_targets(request: IdentifyRegistrationImpactRequest) -> None:
        """Require preview region membership and ranges to match current project storage."""
        snapshots = request.existing_regions
        snapshot_ids = tuple(snapshot.region_id for snapshot in snapshots)
        if len(set(snapshot_ids)) != len(snapshot_ids):
            msg = "Identify registration region snapshot identities must be unique."
            raise ValueError(msg)

        current_regions = request.project.list_absorption_regions()
        current_ids = tuple(region.region_id for region in current_regions)
        if snapshot_ids != current_ids:
            msg = "Identify registration region targets are stale."
            raise ValueError(msg)
        current_memberships = tuple(
            (region.region_id, tuple(region.line_ids)) for region in current_regions
        )
        if request.region_line_memberships != current_memberships:
            msg = "Identify registration region membership targets are stale."
            raise ValueError(msg)

        current_lines = request.project.list_absorption_lines()
        expected_ranges = {
            region.region_id: tuple(
                line.lambda_range
                for line in current_lines
                if line.region_id == region.region_id and line.lambda_range is not None
            )
            for region in current_regions
        }
        for snapshot in snapshots:
            if snapshot.line_ranges != expected_ranges[snapshot.region_id]:
                msg = f"Identify registration region target is stale: {snapshot.region_id}"
                raise ValueError(msg)


def _temporary_line_snapshot(temporary_line: TemporaryLine) -> TemporaryLineSnapshot:
    """Convert one live session temporary line into its exact scientific DTO."""
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


__all__ = [
    "IdentifyRegistrationImpactPreviewUseCase",
    "IdentifyRegistrationImpactProjectPort",
    "IdentifyRegistrationImpactRequest",
    "IdentifyRegistrationImpactSessionPort",
]
