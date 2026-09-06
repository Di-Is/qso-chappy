"""Tests for identify coordinator line count calculation (ADR: identify-panel-line-count-unification).

These tests verify that:
1. old_member_count uses group_lines_by_multiplet() for multiplet-consolidated count
2. new_lines_count uses temporary_line_id_to_row lookup for multiplet-consolidated count
3. member_count = old_member_count + new_lines_count (both consolidated)
"""

from __future__ import annotations

import pytest

from chappy.core.absorption.models import AbsorptionLine
from chappy.core.absorption_display import group_lines_by_multiplet
from chappy.gui.modes.identify.panel.panel_models import TemporaryLineRow


class TestGroupLinesByMultiplet:
    """Tests for group_lines_by_multiplet function used in old_member_count calculation."""

    def test_single_line_returns_one_group(self) -> None:
        """Single line should return one group."""
        line = AbsorptionLine(
            line_id="line1",
            species="H I",
            rest_wavelength=1215.67,
            center_z=1.0,
            window_kms=150.0,
            lambda_range=(2430.0, 2440.0),
            multiplet_ids=[],
            multiplet_label="",
            transition_name="H I 1215.7",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        groups = group_lines_by_multiplet([line])
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_doublet_with_mutual_references_returns_one_group(self) -> None:
        """Doublet with mutual multiplet_ids should return one group."""
        line1 = AbsorptionLine(
            line_id="mg2_2796",
            species="Mg II",
            rest_wavelength=2796.35,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(6990.0, 7000.0),
            multiplet_ids=["mg2_2803"],
            multiplet_label="",
            transition_name="Mg II 2796.4",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        line2 = AbsorptionLine(
            line_id="mg2_2803",
            species="Mg II",
            rest_wavelength=2803.53,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(7005.0, 7015.0),
            multiplet_ids=["mg2_2796"],
            multiplet_label="",
            transition_name="Mg II 2803.5",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        groups = group_lines_by_multiplet([line1, line2])
        assert len(groups) == 1, "Doublet should be grouped into one"
        assert len(groups[0]) == 2, "Group should contain both lines"

    def test_two_doublets_returns_two_groups(self) -> None:
        """Two separate doublets should return two groups."""
        # MgII doublet
        mg_line1 = AbsorptionLine(
            line_id="mg2_2796",
            species="Mg II",
            rest_wavelength=2796.35,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(6990.0, 7000.0),
            multiplet_ids=["mg2_2803"],
            multiplet_label="",
            transition_name="Mg II 2796.4",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        mg_line2 = AbsorptionLine(
            line_id="mg2_2803",
            species="Mg II",
            rest_wavelength=2803.53,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(7005.0, 7015.0),
            multiplet_ids=["mg2_2796"],
            multiplet_label="",
            transition_name="Mg II 2803.5",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        # CIV doublet
        civ_line1 = AbsorptionLine(
            line_id="civ_1548",
            species="C IV",
            rest_wavelength=1548.20,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(3870.0, 3880.0),
            multiplet_ids=["civ_1551"],
            multiplet_label="",
            transition_name="C IV 1548.2",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        civ_line2 = AbsorptionLine(
            line_id="civ_1551",
            species="C IV",
            rest_wavelength=1550.78,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(3876.0, 3886.0),
            multiplet_ids=["civ_1548"],
            multiplet_label="",
            transition_name="C IV 1550.8",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        groups = group_lines_by_multiplet([mg_line1, mg_line2, civ_line1, civ_line2])
        assert len(groups) == 2, "Two doublets should form two groups"

    def test_mixed_multiplet_and_single_lines(self) -> None:
        """Mix of multiplet and single lines should be grouped correctly."""
        # Single line
        single = AbsorptionLine(
            line_id="h1_1216",
            species="H I",
            rest_wavelength=1215.67,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(3039.0, 3049.0),
            multiplet_ids=[],
            multiplet_label="",
            transition_name="H I 1215.7",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        # Doublet
        doublet1 = AbsorptionLine(
            line_id="mg2_2796",
            species="Mg II",
            rest_wavelength=2796.35,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(6990.0, 7000.0),
            multiplet_ids=["mg2_2803"],
            multiplet_label="",
            transition_name="Mg II 2796.4",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        doublet2 = AbsorptionLine(
            line_id="mg2_2803",
            species="Mg II",
            rest_wavelength=2803.53,
            center_z=1.5,
            window_kms=150.0,
            lambda_range=(7005.0, 7015.0),
            multiplet_ids=["mg2_2796"],
            multiplet_label="",
            transition_name="Mg II 2803.5",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )
        groups = group_lines_by_multiplet([single, doublet1, doublet2])
        assert len(groups) == 2, "Should have 2 groups: 1 single + 1 doublet"


class TestLineIdToRowLookup:
    """Tests for temporary_line_id_to_row lookup used in new_lines_count calculation."""

    def test_lookup_finds_row_by_primary_id(self) -> None:
        """Lookup should find TemporaryLineRow by primary temporary_line_id."""
        row = TemporaryLineRow(
            temporary_line_ids=("primary_id", "secondary_id"),
            species="Mg II",
            lambda_start=6990.0,
            lambda_end=7015.0,
            creation_method="manual",
            transition_name="Mg II 2796.4",
        )
        rows = [row]

        # Build lookup
        temporary_line_id_to_row: dict[str, TemporaryLineRow] = {}
        for r in rows:
            for sid in r.temporary_line_ids:
                temporary_line_id_to_row[sid] = r

        assert temporary_line_id_to_row.get("primary_id") is row
        assert temporary_line_id_to_row.get("secondary_id") is row

    def test_unique_row_count_for_multiplet(self) -> None:
        """Multiple IDs from same row should count as 1 unique row."""
        row = TemporaryLineRow(
            temporary_line_ids=("mg2_2796", "mg2_2803"),
            species="Mg II",
            lambda_start=6990.0,
            lambda_end=7015.0,
            creation_method="manual",
            transition_name="Mg II 2796.4",
        )
        rows = [row]

        # Build lookup
        temporary_line_id_to_row: dict[str, TemporaryLineRow] = {}
        for r in rows:
            for sid in r.temporary_line_ids:
                temporary_line_id_to_row[sid] = r

        # Simulate counting unique rows for preview
        member_temporary_line_ids = ["mg2_2796", "mg2_2803"]  # Both IDs
        unique_rows: set[int] = set()
        for sid in member_temporary_line_ids:
            matched_row = temporary_line_id_to_row.get(sid)
            if matched_row is not None:
                unique_rows.add(id(matched_row))

        assert len(unique_rows) == 1, "Doublet should count as 1 unique row"

    def test_two_separate_rows_count_as_two(self) -> None:
        """Two separate rows should count as 2."""
        row1 = TemporaryLineRow(
            temporary_line_ids=("mg2_2796", "mg2_2803"),
            species="Mg II",
            lambda_start=6990.0,
            lambda_end=7015.0,
            creation_method="manual",
            transition_name="Mg II 2796.4",
        )
        row2 = TemporaryLineRow(
            temporary_line_ids=("civ_1548", "civ_1551"),
            species="C IV",
            lambda_start=3870.0,
            lambda_end=3886.0,
            creation_method="manual",
            transition_name="C IV 1548.2",
        )
        rows = [row1, row2]

        # Build lookup
        temporary_line_id_to_row: dict[str, TemporaryLineRow] = {}
        for r in rows:
            for sid in r.temporary_line_ids:
                temporary_line_id_to_row[sid] = r

        # Simulate counting unique rows for preview
        member_temporary_line_ids = ["mg2_2796", "mg2_2803", "civ_1548", "civ_1551"]
        unique_rows: set[int] = set()
        for sid in member_temporary_line_ids:
            matched_row = temporary_line_id_to_row.get(sid)
            if matched_row is not None:
                unique_rows.add(id(matched_row))

        assert len(unique_rows) == 2, "Two doublets should count as 2 unique rows"


class TestMemberCountCalculation:
    """Tests for member_count = old_member_count + new_lines_count."""

    def test_member_count_with_no_existing_group(self) -> None:
        """New group should have member_count = new_lines_count."""
        # Simulate new group with 1 doublet
        old_member_count = None
        new_lines_count = 1  # 1 doublet (consolidated)

        member_count = new_lines_count + (old_member_count or 0)
        assert member_count == 1

    def test_member_count_with_existing_group(self) -> None:
        """Existing group should have member_count = old + new (both consolidated)."""
        # Existing group has 2 lines (1 doublet consolidated)
        old_member_count = 1  # 1 doublet (consolidated)
        # Adding 1 new doublet (consolidated)
        new_lines_count = 1

        member_count = new_lines_count + (old_member_count or 0)
        assert member_count == 2

    def test_member_count_matches_confirmed_display(self) -> None:
        """Preview member_count should match what will be displayed after confirmation.

        Scenario:
        - Existing region has 4 lines: MgII doublet + CIV doublet
        - After multiplet consolidation: 2 groups
        - Adding 1 new doublet: OVI 1032/1038
        - Expected: old=2, new=1, total=3
        """
        # Simulate existing region lines
        existing_lines = [
            AbsorptionLine(
                line_id="mg2_2796",
                species="Mg II",
                rest_wavelength=2796.35,
                center_z=1.5,
                window_kms=150.0,
                lambda_range=(6990.0, 7000.0),
                multiplet_ids=["mg2_2803"],
                multiplet_label="",
                transition_name="Mg II 2796.4",
                oscillator_strength=0.1,
                gamma_value=1e8,
            ),
            AbsorptionLine(
                line_id="mg2_2803",
                species="Mg II",
                rest_wavelength=2803.53,
                center_z=1.5,
                window_kms=150.0,
                lambda_range=(7005.0, 7015.0),
                multiplet_ids=["mg2_2796"],
                multiplet_label="",
                transition_name="Mg II 2803.5",
                oscillator_strength=0.1,
                gamma_value=1e8,
            ),
            AbsorptionLine(
                line_id="civ_1548",
                species="C IV",
                rest_wavelength=1548.20,
                center_z=1.5,
                window_kms=150.0,
                lambda_range=(3870.0, 3880.0),
                multiplet_ids=["civ_1551"],
                multiplet_label="",
                transition_name="C IV 1548.2",
                oscillator_strength=0.1,
                gamma_value=1e8,
            ),
            AbsorptionLine(
                line_id="civ_1551",
                species="C IV",
                rest_wavelength=1550.78,
                center_z=1.5,
                window_kms=150.0,
                lambda_range=(3876.0, 3886.0),
                multiplet_ids=["civ_1548"],
                multiplet_label="",
                transition_name="C IV 1550.8",
                oscillator_strength=0.1,
                gamma_value=1e8,
            ),
        ]

        # Calculate old_member_count using group_lines_by_multiplet
        existing_groups = group_lines_by_multiplet(existing_lines)
        old_member_count = len(existing_groups)
        assert old_member_count == 2, "4 lines forming 2 doublets = 2 groups"

        # Simulate new row (OVI doublet, already consolidated)
        new_row = TemporaryLineRow(
            temporary_line_ids=("ovi_1032", "ovi_1038"),
            species="O VI",
            lambda_start=2580.0,
            lambda_end=2600.0,
            creation_method="manual",
            transition_name="O VI 1031.9",
        )
        rows = [new_row]

        # Build lookup
        temporary_line_id_to_row: dict[str, TemporaryLineRow] = {}
        for r in rows:
            for sid in r.temporary_line_ids:
                temporary_line_id_to_row[sid] = r

        # Calculate new_lines_count
        member_temporary_line_ids = ["ovi_1032", "ovi_1038"]
        unique_rows: set[int] = set()
        for sid in member_temporary_line_ids:
            matched_row = temporary_line_id_to_row.get(sid)
            if matched_row is not None:
                unique_rows.add(id(matched_row))
        new_lines_count = len(unique_rows)
        assert new_lines_count == 1, "1 doublet = 1 group"

        # Calculate member_count
        member_count = new_lines_count + (old_member_count or 0)
        assert member_count == 3, "2 existing + 1 new = 3 total"
