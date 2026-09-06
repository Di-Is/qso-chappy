"""Tree item rendering helpers for the identify workflow sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from chappy.gui.modes.identify.panel.panel_models import (
    ConfirmedGroupItemPayload,
    ConfirmedLineItemPayload,
    ConfirmedLineRow,
    ConfirmedRegionRow,
    RegionPreviewRow,
    TemporaryLineItemPayload,
    TemporaryLineRow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class IdentifyWorkflowTreeText:
    """Translated text used while rendering workflow tree items."""

    unknown: str
    grouped_template: str = ""
    new_region_template: str = ""
    append_region_template: str = ""
    overlap_warning: str = ""


class IdentifyWorkflowTreeRenderer:
    """Populate identify workflow tree widgets with typed item payloads."""

    def __init__(self) -> None:
        """Initialize the renderer."""

    def render_temporary_lines(
        self,
        tree: QTreeWidget,
        lines: Sequence[TemporaryLineRow],
        previews: Sequence[RegionPreviewRow],
        *,
        selected_primary_ids: set[str],
        text: IdentifyWorkflowTreeText,
    ) -> None:
        """Populate the temporary tree grouped by registration previews.

        Group heading rows are non-selectable; child rows carry the temporary
        line payloads and restore the previous selection by primary ID.
        """
        tree.clear()

        row_lookup: dict[str, TemporaryLineRow] = {}
        for row in lines:
            for temporary_line_id in row.temporary_line_ids:
                row_lookup[temporary_line_id] = row

        display_index = 0
        rendered_row_ids: set[int] = set()
        for preview in previews:
            member_rows = self._unique_member_rows(preview.member_temporary_line_ids, row_lookup)
            if not member_rows:
                continue
            heading = QTreeWidgetItem(tree)
            heading.setText(0, self._group_heading_text(preview, member_rows, text=text))
            heading.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if preview.warning:
                heading.setToolTip(0, text.overlap_warning)

            for member_row in self._sorted_rows(member_rows):
                rendered_row_ids.add(id(member_row))
                display_index += 1
                self._add_temporary_item(
                    heading,
                    member_row,
                    display_index=display_index,
                    selected_primary_ids=selected_primary_ids,
                    text=text,
                )
            heading.setExpanded(True)

        for row in self._sorted_rows(lines):
            if id(row) in rendered_row_ids:
                continue
            display_index += 1
            self._add_temporary_item(
                tree,
                row,
                display_index=display_index,
                selected_primary_ids=selected_primary_ids,
                text=text,
            )

    def render_confirmed_groups(
        self,
        tree: QTreeWidget,
        groups: Sequence[ConfirmedRegionRow],
        *,
        text: IdentifyWorkflowTreeText,
    ) -> None:
        """Populate the group tree with confirmed groups."""
        tree.clear()
        for group in groups:
            self.create_group_item(
                tree=tree,
                group_id=group.group_id,
                label=group.label,
                lines=group.lines,
                is_expanded=group.is_expanded,
                text=text,
            )

    def create_group_item(
        self,
        *,
        tree: QTreeWidget,
        group_id: str,
        label: str,
        lines: Sequence[ConfirmedLineRow],
        is_expanded: bool,
        text: IdentifyWorkflowTreeText,
    ) -> QTreeWidgetItem:
        """Create a confirmed group item and its line children."""
        group_item = QTreeWidgetItem(tree)
        group_item.setText(0, label)
        group_item.setData(0, Qt.ItemDataRole.UserRole, ConfirmedGroupItemPayload(group_id))

        for line in lines:
            self.add_confirmed_line_item(group_item, line, text=text)

        group_item.setExpanded(is_expanded)
        return group_item

    def add_confirmed_line_item(
        self, parent: QTreeWidgetItem, line: ConfirmedLineRow, *, text: IdentifyWorkflowTreeText
    ) -> QTreeWidgetItem:
        """Add a confirmed line item as a child of the given parent."""
        base_label = self._line_display_name(line, text=text)
        line_label = f"{line.display_id}. {base_label}" if line.display_id else base_label
        line_text = f"{line_label} [z={line.redshift:.4f}]"

        line_item = QTreeWidgetItem(parent)
        line_item.setText(0, line_text)
        line_item.setData(0, Qt.ItemDataRole.UserRole, ConfirmedLineItemPayload(line.line_id))
        return line_item

    def format_temporary_line(self, line: TemporaryLineRow, *, display_index: int) -> str:
        """Format a temporary line for list display."""
        base_label = self.temporary_display_name(line)
        prefix = f"{display_index}. "
        z_part = f"[z={line.redshift:.4f}]" if line.redshift is not None else ""
        range_part = f"@ {line.lambda_start:.1f}-{line.lambda_end:.1f}"
        return f"{prefix}{base_label} {z_part} {range_part}".strip()

    def temporary_display_name(self, line: TemporaryLineRow) -> str:
        """Return the preferred display label for a temporary line."""
        if line.multiplet_label:
            return line.multiplet_label
        return line.transition_name

    def _add_temporary_item(
        self,
        parent: QTreeWidget | QTreeWidgetItem,
        line: TemporaryLineRow,
        *,
        display_index: int,
        selected_primary_ids: set[str],
        text: IdentifyWorkflowTreeText,
    ) -> None:
        primary_id = line.temporary_line_ids[0]
        tree_item = QTreeWidgetItem(
            [self.format_temporary_line(line, display_index=display_index)]
        )
        tree_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            TemporaryLineItemPayload(
                primary_temporary_line_id=primary_id, temporary_line_ids=line.temporary_line_ids
            ),
        )

        member_count = len(line.temporary_line_ids)
        if member_count > 1:
            tree_item.setToolTip(0, text.grouped_template.format(count=member_count))

        if isinstance(parent, QTreeWidget):
            parent.addTopLevelItem(tree_item)
        else:
            parent.addChild(tree_item)
        if primary_id in selected_primary_ids:
            tree_item.setSelected(True)

    def _group_heading_text(
        self,
        preview: RegionPreviewRow,
        member_rows: Sequence[TemporaryLineRow],
        *,
        text: IdentifyWorkflowTreeText,
    ) -> str:
        count = len(member_rows)
        if preview.is_existing_group:
            heading = text.append_region_template.format(region=preview.label, count=count)
        else:
            species = member_rows[0].species or text.unknown
            heading = text.new_region_template.format(
                species=species,
                start=min(row.lambda_start for row in member_rows),
                end=max(row.lambda_end for row in member_rows),
                count=count,
            )
        if preview.warning:
            heading = f"{heading} ⚠"
        return heading

    @staticmethod
    def _unique_member_rows(
        member_temporary_line_ids: Sequence[str], row_lookup: dict[str, TemporaryLineRow]
    ) -> list[TemporaryLineRow]:
        rows: list[TemporaryLineRow] = []
        seen: set[int] = set()
        for member_id in member_temporary_line_ids:
            row = row_lookup.get(member_id)
            if row is None or id(row) in seen:
                continue
            seen.add(id(row))
            rows.append(row)
        return rows

    @staticmethod
    def _sorted_rows(rows: Sequence[TemporaryLineRow]) -> list[TemporaryLineRow]:
        return sorted(
            rows, key=lambda row: row.redshift if row.redshift is not None else float("inf")
        )

    def _line_display_name(self, line: ConfirmedLineRow, *, text: IdentifyWorkflowTreeText) -> str:
        label = (line.transition_name or "").strip()
        if not label:
            label = (line.species or "").strip()
        if label:
            return label
        return text.unknown
