"""Detect bidirectional absorption region and line topology issues."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from chappy.core.absorption.models import UNASSIGNED_REGION_ID

if TYPE_CHECKING:
    from collections.abc import Mapping

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion


class RegionLineTopologyIssueKind(StrEnum):
    """Kinds of invalid region-to-line topology."""

    MISSING_LINE_REFERENCE = "missing_line_reference"
    REGION_LINE_MISMATCH = "region_line_mismatch"
    DUPLICATE_MEMBERSHIP = "duplicate_membership"
    UNLISTED_LINE = "unlisted_line"


@dataclass(frozen=True, slots=True)
class RegionLineTopologyIssue:
    """One invalid region-to-line relationship."""

    kind: RegionLineTopologyIssueKind
    region_id: str
    line_id: str


def find_region_line_topology_issues(
    regions: Mapping[str, AbsorptionRegion], lines: Mapping[str, AbsorptionLine]
) -> tuple[RegionLineTopologyIssue, ...]:
    """Return all region-to-line topology violations in deterministic order."""
    issues: list[RegionLineTopologyIssue] = []
    seen_issues: set[tuple[RegionLineTopologyIssueKind, str, str]] = set()
    memberships: dict[str, list[str]] = {line_id: [] for line_id in lines}

    def add_issue(kind: RegionLineTopologyIssueKind, region_id: str, line_id: str) -> None:
        identity = (kind, region_id, line_id)
        if identity in seen_issues:
            return
        seen_issues.add(identity)
        issues.append(RegionLineTopologyIssue(kind, region_id, line_id))

    for region_id in sorted(regions):
        region = regions[region_id]
        region_identity_matches = region.region_id == region_id
        for line_id in region.line_ids:
            line = lines.get(line_id)
            if line is None:
                add_issue(RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE, region_id, line_id)
                continue

            memberships[line_id].append(region_id)
            if not region_identity_matches:
                add_issue(RegionLineTopologyIssueKind.REGION_LINE_MISMATCH, region_id, line_id)

        if not region_identity_matches and not region.line_ids:
            add_issue(RegionLineTopologyIssueKind.REGION_LINE_MISMATCH, region_id, "")

    for line_id in sorted(lines):
        line = lines[line_id]
        owner_ids = memberships[line_id]
        if not owner_ids:
            region_id = line.region_id or UNASSIGNED_REGION_ID
            if line.line_id != line_id:
                add_issue(RegionLineTopologyIssueKind.REGION_LINE_MISMATCH, region_id, line_id)
            add_issue(RegionLineTopologyIssueKind.UNLISTED_LINE, region_id, line_id)
            continue

        owner_id = min(owner_ids)
        for region_id in sorted(set(owner_ids)):
            if region_id != owner_id or owner_ids.count(region_id) > 1:
                add_issue(RegionLineTopologyIssueKind.DUPLICATE_MEMBERSHIP, region_id, line_id)
        if line.line_id != line_id or line.region_id != owner_id:
            add_issue(RegionLineTopologyIssueKind.REGION_LINE_MISMATCH, owner_id, line_id)

    return tuple(issues)
