"""Pure values describing project-owned analysis state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chappy.core.components.optimize import FitOutcome


@dataclass(frozen=True, order=True, slots=True)
class AnalysisRevision:
    """Non-negative revision of one absorption region's analysis inputs."""

    value: int = 0

    def __post_init__(self) -> None:
        """Reject values that cannot represent a region revision."""
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            msg = "Analysis revision must be an integer."
            raise TypeError(msg)
        if self.value < 0:
            msg = "Analysis revision must be non-negative."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class FitSummary:
    """Numerical evidence produced by one successful optimization."""

    chi_squared: float | None = None
    reduced_chi_squared: float | None = None
    degrees_of_freedom: float | None = None
    n_parameters: int | None = None
    n_function_evaluations: int | None = None
    outcome: FitOutcome | None = None


@dataclass(frozen=True, slots=True)
class AnalysisArtifact:
    """Fit evidence produced from one region revision."""

    region_id: str
    source_revision: AnalysisRevision
    fit_summary: FitSummary

    def __post_init__(self) -> None:
        """Reject an artifact without a region identity."""
        if not self.region_id:
            msg = "Analysis artifact region ID must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RegionAnalysisState:
    """Project-owned analysis state for one absorption region."""

    region_id: str
    current_revision: AnalysisRevision
    artifact: AnalysisArtifact | None = None

    def __post_init__(self) -> None:
        """Require the optional artifact to belong to this region."""
        if not self.region_id:
            msg = "Region analysis state ID must not be empty."
            raise ValueError(msg)
        if self.artifact is not None and self.artifact.region_id != self.region_id:
            msg = "Analysis artifact must belong to its region analysis state."
            raise ValueError(msg)


class AnalysisReadiness(StrEnum):
    """Exclusive readiness derived from project and artifact facts."""

    NOT_ANALYZED = "not_analyzed"
    STALE = "stale"
    LATEST = "latest"

    @property
    def exportable(self) -> bool:
        """Return whether this readiness permits analysis export."""
        return self is AnalysisReadiness.LATEST
