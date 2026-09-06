"""Tests for optimize group analysis use cases."""

from __future__ import annotations

import math

from chappy.application.optimize import OptimizeExportControlsState, OptimizeGroupAnalysisUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisReadiness, FitSummary
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.tie_set import FULL_TIE_MASK, ParameterTieSet
from chappy.core.spectroscopy_project import SpectroscopyProject


def _line(
    line_id: str,
    *,
    center_z: float = 1.0,
    rest_wavelength: float = 1215.67,
    window_kms: float = 150.0,
    region_id: str = "region-1",
    model_ids: list[str] | None = None,
) -> AbsorptionLine:
    """Create a minimal absorption line."""
    return AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=window_kms,
        region_id=region_id,
        multiplet_label="Ly alpha",
        transition_name="Ly alpha",
        oscillator_strength=0.1,
        gamma_value=1e8,
        model_ids=model_ids if model_ids is not None else [],
    )


def _project() -> SpectroscopyProject:
    """Create a project with one optimize group."""
    project = SpectroscopyProject()
    line = _line("line-1")
    region = AbsorptionRegion(
        region_id="region-1", line_ids=[line.line_id], analysis_range=(3500.0, 3600.0)
    )
    project.absorption_lines[line.line_id] = line
    project.absorption_regions[region.region_id] = region
    project.mark_region_needs_optimization(region.region_id)
    return project


def test_record_successful_analysis_clears_needs_flag_and_enables_export() -> None:
    """Ready analysis should clear needs state and enable export."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    summary = FitSummary(chi_squared=1.0)

    usecase.record_successful_analysis(project, "region-1", summary)

    assert project.is_region_needs_optimization("region-1") is False
    assert usecase.analysis_readiness(project, "region-1") is AnalysisReadiness.LATEST
    assert usecase.export_controls_state(project, "region-1") == OptimizeExportControlsState(
        export_enabled=True, needs_visible=False
    )
    assert usecase.fit_summary(project, "region-1") == summary


def test_mark_region_needs_optimization_retains_stale_evidence() -> None:
    """Marking a region dirty should disable export without deleting evidence."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    summary = FitSummary(chi_squared=1.0)
    usecase.record_successful_analysis(project, "region-1", summary)

    assert usecase.mark_region_needs_optimization(project, "region-1") is True

    assert project.is_region_needs_optimization("region-1") is True
    assert usecase.export_controls_state(project, "region-1") == OptimizeExportControlsState(
        export_enabled=False, needs_visible=True
    )
    assert usecase.analysis_readiness(project, "region-1") is AnalysisReadiness.STALE
    assert usecase.fit_summary(project, "region-1") == summary


def test_region_without_artifact_is_not_analyzed_and_not_exportable() -> None:
    """An existing region cannot be exportable without fit evidence."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()

    assert usecase.analysis_readiness(project, "region-1") is AnalysisReadiness.NOT_ANALYZED
    assert usecase.export_controls_state(project, "region-1") == OptimizeExportControlsState(
        export_enabled=False, needs_visible=True
    )


def test_fit_summary_distinguishes_missing_artifact_from_empty_summary() -> None:
    """The public query must not fabricate an empty summary for missing evidence."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()

    assert usecase.fit_summary(project, "region-1") is None

    empty_summary = FitSummary()
    usecase.record_successful_analysis(project, "region-1", empty_summary)

    assert usecase.fit_summary(project, "region-1") == empty_summary
    assert usecase.fit_summary(project, "region-1") is not None


def test_mixed_line_freshness_is_stale_and_not_exportable() -> None:
    """Any stale line must keep a region artifact from being treated as latest."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    second_line = _line("line-2")
    project.absorption_lines[second_line.line_id] = second_line
    project.absorption_regions["region-1"].line_ids.append(second_line.line_id)
    usecase.record_successful_analysis(project, "region-1", FitSummary(chi_squared=1.0))
    project.absorption_lines["line-2"].needs_optimization = True

    assert usecase.analysis_readiness(project, "region-1") is AnalysisReadiness.STALE
    assert usecase.export_controls_state(project, "region-1") == OptimizeExportControlsState(
        export_enabled=False, needs_visible=True
    )


def test_missing_group_returns_disabled_export_state() -> None:
    """Missing state should produce disabled export controls."""
    usecase = OptimizeGroupAnalysisUseCase()

    assert usecase.export_controls_state(None, None) == OptimizeExportControlsState(
        export_enabled=False, needs_visible=False
    )
    assert usecase.analysis_readiness(None, None) is AnalysisReadiness.NOT_ANALYZED
    assert usecase.mark_region_needs_optimization(None, None) is False


def test_region_lines_for_display_orders_by_center_then_wavelength_then_id() -> None:
    """Region lines must come back in the same order the tree displays them."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    later_line = _line("line-2", center_z=2.0)
    project.absorption_lines[later_line.line_id] = later_line
    project.absorption_regions["region-1"].line_ids.append(later_line.line_id)

    lines = usecase.region_lines_for_display(project, "region-1")

    assert [line.line_id for line in lines] == ["line-1", "line-2"]


def test_region_lines_for_display_handles_missing_project_or_region() -> None:
    """Absent project/region/state should be a valid empty result, not an error."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()

    assert usecase.region_lines_for_display(None, "region-1") == ()
    assert usecase.region_lines_for_display(project, None) == ()
    assert usecase.region_lines_for_display(project, "missing-region") == ()


def test_component_count_deduplicates_shared_component_across_lines() -> None:
    """A component referenced by two lines counts once; a dangling id does not count."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    project.absorption_lines["line-1"].model_ids = ["comp-1", "comp-missing"]
    second_line = _line("line-2", model_ids=["comp-1", "comp-2"])
    project.absorption_lines[second_line.line_id] = second_line
    project.absorption_regions["region-1"].line_ids.append(second_line.line_id)
    project.model.add_component_storage(AbsorberComponent(name="a", component_id="comp-1"))
    project.model.add_component_storage(AbsorberComponent(name="b", component_id="comp-2"))

    assert usecase.component_count_for_region(project, "region-1") == 2


def test_component_count_missing_project_or_region_is_zero() -> None:
    """Missing project/region is a valid empty result."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()

    assert usecase.component_count_for_region(None, "region-1") == 0
    assert usecase.component_count_for_region(project, None) == 0
    assert usecase.component_count_for_region(project, "missing-region") == 0


def test_line_for_component_hit_and_miss() -> None:
    """Return the line that references a component id, or None if none does."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    project.absorption_lines["line-1"].model_ids = ["comp-1"]

    assert usecase.line_for_component(project, "comp-1") is project.absorption_lines["line-1"]
    assert usecase.line_for_component(project, "comp-missing") is None
    assert usecase.line_for_component(None, "comp-1") is None
    assert usecase.line_for_component(project, None) is None


def test_line_for_wavelength_picks_bounds_match_and_nearest_center() -> None:
    """Candidates are limited to the region's lines; overlaps resolve by nearest center."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    close_line = _line("line-2", center_z=1.0007)
    project.absorption_lines[close_line.line_id] = close_line
    project.absorption_regions["region-1"].line_ids.append(close_line.line_id)

    line_1_center = 1215.67 * (1 + 1.0)
    line_2_center = 1215.67 * (1 + 1.0007)

    inside_line_1 = usecase.line_for_wavelength(project, "region-1", line_1_center + 0.01)
    assert inside_line_1 is project.absorption_lines["line-1"]

    midpoint = (line_1_center + line_2_center) / 2
    nearer_to_line_2 = usecase.line_for_wavelength(project, "region-1", midpoint + 0.001)
    assert nearer_to_line_2 is close_line

    assert usecase.line_for_wavelength(project, "region-1", 1.0) is None
    assert usecase.line_for_wavelength(project, "region-1", math.nan) is None


def test_line_for_wavelength_scopes_to_the_given_region_only() -> None:
    """A line in another region must not be a candidate even if its range covers wavelength."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    other_region_line = _line("line-other", region_id="region-2")
    project.absorption_lines[other_region_line.line_id] = other_region_line
    project.absorption_regions["region-2"] = AbsorptionRegion(
        region_id="region-2", line_ids=[other_region_line.line_id], analysis_range=(3500.0, 3600.0)
    )
    center = 1215.67 * (1 + 1.0)

    assert usecase.line_for_wavelength(project, "region-2", center) is other_region_line
    assert (
        usecase.line_for_wavelength(project, "region-1", center)
        is project.absorption_lines["line-1"]
    )


def test_tie_member_ids_for_redshift() -> None:
    """Tied components resolve to the shared member set; untied/missing resolve empty."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()
    tied_a = AbsorberComponent(name="tied-a")
    tied_b = AbsorberComponent(name="tied-b")
    untied = AbsorberComponent(name="untied")
    project.model.add_component_storage(tied_a)
    project.model.add_component_storage(tied_b)
    project.model.add_component_storage(untied)
    tie_set = ParameterTieSet(tie_id="tie-1", mask=FULL_TIE_MASK)
    tie_set.add_component(tied_a)
    tie_set.add_component(tied_b)

    assert usecase.tie_member_ids_for_redshift(project, tied_a.id) == frozenset(
        {tied_a.id, tied_b.id}
    )
    assert usecase.tie_member_ids_for_redshift(project, tied_b.id) == frozenset(
        {tied_a.id, tied_b.id}
    )
    assert usecase.tie_member_ids_for_redshift(project, untied.id) == frozenset()
    assert usecase.tie_member_ids_for_redshift(project, "component-missing") == frozenset()
    assert usecase.tie_member_ids_for_redshift(None, tied_a.id) == frozenset()


def test_has_regions_with_lines() -> None:
    """Only assigned regions with at least one line should count."""
    usecase = OptimizeGroupAnalysisUseCase()
    project = _project()

    assert usecase.has_regions_with_lines(project) is True
    assert usecase.has_regions_with_lines(None) is False

    project.absorption_regions["region-1"].line_ids.clear()
    assert usecase.has_regions_with_lines(project) is False
