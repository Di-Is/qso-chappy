"""Atomic history integration for structure split, merge, delete, and unlink."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chappy.application.history import HistoryApplyError, HistoryRecorder
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.change_set import ChangeSet as DomainChangeSet
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.history import CommandHistory
from chappy.core.spectroscopy_project import SpectroscopyProject

from history_apply_fakes import FakeHistoryRefreshPort, build_usecase

if TYPE_CHECKING:
    from pytest import MonkeyPatch

    from chappy.application.history.apply.usecase import HistoryApplyUseCase


def _line(line_id: str, region_id: str, *, multiplet_ids: tuple[str, ...] = ()) -> AbsorptionLine:
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
        multiplet_ids=list(multiplet_ids),
        needs_optimization=False,
    )


def _project(
    regions: tuple[tuple[str, tuple[str, ...]], ...], *, linked: bool = False
) -> tuple[SpectroscopyProject, dict[str, AnalysisArtifact]]:
    """Build deterministic topology with revision-one artifacts."""
    project = SpectroscopyProject()
    artifacts: dict[str, AnalysisArtifact] = {}
    for index, (region_id, line_ids) in enumerate(regions, start=1):
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=list(line_ids), display_color=f"#{index:06d}"
        )
        for line_id in line_ids:
            related = tuple(candidate for candidate in line_ids if candidate != line_id)
            project.absorption_lines[line_id] = _line(
                line_id, region_id, multiplet_ids=related if linked else ()
            )
        revision = AnalysisRevision(1)
        artifact = AnalysisArtifact(
            region_id=region_id, source_revision=revision, fit_summary=FitSummary(chi_squared=1.0)
        )
        artifacts[region_id] = artifact
        project.set_region_analysis_state(
            RegionAnalysisState(region_id, revision, artifact=artifact)
        )
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project, artifacts


def _history(
    project: SpectroscopyProject, *, refresh_port: FakeHistoryRefreshPort | None = None
) -> tuple[CommandHistory, HistoryApplyUseCase]:
    """Connect a real history stack to the structure history handler."""
    history = CommandHistory()
    usecase = build_usecase(
        project_provider=lambda: project, refresh_port=refresh_port or FakeHistoryRefreshPort()
    )
    history.set_applier(usecase)
    return history, usecase


def _revision(project: SpectroscopyProject, region_id: str) -> int | None:
    """Return the current revision for one present region."""
    state = project.region_analysis_state(region_id)
    return None if state is None else state.current_revision.value


@pytest.mark.parametrize("operation", ["split", "merge", "delete", "unlink"])
def test_structure_history_undo_redo_keeps_survivors_stale(operation: str) -> None:
    """Every structure history direction advances survivors and resets recreated regions."""
    linked = operation == "unlink"
    if operation == "merge":
        initial = (("primary", ("line-1",)), ("secondary", ("line-2",)))
    else:
        initial = (("source", ("line-1", "line-2")), ("other", ("line-3",)))
    project, artifacts = _project(initial, linked=linked)
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    use_case = StructureOperationUseCase()

    if operation == "split":
        result = use_case.split_lines(
            project, linked_line_ids=["line-1"], history_recorder=recorder
        )
        assert result is not None and result.new_region is not None
        created_id = result.new_region.region_id
        assert _revision(project, "source") == 2
        assert _revision(project, created_id) == 0
    elif operation == "merge":
        assert use_case.merge_regions(
            project, group_ids=["primary", "secondary"], history_recorder=recorder
        )
        assert _revision(project, "primary") == 2
        assert _revision(project, "secondary") is None
    elif operation == "delete":
        assert use_case.delete_selection(
            project, group_ids=[], linked_line_ids=["line-1"], history_recorder=recorder
        )
        assert _revision(project, "source") == 2
        assert _revision(project, "other") == 1
    else:
        assert use_case.unlink_linked_lines(project, line_id="line-1", history_recorder=recorder)
        assert _revision(project, "source") == 2
        assert all(not line.multiplet_ids for line in project.absorption_lines.values())

    assert history.undo().success
    survivor = "primary" if operation == "merge" else "source"
    assert _revision(project, survivor) == 3
    assert project.region_analysis_state(survivor).artifact is artifacts[survivor]  # type: ignore[union-attr]
    if operation == "split":
        assert _revision(project, created_id) is None
    elif operation == "merge":
        assert _revision(project, "secondary") == 0
    elif operation == "unlink":
        assert project.absorption_lines["line-1"].multiplet_ids == ["line-2"]

    assert history.redo().success
    assert _revision(project, survivor) == 4
    if operation == "split":
        assert _revision(project, created_id) == 0
    elif operation == "merge":
        assert _revision(project, "secondary") is None
    elif operation == "unlink":
        assert all(not line.multiplet_ids for line in project.absorption_lines.values())


def test_region_delete_history_tracks_surviving_cross_region_backlink_revisions() -> None:
    """Delete Undo/Redo must declare and invalidate a surviving backlink exactly once."""
    project, artifacts = _project(
        (("deleted", ("line-deleted",)), ("survivor", ("line-survivor",)))
    )
    project.absorption_lines["line-deleted"].multiplet_ids = ["line-survivor"]
    project.absorption_lines["line-survivor"].multiplet_ids = ["line-deleted"]
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)

    assert StructureOperationUseCase().delete_selection(
        project, group_ids=["deleted"], linked_line_ids=[], history_recorder=recorder
    )
    assert "line-deleted" not in project.absorption_lines
    assert project.absorption_lines["line-survivor"].multiplet_ids == []
    assert _revision(project, "deleted") is None
    assert _revision(project, "survivor") == 2

    assert history.undo().success
    assert project.absorption_lines["line-deleted"].multiplet_ids == ["line-survivor"]
    assert project.absorption_lines["line-survivor"].multiplet_ids == ["line-deleted"]
    assert _revision(project, "deleted") == 0
    assert _revision(project, "survivor") == 3
    survivor_state = project.region_analysis_state("survivor")
    assert survivor_state is not None
    assert survivor_state.artifact is artifacts["survivor"]
    assert project.absorption_lines["line-survivor"].needs_optimization is True

    assert history.redo().success
    assert "line-deleted" not in project.absorption_lines
    assert project.absorption_lines["line-survivor"].multiplet_ids == []
    assert _revision(project, "deleted") is None
    assert _revision(project, "survivor") == 4


def test_region_delete_backlink_history_rebuild_failure_rolls_back_exactly(
    monkeypatch: MonkeyPatch,
) -> None:
    """A backlink Undo failure restores topology, revisions, flags, and stack."""
    project, _artifacts = _project(
        (("deleted", ("line-deleted",)), ("survivor", ("line-survivor",)))
    )
    project.absorption_lines["line-deleted"].multiplet_ids = ["line-survivor"]
    project.absorption_lines["line-survivor"].multiplet_ids = ["line-deleted"]
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().delete_selection(
        project, group_ids=["deleted"], linked_line_ids=[], history_recorder=recorder
    )
    before = _exact_state(project)
    history_before = history.get_state()
    original_rebuild = project.model.rebuild_model_storage

    def fail_rebuild() -> DomainChangeSet:
        original_rebuild()
        raise RuntimeError("injected backlink history rebuild failure")

    monkeypatch.setattr(project.model, "rebuild_model_storage", fail_rebuild)
    with pytest.raises(RuntimeError, match="injected backlink history rebuild failure"):
        history.undo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_region_delete_backlink_history_stale_preflight_keeps_stack() -> None:
    """Surviving-link drift must fail before a delete Undo mutates storage."""
    project, _artifacts = _project(
        (("deleted", ("line-deleted",)), ("survivor", ("line-survivor",)))
    )
    project.absorption_lines["line-deleted"].multiplet_ids = ["line-survivor"]
    project.absorption_lines["line-survivor"].multiplet_ids = ["line-deleted"]
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().delete_selection(
        project, group_ids=["deleted"], linked_line_ids=[], history_recorder=recorder
    )
    project.absorption_lines["line-survivor"].multiplet_ids = ["external-drift"]
    before = _exact_state(project)
    history_before = history.get_state()

    with pytest.raises(HistoryApplyError, match="source state is not exact"):
        history.undo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_delete_model_topology_round_trips_and_invalidates_all_survivors() -> None:
    """Delete history restores linked models while every surviving region stays stale."""
    project, artifacts = _project((("source", ("line-1", "line-2")), ("other", ("line-3",))))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)

    assert StructureOperationUseCase().delete_selection(
        project, group_ids=[], linked_line_ids=["line-1"], history_recorder=recorder
    )
    assert project.find_absorber_component(component.id) is None
    assert _revision(project, "source") == 2
    assert _revision(project, "other") == 2

    assert history.undo().success
    restored = project.find_absorber_component(component.id)
    assert restored is not None
    assert project.absorption_lines["line-1"].model_ids == [component.id]
    assert _revision(project, "source") == 3
    assert _revision(project, "other") == 3
    assert project.region_analysis_state("source").artifact is artifacts["source"]  # type: ignore[union-attr]
    assert project.region_analysis_state("other").artifact is artifacts["other"]  # type: ignore[union-attr]

    assert history.redo().success
    assert project.find_absorber_component(component.id) is None
    assert _revision(project, "source") == 4
    assert _revision(project, "other") == 4


def _exact_state(project: SpectroscopyProject) -> tuple[object, ...]:
    """Capture exact mutable facts required by rollback assertions."""
    return (
        tuple(
            (key, id(region), tuple(region.line_ids), region.display_color)
            for key, region in project.absorption_regions.items()
        ),
        tuple(
            (
                key,
                id(line),
                line.region_id,
                tuple(line.multiplet_ids),
                tuple(line.model_ids),
                line.needs_optimization,
            )
            for key, line in project.absorption_lines.items()
        ),
        tuple((id(component), component.id) for component in project.model.components),
        project.stored_region_analysis_states_for_transaction(),
        project.modified,
        project.model.snapshot_derived_state_for_transaction(),
    )


@pytest.mark.parametrize("operation", ["split", "merge", "delete"])
def test_structure_history_rebuild_failure_rolls_back_state_and_stack(
    operation: str, monkeypatch: MonkeyPatch
) -> None:
    """A post-mutation failure restores topology, freshness, caches, and history position."""
    project, _artifacts = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    use_case = StructureOperationUseCase()
    if operation == "split":
        assert use_case.split_lines(project, linked_line_ids=["line-1"], history_recorder=recorder)
    elif operation == "merge":
        assert use_case.merge_regions(
            project, group_ids=["source", "target"], history_recorder=recorder
        )
    else:
        assert use_case.delete_selection(
            project, group_ids=[], linked_line_ids=["line-1"], history_recorder=recorder
        )
    before = _exact_state(project)
    history_before = history.get_state()
    original_rebuild = project.model.rebuild_model_storage

    def fail_rebuild() -> DomainChangeSet:
        original_rebuild()
        raise RuntimeError("injected structure history rebuild failure")

    monkeypatch.setattr(project.model, "rebuild_model_storage", fail_rebuild)
    with pytest.raises(RuntimeError, match="injected structure history rebuild failure"):
        history.undo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_structure_history_exact_preflight_rejects_drift_without_stack_change() -> None:
    """Unrelated topology drift is rejected before an Undo mutates anything."""
    project, _artifacts = _project((("source", ("line-1", "line-2")),))
    history, _usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().split_lines(
        project, linked_line_ids=["line-1"], history_recorder=recorder
    )
    destination = next(
        region_id for region_id in project.absorption_regions if region_id != "source"
    )
    project.absorption_regions[destination].display_color = "#ffffff"
    history_before = history.get_state()

    with pytest.raises(HistoryApplyError, match="source state is not exact"):
        history.undo()

    assert history.get_state() == history_before
    assert project.absorption_regions[destination].display_color == "#ffffff"


def test_structure_history_postcondition_failure_rolls_back_exactly(
    monkeypatch: MonkeyPatch,
) -> None:
    """A command that misses its declared target topology cannot commit."""
    project, _artifacts = _project((("source", ("line-1", "line-2")),))
    history, usecase = _history(project)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().split_lines(
        project, linked_line_ids=["line-1"], history_recorder=recorder
    )
    before = _exact_state(project)
    history_before = history.get_state()
    original_apply = usecase._structure_applier.apply_absorption_region_states_exact

    def corrupt_after_apply(snapshots: tuple[object, ...]) -> object:
        change_set = original_apply(snapshots)  # type: ignore[arg-type]
        project.absorption_regions["source"].display_color = "#badbad"
        return change_set

    monkeypatch.setattr(
        usecase._structure_applier, "apply_absorption_region_states_exact", corrupt_after_apply
    )
    with pytest.raises(HistoryApplyError, match="source state is not exact"):
        history.undo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_structure_history_observer_failures_are_isolated() -> None:
    """Committed structure state reaches later domain observers after a failure."""
    project, _artifacts = _project((("source", ("line-1", "line-2")),))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    refresh_port = FakeHistoryRefreshPort()
    history, _usecase = _history(project, refresh_port=refresh_port)
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().split_lines(
        project, linked_line_ids=["line-1"], history_recorder=recorder
    )
    observed: list[object] = []

    def fail_domain_observer(_event: object) -> None:
        raise RuntimeError("injected domain observer failure")

    project.model.events.subscribe(fail_domain_observer)
    project.model.events.subscribe(observed.append)

    assert history.undo().success
    assert observed
    assert refresh_port.targets() == ()
