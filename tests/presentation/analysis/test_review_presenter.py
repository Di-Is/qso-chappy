"""Table-driven tests for Analysis review presentation."""

from __future__ import annotations

import pytest

from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisReadiness,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.presentation.analysis import (
    AnalysisFitResultDisplay,
    AnalysisFitResultKind,
    AnalysisNextAction,
    AnalysisRegionDisplay,
    AnalysisReviewFacts,
    AnalysisReviewPresenter,
    AnalysisReviewRow,
    AnalysisReviewSummary,
)


def _state(
    *,
    current_revision: int = 2,
    artifact_revision: int | None = None,
    summary: FitSummary | None = None,
) -> RegionAnalysisState:
    """Build one project-owned state for presentation tests."""
    artifact = None
    if artifact_revision is not None:
        artifact = AnalysisArtifact(
            region_id="region-1",
            source_revision=AnalysisRevision(artifact_revision),
            fit_summary=summary or FitSummary(chi_squared=1.0),
        )
    return RegionAnalysisState(
        region_id="region-1",
        current_revision=AnalysisRevision(current_revision),
        artifact=artifact,
    )


def _facts(
    readiness: AnalysisReadiness,
    *,
    state: RegionAnalysisState | None,
    requires_reanalysis: bool = False,
    line_ids: tuple[str, ...] = ("line-1",),
    missing_line_ids: tuple[str, ...] = (),
) -> AnalysisReviewFacts:
    """Build authoritative row facts with a stable region identity."""
    return AnalysisReviewFacts(
        region_id="region-1",
        region_label="Region 1",
        readiness=readiness,
        analysis_state=state,
        requires_reanalysis=requires_reanalysis,
        line_ids=line_ids,
        missing_line_ids=missing_line_ids,
    )


@pytest.mark.parametrize(
    ("facts", "fit_kind", "next_action", "has_summary"),
    [
        pytest.param(
            _facts(AnalysisReadiness.NOT_ANALYZED, state=_state()),
            AnalysisFitResultKind.NOT_ANALYZED,
            AnalysisNextAction.ANALYZE,
            False,
            id="not-analyzed-without-artifact",
        ),
        pytest.param(
            _facts(AnalysisReadiness.STALE, state=_state(current_revision=2, artifact_revision=1)),
            AnalysisFitResultKind.STALE,
            AnalysisNextAction.REANALYZE,
            False,
            id="stale-revision-hides-old-summary",
        ),
        pytest.param(
            _facts(
                AnalysisReadiness.STALE,
                state=_state(
                    current_revision=2,
                    artifact_revision=2,
                    summary=FitSummary(reduced_chi_squared=1.4),
                ),
                requires_reanalysis=True,
            ),
            AnalysisFitResultKind.STALE,
            AnalysisNextAction.REANALYZE,
            False,
            id="explicit-reanalysis-hides-current-summary",
        ),
        pytest.param(
            _facts(
                AnalysisReadiness.LATEST,
                state=_state(
                    current_revision=2,
                    artifact_revision=2,
                    summary=FitSummary(reduced_chi_squared=1.25, n_function_evaluations=8),
                ),
            ),
            AnalysisFitResultKind.NUMERICAL,
            AnalysisNextAction.OPEN_REGION,
            True,
            id="latest-numerical-summary",
        ),
    ],
)
def test_build_row_resolves_all_display_semantics(
    facts: AnalysisReviewFacts,
    fit_kind: AnalysisFitResultKind,
    next_action: AnalysisNextAction,
    has_summary: bool,
) -> None:
    """The GUI receives complete typed values for all columns."""
    row = AnalysisReviewPresenter().build_row(facts)

    assert row.region.region_id == "region-1"
    assert row.region.label == "Region 1"
    assert row.analysis_status is facts.readiness
    assert row.fit_result.kind is fit_kind
    assert (row.fit_result.summary is not None) is has_summary
    assert row.next_action is next_action


def test_latest_numerical_row_preserves_core_summary_identity() -> None:
    """Formatting remains a GUI concern without copying or weakening core evidence."""
    summary = FitSummary(chi_squared=12.5, reduced_chi_squared=1.25)
    facts = _facts(AnalysisReadiness.LATEST, state=_state(artifact_revision=2, summary=summary))

    row = AnalysisReviewPresenter().build_row(facts)

    assert row.fit_result.summary is summary


def test_summary_counts_exclusive_readiness() -> None:
    """Summary counts are constructed from typed rows rather than GUI text."""
    presenter = AnalysisReviewPresenter()
    rows = (
        presenter.build_row(_facts(AnalysisReadiness.NOT_ANALYZED, state=_state())),
        presenter.build_row(
            _facts(
                AnalysisReadiness.STALE,
                state=_state(artifact_revision=1, summary=FitSummary(chi_squared=4.0)),
            )
        ),
        presenter.build_row(
            _facts(
                AnalysisReadiness.LATEST,
                state=_state(artifact_revision=2, summary=FitSummary(chi_squared=3.0)),
            )
        ),
    )

    summary = presenter.build_summary(iter(rows))

    assert summary.total == 3
    assert summary.not_analyzed == 1
    assert summary.stale == 1
    assert summary.latest == 1


@pytest.mark.parametrize(
    ("readiness", "state", "requires_reanalysis"),
    [
        pytest.param(
            AnalysisReadiness.NOT_ANALYZED,
            _state(artifact_revision=2),
            False,
            id="not-analyzed-with-artifact",
        ),
        pytest.param(AnalysisReadiness.STALE, _state(), False, id="stale-without-artifact"),
        pytest.param(
            AnalysisReadiness.LATEST,
            _state(artifact_revision=1),
            False,
            id="latest-with-revision-mismatch",
        ),
        pytest.param(
            AnalysisReadiness.LATEST,
            _state(artifact_revision=2),
            True,
            id="latest-with-reanalysis-request",
        ),
    ],
)
def test_facts_reject_contradictions_from_the_readiness_contract(
    readiness: AnalysisReadiness, state: RegionAnalysisState, requires_reanalysis: bool
) -> None:
    """Contradictory external facts cannot silently become a misleading row."""
    with pytest.raises(ValueError):
        _facts(readiness, state=state, requires_reanalysis=requires_reanalysis)


def test_missing_line_ids_must_belong_to_the_region_references() -> None:
    """Missing references cannot name unrelated lines."""
    with pytest.raises(ValueError, match="Missing line IDs"):
        _facts(
            AnalysisReadiness.NOT_ANALYZED,
            state=_state(),
            line_ids=("line-1",),
            missing_line_ids=("line-other",),
        )


@pytest.mark.parametrize(
    ("line_ids", "missing_line_ids"),
    [
        pytest.param((), (), id="empty-region"),
        pytest.param(("line-1", "line-missing"), ("line-missing",), id="missing-line"),
    ],
)
def test_available_readiness_rejects_incomplete_region_topology(
    line_ids: tuple[str, ...], missing_line_ids: tuple[str, ...]
) -> None:
    """An incapable region cannot become latest and therefore export-ready."""
    with pytest.raises(ValueError, match="complete region line topology"):
        _facts(
            AnalysisReadiness.LATEST,
            state=_state(artifact_revision=2, summary=FitSummary(chi_squared=1.0)),
            line_ids=line_ids,
            missing_line_ids=missing_line_ids,
        )


@pytest.mark.parametrize(
    ("line_ids", "missing_line_ids", "message"),
    [
        pytest.param(("",), (), "must not be empty", id="empty-line-id"),
        pytest.param(
            ("line-1", "line-2"),
            ("line-2", "line-2"),
            "must be unique",
            id="duplicate-missing-line-id",
        ),
    ],
)
def test_facts_reject_invalid_line_identity_collections(
    line_ids: tuple[str, ...], missing_line_ids: tuple[str, ...], message: str
) -> None:
    """Cause inputs retain stable, non-duplicated line identities."""
    with pytest.raises(ValueError, match=message):
        _facts(
            AnalysisReadiness.NOT_ANALYZED,
            state=_state(),
            line_ids=line_ids,
            missing_line_ids=missing_line_ids,
        )


def test_numerical_fit_display_rejects_empty_summary() -> None:
    """A numerical fit result must carry at least one measured value."""
    with pytest.raises(ValueError, match="at least one summary value"):
        AnalysisFitResultDisplay(AnalysisFitResultKind.NUMERICAL, FitSummary())


def test_review_row_rejects_cross_column_contradictions() -> None:
    """Public row construction cannot disagree with exclusive readiness semantics."""
    with pytest.raises(ValueError, match="next action"):
        AnalysisReviewRow(
            region=AnalysisRegionDisplay("region-1", "Region 1"),
            analysis_status=AnalysisReadiness.STALE,
            fit_result=AnalysisFitResultDisplay(AnalysisFitResultKind.STALE),
            next_action=AnalysisNextAction.OPEN_REGION,
        )


def test_review_row_rejects_fit_kind_disagreeing_with_readiness() -> None:
    """The fit-result column is a pure derivation of the exclusive status."""
    with pytest.raises(ValueError, match="fit-result display"):
        AnalysisReviewRow(
            region=AnalysisRegionDisplay("region-1", "Region 1"),
            analysis_status=AnalysisReadiness.LATEST,
            fit_result=AnalysisFitResultDisplay(AnalysisFitResultKind.STALE),
            next_action=AnalysisNextAction.OPEN_REGION,
        )


def test_summary_rejects_counts_that_do_not_add_up() -> None:
    """Readiness counts must partition the total exactly."""
    with pytest.raises(ValueError, match="add up"):
        AnalysisReviewSummary(total=2, not_analyzed=0, stale=0, latest=1)
