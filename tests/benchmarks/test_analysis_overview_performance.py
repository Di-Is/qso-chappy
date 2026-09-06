"""Reproducible synthetic workload benchmarks for the Analysis Overview table.

Run without xdist so pytest-benchmark can collect timings::

    uv run pytest tests/benchmarks/test_analysis_overview_performance.py \
        -n 0 --benchmark-only --benchmark-columns=min,mean,max,rounds

The 10/100/1000 region inputs are synthetic target workloads. They are not
evidence of typical real-project sizes.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtTest import QSignalSpy
from pytest_benchmark.fixture import BenchmarkFixture

from chappy.core.analysis import AnalysisReadiness, FitSummary
from chappy.gui.modes.analysis.overview.table_model import (
    REGION_ID_ROLE,
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

_REGION_COUNTS = (10, 100, 1000)
_VISIBLE_ROW_COUNT = 20


def _synthetic_rows(region_count: int, *, revision: int = 0) -> tuple[AnalysisReviewRow, ...]:
    """Build deterministic synthetic rows for one target workload size."""
    return tuple(_synthetic_row(index, revision=revision) for index in range(region_count))


def _synthetic_row(index: int, *, revision: int) -> AnalysisReviewRow:
    region_id = f"region-{index:04d}"
    changed_suffix = f" revision-{revision}" if revision and index % 10 == 0 else ""
    region = AnalysisRegionDisplay(
        region_id, f"Region {index:04d} cohort-{index % 2}{changed_suffix}"
    )
    readiness = tuple(AnalysisReadiness)[index % len(AnalysisReadiness)]
    if readiness is AnalysisReadiness.NOT_ANALYZED:
        return AnalysisReviewRow(
            region,
            readiness,
            AnalysisFitResultDisplay(AnalysisFitResultKind.NOT_ANALYZED),
            AnalysisNextAction.ANALYZE,
        )
    if readiness is AnalysisReadiness.STALE:
        return AnalysisReviewRow(
            region,
            readiness,
            AnalysisFitResultDisplay(AnalysisFitResultKind.STALE),
            AnalysisNextAction.REANALYZE,
        )
    return AnalysisReviewRow(
        region,
        readiness,
        AnalysisFitResultDisplay(
            AnalysisFitResultKind.NUMERICAL, FitSummary(reduced_chi_squared=1.0 + index / 1000)
        ),
        AnalysisNextAction.OPEN_REGION,
    )


def _bench(benchmark: BenchmarkFixture, operation: Callable[[], object]) -> object:
    """Use bounded rounds so all workload sizes remain quick to rerun locally."""
    return benchmark.pedantic(operation, rounds=10, iterations=1, warmup_rounds=2)


def _proxy(rows: tuple[AnalysisReviewRow, ...]) -> AnalysisReviewProxyModel:
    source = AnalysisReviewTableModel()
    source.sync_rows(rows)
    proxy = AnalysisReviewProxyModel()
    proxy.setSourceModel(source)
    return proxy


def _visible_region_ids(proxy: AnalysisReviewProxyModel) -> tuple[str, ...]:
    return tuple(
        proxy.region_id_for_index(proxy.index(row, 0)) or "" for row in range(proxy.rowCount())
    )


@pytest.mark.benchmark(group="analysis_overview_row_generation")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_row_generation(benchmark: BenchmarkFixture, region_count: int) -> None:
    rows = _bench(benchmark, lambda: _synthetic_rows(region_count))

    assert isinstance(rows, tuple)
    assert len(rows) == region_count


@pytest.mark.benchmark(group="analysis_overview_initial_sync")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_initial_sync(benchmark: BenchmarkFixture, region_count: int) -> None:
    rows = _synthetic_rows(region_count)

    def initial_sync() -> AnalysisReviewTableModel:
        model = AnalysisReviewTableModel()
        model.sync_rows(rows)
        return model

    model = _bench(benchmark, initial_sync)

    assert isinstance(model, AnalysisReviewTableModel)
    assert model.rowCount() == region_count


@pytest.mark.benchmark(group="analysis_overview_filter")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_filter(benchmark: BenchmarkFixture, region_count: int) -> None:
    proxy = _proxy(_synthetic_rows(region_count))
    next_cohort = [0]

    def filter_rows() -> tuple[str, ...]:
        next_cohort[0] = 1 - next_cohort[0]
        proxy.set_review_filter(AnalysisReviewFilter(query=f"cohort-{next_cohort[0]}"))
        return _visible_region_ids(proxy)

    visible_ids = _bench(benchmark, filter_rows)

    assert isinstance(visible_ids, tuple)
    assert len(visible_ids) == region_count // 2


@pytest.mark.benchmark(group="analysis_overview_sort")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_sort(benchmark: BenchmarkFixture, region_count: int) -> None:
    proxy = _proxy(_synthetic_rows(region_count))
    descending = [False]

    def sort_rows() -> tuple[str, ...]:
        descending[0] = not descending[0]
        direction = (
            AnalysisReviewSortDirection.DESCENDING
            if descending[0]
            else AnalysisReviewSortDirection.ASCENDING
        )
        proxy.set_review_sort(AnalysisReviewSort(AnalysisReviewColumn.REGION, direction))
        return _visible_region_ids(proxy)

    visible_ids = _bench(benchmark, sort_rows)

    assert isinstance(visible_ids, tuple)
    assert len(visible_ids) == region_count


@pytest.mark.benchmark(group="analysis_overview_selection_lookup")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_selection_lookup(benchmark: BenchmarkFixture, region_count: int) -> None:
    proxy = _proxy(_synthetic_rows(region_count))
    target_region_id = f"region-{region_count - 1:04d}"

    index = _bench(benchmark, lambda: proxy.index_for_region_id(target_region_id))

    assert isinstance(index, QModelIndex)
    assert proxy.region_id_for_index(index) == target_region_id


@pytest.mark.benchmark(group="analysis_overview_incremental_update")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_incremental_update(benchmark: BenchmarkFixture, region_count: int) -> None:
    revisions = (_synthetic_rows(region_count), _synthetic_rows(region_count, revision=1))
    model = AnalysisReviewTableModel()
    model.sync_rows(revisions[0])
    next_revision = [0]

    def update_rows() -> tuple[AnalysisReviewRow, ...]:
        next_revision[0] = 1 - next_revision[0]
        incoming = revisions[next_revision[0]]
        model.sync_rows(incoming)
        return incoming

    incoming = _bench(benchmark, update_rows)

    assert isinstance(incoming, tuple)
    assert tuple(model.row_at(row) for row in range(model.rowCount())) == incoming


@pytest.mark.benchmark(group="analysis_overview_viewport_data")
@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_benchmark_viewport_data_materialization(
    benchmark: BenchmarkFixture, region_count: int
) -> None:
    """Measure display-data reads for a 20-row viewport as a paint equivalent."""
    proxy = _proxy(_synthetic_rows(region_count))
    visible_rows = min(region_count, _VISIBLE_ROW_COUNT)

    def materialize_viewport() -> tuple[object, ...]:
        return tuple(
            proxy.data(proxy.index(row, column))
            for row in range(visible_rows)
            for column in range(proxy.columnCount())
        )

    values = _bench(benchmark, materialize_viewport)

    assert isinstance(values, tuple)
    assert len(values) == visible_rows * proxy.columnCount()


@pytest.mark.parametrize("region_count", _REGION_COUNTS)
def test_incremental_update_preserves_selection_without_full_rebuild(region_count: int) -> None:
    """Keep results and ID selection stable while only changed rows are signalled."""
    original = _synthetic_rows(region_count)
    updated = _synthetic_rows(region_count, revision=1)
    source = AnalysisReviewTableModel()
    source.sync_rows(original)
    proxy = AnalysisReviewProxyModel()
    proxy.setSourceModel(source)
    proxy.set_review_filter(AnalysisReviewFilter(query="cohort-1"))
    proxy.set_review_sort(
        AnalysisReviewSort(AnalysisReviewColumn.REGION, AnalysisReviewSortDirection.DESCENDING)
    )
    selection = QItemSelectionModel(proxy)
    target_region_id = f"region-{region_count - 1:04d}"
    target = proxy.index_for_region_id(target_region_id)
    selection.setCurrentIndex(
        target,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    resets = QSignalSpy(source.modelReset)
    changes = QSignalSpy(source.dataChanged)

    source.sync_rows(updated)

    expected_ids = tuple(
        row.region.region_id
        for row in sorted(
            (row for row in updated if "cohort-1" in row.region.label),
            key=lambda row: (row.region.label.casefold(), row.region.region_id.casefold()),
            reverse=True,
        )
    )
    assert resets.count() == 0
    assert changes.count() == (region_count + 9) // 10
    assert tuple(source.row_at(row) for row in range(source.rowCount())) == updated
    assert _visible_region_ids(proxy) == expected_ids
    assert proxy.region_id_for_index(selection.currentIndex()) == target_region_id
