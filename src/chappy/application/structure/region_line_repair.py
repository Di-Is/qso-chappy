"""Repair invalid bidirectional absorption region and line topology."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.application.structure.region_line_topology import (
    RegionLineTopologyIssue,
    RegionLineTopologyIssueKind,
    find_region_line_topology_issues,
)
from chappy.core.absorption.registry import AbsorptionRegistry

if TYPE_CHECKING:
    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion


@dataclass(frozen=True, slots=True)
class RegionLineRepairAction:
    """One user-reportable repair applied to a line relationship."""

    kind: RegionLineTopologyIssueKind
    region_id: str
    line_id: str
    line_species: str
    line_transition: str


@dataclass(frozen=True, slots=True)
class RegionLineRepairReport:
    """Repairs applied while restoring a project."""

    actions: tuple[RegionLineRepairAction, ...]

    @property
    def has_repairs(self) -> bool:
        """Return whether any topology repair was applied."""
        return bool(self.actions)


class RepairRegionLineTopologyUseCase:
    """Restore deterministic bidirectional region and line ownership."""

    def execute(
        self, regions: dict[str, AbsorptionRegion], lines: dict[str, AbsorptionLine]
    ) -> RegionLineRepairReport:
        """Mutate regions and lines in place to restore bidirectional consistency."""
        issues = find_region_line_topology_issues(regions, lines)
        if not issues:
            return RegionLineRepairReport(actions=())

        registry = AbsorptionRegistry()
        registry.regions = regions
        registry.lines = lines
        affected_region_ids: set[str] = set()

        for region_id, region in regions.items():
            retained_line_ids = [line_id for line_id in region.line_ids if line_id in lines]
            if retained_line_ids != region.line_ids:
                region.line_ids = retained_line_ids
                affected_region_ids.add(region_id)

        memberships = self._memberships(regions, lines)
        for line_id, line in lines.items():
            owner_ids = memberships[line_id]
            if owner_ids:
                owner_id = owner_ids[0]
                for region_id in owner_ids[1:]:
                    regions[region_id].remove_lines([line_id])
                    affected_region_ids.add(region_id)
                owner_region = regions[owner_id]
                normalized_ids = list(dict.fromkeys(owner_region.line_ids))
                if normalized_ids != owner_region.line_ids:
                    owner_region.line_ids = normalized_ids
                    affected_region_ids.add(owner_id)
                if line.region_id != owner_id:
                    line.region_id = owner_id
                    affected_region_ids.add(owner_id)
                continue

            unassigned = registry.ensure_unassigned_region()
            unassigned.attach_lines([line_id])
            line.region_id = unassigned.region_id
            affected_region_ids.add(unassigned.region_id)

        for region_id in sorted(affected_region_ids):
            registry.update_region_analysis_range(region_id)
            registry.set_region_needs_optimization(region_id, needs_optimization=True)

        return RegionLineRepairReport(actions=self._actions_for_issues(issues, lines))

    @staticmethod
    def _memberships(
        regions: dict[str, AbsorptionRegion], lines: dict[str, AbsorptionLine]
    ) -> dict[str, tuple[str, ...]]:
        owners: dict[str, set[str]] = {line_id: set() for line_id in lines}
        for region_id, region in regions.items():
            for line_id in region.line_ids:
                if line_id in owners:
                    owners[line_id].add(region_id)
        return {line_id: tuple(sorted(region_ids)) for line_id, region_ids in owners.items()}

    @staticmethod
    def _actions_for_issues(
        issues: tuple[RegionLineTopologyIssue, ...], lines: dict[str, AbsorptionLine]
    ) -> tuple[RegionLineRepairAction, ...]:
        actions: list[RegionLineRepairAction] = []
        for issue in issues:
            line = lines.get(issue.line_id)
            actions.append(
                RegionLineRepairAction(
                    kind=issue.kind,
                    region_id=issue.region_id,
                    line_id=issue.line_id,
                    line_species=line.species if line is not None else "",
                    line_transition=line.transition_name if line is not None else "",
                )
            )
        return tuple(actions)
