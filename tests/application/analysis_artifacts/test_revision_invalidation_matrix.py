"""Accepted cross-command revision and invalidation policy matrix."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pytest

from chappy.application.analysis_artifacts import (
    GlobalAnalysisMutationUseCase,
    RegionLocalAtomicMutationUseCase,
    RegionLocalMutationRequest,
)
from chappy.application.continuum import ContinuumComponentMutationUseCase
from chappy.application.identify import AtomicIdentifyRegistrationUseCase
from chappy.application.optimize import (
    EditLineAnalysisHalfWidthUseCase,
    MaskMutationUseCase,
    TieSetEditUseCase,
)
from chappy.application.spectrum import AbsorberEditUseCase, ResolutionUpdateUseCase
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.spectroscopy_project import SpectroscopyProject


class _MutationScope(StrEnum):
    """Scientific invalidation scopes exercised by production commands."""

    GLOBAL = "global"
    REGION_LOCAL = "region_local"
    NO_CHANGE = "no_change"
    DISPLAY_ONLY = "display_only"


@dataclass(frozen=True, slots=True)
class _MutationCase:
    """One Accepted-table row and its production application owner."""

    name: str
    scope: _MutationScope
    production_owner: type[object]


_MUTATION_CASES = (
    _MutationCase("parameter-value", _MutationScope.GLOBAL, AbsorberEditUseCase),
    _MutationCase("parameter-fixed", _MutationScope.GLOBAL, GlobalAnalysisMutationUseCase),
    _MutationCase("tie", _MutationScope.GLOBAL, TieSetEditUseCase),
    _MutationCase(
        "scientific-model-component", _MutationScope.GLOBAL, GlobalAnalysisMutationUseCase
    ),
    _MutationCase("continuum", _MutationScope.GLOBAL, ContinuumComponentMutationUseCase),
    _MutationCase("resolution", _MutationScope.GLOBAL, ResolutionUpdateUseCase),
    _MutationCase("mask-add", _MutationScope.REGION_LOCAL, MaskMutationUseCase),
    _MutationCase("mask-update", _MutationScope.REGION_LOCAL, MaskMutationUseCase),
    _MutationCase("mask-delete", _MutationScope.REGION_LOCAL, MaskMutationUseCase),
    _MutationCase(
        "analysis-half-width", _MutationScope.REGION_LOCAL, EditLineAnalysisHalfWidthUseCase
    ),
    _MutationCase("no-change", _MutationScope.NO_CHANGE, GlobalAnalysisMutationUseCase),
    _MutationCase("display-only", _MutationScope.DISPLAY_ONLY, StructureOperationUseCase),
)


def _project() -> SpectroscopyProject:
    """Create two fresh analyzed regions with retained numerical evidence."""
    project = SpectroscopyProject()
    for index in (1, 2):
        region_id = f"region-{index}"
        line_id = f"line-{index}"
        project.absorption_lines[line_id] = AbsorptionLine(
            line_id=line_id,
            species="C IV",
            rest_wavelength=1548.2,
            center_z=2.0,
            window_kms=120.0,
            multiplet_label="C IV",
            transition_name=line_id,
            oscillator_strength=0.19,
            gamma_value=1e8,
            region_id=region_id,
            needs_optimization=False,
        )
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=[line_id]
        )
        revision = AnalysisRevision(4)
        project.set_region_analysis_state(
            RegionAnalysisState(
                region_id=region_id,
                current_revision=revision,
                artifact=AnalysisArtifact(
                    region_id=region_id,
                    source_revision=revision,
                    fit_summary=FitSummary(
                        chi_squared=float(index),
                        reduced_chi_squared=float(index) / 2,
                        degrees_of_freedom=10.0,
                        n_parameters=4,
                        n_function_evaluations=7,
                    ),
                ),
            )
        )
    return project


@pytest.mark.parametrize("case", _MUTATION_CASES, ids=lambda case: case.name)
def test_non_structure_revision_and_invalidation_matrix(case: _MutationCase) -> None:
    """Every non-structure Accepted row obeys its shared production transaction scope.

    Focused tests for each listed ``production_owner`` exercise its domain mutation and
    history payload. This matrix fixes the common revision/artifact policy those owners
    delegate to, without duplicating their workflow-specific setup here.
    """
    project = _project()
    states_before = {state.region_id: state for state in project.region_analysis_states()}
    marker = {"value": 0}

    def change_marker() -> bool:
        marker["value"] = 1
        return True

    def restore_marker() -> None:
        marker["value"] = 0

    if case.scope is _MutationScope.GLOBAL:
        impact = GlobalAnalysisMutationUseCase().execute(
            project, mutate=change_marker, rollback=restore_marker
        )
        expected_affected = {"region-1", "region-2"}
        assert impact.affected_region_ids == ("region-1", "region-2")
    elif case.scope is _MutationScope.REGION_LOCAL:
        result = RegionLocalAtomicMutationUseCase().execute(
            project,
            RegionLocalMutationRequest(affected_region_ids=("region-1", "region-1")),
            mutate=change_marker,
            rollback=restore_marker,
        )
        expected_affected = {"region-1"}
        assert result.impact.affected_region_ids == ("region-1",)
    elif case.scope is _MutationScope.NO_CHANGE:
        impact = GlobalAnalysisMutationUseCase().execute(
            project, mutate=lambda: False, rollback=restore_marker
        )
        expected_affected = set()
        assert not impact.changed
    else:
        expected_affected = set()

    assert case.production_owner.__module__.startswith("chappy.application")
    for region_id in ("region-1", "region-2"):
        before = states_before[region_id]
        after = project.region_analysis_state(region_id)
        assert after is not None
        expected_revision = before.current_revision.value + (region_id in expected_affected)
        assert after.current_revision == AnalysisRevision(expected_revision)
        assert after.artifact is before.artifact
        assert after.artifact is not None
        assert after.artifact.source_revision == AnalysisRevision(4)
        line = project.absorption_lines[f"line-{region_id[-1]}"]
        assert line.needs_optimization is (region_id in expected_affected)


@pytest.mark.parametrize(
    "case",
    [
        _MutationCase("move-existing", _MutationScope.REGION_LOCAL, StructureOperationUseCase),
        _MutationCase(
            "move-new-and-remove-source", _MutationScope.REGION_LOCAL, StructureOperationUseCase
        ),
        _MutationCase("split", _MutationScope.REGION_LOCAL, StructureOperationUseCase),
        _MutationCase("merge", _MutationScope.REGION_LOCAL, StructureOperationUseCase),
        _MutationCase("unlink", _MutationScope.REGION_LOCAL, StructureOperationUseCase),
        _MutationCase("delete-local", _MutationScope.REGION_LOCAL, StructureOperationUseCase),
        _MutationCase("delete-region", _MutationScope.REGION_LOCAL, StructureOperationUseCase),
        _MutationCase("delete-model-global", _MutationScope.GLOBAL, StructureOperationUseCase),
        _MutationCase(
            "identify-existing-and-new",
            _MutationScope.REGION_LOCAL,
            AtomicIdentifyRegistrationUseCase,
        ),
    ],
    ids=lambda case: case.name,
)
def test_structure_accepted_rows_are_present_in_atomic_revision_matrix(
    case: _MutationCase,
) -> None:
    """Keep every structure and Identify Accepted row in the atomic topology matrix."""
    from tests.application.structure.test_atomic_mutation_executor import _MATRIX_CASES

    matrix_names = {case.name for case in _MATRIX_CASES}

    assert case.name in matrix_names
    assert case.production_owner.__module__.startswith("chappy.application")
