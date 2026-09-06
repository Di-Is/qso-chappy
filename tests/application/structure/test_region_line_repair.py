"""Tests for deterministic absorption region and line topology repair."""

from __future__ import annotations

from chappy.application.structure.region_line_repair import RepairRegionLineTopologyUseCase
from chappy.application.structure.region_line_topology import (
    RegionLineTopologyIssueKind,
    find_region_line_topology_issues,
)
from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion


def _line(
    line_id: str, region_id: str | None, *, wavelength_range: tuple[float, float]
) -> AbsorptionLine:
    return AbsorptionLine(
        line_id=line_id,
        species="C IV",
        rest_wavelength=1548.195,
        center_z=0.5,
        window_kms=150.0,
        multiplet_label="C IV",
        transition_name=line_id,
        oscillator_strength=0.19,
        gamma_value=2.65e8,
        lambda_range=wavelength_range,
        region_id=region_id,
    )


def test_repairs_all_issue_kinds_with_region_membership_as_authority() -> None:
    """Repair applies every resolution rule and records human-readable actions."""
    regions = {
        "region-b": AbsorptionRegion(
            "region-b", ["shared", "mismatch"], analysis_range=(1.0, 2.0)
        ),
        "region-a": AbsorptionRegion(
            "region-a", ["shared", "owned", "missing"], analysis_range=(1.0, 2.0)
        ),
    }
    lines = {
        "shared": _line("shared", "region-b", wavelength_range=(10.0, 20.0)),
        "owned": _line("owned", "region-a", wavelength_range=(30.0, 40.0)),
        "mismatch": _line("mismatch", "missing-region", wavelength_range=(50.0, 60.0)),
        "unlisted": _line("unlisted", "missing-region", wavelength_range=(70.0, 80.0)),
    }

    report = RepairRegionLineTopologyUseCase().execute(regions, lines)

    assert report.has_repairs is True
    assert {action.kind for action in report.actions} == {
        RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE,
        RegionLineTopologyIssueKind.REGION_LINE_MISMATCH,
        RegionLineTopologyIssueKind.DUPLICATE_MEMBERSHIP,
        RegionLineTopologyIssueKind.UNLISTED_LINE,
    }
    assert all(
        action.line_species == "C IV"
        for action in report.actions
        if action.kind is not RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE
    )
    assert regions["region-a"].line_ids == ["shared", "owned"]
    assert regions["region-b"].line_ids == ["mismatch"]
    assert regions[UNASSIGNED_REGION_ID].line_ids == ["unlisted"]
    assert lines["shared"].region_id == "region-a"
    assert lines["mismatch"].region_id == "region-b"
    assert lines["unlisted"].region_id == UNASSIGNED_REGION_ID
    assert regions["region-a"].analysis_range == (10.0, 40.0)
    assert regions["region-b"].analysis_range == (50.0, 60.0)
    assert regions[UNASSIGNED_REGION_ID].analysis_range == (70.0, 80.0)
    assert all(line.needs_optimization for line in lines.values())
    assert find_region_line_topology_issues(regions, lines) == ()


def test_duplicate_owner_is_lexicographically_smallest_region() -> None:
    """Duplicate membership resolution does not depend on mapping insertion order."""
    regions = {
        "region-z": AbsorptionRegion("region-z", ["line-1"]),
        "region-a": AbsorptionRegion("region-a", ["line-1"]),
    }
    lines = {"line-1": _line("line-1", "region-z", wavelength_range=(10.0, 20.0))}

    RepairRegionLineTopologyUseCase().execute(regions, lines)

    assert regions["region-a"].line_ids == ["line-1"]
    assert regions["region-z"].line_ids == []
    assert lines["line-1"].region_id == "region-a"


def test_consistent_topology_is_not_mutated() -> None:
    """A consistent input returns an empty report without changing freshness."""
    regions = {"region-a": AbsorptionRegion("region-a", ["line-1"])}
    lines = {"line-1": _line("line-1", "region-a", wavelength_range=(10.0, 20.0))}

    report = RepairRegionLineTopologyUseCase().execute(regions, lines)

    assert report.has_repairs is False
    assert lines["line-1"].needs_optimization is False
