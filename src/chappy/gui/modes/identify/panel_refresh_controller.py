"""Refresh identify panel candidate and workflow views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from chappy.core.velocity_ranges import DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE
from chappy.gui.modes.identify.panel import panel_models
from chappy.gui.modes.identify.panel.workflow_view_model_builder import (
    IdentifyWorkflowBuilderInput,
    IdentifyWorkflowMethodLabels,
    IdentifyWorkflowViewModelBuilder,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from chappy.core.identify_state import DetectedRegion, IdentifySessionState, RegionPreview
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
    from chappy.gui.modes.identify.panel.panel_models import CandidateRow


@dataclass(frozen=True, slots=True)
class IdentifyPanelRefreshPorts:
    """Collaborators required to refresh identify panel state."""

    panel_provider: Callable[[], IdentifySidePanel | None]
    project_provider: Callable[[], SpectroscopyProject | None]
    session_provider: Callable[[], IdentifySessionState]
    atomic_data_available_provider: Callable[[], bool]
    detection_provider: Callable[[], list[DetectedRegion]]
    detection_overlay_callback: Callable[[Sequence[DetectedRegion]], None]
    line_overlay_callback: Callable[[], None]
    region_previews_provider: Callable[[], Sequence[RegionPreview]]


class IdentifyPanelRefreshController(QObject):
    """Apply identify detection and workflow snapshots to the side panel."""

    def __init__(
        self,
        ports: IdentifyPanelRefreshPorts,
        *,
        workflow_builder: IdentifyWorkflowViewModelBuilder | None = None,
    ) -> None:
        """Initialize the controller."""
        super().__init__()
        self._ports = ports
        self._workflow_builder = workflow_builder or IdentifyWorkflowViewModelBuilder()
        self._primary_to_members: dict[str, tuple[str, ...]] = {}

    @property
    def primary_to_members(self) -> dict[str, tuple[str, ...]]:
        """Return the latest primary-to-member temporary line mapping."""
        return self._primary_to_members

    def current_candidate_rows(self) -> tuple[CandidateRow, ...]:
        """Return displayed candidate rows available for focus actions."""
        panel = self._ports.panel_provider()
        if panel is None:
            return ()
        return panel.current_candidates

    def refresh_candidates(self) -> None:
        """Refresh detected candidate regions and detection overlays."""
        regions = self._ports.detection_provider()
        candidate_rows = self._candidate_rows(regions)
        self._ports.detection_overlay_callback(regions)

        if panel := self._ports.panel_provider():
            panel.set_candidates(candidate_rows)

    def refresh_workflow(self) -> None:
        """Refresh temporary-line, preview, and confirmed-region workflow rows."""
        panel = self._ports.panel_provider()
        if panel is None:
            return

        project = self._ports.project_provider()
        absorption_lines = project.list_absorption_lines() if project else []
        absorption_regions = project.list_absorption_regions() if project else []
        session = self._ports.session_provider()
        view_model = self._workflow_builder.build(
            IdentifyWorkflowBuilderInput(
                temporary_lines=session.temporary_lines,
                region_previews=tuple(self._ports.region_previews_provider()),
                absorption_lines=absorption_lines,
                absorption_regions=absorption_regions,
                multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
                atomic_data_available=self._ports.atomic_data_available_provider(),
                method_labels=IdentifyWorkflowMethodLabels(
                    candidate_table=self.tr("Candidate table"),
                    manual=self.tr("Manual placement"),
                    velocity_plot=self.tr("Velocity plot"),
                ),
            )
        )

        self._primary_to_members = view_model.primary_to_members
        panel.set_temporary_lines(view_model.temporary_line_rows, view_model.region_preview_rows)
        panel.set_confirmed_regions(view_model.confirmed_region_rows)
        self._ports.line_overlay_callback()

    def _candidate_rows(
        self, regions: Sequence[DetectedRegion]
    ) -> list[panel_models.CandidateRow]:
        """Build sorted detection candidate rows for the panel."""
        candidate_rows = [
            panel_models.CandidateRow(
                identifier=region.region_id,
                lambda_start=region.lambda_start,
                lambda_end=region.lambda_end,
                sigma=region.sigma,
                status=region.status,
            )
            for region in regions
        ]
        candidate_rows.sort(key=lambda row: row.lambda_start)
        return candidate_rows
