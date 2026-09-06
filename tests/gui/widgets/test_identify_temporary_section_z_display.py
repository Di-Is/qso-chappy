"""Tests for IdentifyTemporarySection z (redshift) display in tree format.

Updated for tree-based display format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from chappy.gui.modes.identify.panel.panel_models import TemporaryLineRow, TemporaryLineItemPayload
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
    redshift: float = 1.0,
) -> TemporaryLineRow:
    """Create a TemporaryLineRow for testing."""
    return TemporaryLineRow(
        temporary_line_ids=temporary_line_ids,
        species=species,
        lambda_start=lambda_start,
        lambda_end=lambda_end,
        creation_method=creation_method,
        transition_name=transition_name or species,
        redshift=redshift,
    )


class TestZDisplayInTreeFormat:
    """Tests for z value display in tree format."""

    def test_z_value_displayed_in_tree_item(self, section: IdentifyTemporarySection) -> None:
        """Z value should be displayed in tree item text."""
        rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.2345)
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        # Display text should contain z value
        display_text = item.text(0)
        assert "[z=1.2345]" in display_text

    def test_z_value_displayed_with_four_decimals(self, section: IdentifyTemporarySection) -> None:
        """Z value should be displayed with 4 decimal places."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("id1",),
                species="H I",
                redshift=1.23456789,  # More than 4 decimals
            )
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        # Should be formatted to 4 decimals: 1.2346 (rounded)
        display_text = item.text(0)
        assert "[z=1.2346]" in display_text

    def test_z_zero_displayed_correctly(self, section: IdentifyTemporarySection) -> None:
        """Z value of 0 should be displayed as 0.0000."""
        rows = [_make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=0.0)]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        display_text = item.text(0)
        assert "[z=0.0000]" in display_text

    def test_z_small_value_displayed_correctly(self, section: IdentifyTemporarySection) -> None:
        """Small z value should be displayed with 4 decimal places."""
        rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=0.0001)
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        display_text = item.text(0)
        assert "[z=0.0001]" in display_text

    def test_z_large_value_displayed_correctly(self, section: IdentifyTemporarySection) -> None:
        """Large z value should be displayed with 4 decimal places."""
        rows = [
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=5.1234)
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        display_text = item.text(0)
        assert "[z=5.1234]" in display_text


class TestZOrderSorting:
    """Tests for z-order sorting (default behavior)."""

    def test_items_sorted_by_z_ascending(self, section: IdentifyTemporarySection) -> None:
        """Items should be sorted by redshift ascending."""
        rows = [
            _make_temporary_line_row(temporary_line_ids=("id3",), species="C IV", redshift=3.0),
            _make_temporary_line_row(temporary_line_ids=("id1",), species="H I", redshift=1.0),
            _make_temporary_line_row(temporary_line_ids=("id2",), species="O VI", redshift=2.0),
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        assert tree.topLevelItemCount() == 3

        # Should be sorted by z: id1, id2, id3
        from PySide6.QtCore import Qt

        item0 = tree.topLevelItem(0)
        item1 = tree.topLevelItem(1)
        item2 = tree.topLevelItem(2)

        assert item0 is not None
        assert item1 is not None
        assert item2 is not None

        payload0 = item0.data(0, Qt.ItemDataRole.UserRole)
        payload1 = item1.data(0, Qt.ItemDataRole.UserRole)
        payload2 = item2.data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(payload0, TemporaryLineItemPayload)
        assert isinstance(payload1, TemporaryLineItemPayload)
        assert isinstance(payload2, TemporaryLineItemPayload)
        assert payload0.primary_temporary_line_id == "id1"
        assert payload1.primary_temporary_line_id == "id2"
        assert payload2.primary_temporary_line_id == "id3"


class TestMultipletTooltipInTree:
    """Tests for multiplet tooltip in tree format."""

    def test_multiplet_has_tooltip(self, section: IdentifyTemporarySection) -> None:
        """Multiplet row should have tooltip with member count."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("id1", "id2", "id3"),  # 3 members
                species="Mg II",
                redshift=1.5000,
            )
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        tooltip = item.toolTip(0)
        assert "3" in tooltip, f"Expected '3' in tooltip, got: {tooltip}"
        assert "grouped" in tooltip.lower(), f"Expected 'grouped' in tooltip, got: {tooltip}"

    def test_single_line_has_no_multiplet_tooltip(self, section: IdentifyTemporarySection) -> None:
        """Single line should not have multiplet tooltip."""
        rows = [
            _make_temporary_line_row(
                temporary_line_ids=("single_id",),  # Single member
                species="H I",
                redshift=1.0000,
            )
        ]
        section.set_temporary_lines(rows)

        tree = section._temporary_tree
        item = tree.topLevelItem(0)
        assert item is not None

        tooltip = item.toolTip(0)
        assert "grouped" not in tooltip.lower()
