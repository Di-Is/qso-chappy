"""Side panel implementation for identify mode workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QPaintEvent

    from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
    from chappy.gui.modes.identify.panel.panel_models import (
        CandidateRow,
        ConfirmedRegionRow,
        LineListItem,
        RegionPreviewRow,
        TemporaryLineRow,
    )

from PySide6.QtCore import QEvent, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QSplitter, QSplitterHandle, QVBoxLayout, QWidget

from chappy.gui.common.collapsible_section import CollapsibleSection
from chappy.gui.modes.identify.panel.candidate_section import IdentifyCandidateSection
from chappy.gui.modes.identify.panel.confirmed_section import IdentifyConfirmedRegionsSection
from chappy.gui.modes.identify.panel.preset_lines_section import IdentifyPresetLinesSection
from chappy.gui.modes.identify.panel.temporary_section import IdentifyTemporarySection
from chappy.gui.theme import Colors
from chappy.gui.visual_tokens import SidePanelMetrics
from chappy.i18n import get_language_switcher

if TYPE_CHECKING:
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.mode_state_store import ModeStateStore

NONEMPTY_SPLITTER_SIZES_KEY = "identify_panel/nonempty_splitter_sizes"
CONFIRMED_COLLAPSED_KEY = "identify_panel/confirmed_section_collapsed"


class _IdentifySplitterHandle(QSplitterHandle):
    """Splitter handle that only advertises an available resize operation."""

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        """Draw a centered grip only while the handle is enabled."""
        if not self.isEnabled():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.TEXT_SECONDARY))
        center = self.rect().center()
        for offset in (-6.0, -2.0, 2.0, 6.0):
            painter.drawEllipse(QPointF(center.x() + offset, center.y()), 1.0, 1.0)
        painter.end()


class _IdentifySplitter(QSplitter):
    """Vertical identify splitter with state-aware grip rendering."""

    @override
    def createHandle(self) -> QSplitterHandle:
        """Create the identify-specific handle."""
        return _IdentifySplitterHandle(self.orientation(), self)


class IdentifySidePanel(QWidget):
    """Single-column, workflow-ordered side panel for identify mode."""

    preset_changed = Signal(str)
    manage_presets_requested = Signal()
    reference_line_changed = Signal(str)
    new_candidate_analysis_half_width_changed = Signal(object)
    sigma_threshold_changed = Signal(float)
    candidate_activated = Signal(str)
    temporary_delete_requested = Signal(list)
    temporary_clear_requested = Signal()
    registration_requested = Signal(list)  # list[str] - selected IDs, empty for all
    temporary_selection_changed = Signal(list)
    group_focus_requested = Signal(str, float, float)
    line_focus_requested = Signal(str, float, float)
    region_open_requested = Signal(str)
    region_structure_edit_requested = Signal(str)
    ui_state_changed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        project: SpectroscopyProject | None = None,
        mode_state_store: ModeStateStore | None = None,
    ) -> None:
        """Initialize identify mode side panel with optional context."""
        super().__init__(parent)
        self.setObjectName("identifySidePanel")

        self._project: SpectroscopyProject | None = project
        self._mode_state_store: ModeStateStore | None = mode_state_store
        self._language_switcher = get_language_switcher(self)
        self._current_candidates: list[CandidateRow] = []
        self._last_nonempty_splitter_sizes: tuple[int, int, int] | None = None
        self._applying_splitter_layout = False

        self._preset_section = IdentifyPresetLinesSection(self)
        self._preset_section.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )

        self._candidate_section = IdentifyCandidateSection(self)
        self._temporary_section = IdentifyTemporarySection(self)
        self._confirmed_section = IdentifyConfirmedRegionsSection(self)
        self._confirmed_collapsible = CollapsibleSection(
            self._confirmed_section,
            self,
            header_object_name="identifyConfirmedCollapsibleHeader",
            expanded_vertical_policy=QSizePolicy.Policy.Expanding,
        )
        self._confirmed_collapsible.setObjectName("identifyConfirmedCollapsible")
        self._confirmed_collapsible.set_collapsed(True)

        self._splitter = _IdentifySplitter(Qt.Orientation.Vertical, self)
        self._splitter.setObjectName("identifyPanelSplitter")
        self._splitter.setHandleWidth(SidePanelMetrics.SPLITTER_HANDLE_WIDTH)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._candidate_section)
        self._splitter.addWidget(self._temporary_section)
        self._splitter.addWidget(self._confirmed_collapsible)
        for index, stretch in enumerate(SidePanelMetrics.IDENTIFY_SPLITTER_RATIO):
            self._splitter.setStretchFactor(index, stretch)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*SidePanelMetrics.OUTER_MARGIN)
        layout.setSpacing(SidePanelMetrics.SECTION_SPACING)
        layout.addWidget(self._preset_section)
        layout.addWidget(self._splitter, 1)

        self._preset_section.preset_changed.connect(self.preset_changed)
        self._preset_section.manage_presets_requested.connect(self.manage_presets_requested)
        self._preset_section.reference_line_changed.connect(self.reference_line_changed)
        self._preset_section.new_candidate_analysis_half_width_changed.connect(
            self.new_candidate_analysis_half_width_changed
        )

        self._candidate_section.sigma_threshold_changed.connect(self.sigma_threshold_changed)
        self._candidate_section.candidate_activated.connect(self.candidate_activated)

        self._temporary_section.temporary_delete_requested.connect(self.temporary_delete_requested)
        self._temporary_section.temporary_clear_requested.connect(self.temporary_clear_requested)
        self._temporary_section.registration_requested.connect(self.registration_requested)
        self._temporary_section.temporary_selection_changed.connect(
            self.temporary_selection_changed
        )
        self._temporary_section.compact_height_changed.connect(
            self._apply_layout_for_content_state, Qt.ConnectionType.QueuedConnection
        )

        self._confirmed_section.group_focus_requested.connect(self.group_focus_requested)
        self._confirmed_section.line_focus_requested.connect(self.line_focus_requested)
        self._confirmed_section.region_open_requested.connect(self.region_open_requested)
        self._confirmed_section.region_structure_edit_requested.connect(
            self.region_structure_edit_requested
        )

        self._confirmed_collapsible.collapse_toggled.connect(self._on_confirmed_collapse_toggled)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        self._language_switcher.language_changed.connect(self._handle_language_changed)
        self._retranslate_ui()
        self._sync_splitter_handle_states()

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Cache the current project reference for later use."""
        if project is self._project:
            return
        self._project = project

    def attach_mode_state_store(self, mode_state_store: ModeStateStore) -> None:
        """Attach the mode state store reference for the panel."""
        if mode_state_store is None:
            msg = "Mode state store is required."
            raise TypeError(msg)
        self._mode_state_store = mode_state_store

    def detach_mode_state_store(self) -> None:
        """Detach the mode state store reference from the panel."""
        self._mode_state_store = None

    def set_presets(self, presets: Sequence[tuple[str, str]], current: str | None = None) -> None:
        """Forward preset data to the preset lines section."""
        self._preset_section.set_presets(presets, current)

    def set_line_items(self, items: Sequence[LineListItem]) -> None:
        """Forward line items to the preset lines section."""
        self._preset_section.set_line_items(items)

    def set_candidates(self, candidates: Sequence[CandidateRow]) -> None:
        """Forward candidate rows to the candidate section."""
        self._candidate_section.set_candidates(candidates)
        self._current_candidates = list(candidates)

    def set_sigma_threshold(self, value: float) -> None:
        """Forward sigma threshold value to the candidate section."""
        self._candidate_section.set_sigma_threshold(value)

    def set_new_candidate_analysis_half_width(self, value: NewCandidateAnalysisHalfWidth) -> None:
        """Forward the future-candidate draft to the preset section."""
        self._preset_section.set_new_candidate_analysis_half_width(value)

    def set_temporary_lines(
        self, lines: Sequence[TemporaryLineRow], previews: Sequence[RegionPreviewRow] = ()
    ) -> None:
        """Display temporary lines grouped by the live registration result."""
        had_feedback = self._temporary_section.has_registration_feedback
        self._temporary_section.clear_registration_feedback()
        had_rows = self._temporary_section.has_rows
        if had_rows and not lines:
            self._capture_current_nonempty_sizes()
        self._temporary_section.set_temporary_lines(lines, previews)
        if had_feedback or had_rows != self._temporary_section.has_rows:
            self._apply_layout_for_content_state()

    def show_registration_feedback(self, message: str) -> None:
        """Show registration feedback after workflow refresh has completed."""
        self._temporary_section.show_registration_feedback(message)
        self._apply_layout_for_content_state()

    def set_confirmed_regions(self, groups: Sequence[ConfirmedRegionRow]) -> None:
        """Forward confirmed regions to the confirmed section."""
        had_groups = self._confirmed_section.has_groups
        if had_groups and not groups:
            self._capture_current_nonempty_sizes()
        self._confirmed_section.set_confirmed_regions(groups)
        self._confirmed_collapsible.set_summary(self._confirmed_section.summary_text())
        if had_groups != self._confirmed_section.has_groups:
            self._apply_layout_for_content_state()

    def reveal_confirmed_regions(self, region_ids: Sequence[str]) -> None:
        """Bring just-registered regions into view in the confirmed section."""
        self._confirmed_section.reveal_regions(region_ids)

    @property
    def current_candidates(self) -> tuple[CandidateRow, ...]:
        """Expose the most recently supplied candidate rows."""
        return tuple(self._current_candidates)

    def restore_ui_state(self, settings: QSettings) -> None:
        """Restore splitter position and section collapse state from settings."""
        self._last_nonempty_splitter_sizes = self._decode_splitter_sizes(
            settings.value(NONEMPTY_SPLITTER_SIZES_KEY, defaultValue=None)
        )
        confirmed_collapsed = settings.value(CONFIRMED_COLLAPSED_KEY, defaultValue=True, type=bool)
        self._confirmed_collapsible.set_collapsed(bool(confirmed_collapsed))
        self._apply_layout_for_content_state()

    def save_ui_state(self, settings: QSettings) -> None:
        """Persist splitter position and section collapse state into settings."""
        self._capture_current_nonempty_sizes()
        if self._last_nonempty_splitter_sizes is not None:
            settings.setValue(
                NONEMPTY_SPLITTER_SIZES_KEY,
                self._encode_splitter_sizes(self._last_nonempty_splitter_sizes),
            )
        settings.setValue(CONFIRMED_COLLAPSED_KEY, self._confirmed_collapsible.is_collapsed())

    def _on_splitter_moved(self, *_: object) -> None:
        if self._applying_splitter_layout:
            return
        self._capture_current_nonempty_sizes()
        self.ui_state_changed.emit()

    def _on_confirmed_collapse_toggled(self, collapsed: bool) -> None:
        if collapsed:
            self._capture_current_nonempty_sizes(
                confirmed_is_flexible=self._confirmed_section.has_groups
            )
        self._apply_layout_for_content_state()
        self.ui_state_changed.emit()

    def _capture_current_nonempty_sizes(
        self, *, confirmed_is_flexible: bool | None = None
    ) -> None:
        temporary_is_flexible = self._temporary_section.has_rows
        if confirmed_is_flexible is None:
            confirmed_is_flexible = (
                self._confirmed_section.has_groups
                and not self._confirmed_collapsible.is_collapsed()
            )
        if not temporary_is_flexible and not confirmed_is_flexible:
            return
        current = self._splitter_size_tuple()
        baseline = self._last_nonempty_splitter_sizes or self._default_nonempty_sizes()
        temporary_size = current[1] if temporary_is_flexible else baseline[1]
        confirmed_size = current[2] if confirmed_is_flexible else baseline[2]
        temporary_reclaim = 0 if temporary_is_flexible else max(0, temporary_size - current[1])
        confirmed_reclaim = 0 if confirmed_is_flexible else max(0, confirmed_size - current[2])
        compact_reclaim = temporary_reclaim + confirmed_reclaim
        candidate_size = max(1, current[0] - compact_reclaim)
        self._last_nonempty_splitter_sizes = (candidate_size, temporary_size, confirmed_size)

    def _apply_layout_for_content_state(self) -> None:
        desired = list(self._last_nonempty_splitter_sizes or self._default_nonempty_sizes())
        if self._temporary_section.has_rows:
            minimum = self._temporary_section.minimum_readable_height()
            if desired[1] < minimum:
                deficit = minimum - desired[1]
                candidate_floor = self._candidate_section.minimumSizeHint().height()
                available_from_candidate = max(0, desired[0] - candidate_floor)
                moved = min(deficit, available_from_candidate)
                desired[0] -= moved
                desired[1] += moved
                desired[1] = max(desired[1], minimum)
        else:
            compact = self._temporary_section.maximumHeight()
            reclaimed = max(0, desired[1] - compact)
            desired[0] += reclaimed
            desired[1] = compact

        confirmed_is_compact = (
            not self._confirmed_section.has_groups or self._confirmed_collapsible.is_collapsed()
        )
        if confirmed_is_compact:
            compact = self._confirmed_collapsible.sizeHint().height()
            reclaimed = max(0, desired[2] - compact)
            desired[0] += reclaimed
            desired[2] = compact

        self._set_splitter_sizes(desired)
        self._sync_splitter_handle_states()

    def _sync_splitter_handle_states(self) -> None:
        """Expose resize affordances only while both adjacent panes are flexible."""
        temporary_is_flexible = self._temporary_section.has_rows
        confirmed_is_flexible = (
            self._confirmed_section.has_groups and not self._confirmed_collapsible.is_collapsed()
        )
        for handle, enabled in (
            (self._splitter.handle(1), temporary_is_flexible),
            (self._splitter.handle(2), temporary_is_flexible and confirmed_is_flexible),
        ):
            handle.setEnabled(enabled)
            cursor = Qt.CursorShape.SplitVCursor if enabled else Qt.CursorShape.ArrowCursor
            handle.setCursor(cursor)
            handle.update()

    def _default_nonempty_sizes(self) -> tuple[int, int, int]:
        ratios = SidePanelMetrics.IDENTIFY_SPLITTER_RATIO
        total = max(700, self._splitter.height())
        ratio_total = sum(ratios)
        return (
            max(1, total * ratios[0] // ratio_total),
            max(1, total * ratios[1] // ratio_total),
            max(1, total * ratios[2] // ratio_total),
        )

    def _splitter_size_tuple(self) -> tuple[int, int, int]:
        sizes = self._splitter.sizes()
        if len(sizes) != 3:
            msg = f"Identify splitter must expose three sizes, got {len(sizes)}."
            raise RuntimeError(msg)
        return (sizes[0], sizes[1], sizes[2])

    def _set_splitter_sizes(self, sizes: Sequence[int]) -> None:
        if len(sizes) != 3:
            msg = "Identify splitter requires exactly three sizes."
            raise ValueError(msg)
        self._applying_splitter_layout = True
        try:
            self._splitter.setSizes(list(sizes))
        finally:
            self._applying_splitter_layout = False

    @staticmethod
    def _encode_splitter_sizes(sizes: tuple[int, int, int]) -> str:
        return ",".join(str(size) for size in sizes)

    @staticmethod
    def _decode_splitter_sizes(value: object) -> tuple[int, int, int] | None:
        if not isinstance(value, str):
            return None
        parts = value.split(",")
        if len(parts) != 3:
            return None
        try:
            sizes = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
        if any(size <= 0 for size in sizes):
            return None
        return sizes

    def _handle_language_changed(self, _: str) -> None:
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self._preset_section.retranslate_ui()
        self._candidate_section.retranslate_ui()
        self._temporary_section.retranslate_ui()
        self._confirmed_section.retranslate_ui()
        self._confirmed_collapsible.set_title(self.tr("Confirmed Regions"))
        self._confirmed_collapsible.set_summary(self._confirmed_section.summary_text())

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Refresh translated text when Qt installs a new translator."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_ui()
