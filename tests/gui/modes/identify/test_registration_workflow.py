"""Tests for identify registration workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from chappy.application.history import ChangeSet, HistoryCommandContext
from chappy.application.history.snapshot_mapping import temporary_line_from_snapshot
from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    BuildRegionPreviewsUseCase,
)
from chappy.core.history import CommandHistory
from chappy.core.identify_state import TemporaryLineContext, IdentifySessionState
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.application.history import HistoryRecorder
from chappy.gui.modes.identify.workflows.registration_workflow import (
    IdentifyRegistrationWorkflow,
    IdentifyRegistrationWorkflowMessages,
    IdentifyRegistrationWorkflowPorts,
)

if TYPE_CHECKING:
    from chappy.application.history import AbsorptionRegionSnapshot
    from chappy.application.identify import TemporaryLineSnapshot
    from chappy.core.history import HistoryEvent
    from chappy.gui.modes.identify.workflows.registration_workflow import (
        IdentifyRegistrationHistoryRecorder,
    )


def _messages() -> IdentifyRegistrationWorkflowMessages:
    """Return deterministic registration workflow messages."""
    return IdentifyRegistrationWorkflowMessages(
        cannot_register_without_project="No project",
        no_temporary_lines_to_register="No candidates",
        temporary_lines_could_not_register="Failed",
        registered_template="Registered {count}",
        registered_details_template=" ({details})",
        new_regions_template="{count} new region(s)",
        appended_template="added to {region}",
        detail_separator=", ",
        multi_overlap_warning="Overlaps multiple existing regions.",
        missing_atomic_template="Missing {count}",
        undo_hint="Undo (Ctrl+Z) reverts this registration.",
        unknown="Unknown",
    )


def _workflow(
    session: IdentifySessionState,
    *,
    project: SpectroscopyProject | None = None,
    primary_members: dict[str, tuple[str, ...]] | None = None,
    history_recorder: IdentifyRegistrationHistoryRecorder | None = None,
) -> IdentifyRegistrationWorkflow:
    """Create a registration workflow with inert external ports."""
    return IdentifyRegistrationWorkflow(
        IdentifyRegistrationWorkflowPorts(
            project_provider=lambda: project,
            session_provider=lambda: session,
            history_recorder_provider=lambda: history_recorder,
            primary_members_provider=lambda: dict(primary_members or {}),
            messages_provider=_messages,
        ),
        BuildRegionPreviewsUseCase(),
        AtomicIdentifyRegistrationUseCase(),
    )


def _add_temporary_line(
    session: IdentifySessionState,
    *,
    line_id: str,
    lambda_min: float,
    lambda_max: float,
    rest_wavelength: float = 1548.195,
) -> str:
    """Add one temporary line and return its line id."""
    temporary_line = session.add_temporary_line(
        "C IV",
        lambda_min,
        lambda_max,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id=line_id,
            rest_wavelength=rest_wavelength,
            multiplet_id="",
            multiplet_label="",
            transition_name="C IV 1548.2",
            oscillator_strength=0.1,
            gamma_value=1e8,
            tie_group_key="",
        ),
    )
    return temporary_line.temporary_line_id


def test_register_temporary_lines_requires_project() -> None:
    """Registration should report a missing project."""
    session = IdentifySessionState()
    workflow = _workflow(session)

    result = workflow.register_temporary_lines(session.temporary_lines)

    assert result.message == "No project"
    assert result.outcome is None
    assert result.refresh_workflow is False
    assert result.refresh_candidates is False


def test_register_temporary_lines_requires_temporary_lines() -> None:
    """Registration should report an empty temporary line selection."""
    session = IdentifySessionState()
    workflow = _workflow(session, project=SpectroscopyProject())

    result = workflow.register_temporary_lines(())

    assert result.message == "No candidates"
    assert result.outcome is None


def test_register_temporary_lines_registers_immediately_and_cleans_session() -> None:
    """One registration call creates lines and regions without a confirm step."""
    project = SpectroscopyProject()
    session = project.identify_state
    _add_temporary_line(session, line_id="civ-1", lambda_min=5000.0, lambda_max=5004.0)
    _add_temporary_line(session, line_id="civ-2", lambda_min=5002.0, lambda_max=5006.0)
    workflow = _workflow(session, project=project)

    result = workflow.register_temporary_lines(session.temporary_lines)

    assert result.message == (
        "Registered 2 (1 new region(s)) Undo (Ctrl+Z) reverts this registration."
    )
    assert result.outcome is not None
    assert len(result.outcome.created_line_ids) == 2
    assert result.outcome.multi_overlap_warning is False
    assert session.temporary_lines == []
    region_ids = {line.region_id for line in project.absorption_lines.values()}
    assert len(region_ids) == 1


def test_partial_registration_converges_to_one_shot_structure() -> None:
    """Split registrations should be absorbed into the same region."""
    project = SpectroscopyProject()
    session = project.identify_state
    first = _add_temporary_line(session, line_id="civ-1", lambda_min=5000.0, lambda_max=5004.0)
    second = _add_temporary_line(session, line_id="civ-2", lambda_min=5002.0, lambda_max=5006.0)
    workflow = _workflow(session, project=project)

    first_result = workflow.register_temporary_lines(
        [line for line in session.temporary_lines if line.temporary_line_id == first]
    )
    second_result = workflow.register_temporary_lines(
        [line for line in session.temporary_lines if line.temporary_line_id == second]
    )

    assert first_result.outcome is not None
    assert second_result.outcome is not None
    first_region_id = first_result.outcome.affected_region_ids[0]
    assert first_region_id in first_result.outcome.created_region_ids
    assert second_result.outcome.created_region_ids == ()
    assert second_result.outcome.appended_region_ids == (first_region_id,)
    assert second_result.message.startswith("Registered 1 (added to ")
    assert second_result.message.endswith("Undo (Ctrl+Z) reverts this registration.")
    region_ids = {line.region_id for line in project.absorption_lines.values()}
    assert region_ids == {first_region_id}


class _HistoryRoundTripApplier:
    """Apply identify register undo/redo against a real project and session."""

    def __init__(self, project: SpectroscopyProject) -> None:
        self._project = project

    def apply_history_event(self, event: HistoryEvent, *, is_undo: bool) -> bool:
        context = HistoryCommandContext(structure_port=self, identify_port=self)
        result = event.command.undo(context) if is_undo else event.command.redo(context)
        return result.success

    def remove_absorption_lines(
        self, line_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        for line_id in line_ids:
            self._project.remove_absorption_line(line_id, delete_models=delete_models)
        return ChangeSet(changed_line_ids=line_ids)

    def restore_identify_temporary_lines(
        self, snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> ChangeSet:
        for snapshot in snapshots:
            self._project.identify_state.restore_temporary_line(
                temporary_line_from_snapshot(snapshot)
            )
        return ChangeSet(
            changed_temporary_line_ids=tuple(snapshot.temporary_line_id for snapshot in snapshots)
        )

    def update_identify_region_analysis_ranges(self, region_ids: tuple[str, ...]) -> ChangeSet:
        for region_id in region_ids:
            if region_id in self._project.absorption_regions:
                self._project.update_region_analysis_range(region_id)
        return ChangeSet(changed_region_ids=region_ids)

    def apply_absorption_region_states_partial_exact(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore exact fields for affected regions still present after history apply."""
        for snapshot in snapshots:
            region = self._project.absorption_regions[snapshot.region_id]
            region.line_ids[:] = snapshot.line_ids
            region.display_color = snapshot.display_color
            region.analysis_range = snapshot.analysis_range
            region.created_at = snapshot.created_at
        return ChangeSet(changed_region_ids=tuple(item.region_id for item in snapshots))


def test_register_and_undo_round_trip_restores_temporary_lines() -> None:
    """record_ident_register_selected undo removes lines and restores temporary lines."""
    project = SpectroscopyProject()
    session = project.identify_state
    temporary_line_id = _add_temporary_line(
        session, line_id="civ-1", lambda_min=5000.0, lambda_max=5004.0
    )
    command_history = CommandHistory()
    command_history.set_applier(_HistoryRoundTripApplier(project))
    recorder = HistoryRecorder(command_history, lambda: project)
    workflow = _workflow(session, project=project, history_recorder=recorder)

    result = workflow.register_temporary_lines(session.temporary_lines)

    assert result.outcome is not None
    assert project.absorption_lines
    assert session.temporary_lines == []

    undo_result = command_history.undo()

    assert undo_result.success
    assert project.absorption_lines == {}
    assert [temporary_line.temporary_line_id for temporary_line in session.temporary_lines] == [
        temporary_line_id
    ]


def test_expand_multiplet_temporary_lines_deduplicates_members() -> None:
    """Selected primary ids should expand to unique member ids."""
    workflow = _workflow(
        IdentifySessionState(),
        primary_members={
            "primary": ("primary", "member-a", "member-b"),
            "second": ("member-b", "member-c"),
        },
    )

    assert workflow.expand_multiplet_temporary_lines(["primary", "second", "member-a"]) == [
        "primary",
        "member-a",
        "member-b",
        "member-c",
    ]
