"""Adapters between identify GUI workflows and application DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from chappy.application.identify import (
    AtomicLineSnapshot,
    BuildVelocityPreviewUseCase,
    DetectedRegionSnapshot,
    PreviewEntryModel,
    RegionPreviewSnapshot,
    TemporaryLineSnapshot,
    VelocityPreview,
    VelocityTemporaryLineRequest,
)
from chappy.core.identify_state import DetectedRegion, RegionPreview
from chappy.core.velocity_ranges import LineAnalysisHalfWidth
from chappy.presentation.identify import PreviewEntry, preview_entry_to_plot_payload

if TYPE_CHECKING:
    from collections.abc import Mapping

    from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth


class IdentifyAtomicLinePort(Protocol):
    """Atomic line fields required by identify application use cases."""

    @property
    def line_id(self) -> str:
        """Return the persistent line identifier."""
        ...

    @property
    def species(self) -> str:
        """Return the species label."""
        ...

    @property
    def wavelength_angstrom(self) -> float:
        """Return the rest wavelength in angstroms."""
        ...

    @property
    def oscillator_strength(self) -> float:
        """Return the oscillator strength."""
        ...

    @property
    def gamma_value(self) -> float:
        """Return the damping gamma value."""
        ...

    @property
    def multiplet_id(self) -> str:
        """Return the multiplet identifier."""
        ...

    @property
    def multiplet_label(self) -> str:
        """Return the multiplet display label."""
        ...

    @property
    def transition_name(self) -> str:
        """Return the transition name."""
        ...


class TemporaryLinePort(Protocol):
    """Temporary line fields required by identify registration use cases."""

    @property
    def temporary_line_id(self) -> str:
        """Return the temporary line identifier."""
        ...

    @property
    def species(self) -> str:
        """Return the species label."""
        ...

    @property
    def lambda_min(self) -> float:
        """Return the lower wavelength bound."""
        ...

    @property
    def lambda_max(self) -> float:
        """Return the upper wavelength bound."""
        ...

    @property
    def creation_method(self) -> str:
        """Return the temporary-line creation method."""
        ...

    @property
    def line_id(self) -> str:
        """Return the atomic line identifier."""
        ...

    @property
    def rest_wavelength(self) -> float:
        """Return the rest wavelength."""
        ...

    @property
    def center_z(self) -> float:
        """Return the temporary-line redshift."""
        ...

    @property
    def multiplet_id(self) -> str:
        """Return the multiplet identifier."""
        ...

    @property
    def multiplet_label(self) -> str:
        """Return the multiplet display label."""
        ...

    @property
    def tie_group_key(self) -> str:
        """Return the transient declarative tie-group key."""
        ...

    @property
    def transition_name(self) -> str:
        """Return the transition name."""
        ...

    @property
    def oscillator_strength(self) -> float:
        """Return the oscillator strength."""
        ...

    @property
    def gamma_value(self) -> float:
        """Return the damping gamma value."""
        ...

    @property
    def analysis_half_width_kms(self) -> float:
        """Return the temporary-line analysis half-width."""
        ...


class VelocityPreviewBuilderPort(Protocol):
    """Build velocity preview entries from immutable application snapshots."""

    def build_preview(
        self,
        *,
        observed_wavelength: float,
        baseline_line: AtomicLineSnapshot,
        preset_lines: tuple[AtomicLineSnapshot, ...],
        new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth,
        include_all_preview_lines: bool,
        data_bounds: tuple[float, float] | None,
    ) -> VelocityPreview:
        """Build a velocity preview."""
        ...


class VelocityPreviewAdapter:
    """Convert identify preview requests into application preview results."""

    def __init__(self, usecase: BuildVelocityPreviewUseCase) -> None:
        """Initialize the adapter.

        Args:
            usecase: Velocity preview use case.
        """
        self._usecase = usecase

    def build_preview(
        self,
        *,
        observed_wavelength: float,
        baseline_line: AtomicLineSnapshot,
        preset_lines: tuple[AtomicLineSnapshot, ...],
        new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth,
        include_all_preview_lines: bool,
        data_bounds: tuple[float, float] | None,
    ) -> VelocityPreview:
        """Build a velocity preview.

        Args:
            observed_wavelength: Observed wavelength.
            baseline_line: Baseline line snapshot.
            preset_lines: Preset line snapshots.
            new_candidate_analysis_half_width: Analysis half-width for future candidates.
            include_all_preview_lines: Whether to include all preview lines.
            data_bounds: Optional wavelength bounds.

        Returns:
            Velocity preview result.
        """
        return self._usecase.build(
            VelocityTemporaryLineRequest(
                observed_wavelength=observed_wavelength,
                baseline_line=baseline_line,
                preset_lines=preset_lines,
                new_candidate_analysis_half_width=new_candidate_analysis_half_width,
                include_all_preview_lines=include_all_preview_lines,
                data_bounds=data_bounds,
            )
        )


def atomic_line_to_snapshot(
    line: IdentifyAtomicLinePort, *, tie_group_key: str
) -> AtomicLineSnapshot:
    """Convert an atomic line boundary to an application snapshot.

    Args:
        line: Atomic line boundary.
        tie_group_key: Transient declarative tie-group key, or an empty string.

    Returns:
        Immutable atomic line snapshot for application use cases.
    """
    return AtomicLineSnapshot(
        line_id=line.line_id,
        species=line.species,
        wavelength_angstrom=line.wavelength_angstrom,
        oscillator_strength=line.oscillator_strength,
        gamma_value=line.gamma_value,
        multiplet_id=line.multiplet_id,
        multiplet_label=line.multiplet_label,
        transition_name=line.transition_name,
        tie_group_key=tie_group_key,
    )


def build_cursor_preview_entries(  # noqa: PLR0913
    *,
    preview_builder: VelocityPreviewBuilderPort,
    lines: tuple[IdentifyAtomicLinePort, ...],
    baseline_line: IdentifyAtomicLinePort,
    redshift: float,
    new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth,
    shift_pressed: bool,
    tie_group_keys: Mapping[str, str],
    data_bounds: tuple[float, float] | None = None,
    for_preview: bool = True,
) -> list[PreviewEntry]:
    """Build plot payload entries for identify cursor preview.

    Args:
        preview_builder: Boundary that builds application preview models.
        lines: Active preset lines.
        baseline_line: Baseline line for redshift conversion.
        redshift: Preview redshift.
        new_candidate_analysis_half_width: Analysis half-width for future candidates.
        shift_pressed: Whether the preview request includes all lines.
        tie_group_keys: Mapping from line ID to transient tie-group key.
        data_bounds: Optional wavelength bounds.
        for_preview: Whether this request is for visual preview.

    Returns:
        Plot preview entries.
    """
    observed_wavelength = baseline_line.wavelength_angstrom * (1.0 + redshift)
    include_all = shift_pressed if for_preview else False
    preview = preview_builder.build_preview(
        observed_wavelength=observed_wavelength,
        baseline_line=atomic_line_to_snapshot(
            baseline_line, tie_group_key=tie_group_keys.get(baseline_line.line_id, "")
        ),
        preset_lines=tuple(
            atomic_line_to_snapshot(line, tie_group_key=tie_group_keys.get(line.line_id, ""))
            for line in lines
        ),
        new_candidate_analysis_half_width=new_candidate_analysis_half_width,
        include_all_preview_lines=include_all,
        data_bounds=data_bounds,
    )
    return [preview_entry_to_plot_payload(entry) for entry in preview.entries]


def preview_entry_to_model(entry: PreviewEntry) -> PreviewEntryModel:
    """Convert a plot preview entry to an application model.

    Args:
        entry: Plot preview entry.

    Returns:
        Typed preview entry model.
    """
    return PreviewEntryModel(
        line_id=entry["line_id"],
        lambda_min=entry["lambda_min"],
        lambda_max=entry["lambda_max"],
        center=entry["center"],
        label=entry["label"],
        original_label=entry["original_label"],
        transition_name=entry["transition_name"],
        color=entry["color"],
        is_primary=entry["is_primary"],
        fill_alpha=entry["fill_alpha"],
        line_alpha=entry["line_alpha"],
        line_width=entry["line_width"],
        line_style=entry["line_style"],
        multiplet_id=entry["multiplet_id"],
        multiplet_label=entry["multiplet_label"],
        species=entry["species"],
        rest_wavelength=entry["rest_wavelength"],
        oscillator_strength=entry["oscillator_strength"],
        gamma_value=entry["gamma_value"],
        delta_velocity=entry["delta_velocity"],
        tie_group_key=entry["tie_group_key"],
    )


def temporary_line_to_snapshot(temporary_line: TemporaryLinePort) -> TemporaryLineSnapshot:
    """Convert a temporary line boundary to an application snapshot.

    Args:
        temporary_line: Temporary line boundary.

    Returns:
        Immutable application temporary-line snapshot.
    """
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
        tie_group_key=temporary_line.tie_group_key,
        transition_name=temporary_line.transition_name,
        oscillator_strength=temporary_line.oscillator_strength,
        gamma_value=temporary_line.gamma_value,
        analysis_half_width=LineAnalysisHalfWidth(temporary_line.analysis_half_width_kms),
    )


def detected_region_from_snapshot(region: DetectedRegionSnapshot) -> DetectedRegion:
    """Convert an application detection snapshot to a core detected region.

    Args:
        region: Immutable application detection snapshot.

    Returns:
        Mutable core detected region for identify session state.
    """
    return DetectedRegion(
        region_id=region.region_id,
        lambda_start=region.lambda_start,
        lambda_end=region.lambda_end,
        lambda_bar=region.lambda_bar,
        sigma=region.sigma,
        status=region.status,
    )


def region_preview_from_snapshot(preview: RegionPreviewSnapshot) -> RegionPreview:
    """Convert an application preview snapshot to a core preview.

    Args:
        preview: Immutable application preview snapshot.

    Returns:
        Mutable core preview for identify session state.
    """
    return RegionPreview(
        group_id=preview.group_id,
        name=preview.name,
        member_temporary_line_ids=list(preview.member_temporary_line_ids),
        overlap_warning=preview.overlap_warning,
        color=preview.color,
        existing_group_id=preview.existing_group_id,
    )
