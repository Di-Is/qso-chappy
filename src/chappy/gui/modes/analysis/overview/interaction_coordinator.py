"""Interaction coordinator for structure-mode side panel events."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QObject, QPoint

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.core.absorption_display import format_region_display
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.adapters import StructureHistoryRecorder
from chappy.gui.theme import create_styled_menu

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from chappy.application.structure import StructureImpactPreview
    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.gui.modes.analysis.overview.operation_controller import (
        StructureOperationController,
    )
    from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
    from chappy.presentation.analysis.structure.tree_presenter import StructureRegionEntry

GROUP_FOCUS_FRACTION = 0.1
GROUP_MIN_PADDING = 0.5
ZERO_SPAN_PADDING_BASE = 1.0
ZERO_SPAN_PADDING_FACTOR = 0.01
LINKED_LINE_FOCUS_FRACTION = 0.002
LINKED_LINE_FOCUS_MIN_SPAN = 1.0


class StructureRefreshPanelPort(Protocol):
    """Panel operations required after structure workflow mutations."""

    def clear_selection(self) -> None:
        """Clear the current panel selection."""
        ...

    def refresh(self) -> None:
        """Refresh panel contents outside committed topology publication."""
        ...

    def group_entry(self, identifier: str) -> StructureRegionEntry | None:
        """Return structure group metadata for the identifier."""
        ...

    def set_unlink_enabled(self, enabled: bool) -> None:
        """Set availability of the linked-line unlink operation."""
        ...

    def set_structure_actions_enabled(
        self, *, merge: bool, split: bool, delete: bool, unlink: bool
    ) -> None:
        """Set availability of every visible structure action."""
        ...


type ProjectProvider = Callable[[], SpectroscopyProject | None]
type HistoryRecorderProvider = Callable[[], StructureHistoryRecorder | None]
type FocusRangeCallback = Callable[[float, float], None]
type StatusCallback = Callable[[str, int, bool], None]
type DeleteConfirmation = Callable[[StructureImpactPreview, SpectroscopyProject], bool]
type UnlinkConfirmation = Callable[[StructureImpactPreview, SpectroscopyProject], bool]


@dataclass(frozen=True, slots=True)
class StructureInteractionPorts:
    """Shell callbacks required by the structure interaction coordinator."""

    project_provider: ProjectProvider
    history_recorder_provider: HistoryRecorderProvider
    focus_range_callback: FocusRangeCallback
    status_callback: StatusCallback
    delete_confirmation: DeleteConfirmation
    unlink_confirmation: UnlinkConfirmation
    context_menu_parent: QWidget


class StructureInteractionCoordinator(QObject):
    """Coordinate structure-mode panel events, operation results, and shell ports."""

    def __init__(
        self,
        *,
        operations: StructureOperationController,
        ports: StructureInteractionPorts,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            operations: Structure operation workflow controller.
            ports: Shell callbacks for project, history, status, and UI routing.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._operations = operations
        self._ports = ports
        self._panel: StructureRefreshPanelPort | None = None
        self._selection: tuple[list[str], list[str]] = ([], [])

    @property
    def selection(self) -> tuple[list[str], list[str]]:
        """Return the current structure selection snapshot."""
        groups, linked_lines = self._selection
        return list(groups), list(linked_lines)

    def set_panel(self, panel: StructureRefreshPanelPort | None) -> None:
        """Set the panel used for refresh and selection updates."""
        self._panel = panel

    def connect_panel(self, panel: StructureSidePanel) -> None:
        """Connect structure panel signals to this coordinator."""
        self.set_panel(panel)
        panel.selection_changed.connect(self.handle_selection)
        panel.group_activated.connect(self.handle_group_activated)
        panel.line_activated.connect(self.handle_line_activated)
        panel.context_menu_requested.connect(self.handle_context_menu)
        panel.line_move_requested.connect(self.handle_line_move)
        panel.merge_requested.connect(self.execute_merge)
        panel.split_requested.connect(self.execute_split)
        panel.delete_requested.connect(self.execute_delete)
        panel.unlink_requested.connect(self.execute_unlink)

    def clear_selection_state(self) -> None:
        """Clear coordinator selection state."""
        self._selection = ([], [])
        if self._panel is not None:
            self._panel.set_unlink_enabled(False)
            self._panel.set_structure_actions_enabled(
                merge=False, split=False, delete=False, unlink=False
            )

    def refresh_active_panel(self) -> None:
        """Refresh the panel and synchronize its current selection."""
        if self._panel is not None:
            self._panel.refresh()
        groups, linked_lines = self._selection
        self.handle_selection(groups, linked_lines)

    def handle_selection(self, group_ids: list[str], linked_line_ids: list[str]) -> None:
        """Update structure selection and dependent shell controls."""
        previous_groups, previous_linked_lines = self._selection
        current_groups = list(group_ids)
        current_linked_lines = list(linked_line_ids)
        self._selection = (current_groups, current_linked_lines)

        if (
            not current_groups
            and not current_linked_lines
            and (previous_groups or previous_linked_lines)
        ):
            self._emit_status(self.tr("No selection"))

        if self._panel is not None:
            unlink = self._operations.can_unlink(
                self._ports.project_provider(), current_groups, current_linked_lines
            )
            self._panel.set_structure_actions_enabled(
                merge=self._operations.can_merge(current_groups, current_linked_lines),
                split=self._operations.can_split(current_groups, current_linked_lines),
                delete=self._operations.can_delete(current_groups, current_linked_lines),
                unlink=unlink,
            )

    def handle_group_activated(self, group_id: str) -> None:
        """Focus the spectrum to the activated structure group."""
        if self._panel is None:
            return
        entry = self._panel.group_entry(group_id)
        if entry is None or entry.wavelength_min is None:
            return

        min_wave = entry.wavelength_min
        max_wave = entry.wavelength_max if entry.wavelength_max is not None else min_wave
        if max_wave < min_wave:
            min_wave, max_wave = max_wave, min_wave

        span = max_wave - min_wave
        padding = (
            max(
                ZERO_SPAN_PADDING_BASE,
                abs(min_wave) * ZERO_SPAN_PADDING_FACTOR + ZERO_SPAN_PADDING_BASE,
            )
            if span <= 0
            else max(span * GROUP_FOCUS_FRACTION, GROUP_MIN_PADDING)
        )
        self._ports.focus_range_callback(min_wave - padding, max_wave + padding)

    def handle_line_activated(self, line_id: str) -> None:
        """Focus the spectrum to the activated structure line."""
        project = self._ports.project_provider()
        if project is None:
            return

        line = project.absorption_lines.get(line_id)
        if line is None:
            return

        observed = _observed_line_wavelength(line)

        span = max(observed * LINKED_LINE_FOCUS_FRACTION, LINKED_LINE_FOCUS_MIN_SPAN)
        self._ports.focus_range_callback(observed - span, observed + span)

    def handle_context_menu(
        self, global_pos: QPoint, group_ids: list[str], linked_line_ids: list[str]
    ) -> None:
        """Display structure-mode context menu actions."""
        menu_title = self.tr("Analysis Structure")
        menu = create_styled_menu(self._ports.context_menu_parent, menu_title)

        merge_action = menu.addAction(self.tr("Merge selected regions"))
        merge_action.setEnabled(self._operations.can_merge(group_ids, linked_line_ids))

        split_action = menu.addAction(self.tr("Split line into new region"))
        split_action.setEnabled(self._operations.can_split(group_ids, linked_line_ids))

        unlink_action = menu.addAction(self.tr("Unlink these linked lines"))
        unlink_action.setEnabled(
            self._operations.can_unlink(self._ports.project_provider(), group_ids, linked_line_ids)
        )

        delete_action = menu.addAction(self.tr("Delete selection"))
        delete_action.setEnabled(self._operations.can_delete(group_ids, linked_line_ids))

        focus_action = menu.addAction(self.tr("Move spectrum to selection"))
        focus_action.setEnabled(self._operations.can_focus(group_ids, linked_line_ids))

        triggered = menu.exec(global_pos)
        if triggered is None:
            return

        if triggered is merge_action:
            self.execute_merge()
        elif triggered is split_action:
            self.execute_split()
        elif triggered is unlink_action:
            self.execute_unlink()
        elif triggered is delete_action:
            self.execute_delete()
        elif triggered is focus_action:
            if group_ids and not linked_line_ids:
                self.handle_group_activated(group_ids[0])
            elif linked_line_ids and not group_ids:
                self.handle_line_activated(linked_line_ids[0])

    def handle_line_move(self, target_region_id: str, line_ids: list[str]) -> None:
        """Move selected structure lines to the target region."""
        project = self._ports.project_provider()

        target_region = target_region_id or None
        result = self._operations.move_lines(
            project,
            line_ids=line_ids,
            target_region_id=target_region,
            history_recorder=self._ports.history_recorder_provider(),
        )
        if result is None or project is None:
            return

        def announce() -> None:
            destination_name = self._get_region_display_name(project, result.destination_region)
            self._emit_status(
                self.tr("Moved {count} lines to {destination}.").format(
                    count=result.moved_linked_line_count, destination=destination_name
                ),
                undo_hint=True,
            )

        self._publish_committed_change(clear_panel_selection=False, announce=announce)

    def execute_merge(self) -> bool:
        """Merge the current structure region selection."""
        project = self._ports.project_provider()
        group_ids, _ = self._selection

        result = self._operations.merge_regions(
            project, group_ids=group_ids, history_recorder=self._ports.history_recorder_provider()
        )
        if result is None or project is None:
            return False

        def announce() -> None:
            merged_name = self._get_region_display_name(project, result.merged_region)
            self._emit_status(
                self.tr("Merged {count} regions into {name}.").format(
                    count=len(group_ids), name=merged_name
                ),
                undo_hint=True,
            )

        self._publish_committed_change(clear_panel_selection=True, announce=announce)
        return True

    def execute_split(self) -> bool:
        """Split the current structure line selection into a new region."""
        project = self._ports.project_provider()
        _, linked_line_ids = self._selection

        result = self._operations.split_lines(
            project,
            linked_line_ids=linked_line_ids,
            history_recorder=self._ports.history_recorder_provider(),
        )
        if result is None or project is None:
            return False

        def announce() -> None:
            new_region_name = self._get_region_display_name(project, result.new_region)
            self._emit_status(
                self.tr('Created new region "{name}" from the selection.').format(
                    name=new_region_name
                ),
                undo_hint=True,
            )

        self._publish_committed_change(clear_panel_selection=True, announce=announce)
        return True

    def execute_delete(self) -> bool:
        """Delete the current structure selection."""
        project = self._ports.project_provider()

        group_ids, linked_line_ids = self._selection
        preview = self._operations.preview_delete(
            project, group_ids=group_ids, linked_line_ids=linked_line_ids
        )
        if (
            project is None
            or preview is None
            or not self._ports.delete_confirmation(preview, project)
        ):
            return False
        result = self._operations.delete_selection(
            project,
            group_ids=group_ids,
            linked_line_ids=linked_line_ids,
            history_recorder=self._ports.history_recorder_provider(),
        )
        if result is None:
            return False

        self._selection = ([], [])
        summary_parts: list[str] = []
        if result.groups_removed:
            summary_parts.append(self.tr("{count} regions").format(count=result.groups_removed))
        if result.lines_removed:
            summary_parts.append(self.tr("{count} lines").format(count=result.lines_removed))
        summary = ", ".join(summary_parts)
        self._publish_committed_change(
            clear_panel_selection=True,
            announce=lambda: self._emit_status(
                self.tr("Deleted {summary}.").format(summary=summary), undo_hint=True
            ),
        )
        return True

    def execute_unlink(self) -> bool:
        """Unlink the current structure linked-line selection."""
        project = self._ports.project_provider()
        _, linked_line_ids = self._selection
        preview = self._operations.preview_unlink(project, linked_line_ids=linked_line_ids)
        if (
            project is None
            or preview is None
            or not self._ports.unlink_confirmation(preview, project)
        ):
            return False
        result = self._operations.unlink_linked_lines(
            project,
            linked_line_ids=linked_line_ids,
            history_recorder=self._ports.history_recorder_provider(),
        )
        if result is None:
            return False

        self._selection = ([], [])
        self._publish_committed_change(
            clear_panel_selection=True,
            announce=lambda: self._emit_status(
                self.tr("Unlinked {count} linked lines.").format(
                    count=len(result.unlinked_line_ids)
                ),
                undo_hint=True,
            ),
        )
        return True

    def _publish_committed_change(
        self, *, clear_panel_selection: bool, announce: Callable[[], object]
    ) -> None:
        """Run independent UI observers after a scientific structure commit."""
        actions: list[Callable[[], object]] = []
        panel = self._panel
        if panel is not None and clear_panel_selection:
            actions.append(panel.clear_selection)
        actions.extend((lambda: self.handle_selection([], []), announce))
        run_postcommit_actions_isolated(*actions)

    def _get_region_display_name(
        self, project: SpectroscopyProject, region: AbsorptionRegion | None
    ) -> str:
        """Get dynamic display name for an absorption region."""
        if region is None:
            return self.tr("new region")

        lines = [
            project.absorption_lines[line_id]
            for line_id in region.line_ids
            if line_id in project.absorption_lines
        ]
        if not lines:
            return region.region_id[:8]

        display_info = format_region_display(lines, region.analysis_range)
        return display_info.display_name

    def _emit_status(
        self, message: str, timeout_ms: int = 2500, *, undo_hint: bool = False
    ) -> None:
        """Emit a status message through the shell callback."""
        self._ports.status_callback(message, timeout_ms, undo_hint)


def _observed_line_wavelength(line: AbsorptionLine) -> float:
    """Return the observed wavelength for a valid structure line."""
    rest_wavelength = _finite_line_float("rest_wavelength", line.rest_wavelength)
    center_z = _finite_line_float("center_z", line.center_z)
    if rest_wavelength <= 0:
        msg = f"Structure line rest_wavelength must be positive, got {rest_wavelength}."
        raise ValueError(msg)

    observed = rest_wavelength * (1.0 + center_z)
    if not math.isfinite(observed) or observed <= 0:
        msg = f"Structure line observed wavelength must be positive and finite, got {observed}."
        raise ValueError(msg)
    return observed


def _finite_line_float(name: str, value: float) -> float:
    """Return a finite float value from a required structure line field."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        msg = f"Structure line {name} must be numeric, got {type(value).__name__}."
        raise TypeError(msg)
    numeric = float(value)
    if not math.isfinite(numeric):
        msg = f"Structure line {name} must be finite, got {numeric}."
        raise ValueError(msg)
    return numeric
