"""Interaction and layout tests for the Accepted Analysis Overview review widget."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QComboBox, QHeaderView, QLineEdit, QPushButton

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisReadiness, FitSummary
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from chappy.gui.modes.analysis.overview.review_controller import AnalysisOverviewReviewController
from chappy.gui.modes.analysis.overview.review_widget import AnalysisOverviewReviewWidget
from chappy.gui.modes.analysis.overview.summary_panel import AnalysisOverviewSummaryPanel
from chappy.gui.modes.analysis.overview.table_model import (
    AnalysisReviewColumn,
    column_width_probe_texts,
)
from chappy.gui.modes.common.analysis_navigation import AnalysisNavigationState
from chappy.presentation.analysis import (
    AnalysisFitResultDisplay,
    AnalysisFitResultKind,
    AnalysisNextAction,
    AnalysisRegionDisplay,
    AnalysisReviewPresenter,
    AnalysisReviewRow,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


class _Navigation:
    """In-memory Overview navigation port retaining only IDs and semantic keys."""

    def __init__(self, state: AnalysisNavigationState = AnalysisNavigationState()) -> None:
        self.state = state
        self.update_count = 0

    def select_overview_region(self, region_id: str | None) -> bool:
        self.state = replace(self.state, overview_selection=region_id)
        return True

    def update_overview_view(
        self,
        *,
        filter_text: str,
        filter_readiness: tuple[AnalysisReadiness, ...],
        sort_column_id: str | None,
        sort_ascending: bool,
        visible_column_ids: tuple[str, ...],
        column_order: tuple[str, ...],
        top_visible_region_id: str | None,
    ) -> None:
        self.update_count += 1
        self.state = replace(
            self.state,
            filter_text=filter_text,
            filter_readiness=filter_readiness,
            sort_column_id=sort_column_id,
            sort_ascending=sort_ascending,
            visible_column_ids=visible_column_ids,
            column_order=column_order,
            top_visible_region_id=top_visible_region_id,
        )

    def update_structure_selection(
        self, *, region_ids: tuple[str, ...], line_ids: tuple[str, ...]
    ) -> None:
        """Retain session-only structure IDs for protocol completeness."""
        _ = region_ids, line_ids


class _RecordingSummaryPanel(AnalysisOverviewSummaryPanel):
    """Record selection/project pairs rendered by the real review widget."""

    def __init__(self) -> None:
        self.rendered_selections: list[
            tuple[AnalysisReviewRow | None, SpectroscopyProject | None]
        ] = []
        super().__init__()

    def render_selection(
        self, row: AnalysisReviewRow | None, project: SpectroscopyProject | None
    ) -> None:
        """Record and render a selected row with its project."""
        self.rendered_selections.append((row, project))
        super().render_selection(row, project)


def _row(region_id: str, readiness: AnalysisReadiness, label: str) -> AnalysisReviewRow:
    fit_results = {
        AnalysisReadiness.NOT_ANALYZED: AnalysisFitResultDisplay(
            AnalysisFitResultKind.NOT_ANALYZED
        ),
        AnalysisReadiness.STALE: AnalysisFitResultDisplay(AnalysisFitResultKind.STALE),
        AnalysisReadiness.LATEST: AnalysisFitResultDisplay(
            AnalysisFitResultKind.NUMERICAL, FitSummary(reduced_chi_squared=1.0)
        ),
    }
    actions = {
        AnalysisReadiness.NOT_ANALYZED: AnalysisNextAction.ANALYZE,
        AnalysisReadiness.STALE: AnalysisNextAction.REANALYZE,
        AnalysisReadiness.LATEST: AnalysisNextAction.OPEN_REGION,
    }
    return AnalysisReviewRow(
        region=AnalysisRegionDisplay(region_id, label),
        analysis_status=readiness,
        fit_result=fit_results[readiness],
        next_action=actions[readiness],
    )


def _sync(widget: AnalysisOverviewReviewWidget, rows: tuple[AnalysisReviewRow, ...]) -> None:
    widget.sync_rows(rows, AnalysisReviewPresenter().build_summary(rows))


def _project_with_region(region_id: str) -> SpectroscopyProject:
    project = SpectroscopyProject()
    line_id = f"line-{region_id}"
    project.absorption_lines[line_id] = AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=1215.67,
        center_z=2.0,
        window_kms=150.0,
        multiplet_label="H I",
        transition_name="Lyα",
        oscillator_strength=0.4164,
        gamma_value=6.265e8,
        region_id=region_id,
    )
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=[line_id]
    )
    return project


def test_project_switch_never_renders_a_row_from_another_project(qtbot: QtBot) -> None:
    """Project replacement synchronizes new rows before restoring selection."""
    project_a = _project_with_region("region-a")
    project_b = _project_with_region("region-b")
    current_project = [project_a]
    navigation = _Navigation(AnalysisNavigationState(overview_selection="region-a"))
    summary = _RecordingSummaryPanel()
    review = AnalysisOverviewReviewWidget(navigation, summary_panel=summary)
    panel = StructureSidePanel(navigation=navigation, review=review, embed_review=False)
    controller = AnalysisOverviewReviewController(
        view=panel, project_provider=lambda: current_project[0], parent=panel
    )
    panel.review_refresh_requested.connect(controller.refresh)
    qtbot.addWidget(summary)
    qtbot.addWidget(panel)

    panel.set_project(project_a)
    assert review.selected_region_id() == "region-a"

    current_project[0] = project_b
    panel.set_project(project_b)

    assert summary.rendered_selections
    assert all(
        row is None or (project is not None and row.region.region_id in project.absorption_regions)
        for row, project in summary.rendered_selections
    )


def test_row_selection_is_id_based_and_does_not_open_detail(qtbot: QtBot) -> None:
    """Selection updates navigation while only Enter/double-click/button open Detail."""
    navigation = _Navigation()
    widget = AnalysisOverviewReviewWidget(navigation)
    qtbot.addWidget(widget)
    _sync(widget, (_row("region-1", AnalysisReadiness.STALE, "Region 1"),))
    opened = QSignalSpy(widget.region_open_requested)

    widget.table_view.selectRow(0)
    QApplication.processEvents()

    assert navigation.state.overview_selection == "region-1"
    assert opened.count() == 0

    qtbot.keyClick(widget.table_view, Qt.Key.Key_Return)
    assert opened.count() == 1
    widget.table_view.doubleClicked.emit(widget.table_view.currentIndex())
    assert opened.count() == 2
    button = widget.findChild(QPushButton, "analysisOverviewOpenRegionButton")
    assert button is not None
    button.click()
    assert opened.count() == 3


def test_delete_key_emits_region_delete_requested_for_selection_only(qtbot: QtBot) -> None:
    """Delete emits the region delete intent only when one row is selected."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    _sync(widget, (_row("region-1", AnalysisReadiness.STALE, "Region 1"),))
    deleted = QSignalSpy(widget.region_delete_requested)

    qtbot.keyClick(widget.table_view, Qt.Key.Key_Delete)
    assert deleted.count() == 0

    widget.table_view.selectRow(0)
    QApplication.processEvents()
    qtbot.keyClick(widget.table_view, Qt.Key.Key_Delete)
    assert deleted.count() == 1
    assert deleted.at(0)[0] == "region-1"


def test_row_context_menu_offers_open_and_delete(qtbot: QtBot) -> None:
    """The row context menu exposes open and delete intents for the row region."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    _sync(widget, (_row("region-1", AnalysisReadiness.STALE, "Region 1"),))

    menu = widget._build_row_context_menu("region-1")
    assert [action.text() for action in menu.actions()] == ["Open region", "Delete region…"]

    opened = QSignalSpy(widget.region_open_requested)
    deleted = QSignalSpy(widget.region_delete_requested)
    menu.actions()[0].trigger()
    menu.actions()[1].trigger()
    assert opened.count() == 1
    assert opened.at(0)[0] == "region-1"
    assert deleted.count() == 1
    assert deleted.at(0)[0] == "region-1"


def test_filter_exception_shows_return_region_without_changing_filter(qtbot: QtBot) -> None:
    """A Detail return target is temporarily visible outside the persisted filter."""
    navigation = _Navigation(
        AnalysisNavigationState(
            focused_region_id="region-return",
            overview_selection="region-return",
            filter_text="other",
        )
    )
    widget = AnalysisOverviewReviewWidget(navigation)
    qtbot.addWidget(widget)
    widget.restore_navigation_state()
    _sync(
        widget,
        (
            _row("region-return", AnalysisReadiness.LATEST, "Return target"),
            _row("region-other", AnalysisReadiness.LATEST, "Other"),
        ),
    )

    assert widget.proxy_model.rowCount() == 2
    assert widget.proxy_model.filter_exception_region_id == "region-return"
    assert navigation.state.filter_text == "other"

    filter_edit = widget.findChild(QLineEdit, "analysisOverviewFilterEdit")
    assert filter_edit is not None
    filter_edit.setText("other updated")
    assert widget.proxy_model.filter_exception_region_id is None


def test_detail_return_focuses_exception_row_without_changing_filter(qtbot: QtBot) -> None:
    """Returning from Detail focuses its proxy row even when the filter excludes it."""
    navigation = _Navigation(AnalysisNavigationState(filter_text="other"))
    widget = AnalysisOverviewReviewWidget(navigation)
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()
    widget.restore_navigation_state()
    _sync(
        widget,
        (
            _row("region-return", AnalysisReadiness.LATEST, "Return target"),
            _row("region-other", AnalysisReadiness.LATEST, "Other"),
        ),
    )

    assert widget.focus_return_region("region-return") is True

    assert widget.selected_region_id() == "region-return"
    assert widget.table_view.hasFocus()
    assert widget.proxy_model.filter_exception_region_id == "region-return"
    assert navigation.state.filter_text == "other"


def test_compact_projection_uses_viewport_and_summary_width(qtbot: QtBot) -> None:
    """Small actual content widths select three columns and wide widths restore five."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    QApplication.processEvents()
    widget.update_compact_mode()
    assert widget.compact
    assert widget.table_model.columnCount() == 3

    widget.resize(1200, 400)
    QApplication.processEvents()
    widget.update_compact_mode()
    assert not widget.compact
    assert widget.table_model.columnCount() == 4


def test_compact_projection_ignores_externally_hosted_summary_width(qtbot: QtBot) -> None:
    """A summary hosted in the side panel must not shrink the width budget.

    Regression: subtracting the external summary width pushed a ~990px wide
    review pane into the 3-column projection on wide production windows.
    """
    summary = AnalysisOverviewSummaryPanel()
    qtbot.addWidget(summary)
    summary.resize(540, 400)
    summary.show()
    widget = AnalysisOverviewReviewWidget(_Navigation(), summary_panel=summary)
    qtbot.addWidget(widget)
    widget.resize(990, 400)
    widget.show()
    QApplication.processEvents()

    widget.update_compact_mode()

    assert not widget.compact
    assert widget.table_model.columnCount() == 4


def test_overview_minimum_contract_preserves_review_and_spectrum_budget(qtbot: QtBot) -> None:
    """The 800x600 baseline leaves the required spectrum and review content budgets."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    assert widget.minimumHeight() == 144
    assert widget.MINIMUM_SUMMARY_WIDTH == 220
    assert 800 - widget.MINIMUM_SUMMARY_WIDTH >= widget.MINIMUM_SPECTRUM_WIDTH


def test_full_projection_column_policy_is_fixed_plus_single_stretch(qtbot: QtBot) -> None:
    """Full projection uses bounded fixed widths and stretches only REGION."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    widget.resize(1200, 400)
    widget.show()
    QApplication.processEvents()
    widget.update_compact_mode()
    assert not widget.compact

    header = widget.table_view.horizontalHeader()
    assert not header.stretchLastSection()
    assert header.textElideMode() == Qt.TextElideMode.ElideRight
    for logical, column in enumerate(widget.table_model.column_keys):
        mode = header.sectionResizeMode(logical)
        assert mode != QHeaderView.ResizeMode.ResizeToContents
        if column is AnalysisReviewColumn.REGION:
            assert mode == QHeaderView.ResizeMode.Stretch
        else:
            assert mode == QHeaderView.ResizeMode.Interactive

    metrics = header.fontMetrics()
    for column in (
        AnalysisReviewColumn.STATUS,
        AnalysisReviewColumn.FIT_RESULT,
        AnalysisReviewColumn.NEXT_ACTION,
    ):
        logical = widget.table_model.column_index(column)
        assert logical is not None
        widest = max(metrics.horizontalAdvance(text) for text in column_width_probe_texts(column))
        assert widget.table_view.columnWidth(logical) >= widest


def test_compact_switch_reapplies_column_policy(qtbot: QtBot) -> None:
    """set_compact() resets the model, so the policy must survive both switches."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    QApplication.processEvents()
    widget.update_compact_mode()
    assert widget.compact

    header = widget.table_view.horizontalHeader()
    assert not header.stretchLastSection()
    region = widget.table_model.column_index(AnalysisReviewColumn.REGION)
    assert region is not None
    assert header.sectionResizeMode(region) == QHeaderView.ResizeMode.Stretch

    widget.resize(1200, 400)
    QApplication.processEvents()
    widget.update_compact_mode()
    assert not widget.compact
    region = widget.table_model.column_index(AnalysisReviewColumn.REGION)
    assert region is not None
    assert header.sectionResizeMode(region) == QHeaderView.ResizeMode.Stretch
    assert not header.stretchLastSection()


def test_summary_filter_request_switches_readiness_combo(qtbot: QtBot) -> None:
    """A summary count click narrows the region list to that readiness."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    _sync(
        widget,
        (
            _row("region-1", AnalysisReadiness.STALE, "Region 1"),
            _row("region-2", AnalysisReadiness.LATEST, "Region 2"),
        ),
    )

    summary = widget.findChild(AnalysisOverviewSummaryPanel)
    assert summary is not None
    summary.readiness_filter_requested.emit(AnalysisReadiness.STALE.value)

    combo = widget.findChild(QComboBox, "analysisOverviewReadinessFilter")
    assert combo is not None
    assert combo.currentData() == AnalysisReadiness.STALE.value
    assert widget.proxy_model.rowCount() == 1

    summary.readiness_filter_requested.emit("all")
    assert combo.currentData() == "all"


def test_summary_first_region_request_selects_first_visible_row(qtbot: QtBot) -> None:
    """The empty-state link selects the first row like a user click."""
    navigation = _Navigation()
    widget = AnalysisOverviewReviewWidget(navigation)
    qtbot.addWidget(widget)
    _sync(
        widget,
        (
            _row("region-1", AnalysisReadiness.STALE, "Region 1"),
            _row("region-2", AnalysisReadiness.LATEST, "Region 2"),
        ),
    )
    widget.clear_selection()
    selected = QSignalSpy(widget.region_selected)

    first_region_id = widget.proxy_model.region_id_for_index(widget.proxy_model.index(0, 0))
    assert first_region_id is not None
    summary = widget.findChild(AnalysisOverviewSummaryPanel)
    assert summary is not None
    summary.first_region_requested.emit()
    QApplication.processEvents()

    assert widget.selected_region_id() == first_region_id
    assert navigation.state.overview_selection == first_region_id
    assert selected.count() == 1


def test_readiness_filter_minimum_width_fits_longest_item(qtbot: QtBot) -> None:
    """The readiness combo must never clip its longest translated item."""
    widget = AnalysisOverviewReviewWidget(_Navigation())
    qtbot.addWidget(widget)
    combo = widget.findChild(QComboBox, "analysisOverviewReadinessFilter")
    assert combo is not None

    metrics = combo.fontMetrics()
    longest = max(
        metrics.horizontalAdvance(combo.itemText(index)) for index in range(combo.count())
    )
    assert combo.minimumWidth() >= longest + 40
