"""Command-line interface for spectral database generation.

This module implements the argparse-based CLI matching the interface
of the original fetch_nist_lines.py script.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
from typing import TYPE_CHECKING

from spectral_database.csv_writer import write_csv
from spectral_database.data_models import FilterOptions
from spectral_database.excitation import annotate_excitation_labels
from spectral_database.filters import collect_level_decay_totals, to_records
from spectral_database.hydrogen import synthesize_hydrogen_series
from spectral_database.multiplet import process_multiplets
from spectral_database.nist_client import fetch_tables_resilient, safe_meta_get
from spectral_database.species import (
    build_filter_set_for_presets,
    build_species_list,
    load_species_from_file,
    load_species_presets,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from spectral_database.data_models import LineRecord


# Default wavelength span used when aggregating level decay rates for gamma.
_GAMMA_FULL_RANGE_MIN_A = 0.1
_GAMMA_FULL_RANGE_MAX_A = 1_000_000.0


logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (None uses sys.argv)

    Returns:
        Exit code (0 for success)
    """
    species_presets_dict = load_species_presets()

    p = argparse.ArgumentParser(description="Fetch NIST spectral lines to CSV")
    p.add_argument("-o", "--output", default="nist_lines.csv", help="Output CSV path")
    p.add_argument("--min", dest="min_ang", type=float, default=100.0, help="Min wavelength [Å]")
    p.add_argument("--max", dest="max_ang", type=float, default=25000.0, help="Max wavelength [Å]")
    p.add_argument(
        "--element",
        action="append",
        default=[],
        help="Element symbol, repeatable (e.g., --element Fe --element Mg)",
    )
    p.add_argument(
        "--charge",
        type=int,
        action="append",
        default=[],
        help="Charge state (0=I, 1=II, ...). Repeatable; pairs with --element.",
    )
    p.add_argument(
        "--species",
        action="append",
        default=[],
        help='Direct NIST "Spectra" strings (e.g., "Fe II", "Mg I-III"). Repeatable.',
    )
    if species_presets_dict:
        p.add_argument(
            "--species-preset",
            dest="species_presets",
            action="append",
            choices=sorted(species_presets_dict.keys()),
            default=[],
            help=(
                "Shortcut list of spectra (e.g., qso_absorbers). "
                "Combine with --species to add more lines."
            ),
        )
    p.add_argument(
        "--species-file",
        dest="species_files",
        action="append",
        default=[],
        help=(
            "Load species from CSV/TXT file (default column 'species'). "
            "Repeatable; entries normalize to NIST spectra names."
        ),
    )
    p.add_argument(
        "--species-column",
        dest="species_column",
        default="species",
        help="Column name to read when using --species-file (default: species)",
    )
    # Science filters (E1 transitions only)
    p.add_argument(
        "--max-ei",
        type=float,
        default=None,
        help="Maximum lower-level energy Ei in eV (e.g., 0.5 for near-ground levels)",
    )
    p.add_argument(
        "--min-f", type=float, default=None, help="Minimum oscillator strength f (e.g., 1e-3)"
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel NIST requests (1 keeps sequential behavior)",
    )
    p.add_argument(
        "--gamma-full-range-min",
        type=float,
        default=_GAMMA_FULL_RANGE_MIN_A,
        help="Minimum wavelength [Å] for full-range gamma aggregation queries",
    )
    p.add_argument(
        "--gamma-full-range-max",
        type=float,
        default=_GAMMA_FULL_RANGE_MAX_A,
        help="Maximum wavelength [Å] for full-range gamma aggregation queries",
    )
    p.add_argument(
        "--no-gamma-full-range",
        action="store_true",
        help="Disable additional full-range queries used for gamma aggregation",
    )
    p.add_argument(
        "--meta-name",
        default="NIST ASD Lines",
        help="# name: metadata line to write (set empty to skip)",
    )
    p.add_argument(
        "--meta-version",
        default="1.0.0",
        help="# version: metadata line to write (set empty to skip)",
    )
    p.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")
    p.add_argument(
        "--include-absorption-multiplet-id",
        action="store_true",
        help="Include debug absorption_multiplet_id column in CSV output",
    )
    p.add_argument(
        "--include-gi-gk",
        action="store_true",
        help="Include degeneracy gi_gk column in CSV output (debug)",
    )
    p.add_argument(
        "--include-gamma-components",
        action="store_true",
        help="Include gamma_upper/gamma_lower diagnostic columns in CSV output",
    )
    p.add_argument(
        "--include-aki", action="store_true", help="Include raw Einstein Aki values in CSV output"
    )

    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG
        if args.verbose >= 2
        else (logging.INFO if args.verbose else logging.WARNING),
        format="%(levelname)s: %(message)s",
    )

    file_species: list[str] = []
    for path in getattr(args, "species_files", []) or []:
        loaded = load_species_from_file(path, args.species_column)
        if loaded:
            logger.info("Loaded %d species from %s", len(loaded), path)
            file_species.extend(loaded)

    species_list = build_species_list(
        args.element,
        args.charge,
        args.species,
        getattr(args, "species_presets", None),
        file_species,
        species_presets_dict,
    )
    logger.info("Query species: %s", "; ".join(species_list))

    preset_filter_set = build_filter_set_for_presets(
        getattr(args, "species_presets", None), species_presets_dict
    )
    has_preset_filters = bool(preset_filter_set.defaults or preset_filter_set.profiles)

    species_order_map: dict[str, int] | None = None
    if species_list:
        species_order_map = {}
        for idx, item in enumerate(species_list):
            normalized = item.lower()
            if normalized not in species_order_map:
                species_order_map[normalized] = idx
            element = normalized.split()[0]
            if element and element not in species_order_map:
                species_order_map[element] = idx

    # Build filter options (E1 transitions only)
    fopts = FilterOptions()
    fopts.allowed_types = {"E1"}
    fopts.assume_e1_when_missing = True  # Treat missing Type as E1 if f-value exists
    fopts.strict_ei = False

    if args.max_ei is not None:
        fopts.max_ei_ev = float(args.max_ei)
    if args.min_f is not None:
        fopts.min_f = float(args.min_f)

    try:
        tables = fetch_tables_resilient(
            species_list, args.min_ang, args.max_ang, max_workers=max(1, int(args.workers))
        )
    except Exception:
        logger.exception("astroquery request failed while fetching transition tables")
        tables = []

    if not tables:
        logger.error("No results returned from NIST for the given parameters.")
        return 2

    gamma_tables: list
    if args.no_gamma_full_range:
        gamma_tables = list(tables)
    else:
        try:
            gamma_tables = fetch_tables_resilient(
                species_list,
                args.gamma_full_range_min,
                args.gamma_full_range_max,
                max_workers=max(1, int(args.workers)),
            )
        except Exception:
            logger.exception("Full-range gamma query failed during resilient fetch")
            gamma_tables = []
        if not gamma_tables:
            logger.warning("Falling back to limited-range tables for gamma aggregation")
            gamma_tables = list(tables)

    level_decay_totals = collect_level_decay_totals(gamma_tables)
    gamma_tables.clear()

    unique: dict[str, LineRecord] = {}
    for idx, t in enumerate(tables):
        if args.verbose and idx == 0:
            with contextlib.suppress(Exception):
                logger.info("First table columns: %s", ", ".join(map(str, t.colnames)))
        species_meta = str(safe_meta_get(t, "species", "") or "")
        effective_filters = (
            preset_filter_set.resolve(fopts, species_meta) if has_preset_filters else fopts
        )
        recs = to_records(t, filters=effective_filters, level_totals=level_decay_totals)
        for r in recs:
            unique[r.line_id] = r
    records = list(unique.values())
    synthesized_series = synthesize_hydrogen_series(records)
    if synthesized_series:
        existing_ids = {record.line_id for record in records}
        for series_record in synthesized_series:
            if series_record.line_id in existing_ids:
                continue
            records.append(series_record)
            existing_ids.add(series_record.line_id)
    if not records:
        logger.error("No valid lines with f_value and wavelength found.")
        return 3

    # Process multiplets using new spec.md algorithm
    multiplet_metrics = process_multiplets(records)

    annotate_excitation_labels(records)

    # Sort by absorption_multiplet_id, then wavelength (spec.md §5.6)
    records.sort(key=lambda r: (r.absorption_multiplet_id or "", r.wavelength))

    write_csv(
        args.output,
        records,
        args.meta_name or None,
        args.meta_version or None,
        include_absorption_multiplet_id=args.include_absorption_multiplet_id,
        include_gi_gk=args.include_gi_gk,
        include_gamma_components=args.include_gamma_components,
        include_aki=args.include_aki,
        multiplet_metrics=multiplet_metrics,
        species_order=species_order_map,
    )
    logger.info("Wrote %d lines to %s", len(records), args.output)
    return 0
