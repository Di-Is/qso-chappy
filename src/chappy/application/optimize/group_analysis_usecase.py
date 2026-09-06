"""Use cases for Optimize region analysis state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.application.analysis_artifacts import (
    AnalysisArtifactStoreUseCase,
    DeriveAnalysisReadinessUseCase,
    RecordSuccessfulAnalysisUseCase,
)
from chappy.application.analysis_artifacts.store_usecase import SuccessfulAnalysisProjectPort
from chappy.application.optimize.model_addition_usecase import model_addition_wavelength_range
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.absorption_display import sort_lines_for_display
from chappy.core.analysis import AnalysisReadiness, FitSummary, RegionAnalysisState
from chappy.core.components.tie_set import effective_tie_set_for_parameter

if TYPE_CHECKING:
    from datetime import datetime

    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.components.absorber import AbsorberComponent


class GroupAnalysisProjectPort(SuccessfulAnalysisProjectPort, Protocol):
    """Project operations required by Optimize region analysis."""

    modified: datetime

    def is_region_needs_optimization(self, region_id: str) -> bool:
        """Return whether a region needs optimization."""
        ...

    def mark_region_needs_optimization(self, region_id: str) -> int:
        """Mark a region as needing optimization."""
        ...

    def find_absorber_component(self, component_id: str) -> AbsorberComponent | None:
        """Return the absorber component matching an id, if present."""
        ...


@dataclass(frozen=True, slots=True)
class OptimizeExportControlsState:
    """Export control state derived from region analysis readiness."""

    export_enabled: bool
    needs_visible: bool


class OptimizeGroupAnalysisUseCase:
    """Coordinate Optimize operations over project-owned analysis state."""

    def __init__(self) -> None:
        """Initialize stateless analysis transition collaborators."""
        self._derive_readiness = DeriveAnalysisReadinessUseCase()
        self._artifacts = AnalysisArtifactStoreUseCase()
        self._record_success = RecordSuccessfulAnalysisUseCase(artifacts=self._artifacts)

    def export_controls_state(
        self, project: GroupAnalysisProjectPort | None, group_id: str | None
    ) -> OptimizeExportControlsState:
        """Return export and stale-indicator state for one region."""
        if not group_id or project is None or group_id not in project.absorption_regions:
            return OptimizeExportControlsState(export_enabled=False, needs_visible=False)

        readiness = self.analysis_readiness(project, group_id)
        return OptimizeExportControlsState(
            export_enabled=readiness.exportable,
            needs_visible=self.region_needs_optimization(project, group_id),
        )

    def analysis_readiness(
        self, project: GroupAnalysisProjectPort | None, group_id: str | None
    ) -> AnalysisReadiness:
        """Derive readiness from current authoritative project facts."""
        if project is None or not group_id:
            return AnalysisReadiness.NOT_ANALYZED
        return self._derive_readiness.execute(project, group_id)

    def region_needs_optimization(
        self, project: GroupAnalysisProjectPort | None, group_id: str
    ) -> bool:
        """Return whether a region needs optimization."""
        if project is None:
            return True
        return project.is_region_needs_optimization(group_id)

    def record_successful_analysis(
        self, project: GroupAnalysisProjectPort | None, group_id: str, summary: FitSummary
    ) -> None:
        """Atomically store successful fit evidence and clear stale line flags."""
        if project is None:
            msg = "A project is required to record successful analysis."
            raise RuntimeError(msg)
        self._record_success.execute(project, group_id, summary)

    def mark_region_needs_optimization(
        self, project: GroupAnalysisProjectPort | None, group_id: str | None
    ) -> bool:
        """Atomically mark lines stale and advance the region input revision."""
        if not group_id or project is None or group_id not in project.absorption_regions:
            return False

        state = self.snapshot_group_analysis(project, group_id)
        region = project.absorption_regions[group_id]
        flags = tuple(
            (line_id, project.absorption_lines[line_id].needs_optimization)
            for line_id in region.line_ids
            if line_id in project.absorption_lines
        )
        modified = project.modified
        try:
            project.mark_region_needs_optimization(group_id)
            self._artifacts.invalidate(project, group_id)
        except Exception:
            self._artifacts.restore(project, state)
            for line_id, needs_optimization in flags:
                project.absorption_lines[line_id].needs_optimization = needs_optimization
            project.modified = modified
            raise
        return True

    def fit_summary(
        self, project: GroupAnalysisProjectPort | None, group_id: str
    ) -> FitSummary | None:
        """Return stored fit evidence without fabricating an empty summary."""
        if project is None:
            return None
        state = project.region_analysis_state(group_id)
        return state.artifact.fit_summary if state is not None and state.artifact else None

    @staticmethod
    def snapshot_group_analysis(
        project: GroupAnalysisProjectPort, group_id: str
    ) -> RegionAnalysisState:
        """Capture exact project-owned analysis state for transaction rollback."""
        state = project.region_analysis_state(group_id)
        if state is None:
            msg = f"Analysis region not found: {group_id}"
            raise ValueError(msg)
        return state

    def region_lines_for_display(
        self, project: GroupAnalysisProjectPort | None, region_id: str | None
    ) -> tuple[AbsorptionLine, ...]:
        """Return the display-ordered absorption lines belonging to one region."""
        if project is None or not region_id:
            return ()
        region = project.absorption_regions.get(region_id)
        if region is None:
            return ()
        lines = [
            project.absorption_lines[line_id]
            for line_id in region.line_ids
            if line_id in project.absorption_lines
        ]
        return tuple(sort_lines_for_display(lines))

    def component_count_for_region(
        self, project: GroupAnalysisProjectPort | None, region_id: str | None
    ) -> int:
        """Return the number of distinct live components across a region's lines."""
        if project is None or not region_id:
            return 0
        region = project.absorption_regions.get(region_id)
        if region is None:
            return 0
        component_ids: set[str] = set()
        for line_id in region.line_ids:
            line = project.absorption_lines.get(line_id)
            if line is None:
                continue
            for model_id in line.model_ids:
                if project.find_absorber_component(model_id) is not None:
                    component_ids.add(model_id)
        return len(component_ids)

    def has_regions_with_lines(self, project: GroupAnalysisProjectPort | None) -> bool:
        """Return whether the project has any assigned region containing lines."""
        if project is None:
            return False
        for region_id, region in project.absorption_regions.items():
            if region_id == UNASSIGNED_REGION_ID:
                continue
            if region.line_ids:
                return True
        return False

    def line_for_component(
        self, project: GroupAnalysisProjectPort | None, component_id: str | None
    ) -> AbsorptionLine | None:
        """Return the first absorption line referencing a component id."""
        if project is None or not component_id:
            return None
        for line in project.absorption_lines.values():
            if component_id in line.model_ids:
                return line
        return None

    def line_for_wavelength(
        self, project: GroupAnalysisProjectPort | None, region_id: str | None, wavelength: float
    ) -> AbsorptionLine | None:
        """Return the region line whose accepted wavelength range covers `wavelength`.

        Candidates are limited to the lines of the given region (the region the
        tree currently displays). Ties between overlapping ranges are broken by
        nearest line center.
        """
        best_candidate: tuple[float, AbsorptionLine] | None = None
        for line in self.region_lines_for_display(project, region_id):
            bounds = model_addition_wavelength_range(line)
            if bounds is None:
                continue
            low, high = bounds
            if not (low <= wavelength <= high):
                continue
            center = line_center_wavelength(line)
            distance = abs(center - wavelength)
            if best_candidate is None or distance < best_candidate[0]:
                best_candidate = (distance, line)
        return best_candidate[1] if best_candidate else None

    def tie_member_ids_for_redshift(
        self, project: GroupAnalysisProjectPort | None, component_id: str
    ) -> frozenset[str]:
        """Return the ids of components sharing redshift with the given component."""
        if project is None:
            return frozenset()
        component = project.find_absorber_component(component_id)
        if component is None:
            return frozenset()
        tie_set = effective_tie_set_for_parameter(component, "redshift")
        if tie_set is None:
            return frozenset()
        return frozenset(member.id for member in tie_set.components)


def line_center_wavelength(line: AbsorptionLine) -> float:
    """Return the observed-frame center wavelength of a validated absorption line."""
    return float(line.rest_wavelength) * (1.0 + float(line.center_z))
