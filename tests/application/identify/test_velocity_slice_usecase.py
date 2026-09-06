"""Tests for identify velocity slice candidate use case."""

from __future__ import annotations

from typing import cast

import pytest

from chappy.application.identify import (
    BuildVelocitySliceTemporaryLinesUseCase,
    VelocitySliceTemporaryLineRequest,
    VelocitySliceSelection,
)
from chappy.core.atomic_data import AtomicLine, AtomicLineData
from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth


class _AtomicData:
    """Fake atomic data source for velocity slice tests."""

    def __init__(self, lines: tuple[AtomicLine, ...]) -> None:
        """Initialize indexed atomic lines."""
        self._lines = {line.line_id: line for line in lines}

    def get_line_by_id(self, line_id: str) -> AtomicLine | None:
        """Return a line by identifier."""
        return self._lines.get(line_id)


def _atomic_line(
    line_id: str, wavelength: float, *, multiplet_label: str = "C IV doublet"
) -> AtomicLine:
    """Build an atomic line for velocity slice tests."""
    return AtomicLine(
        line_identifier=line_id,
        species="C IV",
        wavelength_angstrom=wavelength,
        oscillator_strength=0.2,
        gamma_value=1.0,
        multiplet_id="CIV",
        multiplet_label=multiplet_label,
        transition_name=f"C IV {wavelength:.1f}",
    )


def test_build_velocity_slice_candidates_uses_atomic_metadata() -> None:
    """Selected velocity slices become reproducible preview entries."""
    atomic_data = cast(
        "AtomicLineData",
        _AtomicData((_atomic_line("line-a", 1548.2), _atomic_line("line-b", 1550.8))),
    )
    request = VelocitySliceTemporaryLineRequest(
        center_z=2.0,
        new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(100.0),
        slices=(
            VelocitySliceSelection(
                line_id="line-a", label="fallback", is_primary=True, tie_group_key="group"
            ),
            VelocitySliceSelection(
                line_id="line-b", label="fallback", is_primary=False, tie_group_key="group"
            ),
        ),
    )

    entries = BuildVelocitySliceTemporaryLinesUseCase().build(request, atomic_data)

    assert len(entries) == 2
    assert entries[0].line_id == "line-a"
    assert entries[0].label == "C IV 1548.2"
    assert entries[0].is_primary is True
    assert entries[0].tie_group_key == "group"
    assert entries[0].lambda_min < 1548.2 * 3.0 < entries[0].lambda_max
    assert entries[1].line_style == "--"
    assert entries[1].tie_group_key == "group"


def test_build_velocity_slice_candidates_derives_declared_group_label() -> None:
    """Plain catalog lines use their shared species as the declaration label."""
    atomic_data = cast(
        "AtomicLineData", _AtomicData((_atomic_line("line-a", 1548.2, multiplet_label=""),))
    )
    request = VelocitySliceTemporaryLineRequest(
        center_z=2.0,
        new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(100.0),
        slices=(
            VelocitySliceSelection(
                line_id="line-a", label="fallback", is_primary=True, tie_group_key="group"
            ),
        ),
    )

    entries = BuildVelocitySliceTemporaryLinesUseCase().build(request, atomic_data)

    assert entries[0].multiplet_label == "C IV"


def test_build_velocity_slice_candidates_skips_unknown_or_invalid_entries() -> None:
    """Invalid selected slices are ignored instead of producing partial payloads."""
    atomic_data = cast("AtomicLineData", _AtomicData((_atomic_line("line-a", 1548.2),)))
    request = VelocitySliceTemporaryLineRequest(
        center_z=2.0,
        new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(100.0),
        slices=(
            VelocitySliceSelection(
                line_id=None, label="missing", is_primary=True, tie_group_key=""
            ),
            VelocitySliceSelection(
                line_id="unknown", label="missing", is_primary=True, tie_group_key=""
            ),
            VelocitySliceSelection(
                line_id="line-a", label="valid", is_primary=True, tie_group_key=""
            ),
        ),
    )

    entries = BuildVelocitySliceTemporaryLinesUseCase().build(request, atomic_data)

    assert tuple(entry.line_id for entry in entries) == ("line-a",)


def test_build_velocity_slice_candidates_rejects_invalid_window() -> None:
    """A non-positive future-candidate half-width is rejected at the typed boundary."""
    with pytest.raises(ValueError, match="between"):
        NewCandidateAnalysisHalfWidth(0.0)
