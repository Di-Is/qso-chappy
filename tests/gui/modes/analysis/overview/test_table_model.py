"""Tests for the typed Analysis Overview table and proxy models."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QPersistentModelIndex, QTranslator, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QSignalSpy

from chappy.core.analysis import AnalysisReadiness, FitSummary
from chappy.gui.modes.analysis.overview import table_model as table_model_module
from chappy.gui.modes.analysis.overview.table_model import (
    COMPACT_COLUMNS,
    FULL_COLUMNS,
    REGION_ID_ROLE,
    REVIEW_ROW_ROLE,
    AnalysisReviewColumn,
    AnalysisReviewFilter,
    AnalysisReviewProxyModel,
    AnalysisReviewSort,
    AnalysisReviewSortDirection,
    AnalysisReviewTableModel,
)
from chappy.presentation.analysis import (
    AnalysisFitResultDisplay,
    AnalysisFitResultKind,
    AnalysisNextAction,
    AnalysisRegionDisplay,
    AnalysisReviewRow,
)


def _row(
    region_id: str,
    readiness: AnalysisReadiness,
    *,
    label: str | None = None,
    reduced_chi_squared: float = 1.0,
) -> AnalysisReviewRow:
    fit_results = {
        AnalysisReadiness.NOT_ANALYZED: AnalysisFitResultDisplay(
            AnalysisFitResultKind.NOT_ANALYZED
        ),
        AnalysisReadiness.STALE: AnalysisFitResultDisplay(AnalysisFitResultKind.STALE),
        AnalysisReadiness.LATEST: AnalysisFitResultDisplay(
            AnalysisFitResultKind.NUMERICAL, FitSummary(reduced_chi_squared=reduced_chi_squared)
        ),
    }
    actions = {
        AnalysisReadiness.NOT_ANALYZED: AnalysisNextAction.ANALYZE,
        AnalysisReadiness.STALE: AnalysisNextAction.REANALYZE,
        AnalysisReadiness.LATEST: AnalysisNextAction.OPEN_REGION,
    }
    return AnalysisReviewRow(
        region=AnalysisRegionDisplay(region_id, label or region_id),
        analysis_status=readiness,
        fit_result=fit_results[readiness],
        next_action=actions[readiness],
    )


def _proxy_with_rows(*rows: AnalysisReviewRow) -> AnalysisReviewProxyModel:
    source = AnalysisReviewTableModel()
    source.sync_rows(rows)
    proxy = AnalysisReviewProxyModel()
    proxy.setSourceModel(source)
    return proxy


def _visible_ids(proxy: AnalysisReviewProxyModel) -> list[str]:
    return [
        proxy.region_id_for_index(proxy.index(row, 0)) or "" for row in range(proxy.rowCount())
    ]


@pytest.fixture()
def japanese_translator(qapp: QApplication) -> Iterator[None]:
    """Install the packaged Japanese catalog for translated model assertions."""
    del qapp
    translator = QTranslator()
    qm_path = Path(__file__).resolve().parents[5] / "src/chappy/i18n/qt/chappy_ja.qm"
    assert translator.load(str(qm_path))
    assert QCoreApplication.installTranslator(translator)
    try:
        yield
    finally:
        QCoreApplication.removeTranslator(translator)


def test_static_translation_source_maps_cover_every_typed_value() -> None:
    assert set(table_model_module._COLUMN_LABEL_SOURCES) == set(AnalysisReviewColumn)
    assert set(table_model_module._STATUS_LABEL_SOURCES) == set(AnalysisReadiness)
    assert set(table_model_module._FIT_RESULT_LABEL_SOURCES) == (
        set(AnalysisFitResultKind) - {AnalysisFitResultKind.NUMERICAL}
    )
    assert set(table_model_module._ACTION_LABEL_SOURCES) == set(AnalysisNextAction)


def test_japanese_catalog_translates_all_table_headers_and_typed_labels(
    japanese_translator: None,
) -> None:
    del japanese_translator
    model = AnalysisReviewTableModel()
    model.sync_rows(tuple(_row(readiness.value, readiness) for readiness in AnalysisReadiness))

    assert [model.headerData(column, Qt.Orientation.Horizontal) for column in range(4)] == [
        "領域",
        "解析状態",
        "フィット結果",
        "次の操作",
    ]
    assert [model.data(model.index(row, 1)) for row in range(3)] == [
        "未解析",
        "結果が古い",
        "最新",
    ]
    assert [model.data(model.index(row, 2)) for row in range(3)] == [
        "—",
        "結果が古い",
        "換算χ²: 1",
    ]
    assert [model.data(model.index(row, 3)) for row in range(3)] == [
        "解析",
        "再解析",
        "領域を開く",
    ]

    model.set_compact(True)

    assert [model.headerData(column, Qt.Orientation.Horizontal) for column in range(3)] == [
        "領域",
        "解析状態",
        "次の操作",
    ]
    assert model.data(model.index(1, 1)) == "結果が古い"


def test_japanese_catalog_covers_every_fit_result_and_action_mapping(
    japanese_translator: None,
) -> None:
    del japanese_translator
    numerical_rows = tuple(
        AnalysisReviewRow(
            region=AnalysisRegionDisplay(f"numerical-{index}", f"numerical-{index}"),
            analysis_status=AnalysisReadiness.LATEST,
            fit_result=AnalysisFitResultDisplay(AnalysisFitResultKind.NUMERICAL, summary),
            next_action=AnalysisNextAction.OPEN_REGION,
        )
        for index, summary in enumerate(
            (
                FitSummary(reduced_chi_squared=1.25),
                FitSummary(chi_squared=2.5),
                FitSummary(degrees_of_freedom=7),
            )
        )
    )
    fit_rows = {
        AnalysisFitResultKind.NOT_ANALYZED: _row("not-analyzed", AnalysisReadiness.NOT_ANALYZED),
        AnalysisFitResultKind.STALE: _row("stale", AnalysisReadiness.STALE),
        AnalysisFitResultKind.NUMERICAL: numerical_rows[0],
    }

    assert {kind: table_model_module._fit_result_label(row) for kind, row in fit_rows.items()} == {
        AnalysisFitResultKind.NOT_ANALYZED: "—",
        AnalysisFitResultKind.STALE: "結果が古い",
        AnalysisFitResultKind.NUMERICAL: "換算χ²: 1.25",
    }
    assert [table_model_module._fit_result_label(row) for row in numerical_rows] == [
        "換算χ²: 1.25",
        "χ²: 2.5",
        "フィット結果: 7",
    ]
    assert {action: table_model_module._action_label(action) for action in AnalysisNextAction} == {
        AnalysisNextAction.ANALYZE: "解析",
        AnalysisNextAction.REANALYZE: "再解析",
        AnalysisNextAction.OPEN_REGION: "領域を開く",
    }


def test_baseline_data_roles_and_compact_projection_are_semantic() -> None:
    row = _row("region-1", AnalysisReadiness.STALE, label="Region One")
    model = AnalysisReviewTableModel()
    model.sync_rows((row,))

    assert model.columnCount() == 4
    assert model.column_keys == FULL_COLUMNS
    assert model.column_index(AnalysisReviewColumn.FIT_RESULT) == 2
    assert model.data(model.index(0, 0), REGION_ID_ROLE) == "region-1"
    assert model.data(model.index(0, 3), REVIEW_ROW_ROLE) is row
    assert model.data(model.index(0, 0)) == "Region One"
    assert model.flags(model.index(0, 0)) == (
        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    )

    model.set_compact(True)

    assert model.compact
    assert model.columnCount() == 3
    assert model.column_keys == COMPACT_COLUMNS
    assert model.column_index(AnalysisReviewColumn.STATUS) == 1
    assert model.column_index(AnalysisReviewColumn.FIT_RESULT) is None
    assert "Result stale" in str(model.data(model.index(0, 1)))


def test_status_column_tooltip_is_empty() -> None:
    model = AnalysisReviewTableModel()
    model.sync_rows((_row("region-a", AnalysisReadiness.STALE),))

    status_index = model.index(0, model.column_index(AnalysisReviewColumn.STATUS) or 0)

    assert model.data(status_index, int(Qt.ItemDataRole.ToolTipRole)) is None


def test_normal_sync_uses_granular_signals_and_preserves_persistent_identity() -> None:
    model = AnalysisReviewTableModel()
    first = _row("region-a", AnalysisReadiness.NOT_ANALYZED, label="A")
    second = _row("region-b", AnalysisReadiness.STALE, label="B")
    model.sync_rows((first, second))
    persistent_second = QPersistentModelIndex(model.index(1, 0))
    resets = QSignalSpy(model.modelReset)
    inserts = QSignalSpy(model.rowsInserted)
    removes = QSignalSpy(model.rowsRemoved)
    moves = QSignalSpy(model.rowsMoved)
    changes = QSignalSpy(model.dataChanged)

    updated_second = _row("region-b", AnalysisReadiness.STALE, label="B updated")
    third = _row("region-c", AnalysisReadiness.LATEST, label="C")
    model.sync_rows((updated_second, third))

    assert resets.count() == 0
    assert removes.count() == 1
    assert inserts.count() == 1
    assert moves.count() == 0
    assert changes.count() == 1
    assert persistent_second.isValid()
    assert persistent_second.row() == 0
    assert model.data(persistent_second) == "B updated"
    assert model.row_for_region_id("region-b") is updated_second
    assert not model.index_for_region_id("region-a").isValid()


def test_sync_moves_existing_ids_without_reset() -> None:
    model = AnalysisReviewTableModel()
    first = _row("region-a", AnalysisReadiness.NOT_ANALYZED)
    second = _row("region-b", AnalysisReadiness.STALE)
    model.sync_rows((first, second))
    persistent_first = QPersistentModelIndex(model.index(0, 0))
    resets = QSignalSpy(model.modelReset)
    moves = QSignalSpy(model.rowsMoved)

    model.sync_rows((second, first))

    assert resets.count() == 0
    assert moves.count() == 1
    assert persistent_first.row() == 1
    assert model.data(persistent_first, REGION_ID_ROLE) == "region-a"


def test_sync_rejects_duplicate_stable_ids_before_mutation() -> None:
    original = _row("region-a", AnalysisReadiness.NOT_ANALYZED)
    model = AnalysisReviewTableModel()
    model.sync_rows((original,))

    with pytest.raises(ValueError, match="unique region IDs"):
        model.sync_rows((original, original))

    assert model.rowCount() == 1
    assert model.row_at(0) is original


def test_proxy_combines_typed_filter_criteria() -> None:
    proxy = _proxy_with_rows(
        _row("alpha", AnalysisReadiness.LATEST, label="Alpha field"),
        _row("beta", AnalysisReadiness.STALE, label="Beta field"),
        _row("gamma", AnalysisReadiness.NOT_ANALYZED, label="Gamma field"),
    )

    proxy.set_review_filter(
        AnalysisReviewFilter(
            query="  BETA ",
            readiness=frozenset((AnalysisReadiness.STALE, AnalysisReadiness.LATEST)),
        )
    )

    assert proxy.review_filter.query == "beta"
    assert _visible_ids(proxy) == ["beta"]


def test_filter_exception_does_not_mutate_filter_and_clears_on_filter_change() -> None:
    latest = _row("latest", AnalysisReadiness.LATEST)
    stale = _row("stale", AnalysisReadiness.STALE)
    proxy = _proxy_with_rows(latest, stale)
    stale_filter = AnalysisReviewFilter(readiness=frozenset((AnalysisReadiness.STALE,)))
    proxy.set_review_filter(stale_filter)
    assert _visible_ids(proxy) == ["stale"]

    proxy.set_filter_exception("latest")

    assert proxy.review_filter is stale_filter
    assert proxy.filter_exception_region_id == "latest"
    assert set(_visible_ids(proxy)) == {"latest", "stale"}
    assert proxy.index_for_region_id("latest").isValid()

    replacement_filter = AnalysisReviewFilter(
        readiness=frozenset((AnalysisReadiness.STALE, AnalysisReadiness.NOT_ANALYZED))
    )
    proxy.set_review_filter(replacement_filter)

    assert proxy.filter_exception_region_id is None
    assert _visible_ids(proxy) == ["stale"]


def test_filter_exception_rejects_empty_identity() -> None:
    proxy = AnalysisReviewProxyModel()

    with pytest.raises(ValueError, match="must not be empty"):
        proxy.set_filter_exception("")


@pytest.mark.parametrize(
    ("review_sort", "expected"),
    [
        (AnalysisReviewSort(AnalysisReviewColumn.STATUS), ["stale", "latest-high", "latest-low"]),
        (
            AnalysisReviewSort(AnalysisReviewColumn.FIT_RESULT),
            ["stale", "latest-low", "latest-high"],
        ),
        (
            AnalysisReviewSort(
                AnalysisReviewColumn.FIT_RESULT, AnalysisReviewSortDirection.DESCENDING
            ),
            ["latest-high", "latest-low", "stale"],
        ),
    ],
)
def test_proxy_applies_typed_semantic_sort(
    review_sort: AnalysisReviewSort, expected: list[str]
) -> None:
    proxy = _proxy_with_rows(
        _row("latest-high", AnalysisReadiness.LATEST, reduced_chi_squared=3.0),
        _row("stale", AnalysisReadiness.STALE),
        _row("latest-low", AnalysisReadiness.LATEST, reduced_chi_squared=0.5),
    )

    proxy.set_review_sort(review_sort)

    assert proxy.review_sort == review_sort
    assert _visible_ids(proxy) == expected


def test_proxy_fails_fast_for_wrong_source_model() -> None:
    proxy = AnalysisReviewProxyModel()

    with pytest.raises(TypeError, match="requires AnalysisReviewTableModel"):
        proxy.index_for_region_id("region-a")


def test_region_column_exposes_full_label_tooltip() -> None:
    model = AnalysisReviewTableModel()
    model.sync_rows(
        (_row("region-a", AnalysisReadiness.LATEST, label="A very long region label"),)
    )

    region_index = model.index(0, model.column_index(AnalysisReviewColumn.REGION) or 0)

    assert model.data(region_index, int(Qt.ItemDataRole.ToolTipRole)) == "A very long region label"


def test_column_width_probe_texts_bound_fixed_width_columns() -> None:
    for column in (
        AnalysisReviewColumn.STATUS,
        AnalysisReviewColumn.FIT_RESULT,
        AnalysisReviewColumn.NEXT_ACTION,
    ):
        texts = table_model_module.column_width_probe_texts(column)
        assert len(texts) > 1
        assert all(text for text in texts)

    region_texts = table_model_module.column_width_probe_texts(AnalysisReviewColumn.REGION)
    assert len(region_texts) == 1
