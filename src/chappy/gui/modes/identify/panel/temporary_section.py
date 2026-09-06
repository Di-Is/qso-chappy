"""Temporary line and registration section for the identify side panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PySide6.QtGui import QResizeEvent

    from chappy.gui.modes.identify.panel.panel_models import RegionPreviewRow, TemporaryLineRow

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from chappy.gui.common.side_panel_heading import apply_side_panel_heading_style
from chappy.gui.modes.identify.panel.workflow_selection_controller import (
    IdentifyWorkflowSelectionController,
)
from chappy.gui.modes.identify.panel.workflow_tree_renderer import (
    IdentifyWorkflowTreeRenderer,
    IdentifyWorkflowTreeText,
)
from chappy.gui.theme import (
    apply_button_variant,
    create_styled_menu,
    empty_state_label_style,
    table_surface_frame_style,
)
from chappy.gui.visual_tokens import LayoutMetrics, SidePanelMetrics


class IdentifyTemporarySection(QWidget):
    """Temporary lines grouped by registration result, with one-click register."""

    compact_height_changed = Signal()
    temporary_delete_requested = Signal(list)
    temporary_clear_requested = Signal()
    registration_requested = Signal(list)  # list[str] - selected IDs, empty for all
    temporary_selection_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construct the temporary lines section."""
        super().__init__(parent)
        self.setObjectName("identifyTemporarySection")
        self._temporary_line_rows: list[TemporaryLineRow] = []
        self._preview_rows: list[RegionPreviewRow] = []
        self._tree_renderer = IdentifyWorkflowTreeRenderer()
        self._selection_controller = IdentifyWorkflowSelectionController()

        self._build_layout()
        self._unconstrained_maximum_height = self.maximumHeight()
        self.retranslate_ui()
        self.set_temporary_lines([])

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SidePanelMetrics.SECTION_SPACING)

        self._temporary_label = QLabel(self)
        self._temporary_label.setObjectName("identifyTemporaryHeader")
        apply_side_panel_heading_style(self._temporary_label)
        root.addWidget(self._temporary_label)

        self._temporary_tree = QTreeWidget(self)
        self._temporary_tree.setObjectName("identifyTemporaryTree")
        self._temporary_tree.setColumnCount(1)
        self._temporary_tree.setHeaderHidden(True)
        self._temporary_tree.setRootIsDecorated(False)
        self._temporary_tree.setIndentation(12)
        self._temporary_tree.setUniformRowHeights(True)
        self._temporary_tree.setAlternatingRowColors(True)
        self._temporary_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._temporary_tree.setStyleSheet(
            "QTreeWidget#identifyTemporaryTree { border: none; border-radius: 0; }"
        )
        self._temporary_tree.itemSelectionChanged.connect(self._on_temporary_selection_changed)

        self._temporary_placeholder = QLabel(self)
        self._temporary_placeholder.setObjectName("identifyTemporaryEmptyState")
        self._temporary_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._temporary_placeholder.setWordWrap(True)
        self._temporary_placeholder.setStyleSheet(empty_state_label_style())

        self._content_surface = QFrame(self)
        self._content_surface.setObjectName("identifyTemporaryContentSurface")
        self._content_surface.setStyleSheet(
            table_surface_frame_style("identifyTemporaryContentSurface")
        )
        content_layout = QVBoxLayout(self._content_surface)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._temporary_tree, 1)
        content_layout.addWidget(self._temporary_placeholder)

        self._button_bar = QWidget(self)
        self._button_bar.setObjectName("identifyTemporaryButtonBar")
        button_layout = QVBoxLayout(self._button_bar)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(SidePanelMetrics.SECTION_SPACING)
        secondary_row = QHBoxLayout()
        secondary_row.setContentsMargins(0, 0, 0, 0)
        secondary_row.setSpacing(SidePanelMetrics.BUTTON_ROW_SPACING)
        commit_row = QHBoxLayout()
        commit_row.setContentsMargins(0, 0, 0, 0)
        commit_row.setSpacing(SidePanelMetrics.BUTTON_ROW_SPACING)
        self._delete_button = QPushButton(self)
        self._more_button = QPushButton(self)
        self._register_button = QPushButton(self)

        self._delete_button.setObjectName("identifyTemporaryDeleteButton")
        self._more_button.setObjectName("identifyTemporaryMoreButton")
        self._register_button.setObjectName("identifyTemporaryRegisterButton")

        self._delete_button.clicked.connect(self._emit_delete_requested)
        self._register_button.clicked.connect(self._emit_registration_requested)

        self._more_menu = create_styled_menu(self)
        self._clear_action = self._more_menu.addAction("")
        self._clear_action.triggered.connect(self.temporary_clear_requested)
        self._more_button.setMenu(self._more_menu)

        apply_button_variant(self._delete_button, "secondary")
        apply_button_variant(self._more_button, "text")
        apply_button_variant(self._register_button, "primary")

        secondary_row.addWidget(self._delete_button)
        secondary_row.addWidget(self._more_button)
        secondary_row.addStretch(1)
        commit_row.addStretch(1)
        commit_row.addWidget(self._register_button)
        button_layout.addLayout(secondary_row)
        button_layout.addLayout(commit_row)
        self._registration_feedback = QWidget(self._content_surface)
        self._registration_feedback.setObjectName("identifyRegistrationFeedback")
        feedback_layout = QVBoxLayout(self._registration_feedback)
        feedback_padding = SidePanelMetrics.BUTTON_ROW_SPACING
        feedback_layout.setContentsMargins(
            feedback_padding, feedback_padding, feedback_padding, feedback_padding
        )
        feedback_layout.setSpacing(SidePanelMetrics.BUTTON_ROW_SPACING)
        self._registration_feedback_label = QLabel(self._registration_feedback)
        self._registration_feedback_label.setObjectName("identifyRegistrationFeedbackLabel")
        self._registration_feedback_label.setWordWrap(True)
        self._registration_feedback_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        feedback_layout.addWidget(self._registration_feedback_label)
        content_layout.addWidget(self._registration_feedback)
        self._registration_feedback.setVisible(False)

        root.addWidget(self._content_surface, 1)
        root.addWidget(self._button_bar)

    def retranslate_ui(self) -> None:
        """Apply the active language to all visible strings."""
        self._update_heading()
        self._temporary_placeholder.setText(
            self.tr("Added temporary lines appear here, grouped by registration destination.")
        )
        self._delete_button.setText(self.tr("Delete"))
        self._more_button.setText("⋯")
        self._more_button.setToolTip(self.tr("More actions"))
        self._more_button.setAccessibleName(self.tr("More actions"))
        self._clear_action.setText(self.tr("Clear All"))
        self._update_button_states()
        if self._temporary_line_rows:
            self.set_temporary_lines(self._temporary_line_rows, self._preview_rows)
        else:
            self._apply_content_layout(has_rows=False)

    def set_temporary_lines(
        self, lines: Sequence[TemporaryLineRow], previews: Sequence[RegionPreviewRow] = ()
    ) -> None:
        """Display temporary lines grouped by the live registration result."""
        selected_primary_ids = self._selection_controller.selected_temporary_primary_id_set(
            self._temporary_tree
        )

        self._temporary_line_rows = list(lines)
        self._preview_rows = list(previews)

        self._temporary_tree.blockSignals(True)
        self._tree_renderer.render_temporary_lines(
            self._temporary_tree,
            self._temporary_line_rows,
            self._preview_rows,
            selected_primary_ids=selected_primary_ids,
            text=self._tree_text(),
        )
        self._temporary_tree.blockSignals(False)

        has_rows = bool(self._temporary_line_rows)
        self._apply_content_layout(has_rows=has_rows)
        self._update_heading()
        self._update_button_states()

    def show_registration_feedback(self, message: str) -> None:
        """Show passive feedback for a successful registration."""
        if not message:
            self.clear_registration_feedback()
            return
        self._registration_feedback_label.setText(message)
        self._registration_feedback.setVisible(True)
        self._apply_content_layout(has_rows=self.has_rows)

    def clear_registration_feedback(self) -> None:
        """Clear registration feedback at the next workflow update."""
        if not self.has_registration_feedback:
            return
        self._registration_feedback.setVisible(False)
        self._registration_feedback_label.clear()
        self._apply_content_layout(has_rows=self.has_rows)

    def _apply_content_layout(self, *, has_rows: bool) -> None:
        """Apply visibility and height constraints derived from row presence."""
        self.setMaximumHeight(self._unconstrained_maximum_height)
        self._temporary_tree.setVisible(has_rows)
        self._temporary_placeholder.setVisible(not has_rows and not self.has_registration_feedback)
        self._button_bar.setVisible(has_rows)
        vertical_policy = QSizePolicy.Policy.Expanding if has_rows else QSizePolicy.Policy.Maximum
        self.setSizePolicy(QSizePolicy.Policy.Expanding, vertical_policy)
        layout = self.layout()
        if layout is None:
            msg = "Temporary section layout is required."
            raise RuntimeError(msg)
        content_layout = self._content_surface.layout()
        if content_layout is None:
            msg = "Temporary content surface layout is required."
            raise RuntimeError(msg)
        content_layout.invalidate()
        content_layout.activate()
        self._content_surface.updateGeometry()
        layout.invalidate()
        layout.activate()
        if not has_rows:
            self._update_compact_maximum_height()
        self.updateGeometry()

    def _update_compact_maximum_height(self) -> None:
        """Fit wrapped empty or feedback content to the current panel width."""
        layout = self.layout()
        if layout is None:
            msg = "Temporary section layout is required."
            raise RuntimeError(msg)
        compact_height = layout.totalHeightForWidth(self.width())
        if compact_height < 0:
            compact_height = layout.totalSizeHint().height()
        height_changed = compact_height != self.maximumHeight()
        if height_changed:
            self.setMaximumHeight(compact_height)
        layout.setGeometry(self.rect())
        if height_changed:
            self.compact_height_changed.emit()

    @property
    def has_rows(self) -> bool:
        """Return whether temporary groups are available."""
        return bool(self._temporary_line_rows)

    @property
    def has_registration_feedback(self) -> bool:
        """Return whether registration feedback is currently visible."""
        return not self._registration_feedback.isHidden()

    def minimum_readable_height(self) -> int:
        """Return the height needed for a group heading, two rows, and actions."""
        row_height = self._temporary_tree.sizeHintForRow(0)
        if row_height <= 0:
            row_height = self._temporary_tree.fontMetrics().height() + 8
        tree_height = (
            row_height * SidePanelMetrics.IDENTIFY_TEMPORARY_MIN_VISIBLE_ROWS
            + 2 * LayoutMetrics.SEPARATOR_THIN
        )
        layout = self.layout()
        if layout is None:
            msg = "Temporary section layout is required."
            raise RuntimeError(msg)
        feedback_height = (
            self._registration_feedback.sizeHint().height()
            if self.has_registration_feedback
            else 0
        )
        return (
            self._temporary_label.sizeHint().height()
            + tree_height
            + self._button_bar.sizeHint().height()
            + 2 * layout.spacing()
            + feedback_height
        )

    def _tree_text(self) -> IdentifyWorkflowTreeText:
        """Return translated tree renderer text."""
        return IdentifyWorkflowTreeText(
            unknown=self.tr("Unknown"),
            grouped_template=self.tr("{count} lines grouped"),
            #: {species} is a species label; {start}/{end} are wavelengths in Å;
            #: {count} is the number of lines bundled into the new region.
            new_region_template=self.tr("New region: {species} {start:.1f}–{end:.1f} Å ({count})"),
            #: {region} is an existing region name; {count} is the number of lines added.
            append_region_template=self.tr("→ Add to {region} ({count})"),
            overlap_warning=self.tr(
                "Overlaps multiple existing regions. Check the assignment in Analysis "
                "Structure after registering."
            ),
        )

    def _update_heading(self) -> None:
        group_count = len(self._temporary_line_rows)
        line_count = sum(len(row.temporary_line_ids) for row in self._temporary_line_rows)
        #: {groups} and {lines} are localized count-and-unit phrases.
        template = self.tr("To register: {groups} / {lines}")
        self._temporary_label.setText(
            template.format(
                groups=self._group_count_text(group_count), lines=self._line_count_text(line_count)
            )
        )

    def _on_temporary_selection_changed(self) -> None:
        selected_ids = self._selection_controller.selected_temporary_primary_ids(
            self._temporary_tree
        )
        self._update_button_states()
        self.temporary_selection_changed.emit(selected_ids)

    def _emit_delete_requested(self) -> None:
        temporary_line_ids = self._selection_controller.selected_temporary_primary_ids(
            self._temporary_tree
        )
        if temporary_line_ids:
            self.temporary_delete_requested.emit(temporary_line_ids)

    def _emit_registration_requested(self) -> None:
        selected_ids = self._selection_controller.selected_temporary_primary_ids(
            self._temporary_tree
        )
        self.registration_requested.emit(selected_ids)

    def _update_button_states(self) -> None:
        selected_count = len(
            self._selection_controller.selected_temporary_primary_ids(self._temporary_tree)
        )
        has_selection = selected_count > 0
        has_rows = bool(self._temporary_line_rows)

        target_count = selected_count if has_selection else len(self._temporary_line_rows)
        groups = self._group_count_text(target_count)
        if has_selection:
            #: {groups} is a localized group count such as "2 groups".
            label = self.tr("Register selected ({groups})").format(groups=groups)
        else:
            #: {groups} is a localized group count such as "2 groups".
            label = self.tr("Register all ({groups})").format(groups=groups)
        self._register_button.setText(label)

        self._delete_button.setEnabled(has_selection)
        self._more_button.setEnabled(has_rows)
        self._clear_action.setEnabled(has_rows)
        self._register_button.setEnabled(has_rows)
        self._register_button.setToolTip(
            ""
            if has_rows
            else self.tr("No temporary lines. Shift+click on the spectrum to add them.")
        )

    def _group_count_text(self, count: int) -> str:
        """Return a translated temporary-group count."""
        #: {count} is the number of temporary groups.
        template = self.tr("{count} group") if count == 1 else self.tr("{count} groups")
        return template.format(count=count)

    def _line_count_text(self, count: int) -> str:
        """Return a translated constituent-line count."""
        #: {count} is the number of constituent lines.
        template = self.tr("{count} line") if count == 1 else self.tr("{count} lines")
        return template.format(count=count)

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Refresh translated text when Qt installs a new translator."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute compact height when wrapped content receives a new width."""
        super().resizeEvent(event)
        if not self.has_rows:
            self._update_compact_maximum_height()
