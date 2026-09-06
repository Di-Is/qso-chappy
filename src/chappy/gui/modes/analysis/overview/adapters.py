"""Structure-mode operation adapter for GUI controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.application.structure import (
    StructureDeleteResult,
    StructureHistoryRecorder,
    StructureMergeResult,
    StructureMoveResult,
    StructureProjectPort,
    StructureSplitResult,
    StructureUnlinkResult,
)

if TYPE_CHECKING:
    from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase


class StructureOperationAdapter:
    """Delegate structure project operations to application use cases."""

    def __init__(self, use_case: StructureOperationUseCase) -> None:
        """Initialize the adapter.

        Args:
            use_case: Structure operation use case.
        """
        self._use_case = use_case

    def move_lines(
        self,
        project: StructureProjectPort,
        *,
        line_ids: list[str],
        target_region_id: str | None,
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureMoveResult | None:
        """Move selected lines to a target region."""
        return self._use_case.move_lines(
            project,
            line_ids=line_ids,
            target_region_id=target_region_id,
            history_recorder=history_recorder,
        )

    def merge_regions(
        self,
        project: StructureProjectPort,
        *,
        group_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureMergeResult | None:
        """Merge selected regions into the primary region."""
        return self._use_case.merge_regions(
            project, group_ids=group_ids, history_recorder=history_recorder
        )

    def split_lines(
        self,
        project: StructureProjectPort,
        *,
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureSplitResult | None:
        """Split selected lines into a new region."""
        return self._use_case.split_lines(
            project, linked_line_ids=linked_line_ids, history_recorder=history_recorder
        )

    def delete_selection(
        self,
        project: StructureProjectPort,
        *,
        group_ids: list[str],
        linked_line_ids: list[str],
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureDeleteResult | None:
        """Delete selected regions and linked lines."""
        return self._use_case.delete_selection(
            project,
            group_ids=group_ids,
            linked_line_ids=linked_line_ids,
            history_recorder=history_recorder,
        )

    def unlink_linked_lines(
        self,
        project: StructureProjectPort,
        *,
        line_id: str,
        history_recorder: StructureHistoryRecorder | None,
    ) -> StructureUnlinkResult | None:
        """Remove the materialized links for one selected linked-line group."""
        return self._use_case.unlink_linked_lines(
            project, line_id=line_id, history_recorder=history_recorder
        )


__all__ = [
    "StructureDeleteResult",
    "StructureHistoryRecorder",
    "StructureMergeResult",
    "StructureMoveResult",
    "StructureOperationAdapter",
    "StructureProjectPort",
    "StructureSplitResult",
    "StructureUnlinkResult",
]
