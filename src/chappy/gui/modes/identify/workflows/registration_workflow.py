"""Registration workflow for identify mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.application.history.snapshot_mapping import absorption_region_snapshot
from chappy.application.identify import (
    AtomicRegisterSelectedLinesRequest,
    AtomicRegisterSelectedLinesResult,
    BuildRegionPreviewsRequest,
    BuildRegionPreviewsUseCase,
    ExistingRegionSnapshot,
    RegistrationOutcome,
    TemporaryLineSnapshot,
)
from chappy.core.absorption_display import format_region_display
from chappy.core.velocity_ranges import DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE
from chappy.gui.modes.identify.application_adapters import (
    region_preview_from_snapshot,
    temporary_line_to_snapshot,
)
from chappy.gui.modes.identify.registration_controller import IdentifyRegistrationResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from contextlib import AbstractContextManager

    from chappy.application.history import AbsorptionRegionSnapshot
    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.identify_state import IdentifySessionState, RegionPreview, TemporaryLine
    from chappy.core.spectroscopy_project import SpectroscopyProject


class IdentifyRegistrationHistoryRecorder(Protocol):
    """History operation required by registration confirmation."""

    def atomic_recording(self) -> AbstractContextManager[None]:
        """Return a rollback scope covering the complete history stack."""
        ...

    def record_ident_register_selected(
        self,
        project: SpectroscopyProject,
        created_line_ids: list[str],
        created_region_ids: list[str],
        _removed_temporary_line_ids: list[str],
        temporary_line_snapshots: tuple[TemporaryLineSnapshot, ...],
        affected_region_ids: list[str],
        before_affected_region_snapshots: tuple[AbsorptionRegionSnapshot, ...],
    ) -> None:
        """Record identify registration confirmation."""
        ...


class IdentifyRegistrationUseCasePort(Protocol):
    """Atomic registration command consumed by the GUI workflow."""

    def register(
        self, request: AtomicRegisterSelectedLinesRequest
    ) -> AtomicRegisterSelectedLinesResult:
        """Commit one exact-preflighted registration command."""
        ...


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationWorkflowMessages:
    """Translated messages emitted by registration workflow."""

    cannot_register_without_project: str
    no_temporary_lines_to_register: str
    temporary_lines_could_not_register: str
    registered_template: str
    registered_details_template: str
    new_regions_template: str
    appended_template: str
    detail_separator: str
    multi_overlap_warning: str
    missing_atomic_template: str
    undo_hint: str
    unknown: str


@dataclass(frozen=True, slots=True)
class IdentifyRegistrationWorkflowPorts:
    """External state required by identify registration workflow."""

    project_provider: Callable[[], SpectroscopyProject | None]
    session_provider: Callable[[], IdentifySessionState]
    history_recorder_provider: Callable[[], IdentifyRegistrationHistoryRecorder | None]
    primary_members_provider: Callable[[], dict[str, tuple[str, ...]]]
    messages_provider: Callable[[], IdentifyRegistrationWorkflowMessages]


class IdentifyRegistrationWorkflow:
    """Build grouping results and register identify temporary lines immediately."""

    def __init__(
        self,
        ports: IdentifyRegistrationWorkflowPorts,
        preview_usecase: BuildRegionPreviewsUseCase,
        register_usecase: IdentifyRegistrationUseCasePort,
    ) -> None:
        """Initialize the workflow."""
        self._ports = ports
        self._preview_usecase = preview_usecase
        self._register_usecase = register_usecase

    def expand_multiplet_temporary_lines(self, selected_ids: Sequence[str]) -> list[str]:
        """Expand selected primary IDs to all multiplet member IDs."""
        primary_to_members = self._ports.primary_members_provider()
        expanded: list[str] = []
        seen: set[str] = set()

        for primary_id in selected_ids:
            if primary_id in primary_to_members:
                for member_id in primary_to_members[primary_id]:
                    if member_id not in seen:
                        expanded.append(member_id)
                        seen.add(member_id)
            elif primary_id not in seen:
                expanded.append(primary_id)
                seen.add(primary_id)

        return expanded

    def build_region_previews(self, lines: Sequence[TemporaryLine]) -> list[RegionPreview]:
        """Build registration previews for temporary lines."""
        lines_list = list(lines)
        if not lines_list:
            return []

        result = self._preview_usecase.build(
            BuildRegionPreviewsRequest(
                temporary_lines=tuple(temporary_line_to_snapshot(line) for line in lines_list),
                existing_regions=tuple(self._existing_region_snapshots()),
                multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
                unknown_label=self._messages().unknown,
            )
        )
        return [region_preview_from_snapshot(preview) for preview in result.previews]

    def get_region_display_name(self, region: AbsorptionRegion) -> str:
        """Return dynamic display name for an existing absorption region."""
        project = self._ports.project_provider()
        if project is None:
            return region.region_id[:8]
        return self._get_region_display_name(project, region)

    def register_temporary_lines(
        self, lines: Sequence[TemporaryLine]
    ) -> IdentifyRegistrationResult:
        """Register the given temporary lines immediately.

        Args:
            lines: Temporary lines selected for registration.

        Returns:
            Registration result with the typed outcome for status display.
        """
        project = self._ports.project_provider()
        session = self._ports.session_provider()
        messages = self._messages()
        if project is None:
            return IdentifyRegistrationResult(
                messages.cannot_register_without_project,
                refresh_workflow=False,
                refresh_candidates=False,
            )

        temporary_line_snapshots = tuple(temporary_line_to_snapshot(line) for line in lines)
        if not temporary_line_snapshots:
            return IdentifyRegistrationResult(
                messages.no_temporary_lines_to_register,
                refresh_workflow=False,
                refresh_candidates=False,
            )

        history_recorder = self._ports.history_recorder_provider()
        before_region_snapshots = {
            region.region_id: absorption_region_snapshot(region)
            for region in project.list_absorption_regions()
        }

        def record_history(outcome: RegistrationOutcome) -> None:
            if history_recorder is None:
                return
            history_recorder.record_ident_register_selected(
                project,
                list(outcome.created_line_ids),
                list(outcome.created_region_ids),
                list(outcome.processed_temporary_line_ids),
                temporary_line_snapshots,
                list(outcome.affected_region_ids),
                tuple(
                    before_region_snapshots[region_id]
                    for region_id in outcome.affected_region_ids
                    if region_id in before_region_snapshots
                ),
            )

        result = self._register_usecase.register(
            AtomicRegisterSelectedLinesRequest(
                project=project,
                session=session,
                temporary_lines=temporary_line_snapshots,
                existing_regions=tuple(self._existing_region_snapshots()),
                region_line_memberships=tuple(
                    (region.region_id, tuple(region.line_ids))
                    for region in project.list_absorption_regions()
                ),
                multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
                unknown_label=messages.unknown,
                record_history=record_history if history_recorder is not None else None,
                history_scope=(
                    history_recorder.atomic_recording if history_recorder is not None else None
                ),
            )
        )

        if result.outcome is None:
            return IdentifyRegistrationResult(messages.temporary_lines_could_not_register)

        sync_lines = [
            line
            for line_id in result.mode_sync_line_ids
            if (line := project.find_absorption_line(line_id)) is not None
        ]
        run_postcommit_actions_isolated(
            lambda: self._synchronise_model_region_links(project, sync_lines)
        )

        message = self._registration_status_message(project, result.outcome, messages)
        return IdentifyRegistrationResult(message, outcome=result.outcome)

    def _registration_status_message(
        self,
        project: SpectroscopyProject,
        outcome: RegistrationOutcome,
        messages: IdentifyRegistrationWorkflowMessages,
    ) -> str:
        """Format the typed registration outcome into a status message."""
        message = messages.registered_template.format(count=outcome.confirmed_count)

        details: list[str] = []
        # created_region_ids also carries the auto-created unassigned region; only
        # count created regions that actually received registered lines.
        new_region_count = len(set(outcome.created_region_ids) & set(outcome.affected_region_ids))
        if new_region_count:
            details.append(messages.new_regions_template.format(count=new_region_count))
        appended_names = [
            self._get_region_display_name(project, region)
            for region_id in outcome.appended_region_ids
            if (region := project.find_absorption_region(region_id)) is not None
        ]
        details.extend(messages.appended_template.format(region=name) for name in appended_names)
        if details:
            message += messages.registered_details_template.format(
                details=messages.detail_separator.join(details)
            )

        if outcome.multi_overlap_warning:
            message = f"{message} {messages.multi_overlap_warning}"
        if outcome.failed_count:
            warning = messages.missing_atomic_template.format(count=outcome.failed_count)
            message = f"{message} {warning}"
        if outcome.confirmed_count:
            message = f"{message} {messages.undo_hint}"
        return message

    def _existing_region_snapshots(self) -> list[ExistingRegionSnapshot]:
        """Return existing region snapshots for preview grouping."""
        project = self._ports.project_provider()
        if project is None:
            return []

        existing_lines = project.list_absorption_lines()
        snapshots: list[ExistingRegionSnapshot] = []
        for region in project.list_absorption_regions():
            line_ranges = tuple(
                line.lambda_range
                for line in existing_lines
                if line.region_id == region.region_id and line.lambda_range is not None
            )
            snapshots.append(
                ExistingRegionSnapshot(
                    region_id=region.region_id,
                    display_name=self._get_region_display_name(project, region),
                    line_ranges=line_ranges,
                )
            )
        return snapshots

    def _synchronise_model_region_links(
        self, project: SpectroscopyProject, lines: Iterable[AbsorptionLine]
    ) -> None:
        """Ensure model components mirror updated absorption region assignments."""
        for line in lines:
            if line.model_ids:
                project.assign_line_models_to_region(line)

    def _get_region_display_name(
        self, project: SpectroscopyProject, region: AbsorptionRegion
    ) -> str:
        """Return dynamic display name for an existing absorption region."""
        lines = [
            project.absorption_lines[line_id]
            for line_id in region.line_ids
            if line_id in project.absorption_lines
        ]
        if not lines:
            return region.region_id[:8]
        display_info = format_region_display(lines, region.analysis_range)
        return display_info.display_name

    def _messages(self) -> IdentifyRegistrationWorkflowMessages:
        """Return translated registration workflow messages."""
        return self._ports.messages_provider()
