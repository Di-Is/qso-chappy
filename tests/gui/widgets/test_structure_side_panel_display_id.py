"""Tests for StructureSidePanel display ID feature."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel


if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@pytest.fixture
def panel(qtbot: "QtBot") -> StructureSidePanel:
    """Create StructureSidePanel instance."""
    return StructureSidePanel()


def _make_line(
    line_id: str,
    *,
    center_z: float = 1.0,
    rest_wavelength: float = 1215.67,
    species: str = "H I",
    region_id: str | None = None,
) -> AbsorptionLine:
    """Create a minimal AbsorptionLine for testing."""
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=150.0,
        region_id=region_id,
        multiplet_label="",
        transition_name=f"{species} {rest_wavelength:.1f}",
        oscillator_strength=0.1,
        gamma_value=1e8,
    )


def _make_region(region_id: str, line_ids: list[str]) -> AbsorptionRegion:
    """Create a minimal AbsorptionRegion for testing."""
    return AbsorptionRegion(region_id=region_id, line_ids=line_ids)


class TestLinkedLineNodeDisplayId:
    """Tests for display ID in _LinkedLineNode."""

    def test_linked_line_node_has_display_id_field(self) -> None:
        """_LinkedLineNode should have a display_id field."""
        # Import inside test to check existence
        from chappy.gui.modes.analysis.overview.panel import _LinkedLineNode

        assert hasattr(_LinkedLineNode, "__dataclass_fields__")
        fields = _LinkedLineNode.__dataclass_fields__
        assert "display_id" in fields, "_LinkedLineNode should have 'display_id' field"

    def test_display_id_default_is_none(self) -> None:
        """display_id should default to None."""
        from chappy.gui.modes.analysis.overview.panel import _LinkedLineNode

        node = _LinkedLineNode(
            line_ids=("test",),
            header_label="Test Label",
            lambda_range=None,
            needs_optimization=False,
        )
        assert node.display_id is None


class TestLineDisplayOrder:
    """Tests for line display order in StructureSidePanel."""

    def test_lines_sorted_by_center_z(self, panel: StructureSidePanel) -> None:
        """Lines should be sorted by center_z ascending."""
        # Setup: Create project with lines in reverse z order
        project = SpectroscopyProject()

        line_high_z = _make_line("line_high", center_z=2.5, region_id="region_1")
        line_low_z = _make_line("line_low", center_z=1.0, region_id="region_1")
        line_mid_z = _make_line("line_mid", center_z=1.8, region_id="region_1")

        region = _make_region("region_1", ["line_high", "line_low", "line_mid"])

        project.absorption_lines["line_high"] = line_high_z
        project.absorption_lines["line_low"] = line_low_z
        project.absorption_lines["line_mid"] = line_mid_z
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        # Verify: Lines in tree are in z-ascending order
        # Find the region group item
        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)  # Qt.ItemDataRole.UserRole
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None, "Group item not found"
        assert group_item.childCount() == 3

        # First child should be line_low (z=1.0) with display ID "1"
        child_0 = group_item.child(0)
        assert child_0 is not None
        text_0 = child_0.text(0)
        assert text_0.startswith("1."), f"First line should start with '1.': {text_0}"

        # Second child should be line_mid (z=1.8) with display ID "2"
        child_1 = group_item.child(1)
        assert child_1 is not None
        text_1 = child_1.text(0)
        assert text_1.startswith("2."), f"Second line should start with '2.': {text_1}"

        # Third child should be line_high (z=2.5) with display ID "3"
        child_2 = group_item.child(2)
        assert child_2 is not None
        text_2 = child_2.text(0)
        assert text_2.startswith("3."), f"Third line should start with '3.': {text_2}"

    def test_lines_sorted_by_wavelength_on_same_z(self, panel: StructureSidePanel) -> None:
        """Lines with same z should be sorted by rest_wavelength."""
        project = SpectroscopyProject()

        # Uses exact wavelengths from spectral_lines.csv
        line_long_wl = _make_line(
            "line_long",
            center_z=1.5,
            rest_wavelength=2796.352,
            species="Mg II",
            region_id="region_1",
        )
        line_short_wl = _make_line(
            "line_short",
            center_z=1.5,
            rest_wavelength=1215.668237,
            species="H I",
            region_id="region_1",
        )

        region = _make_region("region_1", ["line_long", "line_short"])

        project.absorption_lines["line_long"] = line_long_wl
        project.absorption_lines["line_short"] = line_short_wl
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        # Find the region group item
        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        assert group_item.childCount() == 2

        # First should be shorter wavelength with ID "1"
        child_0 = group_item.child(0)
        text_0 = child_0.text(0)
        assert text_0.startswith("1."), f"Shorter wavelength line should be first: {text_0}"

        # Second should be longer wavelength with ID "2"
        child_1 = group_item.child(1)
        text_1 = child_1.text(0)
        assert text_1.startswith("2."), f"Longer wavelength line should be second: {text_1}"

    def test_display_id_format_in_header(self, panel: StructureSidePanel) -> None:
        """Display ID should appear as 'N. [header]' format."""
        project = SpectroscopyProject()

        line = _make_line("line_1", center_z=1.5, region_id="region_1")
        region = _make_region("region_1", ["line_1"])

        project.absorption_lines[line.line_id] = line
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        # Find the line item
        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        assert group_item.childCount() == 1

        child = group_item.child(0)
        text = child.text(0)
        # Format should be "N. [species wavelength @ range Å (z:redshift, ±window km/s)]"
        assert text.startswith("1. "), f"Header should start with '1. ': {text}"
