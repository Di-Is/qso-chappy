"""Atomic Identify registration history integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chappy.application.history import (
    AbsorptionRegionSnapshot,
    HistoryApplyError,
    HistoryRefreshTarget,
    IdentifyRegisterSelectedCommand,
)
from chappy.application.history.snapshot_mapping import (
    absorption_line_snapshot,
    absorption_region_snapshot,
    temporary_line_from_snapshot,
    temporary_line_snapshot,
)
from chappy.application.identify import TemporaryLineSnapshot
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.history import CommandHistory, HistoryEvent
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.velocity_ranges import LineAnalysisHalfWidth

from history_apply_fakes import FakeHistoryRefreshPort, build_usecase

if TYPE_CHECKING:
    from pytest import MonkeyPatch

    from chappy.application.history import ChangeSet
    from chappy.application.history.apply.usecase import HistoryApplyUseCase


def _line(line_id: str, region_id: str) -> AbsorptionLine:
    """Build one Identify-created line."""
    return AbsorptionLine(
        line_id=line_id,
        species="C IV",
        rest_wavelength=1548.2,
        center_z=2.0,
        window_kms=200.0,
        multiplet_label="C IV",
        transition_name="1548",
        oscillator_strength=0.19,
        gamma_value=2.64e8,
        lambda_range=(1547.0, 1549.0),
        region_id=region_id,
        needs_optimization=True,
        created_by="identify",
    )


def _temporary_line() -> TemporaryLineSnapshot:
    """Build the consumed temporary-line snapshot."""
    return TemporaryLineSnapshot(
        temporary_line_id="temporary-line",
        species="C IV",
        lambda_min=1547.0,
        lambda_max=1549.0,
        creation_method="manual",
        line_id="atomic-line",
        rest_wavelength=1548.2,
        center_z=2.0,
        multiplet_id="civ",
        multiplet_label="C IV",
        transition_name="1548",
        oscillator_strength=0.19,
        gamma_value=2.64e8,
        analysis_half_width=LineAnalysisHalfWidth(200.0),
        tie_group_key="",
    )


def _fixture(
    *, created_region: bool, refresh_port: FakeHistoryRefreshPort | None = None
) -> tuple[SpectroscopyProject, CommandHistory, HistoryApplyUseCase, str, AnalysisArtifact | None]:
    """Build the committed after-state and matching registration command."""
    project = SpectroscopyProject()
    region_id = "region"
    created_at = datetime(2020, 1, 1, tzinfo=UTC)
    existing_line_ids: tuple[str, ...] = () if created_region else ("existing",)
    if not created_region:
        project.absorption_lines["existing"] = _line("existing", region_id)
    project.absorption_lines["created"] = _line("created", region_id)
    region = AbsorptionRegion(
        region_id=region_id,
        line_ids=[*existing_line_ids, "created"],
        display_color="#123456",
        analysis_range=(1547.0, 1549.0),
        created_at=created_at,
    )
    project.absorption_regions[region_id] = region
    artifact: AnalysisArtifact | None = None
    if created_region:
        project.set_region_analysis_state(RegionAnalysisState(region_id, AnalysisRevision()))
        before_regions: tuple[AbsorptionRegionSnapshot, ...] = ()
    else:
        revision = AnalysisRevision(2)
        artifact = AnalysisArtifact(
            region_id=region_id,
            source_revision=AnalysisRevision(1),
            fit_summary=FitSummary(chi_squared=1.0),
        )
        project.set_region_analysis_state(RegionAnalysisState(region_id, revision, artifact))
        before_regions = (
            AbsorptionRegionSnapshot(
                region_id=region_id,
                line_ids=existing_line_ids,
                display_color=region.display_color,
                analysis_range=region.analysis_range,
                created_at=region.created_at,
            ),
        )
    command = IdentifyRegisterSelectedCommand(
        created_line_ids=("created",),
        removed_temporary_line_ids=("temporary-line",),
        temporary_line_snapshots=(_temporary_line(),),
        affected_region_ids=(region_id,),
        line_snapshots=(absorption_line_snapshot(project.absorption_lines["created"]),),
        before_affected_region_snapshots=before_regions,
        after_affected_region_snapshots=(absorption_region_snapshot(region),),
    )
    history = CommandHistory()
    usecase = build_usecase(
        project_provider=lambda: project, refresh_port=refresh_port or FakeHistoryRefreshPort()
    )
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=command))
    return project, history, usecase, region_id, artifact


def _exact_state(project: SpectroscopyProject) -> tuple[object, ...]:
    """Capture all Identify registration state that preflight must leave untouched."""
    return (
        tuple(
            (key, absorption_region_snapshot(region))
            for key, region in project.absorption_regions.items()
        ),
        tuple(
            (key, absorption_line_snapshot(line)) for key, line in project.absorption_lines.items()
        ),
        tuple(temporary_line_snapshot(item) for item in project.identify_state.temporary_lines),
        project.stored_region_analysis_states_for_transaction(),
        project.modified,
        project.model.snapshot_derived_state_for_transaction(),
    )


@pytest.mark.parametrize("created_region", [False, True])
def test_registration_undo_redo_revision_and_temporary_line_matrix(created_region: bool) -> None:
    """Undo/Redo stales survivors and resets only recreated regions."""
    project, history, _usecase, region_id, artifact = _fixture(created_region=created_region)

    assert history.undo().success
    assert "created" not in project.absorption_lines
    assert [item.temporary_line_id for item in project.identify_state.temporary_lines] == [
        "temporary-line"
    ]
    if created_region:
        assert region_id not in project.absorption_regions
    else:
        state = project.region_analysis_state(region_id)
        assert state is not None
        assert state.current_revision == AnalysisRevision(3)
        assert state.artifact is artifact

    assert history.redo().success
    assert project.identify_state.temporary_lines == []
    assert "created" in project.absorption_lines
    state = project.region_analysis_state(region_id)
    assert state is not None
    assert state.current_revision == AnalysisRevision(0 if created_region else 4)
    assert state.artifact is (None if created_region else artifact)


def test_registration_failure_restores_temporary_lines_topology_and_stack(
    monkeypatch: MonkeyPatch,
) -> None:
    """A mid-command failure rolls temporary-line session and project back together."""
    project, history, usecase, _region_id, _artifact = _fixture(created_region=False)
    history_before = history.get_state()
    line_ids_before = tuple(project.absorption_lines)
    original_apply = usecase._structure_applier.apply_absorption_region_states_partial_exact

    def fail_after_apply(snapshots: tuple[AbsorptionRegionSnapshot, ...]) -> ChangeSet:
        result = original_apply(snapshots)
        raise RuntimeError("injected Identify history failure")

    monkeypatch.setattr(
        usecase._structure_applier,
        "apply_absorption_region_states_partial_exact",
        fail_after_apply,
    )
    with pytest.raises(RuntimeError, match="injected Identify history failure"):
        history.undo()

    assert tuple(project.absorption_lines) == line_ids_before
    assert project.identify_state.temporary_lines == []
    assert history.get_state() == history_before


@pytest.mark.parametrize("drift", ["temporary_line", "line", "region"])
def test_registration_exact_preflight_rejects_stale_after_state(drift: str) -> None:
    """Undo rejects stale temporary lines, created lines, and regions before mutation."""
    project, history, _usecase, region_id, _artifact = _fixture(created_region=False)
    if drift == "temporary_line":
        project.identify_state.restore_temporary_line(
            temporary_line_from_snapshot(_temporary_line())
        )
    elif drift == "line":
        project.absorption_lines["created"].species = "stale"
    else:
        project.absorption_regions[region_id].display_color = "#ffffff"
    before = _exact_state(project)
    history_before = history.get_state()

    with pytest.raises(HistoryApplyError, match="state is not exact|still exists"):
        history.undo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_registration_redo_rejects_created_region_collision_before_mutation() -> None:
    """Redo cannot overwrite a newly occupied registration region identity."""
    project, history, _usecase, region_id, _artifact = _fixture(created_region=True)
    assert history.undo().success
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=[], display_color="#abcdef", analysis_range=(1.0, 2.0)
    )
    before = _exact_state(project)
    history_before = history.get_state()

    with pytest.raises(HistoryApplyError, match="already exists"):
        history.redo()

    assert _exact_state(project) == before
    assert history.get_state() == history_before


def test_registration_postcommit_observer_failure_is_isolated() -> None:
    """A failed Identify refresh cannot misreport committed registration as rolled back."""
    refresh_port = FakeHistoryRefreshPort(
        fail_targets=frozenset({HistoryRefreshTarget.IDENTIFY_PANEL})
    )
    project, history, _usecase, _region_id, _artifact = _fixture(
        created_region=False, refresh_port=refresh_port
    )

    assert history.undo().success

    assert "created" not in project.absorption_lines
    assert refresh_port.targets() == (HistoryRefreshTarget.IDENTIFY_PANEL,)
