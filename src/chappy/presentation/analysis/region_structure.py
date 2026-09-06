"""Qt- and translation-independent region structure summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.core.absorption_display import group_lines_by_multiplet, sort_lines_for_display

if TYPE_CHECKING:
    from collections.abc import Sequence

    from chappy.core.absorption.models import AbsorptionLine

MAX_LINKED_LINES_WITH_BREAKDOWN = 6


@dataclass(frozen=True, slots=True)
class LinkedLineSummary:
    """One linked line's redshift and transitions in display order."""

    center_z: float
    transition_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegionStructureSummary:
    """Counts and optional linked-line breakdown for one region."""

    linked_line_count: int
    line_count: int
    linked_lines: tuple[LinkedLineSummary, ...]


def build_region_structure_summary(
    lines: Sequence[AbsorptionLine], *, max_linked_lines: int = MAX_LINKED_LINES_WITH_BREAKDOWN
) -> RegionStructureSummary:
    """Build a region structure summary in the canonical display order."""
    groups = group_lines_by_multiplet(sort_lines_for_display(lines))
    linked_line_count = len(groups)
    if linked_line_count > max_linked_lines:
        linked_lines: tuple[LinkedLineSummary, ...] = ()
    else:
        linked_lines = tuple(
            LinkedLineSummary(
                center_z=group[0].center_z,
                transition_names=tuple(line.transition_name for line in group),
            )
            for group in groups
        )
    return RegionStructureSummary(
        linked_line_count=linked_line_count, line_count=len(lines), linked_lines=linked_lines
    )


__all__ = [
    "MAX_LINKED_LINES_WITH_BREAKDOWN",
    "LinkedLineSummary",
    "RegionStructureSummary",
    "build_region_structure_summary",
]
