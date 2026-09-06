"""Session state helpers for identify mode workflows."""

# ruff: noqa: D102
from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from chappy.core.velocity_ranges import (
    DEFAULT_ANALYSIS_HALF_WIDTH_KMS,
    MAX_ANALYSIS_HALF_WIDTH_KMS,
    MIN_ANALYSIS_HALF_WIDTH_KMS,
    LineAnalysisHalfWidth,
    NewCandidateAnalysisHalfWidth,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = logging.getLogger(__name__)

WorkPhase = Literal["temporary_line_add"]
TemporaryStatus = Literal["pending", "preview", "confirmed"]
RegionStatus = Literal["identified", "candidate", "unused"]

IDENTIFY_TEMPORARY_LINE_LIMIT = 1000
# Identify retains its staged UI vocabulary while sharing the canonical limits.
DEFAULT_VELOCITY_WINDOW_KMS = DEFAULT_ANALYSIS_HALF_WIDTH_KMS
MIN_VELOCITY_WINDOW_KMS = MIN_ANALYSIS_HALF_WIDTH_KMS
MAX_VELOCITY_WINDOW_KMS = MAX_ANALYSIS_HALF_WIDTH_KMS


@dataclass(slots=True)
class DetectedRegion:
    """Snapshot of a detected absorption feature candidate."""

    region_id: str
    lambda_start: float
    lambda_end: float
    lambda_bar: float
    sigma: float
    status: RegionStatus = "candidate"


@dataclass(slots=True)
class TemporaryLineContext:
    """Metadata from AtomicLine used when creating temporary lines.

    All fields are required for scientific reproducibility - values are
    injected from AtomicLine at creation time and stored with the project.
    """

    # Required fields (from AtomicLine)
    line_id: str
    rest_wavelength: float
    multiplet_id: str
    multiplet_label: str
    transition_name: str
    oscillator_strength: float
    gamma_value: float
    tie_group_key: str

    # Optional (can be computed from rest_wavelength and observed wavelength)
    center_z: float | None = None


@dataclass(slots=True)
class TemporaryLine:
    """Working copy of an absorption line prior to grouping.

    Atomic line data fields are required for scientific reproducibility.
    """

    # Required identification fields
    temporary_line_id: str
    species: str
    lambda_min: float
    lambda_max: float
    creation_method: str

    # Required atomic line data (from AtomicLine via context)
    line_id: str
    rest_wavelength: float
    center_z: float
    multiplet_id: str
    multiplet_label: str
    transition_name: str
    oscillator_strength: float
    gamma_value: float
    tie_group_key: str

    # Optional fields
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    analysis_half_width_kms: float = DEFAULT_VELOCITY_WINDOW_KMS
    status: TemporaryStatus = "pending"

    @property
    def center_wavelength(self) -> float:
        """Return mid-point of the wavelength span."""
        return (self.lambda_min + self.lambda_max) / 2.0


@dataclass(slots=True)
class RegionPreview:
    """Grouping result showing how temporary lines will be registered."""

    group_id: str
    name: str
    member_temporary_line_ids: list[str] = field(default_factory=list)
    overlap_warning: bool = False  # True when overlapping multiple existing regions
    color: str | None = None
    existing_group_id: str | None = None  # If set, add to existing group


class IdentifySessionState:
    """In-memory model capturing identify mode working data."""

    def __init__(self) -> None:
        self._temporary_lines: OrderedDict[str, TemporaryLine] = OrderedDict()
        self._detected_regions: dict[str, DetectedRegion] = {}
        self._new_candidate_analysis_half_width = NewCandidateAnalysisHalfWidth(
            DEFAULT_ANALYSIS_HALF_WIDTH_KMS
        )
        self.reference_z: float = 0.0
        self.work_phase: WorkPhase = "temporary_line_add"
        self.last_added_wavelength: float | None = None
        self.last_click_wavelength: float | None = None

    @property
    def temporary_count(self) -> int:
        return len(self._temporary_lines)

    @property
    def temporary_lines(self) -> Sequence[TemporaryLine]:
        return list(self._temporary_lines.values())

    def add_temporary_line(
        self,
        species: str,
        lambda_min: float,
        lambda_max: float,
        *,
        creation_method: str,
        context: TemporaryLineContext,
        analysis_half_width: LineAnalysisHalfWidth | None = None,
    ) -> TemporaryLine:
        """Add a new temporary line with atomic line metadata.

        Args:
            species: Element/ion species (e.g., "C IV").
            lambda_min: Minimum observed wavelength.
            lambda_max: Maximum observed wavelength.
            creation_method: How this line was created.
            context: Required atomic line metadata for reproducibility.
            analysis_half_width: Scientific range copied into the new candidate. Defaults to
                the current future-candidate draft for direct core callers.

        Returns:
            The newly created TemporaryLine.

        Raises:
            ValueError: If line limit is reached.
        """
        if len(self._temporary_lines) >= IDENTIFY_TEMPORARY_LINE_LIMIT:
            msg = "Temporary line limit reached"
            raise ValueError(msg)

        low, high = sorted((lambda_min, lambda_max))

        # Compute center_z from context or from wavelengths
        computed_center = context.center_z
        if computed_center is None and context.rest_wavelength > 0:
            observed = (low + high) / 2.0
            computed_center = (observed / context.rest_wavelength) - 1.0
        # Fallback to 0.0 if computation fails (should not happen with valid data)
        if computed_center is None:
            computed_center = 0.0

        temporary_line_id = uuid4().hex
        line = TemporaryLine(
            temporary_line_id=temporary_line_id,
            species=species,
            lambda_min=low,
            lambda_max=high,
            creation_method=creation_method,
            line_id=context.line_id,
            rest_wavelength=context.rest_wavelength,
            center_z=computed_center,
            multiplet_id=context.multiplet_id,
            multiplet_label=context.multiplet_label,
            tie_group_key=context.tie_group_key,
            transition_name=context.transition_name,
            oscillator_strength=context.oscillator_strength,
            gamma_value=context.gamma_value,
            analysis_half_width_kms=(
                analysis_half_width.kms
                if analysis_half_width is not None
                else self._new_candidate_analysis_half_width.kms
            ),
        )
        self._temporary_lines[temporary_line_id] = line
        self.last_added_wavelength = line.center_wavelength
        return line

    def remove_temporary_lines(self, temporary_line_ids: Iterable[str]) -> list[str]:
        removed: list[str] = []
        for temporary_line_id in temporary_line_ids:
            if temporary_line_id in self._temporary_lines:
                self._temporary_lines.pop(temporary_line_id)
                removed.append(temporary_line_id)
        return removed

    def clear_temporary_lines(self) -> None:
        self._temporary_lines.clear()

    def restore_temporary_line(self, temporary_line: TemporaryLine) -> TemporaryLine:
        """Restore a temporary line from a typed model object.

        Args:
            temporary_line: Temporary line to restore.

        Returns:
            Restored TemporaryLine.
        """
        self._temporary_lines[temporary_line.temporary_line_id] = temporary_line
        return temporary_line

    def snapshot_temporary_lines_for_transaction(self) -> tuple[TemporaryLine, ...]:
        """Capture exact temporary line object identity and order for atomic rollback."""
        return tuple(self._temporary_lines.values())

    def replace_temporary_lines_for_transaction(
        self, temporary_lines: Iterable[TemporaryLine]
    ) -> None:
        """Restore exact temporary line object identity and order without notifications."""
        replacements: OrderedDict[str, TemporaryLine] = OrderedDict()
        for temporary_line in temporary_lines:
            if temporary_line.temporary_line_id in replacements:
                msg = (
                    "Duplicate identify temporary line in transaction snapshot: "
                    f"{temporary_line.temporary_line_id}"
                )
                raise ValueError(msg)
            replacements[temporary_line.temporary_line_id] = temporary_line
        self._temporary_lines = replacements

    @property
    def detected_regions(self) -> Sequence[DetectedRegion]:
        return list(self._detected_regions.values())

    def set_detected_regions(self, regions: Sequence[DetectedRegion]) -> None:
        self._detected_regions = {region.region_id: region for region in regions}

    @property
    def new_candidate_analysis_half_width(self) -> NewCandidateAnalysisHalfWidth:
        """Return the session draft copied only into future candidates."""
        return self._new_candidate_analysis_half_width

    def set_new_candidate_analysis_half_width(self, value: NewCandidateAnalysisHalfWidth) -> None:
        """Replace the future-candidate draft without mutating existing candidates."""
        if not isinstance(value, NewCandidateAnalysisHalfWidth):
            msg = "New candidate analysis half-width must use the validated value type."
            raise TypeError(msg)
        self._new_candidate_analysis_half_width = value


__all__ = [
    "DEFAULT_VELOCITY_WINDOW_KMS",
    "IDENTIFY_TEMPORARY_LINE_LIMIT",
    "DetectedRegion",
    "IdentifySessionState",
    "RegionPreview",
    "TemporaryLine",
    "TemporaryLineContext",
]
