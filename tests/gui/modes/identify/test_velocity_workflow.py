"""Tests for identify velocity workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from chappy.application.identify import BuildVelocitySliceTemporaryLinesUseCase
from chappy.core.atomic_data import AtomicLine, AtomicLineData
from chappy.core.identify_state import IdentifySessionState
from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
from chappy.gui.modes.identify.workflows.velocity_workflow import (
    IdentifyVelocityMessages,
    IdentifyVelocityWorkflow,
    IdentifyVelocityWorkflowPorts,
)
from chappy.presentation.identify import IdentifyVelocitySelectionPort, PreviewEntry


class _AtomicData:
    """Fake atomic data source for velocity workflow tests."""

    def __init__(self, lines: tuple[AtomicLine, ...]) -> None:
        """Initialize indexed atomic lines."""
        self._lines = {line.line_id: line for line in lines}

    def get_line_by_id(self, line_id: str) -> AtomicLine | None:
        """Return a line by identifier."""
        return self._lines.get(line_id)


@dataclass(frozen=True, slots=True)
class _SelectedSlice:
    """Selected velocity slice for workflow confirmation."""

    rest_wavelength: float
    label: str
    center_z: float | None
    line_id: str | None
    is_primary: bool
    tie_group_key: str = ""


def _line(
    line_id: str, wavelength: float, *, transition_name: str = "", multiplet_id: str = ""
) -> AtomicLine:
    """Build an atomic line for velocity workflow tests."""
    return AtomicLine(
        line_identifier=line_id,
        species="C IV",
        wavelength_angstrom=wavelength,
        oscillator_strength=0.2,
        gamma_value=1.0,
        multiplet_id=multiplet_id,
        multiplet_label="C IV doublet" if multiplet_id else "",
        transition_name=transition_name,
    )


def _messages() -> IdentifyVelocityMessages:
    """Return deterministic velocity workflow messages."""
    return IdentifyVelocityMessages(
        baseline_required="Baseline required",
        invalid_wavelength="Invalid wavelength",
        no_lines_selected="No lines",
        invalid_baseline="Invalid baseline",
        centered_template="Centered {z:.4f} {label}",
        closed="Closed",
        select_one="Select one",
        unable_to_create="Unable",
        add_one_template="Added one {species} {start:.1f} {end:.1f}",
        add_many_template="Added many {count}",
        duplicate_partial_template="Duplicates {created} {skipped}",
        duplicate_existing="Existing",
    )


def _workflow(
    session: IdentifySessionState,
    lines: tuple[AtomicLine, ...],
    *,
    baseline: AtomicLine | None,
    statuses: list[str],
    created_entries: list[tuple[list[PreviewEntry], float]],
    refreshes: list[str],
    tie_group_keys: dict[str, str] | None = None,
) -> IdentifyVelocityWorkflow:
    """Create a velocity workflow with recording callbacks."""

    def create_temporary_lines(
        entries: list[PreviewEntry],
        redshift: float,
        analysis_half_width: NewCandidateAnalysisHalfWidth,
    ) -> tuple[list[tuple[object, PreviewEntry]], int, bool]:
        assert analysis_half_width == session.new_candidate_analysis_half_width
        created_entries.append((entries, redshift))
        return ([], 0, False)

    return IdentifyVelocityWorkflow(
        IdentifyVelocityWorkflowPorts(
            session_provider=lambda: session,
            baseline_line_provider=lambda: baseline,
            current_lines_provider=lambda: list(lines),
            atomic_data_provider=lambda: cast(AtomicLineData, _AtomicData(lines)),
            temporary_line_creation_callback=create_temporary_lines,
            status_callback=statuses.append,
            refresh_workflow_callback=lambda: refreshes.append("workflow"),
            refresh_candidates_callback=lambda: refreshes.append("candidates"),
            messages_provider=_messages,
            tie_group_keys_provider=lambda: (
                dict(tie_group_keys)
                if tie_group_keys is not None
                else {
                    line.line_id: f"test:{line.multiplet_id}"
                    for line in lines
                    if line.multiplet_id
                }
            ),
        ),
        BuildVelocitySliceTemporaryLinesUseCase(),
    )


def test_request_velocity_plot_builds_context_and_marks_active() -> None:
    """Requesting a plot should build context and set active velocity state."""
    session = IdentifySessionState()
    baseline = _line("civ-1548", 1548.2, transition_name="C IV 1548", multiplet_id="CIV")
    companion = _line("civ-1550", 1550.8, transition_name="C IV 1550", multiplet_id="CIV")
    statuses: list[str] = []
    created_entries: list[tuple[list[PreviewEntry], float]] = []
    refreshes: list[str] = []
    workflow = _workflow(
        session,
        (baseline, companion),
        baseline=baseline,
        statuses=statuses,
        created_entries=created_entries,
        refreshes=refreshes,
    )

    context = workflow.request_velocity_plot(3096.4)

    assert context is not None
    assert context.center_z == pytest.approx(1.0)
    assert context.species_label == "C IV 1548 (1548.2 Å)"
    assert context.new_candidate_analysis_half_width_kms == 200.0
    assert [slice_info.line_id for slice_info in context.slices] == ["civ-1548", "civ-1550"]
    assert [slice_info.default_selected for slice_info in context.slices] == [True, True]
    assert [slice_info.tie_group_key for slice_info in context.slices] == ["test:CIV", "test:CIV"]
    assert session.reference_z == pytest.approx(1.0)
    assert workflow.is_active() is True
    assert statuses == ["Centered 1.0000 C IV 1548 (1548.2 Å)"]


def test_report_invalid_wavelength_asks_for_a_valid_position() -> None:
    """An unresolvable wavelength reuses the existing invalid wavelength message."""
    statuses: list[str] = []
    workflow = _workflow(
        IdentifySessionState(),
        (_line("civ-1548", 1548.2),),
        baseline=None,
        statuses=statuses,
        created_entries=[],
        refreshes=[],
    )

    workflow.report_invalid_wavelength()

    assert statuses == ["Invalid wavelength"]


def test_request_velocity_plot_without_baseline_reports_baseline_required() -> None:
    """The baseline requirement still takes precedence over wavelength validation."""
    statuses: list[str] = []
    workflow = _workflow(
        IdentifySessionState(),
        (_line("civ-1548", 1548.2),),
        baseline=None,
        statuses=statuses,
        created_entries=[],
        refreshes=[],
    )

    assert workflow.request_velocity_plot(3096.4) is None
    assert statuses == ["Baseline required"]


def test_handle_velocity_plot_closed_resets_state() -> None:
    """Closing an active velocity plot should reset state and emit status."""
    session = IdentifySessionState()
    baseline = _line("civ-1548", 1548.2)
    statuses: list[str] = []
    workflow = _workflow(
        session,
        (baseline,),
        baseline=baseline,
        statuses=statuses,
        created_entries=[],
        refreshes=[],
    )
    assert workflow.request_velocity_plot(3096.4) is not None

    workflow.handle_velocity_plot_closed()

    assert workflow.is_active() is False
    assert session.reference_z == 0.0
    assert statuses[-1] == "Closed"


def test_same_db_multiplet_without_declared_key_is_not_default_selected() -> None:
    """Velocity defaults use declared keys rather than DB multiplet metadata."""
    session = IdentifySessionState()
    baseline = _line("civ-1548", 1548.2, multiplet_id="CIV")
    companion = _line("civ-1550", 1550.8, multiplet_id="CIV")
    workflow = _workflow(
        session,
        (baseline, companion),
        baseline=baseline,
        statuses=[],
        created_entries=[],
        refreshes=[],
        tie_group_keys={},
    )

    context = workflow.request_velocity_plot(3096.4)

    assert context is not None
    assert [slice_info.default_selected for slice_info in context.slices] == [True, False]


def test_confirm_velocity_plot_selection_builds_temporary_line_entries() -> None:
    """Selected velocity slices should be converted into temporary line entries."""
    session = IdentifySessionState()
    baseline = _line("civ-1548", 1548.2, transition_name="C IV 1548")
    statuses: list[str] = []
    created_entries: list[tuple[list[PreviewEntry], float]] = []
    refreshes: list[str] = []
    workflow = _workflow(
        session,
        (baseline,),
        baseline=baseline,
        statuses=statuses,
        created_entries=created_entries,
        refreshes=refreshes,
    )
    selection = _SelectedSlice(
        rest_wavelength=baseline.wavelength_angstrom,
        label="C IV 1548",
        center_z=1.0,
        line_id=baseline.line_id,
        is_primary=True,
        tie_group_key="group-key",
    )
    session.set_new_candidate_analysis_half_width(NewCandidateAnalysisHalfWidth(140.0))

    workflow.confirm_velocity_plot_selection(
        center_z=1.0, slices=cast(list[IdentifyVelocitySelectionPort], [selection])
    )

    assert len(created_entries) == 1
    entries, redshift = created_entries[0]
    assert redshift == 1.0
    assert entries[0]["line_id"] == baseline.line_id
    assert entries[0]["tie_group_key"] == "group-key"
    expected_center = baseline.wavelength_angstrom * 2.0
    expected_delta = expected_center * 140.0 / LIGHT_SPEED_KMS
    assert entries[0]["lambda_min"] == pytest.approx(expected_center - expected_delta)
    assert entries[0]["lambda_max"] == pytest.approx(expected_center + expected_delta)
    assert session.reference_z == 1.0
