"""Use case for deriving region analysis readiness."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.core.analysis import AnalysisReadiness

if TYPE_CHECKING:
    from chappy.application.analysis_artifacts.ports import AnalysisReadinessSourcePort


class DeriveAnalysisReadinessUseCase:
    """Derive one exclusive readiness value from authoritative facts."""

    def execute(self, source: AnalysisReadinessSourcePort, region_id: str) -> AnalysisReadiness:
        """Return readiness in artifact and freshness order."""
        region_state = source.region_analysis_state(region_id)
        if region_state is None:
            return AnalysisReadiness.NOT_ANALYZED

        artifact = region_state.artifact
        if artifact is None:
            return AnalysisReadiness.NOT_ANALYZED

        if (
            source.region_requires_reanalysis(region_id)
            or artifact.source_revision != region_state.current_revision
        ):
            return AnalysisReadiness.STALE

        return AnalysisReadiness.LATEST
