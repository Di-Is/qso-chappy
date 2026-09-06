"""Typed outcomes for atomic scientific structure mutations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chappy.core.absorption.models import AbsorptionRegion
    from chappy.core.change_set import ChangeSet


class StructureInvalidationScope(StrEnum):
    """How a structure mutation selects surviving regions to invalidate."""

    LOCAL_SURVIVORS = "local_survivors"
    ALL_ANALYSIS_CAPABLE_SURVIVORS = "all_analysis_capable_survivors"


class StructureMutationOutcome(StrEnum):
    """Whether a structure command changed scientific project state."""

    CHANGED = "changed"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True)
class StructureRegionDelta:
    """Region and surviving-line topology changed by one mutation."""

    invalidation_scope: StructureInvalidationScope
    affected_surviving_region_ids: tuple[str, ...] = ()
    created_region_ids: tuple[str, ...] = ()
    removed_region_ids: tuple[str, ...] = ()
    changed_surviving_line_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize identities and require three pairwise-disjoint sets."""
        affected = self._normalize("affected surviving", self.affected_surviving_region_ids)
        created = self._normalize("created", self.created_region_ids)
        removed = self._normalize("removed", self.removed_region_ids)
        changed_lines = self._normalize("changed surviving line", self.changed_surviving_line_ids)
        object.__setattr__(self, "affected_surviving_region_ids", affected)
        object.__setattr__(self, "created_region_ids", created)
        object.__setattr__(self, "removed_region_ids", removed)
        object.__setattr__(self, "changed_surviving_line_ids", changed_lines)

        intersections = (
            set(affected) & set(created),
            set(affected) & set(removed),
            set(created) & set(removed),
        )
        if any(intersections):
            msg = "Affected, created, and removed structure region identities must be disjoint."
            raise ValueError(msg)

    @staticmethod
    def _normalize(label: str, region_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Deduplicate non-empty identities while preserving first-seen order."""
        normalized = tuple(dict.fromkeys(region_ids))
        if any(not region_id for region_id in normalized):
            msg = f"Structure {label} region identities cannot be empty."
            raise ValueError(msg)
        return normalized


@dataclass(frozen=True, slots=True)
class StructureMutationResult[T]:
    """Typed changed or no-change result returned by a structure command."""

    outcome: StructureMutationOutcome
    value: T | None = None
    delta: StructureRegionDelta | None = None

    def __post_init__(self) -> None:
        """Require a delta exactly when scientific structure changed."""
        if self.outcome is StructureMutationOutcome.CHANGED and self.delta is None:
            msg = "A changed structure mutation requires a region delta."
            raise ValueError(msg)
        if self.outcome is StructureMutationOutcome.NO_CHANGE and self.delta is not None:
            msg = "A no-change structure mutation cannot carry a region delta."
            raise ValueError(msg)

    @property
    def changed(self) -> bool:
        """Return whether scientific structure changed."""
        return self.outcome is StructureMutationOutcome.CHANGED

    @classmethod
    def changed_result(cls, value: T, delta: StructureRegionDelta) -> StructureMutationResult[T]:
        """Build a changed command result."""
        return cls(outcome=StructureMutationOutcome.CHANGED, value=value, delta=delta)

    @classmethod
    def no_change(cls) -> StructureMutationResult[T]:
        """Build an inert command result."""
        return cls(outcome=StructureMutationOutcome.NO_CHANGE)


@dataclass(frozen=True, slots=True)
class AtomicStructureMutationExecution[T]:
    """Committed structure result plus changes safe to publish after commit."""

    result: StructureMutationResult[T]
    postcommit_changes: ChangeSet


@dataclass(frozen=True, slots=True)
class StructureMoveResult:
    """Result of moving absorption lines between structure regions."""

    destination_id: str
    moved_linked_line_count: int
    destination_region: AbsorptionRegion | None


@dataclass(frozen=True, slots=True)
class StructureMergeResult:
    """Result of merging structure regions."""

    merged_region: AbsorptionRegion


@dataclass(frozen=True, slots=True)
class StructureSplitResult:
    """Result of splitting selected lines into a new structure region."""

    new_region: AbsorptionRegion | None


@dataclass(frozen=True, slots=True)
class StructureDeleteResult:
    """Result of deleting structure regions or linked lines."""

    groups_removed: int
    lines_removed: int


@dataclass(frozen=True, slots=True)
class StructureUnlinkResult:
    """Result of unlinking one materialized linked-line group."""

    unlinked_line_ids: tuple[str, ...]


__all__ = [
    "AtomicStructureMutationExecution",
    "StructureDeleteResult",
    "StructureInvalidationScope",
    "StructureMergeResult",
    "StructureMoveResult",
    "StructureMutationOutcome",
    "StructureMutationResult",
    "StructureRegionDelta",
    "StructureSplitResult",
    "StructureUnlinkResult",
]
