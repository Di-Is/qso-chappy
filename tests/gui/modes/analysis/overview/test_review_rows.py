"""Tests for authoritative project-to-presentation Overview row construction."""

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisReadiness,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.review_rows import AnalysisOverviewRowsBuilder
from chappy.presentation.analysis import AnalysisFitResultKind


def _project() -> SpectroscopyProject:
    project = SpectroscopyProject(name="overview")
    project.absorption_lines["line-1"] = AbsorptionLine(
        line_id="line-1",
        species="C IV",
        rest_wavelength=1548.2,
        center_z=2.0,
        window_kms=150.0,
        region_id="region-1",
        multiplet_label="C IV",
        transition_name="C IV 1548",
        oscillator_strength=0.1,
        gamma_value=1e8,
    )
    project.absorption_regions["region-1"] = AbsorptionRegion(
        region_id="region-1", line_ids=["line-1"]
    )
    return project


def test_builder_uses_readiness_and_pure_presenter_without_cause_inference() -> None:
    """Artifact absence and latest numerical evidence retain their P1 meanings."""
    project = _project()
    builder = AnalysisOverviewRowsBuilder()

    rows, summary = builder.build(project)

    assert len(rows) == 1
    assert rows[0].analysis_status is AnalysisReadiness.NOT_ANALYZED
    assert rows[0].fit_result.kind is AnalysisFitResultKind.NOT_ANALYZED
    assert summary.not_analyzed == 1
    assert summary.latest == 0

    revision = AnalysisRevision()
    artifact = AnalysisArtifact(
        region_id="region-1",
        source_revision=revision,
        fit_summary=FitSummary(reduced_chi_squared=1.2),
    )
    project.set_region_analysis_states((RegionAnalysisState("region-1", revision, artifact),))
    project.absorption_lines["line-1"].needs_optimization = False

    rows, summary = builder.build(project)

    assert rows[0].analysis_status is AnalysisReadiness.LATEST
    assert rows[0].fit_result.kind is AnalysisFitResultKind.NUMERICAL
    assert summary.latest == 1
