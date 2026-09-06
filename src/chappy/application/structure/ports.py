"""Structure-mode application ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from chappy.application.analysis_artifacts import RegionLocalMutationProjectPort
from chappy.application.structure.atomic_mutation_executor import AtomicStructureProjectPort

if TYPE_CHECKING:
    from collections.abc import Sequence
    from contextlib import AbstractContextManager

    from chappy.application.history import (
        AbsorptionLineSnapshot,
        StructureDeleteModelHistorySnapshot,
        StructureMoveHistoryPayload,
        StructureStateSnapshot,
        StructureUnlinkHistoryPayload,
    )
    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion


class StructureProjectPort(AtomicStructureProjectPort, RegionLocalMutationProjectPort, Protocol):
    """Minimal project operations required by structure use cases."""

    def find_absorption_line(self, line_id: str) -> AbsorptionLine | None:
        """Return an absorption line by ID."""
        ...

    def find_absorption_region(self, region_id: str) -> AbsorptionRegion | None:
        """Return an absorption region by ID."""
        ...

    def expand_multiplet_line_ids(self, seed_ids: Sequence[str]) -> list[str]:
        """Expand line IDs with multiplet companions."""
        ...

    def move_absorption_lines(
        self, line_ids: list[str], *, target_region_id: str | None
    ) -> str | None:
        """Move lines into a target region."""
        ...

    def merge_absorption_regions(self, region_ids: list[str]) -> AbsorptionRegion | None:
        """Merge regions into the primary selected region."""
        ...

    def unlink_linked_lines(self, line_id: str) -> tuple[str, ...]:
        """Unlink one materialized linked-line group and return changed line IDs."""
        ...

    def remove_absorption_region(self, region_id: str, *, delete_models: bool = True) -> int:
        """Remove an absorption region."""
        ...

    def remove_absorption_lines_with_multiplet(
        self, line_ids: list[str], *, delete_models: bool = True
    ) -> int:
        """Remove selected lines and multiplet companions."""
        ...


@runtime_checkable
class StructureMoveHistoryRecorder(Protocol):
    """History recorder interface needed by atomic structure moves."""

    def record_structure_move_linked_lines(self, payload: StructureMoveHistoryPayload) -> None:
        """Record moved structure linked lines."""
        ...

    def atomic_recording(self) -> AbstractContextManager[None]:
        """Return the history-only rollback scope required by forward moves."""
        ...


@runtime_checkable
class StructureHistoryRecorder(StructureMoveHistoryRecorder, Protocol):
    """History recorder interface needed by all structure operations."""

    def record_structure_split(
        self,
        expanded_line_ids: tuple[str, ...],
        source_region_id: str,
        new_region_id: str,
        before: StructureStateSnapshot,
        after: StructureStateSnapshot,
    ) -> None:
        """Record a structure split operation."""
        ...

    def record_structure_merge(
        self,
        primary_region_id: str,
        secondary_region_ids: tuple[str, ...],
        before: StructureStateSnapshot,
        after: StructureStateSnapshot,
    ) -> None:
        """Record a structure merge operation."""
        ...

    def record_structure_delete(
        self,
        target_region_ids: tuple[str, ...],
        target_line_ids: tuple[str, ...],
        deleted_lines: tuple[AbsorptionLineSnapshot, ...],
        before: StructureStateSnapshot,
        after: StructureStateSnapshot,
        deleted_model_history: StructureDeleteModelHistorySnapshot | None,
    ) -> None:
        """Record a structure delete operation."""
        ...

    def record_structure_unlink(self, payload: StructureUnlinkHistoryPayload) -> None:
        """Record one materialized linked-line unlink operation."""
        ...


__all__ = ["StructureHistoryRecorder", "StructureMoveHistoryRecorder", "StructureProjectPort"]
