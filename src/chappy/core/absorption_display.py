"""Display ordering and grouping helpers for absorption lines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from chappy.core.absorption.models import AbsorptionLine


@dataclass(frozen=True)
class RegionDisplayInfo:
    """Display information for an absorption region.

    Attributes:
        display_name: Basic display name with species set.
        tooltip: Detailed tooltip with transition names.
    """

    display_name: str
    tooltip: str


def sort_lines_for_display(lines: Sequence[AbsorptionLine]) -> list[AbsorptionLine]:
    """Sort absorption lines for consistent display order.

    Args:
        lines: Absorption lines to sort.

    Returns:
        New list containing lines ordered by center redshift, rest wavelength, and line ID.
    """
    return sorted(lines, key=lambda line: (line.center_z, line.rest_wavelength, line.line_id))


def group_lines_by_multiplet(lines: Sequence[AbsorptionLine]) -> list[list[AbsorptionLine]]:
    """Group absorption lines by multiplet cross-references.

    Args:
        lines: Absorption lines to group. The input order determines group order.

    Returns:
        Groups of absorption lines. Lines inside each group are ordered by oscillator strength,
        then rest wavelength and line ID.
    """
    if not lines:
        return []

    line_map: dict[str, AbsorptionLine] = {line.line_id: line for line in lines}
    parent: dict[str, str] = {line_id: line_id for line_id in line_map}

    def find(line_id: str) -> str:
        """Find the root line ID with path compression."""
        if parent[line_id] != line_id:
            parent[line_id] = find(parent[line_id])
        return parent[line_id]

    def union(left_id: str, right_id: str) -> None:
        """Merge the two line ID sets."""
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[left_root] = right_root

    for line in lines:
        for related_id in line.multiplet_ids:
            if related_id in line_map:
                union(line.line_id, related_id)

    groups_by_root: dict[str, list[AbsorptionLine]] = {}
    root_first_seen: dict[str, int] = {}

    for index, line in enumerate(lines):
        root = find(line.line_id)
        if root not in groups_by_root:
            groups_by_root[root] = []
            root_first_seen[root] = index
        groups_by_root[root].append(line)

    sorted_roots = sorted(groups_by_root, key=lambda root: root_first_seen[root])

    def sort_key(line: AbsorptionLine) -> tuple[bool, float, float, str]:
        """Build a stable sort key for lines within one multiplet group."""
        oscillator_strength = line.oscillator_strength
        missing_oscillator_strength = oscillator_strength <= 0
        return (
            missing_oscillator_strength,
            -oscillator_strength,
            line.rest_wavelength,
            line.line_id,
        )

    return [sorted(groups_by_root[root], key=sort_key) for root in sorted_roots]


def iter_component_display_rows[ComponentT](
    lines: Sequence[AbsorptionLine], resolve: Callable[[str], ComponentT | None]
) -> Iterator[tuple[AbsorptionLine, ComponentT, int]]:
    """Iterate a multiplet group's components with their display numbering.

    Single source of truth shared by the optimize tree and CSV export so both
    surfaces enumerate the same components with identical ``cN`` ordinals.

    Args:
        lines: Lines of one multiplet group, in display order.
        resolve: Lookup from model ID to component; None skips the entry.

    Yields:
        Tuples of owning line, resolved component, and one-based display ordinal.
        Single-line groups keep the model-ID position even when earlier entries
        do not resolve; multi-line groups restart compacted numbering per line.
    """
    if len(lines) == 1:
        line = lines[0]
        for display_ordinal, model_id in enumerate(line.model_ids, start=1):
            component = resolve(model_id)
            if component is not None:
                yield line, component, display_ordinal
        return

    seen_model_ids: set[str] = set()
    for line in lines:
        display_ordinal = 0
        for model_id in line.model_ids:
            component = resolve(model_id)
            if component is None or model_id in seen_model_ids:
                continue
            seen_model_ids.add(model_id)
            display_ordinal += 1
            yield line, component, display_ordinal


def format_region_display(
    lines: Sequence[AbsorptionLine], analysis_range: tuple[float, float] | None
) -> RegionDisplayInfo:
    """Generate display information for an absorption region.

    Args:
        lines: Absorption lines in the region. Must not be empty.
        analysis_range: Wavelength range, or None when the region has no explicit range.

    Returns:
        Display name and tooltip text for the region.

    Raises:
        ValueError: If lines is empty.
    """
    if not lines:
        msg = "lines must not be empty"
        raise ValueError(msg)

    linked_line_count = len(group_lines_by_multiplet(lines))
    range_part = ""
    if analysis_range is not None:
        range_part = f"@ {analysis_range[0]:.1f}-{analysis_range[1]:.1f} "

    species_set = {line.species for line in lines}
    species_part = "|".join(sorted(species_set))
    display_name = f"{species_part} {range_part}({linked_line_count})".strip()

    detail_names = {line.multiplet_label or line.transition_name for line in lines}
    detail_part = "|".join(sorted(detail_names))
    tooltip = f"{detail_part} {range_part}({linked_line_count})".strip()

    return RegionDisplayInfo(display_name=display_name, tooltip=tooltip)


__all__ = [
    "RegionDisplayInfo",
    "format_region_display",
    "group_lines_by_multiplet",
    "iter_component_display_rows",
    "sort_lines_for_display",
]
