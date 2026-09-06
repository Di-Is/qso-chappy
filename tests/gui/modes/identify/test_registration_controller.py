"""Tests for the identify registration controller."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import pytest

from chappy.application.identify import RegistrationOutcome
from chappy.core.identify_state import TemporaryLine
from chappy.gui.modes.identify.registration_controller import (
    IdentifyRegistrationController,
    IdentifyRegistrationMessages,
    IdentifyRegistrationPorts,
    IdentifyRegistrationResult,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _outcome() -> RegistrationOutcome:
    """Build a registration outcome for controller tests."""
    return RegistrationOutcome(
        created_line_ids=("line-1",),
        created_region_ids=("region-1",),
        processed_temporary_line_ids=("line-1",),
        affected_region_ids=("region-1",),
        appended_region_ids=(),
        confirmed_count=1,
        failed_count=0,
        multi_overlap_warning=False,
    )


@dataclass
class _SessionPort:
    """Expose temporary lines to the controller."""

    _temporary_lines: list[TemporaryLine] = field(default_factory=list)

    @property
    def temporary_lines(self) -> Sequence[TemporaryLine]:
        """Return temporary lines."""
        return list(self._temporary_lines)


@dataclass
class _WorkflowPort:
    """Record registration workflow requests."""

    result: IdentifyRegistrationResult | None = None
    expanded_ids: list[str] = field(default_factory=list)
    registered_lines: list[tuple[str, ...]] = field(default_factory=list)

    def expand_multiplet_temporary_lines(self, selected_ids: Sequence[str]) -> list[str]:
        """Return configured expanded ids."""
        self.expanded_ids = list(selected_ids)
        return list(selected_ids)

    def register_temporary_lines(
        self, lines: Sequence[TemporaryLine]
    ) -> IdentifyRegistrationResult:
        """Record temporary line ids submitted for registration."""
        self.registered_lines.append(tuple(line.temporary_line_id for line in lines))
        return self.result or IdentifyRegistrationResult("Registered", outcome=_outcome())


@dataclass
class _Harness:
    """Registration controller test harness."""

    controller: IdentifyRegistrationController
    session: _SessionPort
    workflow: _WorkflowPort
    statuses: list[str]
    workflow_refresh_count: list[int]
    candidates_refresh_count: list[int]


def _temporary_line(identifier: str) -> TemporaryLine:
    """Build a temporary line for controller tests."""
    return TemporaryLine(
        temporary_line_id=identifier,
        species="C IV",
        lambda_min=1000.0,
        lambda_max=1002.0,
        creation_method="test",
        line_id=identifier,
        rest_wavelength=500.0,
        center_z=1.0,
        multiplet_id="",
        multiplet_label="",
        transition_name="C IV 500",
        oscillator_strength=0.1,
        gamma_value=0.2,
        tie_group_key="",
    )


def _messages() -> IdentifyRegistrationMessages:
    """Return stable registration messages."""
    return IdentifyRegistrationMessages(
        no_temporary_lines="No candidates", no_selected_temporary_lines="No selected candidates"
    )


def _harness(*, temporary_lines: list[TemporaryLine] | None = None) -> _Harness:
    """Create a registration controller with recording ports."""
    session = _SessionPort(_temporary_lines=list(temporary_lines or []))
    workflow = _WorkflowPort()
    statuses: list[str] = []
    workflow_refresh_count = [0]
    candidates_refresh_count = [0]

    def refresh_workflow() -> None:
        workflow_refresh_count[0] += 1

    def refresh_candidates() -> None:
        candidates_refresh_count[0] += 1

    controller = IdentifyRegistrationController(
        IdentifyRegistrationPorts(
            session_provider=lambda: session,
            workflow_provider=lambda: workflow,
            status_callback=statuses.append,
            refresh_workflow_callback=refresh_workflow,
            refresh_candidates_callback=refresh_candidates,
            messages_provider=_messages,
        )
    )
    return _Harness(
        controller=controller,
        session=session,
        workflow=workflow,
        statuses=statuses,
        workflow_refresh_count=workflow_refresh_count,
        candidates_refresh_count=candidates_refresh_count,
    )


def test_register_requires_temporary_lines() -> None:
    """Registration reports empty state when no temporary lines exist."""
    harness = _harness()

    outcome = harness.controller.register()

    assert outcome is None
    assert harness.statuses == ["No candidates"]
    assert harness.workflow.registered_lines == []


def test_register_submits_all_temporary_lines_and_refreshes() -> None:
    """Registration without selection submits all temporary lines in one operation."""
    harness = _harness(temporary_lines=[_temporary_line("line-1"), _temporary_line("line-2")])

    outcome = harness.controller.register()

    assert harness.workflow.registered_lines == [("line-1", "line-2")]
    assert harness.statuses == ["Registered"]
    assert harness.workflow_refresh_count == [1]
    assert harness.candidates_refresh_count == [1]
    assert outcome is not None
    assert outcome.message == "Registered"
    assert outcome.created_line_ids == ("line-1",)


def test_register_zero_created_lines_has_status_but_no_inline_result() -> None:
    """A zero-line outcome refreshes and reports status without offering inline Undo."""
    harness = _harness(temporary_lines=[_temporary_line("line-1")])
    harness.workflow.result = IdentifyRegistrationResult(
        "Registered 0 lines",
        outcome=replace(_outcome(), created_line_ids=(), confirmed_count=0, failed_count=1),
    )

    result = harness.controller.register()

    assert result is None
    assert harness.statuses == ["Registered 0 lines"]
    assert harness.workflow_refresh_count == [1]
    assert harness.candidates_refresh_count == [1]


def test_register_filters_selected_temporary_lines() -> None:
    """Selected ids restrict the registered temporary line subset."""
    harness = _harness(temporary_lines=[_temporary_line("line-1"), _temporary_line("line-2")])

    harness.controller.register(["line-2"])

    assert harness.workflow.expanded_ids == ["line-2"]
    assert harness.workflow.registered_lines == [("line-2",)]


def test_register_reports_empty_selection() -> None:
    """Selection matching no temporary lines reports a status without registering."""
    harness = _harness(temporary_lines=[_temporary_line("line-1")])

    outcome = harness.controller.register(["missing"])

    assert outcome is None
    assert harness.statuses == ["No selected candidates"]
    assert harness.workflow.registered_lines == []


def test_register_skips_refresh_when_workflow_declines() -> None:
    """Refresh callbacks follow the workflow result flags."""
    harness = _harness(temporary_lines=[_temporary_line("line-1")])
    harness.workflow.result = IdentifyRegistrationResult(
        "Failed", refresh_workflow=False, refresh_candidates=False
    )

    outcome = harness.controller.register()

    assert outcome is None
    assert harness.statuses == ["Failed"]
    assert harness.workflow_refresh_count == [0]
    assert harness.candidates_refresh_count == [0]


def test_postcommit_observer_failure_does_not_skip_later_refreshes() -> None:
    """One failed GUI observer cannot undo registration or suppress later observers."""
    session = _SessionPort(_temporary_lines=[_temporary_line("line-1")])
    workflow = _WorkflowPort()
    calls: list[str] = []

    def fail_status(_message: str) -> None:
        calls.append("status")
        raise RuntimeError("injected status observer failure")

    controller = IdentifyRegistrationController(
        IdentifyRegistrationPorts(
            session_provider=lambda: session,
            workflow_provider=lambda: workflow,
            status_callback=fail_status,
            refresh_workflow_callback=lambda: calls.append("workflow"),
            refresh_candidates_callback=lambda: calls.append("candidates"),
            messages_provider=_messages,
        )
    )

    result = controller.register()

    assert result is not None
    assert result.created_line_ids == ("line-1",)
    assert calls == ["status", "workflow", "candidates"]


def test_register_missing_workflow_fails_fast() -> None:
    """Missing registration workflow is a composition error."""
    session = _SessionPort(_temporary_lines=[_temporary_line("line-1")])
    statuses: list[str] = []
    controller = IdentifyRegistrationController(
        IdentifyRegistrationPorts(
            session_provider=lambda: session,
            workflow_provider=lambda: None,
            status_callback=statuses.append,
            refresh_workflow_callback=lambda: None,
            refresh_candidates_callback=lambda: None,
            messages_provider=_messages,
        )
    )

    with pytest.raises(RuntimeError, match="registration workflow"):
        controller.register()
    assert statuses == []
