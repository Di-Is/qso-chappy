"""Tests for StructureSidePanel multiplet consolidation feature."""

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
    transition_name: str | None = None,
    region_id: str | None = None,
    multiplet_ids: list[str] | None = None,
    multiplet_label: str | None = None,
) -> AbsorptionLine:
    """Create a minimal AbsorptionLine for testing."""
    # Default transition_name to "species rest_wavelength" if not provided
    if transition_name is None:
        transition_name = f"{species} {rest_wavelength:.1f}"
    # Default multiplet_label to transition_name (for single lines)
    if multiplet_label is None:
        multiplet_label = transition_name
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        transition_name=transition_name,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=150.0,
        region_id=region_id,
        multiplet_ids=multiplet_ids if multiplet_ids is not None else [],
        multiplet_label=multiplet_label,
        oscillator_strength=0.1,
        gamma_value=1e8,
    )


def _make_region(region_id: str, line_ids: list[str]) -> AbsorptionRegion:
    """Create a minimal AbsorptionRegion for testing."""
    return AbsorptionRegion(region_id=region_id, line_ids=line_ids)


class TestMultipletConsolidation:
    """Tests for multiplet consolidation in StructureSidePanel."""

    def test_doublet_displayed_as_single_row(self, panel: StructureSidePanel) -> None:
        """Two lines with multiplet cross-references should display as one row."""
        project = SpectroscopyProject()

        # MgII doublet: 2796/2803
        line1 = _make_line(
            "mg2_2796",
            center_z=1.5,
            rest_wavelength=2796.352,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2803"],
        )
        line2 = _make_line(
            "mg2_2803",
            center_z=1.5,
            rest_wavelength=2803.531,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2796"],
        )

        region = _make_region("region_1", ["mg2_2796", "mg2_2803"])

        project.absorption_lines["mg2_2796"] = line1
        project.absorption_lines["mg2_2803"] = line2
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

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
        # Multiplet should be consolidated into 1 row
        assert group_item.childCount() == 1, (
            f"Expected 1 consolidated row, got {group_item.childCount()}"
        )

    def test_doublet_display_id_is_single_number(self, panel: StructureSidePanel) -> None:
        """Multiplet row should have a single display ID."""
        project = SpectroscopyProject()

        line1 = _make_line(
            "mg2_2796",
            center_z=1.5,
            rest_wavelength=2796.352,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2803"],
        )
        line2 = _make_line(
            "mg2_2803",
            center_z=1.5,
            rest_wavelength=2803.531,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2796"],
        )

        region = _make_region("region_1", ["mg2_2796", "mg2_2803"])

        project.absorption_lines["mg2_2796"] = line1
        project.absorption_lines["mg2_2803"] = line2
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        child = group_item.child(0)
        text = child.text(0)
        # Should start with "1." for the single consolidated row
        assert text.startswith("1."), f"Consolidated row should start with '1.': {text}"

    def test_doublet_header_shows_combined_wavelengths(self, panel: StructureSidePanel) -> None:
        """Multiplet header should show combined wavelengths like 'MgII 2796/2803'."""
        project = SpectroscopyProject()

        line1 = _make_line(
            "mg2_2796",
            center_z=1.5,
            rest_wavelength=2796.352,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2803"],
            multiplet_label="Mg II 2796/2803",
        )
        line2 = _make_line(
            "mg2_2803",
            center_z=1.5,
            rest_wavelength=2803.531,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2796"],
            multiplet_label="Mg II 2796/2803",
        )

        region = _make_region("region_1", ["mg2_2796", "mg2_2803"])

        project.absorption_lines["mg2_2796"] = line1
        project.absorption_lines["mg2_2803"] = line2
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        child = group_item.child(0)
        text = child.text(0)
        # Header should contain both wavelengths separated by "/"
        # Wavelengths are displayed with 1 decimal place (2796.3/2803.5)
        assert "2796" in text and "2803" in text, f"Header should contain both wavelengths: {text}"
        assert "/" in text, f"Header should contain '/' separator: {text}"

    def test_triplet_displayed_as_single_row(self, panel: StructureSidePanel) -> None:
        """Three or more lines in a multiplet should display as one row."""
        project = SpectroscopyProject()

        # Simulated triplet using real H I wavelengths from spectral_lines.csv
        line1 = _make_line(
            "line_a",
            center_z=1.5,
            rest_wavelength=918.129305,
            species="H I",
            region_id="region_1",
            multiplet_ids=["line_b", "line_c"],
        )
        line2 = _make_line(
            "line_b",
            center_z=1.5,
            rest_wavelength=919.351342,
            species="H I",
            region_id="region_1",
            multiplet_ids=["line_a", "line_c"],
        )
        line3 = _make_line(
            "line_c",
            center_z=1.5,
            rest_wavelength=920.963014,
            species="H I",
            region_id="region_1",
            multiplet_ids=["line_a", "line_b"],
        )

        region = _make_region("region_1", ["line_a", "line_b", "line_c"])

        project.absorption_lines["line_a"] = line1
        project.absorption_lines["line_b"] = line2
        project.absorption_lines["line_c"] = line3
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        # Triplet should be consolidated into 1 row
        assert group_item.childCount() == 1, (
            f"Expected 1 consolidated row for triplet, got {group_item.childCount()}"
        )

    def test_mixed_multiplet_and_single_display_ids(self, panel: StructureSidePanel) -> None:
        """Mixed multiplet and single lines should have consecutive display IDs."""
        project = SpectroscopyProject()

        # Single line (will be sorted first by z=1.0)
        single_line = _make_line(
            "single",
            center_z=1.0,
            rest_wavelength=1215.668237,
            species="H I",
            region_id="region_1",
            multiplet_ids=[],
        )

        # Doublet (z=1.5)
        line1 = _make_line(
            "mg2_2796",
            center_z=1.5,
            rest_wavelength=2796.352,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2803"],
        )
        line2 = _make_line(
            "mg2_2803",
            center_z=1.5,
            rest_wavelength=2803.531,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2796"],
        )

        region = _make_region("region_1", ["single", "mg2_2796", "mg2_2803"])

        project.absorption_lines["single"] = single_line
        project.absorption_lines["mg2_2796"] = line1
        project.absorption_lines["mg2_2803"] = line2
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        # Should have 2 rows: single + multiplet
        assert group_item.childCount() == 2, (
            f"Expected 2 rows (1 single + 1 multiplet), got {group_item.childCount()}"
        )

        # First row should be single line with ID "1"
        child_0 = group_item.child(0)
        text_0 = child_0.text(0)
        assert text_0.startswith("1."), f"First row should start with '1.': {text_0}"

        # Second row should be multiplet with ID "2"
        child_1 = group_item.child(1)
        text_1 = child_1.text(0)
        assert text_1.startswith("2."), f"Second row should start with '2.': {text_1}"

    def test_selection_returns_primary_line_id(self, panel: StructureSidePanel) -> None:
        """Selecting a multiplet row should return the primary line ID."""
        project = SpectroscopyProject()

        # Primary = smallest rest_wavelength = mg2_2796
        line1 = _make_line(
            "mg2_2796",
            center_z=1.5,
            rest_wavelength=2796.352,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2803"],
        )
        line2 = _make_line(
            "mg2_2803",
            center_z=1.5,
            rest_wavelength=2803.531,
            species="Mg II",
            region_id="region_1",
            multiplet_ids=["mg2_2796"],
        )

        region = _make_region("region_1", ["mg2_2796", "mg2_2803"])

        project.absorption_lines["mg2_2796"] = line1
        project.absorption_lines["mg2_2803"] = line2
        project.absorption_regions[region.region_id] = region

        panel.set_project(project)
        panel.refresh()

        tree = panel._tree
        group_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            data = item.data(0, 0x0100)
            if isinstance(data, dict) and data.get("id") == "region_1":
                group_item = item
                break

        assert group_item is not None
        child = group_item.child(0)

        # Check the UserRole data contains primary line ID
        child_data = child.data(0, 0x0100)  # Qt.ItemDataRole.UserRole
        assert child_data is not None
        assert isinstance(child_data, dict)
        # Primary ID should be the one with smallest rest_wavelength
        assert child_data.get("id") == "mg2_2796", (
            f"Primary ID should be 'mg2_2796', got {child_data.get('id')}"
        )


class TestLinkedLineNodeLineIds:
    """Tests for _LinkedLineNode line_ids field (plural)."""

    def test_linked_line_node_has_line_ids_field(self) -> None:
        """_LinkedLineNode should have a line_ids field (tuple of strings)."""
        from chappy.gui.modes.analysis.overview.panel import _LinkedLineNode

        assert hasattr(_LinkedLineNode, "__dataclass_fields__")
        fields = _LinkedLineNode.__dataclass_fields__
        assert "line_ids" in fields, "_LinkedLineNode should have 'line_ids' field"

    def test_linked_line_node_line_ids_is_tuple(self) -> None:
        """line_ids should be a tuple of strings."""
        from chappy.gui.modes.analysis.overview.panel import _LinkedLineNode

        node = _LinkedLineNode(
            line_ids=("line1", "line2"),
            header_label="Test Label",
            lambda_range=None,
            needs_optimization=False,
        )
        assert isinstance(node.line_ids, tuple)
        assert node.line_ids == ("line1", "line2")
