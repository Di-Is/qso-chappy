"""Contract tests for exclusive analysis readiness derivation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from chappy.application.analysis_artifacts import DeriveAnalysisReadinessUseCase
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisReadiness,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)


@dataclass(frozen=True, slots=True)
class _Source:
    """Readiness source with independently configurable project facts."""

    state: RegionAnalysisState | None
    requires_reanalysis: bool

    def region_analysis_state(self, region_id: str) -> RegionAnalysisState | None:
        """Return the configured region analysis state."""
        _ = region_id
        return self.state

    def region_requires_reanalysis(self, region_id: str) -> bool:
        """Return the configured reanalysis requirement."""
        _ = region_id
        return self.requires_reanalysis


def _state(
    *, current_revision: int = 0, artifact_revision: int | None = None
) -> RegionAnalysisState:
    """Build one region state, optionally with an artifact."""
    artifact = (
        AnalysisArtifact(
            region_id="region-1",
            source_revision=AnalysisRevision(artifact_revision),
            fit_summary=FitSummary(),
        )
        if artifact_revision is not None
        else None
    )
    return RegionAnalysisState(
        region_id="region-1",
        current_revision=AnalysisRevision(current_revision),
        artifact=artifact,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            _Source(None, False), AnalysisReadiness.NOT_ANALYZED, id="missing-region-state"
        ),
        pytest.param(
            _Source(_state(), True),
            AnalysisReadiness.NOT_ANALYZED,
            id="artifact-absence-wins-over-stale-input",
        ),
        pytest.param(
            _Source(_state(current_revision=2, artifact_revision=1), False),
            AnalysisReadiness.STALE,
            id="revision-mismatch",
        ),
        pytest.param(
            _Source(_state(current_revision=2, artifact_revision=2), True),
            AnalysisReadiness.STALE,
            id="explicit-reanalysis-requirement",
        ),
        pytest.param(
            _Source(_state(current_revision=2, artifact_revision=2), False),
            AnalysisReadiness.LATEST,
            id="matching-current-artifact",
        ),
    ],
)
def test_readiness_derivation_is_exclusive_and_ordered(
    source: _Source, expected: AnalysisReadiness
) -> None:
    """Every fact combination resolves through the documented priority order."""
    result = DeriveAnalysisReadinessUseCase().execute(source, "region-1")

    assert result is expected
    assert result.exportable is (expected is AnalysisReadiness.LATEST)
