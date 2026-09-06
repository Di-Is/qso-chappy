"""Interactive review table and summary surface for Analysis Overview."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from chappy.core.analysis import AnalysisReadiness
from chappy.gui.modes.analysis.overview.summary_panel import AnalysisOverviewSummaryPanel
from chappy.gui.modes.analysis.overview.table_model import (
    FULL_COLUMNS,
    AnalysisReviewColumn,
    AnalysisReviewFilter,
    AnalysisReviewProxyModel,
    AnalysisReviewSort,
    AnalysisReviewSortDirection,
    AnalysisReviewTableModel,
    column_width_probe_texts,
)
from chappy.gui.theme import create_styled_menu

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PySide6.QtGui import QKeyEvent, QResizeEvent, QShowEvent

    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.common.analysis_navigation import AnalysisOverviewNavigationPort
    from chappy.presentation.analysis import AnalysisReviewRow, AnalysisReviewSummary


class _AnalysisReviewTableView(QTableView):
    """Table view that exposes Enter as open and Delete as delete intents."""

    open_requested = Signal()
    delete_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Convert Enter into open and Delete into delete intents."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_requested.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class AnalysisOverviewReviewWidget(QWidget):
    """Own model/proxy/view state while navigation stores only stable IDs."""

    region_selected = Signal(str)
    region_open_requested = Signal(str)
    region_delete_requested = Signal(str)
    structure_edit_requested = Signal(str)

    COMPACT_TABLE_WIDTH = 520
    COMPACT_TOTAL_WIDTH = 760
    MINIMUM_REVIEW_HEIGHT = 144
    MINIMUM_SUMMARY_WIDTH = 220
    MINIMUM_SPECTRUM_WIDTH = 240
    #: Extra pixels per fixed column for cell margins and the sort indicator.
    COLUMN_WIDTH_PADDING = 24
    #: Frame, padding, and drop-down arrow allowance for the readiness combo.
    READINESS_FILTER_CHROME_WIDTH = 48

    def __init__(
        self,
        navigation: AnalysisOverviewNavigationPort | None,
        parent: QWidget | None = None,
        *,
        summary_panel: AnalysisOverviewSummaryPanel | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("analysisOverviewReviewWidget")
        self.setMinimumHeight(self.MINIMUM_REVIEW_HEIGHT)
        self._navigation = navigation
        self._project: SpectroscopyProject | None = None
        self._restoring = False
        self._model = AnalysisReviewTableModel(self)
        self._proxy = AnalysisReviewProxyModel(self)
        self._proxy.setSourceModel(self._model)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        controls = QHBoxLayout()
        self._filter_edit = QLineEdit(self)
        self._filter_edit.setObjectName("analysisOverviewFilterEdit")
        self._filter_edit.setPlaceholderText(self.tr("Filter regions"))
        controls.addWidget(self._filter_edit, 1)
        self._readiness_filter = QComboBox(self)
        self._readiness_filter.setObjectName("analysisOverviewReadinessFilter")
        for text, value in (
            (self.tr("All"), "all"),
            (self.tr("Not analyzed"), AnalysisReadiness.NOT_ANALYZED.value),
            (self.tr("Stale"), AnalysisReadiness.STALE.value),
            (self.tr("Latest"), AnalysisReadiness.LATEST.value),
        ):
            self._readiness_filter.addItem(text, value)
        filter_metrics = self._readiness_filter.fontMetrics()
        longest_item_width = max(
            filter_metrics.horizontalAdvance(self._readiness_filter.itemText(index))
            for index in range(self._readiness_filter.count())
        )
        self._readiness_filter.setMinimumWidth(
            longest_item_width + self.READINESS_FILTER_CHROME_WIDTH
        )
        controls.addWidget(self._readiness_filter)
        root.addLayout(controls)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        self._table = _AnalysisReviewTableView(self)
        self._table.setObjectName("analysisOverviewReviewTable")
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._apply_column_policy()
        content.addWidget(self._table, 1)
        self._summary = summary_panel or AnalysisOverviewSummaryPanel(self)
        self._summary_embedded = summary_panel is None
        if self._summary_embedded:
            content.addWidget(self._summary)
        root.addLayout(content, 1)

        self._filter_edit.textChanged.connect(self._apply_filter_from_controls)
        self._readiness_filter.currentIndexChanged.connect(self._apply_filter_from_controls)
        self._table.selectionModel().selectionChanged.connect(self._handle_selection_changed)
        self._table.doubleClicked.connect(lambda _index: self._emit_open_selected())
        self._table.open_requested.connect(self._emit_open_selected)
        self._table.delete_requested.connect(self._emit_delete_selected)
        self._table.viewport().customContextMenuRequested.connect(self._show_row_context_menu)
        self._table.horizontalHeader().sortIndicatorChanged.connect(self._handle_sort_changed)
        self._table.horizontalHeader().sectionMoved.connect(self._persist_view_state)
        self._table.horizontalHeader().customContextMenuRequested.connect(self._show_column_menu)
        self._table.verticalScrollBar().valueChanged.connect(self._persist_view_state)
        self._summary.open_region_requested.connect(self.region_open_requested)
        self._summary.structure_edit_requested.connect(self.structure_edit_requested)
        self._summary.readiness_filter_requested.connect(self.set_readiness_filter)
        self._summary.first_region_requested.connect(self.select_first_region)

    @property
    def table_model(self) -> AnalysisReviewTableModel:
        """Return the incremental source model."""
        return self._model

    @property
    def proxy_model(self) -> AnalysisReviewProxyModel:
        """Return the typed filter/sort proxy."""
        return self._proxy

    @property
    def table_view(self) -> QTableView:
        """Return the table view for shell layout and focused tests."""
        return self._table

    @property
    def compact(self) -> bool:
        """Return whether the compact three-column projection is active."""
        return self._model.compact

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Replace the project reference without rendering navigation state."""
        self._project = project

    def sync_rows(self, rows: Sequence[AnalysisReviewRow], summary: AnalysisReviewSummary) -> None:
        """Apply incremental row changes and preserve selection by region ID."""
        selected_region_id = self.selected_region_id()
        self._model.sync_rows(rows)
        self._summary.render_summary(summary)
        target = selected_region_id
        if target is None and self._navigation is not None:
            target = self._navigation.state.overview_selection
        self._restore_selection(target)
        self._apply_return_filter_exception()

    def selected_region_id(self) -> str | None:
        """Return the stable identity selected through the proxy."""
        return self._proxy.region_id_for_index(self._table.currentIndex())

    def selected_row(self) -> AnalysisReviewRow | None:
        """Return the selected typed presentation row."""
        return self._proxy.row_for_index(self._table.currentIndex())

    def clear_selection(self) -> None:
        """Clear the current row without emitting an open intent."""
        self._restoring = True
        try:
            self._table.clearSelection()
            self._table.setCurrentIndex(QModelIndex())
            self._summary.render_selection(None, self._project)
        finally:
            self._restoring = False
        if self._navigation is not None:
            self._navigation.select_overview_region(None)

    def select_region(self, region_id: str | None) -> None:
        """Restore one row selection from a stable region identity."""
        self._restore_selection(region_id)

    def set_readiness_filter(self, value: str) -> None:
        """Switch the readiness combo to a filter value ("all" or a readiness)."""
        index = self._readiness_filter.findData(value)
        if index >= 0:
            self._readiness_filter.setCurrentIndex(index)

    def select_first_region(self) -> None:
        """Select the first visible row exactly like a user row click."""
        index = self._proxy.index(0, 0)
        if not index.isValid():
            return
        self._table.setCurrentIndex(index)
        self._table.selectRow(index.row())

    def focus_return_region(self, region_id: str) -> bool:
        """Focus a Detail-return row without changing the active filter."""
        self._proxy.set_filter_exception(None)
        if not self._proxy.index_for_region_id(region_id).isValid():
            self._proxy.set_filter_exception(region_id)
        index = self._proxy.index_for_region_id(region_id)
        if not index.isValid():
            return False
        self._restore_selection(region_id)
        self._table.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._table.setFocus()
        return True

    def restore_navigation_state(self) -> None:
        """Restore persisted view context without storing proxy indexes."""
        navigation = self._navigation
        if navigation is None:
            return
        state = navigation.state
        self._restoring = True
        try:
            self._filter_edit.setText(state.filter_text)
            filter_value = (
                state.filter_readiness[0].value if len(state.filter_readiness) == 1 else "all"
            )
            filter_index = self._readiness_filter.findData(filter_value)
            self._readiness_filter.setCurrentIndex(max(filter_index, 0))
            self._apply_column_state(state.visible_column_ids, state.column_order)
            sort_column = self._column_from_id(state.sort_column_id)
            direction = (
                AnalysisReviewSortDirection.ASCENDING
                if state.sort_ascending
                else AnalysisReviewSortDirection.DESCENDING
            )
            self._proxy.set_review_sort(AnalysisReviewSort(sort_column, direction))
            sort_index = self._model.column_index(sort_column)
            if sort_index is not None:
                order = (
                    Qt.SortOrder.AscendingOrder
                    if state.sort_ascending
                    else Qt.SortOrder.DescendingOrder
                )
                self._table.sortByColumn(sort_index, order)
            self._restore_selection(state.overview_selection)
            self._scroll_to_region(state.top_visible_region_id)
        finally:
            self._restoring = False
        self._apply_column_policy()
        self._apply_filter_from_controls()

    def update_compact_mode(self) -> None:
        """Use actual table viewport and summary widths for compact projection."""
        # The summary width matters only when it shares this widget's row;
        # subtracting an externally hosted summary would double-count it.
        compact = self._table.viewport().width() < self.COMPACT_TABLE_WIDTH or (
            self._summary_embedded
            and self.width() - self._summary.width() < self.COMPACT_TOTAL_WIDTH
        )
        selected = self.selected_region_id()
        compact_changed = compact != self._model.compact
        self._model.set_compact(compact)
        self._restore_selection(selected)
        if not compact and self._navigation is not None:
            state = self._navigation.state
            self._apply_column_state(state.visible_column_ids, state.column_order)
        if compact_changed:
            # set_compact() resets the model, which drops per-section modes
            # and widths, so the column policy must be applied again.
            self._apply_column_policy()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Re-evaluate compact layout from actual child widths."""
        super().resizeEvent(event)
        self.update_compact_mode()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Re-evaluate compact layout when the dock becomes visible.

        A hidden widget can be laid out to its final size without receiving
        a resize event, which would leave a stale compact projection active
        on a wide window until the next manual resize.
        """
        super().showEvent(event)
        self.update_compact_mode()
        # The receiver context drops the deferred call if the widget is
        # destroyed before the event loop runs it.
        QTimer.singleShot(0, self, self.update_compact_mode)

    def _apply_column_policy(self) -> None:
        """Apply the O(1) column sizing policy for the active projection.

        No column ever uses ResizeToContents, so 1000-row syncs cannot
        trigger row scans or width jitter. Bounded columns get one-time
        widths computed from their widest translated value or header text;
        REGION stretches because its labels are the only unbounded values.
        """
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setTextElideMode(Qt.TextElideMode.ElideRight)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        metrics = header.fontMetrics()
        for logical, column in enumerate(self._model.column_keys):
            if column is AnalysisReviewColumn.REGION:
                header.setSectionResizeMode(logical, QHeaderView.ResizeMode.Stretch)
                continue
            header.setSectionResizeMode(logical, QHeaderView.ResizeMode.Interactive)
            width = max(
                metrics.horizontalAdvance(text) for text in column_width_probe_texts(column)
            )
            self._table.setColumnWidth(logical, width + self.COLUMN_WIDTH_PADDING)

    def _apply_filter_from_controls(self) -> None:
        value = self._readiness_filter.currentData()
        readiness: frozenset[AnalysisReadiness] | None = None
        if isinstance(value, str) and value != "all":
            readiness = frozenset((AnalysisReadiness(value),))
        self._proxy.set_review_filter(
            AnalysisReviewFilter(query=self._filter_edit.text(), readiness=readiness)
        )
        if not self._restoring:
            self._persist_view_state()

    def _handle_selection_changed(self) -> None:
        if self._restoring:
            return
        region_id = self.selected_region_id()
        row = self.selected_row()
        self._summary.render_selection(row, self._project)
        if self._navigation is not None:
            self._navigation.select_overview_region(region_id)
        self._proxy.set_filter_exception(None)
        if region_id is not None:
            self.region_selected.emit(region_id)

    def _emit_open_selected(self) -> None:
        region_id = self.selected_region_id()
        if region_id is not None:
            self.region_open_requested.emit(region_id)

    def _emit_delete_selected(self) -> None:
        region_id = self.selected_region_id()
        if region_id is not None:
            self.region_delete_requested.emit(region_id)

    def _show_row_context_menu(self, position: QPoint) -> None:
        index = self._table.indexAt(position)
        region_id = self._proxy.region_id_for_index(index)
        if region_id is None:
            return
        self._table.selectRow(index.row())
        menu = self._build_row_context_menu(region_id)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _build_row_context_menu(self, region_id: str) -> QMenu:
        menu = create_styled_menu(self)
        menu.addAction(self.tr("Open region"), lambda: self.region_open_requested.emit(region_id))
        menu.addAction(
            self.tr("Delete region…"), lambda: self.region_delete_requested.emit(region_id)
        )
        return menu

    def _handle_sort_changed(self, logical_index: int, order: Qt.SortOrder) -> None:
        if not 0 <= logical_index < len(self._model.column_keys):
            return
        column = self._model.column_keys[logical_index]
        direction = (
            AnalysisReviewSortDirection.ASCENDING
            if order is Qt.SortOrder.AscendingOrder
            else AnalysisReviewSortDirection.DESCENDING
        )
        self._proxy.set_review_sort(AnalysisReviewSort(column, direction))
        if not self._restoring:
            self._persist_view_state()

    def _persist_view_state(self) -> None:
        navigation = self._navigation
        if navigation is None or self._restoring:
            return
        header = self._table.horizontalHeader()
        if self._model.compact:
            state = navigation.state
            column_order = state.column_order or tuple(column.value for column in FULL_COLUMNS)
            visible = state.visible_column_ids or tuple(column.value for column in FULL_COLUMNS)
        else:
            column_order = tuple(
                self._model.column_keys[header.logicalIndex(visual)].value
                for visual in range(header.count())
            )
            visible = tuple(
                column.value
                for logical, column in enumerate(self._model.column_keys)
                if not self._table.isColumnHidden(logical)
            )
        sort = self._proxy.review_sort
        navigation.update_overview_view(
            filter_text=self._filter_edit.text(),
            filter_readiness=tuple(
                sorted(self._proxy.review_filter.readiness or (), key=lambda item: item.value)
            ),
            sort_column_id=sort.column.value,
            sort_ascending=sort.direction is AnalysisReviewSortDirection.ASCENDING,
            visible_column_ids=visible,
            column_order=column_order,
            top_visible_region_id=self._top_visible_region_id(),
        )

    def _apply_column_state(
        self, visible_column_ids: tuple[str, ...], column_order: tuple[str, ...]
    ) -> None:
        if self._model.compact:
            return
        visible = (
            set(visible_column_ids)
            if visible_column_ids
            else {column.value for column in FULL_COLUMNS}
        )
        for logical, column in enumerate(self._model.column_keys):
            self._table.setColumnHidden(logical, column.value not in visible)
        header = self._table.horizontalHeader()
        ordered = [
            column
            for column_id in column_order
            if (column := self._column_from_id(column_id)) in self._model.column_keys
        ]
        for column in self._model.column_keys:
            if column not in ordered:
                ordered.append(column)
        for visual, column in enumerate(ordered):
            logical_index = self._model.column_index(column)
            if logical_index is not None:
                header.moveSection(header.visualIndex(logical_index), visual)

    def _show_column_menu(self, position: QPoint) -> None:
        if self._model.compact:
            return
        menu = QMenu(self)
        for logical, _column in enumerate(self._model.column_keys):
            action = menu.addAction(
                str(self._model.headerData(logical, Qt.Orientation.Horizontal))
            )
            action.setCheckable(True)
            action.setChecked(not self._table.isColumnHidden(logical))
            action.toggled.connect(
                lambda checked, index=logical: self._set_column_visible(index, checked)
            )
        menu.exec(self._table.horizontalHeader().mapToGlobal(position))

    def _set_column_visible(self, logical: int, visible: bool) -> None:
        self._table.setColumnHidden(logical, not visible)
        self._persist_view_state()

    def _restore_selection(self, region_id: str | None) -> None:
        self._restoring = True
        try:
            self._table.clearSelection()
            if region_id is None:
                self._table.setCurrentIndex(QModelIndex())
                self._summary.render_selection(None, self._project)
                return
            index = self._proxy.index_for_region_id(region_id)
            if not index.isValid():
                return
            self._table.setCurrentIndex(index)
            self._table.selectRow(index.row())
            self._summary.render_selection(self._proxy.row_for_index(index), self._project)
        finally:
            self._restoring = False

    def _apply_return_filter_exception(self) -> None:
        navigation = self._navigation
        if navigation is None:
            return
        region_id = navigation.state.focused_region_id
        self._proxy.set_filter_exception(None)
        if region_id is None:
            return
        if self._proxy.index_for_region_id(region_id).isValid():
            return
        self._proxy.set_filter_exception(region_id)
        self._restore_selection(region_id)

    def _scroll_to_region(self, region_id: str | None) -> None:
        if region_id is None:
            return
        index = self._proxy.index_for_region_id(region_id)
        if index.isValid():
            self._table.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtTop)

    def _top_visible_region_id(self) -> str | None:
        index = self._table.indexAt(self._table.viewport().rect().topLeft())
        return self._proxy.region_id_for_index(index)

    @staticmethod
    def _column_from_id(column_id: str | None) -> AnalysisReviewColumn:
        if column_id is None:
            return AnalysisReviewColumn.REGION
        try:
            return AnalysisReviewColumn(column_id)
        except ValueError:
            return AnalysisReviewColumn.REGION


__all__ = ["AnalysisOverviewReviewWidget"]
