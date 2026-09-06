"""Tests for absorption region and line topology detection."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from chappy.application.structure.region_line_topology import (
    RegionLineTopologyIssueKind,
    find_region_line_topology_issues,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion


def _line(line_id: str, region_id: str | None) -> AbsorptionLine:
    return AbsorptionLine(
        line_id=line_id,
        species="C IV",
        rest_wavelength=1548.195,
        center_z=0.5,
        window_kms=150.0,
        multiplet_label="C IV",
        transition_name="1548",
        oscillator_strength=0.19,
        gamma_value=2.65e8,
        lambda_range=(2300.0, 2350.0),
        region_id=region_id,
    )


type TopologyCaseFactory = Callable[
    [], tuple[dict[str, AbsorptionRegion], dict[str, AbsorptionLine]]
]


def _missing_reference() -> tuple[dict[str, AbsorptionRegion], dict[str, AbsorptionLine]]:
    return {"region-a": AbsorptionRegion("region-a", ["missing"])}, {}


def _region_line_mismatch() -> tuple[dict[str, AbsorptionRegion], dict[str, AbsorptionLine]]:
    return (
        {"region-a": AbsorptionRegion("region-a", ["line-1"])},
        {"line-1": _line("line-1", "region-b")},
    )


def _duplicate_membership() -> tuple[dict[str, AbsorptionRegion], dict[str, AbsorptionLine]]:
    return (
        {
            "region-a": AbsorptionRegion("region-a", ["line-1"]),
            "region-b": AbsorptionRegion("region-b", ["line-1"]),
        },
        {"line-1": _line("line-1", "region-a")},
    )


def _unlisted_line() -> tuple[dict[str, AbsorptionRegion], dict[str, AbsorptionLine]]:
    return {"region-a": AbsorptionRegion("region-a")}, {"line-1": _line("line-1", "region-a")}


@pytest.mark.parametrize(
    ("factory", "expected_kind"),
    [
        (_missing_reference, RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE),
        (_region_line_mismatch, RegionLineTopologyIssueKind.REGION_LINE_MISMATCH),
        (_duplicate_membership, RegionLineTopologyIssueKind.DUPLICATE_MEMBERSHIP),
        (_unlisted_line, RegionLineTopologyIssueKind.UNLISTED_LINE),
    ],
)
def test_detects_each_region_line_topology_issue(
    factory: TopologyCaseFactory, expected_kind: RegionLineTopologyIssueKind
) -> None:
    """Each supported topology violation is reported."""
    regions, lines = factory()

    issues = find_region_line_topology_issues(regions, lines)

    assert expected_kind in {issue.kind for issue in issues}


def test_consistent_topology_has_no_issues() -> None:
    """A bidirectionally consistent topology produces an empty result."""
    regions = {"region-a": AbsorptionRegion("region-a", ["line-1"])}
    lines = {"line-1": _line("line-1", "region-a")}

    assert find_region_line_topology_issues(regions, lines) == ()


def test_issue_order_is_deterministic_by_region_identity() -> None:
    """Detection is independent of input mapping insertion order."""
    regions = {
        "region-z": AbsorptionRegion("region-z", ["missing-z"]),
        "region-a": AbsorptionRegion("region-a", ["missing-a"]),
    }

    issues = find_region_line_topology_issues(regions, {})

    assert [(issue.region_id, issue.line_id) for issue in issues] == [
        ("region-a", "missing-a"),
        ("region-z", "missing-z"),
    ]
