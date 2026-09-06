"""Pure construction logic for Analysis review display models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.core.analysis import AnalysisReadiness
from chappy.presentation.analysis.models import (
    AnalysisFitResultDisplay,
    AnalysisFitResultKind,
    AnalysisNextAction,
    AnalysisRegionDisplay,
    AnalysisReviewRow,
    AnalysisReviewSummary,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from chappy.core.analysis import RegionAnalysisState


@dataclass(frozen=True, slots=True)
class AnalysisReviewFacts:
    """Authoritative core facts required to construct one review row."""

    region_id: str
    region_label: str
    readiness: AnalysisReadiness
    analysis_state: RegionAnalysisState | None
    requires_reanalysis: bool
    line_ids: tuple[str, ...]
    missing_line_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject contradictory facts before they reach a GUI model."""
        if not self.region_id:
            msg = "Analysis review facts require a region ID."
            raise ValueError(msg)
        if self.analysis_state is not None and self.analysis_state.region_id != self.region_id:
            msg = "Analysis review state must belong to the displayed region."
            raise ValueError(msg)
        if len(set(self.line_ids)) != len(self.line_ids):
            msg = "Analysis review line IDs must be unique."
            raise ValueError(msg)
        if any(not line_id for line_id in self.line_ids):
            msg = "Analysis review line IDs must not be empty."
            raise ValueError(msg)
        if len(set(self.missing_line_ids)) != len(self.missing_line_ids):
            msg = "Missing analysis line IDs must be unique."
            raise ValueError(msg)
        if not set(self.missing_line_ids).issubset(self.line_ids):
            msg = "Missing line IDs must be references owned by the region."
            raise ValueError(msg)
        self._validate_readiness_contract()

    def _validate_readiness_contract(self) -> None:
        """Validate facts guaranteed by the P1 exclusive readiness contract."""
        if not self.line_ids or self.missing_line_ids:
            msg = "Analysis readiness requires complete region line topology."
            raise ValueError(msg)
        state = self.analysis_state
        if state is None:
            msg = "Analysis readiness requires region analysis state."
            raise ValueError(msg)
        artifact = state.artifact
        if self.readiness is AnalysisReadiness.NOT_ANALYZED:
            if artifact is not None:
                msg = "Not-analyzed readiness must not have an artifact."
                raise ValueError(msg)
            return
        if artifact is None:
            msg = "Stale or latest readiness requires an artifact."
            raise ValueError(msg)
        is_stale = self.requires_reanalysis or artifact.source_revision != state.current_revision
        if (self.readiness is AnalysisReadiness.STALE) is not is_stale:
            msg = "Readiness does not match revision and reanalysis facts."
            raise ValueError(msg)


class AnalysisReviewPresenter:
    """Build review rows and aggregate counts without Qt or translation."""

    def build_row(self, facts: AnalysisReviewFacts) -> AnalysisReviewRow:
        """Build all baseline columns from authoritative facts."""
        return AnalysisReviewRow(
            region=AnalysisRegionDisplay(facts.region_id, facts.region_label),
            analysis_status=facts.readiness,
            fit_result=self._fit_result(facts),
            next_action=self._next_action(facts),
        )

    def build_summary(self, rows: Iterable[AnalysisReviewRow]) -> AnalysisReviewSummary:
        """Count exclusive readiness states for an Overview."""
        materialized = tuple(rows)
        readiness_counts = {
            readiness: sum(row.analysis_status is readiness for row in materialized)
            for readiness in AnalysisReadiness
        }
        return AnalysisReviewSummary(
            total=len(materialized),
            not_analyzed=readiness_counts[AnalysisReadiness.NOT_ANALYZED],
            stale=readiness_counts[AnalysisReadiness.STALE],
            latest=readiness_counts[AnalysisReadiness.LATEST],
        )

    @staticmethod
    def _fit_result(facts: AnalysisReviewFacts) -> AnalysisFitResultDisplay:
        readiness = facts.readiness
        if readiness is AnalysisReadiness.NOT_ANALYZED:
            return AnalysisFitResultDisplay(AnalysisFitResultKind.NOT_ANALYZED)
        if readiness is AnalysisReadiness.STALE:
            return AnalysisFitResultDisplay(AnalysisFitResultKind.STALE)

        state = facts.analysis_state
        if state is None or state.artifact is None:  # guarded by facts validation
            msg = "Latest analysis facts must include an artifact."
            raise RuntimeError(msg)
        return AnalysisFitResultDisplay(
            AnalysisFitResultKind.NUMERICAL, state.artifact.fit_summary
        )

    @staticmethod
    def _next_action(facts: AnalysisReviewFacts) -> AnalysisNextAction:
        if facts.readiness is AnalysisReadiness.NOT_ANALYZED:
            return AnalysisNextAction.ANALYZE
        if facts.readiness is AnalysisReadiness.STALE:
            return AnalysisNextAction.REANALYZE
        return AnalysisNextAction.OPEN_REGION


__all__ = ["AnalysisReviewFacts", "AnalysisReviewPresenter"]
