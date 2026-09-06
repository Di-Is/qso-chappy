"""Tests for fine-structure excitation markers on transition labels."""

from __future__ import annotations

from spectral_database.data_models import LineRecord
from spectral_database.excitation import LowerLevel, annotate_excitation_labels, excitation_markers

SI_II_GROUND = LowerLevel("Si", 1, 0.0, "3s2.3p", "2P*")
SI_II_EXCITED = LowerLevel("Si", 1, 0.035613, "3s2.3p", "2P*")
O_I_LEVELS = [
    LowerLevel("O", 0, 0.0, "2s2.2p4", "3P"),
    LowerLevel("O", 0, 0.019622, "2s2.2p4", "3P"),
    LowerLevel("O", 0, 0.028142, "2s2.2p4", "3P"),
]


def test_ground_level_has_no_marker() -> None:
    """A transition from the ground level stays unmarked."""
    assert excitation_markers([SI_II_GROUND, SI_II_EXCITED]) == ["", "*"]


def test_marker_count_follows_ground_term_rank() -> None:
    """Asterisk count is the zero-based rank within the ground term."""
    assert excitation_markers(O_I_LEVELS) == ["", "*", "**"]


def test_levels_outside_ground_term_are_unmarked() -> None:
    """Metastable levels of another term carry no marker."""
    levels = [
        LowerLevel("Fe", 1, 0.0, "3d6.(5D).4s", "a 6D"),
        LowerLevel("Fe", 1, 0.121139, "3d6.(5D).4s", "a 6D"),
        LowerLevel("Fe", 1, 0.232173, "3d7", "a 4F"),
    ]

    assert excitation_markers(levels) == ["", "*", ""]


def test_balmer_lower_levels_are_unmarked() -> None:
    """Hydrogen Balmer lines are not fine-structure excited lines."""
    levels = [LowerLevel("H", 0, 0.0, "1s", "2S"), LowerLevel("H", 0, 10.198806, "2p", "2P*")]

    assert excitation_markers(levels) == ["", ""]


def test_ranks_are_scoped_per_species() -> None:
    """Ground terms of different species do not interfere."""
    markers = excitation_markers([SI_II_EXCITED, *O_I_LEVELS, SI_II_GROUND])

    assert markers == ["*", "", "*", "**", ""]


def test_missing_level_data_is_unmarked() -> None:
    """Rows without energy or term information stay unmarked."""
    levels = [
        LowerLevel("C", 1, 0.0, "2s2.2p", "2P*"),
        LowerLevel("C", 1, None, "2s2.2p", "2P*"),
        LowerLevel("C", 1, 0.00786, None, None),
    ]

    assert excitation_markers(levels) == ["", "", ""]


def _record(name: str, energy: float, multiplet_name: str | None = None) -> LineRecord:
    record = LineRecord(
        line_id=f"{name}-{energy}",
        name=name,
        species="Si II",
        wavelength=1194.5002,
        f_value=0.737,
        gamma=4.103e9,
        element_symbol="Si",
        charge_state=1,
        lower_level_energy=energy,
        lower_level_conf="3s2.3p",
        lower_level_term="2P*",
    )
    record.mutiplet_name = multiplet_name
    return record


def test_annotate_updates_name_and_multiplet_label() -> None:
    """Both the line label and its multiplet label take the marker."""
    ground = _record("Si II 1190.4", 0.0, "Si II 1190/1193")
    excited = _record("Si II 1194.5", 0.035613, "Si II 1195/1197")

    annotate_excitation_labels([ground, excited])

    assert ground.name == "Si II 1190.4"
    assert ground.mutiplet_name == "Si II 1190/1193"
    assert excited.name == "Si II 1194.5*"
    assert excited.mutiplet_name == "Si II 1195/1197*"


def test_annotate_leaves_missing_multiplet_label_unset() -> None:
    """A single line without a multiplet label keeps ``None``."""
    excited = _record("Si II 1533.4", 0.035613)
    annotate_excitation_labels([_record("Si II 1526.7", 0.0), excited])

    assert excited.name == "Si II 1533.4*"
    assert excited.mutiplet_name is None
