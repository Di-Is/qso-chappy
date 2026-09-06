"""Integration tests for topology repair during project mapping."""

from __future__ import annotations

from datetime import UTC, datetime

from chappy.application.project_document import (
    AbsorptionLineDocument,
    AbsorptionRegionDocument,
    AnalysisArtifactDocument,
    FitSummaryDocument,
    IdentifyStateDocument,
    ProjectDocument,
    RegionAnalysisStateDocument,
)
from chappy.application.project_mapper import project_from_document
from chappy.application.structure.region_line_topology import (
    RegionLineTopologyIssueKind,
    find_region_line_topology_issues,
)


def _project_document() -> ProjectDocument:
    timestamp = datetime(2025, 1, 2, tzinfo=UTC)
    return ProjectDocument(
        name="repair-test",
        spectrum_filename=None,
        created=timestamp,
        modified=timestamp,
        metadata={},
        settings={},
        spectrum=None,
        components=(),
        masks=(),
        fit_wavelength_range=None,
        tie_sets=(),
        absorption_regions=(
            AbsorptionRegionDocument(
                region_id="region-a",
                line_ids=("line-1",),
                display_color="#123456",
                analysis_range=(1.0, 2.0),
                created_at=timestamp,
            ),
            AbsorptionRegionDocument(
                region_id="region-empty",
                line_ids=("missing-line",),
                display_color="#654321",
                analysis_range=(3.0, 4.0),
                created_at=timestamp,
            ),
        ),
        absorption_lines=(
            AbsorptionLineDocument(
                line_id="line-1",
                species="C IV",
                rest_wavelength=1548.195,
                center_z=0.5,
                window_kms=150.0,
                multiplet_label="C IV",
                transition_name="1548",
                oscillator_strength=0.19,
                gamma_value=2.65e8,
                lambda_range=(2300.0, 2350.0),
                region_id="missing-region",
                multiplet_ids=(),
                model_ids=(),
                needs_optimization=False,
                created_by="identify",
                created_at=timestamp,
            ),
        ),
        analysis_states=(
            RegionAnalysisStateDocument(
                region_id="region-a",
                current_revision=4,
                artifact=AnalysisArtifactDocument(
                    region_id="region-a",
                    source_revision=4,
                    fit_summary=FitSummaryDocument(
                        chi_squared=1.0,
                        reduced_chi_squared=0.5,
                        degrees_of_freedom=2.0,
                        n_parameters=3,
                        n_function_evaluations=10,
                        outcome="converged",
                    ),
                ),
            ),
        ),
        identify_state=IdentifyStateDocument(
            work_phase="idle",
            reference_z=0.0,
            last_added_wavelength=None,
            last_click_wavelength=None,
        ),
    )


def test_project_from_document_repairs_before_pruning_empty_regions() -> None:
    """Mapping repairs references, stales analysis, and prunes vacated regions."""
    result = project_from_document(_project_document())
    project = result.project

    assert {action.kind for action in result.repair_report.actions} == {
        RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE,
        RegionLineTopologyIssueKind.REGION_LINE_MISMATCH,
    }
    assert project.absorption_regions["region-a"].line_ids == ["line-1"]
    assert project.absorption_lines["line-1"].region_id == "region-a"
    assert project.absorption_lines["line-1"].needs_optimization is True
    assert project.absorption_regions["region-a"].analysis_range == (2300.0, 2350.0)
    assert "region-empty" not in project.absorption_regions
    assert (
        find_region_line_topology_issues(project.absorption_regions, project.absorption_lines)
        == ()
    )

    state = project.region_analysis_state("region-a")
    assert state is not None
    assert state.current_revision.value == 4
    assert state.artifact is not None
    assert state.artifact.source_revision.value == 4
    assert project.region_requires_reanalysis("region-a") is True
