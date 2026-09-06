"""Controller for structure-mode project operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from chappy.application.structure import (
    DeleteStructureRequest,
    StructureImpactPreviewUseCase,
    StructureImpactProjectPort,
    UnlinkStructureRequest,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.application.structure import StructureImpactPreview
    from chappy.gui.modes.analysis.overview.adapters import (
        StructureDeleteResult,
        StructureHistoryRecorder,
        StructureMergeResult,
        StructureMoveResult,
        StructureOperationAdapter,
        StructureProjectPort,
        StructureSplitResult,
        StructureUnlinkResult,
    )


MERGE_SELECTION_THRESHOLD = 2
SINGLE_SELECTION = 1


class StructureOperationController(QObject):
    """Coordinate structure-mode operation validation and use case dispatch."""

    def __init__(
        self,
        *,
        operation_adapter: StructureOperationAdapter,
        impact_previewer: StructureImpactPreviewUseCase | None = None,
        status_callback: Callable[[str], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the controller.

        Args:
            operation_adapter: Operation adapter dependency.
            impact_previewer: Side-effect-free structure impact use case.
            status_callback: Optional callback for validation and failure messages.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._operation_adapter = operation_adapter
        self._impact_previewer = impact_previewer or StructureImpactPreviewUseCase()
        self._status_callback = status_callback

    def move_lines(
        self,
        project: StructureProjectPort | None,
        *,
        line_ids: list[str],
        target_region_id: str | None,
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureMoveResult | None:
        """Move selected lines to a target region."""
        if project is None or not line_ids:
            self._emit_status(self.tr("No project loaded."))
            return None

        result = self._operation_adapter.move_lines(
            project,
            line_ids=line_ids,
            target_region_id=target_region_id,
            history_recorder=history_recorder,
        )
        if result is None:
            self._emit_status(self.tr("Failed to move selected lines."))
        return result

    def can_merge(self, group_ids: list[str], linked_line_ids: list[str]) -> bool:
        """Return whether the current selection can be merged."""
        return len(group_ids) >= MERGE_SELECTION_THRESHOLD and not linked_line_ids

    def can_split(self, group_ids: list[str], linked_line_ids: list[str]) -> bool:
        """Return whether the current selection can be split."""
        return len(linked_line_ids) == SINGLE_SELECTION and not group_ids

    def can_delete(self, group_ids: list[str], linked_line_ids: list[str]) -> bool:
        """Return whether the current selection can be deleted."""
        return (len(group_ids) == SINGLE_SELECTION and not linked_line_ids) or (
            len(linked_line_ids) == SINGLE_SELECTION and not group_ids
        )

    def can_focus(self, group_ids: list[str], linked_line_ids: list[str]) -> bool:
        """Return whether the current selection can be focused in the spectrum view."""
        return self.can_delete(group_ids, linked_line_ids)

    def can_unlink(
        self,
        project: StructureImpactProjectPort | None,
        group_ids: list[str],
        linked_line_ids: list[str],
    ) -> bool:
        """Return whether one selected line belongs to materialized linked lines."""
        if project is None or group_ids or len(linked_line_ids) != SINGLE_SELECTION:
            return False
        selected = project.absorption_lines.get(linked_line_ids[0])
        return selected is not None and bool(selected.multiplet_ids)

    def merge_regions(
        self,
        project: StructureProjectPort | None,
        *,
        group_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureMergeResult | None:
        """Merge selected regions into the primary region."""
        if project is None:
            self._emit_status(self.tr("No project loaded."))
            return None
        if len(group_ids) < MERGE_SELECTION_THRESHOLD:
            self._emit_status(self.tr("Select at least two regions to merge."))
            return None

        result = self._operation_adapter.merge_regions(
            project, group_ids=group_ids, history_recorder=history_recorder
        )
        if result is None:
            self._emit_status(self.tr("Failed to merge the selected regions."))
        return result

    def split_lines(
        self,
        project: StructureProjectPort | None,
        *,
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureSplitResult | None:
        """Split one selected line into a new region."""
        if project is None:
            self._emit_status(self.tr("No project loaded."))
            return None
        if len(linked_line_ids) != SINGLE_SELECTION:
            self._emit_status(self.tr("Select exactly one line to split."))
            return None

        result = self._operation_adapter.split_lines(
            project, linked_line_ids=linked_line_ids, history_recorder=history_recorder
        )
        if result is None:
            self._emit_status(self.tr("Failed to split the selected line."))
        return result

    def delete_selection(
        self,
        project: StructureProjectPort | None,
        *,
        group_ids: list[str],
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureDeleteResult | None:
        """Delete selected regions and linked lines."""
        if project is None:
            self._emit_status(self.tr("No project loaded."))
            return None
        if not group_ids and not linked_line_ids:
            self._emit_status(self.tr("Select regions or lines to delete."))
            return None

        result = self._operation_adapter.delete_selection(
            project,
            group_ids=group_ids,
            linked_line_ids=linked_line_ids,
            history_recorder=history_recorder,
        )
        if result is None:
            self._emit_status(self.tr("Failed to delete the selected items."))
        return result

    def preview_delete(
        self,
        project: StructureImpactProjectPort | None,
        *,
        group_ids: list[str],
        linked_line_ids: list[str],
    ) -> StructureImpactPreview | None:
        """Resolve the exact delete impact without mutating project or UI state."""
        if project is None:
            self._emit_status(self.tr("No project loaded."))
            return None
        preview = self._impact_previewer.preview_delete(
            project,
            DeleteStructureRequest(region_ids=tuple(group_ids), line_ids=tuple(linked_line_ids)),
        )
        if not preview.changed:
            self._emit_status(self.tr("Select regions or lines to delete."))
            return None
        return preview

    def preview_unlink(
        self, project: StructureImpactProjectPort | None, *, linked_line_ids: list[str]
    ) -> StructureImpactPreview | None:
        """Resolve the exact unlink impact without mutating project or UI state."""
        if project is None:
            self._emit_status(self.tr("No project loaded."))
            return None
        if len(linked_line_ids) != SINGLE_SELECTION:
            self._emit_status(self.tr("Select exactly one linked line to unlink."))
            return None
        preview = self._impact_previewer.preview_unlink(
            project, UnlinkStructureRequest(line_id=linked_line_ids[0])
        )
        if not preview.changed:
            self._emit_status(self.tr("The selected line is not linked to other lines."))
            return None
        return preview

    def unlink_linked_lines(
        self,
        project: StructureProjectPort | None,
        *,
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureUnlinkResult | None:
        """Unlink one selected materialized linked-line group."""
        if project is None:
            self._emit_status(self.tr("No project loaded."))
            return None
        if len(linked_line_ids) != SINGLE_SELECTION:
            self._emit_status(self.tr("Select exactly one linked line to unlink."))
            return None
        result = self._operation_adapter.unlink_linked_lines(
            project, line_id=linked_line_ids[0], history_recorder=history_recorder
        )
        if result is None:
            self._emit_status(self.tr("The selected line is not linked to other lines."))
        return result

    def _emit_status(self, message: str) -> None:
        """Emit a status message through the optional shell callback."""
        if self._status_callback is not None:
            self._status_callback(message)
