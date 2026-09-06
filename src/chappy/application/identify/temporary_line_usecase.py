"""Use cases for identify temporary-line preview and creation."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol

from chappy.application.identify.group_labels import declarative_group_label
from chappy.application.identify.models import (
    AtomicLineSnapshot,
    CreatedTemporaryLine,
    PreviewEntryModel,
    TemporaryLineCreationEntry,
    TemporaryLineCreationResult,
    TemporaryLineSnapshot,
    VelocityPreview,
    VelocityTemporaryLineRequest,
)
from chappy.core.constants import LIGHT_SPEED_KMS

if TYPE_CHECKING:
    from collections.abc import Sequence


class TemporaryLineCreationSessionPort(Protocol):
    """Minimal mutation port required for identify temporary-line creation."""

    @property
    def temporary_line_snapshots(self) -> Sequence[TemporaryLineSnapshot]:
        """Return immutable current temporary line snapshots."""

    def add_temporary_line_creation_entry(self, creation_entry: TemporaryLineCreationEntry) -> str:
        """Add one temporary line and return its line ID."""


class TemporaryLineCreationLimitReachedError(ValueError):
    """Raised when the session temporary-line limit is reached."""


_LIMIT_REACHED_ERROR_MESSAGE = "Temporary line limit reached"


def _is_limit_reached_error(error: ValueError) -> bool:
    """Return True when an error indicates the temporary-line limit was reached."""
    return str(error) == _LIMIT_REACHED_ERROR_MESSAGE


def _add_temporary_line_entry(
    session: TemporaryLineCreationSessionPort, creation_entry: TemporaryLineCreationEntry
) -> str:
    """Call the mutation port and normalize limit errors for boundary typing."""
    try:
        return session.add_temporary_line_creation_entry(creation_entry)
    except ValueError as error:
        if _is_limit_reached_error(error):
            raise TemporaryLineCreationLimitReachedError(_LIMIT_REACHED_ERROR_MESSAGE) from error
        raise


class BuildVelocityPreviewUseCase:
    """Build identify velocity preview entries without mutating session state."""

    def build(self, request: VelocityTemporaryLineRequest) -> VelocityPreview:
        """Build cursor preview entries for a velocity temporary-line request.

        Args:
            request: Temporary-line request containing cursor, baseline, preset lines, and bounds.

        Returns:
            Velocity preview with sorted entries.
        """
        baseline_rest = request.baseline_line.wavelength_angstrom
        if baseline_rest <= 0:
            msg = f"Baseline rest wavelength must be positive: {baseline_rest}"
            raise ValueError(msg)

        redshift = (request.observed_wavelength / baseline_rest) - 1.0
        entries = build_preview_entries(
            lines=request.preset_lines,
            baseline_line=request.baseline_line,
            redshift=redshift,
            analysis_half_width_kms=request.new_candidate_analysis_half_width.kms,
            include_all_preview_lines=request.include_all_preview_lines,
            data_bounds=request.data_bounds,
        )
        return VelocityPreview(entries=entries, redshift=redshift)


class CreateTemporaryLineFromVelocityUseCase:
    """Create identify temporary lines through a minimal session mutation port."""

    def create(
        self,
        session: TemporaryLineCreationSessionPort,
        entries: tuple[TemporaryLineCreationEntry, ...],
    ) -> TemporaryLineCreationResult:
        """Create temporary lines from prepared entries.

        Args:
            session: Minimal session mutation port.
            entries: Temporary-line creation entries.

        Returns:
            Creation result with created IDs and duplicate/limit status.
        """
        created: list[CreatedTemporaryLine] = []
        duplicate_count = 0
        limit_reached = False

        for creation_entry in entries:
            entry = creation_entry.preview_entry
            if _is_duplicate_temporary_line(
                session.temporary_line_snapshots, entry.line_id, entry.lambda_min, entry.lambda_max
            ):
                duplicate_count += 1
                continue

            try:
                temporary_line_id = _add_temporary_line_entry(session, creation_entry)
            except TemporaryLineCreationLimitReachedError:
                limit_reached = True
                break

            created.append(CreatedTemporaryLine(temporary_line_id=temporary_line_id, entry=entry))

        return TemporaryLineCreationResult(
            created=tuple(created), duplicate_count=duplicate_count, limit_reached=limit_reached
        )


def build_preview_entries(
    *,
    lines: tuple[AtomicLineSnapshot, ...],
    baseline_line: AtomicLineSnapshot,
    redshift: float,
    analysis_half_width_kms: float,
    include_all_preview_lines: bool,
    data_bounds: tuple[float, float] | None,
) -> tuple[PreviewEntryModel, ...]:
    """Build typed preview entries from atomic line snapshots.

    Args:
        lines: Preset atomic line snapshots.
        baseline_line: Baseline atomic line.
        redshift: Reference redshift.
        analysis_half_width_kms: New-candidate analysis half-width in km/s.
        include_all_preview_lines: Whether to include all preset lines.
        data_bounds: Optional observed wavelength bounds.

    Returns:
        Sorted preview entries.
    """
    if analysis_half_width_kms <= 0:
        return ()

    baseline_tie_group_key = baseline_line.tie_group_key
    baseline_observed = baseline_line.wavelength_angstrom * (1.0 + redshift)
    entries: list[PreviewEntryModel] = []

    for line in lines:
        is_primary = line.line_id == baseline_line.line_id
        same_tie_group = bool(
            baseline_tie_group_key and line.tie_group_key == baseline_tie_group_key
        )

        if not (is_primary or same_tie_group or include_all_preview_lines):
            continue

        observed = line.wavelength_angstrom * (1.0 + redshift)
        if not math.isfinite(observed) or observed <= 0:
            continue

        delta = abs(observed) * (analysis_half_width_kms / LIGHT_SPEED_KMS)
        if not math.isfinite(delta) or delta <= 0:
            continue

        clipped_min = observed - delta
        clipped_max = observed + delta

        if data_bounds is not None:
            data_min, data_max = data_bounds
            if clipped_max < data_min or clipped_min > data_max:
                continue

            clipped_min = max(clipped_min, data_min)
            clipped_max = min(clipped_max, data_max)

            if clipped_max <= clipped_min:
                continue

        display_center = observed
        if data_bounds is not None and math.isfinite(display_center):
            display_center = min(max(display_center, clipped_min), clipped_max)

        label_text = line.transition_name.strip() or _short_label(line, primary=is_primary)
        entries.append(
            PreviewEntryModel(
                line_id=line.line_id,
                lambda_min=clipped_min,
                lambda_max=clipped_max,
                center=display_center,
                label=label_text,
                original_label=label_text,
                transition_name=line.transition_name.strip(),
                color="#0066CC" if is_primary else "#5dade2",
                is_primary=is_primary,
                fill_alpha=0.12 if is_primary else 0.06,
                line_alpha=0.95 if is_primary else 0.65,
                line_width=1.4 if is_primary else 1.0,
                line_style="-." if is_primary else "--",
                multiplet_id=line.multiplet_id,
                multiplet_label=declarative_group_label(
                    multiplet_label=line.multiplet_label,
                    species=line.species,
                    tie_group_key=line.tie_group_key,
                ),
                species=line.species,
                rest_wavelength=line.wavelength_angstrom,
                oscillator_strength=line.oscillator_strength,
                gamma_value=line.gamma_value,
                delta_velocity=_compute_delta_velocity(baseline_observed, observed),
                tie_group_key=line.tie_group_key,
            )
        )

    if not entries:
        return ()

    labelled_entries = _assign_preview_labels(tuple(entries), analysis_half_width_kms)
    return tuple(sorted(labelled_entries, key=lambda item: item.center))


def _assign_preview_labels(
    entries: tuple[PreviewEntryModel, ...], analysis_half_width_kms: float
) -> tuple[PreviewEntryModel, ...]:
    """Limit labelled preview entries to avoid overlap and honour priority.

    Args:
        entries: Preview entries.
        analysis_half_width_kms: New-candidate analysis half-width in km/s.

    Returns:
        Entries with labels suppressed where needed.
    """
    max_labels = 8
    spacing_velocity = max(analysis_half_width_kms * 0.08, 5.0)

    primary_line_id = ""
    baseline_tie_group_key = ""
    for entry in entries:
        if entry.is_primary:
            primary_line_id = entry.line_id
            baseline_tie_group_key = entry.tie_group_key
            break

    ordered = sorted(
        entries,
        key=lambda item: (
            not item.is_primary,
            item.delta_velocity if item.delta_velocity is not None else float("inf"),
        ),
    )

    labelled_ids: set[str] = set()
    labelled_velocities: list[float] = []

    for entry in ordered:
        if not entry.line_id:
            continue

        delta_velocity = entry.delta_velocity
        if delta_velocity is None:
            delta_velocity = float("inf")

        if entry.is_primary:
            labelled_ids.add(entry.line_id)
            labelled_velocities.append(delta_velocity)
            continue

        if len(labelled_ids) >= max_labels:
            continue

        too_close = any(
            abs(delta_velocity - existing) < spacing_velocity for existing in labelled_velocities
        )
        if too_close:
            continue

        labelled_ids.add(entry.line_id)
        labelled_velocities.append(delta_velocity)

    protected_ids: set[str] = set()
    if primary_line_id:
        labelled_ids.add(primary_line_id)
        protected_ids.add(primary_line_id)
    if baseline_tie_group_key:
        for entry in entries:
            if entry.tie_group_key == baseline_tie_group_key:
                labelled_ids.add(entry.line_id)
                protected_ids.add(entry.line_id)
                delta_velocity = entry.delta_velocity
                if (
                    delta_velocity is not None
                    and delta_velocity not in labelled_velocities
                    and not math.isinf(delta_velocity)
                ):
                    labelled_velocities.append(delta_velocity)

    updated: list[PreviewEntryModel] = []
    for entry in entries:
        if entry.line_id and entry.line_id not in labelled_ids:
            updated.append(_replace_label(entry, ""))
        elif entry.line_id in protected_ids and entry.original_label:
            updated.append(_replace_label(entry, entry.original_label))
        else:
            updated.append(entry)
    return tuple(updated)


def _replace_label(entry: PreviewEntryModel, label: str) -> PreviewEntryModel:
    """Return a preview entry with a changed label.

    Args:
        entry: Source entry.
        label: Replacement label.

    Returns:
        New entry with the requested label.
    """
    return PreviewEntryModel(
        line_id=entry.line_id,
        lambda_min=entry.lambda_min,
        lambda_max=entry.lambda_max,
        center=entry.center,
        label=label,
        original_label=entry.original_label,
        transition_name=entry.transition_name,
        color=entry.color,
        is_primary=entry.is_primary,
        fill_alpha=entry.fill_alpha,
        line_alpha=entry.line_alpha,
        line_width=entry.line_width,
        line_style=entry.line_style,
        multiplet_id=entry.multiplet_id,
        multiplet_label=entry.multiplet_label,
        species=entry.species,
        rest_wavelength=entry.rest_wavelength,
        oscillator_strength=entry.oscillator_strength,
        gamma_value=entry.gamma_value,
        delta_velocity=entry.delta_velocity,
        tie_group_key=entry.tie_group_key,
    )


def _compute_delta_velocity(baseline_observed: float, observed: float) -> float:
    """Return absolute velocity offset relative to baseline observed wavelength.

    Args:
        baseline_observed: Observed wavelength of the baseline line.
        observed: Observed wavelength of the compared line.

    Returns:
        Absolute velocity offset in km/s, or infinity when invalid.
    """
    if baseline_observed <= 0 or not math.isfinite(baseline_observed):
        return float("inf")
    if not math.isfinite(observed) or observed <= 0:
        return float("inf")
    return abs(((observed / baseline_observed) - 1.0) * LIGHT_SPEED_KMS)


def _is_duplicate_temporary_line(
    temporary_lines: Sequence[TemporaryLineSnapshot],
    line_id: str | None,
    lambda_min: float,
    lambda_max: float,
) -> bool:
    """Check whether a temporary line with the same line and range exists.

    Args:
        temporary_lines: Current temporary lines.
        line_id: Temporary-line atomic line ID.
        lambda_min: Temporary-line lower wavelength.
        lambda_max: Temporary-line upper wavelength.

    Returns:
        True when an equivalent temporary line exists.
    """
    tolerance = 1e-3
    for temporary_line in temporary_lines:
        if line_id and temporary_line.line_id and temporary_line.line_id != line_id:
            continue
        if line_id and not temporary_line.line_id:
            continue
        if not line_id and temporary_line.line_id:
            continue
        if math.isclose(
            temporary_line.lambda_min, lambda_min, rel_tol=0.0, abs_tol=tolerance
        ) and math.isclose(temporary_line.lambda_max, lambda_max, rel_tol=0.0, abs_tol=tolerance):
            return True
    return False


def _short_label(line: AtomicLineSnapshot, *, primary: bool) -> str:
    """Return compact display label for an atomic line.

    Args:
        line: Atomic line snapshot.
        primary: Whether the line is the baseline line.

    Returns:
        Short display label.
    """
    transition = line.transition_name.strip()
    if transition:
        return transition

    species = line.species.strip()
    if species and primary:
        return f"{species} {line.wavelength_angstrom:.1f}"
    if species:
        return species
    return f"{line.wavelength_angstrom:.1f}"
