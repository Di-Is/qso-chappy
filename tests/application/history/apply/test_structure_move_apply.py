"""Atomic structure-move history integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chappy.application.history import (
    AbsorptionRegionSnapshot,
    ChangeSet,
    HistoryApplyError,
    HistoryApplyErrorCode,
    HistoryRecorder,
    LineRegionAssignment,
    StructureMoveHistoryPayload,
    StructureMoveLinkedLinesCommand,
)
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.change_set import ChangeSet as DomainChangeSet
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.history import CommandHistory, HistoryEvent
from chappy.core.masking import MaskDefinition, MaskMode
from chappy.core.spectroscopy_project import SpectroscopyProject

from history_apply_fakes import FakeHistoryRefreshPort, build_usecase

if TYPE_CHECKING:
    from pytest import MonkeyPatch

    from chappy.application.history.apply.usecase import HistoryApplyUseCase


@dataclass(slots=True)
class _PayloadCapture:
    """Capture one public move history payload without a GUI history stack."""

    payloads: list[StructureMoveHistoryPayload] = field(default_factory=list)

    @contextmanager
    def atomic_recording(self) -> Iterator[None]:
        """Provide the required rollback-aware history scope."""
        snapshot = list(self.payloads)
        try:
            yield
        except Exception:
            self.payloads = snapshot
            raise

    def record_structure_move_linked_lines(self, payload: StructureMoveHistoryPayload) -> None:
        """Capture one payload."""
        self.payloads.append(payload)


def _line(line_id: str, region_id: str) -> AbsorptionLine:
    """Build one fresh absorption line."""
    return AbsorptionLine(
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


def _analysis_state(region_id: str) -> RegionAnalysisState:
    """Build revision-one evidence for one initial region."""
    revision = AnalysisRevision(1)
    return RegionAnalysisState(
        region_id=region_id,
        current_revision=revision,
        artifact=AnalysisArtifact(
            region_id=region_id, source_revision=revision, fit_summary=FitSummary(chi_squared=1.0)
        ),
    )


def _project(
    regions: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[SpectroscopyProject, dict[str, AnalysisArtifact]]:
    """Build deterministic initial topology and retained evidence."""
    project = SpectroscopyProject()
    artifacts: dict[str, AnalysisArtifact] = {}
    for index, (region_id, line_ids) in enumerate(regions, start=1):
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=list(line_ids), display_color=f"#{index:06d}"
        )
        for line_id in line_ids:
            project.absorption_lines[line_id] = _line(line_id, region_id)
        state = _analysis_state(region_id)
        assert state.artifact is not None
        artifacts[region_id] = state.artifact
        project.set_region_analysis_state(state)
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project, artifacts


def _history(
    project: SpectroscopyProject, *, refresh_port: FakeHistoryRefreshPort | None = None
) -> tuple[CommandHistory, HistoryApplyUseCase]:
    """Connect a real command stack to the structure history handler."""
    history = CommandHistory()
    usecase = build_usecase(
        project_provider=lambda: project, refresh_port=refresh_port or FakeHistoryRefreshPort()
    )
    history.set_applier(usecase)
    return history, usecase


def _assert_regions(
    project: SpectroscopyProject, expected: dict[str, tuple[int, AnalysisArtifact | None]]
) -> None:
    """Require exact region presence, revision, artifact identity, and freshness."""
    assert set(project.absorption_regions) == set(expected)
    for region_id, (revision, artifact) in expected.items():
        state = project.region_analysis_state(region_id)
        assert state is not None
        assert state.current_revision == AnalysisRevision(revision)
        assert state.artifact is artifact
        assert all(
            project.absorption_lines[line_id].needs_optimization
            for line_id in project.absorption_regions[region_id].line_ids
        )


@pytest.mark.parametrize(
    "case",
    [
        "existing-survives",
        "existing-source-removed",
        "new-source-survives",
        "new-source-removed",
        "unassigned",
    ],
)
def test_move_undo_redo_revision_and_artifact_matrix(case: str) -> None:
    """Both history directions stale survivors and reset only recreated regions."""
    regions: tuple[tuple[str, tuple[str, ...]], ...]
    target: str | None
    if case == "existing-survives":
        regions = (("source", ("line-1", "line-2")), ("target", ("line-3",)))
        target = "target"
    elif case == "existing-source-removed":
        regions = (("source", ("line-1",)), ("target", ("line-2",)))
        target = "target"
    elif case == "new-source-survives":
        regions = (("source", ("line-1", "line-2")),)
        target = None
    elif case == "new-source-removed":
        regions = (("source", ("line-1",)),)
        target = None
    else:
        regions = ((UNASSIGNED_REGION_ID, ("line-1",)), ("target", ("line-2",)))
        target = "target"

    project, artifacts = _project(regions)
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    result = StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id=target, history_recorder=recorder
    )
    assert result is not None
    destination_id = result.destination_id
    assert history.get_state().undo_count == 1

    if case in {"existing-survives", "unassigned"}:
        source_id = "source" if case == "existing-survives" else UNASSIGNED_REGION_ID
        _assert_regions(
            project, {source_id: (2, artifacts[source_id]), "target": (2, artifacts["target"])}
        )
        assert history.undo().success
        _assert_regions(
            project, {source_id: (3, artifacts[source_id]), "target": (3, artifacts["target"])}
        )
        assert history.redo().success
        _assert_regions(
            project, {source_id: (4, artifacts[source_id]), "target": (4, artifacts["target"])}
        )
    elif case == "existing-source-removed":
        _assert_regions(project, {"target": (2, artifacts["target"])})
        assert history.undo().success
        _assert_regions(project, {"source": (0, None), "target": (3, artifacts["target"])})
        assert history.redo().success
        _assert_regions(project, {"target": (4, artifacts["target"])})
    elif case == "new-source-survives":
        _assert_regions(project, {"source": (2, artifacts["source"]), destination_id: (0, None)})
        assert history.undo().success
        _assert_regions(project, {"source": (3, artifacts["source"])})
        assert history.redo().success
        _assert_regions(project, {"source": (4, artifacts["source"]), destination_id: (0, None)})
    else:
        _assert_regions(project, {destination_id: (0, None)})
        assert history.undo().success
        _assert_regions(project, {"source": (0, None)})
        assert history.redo().success
        _assert_regions(project, {destination_id: (0, None)})

    state = history.get_state()
    assert state.undo_count == 1
    assert state.redo_count == 0


def _exact_state(project: SpectroscopyProject) -> tuple[object, ...]:
    """Capture exact structure/science facts used by rollback assertions."""
    return (
        tuple(
            (key, id(region), region.region_id, tuple(region.line_ids), region.display_color)
            for key, region in project.absorption_regions.items()
        ),
        tuple(
            (key, id(line), line.line_id, line.region_id, line.needs_optimization)
            for key, line in project.absorption_lines.items()
        ),
        tuple((id(mask), mask) for mask in project.model.mask_definitions),
        tuple(
            (component.id, component.group_id)
            for component in project.model.components
            if isinstance(component, AbsorberComponent)
        ),
        project.stored_region_analysis_states_for_transaction(),
        project.modified,
        project.model.snapshot_derived_state_for_transaction(),
    )


@pytest.mark.parametrize("direction", ["undo", "redo"])
def test_move_history_rebuild_failure_restores_exact_state_stack_and_observers(
    direction: str, monkeypatch: MonkeyPatch
) -> None:
    """A derived-stage failure in either direction is an exact silent rollback."""
    project, _artifacts = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=recorder
    )
    if direction == "redo":
        assert history.undo().success

    before = _exact_state(project)
    history_before = history.get_state()
    observed: list[object] = []
    project.model.events.subscribe(observed.append)
    original_rebuild = project.model.rebuild_model_storage

    def fail_rebuild() -> DomainChangeSet:
        original_rebuild()
        raise RuntimeError("injected history rebuild failure")

    monkeypatch.setattr(project.model, "rebuild_model_storage", fail_rebuild)

    with pytest.raises(RuntimeError, match="injected history rebuild failure"):
        getattr(history, direction)()

    assert _exact_state(project) == before
    assert history.get_state() == history_before
    assert observed == []


def test_move_history_mid_command_failure_restores_exact_state_and_stack(
    monkeypatch: MonkeyPatch,
) -> None:
    """A failure after assignment mutation cannot leave partial topology."""
    project, _artifacts = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))
    history, usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=recorder
    )
    before = _exact_state(project)
    history_before = history.get_state()
    original_apply = usecase._structure_applier.apply_absorption_region_states_exact

    def fail_after_region_apply(snapshots: tuple[AbsorptionRegionSnapshot, ...]) -> ChangeSet:
        original_apply(snapshots)
        raise RuntimeError("injected mid-command failure")

    monkeypatch.setattr(
        usecase._structure_applier, "apply_absorption_region_states_exact", fail_after_region_apply
    )

    with pytest.raises(RuntimeError, match="injected mid-command failure"):
        history.undo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_invalid_destination_payload_is_typed_and_retains_stack() -> None:
    """Malformed destination identities fail typed preflight without ValueError leakage."""
    project, _artifacts = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))
    capture = _PayloadCapture()
    assert StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=capture
    )
    invalid_payload = replace(
        capture.payloads[0], destination_assignments=(LineRegionAssignment("line-1", None),)
    )
    history, _usecase = _history(project)
    assert history.push(
        HistoryEvent(command=StructureMoveLinkedLinesCommand(payload=invalid_payload))
    )
    history_before = history.get_state()

    with pytest.raises(HistoryApplyError) as exc_info:
        history.undo()

    assert exc_info.value.error_code is HistoryApplyErrorCode.INVALID_STATE
    assert history.get_state() == history_before


def test_move_history_restores_masks_and_component_groups_exactly() -> None:
    """Region deletion side effects round-trip through the public move payload."""
    project, artifacts = _project((("source", ("line-1",)), ("target", ("line-2",))))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    project.model.restore_mask_definitions_for_transaction(
        (
            MaskDefinition(
                identifier="mask",
                label="source mask",
                mode=MaskMode.RANGE,
                start_wavelength=1000.0,
                end_wavelength=1010.0,
                group_id="source",
            ),
        ),
        model_was_valid=False,
    )
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)

    assert StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=recorder
    )
    assert project.model.mask_definitions == ()
    assert component.group_id == "target"

    assert history.undo().success
    assert tuple(mask.identifier for mask in project.model.mask_definitions) == ("mask",)
    assert project.model.mask_definitions[0].group_id == "source"
    assert component.group_id == "source"
    _assert_regions(project, {"source": (0, None), "target": (3, artifacts["target"])})

    assert history.redo().success
    assert project.model.mask_definitions == ()
    assert component.group_id == "target"
    _assert_regions(project, {"target": (4, artifacts["target"])})


def test_postcommit_domain_and_gui_observer_failures_are_isolated() -> None:
    """Committed Undo reaches later domain observers after an earlier failure."""
    project, _artifacts = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    refresh_port = FakeHistoryRefreshPort()
    history, _usecase = _history(project, refresh_port=refresh_port)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=recorder
    )
    observed: list[object] = []

    def fail_domain_observer(_event: object) -> None:
        raise RuntimeError("injected domain observer failure")

    project.model.events.subscribe(fail_domain_observer)
    project.model.events.subscribe(observed.append)

    assert history.undo().success

    assert observed
    assert refresh_port.targets() == ()
