"""Atomic forward-move contract tests for structure structure editing."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chappy.application.history import StructureMoveHistoryPayload
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.application.structure import (
    StructureTopologyProjectPort,
    StructureTopologySnapshot,
    StructureTopologySnapshotService,
)
from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.masking import MaskDefinition, MaskMode
from chappy.core.spectroscopy_project import SpectroscopyProject

if TYPE_CHECKING:
    from pytest import MonkeyPatch


@dataclass(slots=True)
class _History:
    """Failure-injectable atomic move history recorder."""

    entries: list[StructureMoveHistoryPayload] = field(default_factory=list)
    scope_entries: int = 0
    fail_record: bool = False

    @contextmanager
    def atomic_recording(self) -> Iterator[None]:
        """Restore exact entries after a recording failure."""
        self.scope_entries += 1
        snapshot = list(self.entries)
        try:
            yield
        except Exception:
            self.entries = snapshot
            raise

    def record_structure_move_linked_lines(self, payload: StructureMoveHistoryPayload) -> None:
        """Append one payload and optionally fail afterward."""
        self.entries.append(payload)
        if self.fail_record:
            raise RuntimeError("injected history failure")


@dataclass(slots=True)
class _StructureHistory:
    """Failure-injectable recorder shared by split, merge, and delete tests."""

    entries: list[str] = field(default_factory=list)
    scope_entries: int = 0
    fail_record: bool = False

    @contextmanager
    def atomic_recording(self) -> Iterator[None]:
        """Restore exact entries after a recording failure."""
        self.scope_entries += 1
        snapshot = list(self.entries)
        try:
            yield
        except Exception:
            self.entries = snapshot
            raise

    def _record(self, operation: str) -> None:
        """Append one operation and optionally fail afterward."""
        self.entries.append(operation)
        if self.fail_record:
            raise RuntimeError("injected history failure")

    def record_structure_move_linked_lines(self, _payload: StructureMoveHistoryPayload) -> None:
        """Record an atomic move."""
        self._record("move")

    def record_structure_split(self, **_payload: object) -> None:
        """Record an atomic split."""
        self._record("split")

    def record_structure_merge(self, **_payload: object) -> None:
        """Record an atomic merge."""
        self._record("merge")

    def record_structure_delete(self, **_payload: object) -> None:
        """Record an atomic delete."""
        self._record("delete")

    def record_structure_unlink(self, _payload: object) -> None:
        """Record an atomic linked-line unlink."""
        self._record("unlink")


class _ExplodingTopology(StructureTopologySnapshotService):
    """Snapshot service proving NoChange does not enter the transaction."""

    def capture(self, project: StructureTopologyProjectPort) -> StructureTopologySnapshot:
        """Reject any attempt to enter runtime capture."""
        raise AssertionError("NoChange captured runtime topology")


def _line(
    line_id: str,
    region_id: str,
    *,
    multiplet_ids: tuple[str, ...] = (),
    model_ids: tuple[str, ...] = (),
) -> AbsorptionLine:
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
        model_ids=list(model_ids),
        needs_optimization=False,
    )


def _analysis_state(region_id: str, revision: int = 1) -> RegionAnalysisState:
    """Build one analyzed region with retained evidence."""
    current = AnalysisRevision(revision)
    return RegionAnalysisState(
        region_id=region_id,
        current_revision=current,
        artifact=AnalysisArtifact(
            region_id=region_id,
            source_revision=current,
            fit_summary=FitSummary(chi_squared=float(revision)),
        ),
    )


def _project(
    regions: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    multiplets: dict[str, tuple[str, ...]] | None = None,
) -> SpectroscopyProject:
    """Build a project with deterministic region, line, and analysis order."""
    project = SpectroscopyProject()
    multiplets = multiplets or {}
    for region_id, line_ids in regions:
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id,
            line_ids=list(line_ids),
            display_color=f"#{len(project.absorption_regions) + 1:06d}",
        )
        for line_id in line_ids:
            project.absorption_lines[line_id] = _line(
                line_id, region_id, multiplet_ids=multiplets.get(line_id, ())
            )
    project.set_region_analysis_states(
        _analysis_state(region_id) for region_id in project.absorption_regions
    )
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project


@pytest.mark.parametrize(
    ("regions", "line_ids", "target", "expected_revisions", "creates_region", "removed"),
    [
        (
            (("source", ("line-1", "line-2")), ("target", ("line-3",))),
            ["line-1"],
            "target",
            {"source": 2, "target": 2},
            False,
            (),
        ),
        (
            (("source", ("line-1",)), ("target", ("line-2",))),
            ["line-1"],
            "target",
            {"target": 2},
            False,
            ("source",),
        ),
        ((("source", ("line-1", "line-2")),), ["line-1"], None, {"source": 2}, True, ()),
        ((("source", ("line-1",)),), ["line-1"], None, {}, True, ("source",)),
        (
            ((UNASSIGNED_REGION_ID, ("line-1",)), ("target", ("line-2",))),
            ["line-1"],
            "target",
            {UNASSIGNED_REGION_ID: 2, "target": 2},
            False,
            (),
        ),
    ],
    ids=[
        "existing-survives",
        "existing-source-removed",
        "new-destination-source-survives",
        "new-destination-source-removed",
        "unassigned",
    ],
)
def test_forward_move_revision_matrix(
    regions: tuple[tuple[str, tuple[str, ...]], ...],
    line_ids: list[str],
    target: str | None,
    expected_revisions: dict[str, int],
    creates_region: bool,
    removed: tuple[str, ...],
) -> None:
    """Forward moves invalidate exact survivors and reset only created regions."""
    project = _project(regions)
    artifacts = {
        region_id: project.region_analysis_state(region_id).artifact  # type: ignore[union-attr]
        for region_id, _line_ids in regions
    }
    history = _History()

    result = StructureOperationUseCase().move_lines(
        project, line_ids=line_ids, target_region_id=target, history_recorder=history
    )

    assert result is not None
    payload = history.entries[0]
    assert history.scope_entries == 1
    for region_id, revision in expected_revisions.items():
        state = project.region_analysis_state(region_id)
        assert state is not None
        assert state.current_revision == AnalysisRevision(revision)
        assert state.artifact is artifacts[region_id]
    assert payload.created_new_region is creates_region
    if creates_region:
        created_id = result.destination_id
        assert created_id not in artifacts
        assert created_id == payload.destination_region_id
        state = project.region_analysis_state(created_id)
        assert state == RegionAnalysisState(created_id, AnalysisRevision())
    for region_id in removed:
        assert project.region_analysis_state(region_id) is None
    assert tuple(snapshot.region_id for snapshot in payload.auto_deleted_regions) == removed
    affected_current_ids = (
        *expected_revisions,
        *((result.destination_id,) if creates_region else ()),
    )
    assert all(
        project.absorption_lines[line_id].needs_optimization
        for region_id in affected_current_ids
        for line_id in project.absorption_regions[region_id].line_ids
    )


@pytest.mark.parametrize("selected", [["blue"], ["blue", "red"]], ids=["one-seed", "both-seeds"])
def test_multiplet_expansion_moves_one_linked_line_and_all_member_lines(
    selected: list[str],
) -> None:
    """A selected multiplet seed moves its complete component but counts one linked line."""
    project = _project(
        (("source", ("blue", "red", "other")), ("target", ("target-line",))),
        multiplets={"blue": ("red",), "red": ("blue",)},
    )
    history = _History()

    result = StructureOperationUseCase().move_lines(
        project, line_ids=selected, target_region_id="target", history_recorder=history
    )

    assert result is not None
    assert result.moved_linked_line_count == 1
    assert history.entries[0].expanded_line_ids == ("blue", "red")
    assert project.absorption_regions["source"].line_ids == ["other"]
    assert project.absorption_regions["target"].line_ids == ["target-line", "blue", "red"]


@pytest.mark.parametrize("line_ids", [[], ["line-1"]], ids=["empty", "same-target"])
def test_no_change_skips_topology_and_history_scopes(line_ids: list[str]) -> None:
    """Empty and same-target requests stay inert before transaction snapshots."""
    project = _project((("source", ("line-1",)),))
    history = _History()
    modified = project.modified

    result = StructureOperationUseCase(topology=_ExplodingTopology()).move_lines(
        project, line_ids=line_ids, target_region_id="source", history_recorder=history
    )

    assert result is None
    assert history.scope_entries == 0
    assert history.entries == []
    assert project.modified == modified
    assert project.region_analysis_state("source") == _analysis_state("source")


@pytest.mark.parametrize(
    "line_ids",
    [["line-1", "missing"], ["missing"], ["line-1", "line-1"]],
    ids=["partial-missing", "all-missing", "duplicate"],
)
def test_invalid_requested_identity_aborts_before_partial_move(line_ids: list[str]) -> None:
    """Any missing or duplicate requested ID rejects the complete move request."""
    project = _project((("source", ("line-1",)), ("target", ("line-2",))))
    history = _History()
    before = _exact_state(project, history)

    with pytest.raises(ValueError):
        StructureOperationUseCase(topology=_ExplodingTopology()).move_lines(
            project, line_ids=line_ids, target_region_id="target", history_recorder=history
        )

    assert _exact_state(project, history) == before
    assert history.scope_entries == 0


def test_historyless_programmatic_move_keeps_atomic_science_without_undo_entry() -> None:
    """Non-interactive clients may deliberately omit history while retaining atomic science."""
    project = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))

    result = StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=None
    )

    assert result is not None
    assert project.region_analysis_state("source").current_revision == AnalysisRevision(2)  # type: ignore[union-attr]
    assert project.region_analysis_state("target").current_revision == AnalysisRevision(2)  # type: ignore[union-attr]


def _rollback_fixture() -> tuple[SpectroscopyProject, _History]:
    """Build a move that changes masks and component groups when its source is deleted."""
    project = _project((("source", ("line-1",)), ("target", ("line-2",))))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    mask = MaskDefinition(
        identifier="mask",
        label="source mask",
        mode=MaskMode.RANGE,
        start_wavelength=1000.0,
        end_wavelength=1010.0,
        group_id="source",
    )
    project.model.restore_mask_definitions_for_transaction((mask,), model_was_valid=False)
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project, _History()


def _exact_state(
    project: SpectroscopyProject, history: _History | _StructureHistory
) -> tuple[object, ...]:
    """Return serialization-equivalent state plus runtime identity and order."""
    return (
        tuple(
            (
                key,
                id(region),
                region.region_id,
                tuple(region.line_ids),
                region.display_color,
                region.analysis_range,
                region.created_at,
            )
            for key, region in project.absorption_regions.items()
        ),
        tuple(
            (
                key,
                id(line),
                line.line_id,
                line.region_id,
                tuple(line.multiplet_ids),
                tuple(line.model_ids),
                line.needs_optimization,
            )
            for key, line in project.absorption_lines.items()
        ),
        tuple((id(mask), mask) for mask in project.model.mask_definitions),
        tuple(
            (id(component), component.id, component.group_id, component.tie_set)
            for component in project.model.components
            if isinstance(component, AbsorberComponent)
        ),
        project.stored_region_analysis_states_for_transaction(),
        project.modified,
        project.model.snapshot_derived_state_for_transaction(),
        tuple(history.entries),
    )


@pytest.mark.parametrize("stage", ["mid-move", "derived", "invalidation", "history"])
def test_failure_matrix_restores_exact_state_and_suppresses_observers(
    stage: str, monkeypatch: MonkeyPatch
) -> None:
    """Every forward stage restores topology, evidence, cache, flags, and history exactly."""
    project, history = _rollback_fixture()
    before = _exact_state(project, history)
    observed: list[object] = []
    project.model.events.subscribe(observed.append)

    if stage == "mid-move":
        original_move = project.move_absorption_lines

        def fail_move(line_ids: list[str], *, target_region_id: str | None) -> str | None:
            original_move(line_ids, target_region_id=target_region_id)
            raise RuntimeError("injected mid-move failure")

        monkeypatch.setattr(project, "move_absorption_lines", fail_move)
    elif stage == "derived":
        original_rebuild = project.model.rebuild_model_storage

        def fail_rebuild():  # type: ignore[no-untyped-def]
            original_rebuild()
            raise RuntimeError("injected derived failure")

        monkeypatch.setattr(project.model, "rebuild_model_storage", fail_rebuild)
    elif stage == "invalidation":
        original_set = project.set_region_analysis_states

        def fail_invalidation(states):  # type: ignore[no-untyped-def]
            original_set(states)
            raise RuntimeError("injected invalidation failure")

        monkeypatch.setattr(project, "set_region_analysis_states", fail_invalidation)
    else:
        history.fail_record = True

    with pytest.raises(RuntimeError, match="injected"):
        StructureOperationUseCase().move_lines(
            project, line_ids=["line-1"], target_region_id="target", history_recorder=history
        )

    assert _exact_state(project, history) == before
    assert observed == []


def test_source_deletion_moves_component_drops_masks_and_isolates_postcommit_observers() -> None:
    """Commit publishes after masks/groups are final and one bad listener cannot block another."""
    project, history = _rollback_fixture()
    observed: list[object] = []

    def fail_observer(_changes: object) -> None:
        raise RuntimeError("observer failure")

    project.model.events.subscribe(fail_observer)
    project.model.events.subscribe(observed.append)

    result = StructureOperationUseCase().move_lines(
        project, line_ids=["line-1"], target_region_id="target", history_recorder=history
    )

    assert result is not None
    assert "source" not in project.absorption_regions
    assert project.model.mask_definitions == ()
    component = next(
        component
        for component in project.model.components
        if isinstance(component, AbsorberComponent)
    )
    assert component.group_id == "target"
    assert observed


@pytest.mark.parametrize("source_line_ids", [("line-1", "line-2"), ("line-1",)])
def test_forward_split_resets_created_region_and_invalidates_only_surviving_source(
    source_line_ids: tuple[str, ...],
) -> None:
    """Split preserves stale source evidence while a created region starts at revision zero."""
    project = _project((("source", source_line_ids),))
    source_artifact = project.region_analysis_state("source").artifact  # type: ignore[union-attr]
    history = _StructureHistory()

    result = StructureOperationUseCase().split_lines(
        project,
        linked_line_ids=["line-1"],
        history_recorder=history,  # type: ignore[arg-type]
    )

    assert result is not None
    assert result.new_region is not None
    created_id = result.new_region.region_id
    assert project.region_analysis_state(created_id) == RegionAnalysisState(
        created_id, AnalysisRevision()
    )
    assert project.absorption_lines["line-1"].needs_optimization
    if len(source_line_ids) == 1:
        assert project.region_analysis_state("source") is None
    else:
        source_state = project.region_analysis_state("source")
        assert source_state is not None
        assert source_state.current_revision == AnalysisRevision(2)
        assert source_state.artifact is source_artifact
        assert project.absorption_lines["line-2"].needs_optimization
    assert history.entries == ["split"]
    assert history.scope_entries == 1


def test_forward_merge_invalidates_primary_and_removes_secondary_analysis_state() -> None:
    """Merge advances its surviving primary once and prunes all merged-away evidence."""
    project = _project((("primary", ("line-1",)), ("secondary", ("line-2",))))
    primary_artifact = project.region_analysis_state("primary").artifact  # type: ignore[union-attr]
    history = _StructureHistory()

    result = StructureOperationUseCase().merge_regions(
        project,
        group_ids=["primary", "secondary"],
        history_recorder=history,  # type: ignore[arg-type]
    )

    assert result is not None
    assert result.merged_region.region_id == "primary"
    primary_state = project.region_analysis_state("primary")
    assert primary_state is not None
    assert primary_state.current_revision == AnalysisRevision(2)
    assert primary_state.artifact is primary_artifact
    assert project.region_analysis_state("secondary") is None
    assert all(line.needs_optimization for line in project.absorption_lines.values())
    assert history.entries == ["merge"]
    assert history.scope_entries == 1


def test_forward_delete_with_model_removal_invalidates_every_surviving_region() -> None:
    """Deleting linked model structure applies the global survivor invalidation rule."""
    project = _project((("source", ("line-1", "line-2")), ("other", ("line-3",))))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    history = _StructureHistory()

    result = StructureOperationUseCase().delete_selection(
        project,
        group_ids=[],
        linked_line_ids=["line-1"],
        history_recorder=history,  # type: ignore[arg-type]
    )

    assert result is not None
    assert result.groups_removed == 0
    assert result.lines_removed == 1
    assert component not in project.model.components
    assert project.region_analysis_state("source").current_revision == AnalysisRevision(2)  # type: ignore[union-attr]
    assert project.region_analysis_state("other").current_revision == AnalysisRevision(2)  # type: ignore[union-attr]
    assert history.entries == ["delete"]
    assert history.scope_entries == 1


def test_forward_unlink_invalidates_every_region_containing_changed_lines() -> None:
    """Unlink clears one linked-line group and advances each owning region once."""
    project = _project(
        (("first", ("blue",)), ("second", ("red",))),
        multiplets={"blue": ("red",), "red": ("blue",)},
    )
    artifacts = {
        region_id: project.region_analysis_state(region_id).artifact  # type: ignore[union-attr]
        for region_id in ("first", "second")
    }
    history = _StructureHistory()

    result = StructureOperationUseCase().unlink_linked_lines(
        project,
        line_id="blue",
        history_recorder=history,  # type: ignore[arg-type]
    )

    assert result is not None
    assert result.unlinked_line_ids == ("blue", "red")
    assert project.absorption_lines["blue"].multiplet_ids == []
    assert project.absorption_lines["red"].multiplet_ids == []
    for region_id in ("first", "second"):
        state = project.region_analysis_state(region_id)
        assert state is not None
        assert state.current_revision == AnalysisRevision(2)
        assert state.artifact is artifacts[region_id]
        assert project.absorption_lines[
            project.absorption_regions[region_id].line_ids[0]
        ].needs_optimization
    assert history.entries == ["unlink"]
    assert history.scope_entries == 1


def test_unlink_without_materialized_links_is_no_change() -> None:
    """An independent line never enters the transaction or changes freshness."""
    project = _project((("source", ("line-1",)),))
    history = _StructureHistory()
    modified = project.modified

    result = StructureOperationUseCase(topology=_ExplodingTopology()).unlink_linked_lines(
        project,
        line_id="line-1",
        history_recorder=history,  # type: ignore[arg-type]
    )

    assert result is None
    assert history.entries == []
    assert history.scope_entries == 0
    assert project.modified == modified
    assert project.region_analysis_state("source") == _analysis_state("source")


@pytest.mark.parametrize("operation", ["split", "merge", "delete", "unlink"])
def test_structure_history_failure_restores_exact_topology_and_scientific_state(
    operation: str,
) -> None:
    """Every remaining structure command rolls back model topology and evidence exactly."""
    project = _project((("source", ("line-1", "line-2")), ("target", ("line-3",))))
    component = AbsorberComponent(component_id="component", group_id="source")
    project.model.add_component(component)
    project.absorption_lines["line-1"].model_ids.append(component.id)
    if operation == "unlink":
        project.absorption_lines["line-1"].multiplet_ids.append("line-2")
        project.absorption_lines["line-2"].multiplet_ids.append("line-1")
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    history = _StructureHistory(fail_record=True)
    before = _exact_state(project, history)
    use_case = StructureOperationUseCase()

    with pytest.raises(RuntimeError, match="injected history failure"):
        if operation == "split":
            use_case.split_lines(
                project,
                linked_line_ids=["line-1"],
                history_recorder=history,  # type: ignore[arg-type]
            )
        elif operation == "merge":
            use_case.merge_regions(
                project,
                group_ids=["source", "target"],
                history_recorder=history,  # type: ignore[arg-type]
            )
        elif operation == "delete":
            use_case.delete_selection(
                project,
                group_ids=[],
                linked_line_ids=["line-1"],
                history_recorder=history,  # type: ignore[arg-type]
            )
        else:
            use_case.unlink_linked_lines(
                project,
                line_id="line-1",
                history_recorder=history,  # type: ignore[arg-type]
            )

    assert _exact_state(project, history) == before
    assert history.scope_entries == 1
