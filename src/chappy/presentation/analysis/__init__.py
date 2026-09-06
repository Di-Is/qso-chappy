"""Qt- and translation-independent Analysis review presentation."""

from chappy.presentation.analysis.models import (
    AnalysisFitResultDisplay,
    AnalysisFitResultKind,
    AnalysisNextAction,
    AnalysisRegionDisplay,
    AnalysisReviewRow,
    AnalysisReviewSummary,
)
from chappy.presentation.analysis.presenter import AnalysisReviewFacts, AnalysisReviewPresenter
from chappy.presentation.analysis.region_structure import (
    MAX_LINKED_LINES_WITH_BREAKDOWN,
    LinkedLineSummary,
    RegionStructureSummary,
    build_region_structure_summary,
)

__all__ = [
    "MAX_LINKED_LINES_WITH_BREAKDOWN",
    "AnalysisFitResultDisplay",
    "AnalysisFitResultKind",
    "AnalysisNextAction",
    "AnalysisRegionDisplay",
    "AnalysisReviewFacts",
    "AnalysisReviewPresenter",
    "AnalysisReviewRow",
    "AnalysisReviewSummary",
    "LinkedLineSummary",
    "RegionStructureSummary",
    "build_region_structure_summary",
]
