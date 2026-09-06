"""Velocity plot workflow for identify mode."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.application.identify import (
    BuildVelocitySliceTemporaryLinesUseCase,
    VelocitySliceSelection,
    VelocitySliceTemporaryLineRequest,
)
from chappy.presentation.identify import (
    IdentifyVelocityPlotContext,
    IdentifyVelocitySliceDescriptor,
    PreviewEntry,
    preview_entry_to_plot_payload,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from chappy.core.atomic_data import AtomicLine, AtomicLineData
    from chappy.core.identify_state import IdentifySessionState, TemporaryLine
    from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
    from chappy.presentation.identify import IdentifyVelocitySelectionPort


type VelocityTemporaryLineCreationResult = tuple[
    list[tuple[TemporaryLine, PreviewEntry]], int, bool
]


@dataclass(frozen=True, slots=True)
class IdentifyVelocityMessages:
    """Translated messages emitted by identify velocity workflow."""

    baseline_required: str
    invalid_wavelength: str
    no_lines_selected: str
    invalid_baseline: str
    centered_template: str
    closed: str
    select_one: str
    unable_to_create: str
    add_one_template: str
    add_many_template: str
    duplicate_partial_template: str
    duplicate_existing: str


@dataclass(frozen=True, slots=True)
class IdentifyVelocityWorkflowPorts:
    """External state and callbacks required by velocity workflow."""

    session_provider: Callable[[], IdentifySessionState]
    baseline_line_provider: Callable[[], AtomicLine | None]
    current_lines_provider: Callable[[], list[AtomicLine]]
    atomic_data_provider: Callable[[], AtomicLineData]
    temporary_line_creation_callback: Callable[
        [list[PreviewEntry], float, NewCandidateAnalysisHalfWidth],
        VelocityTemporaryLineCreationResult,
    ]
    status_callback: Callable[[str], None]
    refresh_workflow_callback: Callable[[], None]
    refresh_candidates_callback: Callable[[], None]
    messages_provider: Callable[[], IdentifyVelocityMessages]
    tie_group_keys_provider: Callable[[], Mapping[str, str]]


class IdentifyVelocityWorkflow:
    """Build velocity plot context and create temporary lines from selected slices."""

    def __init__(
        self,
        ports: IdentifyVelocityWorkflowPorts,
        slice_usecase: BuildVelocitySliceTemporaryLinesUseCase,
    ) -> None:
        """Initialize the workflow."""
        self._ports = ports
        self._slice_usecase = slice_usecase
        self._active = False

    def is_active(self) -> bool:
        """Return whether identify velocity plot state is active."""
        return self._active

    def reset(self) -> None:
        """Clear velocity active state without emitting user messages."""
        self._active = False

    def report_invalid_wavelength(self) -> None:
        """Tell the user that a valid wavelength position must be specified."""
        self._ports.status_callback(self._messages().invalid_wavelength)

    def request_velocity_plot(
        self, observed_wavelength: float
    ) -> IdentifyVelocityPlotContext | None:
        """Calculate velocity plot context for the given observed wavelength."""
        messages = self._messages()
        baseline_line = self._ports.baseline_line_provider()
        if baseline_line is None:
            self._ports.status_callback(messages.baseline_required)
            return None

        if observed_wavelength <= 0:
            self._ports.status_callback(messages.invalid_wavelength)
            return None

        lines = self._ports.current_lines_provider()
        if not lines:
            self._ports.status_callback(messages.no_lines_selected)
            return None

        rest = baseline_line.wavelength_angstrom
        if rest <= 0:
            self._ports.status_callback(messages.invalid_baseline)
            return None
        center_z = (observed_wavelength / rest) - 1.0

        session = self._ports.session_provider()
        session.reference_z = center_z
        self._active = True
        slices = self._build_velocity_slices(lines, baseline_line)
        if not slices:
            self._ports.status_callback(messages.no_lines_selected)
            return None
        context = IdentifyVelocityPlotContext(
            center_z=center_z,
            rest_wavelength=rest,
            observed_wavelength=observed_wavelength,
            species_label=self._format_species_label(baseline_line),
            new_candidate_analysis_half_width_kms=session.new_candidate_analysis_half_width.kms,
            slices=tuple(slices),
        )
        self._ports.status_callback(
            messages.centered_template.format(z=center_z, label=context.species_label)
        )
        return context

    def handle_velocity_plot_closed(self) -> None:
        """Reset internal state when the velocity plot is dismissed."""
        if not self._active:
            return
        self._active = False
        self._ports.session_provider().reference_z = 0.0
        self._ports.status_callback(self._messages().closed)

    def confirm_velocity_plot_selection(
        self, *, center_z: float | None, slices: Sequence[IdentifyVelocitySelectionPort]
    ) -> None:
        """Create temporary lines from checked velocity slices."""
        messages = self._messages()
        if not slices:
            self._ports.status_callback(messages.select_one)
            return

        baseline_line = self._ports.baseline_line_provider()
        if baseline_line is None:
            self._ports.status_callback(messages.baseline_required)
            return

        session = self._ports.session_provider()
        center_value = center_z if center_z is not None else session.reference_z
        if not math.isfinite(center_value):
            center_value = 0.0

        analysis_half_width = session.new_candidate_analysis_half_width

        entry_models = self._slice_usecase.build(
            VelocitySliceTemporaryLineRequest(
                center_z=center_value,
                new_candidate_analysis_half_width=analysis_half_width,
                slices=tuple(
                    VelocitySliceSelection(
                        line_id=info.line_id,
                        label=info.label,
                        is_primary=info.is_primary,
                        tie_group_key=info.tie_group_key,
                    )
                    for info in slices
                ),
            ),
            self._ports.atomic_data_provider(),
        )
        entries = [preview_entry_to_plot_payload(entry) for entry in entry_models]

        if not entries:
            self._ports.status_callback(messages.unable_to_create)
            return

        session.reference_z = center_value

        created_lines, duplicate_count, limit_reached = (
            self._ports.temporary_line_creation_callback(
                entries, center_value, analysis_half_width
            )
        )
        self._emit_creation_result(
            created_lines=created_lines,
            duplicate_count=duplicate_count,
            limit_reached=limit_reached,
        )

    def _emit_creation_result(
        self,
        *,
        created_lines: list[tuple[TemporaryLine, PreviewEntry]],
        duplicate_count: int,
        limit_reached: bool,
    ) -> None:
        """Emit status and refresh callbacks for velocity temporary-line creation."""
        messages = self._messages()
        created_count = len(created_lines)
        if created_count:
            self._ports.refresh_workflow_callback()
            self._ports.refresh_candidates_callback()

            if created_count == 1:
                line, _entry = created_lines[0]
                self._ports.status_callback(
                    messages.add_one_template.format(
                        species=line.species, start=line.lambda_min, end=line.lambda_max
                    )
                )
            else:
                self._ports.status_callback(messages.add_many_template.format(count=created_count))

        if duplicate_count and created_count:
            self._ports.status_callback(
                messages.duplicate_partial_template.format(
                    created=created_count, skipped=duplicate_count
                )
            )
        elif duplicate_count and not created_count and not limit_reached:
            self._ports.status_callback(messages.duplicate_existing)

    def _build_velocity_slices(
        self, lines: Sequence[AtomicLine], baseline_line: AtomicLine
    ) -> list[IdentifyVelocitySliceDescriptor]:
        """Assemble velocity slice descriptors from the active preset lines."""
        baseline_id = baseline_line.line_id
        tie_group_keys = self._ports.tie_group_keys_provider()

        ordered: list[IdentifyVelocitySliceDescriptor] = []
        baseline_descriptor: IdentifyVelocitySliceDescriptor | None = None

        baseline_tie_group_key = tie_group_keys.get(baseline_id, "")

        for line in lines:
            is_primary = line.line_id == baseline_id
            line_tie_group_key = tie_group_keys.get(line.line_id, "")
            same_tie_group = bool(
                baseline_tie_group_key and line_tie_group_key == baseline_tie_group_key
            )
            default_selected = is_primary or same_tie_group
            descriptor = IdentifyVelocitySliceDescriptor(
                rest_wavelength=line.wavelength_angstrom,
                label=self._short_label(line, primary=is_primary),
                line_id=line.line_id,
                is_primary=is_primary,
                default_selected=default_selected,
                tie_group_key=line_tie_group_key,
            )
            if is_primary:
                baseline_descriptor = descriptor
            else:
                ordered.append(descriptor)

        if baseline_descriptor is None:
            baseline_descriptor = IdentifyVelocitySliceDescriptor(
                rest_wavelength=baseline_line.wavelength_angstrom,
                label=self._short_label(baseline_line, primary=True),
                line_id=baseline_line.line_id,
                is_primary=True,
                default_selected=True,
                tie_group_key=baseline_tie_group_key,
            )

        return [baseline_descriptor, *ordered]

    def _short_label(self, line: AtomicLine, *, primary: bool) -> str:
        """Return compact display label for a velocity slice."""
        transition = (line.transition_name or "").strip()
        if transition:
            return transition

        species = (line.species or "").strip()
        if species and primary:
            return f"{species} {line.wavelength_angstrom:.1f}"
        if species:
            return species
        return f"{line.wavelength_angstrom:.1f}"

    def _format_species_label(self, atomic_line: AtomicLine) -> str:
        """Return display label for the velocity plot center line."""
        wavelength = atomic_line.wavelength_angstrom
        transition = (atomic_line.transition_name or "").strip()
        if transition:
            return f"{transition} ({wavelength:.1f} Å)"

        species = (atomic_line.species or "").strip()
        if species:
            return f"{species} ({wavelength:.1f} Å)"
        return f"{wavelength:.1f} Å"

    def _messages(self) -> IdentifyVelocityMessages:
        """Return translated velocity workflow messages."""
        return self._ports.messages_provider()
