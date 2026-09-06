"""Typed table and proxy models for the Analysis Overview review rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, override

from PySide6.QtCore import (
    QT_TRANSLATE_NOOP,
    QAbstractTableModel,
    QCoreApplication,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)

from chappy.core.analysis import AnalysisReadiness
from chappy.gui.modes.common.analysis_navigation import ANALYSIS_OVERVIEW_FULL_COLUMNS
from chappy.gui.modes.common.analysis_navigation import (
    AnalysisOverviewColumnId as AnalysisReviewColumn,
)
from chappy.presentation.analysis import (
    AnalysisFitResultKind,
    AnalysisNextAction,
    AnalysisReviewRow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


REGION_ID_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1
REVIEW_ROW_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2

_TRANSLATION_CONTEXT = "AnalysisReviewTableModel"
_INVALID_INDEX = QModelIndex()
type ModelIndex = QModelIndex | QPersistentModelIndex


FULL_COLUMNS: Final = ANALYSIS_OVERVIEW_FULL_COLUMNS
COMPACT_COLUMNS: Final = (
    AnalysisReviewColumn.REGION,
    AnalysisReviewColumn.STATUS,
    AnalysisReviewColumn.NEXT_ACTION,
)

_COLUMN_LABEL_SOURCES: Final = {
    AnalysisReviewColumn.REGION: str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Region")),
    AnalysisReviewColumn.STATUS: str(
        QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Analysis status")
    ),
    AnalysisReviewColumn.FIT_RESULT: str(
        QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Fit result")
    ),
    AnalysisReviewColumn.NEXT_ACTION: str(
        QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Next action")
    ),
}
_STATUS_LABEL_SOURCES: Final = {
    AnalysisReadiness.NOT_ANALYZED: str(
        QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Not analyzed")
    ),
    AnalysisReadiness.STALE: str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Result stale")),
    AnalysisReadiness.LATEST: str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Latest")),
}
_FIT_RESULT_LABEL_SOURCES: Final = {
    AnalysisFitResultKind.NOT_ANALYZED: str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "—")),
    AnalysisFitResultKind.STALE: str(
        QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Result stale")
    ),
}
#: {value} is a locale-neutral formatted reduced chi-squared value.
_REDUCED_CHI_SQUARED_SOURCE: Final = str(
    QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Reduced χ²: {value}")
)
#: {value} is a locale-neutral formatted chi-squared value.
_CHI_SQUARED_SOURCE: Final = str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "χ²: {value}"))
#: {value} is a locale-neutral formatted fit-summary count.
_FIT_RESULT_VALUE_SOURCE: Final = str(
    QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Fit result: {value}")
)
_ACTION_LABEL_SOURCES: Final = {
    AnalysisNextAction.ANALYZE: str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Analyze")),
    AnalysisNextAction.REANALYZE: str(QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Reanalyze")),
    AnalysisNextAction.OPEN_REGION: str(
        QT_TRANSLATE_NOOP("AnalysisReviewTableModel", "Open region")
    ),
}


@dataclass(frozen=True, slots=True)
class AnalysisReviewFilter:
    """Typed filter applied by the Overview proxy model."""

    query: str = ""
    readiness: frozenset[AnalysisReadiness] | None = None

    def __post_init__(self) -> None:
        """Normalize user-entered query text without losing typed criteria."""
        object.__setattr__(self, "query", self.query.strip().casefold())


class AnalysisReviewSortDirection(StrEnum):
    """Qt-independent persisted direction for a review sort."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


@dataclass(frozen=True, slots=True)
class AnalysisReviewSort:
    """Typed semantic sort independent of logical/visual column positions."""

    column: AnalysisReviewColumn = AnalysisReviewColumn.REGION
    direction: AnalysisReviewSortDirection = AnalysisReviewSortDirection.ASCENDING


class AnalysisReviewTableModel(QAbstractTableModel):
    """Four-column review model with an explicit three-column compact layout."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[AnalysisReviewRow] = []
        self._columns: tuple[AnalysisReviewColumn, ...] = FULL_COLUMNS

    @property
    def column_keys(self) -> tuple[AnalysisReviewColumn, ...]:
        """Return stable logical keys for view-owned visibility and ordering."""
        return self._columns

    @property
    def compact(self) -> bool:
        """Return whether the three-column compact projection is active."""
        return self._columns == COMPACT_COLUMNS

    def set_compact(self, compact: bool) -> None:
        """Switch between the baseline five columns and compact three columns."""
        columns = COMPACT_COLUMNS if compact else FULL_COLUMNS
        if columns == self._columns:
            return
        self.beginResetModel()
        self._columns = columns
        self.endResetModel()

    def column_index(self, key: AnalysisReviewColumn) -> int | None:
        """Resolve a semantic key in the current layout for a table view."""
        try:
            return self._columns.index(key)
        except ValueError:
            return None

    @override
    def rowCount(self, parent: ModelIndex = _INVALID_INDEX) -> int:
        """Return the number of top-level review rows."""
        return 0 if parent.isValid() else len(self._rows)

    @override
    def columnCount(self, parent: ModelIndex = _INVALID_INDEX) -> int:
        """Return the number of columns in the active projection."""
        return 0 if parent.isValid() else len(self._columns)

    @override
    def data(self, index: ModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        """Return translated display text or stable typed role data."""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        if not 0 <= index.column() < len(self._columns):
            return None
        row = self._rows[index.row()]
        if role == REGION_ID_ROLE:
            return row.region.region_id
        if role == REVIEW_ROW_ROLE:
            return row
        if role == int(Qt.ItemDataRole.DisplayRole):
            return _display_value(row, self._columns[index.column()])
        if role == int(Qt.ItemDataRole.ToolTipRole):
            return _tooltip_value(row, self._columns[index.column()])
        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        """Return translated horizontal headers for the active projection."""
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation is Qt.Orientation.Vertical:
            return section + 1
        if not 0 <= section < len(self._columns):
            return None
        return _column_label(self._columns[section])

    @override
    def flags(self, index: ModelIndex) -> Qt.ItemFlag:
        """Expose review rows as selectable read-only data."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def row_at(self, source_row: int) -> AnalysisReviewRow:
        """Return a typed row, failing fast for an invalid source row."""
        return self._rows[source_row]

    def row_for_region_id(self, region_id: str) -> AnalysisReviewRow | None:
        """Resolve a row by stable identity rather than a stored row number."""
        source_row = self._source_row_for_region_id(region_id)
        return None if source_row is None else self._rows[source_row]

    def index_for_region_id(self, region_id: str, column: int = 0) -> QModelIndex:
        """Resolve a current source index from a stable region identity."""
        source_row = self._source_row_for_region_id(region_id)
        if source_row is None or not 0 <= column < len(self._columns):
            return QModelIndex()
        return self.index(source_row, column)

    def sync_rows(self, rows: Sequence[AnalysisReviewRow]) -> None:
        """Synchronize by ID using granular signals; never reset normal refreshes."""
        incoming = tuple(rows)
        incoming_ids = tuple(row.region.region_id for row in incoming)
        if len(set(incoming_ids)) != len(incoming_ids):
            msg = "Analysis review rows must have unique region IDs."
            raise ValueError(msg)
        incoming_by_id = {row.region.region_id: row for row in incoming}
        incoming_id_set = frozenset(incoming_ids)

        for source_row in range(len(self._rows) - 1, -1, -1):
            if self._rows[source_row].region.region_id in incoming_id_set:
                continue
            self.beginRemoveRows(QModelIndex(), source_row, source_row)
            del self._rows[source_row]
            self.endRemoveRows()

        for target_row, region_id in enumerate(incoming_ids):
            current_row = self._source_row_for_region_id(region_id)
            if current_row is None:
                self.beginInsertRows(QModelIndex(), target_row, target_row)
                self._rows.insert(target_row, incoming_by_id[region_id])
                self.endInsertRows()
                continue
            if current_row != target_row:
                destination = target_row if current_row > target_row else target_row + 1
                self.beginMoveRows(
                    QModelIndex(), current_row, current_row, QModelIndex(), destination
                )
                moved = self._rows.pop(current_row)
                self._rows.insert(target_row, moved)
                self.endMoveRows()

            replacement = incoming_by_id[region_id]
            if self._rows[target_row] == replacement:
                continue
            self._rows[target_row] = replacement
            first = self.index(target_row, 0)
            last = self.index(target_row, len(self._columns) - 1)
            self.dataChanged.emit(
                first,
                last,
                [
                    int(Qt.ItemDataRole.DisplayRole),
                    int(Qt.ItemDataRole.ToolTipRole),
                    REGION_ID_ROLE,
                    REVIEW_ROW_ROLE,
                ],
            )

    def _source_row_for_region_id(self, region_id: str) -> int | None:
        for source_row, row in enumerate(self._rows):
            if row.region.region_id == region_id:
                return source_row
        return None


class AnalysisReviewProxyModel(QSortFilterProxyModel):
    """Typed filtering/sorting with one temporary filter-exception region."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._review_filter = AnalysisReviewFilter()
        self._review_sort = AnalysisReviewSort()
        self._filter_exception_region_id: str | None = None
        self.setDynamicSortFilter(True)

    @property
    def review_filter(self) -> AnalysisReviewFilter:
        """Return the current immutable filter."""
        return self._review_filter

    @property
    def review_sort(self) -> AnalysisReviewSort:
        """Return the current immutable semantic sort."""
        return self._review_sort

    @property
    def filter_exception_region_id(self) -> str | None:
        """Return the region temporarily visible outside the active filter."""
        return self._filter_exception_region_id

    def set_review_filter(self, review_filter: AnalysisReviewFilter) -> None:
        """Apply a typed filter and clear any navigation-only exception."""
        if review_filter == self._review_filter and self._filter_exception_region_id is None:
            return
        self.beginFilterChange()
        self._review_filter = review_filter
        self._filter_exception_region_id = None
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_filter_exception(self, region_id: str | None) -> None:
        """Temporarily include one region without changing the persisted filter."""
        if region_id == "":
            msg = "A filter-exception region ID must not be empty."
            raise ValueError(msg)
        if region_id == self._filter_exception_region_id:
            return
        self.beginFilterChange()
        self._filter_exception_region_id = region_id
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_review_sort(self, review_sort: AnalysisReviewSort) -> None:
        """Apply a typed semantic sort without exposing logical column indexes."""
        self._review_sort = review_sort
        order = (
            Qt.SortOrder.AscendingOrder
            if review_sort.direction is AnalysisReviewSortDirection.ASCENDING
            else Qt.SortOrder.DescendingOrder
        )
        self.invalidate()
        self.sort(0, order)

    def row_for_index(self, proxy_index: QModelIndex) -> AnalysisReviewRow | None:
        """Resolve the typed source DTO for a proxy index."""
        if not proxy_index.isValid():
            return None
        value = self.data(proxy_index, REVIEW_ROW_ROLE)
        if not isinstance(value, AnalysisReviewRow):
            msg = "Analysis review proxy requires AnalysisReviewRow source role data."
            raise TypeError(msg)
        return value

    def region_id_for_index(self, proxy_index: QModelIndex) -> str | None:
        """Resolve stable identity for selection/navigation state."""
        if not proxy_index.isValid():
            return None
        value = self.data(proxy_index, REGION_ID_ROLE)
        if not isinstance(value, str) or not value:
            msg = "Analysis review proxy requires a non-empty region ID source role."
            raise TypeError(msg)
        return value

    def index_for_region_id(self, region_id: str, column: int = 0) -> QModelIndex:
        """Resolve the current proxy index from a stable region identity."""
        source = self.sourceModel()
        if not isinstance(source, AnalysisReviewTableModel):
            msg = "AnalysisReviewProxyModel requires AnalysisReviewTableModel as its source."
            raise TypeError(msg)
        return self.mapFromSource(source.index_for_region_id(region_id, column))

    @override
    def filterAcceptsRow(self, source_row: int, source_parent: ModelIndex) -> bool:
        """Apply all typed criteria, excepting the current return target."""
        row = self._source_review_row(source_row, source_parent)
        if row.region.region_id == self._filter_exception_region_id:
            return True
        review_filter = self._review_filter
        if (
            review_filter.readiness is not None
            and row.analysis_status not in review_filter.readiness
        ):
            return False
        return not review_filter.query or review_filter.query in _search_text(row)

    @override
    def lessThan(self, left: ModelIndex, right: ModelIndex) -> bool:
        """Compare typed DTO values using the persisted semantic column key."""
        left_row = self._source_review_row(left.row(), left.parent())
        right_row = self._source_review_row(right.row(), right.parent())
        column = self._review_sort.column
        return _sort_key(left_row, column) < _sort_key(right_row, column)

    def _source_review_row(self, source_row: int, source_parent: ModelIndex) -> AnalysisReviewRow:
        source = self.sourceModel()
        if not isinstance(source, AnalysisReviewTableModel):
            msg = "AnalysisReviewProxyModel requires AnalysisReviewTableModel as its source."
            raise TypeError(msg)
        if source_parent.isValid():
            msg = "Analysis review rows must be top-level table rows."
            raise ValueError(msg)
        return source.row_at(source_row)


def _tr(source: str) -> str:
    return QCoreApplication.translate(_TRANSLATION_CONTEXT, source)


def _column_label(column: AnalysisReviewColumn) -> str:
    return _tr(_COLUMN_LABEL_SOURCES[column])


def _status_label(readiness: AnalysisReadiness) -> str:
    return _tr(_STATUS_LABEL_SOURCES[readiness])


def _fit_result_label(row: AnalysisReviewRow) -> str:
    result = row.fit_result
    if result.kind is not AnalysisFitResultKind.NUMERICAL:
        return _tr(_FIT_RESULT_LABEL_SOURCES[result.kind])
    summary = result.summary
    if summary is None:
        msg = "A numerical review result requires a fit summary."
        raise RuntimeError(msg)
    if summary.reduced_chi_squared is not None:
        #: {value} is a locale-neutral formatted reduced chi-squared value.
        return _tr(_REDUCED_CHI_SQUARED_SOURCE).format(value=f"{summary.reduced_chi_squared:g}")
    if summary.chi_squared is not None:
        #: {value} is a locale-neutral formatted chi-squared value.
        return _tr(_CHI_SQUARED_SOURCE).format(value=f"{summary.chi_squared:g}")
    values = (summary.degrees_of_freedom, summary.n_parameters, summary.n_function_evaluations)
    value = next(value for value in values if value is not None)
    #: {value} is a locale-neutral formatted fit-summary count.
    return _tr(_FIT_RESULT_VALUE_SOURCE).format(value=f"{value:g}")


def _action_label(action: AnalysisNextAction) -> str:
    return _tr(_ACTION_LABEL_SOURCES[action])


def _display_value(row: AnalysisReviewRow, column: AnalysisReviewColumn) -> str:
    if column is AnalysisReviewColumn.REGION:
        return row.region.label
    if column is AnalysisReviewColumn.STATUS:
        return _status_label(row.analysis_status)
    if column is AnalysisReviewColumn.FIT_RESULT:
        return _fit_result_label(row)
    return _action_label(row.next_action)


def _tooltip_value(row: AnalysisReviewRow, column: AnalysisReviewColumn) -> str | None:
    if column is AnalysisReviewColumn.REGION:
        return row.region.label
    return None


#: Locale-neutral sample bounding the widest formatted fit-result number.
_FIT_RESULT_WIDTH_SAMPLE: Final = "8888.8888"


def column_width_probe_texts(column: AnalysisReviewColumn) -> tuple[str, ...]:
    """Return translated texts bounding the widest cell of a fixed-width column.

    Covers the header label plus the bounded value sets of STATUS, FIT_RESULT,
    and NEXT_ACTION so views can compute one-time column widths without any
    O(rows) content scan. Unbounded columns return the header label only.
    """
    texts = [_column_label(column)]
    if column is AnalysisReviewColumn.STATUS:
        texts.extend(_tr(source) for source in _STATUS_LABEL_SOURCES.values())
    elif column is AnalysisReviewColumn.FIT_RESULT:
        texts.extend(_tr(source) for source in _FIT_RESULT_LABEL_SOURCES.values())
        texts.extend(
            _tr(template).format(value=_FIT_RESULT_WIDTH_SAMPLE)
            for template in (
                _REDUCED_CHI_SQUARED_SOURCE,
                _CHI_SQUARED_SOURCE,
                _FIT_RESULT_VALUE_SOURCE,
            )
        )
    elif column is AnalysisReviewColumn.NEXT_ACTION:
        texts.extend(_tr(source) for source in _ACTION_LABEL_SOURCES.values())
    return tuple(texts)


def _search_text(row: AnalysisReviewRow) -> str:
    values = (
        row.region.region_id,
        row.region.label,
        row.analysis_status.value,
        row.fit_result.kind.value,
        row.next_action.value,
    )
    return "\n".join(values).casefold()


def _sort_key(row: AnalysisReviewRow, column: AnalysisReviewColumn) -> tuple[object, ...]:
    region_tiebreaker = row.region.region_id.casefold()
    if column is AnalysisReviewColumn.REGION:
        return (row.region.label.casefold(), region_tiebreaker)
    readiness_rank = {
        AnalysisReadiness.NOT_ANALYZED: 0,
        AnalysisReadiness.STALE: 1,
        AnalysisReadiness.LATEST: 2,
    }
    if column is AnalysisReviewColumn.STATUS:
        return (readiness_rank[row.analysis_status], region_tiebreaker)
    if column is AnalysisReviewColumn.FIT_RESULT:
        result = row.fit_result
        kind_rank = {
            AnalysisFitResultKind.NOT_ANALYZED: 0,
            AnalysisFitResultKind.STALE: 1,
            AnalysisFitResultKind.NUMERICAL: 2,
        }
        numerical_value = float("-inf")
        if result.summary is not None:
            evidence = (
                result.summary.reduced_chi_squared,
                result.summary.chi_squared,
                result.summary.degrees_of_freedom,
                result.summary.n_parameters,
                result.summary.n_function_evaluations,
            )
            numerical_value = float(next(value for value in evidence if value is not None))
        return (kind_rank[result.kind], numerical_value, region_tiebreaker)
    return (row.next_action.value, region_tiebreaker)


__all__ = [
    "COMPACT_COLUMNS",
    "FULL_COLUMNS",
    "REGION_ID_ROLE",
    "REVIEW_ROW_ROLE",
    "AnalysisReviewColumn",
    "AnalysisReviewFilter",
    "AnalysisReviewProxyModel",
    "AnalysisReviewSort",
    "AnalysisReviewSortDirection",
    "AnalysisReviewTableModel",
    "column_width_probe_texts",
]
