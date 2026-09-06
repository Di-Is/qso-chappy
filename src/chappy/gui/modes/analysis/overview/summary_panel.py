"""Right-side summary and selected-region details for Analysis Overview."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from chappy.core.analysis import AnalysisReadiness
from chappy.gui.common.collapsible_section import CollapsibleSection
from chappy.gui.theme import Colors, Fonts, apply_button_variant, card_frame_style
from chappy.gui.visual_tokens import SidePanelMetrics
from chappy.presentation.analysis import build_region_structure_summary
from chappy.presentation.analysis.structure.tree_presenter import StructureTreePresenter

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent

    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.presentation.analysis import AnalysisReviewRow, AnalysisReviewSummary

_EXCLUSIVE_STATUSES = (
    AnalysisReadiness.NOT_ANALYZED,
    AnalysisReadiness.STALE,
    AnalysisReadiness.LATEST,
)

_STATUS_OBJECT_NAMES = {
    AnalysisReadiness.NOT_ANALYZED: "analysisOverviewStatusNotAnalyzed",
    AnalysisReadiness.STALE: "analysisOverviewStatusStale",
    AnalysisReadiness.LATEST: "analysisOverviewStatusLatest",
}

_MAX_TRANSITIONS_PER_ROW = 3


class _ClickableLabel(QLabel):
    """Label emitting a click intent while it is enabled."""

    clicked = Signal()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit the click intent for enabled left-button releases inside."""
        if (
            self.isEnabled()
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class AnalysisOverviewSummaryPanel(QWidget):
    """Render typed counts, structure, and explicit user actions."""

    open_region_requested = Signal(str)
    structure_edit_requested = Signal(str)
    readiness_filter_requested = Signal(str)
    first_region_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analysisOverviewSummaryPanel")
        # The minimum width constraint is centralized on the Analysis right
        # stack (workspace.py); no duplicates here.
        self._selected_region_id: str | None = None
        self._last_summary: AnalysisReviewSummary | None = None
        self._last_row: AnalysisReviewRow | None = None
        self._last_project: SpectroscopyProject | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._progress = QLabel(self)
        self._progress.setObjectName("analysisOverviewProgress")
        self._progress.setWordWrap(True)
        self._progress.setStyleSheet(
            f"QLabel#analysisOverviewProgress {{"
            f" font-size: {Fonts.SIZE_LARGE}; font-weight: 600;"
            f" color: {Colors.TEXT_PRIMARY};"
            "}"
        )
        layout.addWidget(self._progress)

        # The text block scrolls so selection and structure stay
        # reachable at the 800x600 minimum window size; the action buttons
        # remain pinned below the scroll surface.
        content = QWidget(self)
        content.setObjectName("analysisOverviewSummaryContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SidePanelMetrics.SECTION_SPACING)
        content_layout.addWidget(self._build_status_section(content))
        content_layout.addWidget(self._build_selection_section(content))
        content_layout.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("analysisOverviewSummaryScroll")
        self._scroll.setWidget(content)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Keep the panel background visible instead of the themed
        # QAbstractScrollArea fill; only section widgets live inside.
        self._scroll.setStyleSheet(
            "#analysisOverviewSummaryScroll, #analysisOverviewSummaryContent"
            " { background: transparent; }"
        )
        layout.addWidget(self._scroll, 1)

        self._open_button = QPushButton(self)
        self._open_button.setObjectName("analysisOverviewOpenRegionButton")
        apply_button_variant(self._open_button, "primary")
        self._open_button.clicked.connect(self._emit_open)
        layout.addWidget(self._open_button)
        self._edit_button = QPushButton(self)
        self._edit_button.setObjectName("analysisOverviewEditStructureButton")
        apply_button_variant(self._edit_button, "secondary")
        self._edit_button.clicked.connect(self._emit_edit)
        layout.addWidget(self._edit_button)

        self._retranslate_static_texts()
        self.render_selection(None, None)

    def _build_status_section(self, parent: QWidget) -> CollapsibleSection:
        content = QWidget(parent)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SidePanelMetrics.COLLAPSIBLE_HEADER_SPACING)

        card = QFrame(content)
        card.setObjectName("analysisOverviewStatusCard")
        card.setStyleSheet(card_frame_style("analysisOverviewStatusCard"))
        grid = QGridLayout(card)
        grid.setContentsMargins(*SidePanelMetrics.CARD_CONTENT_MARGIN)
        grid.setHorizontalSpacing(SidePanelMetrics.SECTION_SPACING)
        grid.setVerticalSpacing(SidePanelMetrics.COLLAPSIBLE_HEADER_SPACING)
        self._status_items: dict[AnalysisReadiness, _ClickableLabel] = {}
        for position, readiness in enumerate(_EXCLUSIVE_STATUSES):
            label = _ClickableLabel(card)
            label.setObjectName(_STATUS_OBJECT_NAMES[readiness])
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.clicked.connect(
                lambda value=readiness.value: self.readiness_filter_requested.emit(value)
            )
            grid.addWidget(label, position // 2, position % 2)
            self._status_items[readiness] = label
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        content_layout.addWidget(card)

        self._status_section = CollapsibleSection(
            content, parent, header_object_name="analysisOverviewStatusHeader"
        )
        self._status_section.setObjectName("analysisOverviewStatusSection")
        return self._status_section

    def _build_selection_section(self, parent: QWidget) -> CollapsibleSection:
        content = QWidget(parent)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SidePanelMetrics.COLLAPSIBLE_HEADER_SPACING)

        self._selection = QLabel(content)
        self._selection.setObjectName("analysisOverviewSelection")
        self._selection.setWordWrap(True)
        content_layout.addWidget(self._selection)

        self._select_first_button = QPushButton(content)
        self._select_first_button.setObjectName("analysisOverviewSelectFirstButton")
        apply_button_variant(self._select_first_button, "text")
        self._select_first_button.clicked.connect(self.first_region_requested)
        content_layout.addWidget(self._select_first_button, 0, Qt.AlignmentFlag.AlignLeft)

        self._structure = QLabel(content)
        self._structure.setObjectName("analysisOverviewReadOnlyStructure")
        self._structure.setWordWrap(True)
        content_layout.addWidget(self._structure)

        self._selection_section = CollapsibleSection(
            content, parent, header_object_name="analysisOverviewSelectionHeader"
        )
        self._selection_section.setObjectName("analysisOverviewSelectionSection")
        return self._selection_section

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Refresh translated text when Qt translators change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_static_texts()
            if self._last_summary is not None:
                self.render_summary(self._last_summary)
            self.render_selection(self._last_row, self._last_project)
        super().changeEvent(event)

    def render_summary(self, summary: AnalysisReviewSummary) -> None:
        """Render authoritative aggregate counts without recomputing them."""
        self._last_summary = summary
        #: {done} regions have an up-to-date fit result out of {total} regions.
        self._progress.setText(
            self.tr("Done {done} / {total} regions").format(
                done=summary.latest, total=summary.total
            )
        )
        counts = {
            AnalysisReadiness.NOT_ANALYZED: summary.not_analyzed,
            AnalysisReadiness.STALE: summary.stale,
            AnalysisReadiness.LATEST: summary.latest,
        }
        for readiness, label in self._status_items.items():
            count = counts[readiness]
            label.setText(self._status_count_text(readiness).format(count=count))
            label.setEnabled(count > 0)

    def render_selection(
        self, row: AnalysisReviewRow | None, project: SpectroscopyProject | None
    ) -> None:
        """Render one typed row and read-only project structure."""
        self._last_row = row
        self._last_project = project
        self._selected_region_id = row.region.region_id if row is not None else None
        enabled = row is not None
        self._open_button.setEnabled(enabled)
        self._edit_button.setEnabled(enabled)
        self._open_button.setToolTip("" if enabled else self.tr("Select a region to open it."))
        self._edit_button.setToolTip("" if enabled else self.tr("Select a region to edit it."))
        self._select_first_button.setVisible(row is None)
        self._structure.setVisible(row is not None)
        if row is None:
            self._selection.setText(self.tr("Select a region from the region list below."))
            return

        #: {region} is the localized display label of the selected analysis region.
        self._selection.setText(self.tr("Selected: {region}").format(region=row.region.label))
        if project is None:
            self._structure.setText("—")
            return

        region = project.absorption_regions[row.region.region_id]
        lines = [project.absorption_lines[line_id] for line_id in region.line_ids]
        summary = build_region_structure_summary(lines)
        #: {linked} is the linked-line count; {lines} is the absorption-line count.
        display_lines = [
            self.tr("Linked lines: {linked} / Lines: {lines}").format(
                linked=summary.linked_line_count, lines=summary.line_count
            )
        ]
        if summary.linked_line_count > 0 and not summary.linked_lines:
            #: {button} is the current label of the button that opens region editing.
            display_lines.append(
                self.tr("See [{button}] for the breakdown.").format(
                    button=self._edit_button.text()
                )
            )
        else:
            for linked_line in summary.linked_lines:
                transition_names = linked_line.transition_names
                names = ", ".join(transition_names[:_MAX_TRANSITIONS_PER_ROW])
                remaining_count = len(transition_names) - _MAX_TRANSITIONS_PER_ROW
                if remaining_count > 0:
                    #: {names} contains the strongest transition names; {count} is omitted lines.
                    names = self.tr("{names} and {count} more").format(
                        names=names, count=remaining_count
                    )
                redshift = StructureTreePresenter.format_redshift(linked_line.center_z) or "—"
                #: {redshift} is the linked line's redshift; {transitions} lists its transitions.
                display_lines.append(
                    self.tr("z={redshift}  {transitions}").format(
                        redshift=redshift, transitions=names
                    )
                )
        self._structure.setText("\n".join(display_lines))

    def _retranslate_static_texts(self) -> None:
        self._status_section.set_title(self.tr("Status"))
        self._selection_section.set_title(self.tr("Selected region"))
        self._open_button.setText(self.tr("Open region"))
        self._edit_button.setText(self.tr("Edit region"))
        self._select_first_button.setText(self.tr("Select the first region"))
        click_note = self.tr("Click to filter the region list.")
        status_tooltips = {
            AnalysisReadiness.NOT_ANALYZED: self.tr(
                "Prerequisites are met but the region has not been fitted yet."
            ),
            AnalysisReadiness.STALE: self.tr(
                "A fit result exists but inputs changed afterwards. Reanalysis is required."
            ),
            AnalysisReadiness.LATEST: self.tr(
                "A fit result exists and matches the current inputs."
            ),
        }
        for readiness, label in self._status_items.items():
            label.setToolTip(f"{status_tooltips[readiness]}\n{click_note}")

    def _status_count_text(self, readiness: AnalysisReadiness) -> str:
        #: {count} is the number of regions in this exclusive analysis status.
        templates = {
            AnalysisReadiness.NOT_ANALYZED: self.tr("Not analyzed: {count}"),
            AnalysisReadiness.STALE: self.tr("Stale: {count}"),
            AnalysisReadiness.LATEST: self.tr("Latest: {count}"),
        }
        return templates[readiness]

    def _emit_open(self) -> None:
        if self._selected_region_id is not None:
            self.open_region_requested.emit(self._selected_region_id)

    def _emit_edit(self) -> None:
        if self._selected_region_id is not None:
            self.structure_edit_requested.emit(self._selected_region_id)


__all__ = ["AnalysisOverviewSummaryPanel"]
