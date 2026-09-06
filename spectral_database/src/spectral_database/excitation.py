"""Fine-structure excitation markers for transition labels.

Absorption-line studies mark a transition whose lower level is a fine-structure
excited level of the ground term with trailing asterisks (``Si II*``, ``O I**``,
``Fe II****``), matching the notation used by VPFIT ``atom.dat``. The number of
asterisks is the zero-based rank of the lower level within the ground term,
ordered by energy. Lower levels outside the ground term (``Fe II a 4F``,
``H I 2p``) carry no marker.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from spectral_database.identifiers import normalize_configuration, normalize_term

if TYPE_CHECKING:
    from collections.abc import Sequence

    from spectral_database.data_models import LineRecord

EXCITATION_MARKER = "*"

_SpeciesKey = tuple[str, int]
_TermKey = tuple[str, str]


@dataclass(frozen=True)
class LowerLevel:
    """Lower level of a transition, reduced to what the marker rule needs."""

    element_symbol: str
    charge_state: int
    energy_ev: float | None
    configuration: str | None
    term: str | None

    @property
    def species_key(self) -> _SpeciesKey:
        """Return the grouping key that scopes a ground term."""
        return (self.element_symbol, self.charge_state)

    @property
    def term_key(self) -> _TermKey | None:
        """Return the normalized term key, or ``None`` when level data is missing."""
        conf = normalize_configuration(self.configuration)
        term = normalize_term(self.term)
        if conf is None or term is None:
            return None
        return (conf, term)


def excitation_markers(levels: Sequence[LowerLevel]) -> list[str]:
    """Return the marker for each level, aligned with the input order.

    Args:
        levels: Lower levels of the transitions to label.

    Returns:
        Marker strings (``""``, ``"*"``, ``"**"``, ...) in input order.
    """
    ranks = _ground_term_ranks(levels)
    markers: list[str] = []
    for level in levels:
        if level.energy_ev is None:
            markers.append("")
            continue
        rank = ranks.get(level.species_key, {}).get(level.energy_ev)
        markers.append(EXCITATION_MARKER * rank if rank else "")
    return markers


def annotate_excitation_labels(records: list[LineRecord]) -> None:
    """Append excitation markers to ``name`` and ``mutiplet_name`` in place.

    Every component of a multiplet shares one lower level, so a multiplet label
    takes the same marker as its components.

    Args:
        records: Records to label, already carrying multiplet names.
    """
    levels = [
        LowerLevel(
            element_symbol=record.element_symbol,
            charge_state=record.charge_state,
            energy_ev=record.lower_level_energy,
            configuration=record.lower_level_conf,
            term=record.lower_level_term,
        )
        for record in records
    ]
    for record, marker in zip(records, excitation_markers(levels), strict=True):
        if not marker:
            continue
        record.name = f"{record.name}{marker}"
        if record.mutiplet_name:
            record.mutiplet_name = f"{record.mutiplet_name}{marker}"


def _ground_term_ranks(levels: Sequence[LowerLevel]) -> dict[_SpeciesKey, dict[float, int]]:
    by_species: dict[_SpeciesKey, set[tuple[float, _TermKey]]] = defaultdict(set)
    for level in levels:
        term_key = level.term_key
        if level.energy_ev is None or term_key is None:
            continue
        by_species[level.species_key].add((level.energy_ev, term_key))

    ranks: dict[_SpeciesKey, dict[float, int]] = {}
    for species_key, entries in by_species.items():
        ordered = sorted(entries)
        ground_term = ordered[0][1]
        ground_energies = [energy for energy, term_key in ordered if term_key == ground_term]
        ranks[species_key] = {energy: rank for rank, energy in enumerate(ground_energies)}
    return ranks
