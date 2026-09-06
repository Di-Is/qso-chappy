"""Structure mode side panel showing absorption regions and lines."""

from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import suppress
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QMouseEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.gui.adapters.model_event_adapter import SpectrumModelEventAdapter
from chappy.gui.modes.analysis.overview.review_widget import AnalysisOverviewReviewWidget
from chappy.gui.theme import (
    BACK_ARROW_PREFIX,
    Colors,
    Fonts,
    apply_button_variant,
    card_frame_style,
    empty_state_label_style,
)
from chappy.gui.utils.region_sorting import sort_regions_for_display
from chappy.gui.visual_tokens import SidePanelMetrics
from chappy.i18n import get_language_switcher
from chappy.presentation.analysis.structure.tree_presenter import (
    StructureLinkedLineNode as _LinkedLineNode,
)
from chappy.presentation.analysis.structure.tree_presenter import (
    StructureRegionEntry as _GroupEntry,
)
from chappy.presentation.analysis.structure.tree_presenter import StructureTreePresenter

if TYPE_CHECKING:
    from chappy.core.components.base import ModelComponent
    from chappy.core.events import RegionTopologyChanged
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.core.spectrum_model import SpectrumModel
    from chappy.gui.modes.common.analysis_navigation import AnalysisOverviewNavigationPort
    from chappy.presentation.analysis import AnalysisReviewRow, AnalysisReviewSummary


_LINE_MIME_TYPE = "application/x-chappy-absorption-line"
_NEW_GROUP_PLACEHOLDER_ID = "__new_group__"
_NEW_REGION_DROP_TARGET = ""


class _StructureTreeWidget(QTreeWidget):
    """Tree widget with drag-and-drop support for absorption lines."""

    move_requested = Signal(str, list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:  # noqa: N802
        line_ids = self._collect_drag_payload()
        if not line_ids:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(
            _LINE_MIME_TYPE, json.dumps({"line_ids": sorted(line_ids)}).encode("utf-8")
        )
        drag.setMimeData(mime_data)
        drag.exec(supported_actions)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._is_valid_drag(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._is_valid_drag(event.mimeData(), event.position().toPoint()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        line_ids = self._decode_drag_payload(event.mimeData())
        if not line_ids:
            event.ignore()
            return

        target_item = self.itemAt(event.position().toPoint())
        target_region_id = _NEW_REGION_DROP_TARGET
        if target_item is not None:
            data = target_item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict):
                event.ignore()
                return
            item_type = data.get("type")
            if item_type == "group":
                region_id = data.get("id")
                if not isinstance(region_id, str):
                    event.ignore()
                    return
                target_region_id = region_id
            elif item_type == "new_group":
                target_region_id = _NEW_REGION_DROP_TARGET
            else:
                event.ignore()
                return

        self.move_requested.emit(target_region_id, line_ids)
        event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if item is None:
            super().mouseDoubleClickEvent(event)
            return

        self.setCurrentItem(item)
        event.accept()
        self.itemDoubleClicked.emit(item, 0)

    def _collect_drag_payload(self) -> set[str]:
        payload: set[str] = set()
        for item in self.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict):
                continue
            item_type = data.get("type")
            if item_type == "absorption_line":
                identifier = data.get("id")
                if isinstance(identifier, str):
                    payload.add(identifier)
                multiplet_ids = data.get("multiplet_ids")
                if isinstance(multiplet_ids, Sequence):
                    for related_id in multiplet_ids:
                        if isinstance(related_id, str):
                            payload.add(related_id)
        return payload

    @staticmethod
    def _decode_drag_payload(mime_data: QMimeData) -> list[str]:
        if not mime_data.hasFormat(_LINE_MIME_TYPE):
            return []
        raw_data = mime_data.data(_LINE_MIME_TYPE).data()
        if raw_data is None:
            return []
        raw = bytes(raw_data)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):  # pragma: no cover - defensive
            return []
        line_ids = payload.get("line_ids", [])
        if not isinstance(line_ids, list):
            return []
        return [lid for lid in line_ids if isinstance(lid, str)]

    def _is_valid_drag(self, mime_data: QMimeData, pos: QPoint | None = None) -> bool:
        if not mime_data.hasFormat(_LINE_MIME_TYPE):
            return False
        if pos is None:
            return True
        target = self.itemAt(pos)
        if target is None:
            return True
        data = target.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return False
        return data.get("type") in {"group", "new_group"}


class StructureSidePanel(QWidget):
    """Side panel dedicated to structure mode absorber management."""

    selection_changed = Signal(list, list)  # region_ids, line_ids
    group_activated = Signal(str)
    line_activated = Signal(str)
    context_menu_requested = Signal(QPoint, list, list)
    line_move_requested = Signal(str, list)
    unlink_requested = Signal()
    merge_requested = Signal()
    split_requested = Signal()
    delete_requested = Signal()
    region_open_requested = Signal(str)
    region_delete_requested = Signal(str)
    review_refresh_requested = Signal()
    back_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        navigation: AnalysisOverviewNavigationPort | None = None,
        review: AnalysisOverviewReviewWidget | None = None,
        embed_review: bool = True,
    ) -> None:
        """Set up UI controls for the structure side panel."""
        super().__init__(parent)
        self.setObjectName("structureSidePanel")

        self._project: SpectroscopyProject | None = None
        self._model: SpectrumModel | None = None
        self._model_event_adapter: SpectrumModelEventAdapter | None = None
        self._groups: dict[str, _GroupEntry] = {}
        self._group_items: dict[str, QTreeWidgetItem] = {}
        self._linked_line_nodes: dict[str, _LinkedLineNode] = {}
        self._linked_line_items: dict[str, QTreeWidgetItem] = {}
        self._new_group_placeholder: QTreeWidgetItem | None = None
        self._language_switcher = get_language_switcher(self)
        self._tree_presenter = self._create_tree_presenter()
        self._navigation = navigation

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*SidePanelMetrics.OUTER_MARGIN)
        layout.setSpacing(SidePanelMetrics.SECTION_SPACING)

        self._review = review or AnalysisOverviewReviewWidget(navigation, self)
        self._review.region_selected.connect(self._on_review_region_selected)
        self._review.region_open_requested.connect(self.region_open_requested)
        self._review.region_delete_requested.connect(self.region_delete_requested)
        self._review.structure_edit_requested.connect(self._show_structure_editor)
        if embed_review:
            layout.addWidget(self._review, stretch=2)

        self._back_button = QPushButton(BACK_ARROW_PREFIX + self.tr("Back to Overview"), self)
        self._back_button.setObjectName("structureSidePanelBackButton")
        self._back_button.setToolTip(self.tr("Return to Analysis Overview (Alt+Left)"))
        apply_button_variant(self._back_button, "text")
        self._back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_button.clicked.connect(self.back_requested)
        back_row = QHBoxLayout()
        back_row.setContentsMargins(0, 0, 0, 0)
        back_row.addWidget(self._back_button)
        back_row.addStretch(1)
        layout.addLayout(back_row)

        self._header_label = QLabel(self.tr("Edit regions"))
        self._header_label.setObjectName("structureSidePanelHeader")
        self._header_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_MEDIUM}; font-weight: 600;"
        )
        layout.addWidget(self._header_label)

        self._tree = _StructureTreeWidget(self)
        self._tree.setObjectName("analysisStructureTree")
        self._tree.setColumnCount(1)
        self._tree.header().setVisible(False)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_font = self._tree.font()
        header_font.setFamily(Fonts.FAMILY)
        self._tree.setFont(header_font)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setAllColumnsShowFocus(True)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setStyleSheet(
            f"QTreeWidget#analysisStructureTree {{"
            f" background-color: {Colors.BACKGROUND_PANEL};"
            f" border: none;"
            "}"
            f"QTreeWidget::item:selected#analysisStructureTree {{"
            f" background-color: {Colors.ACCENT_SELECTION_LIGHT};"
            f" color: {Colors.TEXT_PRIMARY};"
            "}"
        )
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self._tree.move_requested.connect(self._on_tree_move_requested)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.customContextMenuRequested.connect(self._on_context_menu_requested)

        tree_container = QFrame(self)
        tree_container.setObjectName("structureSidePanelTreeContainer")
        tree_layout = QStackedLayout(tree_container)
        tree_layout.setContentsMargins(*SidePanelMetrics.CARD_CONTENT_MARGIN)
        tree_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        tree_layout.addWidget(self._tree)

        tree_container.setStyleSheet(card_frame_style("structureSidePanelTreeContainer"))

        self._placeholder = QLabel(self.tr("Load absorber data to manage regions and lines here."))
        self._placeholder.setObjectName("structureSidePanelEmptyState")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet(empty_state_label_style())
        self._placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        tree_layout.addWidget(self._placeholder)

        self._tree_container = tree_container
        layout.addWidget(tree_container, stretch=1)

        structure_actions = QHBoxLayout()
        self._merge_button = QPushButton(self)
        self._merge_button.setObjectName("analysisOverviewMergeButton")
        self._merge_button.clicked.connect(self.merge_requested.emit)
        apply_button_variant(self._merge_button, "secondary")
        structure_actions.addWidget(self._merge_button)
        self._split_button = QPushButton(self)
        self._split_button.setObjectName("analysisOverviewSplitButton")
        self._split_button.clicked.connect(self.split_requested.emit)
        apply_button_variant(self._split_button, "secondary")
        structure_actions.addWidget(self._split_button)
        self._delete_button = QPushButton(self)
        self._delete_button.setObjectName("analysisOverviewDeleteButton")
        self._delete_button.clicked.connect(self.delete_requested.emit)
        apply_button_variant(self._delete_button, "danger")
        structure_actions.addWidget(self._delete_button)
        layout.addLayout(structure_actions)

        self._unlink_button = QPushButton(self)
        self._unlink_button.setObjectName("structureUnlinkLinkedLinesButton")
        self._unlink_button.setEnabled(False)
        apply_button_variant(self._unlink_button, "secondary")
        self._unlink_button.clicked.connect(self.unlink_requested.emit)
        layout.addWidget(self._unlink_button)
        self._retranslate_structure_actions()
        self.set_structure_actions_enabled(merge=False, split=False, delete=False, unlink=False)

        self._update_placeholder_visibility()
        self.set_structure_editor_visible(False)
        self._language_switcher.language_changed.connect(self._handle_language_changed)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Refresh translated text when Qt translators change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_ui()
        super().changeEvent(event)

    def _handle_language_changed(self, _code: str) -> None:
        """Refresh UI texts when the application language changes."""
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        """Refresh static labels and rebuild dynamic translated items."""
        self._header_label.setText(self.tr("Edit regions"))
        self._back_button.setText(BACK_ARROW_PREFIX + self.tr("Back to Overview"))
        self._back_button.setToolTip(self.tr("Return to Analysis Overview (Alt+Left)"))
        self._placeholder.setText(self.tr("Load absorber data to manage regions and lines here."))
        self._retranslate_structure_actions()
        self._tree_presenter = self._create_tree_presenter()
        selected_groups, selected_linked_lines = self.get_selection()
        self.refresh()
        self.restore_selection(selected_groups, selected_linked_lines)

    def _retranslate_structure_actions(self) -> None:
        """Keep structure action labels short; full sentences live in tooltips."""
        self._merge_button.setText(self.tr("Merge"))
        self._merge_button.setToolTip(self.tr("Merge the selected regions into one region."))
        self._split_button.setText(self.tr("Split"))
        self._split_button.setToolTip(self.tr("Split the selected lines into a new region."))
        self._delete_button.setText(self.tr("Delete"))
        self._delete_button.setToolTip(self.tr("Delete the selected regions and lines."))
        self._unlink_button.setText(self.tr("Unlink linked lines"))
        self._unlink_button.setToolTip(
            self.tr(
                "Unlink these linked lines: keep the lines and remove only the links between them."
            )
        )

    def _create_tree_presenter(self) -> StructureTreePresenter:
        """Create a translated presenter for structure tree rows."""
        return StructureTreePresenter(
            range_tooltip_template=self.tr("Observed range: {minimum:.2f} – {maximum:.2f} Å"),
            linked_line_header_template=self.tr(
                "{species} {wavelengths} [z={redshift}, ±{window} km/s]"
            ),
            unknown_label=self.tr("Unknown"),
        )

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Assign the project whose absorber data will be displayed."""
        if project is self._project:
            return

        self._disconnect_model_signals()
        self._project = project
        self._model = project.model if project is not None else None
        self._review.set_project(project)

        if self._model is not None:
            # Keep tree in sync with absorber additions/removals
            self._model_event_adapter = SpectrumModelEventAdapter(self._model, self)
            self._model_event_adapter.component_added.connect(self._rebuild_from_model)
            self._model_event_adapter.component_removed.connect(self._rebuild_from_model)
            self._model_event_adapter.region_topology_changed.connect(
                self._on_region_topology_changed
            )

        self.refresh()
        self._review.restore_navigation_state()

    def refresh(self) -> None:
        """Rebuild tree contents from the current project state."""
        self.review_refresh_requested.emit()
        selected_region_ids, selected_line_ids = self._tree_selection_ids()
        self._groups = {}
        self._group_items = {}
        self._linked_line_nodes = {}
        self._linked_line_items = {}
        self._tree.blockSignals(True)
        self._tree.clear()
        self._new_group_placeholder = None

        group_entries = self._collect_absorption_group_entries()

        if not group_entries:
            self._insert_new_group_placeholder()
            self._tree.blockSignals(False)
            self._update_placeholder_visibility()
            return

        for group in group_entries:
            top_item = self._create_group_item(group)
            if group.linked_line_nodes:
                for linked_line_node in group.linked_line_nodes:
                    linked_line_item = self._create_linked_line_header_item(
                        top_item, group.identifier, linked_line_node
                    )
                    if linked_line_item is None:
                        continue
                    # Use primary line_id (first in tuple) as key
                    primary_id = linked_line_node.line_ids[0]
                    self._linked_line_nodes[primary_id] = linked_line_node
            self._tree.addTopLevelItem(top_item)
            top_item.setExpanded(True)

        self._insert_new_group_placeholder()
        self._tree.blockSignals(False)
        self._update_placeholder_visibility()
        self._select_tree_items(selected_region_ids, selected_line_ids)

    def render_review(
        self, rows: Sequence[AnalysisReviewRow], summary: AnalysisReviewSummary
    ) -> None:
        """Render controller-provided typed review output."""
        self._review.sync_rows(rows, summary)

    def focus_review_region(self, region_id: str) -> bool:
        """Focus the Overview row restored from Region Detail."""
        return self._review.focus_return_region(region_id)

    def group_entry(self, identifier: str) -> _GroupEntry | None:
        """Return metadata for a registered group identifier."""
        return self._groups.get(identifier)

    def get_selection(self) -> tuple[list[str], list[str]]:
        """Return current (region_ids, line_ids) selection snapshot."""
        if not self._tree_container.isVisible():
            region_id = self._review.selected_region_id()
            return ([region_id] if region_id is not None else []), []
        return self._tree_selection_ids()

    def _tree_selection_ids(self) -> tuple[list[str], list[str]]:
        """Return the identities currently selected in the structure tree."""
        region_ids: list[str] = []
        line_ids: list[str] = []
        for item in self._tree.selectedItems():
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(payload, dict):
                continue
            item_type = payload.get("type")
            identifier = payload.get("id")
            if item_type == "group" and isinstance(identifier, str):
                region_ids.append(identifier)
            elif item_type == "absorption_line" and isinstance(identifier, str):
                line_ids.append(identifier)
        return region_ids, line_ids

    def clear_selection(self) -> None:
        """Clear the current selection without emitting signals."""
        self._review.clear_selection()
        self._tree.blockSignals(True)
        self._tree.clearSelection()
        self._tree.blockSignals(False)
        self._tree.clearFocus()

    def set_unlink_enabled(self, enabled: bool) -> None:
        """Set availability of the explicit linked-line unlink operation."""
        self._unlink_button.setEnabled(enabled)

    def set_structure_actions_enabled(
        self, *, merge: bool, split: bool, delete: bool, unlink: bool
    ) -> None:
        """Set availability of every visible structure editor action."""
        self._merge_button.setEnabled(merge)
        self._split_button.setEnabled(split)
        self._delete_button.setEnabled(delete)
        self._unlink_button.setEnabled(unlink)

    def restore_selection(
        self, region_ids: Sequence[str] | None = None, line_ids: Sequence[str] | None = None
    ) -> None:
        """Reapply selection in the tree without triggering recursive updates."""
        if region_ids:
            self._review.select_region(region_ids[0])
        targets = self._select_tree_items(region_ids or (), line_ids or ())

        if targets:
            self._tree.scrollToItem(targets[0], QAbstractItemView.ScrollHint.PositionAtCenter)

        self._on_selection_changed()

    def _select_tree_items(
        self, region_ids: Sequence[str], line_ids: Sequence[str]
    ) -> list[QTreeWidgetItem]:
        """Select the still-existing identities silently and return their items."""
        targets = [
            item
            for identifier in region_ids
            if (item := self._group_items.get(identifier)) is not None
        ]
        targets.extend(
            item
            for identifier in line_ids
            if (item := self._linked_line_items.get(identifier)) is not None
        )

        self._tree.blockSignals(True)
        self._tree.clearSelection()
        for item in targets:
            item.setSelected(True)
        self._tree.blockSignals(False)
        return targets

    def set_structure_editor_visible(self, visible: bool) -> None:
        """Show or hide the session-only structure editor panel state."""
        self._tree_container.setVisible(visible)
        self._merge_button.setVisible(visible)
        self._split_button.setVisible(visible)
        self._delete_button.setVisible(visible)
        self._unlink_button.setVisible(visible)

    def _on_review_region_selected(self, region_id: str) -> None:
        """Publish row selection without treating it as an open request."""
        if not self._tree_container.isVisible():
            self.selection_changed.emit([region_id], [])

    def _show_structure_editor(self, region_id: str) -> None:
        """Open the existing typed structure editor for one selected region."""
        self.set_structure_editor_visible(True)
        self.restore_selection((region_id,), ())

    def _collect_absorption_group_entries(self) -> list[_GroupEntry]:
        project = self._project
        if not project:
            return []

        absorption_regions = project.absorption_regions
        absorption_lines = project.absorption_lines
        if not absorption_regions or not absorption_lines:
            return []

        entries: list[_GroupEntry] = []
        # Sort by wavelength (left edge of analysis_range) for intuitive ordering
        for region_id, region in sort_regions_for_display(list(absorption_regions.items())):
            if region_id == UNASSIGNED_REGION_ID:
                continue
            entry = self._tree_presenter.build_absorption_region_entry(
                region_id=region_id,
                region=region,
                lines=absorption_lines,
                component_resolver=self._project,
            )
            if entry is not None:
                entries.append(entry)

        self._groups = {entry.identifier: entry for entry in entries}
        return entries

    def _create_group_item(self, group: _GroupEntry) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setIcon(0, QIcon(self._group_color_pixmap(group)))
        self._render_group_item_text(item, group)
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "type": "group",
                "id": group.identifier,
                "component_ids": list({component.id for component in group.components}),
            },
        )
        self._group_items[group.identifier] = item
        return item

    def _render_group_item_text(self, item: QTreeWidgetItem, group: _GroupEntry) -> None:
        parts = [group.label]

        if group.shows_badges:
            range_label = None
            if group.wavelength_min is not None and group.wavelength_max is not None:
                range_text = self._tree_presenter.format_range_text(
                    (group.wavelength_min, group.wavelength_max)
                )
                if range_text:
                    range_label = self.tr("(λ: {range_text} Å)").format(range_text=range_text)

            linked_line_count = self._group_linked_line_count(group)
            count_label = ""
            if linked_line_count:
                if linked_line_count == 1:
                    count_label = self.tr("(1 line)")
                else:
                    count_label = self.tr("({count} lines)").format(count=linked_line_count)

            if range_label:
                parts.append(range_label)
            if count_label:
                parts.append(count_label)

        if group.needs_optimization:
            parts.append("⚠️")

        item.setText(0, " ".join(part for part in parts if part))
        tooltip_lines = [part for part in parts if part and part != "⚠️"]
        if group.needs_optimization:
            tooltip_lines.append("⚠️ " + self.tr("This group needs parameter re-optimization."))
        item.setToolTip(0, "\n".join(tooltip_lines))

    def _group_linked_line_count(self, group: _GroupEntry) -> int:
        if group.linked_line_count:
            return group.linked_line_count
        if group.linked_line_nodes:
            return len(group.linked_line_nodes)
        if group.components:
            return len(group.components)
        return 0

    def _create_linked_line_header_item(
        self, parent: QTreeWidgetItem, group_id: str, linked_line_node: _LinkedLineNode
    ) -> QTreeWidgetItem | None:
        item = QTreeWidgetItem(parent)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        # Prepend display ID to header label
        header_text = linked_line_node.header_label
        if linked_line_node.display_id is not None:
            header_text = f"{linked_line_node.display_id}. {header_text}"

        item.setText(0, header_text)
        if linked_line_node.tooltip:
            item.setToolTip(0, linked_line_node.tooltip)

        # Use primary line_id for selection/operations (ADR 6.3)
        primary_id = linked_line_node.line_ids[0]
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "type": "absorption_line",
                "id": primary_id,
                "group_id": group_id,
                "multiplet_ids": linked_line_node.multiplet_ids,
            },
        )
        self._linked_line_items[primary_id] = item
        return item

    def _update_placeholder_visibility(self) -> None:
        total_items = self._tree.topLevelItemCount()
        placeholder_count = 1 if self._new_group_placeholder is not None else 0
        has_groups = total_items > placeholder_count
        self._placeholder.setVisible(not has_groups)

    def _insert_new_group_placeholder(self) -> None:
        if self._new_group_placeholder is not None:
            index = self._tree.indexOfTopLevelItem(self._new_group_placeholder)
            if index >= 0:
                self._tree.takeTopLevelItem(index)

        placeholder = QTreeWidgetItem()
        placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
        placeholder.setText(0, self.tr("Drop here to create a new region"))
        placeholder.setToolTip(0, self.tr("Drag lines here to create a new region."))
        placeholder.setData(
            0, Qt.ItemDataRole.UserRole, {"type": "new_group", "id": _NEW_GROUP_PLACEHOLDER_ID}
        )
        self._tree.addTopLevelItem(placeholder)
        self._new_group_placeholder = placeholder

    def _disconnect_model_signals(self) -> None:
        if self._model_event_adapter is not None:
            with suppress(TypeError):
                self._model_event_adapter.component_added.disconnect(self._rebuild_from_model)
            with suppress(TypeError):
                self._model_event_adapter.component_removed.disconnect(self._rebuild_from_model)
            with suppress(TypeError):
                self._model_event_adapter.region_topology_changed.disconnect(
                    self._on_region_topology_changed
                )
            self._model_event_adapter.close()
            self._model_event_adapter = None
        self._model = None

    def _on_tree_move_requested(self, target_region_id: str, line_ids: list[str]) -> None:
        if not line_ids:
            return
        self.line_move_requested.emit(target_region_id, line_ids)

    def _on_selection_changed(self) -> None:
        region_ids: list[str] = []
        line_ids: list[str] = []
        for item in self._tree.selectedItems():
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(payload, dict):
                continue
            item_type = payload.get("type")
            if item_type == "group":
                identifier = payload.get("id")
                if isinstance(identifier, str):
                    region_ids.append(identifier)
            elif item_type == "absorption_line":
                identifier = payload.get("id")
                if isinstance(identifier, str):
                    line_ids.append(identifier)
        self.selection_changed.emit(region_ids, line_ids)
        if self._navigation is not None:
            self._navigation.update_structure_selection(
                region_ids=tuple(region_ids), line_ids=tuple(line_ids)
            )

    def _on_item_double_clicked(self, item: QTreeWidgetItem) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return
        item_type = payload.get("type")
        identifier = payload.get("id")
        if not isinstance(identifier, str):
            return
        if item_type == "group":
            self.group_activated.emit(identifier)
        elif item_type == "absorption_line":
            self.line_activated.emit(identifier)

    def _on_context_menu_requested(self, point: QPoint) -> None:
        region_ids: list[str] = []
        line_ids: list[str] = []
        for item in self._tree.selectedItems():
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(payload, dict):
                continue
            item_type = payload.get("type")
            identifier = payload.get("id")
            if not isinstance(identifier, str):
                continue
            if item_type == "group":
                region_ids.append(identifier)
            elif item_type == "absorption_line":
                line_ids.append(identifier)
        self.context_menu_requested.emit(
            self._tree.viewport().mapToGlobal(point), region_ids, line_ids
        )

    def _rebuild_from_model(self, _component: ModelComponent) -> None:
        adapter = self._model_event_adapter
        if adapter is not None and adapter.applying_region_topology_change:
            return
        self.refresh()

    def _on_region_topology_changed(self, _event: RegionTopologyChanged) -> None:
        """Rebuild Overview projections after one committed topology change."""
        self.refresh()

    def _group_color_pixmap(self, group: _GroupEntry) -> QPixmap:
        size = 12
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        color_value = group.color or Colors.TEXT_PRIMARY
        color = QColor(color_value)
        pixmap.fill(color)
        return pixmap
