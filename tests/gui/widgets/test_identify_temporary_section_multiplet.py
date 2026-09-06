"""Tests for IdentifyTemporarySection multiplet consolidation display.

TDD Red phase: These tests should fail until the multiplet consolidation
display is implemented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import Qt

from chappy.gui.modes.identify.panel.panel_models import (
    TemporaryLineRow,
    RegionPreviewRow,
    TemporaryLineItemPayload,
)
from chappy.gui.modes.identify.panel.temporary_section import IdentifyTemporarySection


if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@pytest.fixture
def section(qtbot: "QtBot") -> IdentifyTemporarySection:
    """Create IdentifyTemporarySection instance for testing."""
    return IdentifyTemporarySection()


def _make_temporary_line_row(
    temporary_line_ids: tuple[str, ...],
    species: str = "H I",
    lambda_start: float = 5000.0,
    lambda_end: float = 5010.0,
    creation_method: str = "manual",
    transition_name: str | None = None,
    redshift: float | None = None,
) -> TemporaryLineRow:
    """Create a TemporaryLineRow for testing."""
    return TemporaryLineRow(
        temporary_line_ids=temporary_line_ids,
        species=species,
        lambda_start=lambda_start,
        lambda_end=lambda_end,
        creation_method=creation_method,
        transition_name=transition_name or species,
        redshift=redshift if redshift is not None else 1.0,
    )


class TestTemporaryLineRowDataStructure:
    """Tests for TemporaryLineRow data structure changes."""

    def test_temporary_line_row_has_temporary_line_ids_tuple(self) -> None:
        """TemporaryLineRow should have temporary_line_ids as tuple[str, ...]."""
        row = _make_temporary_line_row(temporary_line_ids=("id1", "id2"), species="Mg II")

        assert isinstance(row.temporary_line_ids, tuple)
        assert row.temporary_line_ids == ("id1", "id2")

    def test_single_line_has_single_element_tuple(self) -> None:
        """Single line should have a single-element tuple."""
        row = _make_temporary_line_row(temporary_line_ids=("single_id",), species="H I")

        assert len(row.temporary_line_ids) == 1
        assert row.temporary_line_ids[0] == "single_id"

    def test_primary_id_is_first_element(self) -> None:
        """Primary ID (for operations) should be the first element."""
        row = _make_temporary_line_row(
            temporary_line_ids=("primary", "secondary", "third"), species="Mg II"
        )

        # Convention: first element is the primary ID
        primary_id = row.temporary_line_ids[0]
        assert primary_id == "primary"


class TestTemporaryLineDisplay:
    """Tests for temporary line display in temporary section."""

    def test_single_temporary_displayed_normally(self, section: IdentifyTemporarySection) -> None:
        """Single line should be displayed normally."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("line1",),
                species="H I",
                lambda_start=1215.0,
                lambda_end=1220.0,
                transition_name="H I 1216",
            )
        ]

        section.set_temporary_lines(rows)

        # Verify tree has 1 item
        tree = section._temporary_tree
        assert tree.topLevelItemCount() == 1

    def test_multiplet_displayed_as_single_row(self, section: IdentifyTemporarySection) -> None:
        """Multiplet (multiple IDs) should be displayed as a single row."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("mg2_2796", "mg2_2803"),
                species="Mg II",
                lambda_start=6990.0,
                lambda_end=7015.0,
                transition_name="Mg II 2796/2803",
            )
        ]

        section.set_temporary_lines(rows)

        # Should still be 1 item (multiplet is pre-grouped)
        tree = section._temporary_tree
        assert tree.topLevelItemCount() == 1

    def test_user_data_contains_primary_id(self, section: IdentifyTemporarySection) -> None:
        """UserRole data should contain primary ID (first element) for operations."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("primary_id", "secondary_id"), species="Mg II"
            )
        ]

        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        from PySide6.QtCore import Qt

        payload = item.data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(payload, TemporaryLineItemPayload)
        assert payload.primary_temporary_line_id == "primary_id"


class TestMultipletDisplayIntegration:
    """Tests for multiplet display integration with coordinator."""

    def test_multiplet_display_name_shows_combined_wavelengths(
        self, section: IdentifyTemporarySection
    ) -> None:
        """Multiplet should show combined wavelengths like 'Mg II 2796/2803'."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("mg2_2796", "mg2_2803"),
                species="Mg II",
                lambda_start=6990.0,
                lambda_end=7015.0,
                transition_name="Mg II 2796/2803",  # Combined name
            )
        ]

        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        # Display text should contain the combined transition name
        display_text = item.text(0)
        assert "Mg II" in display_text

    def test_tooltip_shows_member_count_for_multiplet(
        self, section: IdentifyTemporarySection
    ) -> None:
        """Multiplet row should show tooltip with member count (Risk-15)."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("id1", "id2", "id3"),
                species="Test Species",
                transition_name="Test Triplet",
            )
        ]

        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        # Tooltip should indicate this is a multiplet with 3 members
        tooltip = item.toolTip(0)
        # Risk-15 decides on simple info: "3 lines grouped" or similar
        # For multiplets (temporary_line_ids > 1), tooltip must contain member count
        if len(rows[0].temporary_line_ids) > 1:
            assert "3" in tooltip, f"Tooltip should contain '3' for triplet, got: {tooltip}"

    def test_single_line_has_no_multiplet_tooltip(self, section: IdentifyTemporarySection) -> None:
        """Single line should not have multiplet-related tooltip."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("single_id",), species="H I", transition_name="H I 1216"
            )
        ]

        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        # Single line tooltip should be empty or not mention "grouped"
        tooltip = item.toolTip(0)
        assert "grouped" not in tooltip.lower()


class TestSelectionStateRestoration:
    """Tests for selection state restoration after refresh (Risk-14)."""

    def test_selection_restored_after_refresh(self, section: IdentifyTemporarySection) -> None:
        """Selection should be restored after set_temporary_lines refresh."""
        from PySide6.QtCore import Qt

        # Initial rows - use different redshifts to control sort order
        initial_rows = [
            _make_temporary_line_row(
                temporary_line_ids=("id1",),
                species="H I",
                lambda_start=1215.0,
                lambda_end=1220.0,
                redshift=1.0,
            ),
            _make_temporary_line_row(
                temporary_line_ids=("id2",),
                species="C IV",
                lambda_start=1548.0,
                lambda_end=1555.0,
                redshift=2.0,
            ),
        ]

        section.set_temporary_lines(initial_rows)

        # Select the second item (id2)
        tree = section._temporary_tree
        item1 = tree.topLevelItem(1)
        assert item1 is not None
        item1.setSelected(True)

        # Verify selection before refresh
        selected = tree.selectedItems()
        assert len(selected) > 0
        selected_payload = selected[0].data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(selected_payload, TemporaryLineItemPayload)
        assert selected_payload.primary_temporary_line_id == "id2"

        # Refresh with same data (simulating coordinator refresh)
        section.set_temporary_lines(initial_rows)

        # Selection MUST be restored (strict check)
        selected_after = tree.selectedItems()
        assert len(selected_after) > 0, "Selection was lost after refresh"

        restored_payload = selected_after[0].data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(restored_payload, TemporaryLineItemPayload)
        assert restored_payload.primary_temporary_line_id == "id2"

    def test_selection_cleared_when_item_removed(self, section: IdentifyTemporarySection) -> None:
        """Selection should be cleared if selected item is removed."""
        from PySide6.QtCore import Qt

        # Initial rows
        initial_rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.0),
            _make_temporary_line_row(temporary_line_ids=("id2",), species="C IV", redshift=2.0),
        ]

        section.set_temporary_lines(initial_rows)

        # Select the second item (id2)
        tree = section._temporary_tree
        item1 = tree.topLevelItem(1)
        assert item1 is not None
        item1.setSelected(True)

        # Refresh with id2 removed
        updated_rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.0)
        ]
        section.set_temporary_lines(updated_rows)

        # Tree should have 1 item
        assert tree.topLevelItemCount() == 1

        # Selection should be cleared (id2 no longer exists)
        # OR if there's a selected item, it should not be id2
        selected = tree.selectedItems()
        if selected:
            selected_payload = selected[0].data(0, Qt.ItemDataRole.UserRole)
            assert isinstance(selected_payload, TemporaryLineItemPayload)
            assert selected_payload.primary_temporary_line_id != "id2"


class TestGroupedBundlingDisplay:
    """Tests for the always-visible bundling result in the temporary tree."""

    def test_new_region_heading_groups_multiplet_children(
        self, section: IdentifyTemporarySection
    ) -> None:
        """A new-region preview renders a non-selectable heading with deduplicated children."""
        from PySide6.QtCore import Qt

        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("mg2_2796", "mg2_2803"),
                species="Mg II",
                lambda_start=6990.0,
                lambda_end=7015.0,
                transition_name="Mg II 2796/2803",
            )
        ]
        previews = [
            RegionPreviewRow(
                group_id="preview-1",
                label="Mg II @ 6990-7015Å",
                member_count=2,
                warning=False,
                is_existing_group=False,
                old_member_count=None,
                new_lines_count=1,
                member_temporary_line_ids=["mg2_2796", "mg2_2803"],
            )
        ]

        section.set_temporary_lines(rows, previews)

        tree = section._temporary_tree
        assert tree.topLevelItemCount() == 1
        heading = tree.topLevelItem(0)
        assert heading is not None
        assert heading.text(0).startswith("New region: Mg II")
        assert "(1)" in heading.text(0)
        assert not heading.flags() & Qt.ItemFlag.ItemIsSelectable
        assert heading.childCount() == 1
        child_text = heading.child(0).text(0)
        assert "Mg II" in child_text
        assert "unknown" not in child_text.lower()

    def test_existing_region_heading_shows_append_target_and_warning(
        self, section: IdentifyTemporarySection
    ) -> None:
        """Appending to an existing region shows the target name and overlap warning."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("line1",), species="C IV", transition_name="C IV 1548"
            )
        ]
        previews = [
            RegionPreviewRow(
                group_id="region-3",
                label="Region 3",
                member_count=2,
                warning=True,
                is_existing_group=True,
                old_member_count=1,
                new_lines_count=1,
                member_temporary_line_ids=["line1"],
            )
        ]

        section.set_temporary_lines(rows, previews)

        heading = section._temporary_tree.topLevelItem(0)
        assert heading is not None
        assert heading.text(0) == "→ Add to Region 3 (1) ⚠"
        assert "Overlaps multiple existing regions" in heading.toolTip(0)

    def test_selection_preserved_across_grouped_reevaluation(
        self, section: IdentifyTemporarySection
    ) -> None:
        """Child-row selection survives a re-evaluation of the bundling result."""
        from PySide6.QtCore import Qt

        rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.0),
            _make_temporary_line_row(temporary_line_ids=("id2",), species="C IV", redshift=2.0),
        ]
        previews = [
            RegionPreviewRow(
                group_id="preview-1",
                label="Preview",
                member_count=2,
                warning=False,
                is_existing_group=False,
                old_member_count=None,
                new_lines_count=2,
                member_temporary_line_ids=["id1", "id2"],
            )
        ]
        section.set_temporary_lines(rows, previews)

        heading = section._temporary_tree.topLevelItem(0)
        assert heading is not None
        heading.child(1).setSelected(True)

        section.set_temporary_lines(rows, previews)

        selected = section._temporary_tree.selectedItems()
        assert len(selected) == 1
        payload = selected[0].data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(payload, TemporaryLineItemPayload)
        assert payload.primary_temporary_line_id == "id2"

    def test_register_button_label_and_disabled_tooltip(
        self, section: IdentifyTemporarySection
    ) -> None:
        """Register labels distinguish all groups from selected groups."""
        section.set_temporary_lines([])
        assert not section._register_button.isEnabled()
        assert section._register_button.toolTip() != ""

        rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.0),
            _make_temporary_line_row(temporary_line_ids=("id2",), species="C IV", redshift=2.0),
        ]
        section.set_temporary_lines(rows)
        assert section._register_button.isEnabled()
        assert section._temporary_label.text() == "To register: 2 groups / 2 lines"
        assert section._register_button.text() == "Register all (2 groups)"
        assert section._register_button.toolTip() == ""

        item = section._temporary_tree.topLevelItem(0)
        assert item is not None
        item.setSelected(True)
        assert section._register_button.text() == "Register selected (1 group)"

    def test_heading_counts_groups_and_constituent_lines(
        self, section: IdentifyTemporarySection
    ) -> None:
        """A consolidated multiplet is one group with all member lines counted."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("doublet-a", "doublet-b"), species="C IV", redshift=1.0
            ),
            _make_temporary_line_row(temporary_line_ids=("single",), species="H I", redshift=2.0),
        ]

        section.set_temporary_lines(rows)

        assert section._temporary_label.text() == "To register: 2 groups / 3 lines"

    def test_overflow_clear_action_and_button_variants(
        self, section: IdentifyTemporarySection, qtbot: QtBot
    ) -> None:
        """Clear All is a low-emphasis menu action and registration is the sole primary."""
        section.set_temporary_lines(
            [_make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.0)]
        )

        assert section._delete_button.property("variant") == "secondary"
        assert section._more_button.property("variant") == "text"
        assert section._register_button.property("variant") == "primary"
        assert section._more_button.text() == "⋯"
        assert section._more_button.toolTip() == "More actions"
        assert section._more_button.accessibleName() == "More actions"
        assert section._more_button.focusPolicy() != Qt.FocusPolicy.NoFocus
        assert section._clear_action.text() == "Clear All"

        with qtbot.waitSignal(section.temporary_clear_requested, timeout=1000):
            section._clear_action.trigger()
