"""Coordinate dock layout and mode panel composition for the GUI shell."""
# mypy: disable-error-code="attr-defined"

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.core.absorption_display import format_region_display
from chappy.core.editing_mode import EditingMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.common.range_selector import RangeSelectorWidget
from chappy.gui.modes.analysis.contracts import BottomPage
from chappy.gui.modes.analysis.overview.adapters import (
    StructureHistoryRecorder,
    StructureOperationAdapter,
)
from chappy.gui.modes.analysis.overview.delete_confirmation import confirm_structure_delete
from chappy.gui.modes.analysis.overview.interaction_coordinator import (
    StructureInteractionCoordinator,
    StructureInteractionPorts,
)
from chappy.gui.modes.analysis.overview.operation_controller import StructureOperationController
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from chappy.gui.modes.analysis.overview.review_controller import AnalysisOverviewReviewController
from chappy.gui.modes.analysis.overview.review_widget import AnalysisOverviewReviewWidget
from chappy.gui.modes.analysis.overview.summary_panel import AnalysisOverviewSummaryPanel
from chappy.gui.modes.analysis.overview.unlink_confirmation import confirm_structure_unlink
from chappy.gui.modes.analysis.region_detail import (
    OptimizeContextMenuController,
    OptimizeContextMenuRequest,
    OptimizeSpectrumIntegration,
    OptimizeSpectrumInteractionCoordinatorPort,
    OptimizeSpectrumPanelPort,
)
from chappy.gui.modes.analysis.region_detail.editor import OptimizeEditor
from chappy.gui.modes.analysis.workspace import (
    AnalysisWorkspace,
    AnalysisWorkspaceAccessibility,
    AnalysisWorkspacePages,
)
from chappy.gui.modes.common import ModePanelRegistration, ModePanelRegistry
from chappy.gui.modes.continuum import ContinuumEditor, create_continuum_registration
from chappy.gui.modes.identify import create_identify_registration
from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
from chappy.gui.modes.mode_panel_host import ModeSidePanelHost
from chappy.gui.shell.absorber_editor import AbsorberEditor
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.shortcuts import format_runtime_shortcuts, get_runtime_shortcut_display
from chappy.gui.shell.status_bar import StatusBarController
from chappy.gui.theme import Colors
from chappy.gui.visual_tokens import LayoutMetrics
from chappy.i18n import get_language_switcher

logger = logging.getLogger(__name__)


class _AnalysisAnnouncementAdapter:
    """Publish accessible Analysis alerts through the existing status surface."""

    def __init__(self, emit: Callable[[str, int], None]) -> None:
        self._emit = emit

    def announce(self, message: str) -> None:
        """Publish one message long enough for assistive technology to observe."""
        self._emit(message, 5000)


if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.modes.analysis.region_detail.model_addition_controller import (
        OptimizeModelAdditionUseCasePort,
    )
    from chappy.gui.modes.analysis.region_detail.ui_facade import RegionDetailUi
    from chappy.gui.modes.common.analysis_navigation import (
        AnalysisOverviewNavigationPort,
        AnalysisRegionFocusPort,
    )
    from chappy.gui.modes.mode_state_store import ModeStateStore
    from chappy.gui.protocols.context_menu import ContextMenuActionDescriptor
    from chappy.gui.shell.dependencies import RegionDetailFactory
    from chappy.gui.shell.mode_context_bar import ModeContextBar
    from chappy.gui.shell.mode_shell_coordinator import ModeShellCoordinator
    from chappy.gui.shell.view_stack import ViewStack
    from chappy.gui.shell.window_layout_builder import AnalysisBottomPane, GripSplitter
    from chappy.gui.spectrum.spectrum_view import SpectrumView


@dataclass(frozen=True, slots=True)
class DockLayoutUiParts:
    """Typed shell UI references and callbacks used by dock layout."""

    current_project_provider: Callable[[], SpectroscopyProject | None] | None = None
    status_message_emitter: Callable[[str, int], None] | None = None
    mode_state_store: ModeStateStore | None = None
    analysis_region_focus: AnalysisRegionFocusPort | None = None
    analysis_overview_navigation: AnalysisOverviewNavigationPort | None = None
    open_analysis_region: Callable[[str], bool] | None = None
    back_to_analysis_overview: Callable[[], bool] | None = None
    open_analysis_structure: Callable[[], bool] | None = None
    mode_shell_coordinator: ModeShellCoordinator | None = None
    view_stack: ViewStack | None = None
    mode_context_bar: ModeContextBar | None = None
    status_controller: StatusBarController | None = None
    structure_history_recorder: StructureHistoryRecorder | None = None
    is_velocity_plot_visible: Callable[[], bool] | None = None
    toggle_velocity_plot_optimize: Callable[[], None] | None = None
    refresh_visible_optimize_velocity_overlay: Callable[[], None] | None = None


class DockLayoutCoordinator(QObject):
    """Coordinate dock widget lifecycle and layout.

    This class handles creation, configuration, and management of all
    dock widgets in the main window, including component panels and
    range selectors.
    """

    def __init__(
        self,
        main_window: QMainWindow,
        side_panel_container: QWidget,
        *,
        optimize_model_addition_usecase: OptimizeModelAdditionUseCasePort,
        region_detail_factory: RegionDetailFactory,
    ) -> None:
        """Initialize dock layout coordinator.

        Args:
            main_window: Parent main window instance
            side_panel_container: Placeholder widget provided by layout builder
            optimize_model_addition_usecase: Use case passed to optimize mode panel.
            region_detail_factory: Factory composing the Region Detail UI facade.
        """
        super().__init__()
        self.main_window = main_window
        self.side_panel_container = side_panel_container
        self._optimize_model_addition_usecase = optimize_model_addition_usecase
        self._region_detail_factory = region_detail_factory
        self._panel_stack: QStackedLayout | None = None
        self._ui_parts = DockLayoutUiParts()

        # Track created dock widgets
        self.docks: dict[str, QWidget] = {}

        # Component editors
        self.absorber_editor: AbsorberEditor | None = None
        self.continuum_editor: ContinuumEditor | None = None
        self.optimize_editor: OptimizeEditor | None = None
        self._region_detail_ui: RegionDetailUi | None = None
        self.identify_panel: IdentifySidePanel | None = None
        self.range_selector: RangeSelectorWidget | None = None
        self.mode_panel: ModeSidePanelHost | None = None
        self.structure_panel: StructureSidePanel | None = None
        self.analysis_workspace: AnalysisWorkspace | None = None
        self._overview_review_controller: AnalysisOverviewReviewController | None = None
        self._analysis_bottom_pane: AnalysisBottomPane | None = None
        self._analysis_center_splitter: GripSplitter | None = None
        self._analysis_bottom_restore_height: int | None = None
        self._analysis_bottom_pane_sized = False
        self._language_switcher = get_language_switcher(self)
        self._language_switcher.language_changed.connect(self._on_language_changed)
        self._optimize_integration: OptimizeSpectrumIntegration | None = None
        self._optimize_context_menu = OptimizeContextMenuController(self)
        self._structure_operations = StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase()),
            status_callback=self._emit_status,
            parent=self,
        )
        self._structure_interactions = StructureInteractionCoordinator(
            operations=self._structure_operations,
            ports=StructureInteractionPorts(
                project_provider=self._current_project,
                history_recorder_provider=self._structure_history_recorder,
                focus_range_callback=self._focus_wavelength_range,
                status_callback=self._emit_structure_status,
                delete_confirmation=lambda impact, project: confirm_structure_delete(
                    self.main_window,
                    impact,
                    project,
                    undo_shortcut=get_runtime_shortcut_display(ShellActionId.UNDO),
                ),
                unlink_confirmation=lambda impact, project: confirm_structure_unlink(
                    self.main_window, impact, project
                ),
                context_menu_parent=self.main_window,
            ),
            parent=self,
        )

    def set_ui_parts(self, ui_parts: DockLayoutUiParts) -> None:
        """Inject typed shell UI references used by the dock layout."""
        self._ui_parts = ui_parts

    def _mode_state_store(self) -> ModeStateStore | None:
        """Return the configured mode state store."""
        return self._ui_parts.mode_state_store or self.main_window.mode_state_store

    def _require_mode_state_store(self) -> ModeStateStore:
        """Return the configured mode state store or fail fast."""
        mode_state_store = self._mode_state_store()
        if mode_state_store is None:
            msg = "Mode state store is required for dock layout coordination."
            raise RuntimeError(msg)
        return mode_state_store

    def _require_analysis_region_focus(self) -> AnalysisRegionFocusPort:
        """Return the canonical Analysis focus port or fail fast."""
        focus_port = self._ui_parts.analysis_region_focus or cast(
            "AnalysisRegionFocusPort | None",
            getattr(self.main_window, "_analysis_navigation", None),
        )
        if focus_port is None:
            msg = "Analysis region focus port is required for Region Detail."
            raise RuntimeError(msg)
        return focus_port

    def _require_analysis_overview_navigation(self) -> AnalysisOverviewNavigationPort:
        """Return the project-scoped Overview navigation port."""
        navigation = self._ui_parts.analysis_overview_navigation or cast(
            "AnalysisOverviewNavigationPort | None",
            getattr(self.main_window, "_analysis_navigation", None),
        )
        if navigation is None:
            msg = "Analysis Overview navigation port is required for Overview."
            raise RuntimeError(msg)
        return navigation

    def _mode_shell_coordinator(self) -> ModeShellCoordinator | None:
        """Return the configured mode shell coordinator."""
        return self._ui_parts.mode_shell_coordinator or self.main_window.mode_shell_coordinator

    def _view_stack(self) -> ViewStack | None:
        """Return the configured view stack."""
        return self._ui_parts.view_stack or self.main_window.view_stack

    def _mode_context_bar(self) -> ModeContextBar | None:
        """Return the configured mode context bar."""
        return self._ui_parts.mode_context_bar or self.main_window.mode_context_bar

    def _status_controller(self) -> StatusBarController | None:
        """Return the configured status controller."""
        return self._ui_parts.status_controller or self.main_window.status_controller

    def _refresh_line_overlays_for_mode(self, mode: EditingMode) -> None:
        """Refresh shell line overlays for the provided mode."""
        mode_shell_coordinator = self._mode_shell_coordinator()
        if mode_shell_coordinator is None:
            msg = "Mode shell coordinator is required for overlay refresh."
            raise RuntimeError(msg)
        mode_shell_coordinator.refresh_line_overlays_for_mode(mode)

    def _refresh_visible_optimize_velocity_plot(self) -> None:
        """Refresh the shared optimize velocity plot when visible."""
        callback = self._ui_parts.refresh_visible_optimize_velocity_overlay
        if callback is not None:
            callback()
            return
        self.main_window.optimize_velocity_runtime.refresh_visible_velocity_overlay()

    def refresh_visible_optimize_velocity_plot(self) -> None:
        """Refresh the visible Optimize velocity plot for history application."""
        self._refresh_visible_optimize_velocity_plot()

    def refresh_optimize_wavelength_model_residual(self, region_id: str) -> bool:
        """Refresh selected-region wavelength curves without recalculating the model."""
        return self._require_spectrum_view().refresh_selected_region_model_residual(region_id)

    def _is_velocity_plot_visible(self) -> bool:
        """Return optimize velocity plot visibility."""
        callback = self._ui_parts.is_velocity_plot_visible
        if callback is not None:
            return callback()
        return bool(self.main_window._is_velocity_plot_visible())

    def _toggle_velocity_plot_optimize(self) -> None:
        """Toggle optimize velocity plot via configured callback."""
        callback = self._ui_parts.toggle_velocity_plot_optimize
        if callback is not None:
            callback()
            return
        self.main_window.optimize_velocity_runtime.toggle_velocity_overlay()

    def _emit_shell_status_message(self, message: str, timeout_ms: int) -> None:
        """Emit a shell status message through the configured callback."""
        callback = self._ui_parts.status_message_emitter
        if callback is not None:
            callback(message, timeout_ms)
            return
        self.main_window.status_message.emit(message, timeout_ms)

    def _require_spectrum_view(self) -> SpectrumView:
        """Return the configured spectrum view or fail fast."""
        view_stack = self._view_stack()
        if view_stack is None or view_stack.spectrum_view is None:
            msg = "Spectrum view is required for dock layout coordination."
            raise RuntimeError(msg)
        return view_stack.spectrum_view

    def selected_structure_line_ids(self) -> list[str]:
        """Return selected structure line IDs."""
        return list(self._structure_interactions.selection[1])

    def refresh_structure_panel(self) -> None:
        """Refresh the structure panel and reapply the current structure selection."""
        structure_panel = self._required_structure_panel()

        region_ids, line_ids = self._structure_interactions.selection
        structure_panel.refresh()
        structure_panel.restore_selection(region_ids, line_ids)

    def refresh_optimize_panel_for_history(self, region_id: str | None) -> None:
        """Refresh the optimize panel after a history operation.

        Args:
            region_id: Optional region ID for targeted refresh.
        """
        self._require_region_detail_ui().refresh_for_history(region_id)

    def create_component_dock(self) -> QWidget:
        """Create and configure the main component side panel.

        Returns:
            Configured component panel container
        """
        mode_panel = self._build_mode_panel()

        self._mount_side_panel(mode_panel)
        self.docks["component_dock"] = self.side_panel_container
        return self.side_panel_container

    def _build_mode_panel(self) -> ModeSidePanelHost:
        mode_panel = ModeSidePanelHost()
        self.mode_panel = mode_panel
        registry = ModePanelRegistry()

        project = self._current_project()
        mode_state_store = self._require_mode_state_store()
        mode_shell_coordinator = self._mode_shell_coordinator()
        if mode_shell_coordinator is None:
            msg = "Mode shell coordinator is required to build mode panels."
            raise RuntimeError(msg)
        summary_panel = AnalysisOverviewSummaryPanel(mode_panel)
        review_widget = AnalysisOverviewReviewWidget(
            self._require_analysis_overview_navigation(), mode_panel, summary_panel=summary_panel
        )
        self.structure_panel = StructureSidePanel(
            parent=mode_panel,
            navigation=self._require_analysis_overview_navigation(),
            review=review_widget,
            embed_review=False,
        )
        self._overview_review_controller = AnalysisOverviewReviewController(
            view=self.structure_panel, project_provider=self._current_project, parent=self
        )
        self.structure_panel.review_refresh_requested.connect(
            self._overview_review_controller.refresh
        )
        self.structure_panel.region_open_requested.connect(self._open_analysis_region)
        self.structure_panel.region_delete_requested.connect(self._delete_analysis_region)
        self.structure_panel.back_requested.connect(self._back_to_analysis_overview)
        review_widget.structure_edit_requested.connect(
            lambda _region_id: self._open_analysis_structure()
        )
        self._overview_review_controller.refresh()
        self._structure_interactions.connect_panel(self.structure_panel)

        self.absorber_editor = AbsorberEditor(
            parent=None, project=project, mode_state_store=mode_state_store
        )

        self.continuum_editor = ContinuumEditor(
            parent=mode_panel, project=project, mode_state_store=mode_state_store
        )
        self._connect_continuum_interaction_controller()
        registry.register(
            create_continuum_registration(
                self.continuum_editor,
                mode_shell_coordinator.lifecycle_for_mode(EditingMode.CONTINUUM),
            )
        )

        self.identify_panel = IdentifySidePanel(
            parent=mode_panel, project=project, mode_state_store=mode_state_store
        )
        registry.register(
            create_identify_registration(
                self.identify_panel,
                mode_shell_coordinator.lifecycle_for_mode(EditingMode.IDENTIFY),
            )
        )

        self.optimize_editor = OptimizeEditor(
            parent=None, project=project, mode_state_store=mode_state_store
        )

        self._region_detail_ui = self._region_detail_factory(
            optimize_editor=self.optimize_editor,
            analysis_focus=self._require_analysis_region_focus(),
            mode_state=mode_state_store,
            model_addition_usecase=self._optimize_model_addition_usecase,
            velocity_plot_active_provider=self._is_velocity_plot_visible,
            project_file_path_provider=lambda: self.main_window.project_file_path,
            parent=mode_panel,
        )
        self._region_detail_ui.back_to_overview_requested.connect(self._back_to_analysis_overview)
        self.analysis_workspace = AnalysisWorkspace(
            AnalysisWorkspacePages(
                summary=summary_panel,
                structure=self.structure_panel,
                detail=self._region_detail_ui.panel,
                review=review_widget,
                parameters=self._region_detail_ui.parameter_tree_widget(),
            ),
            accessibility=AnalysisWorkspaceAccessibility(
                right_stack_name=self.tr("Analysis tools"),
                bottom_stack_name=self.tr("Analysis review and parameters"),
            ),
            announcement_port=_AnalysisAnnouncementAdapter(self._emit_shell_status_message),
            parent=mode_panel,
        )
        registry.register(
            ModePanelRegistration(
                mode=EditingMode.ANALYSIS,
                panel=self.analysis_workspace.right_stack,
                lifecycle=mode_shell_coordinator.lifecycle_for_mode(EditingMode.ANALYSIS),
            )
        )
        self._region_detail_ui.export_feedback.connect(self._handle_optimize_export_feedback)
        self._region_detail_ui.operation_feedback.connect(self._handle_optimize_export_feedback)
        self._region_detail_ui.line_analysis_half_width_changed.connect(
            self._handle_optimize_analysis_half_width_changed
        )

        # Setup optimize spectrum integration after panel creation
        # This will be called later when view_stack is available

        registry.install_into(mode_panel)
        return mode_panel

    def _mount_side_panel(self, mode_panel: ModeSidePanelHost) -> None:
        # Clear existing layout if present
        if layout := self.side_panel_container.layout():
            while layout.count():
                item = layout.takeAt(0)
                if item is not None and (widget := item.widget()) is not None:
                    widget.deleteLater()
            layout.deleteLater()

        stack = QStackedLayout()
        stack.setContentsMargins(0, 0, 0, 0)

        placeholder = QWidget(self.side_panel_container)
        placeholder.setObjectName("sidePanelEmptyState")
        placeholder.setStyleSheet(
            "#sidePanelEmptyState {"
            f" background-color: {Colors.BACKGROUND_PANEL};"
            f" border-left: 1px solid {Colors.BORDER_DEFAULT};"
            "}"
        )
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.addStretch()

        component_wrapper = QWidget(self.side_panel_container)
        component_wrapper.setObjectName("sidePanelActiveState")
        component_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        component_wrapper.setStyleSheet(
            "#sidePanelActiveState {"
            f" background-color: {Colors.BACKGROUND_PANEL};"
            f" border-left: 1px solid {Colors.BORDER_DEFAULT};"
            "}"
        )
        wrapper_layout = QVBoxLayout(component_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(mode_panel)

        stack.addWidget(placeholder)
        stack.addWidget(component_wrapper)
        stack.setCurrentIndex(1)

        self.side_panel_container.setLayout(stack)
        self._apply_side_panel_style()
        self._panel_stack = stack

    def _apply_side_panel_style(self) -> None:
        background = Colors.BACKGROUND_PANEL
        self.side_panel_container.setStyleSheet(
            "#sidePanelPlaceholder {"
            f" background-color: {background};"
            f" border-left: 1px solid {Colors.BORDER_DEFAULT};"
            "}"
        )

    def set_panel_active(self, active: bool) -> None:
        """Toggle between the empty placeholder and active component panel."""
        if not self._panel_stack:
            return

        target_index = 1 if active else 0
        if self._panel_stack.currentIndex() != target_index:
            self._panel_stack.setCurrentIndex(target_index)

    def create_range_selector_dock(self) -> QDockWidget:
        """Create and configure the range selector dock widget.

        Returns:
            Configured range selector dock widget
        """
        # Create range selector dock
        range_dock = QDockWidget(self.tr("Fitting Ranges"), self.main_window)
        range_dock.setObjectName("range_dock")

        range_dock.setAllowedAreas(
            Qt.DockWidgetArea.TopDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        # Create range selector widget
        self.range_selector = RangeSelectorWidget()

        range_dock.setWidget(self.range_selector)

        # Add dock to bottom area (initially hidden)
        self.main_window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, range_dock)

        # DISABLED: Hide permanently - using integrated spectrum view group creation instead
        range_dock.setVisible(False)
        range_dock.setEnabled(False)

        # Store reference
        self.docks["range_dock"] = range_dock

        logger.info("✓ Range selector dock setup complete - visible: %s", range_dock.isVisible())

        return range_dock

    def attach_analysis_bottom_pane(
        self, pane: AnalysisBottomPane, splitter: GripSplitter
    ) -> None:
        """Host the Analysis bottom stack inside the central vertical splitter."""
        if self.analysis_workspace is None:
            msg = "Analysis workspace is required to attach its bottom pane."
            raise RuntimeError(msg)

        pane.attach_content(self.analysis_workspace.bottom_stack)
        pane.hide()
        self._analysis_bottom_pane = pane
        self._analysis_center_splitter = splitter
        self.analysis_workspace.bottom_stack.currentChanged.connect(
            self._refresh_analysis_bottom_pane_title
        )
        splitter.handle_double_clicked.connect(self._toggle_analysis_bottom_pane_maximized)
        self._refresh_analysis_bottom_pane_title()

    def _analysis_bottom_pane_title(self) -> str:
        """Return the surface-following header for the Analysis bottom pane."""
        workspace = self.analysis_workspace
        if workspace is not None and workspace.current_bottom_page is BottomPage.PARAMETERS:
            region_label = self._analysis_detail_region_label()
            if region_label:
                return f"{self.tr('Parameters')} — {region_label}"
            return self.tr("Parameters")
        return self.tr("Region list")

    def _analysis_detail_region_label(self) -> str | None:
        """Return the focused Detail region's display name when resolvable."""
        region_detail_ui = self._region_detail_ui
        if region_detail_ui is None:
            return None
        region_id = region_detail_ui.current_region_id()
        if region_id is None:
            return None
        project = self._current_project()
        if project is None:
            return None
        region = project.absorption_regions.get(region_id)
        if region is None:
            return None
        lines = [
            project.absorption_lines[line_id]
            for line_id in region.line_ids
            if line_id in project.absorption_lines
        ]
        if not lines:
            return None
        return format_region_display(lines, region.analysis_range).display_name

    def refresh_analysis_bottom_pane_title(self) -> None:
        """Re-render the pane header after the focused Detail region changed."""
        self._refresh_analysis_bottom_pane_title()

    def _refresh_analysis_bottom_pane_title(self, *_: object) -> None:
        """Re-title the bottom pane after a surface or language change."""
        if self._analysis_bottom_pane is not None:
            self._analysis_bottom_pane.set_title(self._analysis_bottom_pane_title())

    def _update_analysis_bottom_pane(self, mode: EditingMode | None) -> None:
        """Show the bottom pane only for the top-level Analysis mode."""
        pane = self._analysis_bottom_pane
        if pane is None:
            return
        active = mode is EditingMode.ANALYSIS
        pane.setVisible(active)
        if active:
            self._refresh_analysis_bottom_pane_title()
            self._apply_initial_analysis_bottom_pane_height()

    def mark_analysis_bottom_pane_height_restored(self) -> None:
        """Keep a persisted splitter height instead of the default ratio."""
        self._analysis_bottom_pane_sized = True

    def _apply_initial_analysis_bottom_pane_height(self) -> None:
        """Give the bottom pane roughly 30% of the splitter on first entry.

        Skipped once a persisted splitter state was restored or the default
        was already applied; the spectrum keeps its 240px content contract.
        """
        splitter = self._analysis_center_splitter
        pane = self._analysis_bottom_pane
        if splitter is None or pane is None or self._analysis_bottom_pane_sized:
            return
        total = splitter.height() - splitter.handleWidth()
        minimum = pane.minimumSizeHint().height()
        if total < LayoutMetrics.SPECTRUM_MIN_HEIGHT + minimum:
            return
        preferred = max(minimum, int(total * 0.30))
        preferred = min(preferred, total - LayoutMetrics.SPECTRUM_MIN_HEIGHT)
        self._analysis_bottom_pane_sized = True
        splitter.setSizes([total - preferred, preferred])

    def _toggle_analysis_bottom_pane_maximized(self) -> None:
        """Flip between a maximized bottom pane and the last user height."""
        splitter = self._analysis_center_splitter
        pane = self._analysis_bottom_pane
        if splitter is None or pane is None or pane.isHidden():
            return
        sizes = splitter.sizes()
        total = sum(sizes)
        maximized = total - LayoutMetrics.SPECTRUM_MIN_HEIGHT
        if maximized <= pane.minimumSizeHint().height():
            return
        if sizes[1] >= maximized:
            restore = self._analysis_bottom_restore_height or max(
                pane.minimumSizeHint().height(), int(total * 0.30)
            )
            restore = min(restore, maximized)
            splitter.setSizes([total - restore, restore])
            return
        self._analysis_bottom_restore_height = sizes[1]
        splitter.setSizes([LayoutMetrics.SPECTRUM_MIN_HEIGHT, maximized])

    def _on_language_changed(self, _code: str) -> None:
        """Re-apply translated titles owned by the dock layout."""
        self._refresh_analysis_bottom_pane_title()

    def get_component_editors(
        self,
    ) -> tuple[AbsorberEditor | None, ContinuumEditor | None, OptimizeEditor | None]:
        """Get references to component editors.

        Returns:
            Tuple of (absorber_editor, continuum_editor, optimize_editor)
        """
        return self.absorber_editor, self.continuum_editor, self.optimize_editor

    def _connect_continuum_interaction_controller(self) -> None:
        """Inject the continuum-owned interaction controller into the spectrum input."""
        if self.continuum_editor is None:
            msg = "Continuum editor is required to create continuum interaction controller."
            raise RuntimeError(msg)

        spectrum_view = self._require_spectrum_view()

        input_adapter = spectrum_view.spectrum_input_adapter
        controller = self.continuum_editor.create_interaction_controller(
            snapshot_consumer=input_adapter.consume_interaction_snapshot,
            current_points=input_adapter.current_continuum_points,
        )
        input_adapter.set_continuum_interaction_controller(controller)

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Set project for all component editors.

        Args:
            project: Project instance to set
        """
        if self.optimize_editor:
            self.optimize_editor.set_project(project)
        if self._region_detail_ui:
            self._region_detail_ui.set_project(project)
        elif self.absorber_editor:
            self.absorber_editor.set_project(project)
        if self.continuum_editor:
            self.continuum_editor.set_project(project)
        if self.identify_panel:
            self.identify_panel.set_project(project)
            self.identify_panel.attach_mode_state_store(self._require_mode_state_store())
        if self.structure_panel:
            self.structure_panel.set_project(project)
            self._structure_interactions.set_panel(self.structure_panel)
        self._structure_interactions.clear_selection_state()

    def _focus_wavelength_range(self, min_wave: float, max_wave: float) -> None:
        spectrum_view = self._require_spectrum_view()
        spectrum_view.coordinator.coordinate_range_update(
            "structure-focus", min_wave, max_wave, record_history=False
        )
        self._emit_shell_status_message(
            self.tr("Focused spectrum to {minimum:.1f}–{maximum:.1f} Å").format(
                minimum=min_wave, maximum=max_wave
            ),
            2000,
        )

    def _handle_structure_line_move(self, target_region_id: str, line_ids: list[str]) -> None:
        self._sync_structure_panel_port()
        self._structure_interactions.handle_line_move(target_region_id, line_ids)

    def _execute_structure_merge(self) -> bool:
        self._sync_structure_panel_port()
        return self._structure_interactions.execute_merge()

    def _execute_structure_split(self) -> bool:
        self._sync_structure_panel_port()
        return self._structure_interactions.execute_split()

    def _execute_structure_delete(self) -> bool:
        self._sync_structure_panel_port()
        return self._structure_interactions.execute_delete()

    def _delete_analysis_region(self, region_id: str) -> None:
        """Delete one review-table region through the shared structure delete path."""
        self._sync_structure_panel_port()
        self._structure_interactions.handle_selection([region_id], [])
        self._structure_interactions.execute_delete()

    def _open_analysis_region(self, region_id: str) -> None:
        """Forward an explicit Overview intent to the Analysis surface owner."""
        callback = self._ui_parts.open_analysis_region
        if callback is None:
            msg = "Analysis surface coordinator is required to open Region Detail."
            raise RuntimeError(msg)
        callback(region_id)

    def _back_to_analysis_overview(self) -> None:
        """Forward the visible Detail back action to the surface owner."""
        callback = self._ui_parts.back_to_analysis_overview
        if callback is None:
            msg = "Analysis surface coordinator is required to return to Overview."
            raise RuntimeError(msg)
        callback()

    def _open_analysis_structure(self) -> None:
        """Forward Structure entry to the Analysis surface owner."""
        callback = self._ui_parts.open_analysis_structure
        if callback is None:
            msg = "Analysis surface coordinator is required to open Structure."
            raise RuntimeError(msg)
        callback()

    def _sync_structure_panel_port(self) -> None:
        """Synchronize the current structure panel reference with the mode coordinator."""
        if self.structure_panel is not None:
            self._structure_interactions.set_panel(self.structure_panel)

    def _required_structure_panel(self) -> StructureSidePanel:
        """Return the required structure panel or fail on missing composition."""
        if self.structure_panel is None:
            msg = "Dock layout coordinator requires a structure panel."
            raise RuntimeError(msg)
        return self.structure_panel

    def _require_region_detail_ui(self) -> RegionDetailUi:
        """Return the required Region Detail UI facade or fail on missing composition."""
        if self._region_detail_ui is None:
            msg = "Dock layout coordinator requires an optimize panel."
            raise RuntimeError(msg)
        return self._region_detail_ui

    def _current_project(self) -> SpectroscopyProject | None:
        """Return the current project exposed by the main window."""
        provider = self._ui_parts.current_project_provider
        project = provider() if provider is not None else self.main_window.current_project
        return project if isinstance(project, SpectroscopyProject) else None

    def _structure_history_recorder(self) -> StructureHistoryRecorder | None:
        """Return the structure history recorder exposed by the main window."""
        candidate = self._ui_parts.structure_history_recorder or self.main_window._history_recorder
        if isinstance(candidate, StructureHistoryRecorder):
            return candidate
        msg = "Main window history recorder does not implement Analysis Structure recording."
        raise RuntimeError(msg)

    def _emit_status(
        self, message: str, timeout_ms: int = 2500, *, undo_hint: bool = False
    ) -> None:
        if undo_hint:
            #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
            undo_hint_text = format_runtime_shortcuts(self.tr("Press {undo_shortcut} to undo"))
            message = f"{message} {undo_hint_text}"
        self._emit_shell_status_message(message, timeout_ms)

    def _emit_structure_status(
        self, message: str, timeout_ms: int = 2500, undo_hint: bool = False
    ) -> None:
        """Emit a structure status message from the mode coordinator."""
        self._emit_status(message, timeout_ms, undo_hint=undo_hint)

    def _handle_optimize_export_feedback(self, message: str, timeout_ms: int, level: str) -> None:
        """Route optimize export notifications to the shared status bar."""
        status_controller = self._status_controller()
        if isinstance(status_controller, StatusBarController):
            status_controller.show_message(message, timeout_ms, level)
            return
        msg = "Main window status_controller is not configured."
        raise RuntimeError(msg)

    def _handle_optimize_analysis_half_width_changed(self, region_id: str) -> None:
        """Refresh Optimize spectrum surfaces after a scientific range edit."""
        self.refresh_optimize_wavelength_model_residual(region_id)
        self._refresh_line_overlays_for_mode(EditingMode.ANALYSIS)
        self._refresh_visible_optimize_velocity_plot()

    def activate_mode(self, mode: EditingMode | None) -> None:
        """Activate the side panel associated with the provided mode."""
        self._update_analysis_bottom_pane(mode)

        if not self.mode_panel:
            return
        self.mode_panel.activate_mode(mode)

        if mode == EditingMode.ANALYSIS and self.structure_panel and self._region_detail_ui:
            self._structure_interactions.refresh_active_panel()
            self._region_detail_ui.refresh()
            self.setup_optimize_integration()

    def setup_optimize_integration(self) -> None:
        """Setup integration between optimize panel and spectrum presenter.

        This should be called after both the optimize panel and spectrum view are initialized.
        """
        if not self._region_detail_ui or self._optimize_integration:
            return

        # Get spectrum presenter from view stack
        spectrum_interaction_coordinator = self._require_spectrum_view().coordinator
        if not isinstance(
            spectrum_interaction_coordinator, OptimizeSpectrumInteractionCoordinatorPort
        ):
            msg = "Spectrum interaction facade does not implement optimize integration port."
            raise TypeError(msg)

        if not isinstance(self._region_detail_ui, OptimizeSpectrumPanelPort):
            msg = "Analysis Region Detail panel does not implement spectrum integration port."
            raise TypeError(msg)

        # Create integration between spectrum and optimize panel
        self._optimize_integration = OptimizeSpectrumIntegration(
            spectrum_interaction_coordinator,
            self._region_detail_ui,
            velocity_visible_provider=self._is_velocity_plot_visible,
            velocity_toggle_callback=self._toggle_velocity_plot_optimize,
            cursor_feedback_callback=spectrum_interaction_coordinator.apply_optimize_cursor_mode,
            context_menu_action_provider=self._optimize_context_menu_actions,
        )

        # Set integration in presenter
        spectrum_interaction_coordinator.attach_optimize_integration(self._optimize_integration)

        spectrum_view = self._require_spectrum_view()
        spectrum_view.set_tie_label_resolver(self._region_detail_ui.tie_label_for_redshift)
        spectrum_view.set_velocity_tie_member_resolver(
            self._region_detail_ui.tie_member_ids_for_redshift
        )

    def _optimize_context_menu_actions(
        self,
        wavelength: float,
        can_add_component: bool,
        has_selected_line: bool,
        has_selected_region: bool,
        velocity_plot_visible: bool,
    ) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return optimize context menu actions from the mode-local controller."""
        return self._optimize_context_menu.actions_for_request(
            OptimizeContextMenuRequest(
                wavelength=wavelength,
                can_add_component=can_add_component,
                has_selected_line=has_selected_line,
                has_selected_region=has_selected_region,
                velocity_plot_visible=velocity_plot_visible,
            )
        )

    def optimize_context_menu_actions(
        self, wavelength: float
    ) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return optimize context menu actions for a spectrum position."""
        if self._optimize_integration is None:
            return ()
        return self._optimize_integration.context_menu_actions(wavelength)

    def optimize_integration(self) -> OptimizeSpectrumIntegration | None:
        """Return the optimize spectrum integration if it has been created."""
        return self._optimize_integration

    def region_detail_ui(self) -> RegionDetailUi | None:
        """Return the Region Detail UI facade if it has been composed."""
        return self._region_detail_ui

    def analysis_current_region_id(self) -> str | None:
        """Return the region currently focused in Analysis Detail."""
        if self._region_detail_ui is None:
            return None
        return self._region_detail_ui.current_region_id()
