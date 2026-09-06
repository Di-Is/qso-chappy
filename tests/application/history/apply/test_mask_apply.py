"""Tests for atomic scientific mask history application."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np

import pytest

from chappy.application.history import HistoryApplyError, HistoryRefreshTarget, MaskHistoryCommand
from chappy.application.history.snapshot_mapping import mask_definition_snapshot
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.events import MasksChanged
from chappy.core.history import CommandHistory, HistoryEvent, OperationId
from chappy.core.masking import MaskDefinition, MaskMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum

from history_apply_fakes import FakeHistoryRefreshPort, build_usecase

if TYPE_CHECKING:
    from chappy.core.change_set import ChangeSet


def _mask(identifier: str, group_id: str, *, start: float = 5001.0) -> MaskDefinition:
    return MaskDefinition(
        identifier=identifier,
        label=identifier,
        mode=MaskMode.RANGE,
        start_wavelength=start,
        end_wavelength=start + 1.0,
        center=start + 0.5,
        half_width=0.5,
        group_id=group_id,
    )


def _line(line_id: str, region_id: str) -> AbsorptionLine:
    return AbsorptionLine(
        line_id=line_id,
        species="C IV",
        rest_wavelength=1548.2,
        center_z=2.0,
        window_kms=100.0,
        multiplet_label="C IV",
        transition_name=line_id,
        oscillator_strength=0.1,
        gamma_value=1e8,
        region_id=region_id,
        needs_optimization=False,
    )


def _project(masks: tuple[MaskDefinition, ...]) -> SpectroscopyProject:
    project = SpectroscopyProject()
    wavelength = np.linspace(5000.0, 5010.0, 40, dtype=np.float64)
    project.model.set_observed_spectrum(
        Spectrum(wavelength=wavelength, flux=np.ones_like(wavelength), error=None, header={})
    )
    for index in (1, 2):
        region_id = f"region-{index}"
        line = _line(f"line-{index}", region_id)
        project.absorption_lines[line.line_id] = line
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=[line.line_id]
        )
        revision = AnalysisRevision(1)
        project.set_region_analysis_state(
            RegionAnalysisState(
                region_id=region_id,
                current_revision=revision,
                artifact=AnalysisArtifact(
                    region_id=region_id,
                    source_revision=revision,
                    fit_summary=FitSummary(chi_squared=1.0),
                ),
            )
        )
    project.model.restore_mask_definitions_for_transaction(masks, model_was_valid=False)
    project.model.rebuild_model_storage()
    project.modified = datetime(2020, 1, 1, tzinfo=UTC)
    return project


def _history(
    project: SpectroscopyProject, command: MaskHistoryCommand
) -> tuple[CommandHistory, FakeHistoryRefreshPort]:
    history = CommandHistory()
    refresh_port = FakeHistoryRefreshPort()
    usecase = build_usecase(project_provider=lambda: project, refresh_port=refresh_port)
    history.set_applier(usecase)
    assert history.push(HistoryEvent(command=command))
    return history, refresh_port


def _delete_command(target: MaskDefinition, *, index: int) -> MaskHistoryCommand:
    return MaskHistoryCommand(
        op_id=OperationId.MASK_DELETE,
        mask_id=target.identifier,
        before=mask_definition_snapshot(target),
        after=None,
        before_index=index,
        after_index=None,
        affected_region_ids=(target.group_id,),  # type: ignore[arg-type]
    )


def test_mask_create_undo_redo_restores_exact_insertion_position() -> None:
    """Create history preserves collection order in both directions."""
    first = _mask("first", "region-1")
    target = _mask("target", "region-1", start=5003.0)
    last = _mask("last", "region-2", start=5005.0)
    project = _project((first, target, last))
    command = MaskHistoryCommand(
        op_id=OperationId.MASK_CREATE,
        mask_id=target.identifier,
        before=None,
        after=mask_definition_snapshot(target),
        before_index=None,
        after_index=1,
        affected_region_ids=("region-1",),
    )
    history, _refresh_port = _history(project, command)
    artifact = project.region_analysis_state("region-1").artifact  # type: ignore[union-attr]

    assert history.undo().success
    assert tuple(mask.identifier for mask in project.model.mask_definitions) == ("first", "last")
    assert history.redo().success
    assert tuple(mask.identifier for mask in project.model.mask_definitions) == (
        "first",
        "target",
        "last",
    )

    state = project.region_analysis_state("region-1")
    assert state is not None and state.current_revision == AnalysisRevision(3)
    assert state.artifact is artifact
    assert project.absorption_lines["line-1"].needs_optimization


def test_mask_delete_undo_redo_restores_exact_collection_order_and_stales_region() -> None:
    """Delete history recreates the original position and never revives freshness."""
    first = _mask("first", "region-1")
    target = _mask("target", "region-1", start=5003.0)
    last = _mask("last", "region-2", start=5005.0)
    project = _project((first, last))
    history, _refresh_port = _history(project, _delete_command(target, index=1))
    artifact = project.region_analysis_state("region-1").artifact  # type: ignore[union-attr]

    assert history.undo().success
    assert tuple(mask.identifier for mask in project.model.mask_definitions) == (
        "first",
        "target",
        "last",
    )
    assert history.redo().success
    assert tuple(mask.identifier for mask in project.model.mask_definitions) == ("first", "last")

    first_state = project.region_analysis_state("region-1")
    second_state = project.region_analysis_state("region-2")
    assert first_state is not None and first_state.current_revision == AnalysisRevision(3)
    assert first_state.artifact is artifact
    assert second_state is not None and second_state.current_revision == AnalysisRevision(1)
    assert project.absorption_lines["line-1"].needs_optimization
    assert not project.absorption_lines["line-2"].needs_optimization


def test_mask_update_invalidates_old_and_new_regions_once_with_deduped_scope() -> None:
    """Moving a mask stales both owning regions exactly once."""
    before = _mask("target", "region-1")
    after = _mask("target", "region-2", start=5002.0)
    project = _project((after,))
    command = MaskHistoryCommand(
        op_id=OperationId.MASK_EDIT,
        mask_id="target",
        before=mask_definition_snapshot(before),
        after=mask_definition_snapshot(after),
        before_index=0,
        after_index=0,
        affected_region_ids=("region-1", "region-2", "region-1"),
    )
    assert command.affected_region_ids == ("region-1", "region-2")
    history, _refresh_port = _history(project, command)

    assert history.undo().success

    assert project.model.mask_definitions == (before,)
    assert tuple(state.current_revision for state in project.region_analysis_states()) == (
        AnalysisRevision(2),
        AnalysisRevision(2),
    )
    assert all(line.needs_optimization for line in project.absorption_lines.values())

    assert history.redo().success

    assert project.model.mask_definitions == (after,)
    assert tuple(state.current_revision for state in project.region_analysis_states()) == (
        AnalysisRevision(3),
        AnalysisRevision(3),
    )
    assert all(line.needs_optimization for line in project.absorption_lines.values())


def test_mask_exact_target_is_no_change_without_notification_or_freshness_churn() -> None:
    """An already-absent create Undo target is completely inert."""
    target = _mask("target", "region-1")
    project = _project(())
    command = MaskHistoryCommand(
        op_id=OperationId.MASK_CREATE,
        mask_id=target.identifier,
        before=None,
        after=mask_definition_snapshot(target),
        before_index=None,
        after_index=0,
        affected_region_ids=("region-1",),
    )
    history, refresh_port = _history(project, command)
    states_before = project.region_analysis_states()
    modified_before = project.modified
    received: list[ChangeSet] = []
    project.model.events.subscribe(received.append)

    assert history.undo().success

    assert project.region_analysis_states() == states_before
    assert project.modified == modified_before
    assert not any(line.needs_optimization for line in project.absorption_lines.values())
    assert received == []
    assert refresh_port.region_ids_for(HistoryRefreshTarget.OPTIMIZE_PANEL) == []


def test_mask_update_missing_storage_target_is_recoverable_and_stack_safe() -> None:
    """A missing update source fails before mutation and keeps the Undo entry."""
    before = _mask("target", "region-1")
    after = _mask("target", "region-1", start=5004.0)
    project = _project(())
    command = MaskHistoryCommand(
        op_id=OperationId.MASK_EDIT,
        mask_id="target",
        before=mask_definition_snapshot(before),
        after=mask_definition_snapshot(after),
        before_index=0,
        after_index=0,
        affected_region_ids=("region-1", "region-1"),
    )
    history, _refresh_port = _history(project, command)

    with pytest.raises(HistoryApplyError, match="target not found"):
        history.undo()

    assert history.can_undo
    assert not history.can_redo


def test_mask_failure_restores_order_derived_cache_freshness_modified_and_stack() -> None:
    """Failure after rebuild restores the entire mask scientific transaction."""
    first = _mask("first", "region-1")
    target = _mask("target", "region-1", start=5003.0)
    last = _mask("last", "region-2", start=5005.0)
    project = _project((first, last))
    history, _refresh_port = _history(project, _delete_command(target, index=1))
    masks_before = project.model.mask_definitions
    derived_before = project.model.snapshot_derived_state_for_transaction()
    states_before = project.region_analysis_states()
    modified_before = project.modified
    history_before = history.get_state()

    with (
        patch.object(
            project,
            "mark_region_needs_optimization",
            side_effect=RuntimeError("mask freshness failure"),
        ),
        np.testing.assert_raises_regex(RuntimeError, "mask freshness failure"),
    ):
        history.undo()

    assert project.model.mask_definitions == masks_before
    assert all(
        restored is original
        for restored, original in zip(project.model.mask_definitions, masks_before, strict=True)
    )
    derived_after = project.model.snapshot_derived_state_for_transaction()
    assert derived_after.model_valid is derived_before.model_valid
    assert derived_before.model_flux is not None and derived_after.model_flux is not None
    np.testing.assert_array_equal(derived_after.model_flux, derived_before.model_flux)
    assert derived_before.residuals is not None and derived_after.residuals is not None
    np.testing.assert_array_equal(derived_after.residuals, derived_before.residuals)
    assert derived_before.raw_model_flux is not None and derived_after.raw_model_flux is not None
    np.testing.assert_array_equal(derived_after.raw_model_flux, derived_before.raw_model_flux)
    assert project.region_analysis_states() == states_before
    assert not any(line.needs_optimization for line in project.absorption_lines.values())
    assert project.modified == modified_before
    assert history.get_state() == history_before


def test_mask_postcommit_listener_failure_does_not_skip_later_listener() -> None:
    """A failed observer is isolated after mask science commits."""
    target = _mask("target", "region-1")
    project = _project(())
    history, _refresh_port = _history(project, _delete_command(target, index=0))
    received: list[ChangeSet] = []

    def fail_listener(_changes: ChangeSet) -> None:
        raise RuntimeError("mask observer failure")

    project.model.events.subscribe(fail_listener)
    project.model.events.subscribe(received.append)

    assert history.undo().success

    assert project.model.mask_definitions == (target,)
    assert any(change_set.contains(MasksChanged) for change_set in received)
    assert history.can_redo
