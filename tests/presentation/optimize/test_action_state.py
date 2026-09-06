"""Tests for Region Detail action-state and summary display selection."""

from __future__ import annotations

import pytest

from chappy.core.analysis import AnalysisReadiness
from chappy.presentation.optimize import (
    FitBlockedReason,
    FitChi2View,
    FitCompleteView,
    FitCustomView,
    FitFailedView,
    FitReadyView,
    FitRunningView,
    RegionDetailActionInputs,
    RegionDetailActionState,
    SummaryFitChi2,
    SummaryFitPlaceholder,
    SummaryNoteAddModelComponent,
    SummaryNoteBlocked,
    SummaryNoteCustomMessage,
    SummaryNoteHidden,
    SummaryNoteRunFit,
    SummaryNoteStaleRegion,
    SummaryStateFailed,
    SummaryStateFitted,
    SummaryStateNeedsOptimization,
    SummaryStateNotFitted,
    SummaryStateOptimizing,
    SummaryStatePlaceholder,
    action_state,
    fit_blocked_reason,
    summary_fit_display,
    summary_note_display,
    summary_state_display,
)


def _inputs(
    *,
    fit_running: bool = False,
    has_spectrum: bool = True,
    has_region_selected: bool = True,
    has_model_components: bool = True,
    readiness: AnalysisReadiness = AnalysisReadiness.LATEST,
) -> RegionDetailActionInputs:
    return RegionDetailActionInputs(
        fit_running=fit_running,
        has_spectrum=has_spectrum,
        has_region_selected=has_region_selected,
        has_model_components=has_model_components,
        readiness=readiness,
    )


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (_inputs(fit_running=True), FitBlockedReason.FIT_RUNNING),
        (_inputs(has_spectrum=False), FitBlockedReason.NO_SPECTRUM),
        (_inputs(has_region_selected=False), FitBlockedReason.NO_REGION_SELECTED),
        (_inputs(has_model_components=False), FitBlockedReason.NO_MODEL_COMPONENTS),
        (_inputs(), None),
    ],
)
def test_fit_blocked_reason(
    inputs: RegionDetailActionInputs, expected: FitBlockedReason | None
) -> None:
    """Blocked reason should follow prerequisite priority order."""
    assert fit_blocked_reason(inputs) is expected


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (_inputs(has_spectrum=False), RegionDetailActionState.NO_CONTEXT),
        (_inputs(has_region_selected=False), RegionDetailActionState.NO_CONTEXT),
        (_inputs(has_model_components=False), RegionDetailActionState.EMPTY),
        (_inputs(readiness=AnalysisReadiness.LATEST), RegionDetailActionState.FITTED),
        (_inputs(readiness=AnalysisReadiness.STALE), RegionDetailActionState.NEEDS_FIT),
        (_inputs(readiness=AnalysisReadiness.NOT_ANALYZED), RegionDetailActionState.NEEDS_FIT),
        (
            _inputs(fit_running=True, readiness=AnalysisReadiness.LATEST),
            RegionDetailActionState.FITTED,
        ),
    ],
)
def test_action_state(inputs: RegionDetailActionInputs, expected: RegionDetailActionState) -> None:
    """Action state should be exclusive and derived from blocked reason plus readiness."""
    assert action_state(inputs) is expected


@pytest.mark.parametrize(
    ("state", "readiness", "status", "expected_type"),
    [
        (
            RegionDetailActionState.FITTED,
            AnalysisReadiness.LATEST,
            FitRunningView(),
            SummaryStateOptimizing,
        ),
        (
            RegionDetailActionState.FITTED,
            AnalysisReadiness.LATEST,
            FitFailedView(),
            SummaryStateFailed,
        ),
        (
            RegionDetailActionState.NO_CONTEXT,
            AnalysisReadiness.NOT_ANALYZED,
            FitReadyView(),
            SummaryStatePlaceholder,
        ),
        (
            RegionDetailActionState.FITTED,
            AnalysisReadiness.LATEST,
            FitCompleteView(),
            SummaryStateFitted,
        ),
        (
            RegionDetailActionState.NEEDS_FIT,
            AnalysisReadiness.STALE,
            FitReadyView(),
            SummaryStateNeedsOptimization,
        ),
        (
            RegionDetailActionState.NEEDS_FIT,
            AnalysisReadiness.NOT_ANALYZED,
            FitReadyView(),
            SummaryStateNotFitted,
        ),
        (
            RegionDetailActionState.EMPTY,
            AnalysisReadiness.NOT_ANALYZED,
            FitReadyView(),
            SummaryStateNotFitted,
        ),
    ],
)
def test_summary_state_display(
    state: RegionDetailActionState,
    readiness: AnalysisReadiness,
    status: object,
    expected_type: type,
) -> None:
    """Running/failed status should take priority over action-state placement."""
    result = summary_state_display(state, readiness, status)  # type: ignore[arg-type]
    assert isinstance(result, expected_type)


def test_summary_fit_display_prefers_project_summary() -> None:
    """A stored project chi-squared should take priority over the live fit status."""
    result = summary_fit_display(
        FitChi2View(chi2=5.0, reduced=1.2), project_chi2=3.0, project_reduced=0.5
    )
    assert result == SummaryFitChi2(chi2=3.0, reduced=0.5)


def test_summary_fit_display_falls_back_to_status() -> None:
    """A CHI2 status should populate the display when no project summary exists."""
    result = summary_fit_display(
        FitChi2View(chi2=5.0, reduced=None), project_chi2=None, project_reduced=None
    )
    assert result == SummaryFitChi2(chi2=5.0, reduced=None)


def test_summary_fit_display_placeholder_when_no_data() -> None:
    """No chi-squared value anywhere should yield a placeholder."""
    result = summary_fit_display(FitReadyView(), project_chi2=None, project_reduced=None)
    assert isinstance(result, SummaryFitPlaceholder)


def test_summary_fit_display_rejects_non_finite_chi2() -> None:
    """A non-finite chi-squared value should not be surfaced as a statistic."""
    result = summary_fit_display(FitReadyView(), project_chi2=float("nan"), project_reduced=None)
    assert isinstance(result, SummaryFitPlaceholder)


def test_summary_fit_display_drops_non_finite_reduced() -> None:
    """A non-finite reduced chi-squared should be dropped but not block the display."""
    result = summary_fit_display(FitReadyView(), project_chi2=4.0, project_reduced=float("inf"))
    assert result == SummaryFitChi2(chi2=4.0, reduced=None)


def test_summary_note_display_custom_message_takes_priority() -> None:
    """An application-supplied message should override every other note."""
    result = summary_note_display(
        RegionDetailActionState.EMPTY,
        AnalysisReadiness.NOT_ANALYZED,
        FitCustomView(message="hello"),
        None,
    )
    assert result == SummaryNoteCustomMessage(message="hello")


def test_summary_note_display_hidden_while_running() -> None:
    """No note should be shown while a fit is running."""
    result = summary_note_display(
        RegionDetailActionState.NEEDS_FIT, AnalysisReadiness.STALE, FitRunningView(), None
    )
    assert isinstance(result, SummaryNoteHidden)


@pytest.mark.parametrize(
    ("state", "readiness", "blocked_reason", "expected"),
    [
        (
            RegionDetailActionState.NO_CONTEXT,
            AnalysisReadiness.NOT_ANALYZED,
            FitBlockedReason.NO_SPECTRUM,
            SummaryNoteBlocked(reason=FitBlockedReason.NO_SPECTRUM),
        ),
        (
            RegionDetailActionState.NO_CONTEXT,
            AnalysisReadiness.NOT_ANALYZED,
            None,
            SummaryNoteHidden(),
        ),
        (
            RegionDetailActionState.EMPTY,
            AnalysisReadiness.NOT_ANALYZED,
            FitBlockedReason.NO_MODEL_COMPONENTS,
            SummaryNoteAddModelComponent(),
        ),
        (
            RegionDetailActionState.NEEDS_FIT,
            AnalysisReadiness.STALE,
            None,
            SummaryNoteStaleRegion(),
        ),
        (
            RegionDetailActionState.NEEDS_FIT,
            AnalysisReadiness.NOT_ANALYZED,
            None,
            SummaryNoteRunFit(),
        ),
        (RegionDetailActionState.FITTED, AnalysisReadiness.LATEST, None, SummaryNoteHidden()),
    ],
)
def test_summary_note_display(
    state: RegionDetailActionState,
    readiness: AnalysisReadiness,
    blocked_reason: FitBlockedReason | None,
    expected: object,
) -> None:
    """Notes should follow action state, falling back to blocked-reason detail."""
    result = summary_note_display(state, readiness, FitReadyView(), blocked_reason)
    assert result == expected
