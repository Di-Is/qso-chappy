"""Confirmed regions section for the identify side panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QKeyEvent, QMouseEvent

    from chappy.gui.modes.identify.panel.panel_models import ConfirmedRegionRow

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chappy.gui.modes.identify.panel.panel_models import ConfirmedGroupItemPayload
from chappy.gui.modes.identify.panel.workflow_selection_controller import (
    IdentifyWorkflowSelectionController,
)
from chappy.gui.modes.identify.panel.workflow_tree_renderer import (
    IdentifyWorkflowTreeRenderer,
    IdentifyWorkflowTreeText,
)
from chappy.gui.theme import create_styled_menu, empty_state_label_style, table_surface_frame_style
from chappy.gui.visual_tokens import SidePanelMetrics


class _ConfirmedRegionsTree(QTreeWidget):
    """Tree whose Qt activation signal consistently covers Enter and double-click."""

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Activate the current item when Enter or Return is pressed."""
        item = self.currentItem()
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return) and item is not None:
            self.itemActivated.emit(item, max(0, self.currentColumn()))
            event.accept()
            return
        super().keyPressEvent(event)

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Convert a double-click into exactly one Qt activation signal."""
        item = self.itemAt(event.position().toPoint())
        if item is None:
            super().mouseDoubleClickEvent(event)
            return
        was_blocked = self.blockSignals(True)
        super().mouseDoubleClickEvent(event)
        self.blockSignals(was_blocked)
        self.itemActivated.emit(item, self.currentColumn())


class IdentifyConfirmedRegionsSection(QWidget):
    """Confirmed absorption regions with focus and activation interactions."""

    group_focus_requested = Signal(str, float, float)
    line_focus_requested = Signal(str, float, float)
    region_open_requested = Signal(str)
    region_structure_edit_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construct the confirmed regions section."""
        super().__init__(parent)
        self.setObjectName("identifyConfirmedSection")
        self._confirmed_regions: list[ConfirmedRegionRow] = []
        self._tree_renderer = IdentifyWorkflowTreeRenderer()
        self._selection_controller = IdentifyWorkflowSelectionController()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SidePanelMetrics.SECTION_SPACING)

        self._groups_tree = _ConfirmedRegionsTree(self)
        self._groups_tree.setObjectName("identifyGroupsTree")
        self._groups_tree.setColumnCount(1)
        self._groups_tree.setHeaderHidden(True)
        self._groups_tree.setRootIsDecorated(True)
        self._groups_tree.setIndentation(16)
        self._groups_tree.setUniformRowHeights(True)
        self._groups_tree.setAlternatingRowColors(True)
        self._groups_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._groups_tree.setStyleSheet(
            "QTreeWidget#identifyGroupsTree { border: none; border-radius: 0; }"
        )
        self._groups_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._groups_tree.itemActivated.connect(self._activate_focus_target)
        self._groups_tree.customContextMenuRequested.connect(self._show_row_context_menu)

        self._empty_placeholder = QLabel(self)
        self._empty_placeholder.setObjectName("identifyConfirmedEmptyState")
        self._empty_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_placeholder.setWordWrap(True)
        self._empty_placeholder.setStyleSheet(empty_state_label_style())

        self._content_surface = QFrame(self)
        self._content_surface.setObjectName("identifyConfirmedContentSurface")
        self._content_surface.setStyleSheet(
            table_surface_frame_style("identifyConfirmedContentSurface")
        )
        content_layout = QVBoxLayout(self._content_surface)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._groups_tree, 1)
        content_layout.addWidget(self._empty_placeholder)
        root.addWidget(self._content_surface, 1)

        self.retranslate_ui()
        self.set_confirmed_regions([])

    def retranslate_ui(self) -> None:
        """Apply the active language to all visible strings."""
        self._empty_placeholder.setText(self.tr("Registered regions appear here."))
        if self._confirmed_regions:
            self.set_confirmed_regions(self._confirmed_regions)

    def set_confirmed_regions(self, groups: Sequence[ConfirmedRegionRow]) -> None:
        """Populate the confirmed regions tree."""
        self._confirmed_regions = list(groups)
        self._tree_renderer.render_confirmed_groups(
            self._groups_tree, self._confirmed_regions, text=self._tree_text()
        )

        self._groups_tree.setVisible(bool(self._confirmed_regions))
        self._empty_placeholder.setVisible(not self._confirmed_regions)

    def reveal_regions(self, region_ids: Sequence[str]) -> None:
        """Select and scroll to the first of the given regions."""
        wanted = set(region_ids)
        matched: list[QTreeWidgetItem] = []
        for index in range(self._groups_tree.topLevelItemCount()):
            item = self._groups_tree.topLevelItem(index)
            if item is None:
                continue
            payload = self._selection_controller.item_payload(item)
            if isinstance(payload, ConfirmedGroupItemPayload) and payload.group_id in wanted:
                matched.append(item)
        if not matched:
            return
        self._groups_tree.setCurrentItem(matched[0])
        self._groups_tree.scrollToItem(matched[0], QAbstractItemView.ScrollHint.PositionAtTop)

    @property
    def has_groups(self) -> bool:
        """Return whether confirmed regions are available."""
        return bool(self._confirmed_regions)

    def summary_text(self) -> str:
        """Return the collapsed summary with count and representative region context."""
        count = len(self._confirmed_regions)
        if count == 0:
            return self.tr("0 regions · Shown after registration")
        regions = self.tr("{count} region") if count == 1 else self.tr("{count} regions")
        representative = self._confirmed_regions[-1]
        if representative.lines:
            line = representative.lines[0]
            #: {regions} is a localized region count; {label} is a region label;
            #: {species} and {redshift} identify its first line.
            template = self.tr("{regions} · {label} · {species} z={redshift:.4f}")
            return template.format(
                regions=regions.format(count=count),
                label=representative.label,
                species=line.species,
                redshift=line.redshift,
            )
        #: {regions} is a localized region count; {label} is a region label.
        template = self.tr("{regions} · {label}")
        return template.format(regions=regions.format(count=count), label=representative.label)

    def _tree_text(self) -> IdentifyWorkflowTreeText:
        return IdentifyWorkflowTreeText(unknown=self.tr("Unknown"))

    def _activate_focus_target(self, item: QTreeWidgetItem, _column: int) -> None:
        """Focus the group or line activated by Enter or double-click."""
        if item is None:
            return

        target = self._selection_controller.resolve_focus_target(
            item, confirmed_regions=self._confirmed_regions
        )
        if target is None:
            return

        if target.is_group:
            self.group_focus_requested.emit(
                target.identifier, target.min_wavelength, target.max_wavelength
            )
        else:
            self.line_focus_requested.emit(
                target.identifier, target.min_wavelength, target.max_wavelength
            )

    def _show_row_context_menu(self, position: QPoint) -> None:
        """Offer the Analysis entry points for the region under the cursor."""
        item = self._groups_tree.itemAt(position)
        if item is None:
            return
        region_id = self._resolve_region_id(item)
        if region_id is None:
            return

        self._groups_tree.setCurrentItem(item)
        menu = create_styled_menu(self)
        menu.addAction(self.tr("Open region"), lambda: self.region_open_requested.emit(region_id))
        menu.addAction(
            self.tr("Edit region"), lambda: self.region_structure_edit_requested.emit(region_id)
        )
        menu.exec(self._groups_tree.viewport().mapToGlobal(position))

    def _resolve_region_id(self, item: QTreeWidgetItem) -> str | None:
        payload = self._selection_controller.item_payload(item)
        if isinstance(payload, ConfirmedGroupItemPayload):
            return payload.group_id
        parent = item.parent()
        if parent is None:
            return None
        parent_payload = self._selection_controller.item_payload(parent)
        if isinstance(parent_payload, ConfirmedGroupItemPayload):
            return parent_payload.group_id
        return None

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Refresh translated text when Qt installs a new translator."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
