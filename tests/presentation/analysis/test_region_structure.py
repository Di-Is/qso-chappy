"""Tests for Qt-independent region structure summaries."""

from __future__ import annotations

from chappy.core.absorption.models import AbsorptionLine
from chappy.presentation.analysis import build_region_structure_summary


def _line(
    line_id: str,
    *,
    center_z: float,
    transition_name: str,
    oscillator_strength: float,
    multiplet_ids: list[str] | None = None,
) -> AbsorptionLine:
    return AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=1000.0 + len(line_id),
        center_z=center_z,
        window_kms=150.0,
        multiplet_label="H I Lyman series",
        transition_name=transition_name,
        oscillator_strength=oscillator_strength,
        gamma_value=1.0e8,
        multiplet_ids=list(multiplet_ids or []),
    )


def test_single_line_region_has_one_linked_line() -> None:
    line = _line("lya", center_z=2.3412, transition_name="Lyα", oscillator_strength=0.4164)

    summary = build_region_structure_summary([line])

    assert summary.linked_line_count == 1
    assert summary.line_count == 1
    assert len(summary.linked_lines) == 1
    assert summary.linked_lines[0].center_z == 2.3412
    assert summary.linked_lines[0].transition_names == ("Lyα",)


def test_linked_transitions_are_ordered_by_descending_oscillator_strength() -> None:
    weak = _line(
        "weak",
        center_z=2.3412,
        transition_name="Lyγ",
        oscillator_strength=0.029,
        multiplet_ids=["strong", "middle"],
    )
    strong = _line(
        "strong",
        center_z=2.3412,
        transition_name="Lyα",
        oscillator_strength=0.4164,
        multiplet_ids=["weak", "middle"],
    )
    middle = _line(
        "middle",
        center_z=2.3412,
        transition_name="Lyβ",
        oscillator_strength=0.079,
        multiplet_ids=["weak", "strong"],
    )

    summary = build_region_structure_summary([weak, strong, middle])

    assert summary.linked_line_count == 1
    assert summary.line_count == 3
    assert summary.linked_lines[0].center_z == strong.center_z
    assert summary.linked_lines[0].transition_names == ("Lyα", "Lyβ", "Lyγ")


def test_linked_lines_are_ordered_by_ascending_redshift() -> None:
    high_a = _line(
        "high-a",
        center_z=2.8107,
        transition_name="C IV 1548.2",
        oscillator_strength=0.19,
        multiplet_ids=["high-b"],
    )
    low = _line("low", center_z=2.3412, transition_name="Lyα", oscillator_strength=0.4164)
    high_b = _line(
        "high-b",
        center_z=2.8107,
        transition_name="C IV 1550.8",
        oscillator_strength=0.095,
        multiplet_ids=["high-a"],
    )

    summary = build_region_structure_summary([high_a, low, high_b])

    assert tuple(item.center_z for item in summary.linked_lines) == (2.3412, 2.8107)
    assert summary.linked_lines[1].transition_names == ("C IV 1548.2", "C IV 1550.8")


def test_breakdown_is_omitted_above_linked_line_threshold() -> None:
    lines = [
        _line(
            f"line-{index}",
            center_z=float(index),
            transition_name=f"Line {index}",
            oscillator_strength=1.0,
        )
        for index in range(3)
    ]

    summary = build_region_structure_summary(lines, max_linked_lines=2)

    assert summary.linked_line_count == 3
    assert summary.line_count == 3
    assert summary.linked_lines == ()


def test_empty_input_returns_empty_counts_and_breakdown() -> None:
    summary = build_region_structure_summary([])

    assert summary.linked_line_count == 0
    assert summary.line_count == 0
    assert summary.linked_lines == ()
