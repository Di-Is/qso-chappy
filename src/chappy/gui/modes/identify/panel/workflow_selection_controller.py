"""Selection and focus resolution for the identify workflow sections."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from chappy.gui.modes.identify.panel.panel_models import (
    ConfirmedGroupItemPayload,
    ConfirmedLineItemPayload,
    ConfirmedLineRow,
    ConfirmedRegionRow,
    IdentifyWorkflowItemPayload,
    TemporaryLineItemPayload,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


@dataclass(frozen=True, slots=True)
class IdentifyWorkflowFocusTarget:
    """Resolved target for focusing a spectrum range."""

    identifier: str
    min_wavelength: float
    max_wavelength: float
    is_group: bool


class IdentifyWorkflowSelectionController:
    """Resolve workflow tree selections from typed item payloads."""

    def selected_temporary_primary_ids(self, tree: QTreeWidget) -> list[str]:
        """Return primary IDs for selected temporary rows."""
        selected_ids: list[str] = []
        for item in tree.selectedItems():
            payload = self.item_payload(item)
            if isinstance(payload, TemporaryLineItemPayload):
                selected_ids.append(payload.primary_temporary_line_id)
        return selected_ids

    def selected_temporary_primary_id_set(self, tree: QTreeWidget) -> set[str]:
        """Return primary IDs for selected temporary rows as a set."""
        return set(self.selected_temporary_primary_ids(tree))

    def resolve_focus_target(
        self, item: QTreeWidgetItem, *, confirmed_regions: Sequence[ConfirmedRegionRow]
    ) -> IdentifyWorkflowFocusTarget | None:
        """Resolve the spectrum focus target represented by a group tree item."""
        payload = self.item_payload(item)
        if payload is None:
            return None

        if isinstance(payload, ConfirmedGroupItemPayload):
            ranges = self._collect_descendant_ranges(item, confirmed_regions=confirmed_regions)
            if not ranges:
                return None
            min_wave = min(start for start, _ in ranges)
            max_wave = max(end for _, end in ranges)
            if not math.isfinite(min_wave) or not math.isfinite(max_wave):
                return None
            return IdentifyWorkflowFocusTarget(
                identifier=payload.group_id,
                min_wavelength=float(min_wave),
                max_wavelength=float(max_wave),
                is_group=True,
            )

        if isinstance(payload, ConfirmedLineItemPayload):
            range_pair = self._resolve_item_range(payload, confirmed_regions=confirmed_regions)
            if range_pair is None or not all(math.isfinite(value) for value in range_pair):
                return None
            return IdentifyWorkflowFocusTarget(
                identifier=payload.line_id,
                min_wavelength=float(range_pair[0]),
                max_wavelength=float(range_pair[1]),
                is_group=False,
            )

        return None

    def item_payload(self, item: QTreeWidgetItem) -> IdentifyWorkflowItemPayload | None:
        """Return the typed payload stored on an item, if present."""
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(
            payload,
            (TemporaryLineItemPayload, ConfirmedGroupItemPayload, ConfirmedLineItemPayload),
        ):
            return payload
        return None

    def _collect_descendant_ranges(
        self, root_item: QTreeWidgetItem, *, confirmed_regions: Sequence[ConfirmedRegionRow]
    ) -> list[tuple[float, float]]:
        ranges: list[tuple[float, float]] = []
        nodes: list[QTreeWidgetItem] = [root_item]
        while nodes:
            node = nodes.pop()
            payload = self.item_payload(node)
            if isinstance(payload, ConfirmedLineItemPayload):
                range_pair = self._resolve_item_range(payload, confirmed_regions=confirmed_regions)
                if range_pair is not None:
                    ranges.append(range_pair)
            if node.childCount():
                nodes.extend(node.child(index) for index in range(node.childCount()))
        return ranges

    def _resolve_item_range(
        self, payload: ConfirmedLineItemPayload, *, confirmed_regions: Sequence[ConfirmedRegionRow]
    ) -> tuple[float, float] | None:
        line_row = self._find_confirmed_line_row(payload.line_id, confirmed_regions)
        if line_row is None:
            return None
        return self._normalise_range(line_row.lambda_start, line_row.lambda_end)

    @staticmethod
    def _find_confirmed_line_row(
        line_id: str, confirmed_regions: Sequence[ConfirmedRegionRow]
    ) -> ConfirmedLineRow | None:
        for group in confirmed_regions:
            for line in group.lines:
                if line.line_id == line_id:
                    return line
        return None

    @staticmethod
    def _normalise_range(lambda_start: float, lambda_end: float) -> tuple[float, float]:
        if lambda_end < lambda_start:
            lambda_start, lambda_end = lambda_end, lambda_start
        return float(lambda_start), float(lambda_end)
