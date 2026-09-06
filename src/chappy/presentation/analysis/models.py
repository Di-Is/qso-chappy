"""Qt-free display models for the Analysis review table."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from chappy.core.analysis import AnalysisReadiness

if TYPE_CHECKING:
    from chappy.core.analysis import FitSummary


class AnalysisFitResultKind(StrEnum):
    """Mutually exclusive presentation state for the fit-result column."""

    NOT_ANALYZED = "not_analyzed"
    STALE = "stale"
    NUMERICAL = "numerical"


class AnalysisNextAction(StrEnum):
    """Semantic action displayed in the final review-table column."""

    ANALYZE = "analyze"
    REANALYZE = "reanalyze"
    OPEN_REGION = "open_region"


@dataclass(frozen=True, slots=True)
class AnalysisRegionDisplay:
    """Stable identity and untranslated display label for one region."""

    region_id: str
    label: str

    def __post_init__(self) -> None:
        """Reject rows that cannot provide a stable model role."""
        if not self.region_id:
            msg = "Analysis review region ID must not be empty."
            raise ValueError(msg)
        if not self.label:
            msg = "Analysis review region label must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AnalysisFitResultDisplay:
    """Typed fit-result payload that never exposes stale numerical evidence."""

    kind: AnalysisFitResultKind
    summary: FitSummary | None = None

    def __post_init__(self) -> None:
        """Keep numerical evidence exclusive to the numerical state."""
        has_summary = self.summary is not None
        if has_summary is not (self.kind is AnalysisFitResultKind.NUMERICAL):
            msg = "Only a numerical fit result may carry a fit summary."
            raise ValueError(msg)
        if self.summary is not None and not _fit_summary_has_evidence(self.summary):
            msg = "A numerical fit result requires at least one summary value."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AnalysisReviewRow:
    """Typed display DTO for the Overview review table columns."""

    region: AnalysisRegionDisplay
    analysis_status: AnalysisReadiness
    fit_result: AnalysisFitResultDisplay
    next_action: AnalysisNextAction

    def __post_init__(self) -> None:
        """Reject column combinations that contradict exclusive readiness."""
        expected_actions = {
            AnalysisReadiness.NOT_ANALYZED: AnalysisNextAction.ANALYZE,
            AnalysisReadiness.STALE: AnalysisNextAction.REANALYZE,
            AnalysisReadiness.LATEST: AnalysisNextAction.OPEN_REGION,
        }
        if self.next_action is not expected_actions[self.analysis_status]:
            msg = "Analysis next action must match readiness."
            raise ValueError(msg)

        expected_fit_kinds = {
            AnalysisReadiness.NOT_ANALYZED: AnalysisFitResultKind.NOT_ANALYZED,
            AnalysisReadiness.STALE: AnalysisFitResultKind.STALE,
            AnalysisReadiness.LATEST: AnalysisFitResultKind.NUMERICAL,
        }
        if self.fit_result.kind is not expected_fit_kinds[self.analysis_status]:
            msg = "Analysis fit-result display must match readiness."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AnalysisReviewSummary:
    """Counts displayed by the Overview summary panel."""

    total: int
    not_analyzed: int
    stale: int
    latest: int

    def __post_init__(self) -> None:
        """Require counts to describe one complete row collection."""
        counts = (self.total, self.not_analyzed, self.stale, self.latest)
        if any(count < 0 for count in counts):
            msg = "Analysis review summary counts must be non-negative."
            raise ValueError(msg)
        if self.not_analyzed + self.stale + self.latest != self.total:
            msg = "Analysis readiness counts must add up to the total."
            raise ValueError(msg)


def _fit_summary_has_evidence(summary: FitSummary) -> bool:
    """Return whether a fit summary contains at least one measured value."""
    return any(
        value is not None
        for value in (
            summary.chi_squared,
            summary.reduced_chi_squared,
            summary.degrees_of_freedom,
            summary.n_parameters,
            summary.n_function_evaluations,
        )
    )


__all__ = [
    "AnalysisFitResultDisplay",
    "AnalysisFitResultKind",
    "AnalysisNextAction",
    "AnalysisRegionDisplay",
    "AnalysisReviewRow",
    "AnalysisReviewSummary",
]
