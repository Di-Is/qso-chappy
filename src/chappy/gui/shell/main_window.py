"""Main application window for Chappy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QSettings, Signal, Slot
from PySide6.QtWidgets import QDockWidget, QMainWindow, QProgressBar, QWidget

from chappy.application.analysis_artifacts import DeriveAnalysisReadinessUseCase
from chappy.application.history import HistoryRecorder
from chappy.application.optimize import CosmologyChangeNotifier
from chappy.application.spectrum import ResolutionUpdateUseCase
from chappy.core.absorption import UNASSIGNED_REGION_ID
from chappy.core.analysis import AnalysisReadiness
from chappy.core.editing_mode import EditingMode
from chappy.core.history import CommandHistory, HistoryState
from chappy.core.presets import METAL_LINES_PRESET_ID
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.adapters.model_event_adapter import SpectrumModelEventAdapter
from chappy.gui.common.shared_operations import AnalysisOperationPanel, AnalysisOperationSurface
from chappy.gui.common.tutorial import (
    COMPLETION_NOTE_SOURCES,
    FIT_OUTCOME_NOTE_SOURCES,
    TutorialCompletion,
    TutorialPrerequisite,
)
from chappy.gui.dialogs.welcome_dialog import WelcomeDialog
from chappy.gui.history.bridge import HistoryBridge
from chappy.gui.modes.analysis.contracts import PanelState
from chappy.gui.modes.analysis.intents import OpenAnalysisRegionIntent, OpenAnalysisStructureIntent
from chappy.gui.modes.analysis.surface_coordinator import AnalysisSurfaceCoordinator
from chappy.gui.modes.common.analysis_navigation import AnalysisSurface
from chappy.gui.modes.identify.velocity_plot_controller import IdentifyVelocityRangePort
from chappy.gui.protocols.intent_types import ZoomFactorIntent
from chappy.gui.shell.absorber_coordinator import AbsorberEditorSignalPort
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.analysis_surface_ui_adapter import (
    AnalysisSurfacePresentationAdapter,
    AnalysisSurfaceUiAdapter,
    AnalysisSurfaceUiPorts,
)
from chappy.gui.shell.analysis_transition_guard_adapter import AnalysisTransitionGuardAdapter
from chappy.gui.shell.data_control_coordinator import (
    DataControlCoordinator,
    DataControlCoordinatorPorts,
)
from chappy.gui.shell.display_menu_controller import DisplayMenuController
from chappy.gui.shell.dock_layout_coordinator import DockLayoutUiParts
from chappy.gui.shell.mode_shell_coordinator import ModeShellCoordinator, ModeShellUiParts
from chappy.gui.shell.project_switch_coordinator import (
    ProjectSwitchCoordinator,
    ProjectSwitchPorts,
)
from chappy.gui.shell.resolution_update_adapter import (
    ResolutionChangeNotifier,
    ResolutionUpdateAdapter,
)
from chappy.gui.shell.signal_connector import (
    ShellSignalConnectorBindings,
    ShellSignalConnectorPorts,
)
from chappy.gui.shell.spectrum_region_focus_controller import SpectrumRegionFocusController
from chappy.gui.shell.tutorial_chapters import (
    build_advanced_walkthrough_chapters,
    build_essential_walkthrough_chapters,
)
from chappy.gui.shell.tutorial_start_override import resolve_tutorial_start_chapters
from chappy.gui.shell.tutorial_tour_controller import TutorialTourController
from chappy.gui.spectrum.spectrum_view import SpectrumView
from chappy.gui.theme import get_application_stylesheet
from chappy.i18n import LanguageSwitcher, get_language_switcher
from chappy.infrastructure.resources import resolve_data_path

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent

    from chappy.application.optimize import FitResultRawPayload
    from chappy.application.project_io_usecase import ProjectIOUseCase
    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.atomic_data import AtomicLineData
    from chappy.core.events import RegionTopologyChanged
    from chappy.core.presets import Preset
    from chappy.gui.common.range_selector import RangeSelectorWidget
    from chappy.gui.common.tutorial import TutorialChapter
    from chappy.gui.modes.analysis.region_detail.editor import OptimizeEditor
    from chappy.gui.modes.analysis.region_detail.model_addition_controller import (
        OptimizeModelAdditionUseCasePort,
    )
    from chappy.gui.modes.analysis.region_detail.runtime import OptimizeVelocityOverlayRuntimePort
    from chappy.gui.modes.continuum import ContinuumEditor, ContinuumHistoryRecorder
    from chappy.gui.modes.continuum.coordinator import ContinuumCoordinator
    from chappy.gui.modes.continuum.shared_surface_context_controller import (
        ContinuumSharedSurfaceContextController,
    )
    from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
    from chappy.gui.modes.identify.runtime import IdentifyVelocityOverlayRuntimePort
    from chappy.gui.modes.identify.velocity_plot_controller import IdentifyVelocityWorkflowPort
    from chappy.gui.modes.identify.workflow_ports import IdentifyModeCoordinatorPort
    from chappy.gui.modes.mode_state_store import ModeStateStore
    from chappy.gui.protocols.optimize_spectrum import SpectrumModeIntegrationPort
    from chappy.gui.shell.absorber_coordinator import AbsorberCoordinator
    from chappy.gui.shell.actions.dispatcher import ActionDispatcher
    from chappy.gui.shell.analysis_navigation_coordinator import AnalysisNavigationCoordinator
    from chappy.gui.shell.data_control_panel import DataControlPanel
    from chappy.gui.shell.dependencies import ShellRuntimeParts
    from chappy.gui.shell.dialog_workflow_coordinator import DialogWorkflowCoordinator
    from chappy.gui.shell.dock_layout_coordinator import DockLayoutCoordinator
    from chappy.gui.shell.history_wiring_coordinator import HistoryWiringCoordinator
    from chappy.gui.shell.menu_action_factory import MenuActionFactory
    from chappy.gui.shell.mode_context_bar import ModeContextBar
    from chappy.gui.shell.mode_shell_coordinator import ModeShellCoordinator
    from chappy.gui.shell.project_session_controller import ProjectSessionController
    from chappy.gui.shell.signal_connector import ShellSignalConnector
    from chappy.gui.shell.spectrum_surface_coordinator import SpectrumSurfaceCoordinator
    from chappy.gui.shell.status_bar import StatusBarController
    from chappy.gui.shell.view_stack import ViewStack
    from chappy.gui.shell.window_bootstrapper import WindowBootstrapper, WindowLifecycleCoordinator
    from chappy.gui.shell.window_layout_builder import WindowLayoutBuilder
    from chappy.presentation.interaction.interaction_contracts import OptimizeMaskGroupChange
    from chappy.presentation.spectrum import SpectrumDisplayOptions

logger = logging.getLogger(__name__)

_SAMPLE_FLUX_RESOURCE = ("sample_data", "J033106-382404_f.fits")
_SAMPLE_ERROR_RESOURCE = ("sample_data", "J033106-382404_e.fits")
# SQUAD DR1 nominal resolving power interpolated at the tutorial's C IV region
# (~4763 Å); provenance in sample_data/README.md.
_SAMPLE_RESOLVING_POWER = 54_000.0
_WELCOME_SHOWN_SETTINGS_KEY = "tutorial/welcome_shown"


def _find_sample_spectrum_pair() -> tuple[Path, Path] | None:
    """Locate the bundled sample flux/error FITS pair.

    Returns:
        Resolved flux and error paths, or None if the sample is not bundled.
    """
    flux_path = resolve_data_path(*_SAMPLE_FLUX_RESOURCE)
    error_path = resolve_data_path(*_SAMPLE_ERROR_RESOURCE)
    if flux_path is None or error_path is None:
        return None
    return flux_path, error_path


_TUTORIAL_PRESET_LINE_IDS = frozenset(
    {
        "580d9a1e59b77a82",  # Fe II 2374.5
        "b5ddd1f3fcc99c31",  # Fe II 2382.8
        "c63f98a2a68fc72d",  # Fe II 2586.6
        "74a08828146e7ef2",  # Fe II 2600.2
        "d85a4a9d4dfb3235",  # Mg II 2796.4
        "380d715c908636f5",  # Mg II 2803.5
    }
)
_TUTORIAL_REGION_LINES = frozenset(
    {
        ("Fe II", 2374.5),
        ("Fe II", 2382.8),
        ("Fe II", 2586.6),
        ("Fe II", 2600.2),
        ("Mg II", 2796.4),
        ("Mg II", 2803.5),
    }
)


class MainWindow(QMainWindow):
    """Main application window for chappy spectroscopy analysis.

    This is the primary GUI window that coordinates all views, coordinators,
    and provides the main user interface for the application.

    Uses composition pattern instead of mixins for better maintainability.

    Signals:
        project_changed: Emitted when current project changes
        status_message: Emitted to update status bar
    """

    # Qt signals
    project_changed = Signal(SpectroscopyProject)
    status_message = Signal(  # Qt signal follows framework naming convention
        str, int
    )  # message, timeout_ms

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        project_io_usecase: ProjectIOUseCase,
        atomic_data: AtomicLineData,
        preset_store: IdentifyPresetStore,
        optimize_model_addition_usecase: OptimizeModelAdditionUseCasePort,
        shell_parts_factory: Callable[[MainWindow], ShellRuntimeParts],
    ) -> None:
        """Initialize main window.

        Args:
            parent: Parent widget (usually None for main window)
            project_io_usecase: Project I/O use case for project file operations.
            atomic_data: Atomic line repository for identify workflows.
            preset_store: Qt-aware identify preset store facade.
            optimize_model_addition_usecase: Optimize model-addition use case.
            shell_parts_factory: Factory providing prebuilt shell collaborators.
        """
        super().__init__(parent)
        _ = project_io_usecase

        self._atomic_data = atomic_data
        self.preset_store: IdentifyPresetStore = preset_store
        self.preset_store.setParent(self)
        self._optimize_model_addition_usecase = optimize_model_addition_usecase

        # Shell collaborators are injected by the composition root.
        self._window_bootstrapper: WindowBootstrapper
        self._project_session: ProjectSessionController | None = None
        self._signal_connector: ShellSignalConnector
        self._window_lifecycle: WindowLifecycleCoordinator
        self._action_dispatcher: ActionDispatcher
        self._analysis_navigation: AnalysisNavigationCoordinator
        self._layout_builder: WindowLayoutBuilder | None = None
        self._action_factory: MenuActionFactory | None = None
        self._dock_coordinator: DockLayoutCoordinator | None = None
        self._data_control_coordinator: DataControlCoordinator | None = None
        self._display_menu_controller: DisplayMenuController | None = None
        self._progress_bar: QProgressBar | None = None
        self._analysis_surface_coordinator: AnalysisSurfaceCoordinator | None = None
        self._region_topology_event_adapter: SpectrumModelEventAdapter | None = None

        # UI components that will be created
        self.central_widget: QWidget | None = None
        self.view_stack: ViewStack | None = None
        self.range_selector: RangeSelectorWidget | None = None
        self.range_dock: QDockWidget | None = None
        self.mode_state_store: ModeStateStore | None = None
        self.mode_context_bar: ModeContextBar | None = None
        self.data_control_panel: DataControlPanel | None = None
        self.data_control_container: QWidget | None = None
        self.status_controller: StatusBarController | None = None
        self._language_switcher: LanguageSwitcher = get_language_switcher(self)
        self._resolution_updates = ResolutionUpdateAdapter(ResolutionUpdateUseCase())

        # Component references that will be set during setup
        self.absorber_editor: AbsorberEditorSignalPort | None = None
        self.continuum_editor: ContinuumEditor | None = None
        self.optimize_editor: OptimizeEditor | None = None
        self.mode_shell_coordinator: ModeShellCoordinator | None = None
        self._tutorial_tour: TutorialTourController | None = None
        self._tutorial_initial_preset_ids: frozenset[str] = frozenset()
        self._dialog_workflow: DialogWorkflowCoordinator
        self._history_wiring: HistoryWiringCoordinator
        self._spectrum_surface: SpectrumSurfaceCoordinator
        # History management (undo/redo)
        self._command_history = CommandHistory()
        self._history_bridge = HistoryBridge(self._command_history, parent=self)
        self._history_recorder = HistoryRecorder(
            self._command_history, lambda: self.current_project
        )
        self._history_bridge.set_resolution_change_notifier_provider(
            self._resolution_change_notifier
        )
        self._project_switch_coordinator: ProjectSwitchCoordinator

        shell_parts = shell_parts_factory(self)
        self._dialog_workflow = shell_parts.dialog_workflow
        self._history_wiring = shell_parts.history_wiring
        self._spectrum_surface = shell_parts.spectrum_surface
        self._velocity_overlay_port = shell_parts.velocity_overlay_port
        self._identify_runtime = shell_parts.identify_velocity_runtime
        self._optimize_runtime = shell_parts.optimize_velocity_runtime
        self._continuum_mode_runtime = shell_parts.continuum_mode_runtime
        self._configure_shell(shell_parts)

        # Apply global application theme
        self.setStyleSheet(get_application_stylesheet())

        # Setup UI components
        self._create_actions()  # Initialize action factory and coordinators
        self._setup_window()  # Setup window properties
        self._create_menus()  # Create menu bar
        self._create_status_bar()  # Create status bar
        self._create_central_widget()  # Create central widget

        # Cache shared UI components
        layout_builder = self._require_layout_builder()
        self.mode_context_bar = layout_builder.mode_context_bar
        self.data_control_panel = layout_builder.data_control_panel
        self.data_control_container = layout_builder.data_control_container
        self.status_controller = layout_builder.status_controller
        self._setup_data_control_coordinator()
        self._sync_bootstrap_parts()

        # Initialize mode state store BEFORE creating Dock layouts
        if self.mode_shell_coordinator:
            self.mode_shell_coordinator.setup_mode_state_store()
            self.mode_state_store = self.mode_shell_coordinator.mode_state_store
            if self.mode_state_store is None:
                msg = "Mode state store was not created"
                raise RuntimeError(msg)

        # Create Dock layouts after mode state store is initialized
        self._create_dock_widgets()

        # Setup handlers and connections
        self._setup_handlers()
        self._setup_coordinators()  # Setup coordinators
        self._connect_signals()  # Connect internal signals
        self._setup_event_handling()  # Setup event handling
        self._setup_project_handling()  # Setup project handling
        self._history_wiring.setup()
        self._spectrum_surface.setup()

        # Initialize mode UI state
        if self.mode_shell_coordinator:
            initial_mode = self.mode_shell_coordinator.get_current_mode()
            if initial_mode:
                self._on_coordinator_mode_changed(initial_mode)

        self._restore_settings()

    def _configure_shell(self, shell_parts: ShellRuntimeParts) -> None:
        """Bind composition-owned shell collaborators to the window."""
        self._window_bootstrapper = shell_parts.window_bootstrapper
        self._project_session = shell_parts.project_session
        project_session = self._require_project_session()
        self._signal_connector = shell_parts.signal_connector
        self._window_lifecycle = shell_parts.window_lifecycle
        self._action_dispatcher = shell_parts.action_dispatcher
        self._analysis_navigation = shell_parts.analysis_navigation
        self.mode_shell_coordinator = shell_parts.mode_shell_coordinator
        self._sync_bootstrap_parts()
        self._signal_connector.set_coordinators(
            absorber_coordinator=shell_parts.absorber_coordinator,
            continuum_coordinator=shell_parts.continuum_coordinator,
            identify_coordinator=shell_parts.identify_coordinator,
            mode_shell_coordinator=shell_parts.mode_shell_coordinator,
        )
        if self.mode_shell_coordinator is not None:
            self.mode_shell_coordinator.set_mode_runtimes(shell_parts.mode_runtimes)
        self._project_switch_coordinator = ProjectSwitchCoordinator(
            ProjectSwitchPorts(
                clear_history=self._history_bridge.clear,
                set_mode_project=lambda project: (
                    self.mode_shell_coordinator.set_project(project)
                    if self.mode_shell_coordinator is not None
                    else None
                ),
                update_action_states=lambda project: (
                    self.action_factory.update_action_states(project)
                    if self.action_factory is not None
                    else None
                ),
                set_view_project=lambda project: (
                    self.view_stack.set_project(project) if self.view_stack is not None else None
                ),
                set_dock_project=lambda project: (
                    self.dock_coordinator.set_project(project)
                    if self.dock_coordinator is not None
                    else None
                ),
                emit_project_changed=project_session.emit_project_changed,
            )
        )

    def _sync_bootstrap_parts(self) -> None:
        """Cache the latest shell UI parts assembled by the bootstrapper."""
        parts = self._window_bootstrapper.parts
        self._layout_builder = parts.layout_builder
        self._action_factory = parts.action_factory
        self._dock_coordinator = parts.dock_coordinator
        self._progress_bar = parts.progress_bar
        if self.mode_shell_coordinator is not None:
            self.mode_shell_coordinator.set_ui_parts(
                ModeShellUiParts(
                    view_stack=self.view_stack,
                    mode_context_bar=self.mode_context_bar,
                    action_factory=self._action_factory,
                    action_map_provider=lambda: self.action_map,
                    dock_coordinator=self._dock_coordinator,
                    data_control_panel=self.data_control_container,
                    status_controller=self.status_controller,
                    range_dock=self.range_dock,
                    current_project_provider=lambda: self.current_project,
                    hide_velocity_plot=self._identify_runtime.hide_velocity_plot,
                    analysis_detail_active_provider=lambda: (
                        self._analysis_navigation.state.surface is AnalysisSurface.REGION_DETAIL
                    ),
                )
            )
        if self._dock_coordinator is not None:
            self._dock_coordinator.set_ui_parts(
                DockLayoutUiParts(
                    current_project_provider=lambda: self.current_project,
                    status_message_emitter=self.status_message.emit,
                    mode_state_store=self.mode_state_store,
                    analysis_region_focus=self._analysis_navigation,
                    analysis_overview_navigation=self._analysis_navigation,
                    open_analysis_region=(
                        self.open_analysis_region
                        if self._analysis_surface_coordinator is not None
                        else None
                    ),
                    back_to_analysis_overview=(
                        self.back_to_analysis_overview
                        if self._analysis_surface_coordinator is not None
                        else None
                    ),
                    open_analysis_structure=(
                        self.open_analysis_structure
                        if self._analysis_surface_coordinator is not None
                        else None
                    ),
                    mode_shell_coordinator=self.mode_shell_coordinator,
                    view_stack=self.view_stack,
                    mode_context_bar=self.mode_context_bar,
                    status_controller=self.status_controller,
                    structure_history_recorder=self._history_recorder,
                    is_velocity_plot_visible=self._velocity_overlay_port.is_velocity_overlay_visible,
                    toggle_velocity_plot_optimize=self._optimize_runtime.toggle_velocity_overlay,
                    refresh_visible_optimize_velocity_overlay=(
                        self._optimize_runtime.refresh_visible_velocity_overlay
                    ),
                )
            )

    def _require_layout_builder(self) -> WindowLayoutBuilder:
        """Return the layout builder or fail fast."""
        if self._layout_builder is None:
            msg = "Layout builder is required after shell bootstrap."
            raise RuntimeError(msg)
        return self._layout_builder

    def _require_action_factory(self) -> MenuActionFactory:
        """Return the action factory or fail fast."""
        if self._action_factory is None:
            msg = "Menu action factory is required after shell bootstrap."
            raise RuntimeError(msg)
        return self._action_factory

    def _require_dock_coordinator(self) -> DockLayoutCoordinator:
        """Return the dock coordinator or fail fast."""
        if self._dock_coordinator is None:
            msg = "Dock coordinator is required after shell bootstrap."
            raise RuntimeError(msg)
        return self._dock_coordinator

    def _require_project_session(self) -> ProjectSessionController:
        """Return the project session or fail fast."""
        if self._project_session is None:
            msg = "Project session is required after shell bootstrap."
            raise RuntimeError(msg)
        return self._project_session

    @property
    def current_project(self) -> SpectroscopyProject | None:
        """Get current project."""
        project_session = self._project_session
        if project_session is None:
            return None
        return project_session.current_project

    @property
    def confirmed_line_overlay_region_id(self) -> str | None:
        """Return the focused Detail region limiting confirmed line overlays."""
        surface = self._analysis_surface_coordinator
        mode_shell = self.mode_shell_coordinator
        if (
            surface is None
            or mode_shell is None
            or mode_shell.get_current_mode() is not EditingMode.ANALYSIS
            or surface.panel_state is not PanelState.REGION_DETAIL
        ):
            return None
        return self._analysis_navigation.state.focused_region_id

    @property
    def project_file_path(self) -> str | None:
        """Get the file path recorded for the current project, if any."""
        project_session = self._project_session
        if project_session is None:
            return None
        return project_session.project_file_path

    @property
    def layout_builder(self) -> WindowLayoutBuilder | None:
        """Get layout builder from window setup handler."""
        return self._layout_builder

    @property
    def action_factory(self) -> MenuActionFactory | None:
        """Get action factory from window setup handler."""
        return self._action_factory

    @property
    def dock_coordinator(self) -> DockLayoutCoordinator | None:
        """Get dock coordinator from window setup handler."""
        return self._dock_coordinator

    @property
    def progress_bar(self) -> QProgressBar | None:
        """Get progress bar from window setup handler."""
        return self._progress_bar

    @property
    def absorber_coordinator(self) -> AbsorberCoordinator | None:
        """Get the absorber coordinator from the shell signal connector."""
        return self._signal_connector.absorber_coordinator

    @property
    def continuum_coordinator(self) -> ContinuumCoordinator | None:
        """Get the continuum coordinator from the shell signal connector."""
        return self._signal_connector.continuum_coordinator

    @property
    def identify_coordinator(self) -> IdentifyModeCoordinatorPort | None:
        """Get the identify coordinator from the shell signal connector."""
        return self._signal_connector.identify_coordinator

    @property
    def identify_velocity_runtime(self) -> IdentifyVelocityOverlayRuntimePort:
        """Return the identify runtime owning velocity overlay workflows."""
        return self._identify_runtime

    @property
    def optimize_velocity_runtime(self) -> OptimizeVelocityOverlayRuntimePort:
        """Return the optimize runtime owning velocity overlay workflows."""
        return self._optimize_runtime

    @property
    def continuum_mode_runtime(self) -> ContinuumSharedSurfaceContextController:
        """Return the continuum runtime owning shared-surface commands."""
        if self._continuum_mode_runtime is None:
            msg = "Continuum mode runtime is required after shell setup."
            raise RuntimeError(msg)
        return self._continuum_mode_runtime

    @property
    def display_menu_controller(self) -> DisplayMenuController:
        """Return the Display menu controller or fail fast."""
        if self._display_menu_controller is None:
            msg = "Display menu controller is required after shell setup."
            raise RuntimeError(msg)
        return self._display_menu_controller

    def _setup_handlers(self) -> None:
        """Setup handler callbacks and connections."""
        project_session = self._require_project_session()
        project_session.set_window_title_update_callback(self._update_window_title)
        project_session.project_changed.connect(self.project_changed)
        project_session.status_message.connect(self.status_message)

        self._window_lifecycle.set_project_session(project_session)
        self._window_lifecycle.set_save_settings_callback(self._save_settings)
        self._signal_connector.set_ports(
            ShellSignalConnectorPorts(
                status_message=lambda msg: self.status_message.emit(msg, 3000),
                mode_changed=self._on_coordinator_mode_changed,
                hide_velocity_plot=self._identify_runtime.hide_velocity_plot,
                confirm_velocity_plot_selection=(
                    self._identify_runtime.confirm_velocity_plot_selection
                ),
                active_view_changed=self._emit_active_view_status,
                cursor_coordinates_changed=self.handle_cursor_coordinates_changed,
                cursor_coordinates_cleared=self.handle_cursor_coordinates_cleared,
                fit_started=self._show_fit_started_status,
                fit_completed=self._show_fit_completed_status,
                optimize_region_changed=self._on_optimize_region_changed,
            )
        )

    def _create_actions(self) -> None:
        """Create all application actions and initialize coordinators."""
        self._window_bootstrapper.create_actions(self._action_dispatcher)
        self._sync_bootstrap_parts()

    @property
    def action_map(self) -> dict[ShellActionId, QAction]:
        """Return a mapping of action identifiers to QAction instances."""
        return self._require_action_factory().get_all_actions()

    def _show_about_dialog_fallback(self) -> None:
        """Delegate About dialog display through the action factory."""
        self._require_action_factory()._show_about_dialog()

    def show_about_dialog(self) -> None:
        """Show the About dialog through the registered shell action UI."""
        self._show_about_dialog_fallback()

    def _emit_status_message(self, message: str, timeout_ms: int) -> None:
        """Emit a shell status message through the Qt signal."""
        self.status_message.emit(message, timeout_ms)

    def show_status_message(self, message: str, timeout_ms: int) -> None:
        """Show a shell status message through the Qt signal."""
        self._emit_status_message(message, timeout_ms)

    def show_welcome_dialog(self) -> None:
        """Show the welcome dialog and act on the selected learning path.

        The developer start override replaces this with a tour over the
        current project, leaving the loaded data untouched.
        """
        override_chapters = resolve_tutorial_start_chapters()
        if override_chapters is not None:
            self._start_tutorial_walkthrough(override_chapters)
            return
        sample_pair = _find_sample_spectrum_pair()
        dialog = WelcomeDialog(self, sample_available=sample_pair is not None)
        dialog.exec()
        if dialog.choice is WelcomeDialog.Choice.DISMISS or sample_pair is None:
            return
        flux_path, error_path = sample_pair
        self._require_project_session().open_sample_data(
            str(flux_path), str(error_path), resolving_power=_SAMPLE_RESOLVING_POWER
        )
        if dialog.choice is WelcomeDialog.Choice.START_ESSENTIAL_WALKTHROUGH:
            self.start_tutorial_essential_walkthrough()
        elif dialog.choice is WelcomeDialog.Choice.START_ADVANCED_WALKTHROUGH:
            self.start_tutorial_advanced_walkthrough()

    def start_tutorial_essential_walkthrough(self) -> None:
        """Start (or restart) the essential guided walkthrough."""
        self._start_tutorial_walkthrough(build_essential_walkthrough_chapters())

    def start_tutorial_advanced_walkthrough(self) -> None:
        """Start (or restart) the advanced guided walkthrough."""
        self._start_tutorial_walkthrough(build_advanced_walkthrough_chapters())

    def _start_tutorial_walkthrough(self, chapters: tuple[TutorialChapter, ...]) -> None:
        """Replace any running tour with a walkthrough over ``chapters``."""
        if self.mode_shell_coordinator is None:
            msg = "Mode coordinator must be initialized before the tutorial tour."
            raise RuntimeError(msg)
        if self._tutorial_tour is not None:
            self._tutorial_tour.stop()
            self.mode_shell_coordinator.mode_changed.disconnect(
                self._tutorial_tour.notify_mode_changed
            )
            self._tutorial_tour.deleteLater()
        self._tutorial_initial_preset_ids = frozenset(
            preset.id for preset in self.preset_store.list_presets()
        )
        self._tutorial_tour = TutorialTourController(
            self,
            chapters=chapters,
            switch_mode=self.switch_mode,
            switch_analysis_surface=self._switch_tutorial_analysis_surface,
            switch_analysis_panel=self._switch_tutorial_analysis_panel,
            chapter_context_changed=self._set_tutorial_chapter_context,
            prerequisite_checks=self._tutorial_prerequisite_checks(),
            completion_checks=self._tutorial_completion_checks(),
            completion_notes=self._tutorial_completion_notes(),
        )
        self.mode_shell_coordinator.mode_changed.connect(self._tutorial_tour.notify_mode_changed)
        self._tutorial_tour.start()

    def _tutorial_prerequisite_checks(self) -> dict[TutorialPrerequisite, Callable[[], bool]]:
        """Return tutorial prerequisite predicates over live project state."""
        return {
            TutorialPrerequisite.HAS_CONFIRMED_REGION: (
                lambda: self._confirmed_tutorial_region_count() >= 1
            ),
            TutorialPrerequisite.HAS_TWO_REGIONS: (
                lambda: self._confirmed_tutorial_region_count() >= 2
            ),
            TutorialPrerequisite.HAS_TOUR_CREATED_PRESET: (self._tutorial_new_preset_is_selected),
            TutorialPrerequisite.HAS_TUTORIAL_MULTI_ION_REGION: (
                self._has_tutorial_multi_ion_region
            ),
        }

    def _confirmed_tutorial_region_count(self) -> int:
        """Return how many non-unassigned absorption regions exist."""
        project = self.current_project
        if project is None:
            return 0
        return sum(
            1 for region_id in project.absorption_regions if region_id != UNASSIGNED_REGION_ID
        )

    def _tutorial_new_preset_is_selected(self) -> bool:
        """Return whether a preset created since this tour began is selected."""
        preset = self._current_tutorial_preset()
        return (
            preset is not None
            and preset.is_editable
            and preset.id not in self._tutorial_initial_preset_ids
        )

    def _has_tutorial_multi_ion_region(self) -> bool:
        """Return whether one region contains exactly the six tutorial transitions."""
        project = self.current_project
        if project is None:
            return False
        return any(
            region_id != UNASSIGNED_REGION_ID
            and self._tutorial_region_has_exact_transitions(region_id)
            for region_id in project.absorption_regions
        )

    def _tutorial_completion_checks(self) -> dict[TutorialCompletion, Callable[[], bool]]:
        """Return tutorial step-completion predicates over live project state."""
        return {
            TutorialCompletion.METAL_LINES_PRESET_SELECTED: (
                self._tutorial_metal_lines_preset_selected
            ),
            TutorialCompletion.REFERENCE_LINE_IS_CIV1548: (
                self._tutorial_reference_line_is_civ1548
            ),
            TutorialCompletion.CONFIRMED_REGION_EXISTS: (
                lambda: self._confirmed_tutorial_region_count() >= 1
            ),
            TutorialCompletion.NEW_TUTORIAL_PRESET_SELECTED: (
                self._tutorial_new_preset_is_selected
            ),
            TutorialCompletion.PRESET_HAS_TUTORIAL_LINES: (
                self._tutorial_preset_has_tutorial_lines
            ),
            TutorialCompletion.PRESET_FE2_UNLINKED: self._tutorial_preset_fe2_unlinked,
            TutorialCompletion.PRESET_FE2_SINGLE_GROUP: (self._tutorial_preset_fe2_single_group),
            TutorialCompletion.PRESET_BASELINE_IS_MG2796: (
                self._tutorial_preset_baseline_is_mg2796
            ),
            TutorialCompletion.TUTORIAL_PRESET_SELECTED: self._tutorial_preset_is_selected,
            TutorialCompletion.VELOCITY_PLOT_VISIBLE: self._tutorial_velocity_plot_visible,
            TutorialCompletion.VELOCITY_SLICES_SELECTED: (self._tutorial_velocity_slices_selected),
            TutorialCompletion.FE2_AND_MG2_REGIONS_EXIST: (
                self._tutorial_fe2_and_mg2_regions_exist
            ),
            TutorialCompletion.MULTI_ION_REGION_EXISTS: self._has_tutorial_multi_ion_region,
            TutorialCompletion.MONO_ION_REGIONS_RESTORED: (
                self._tutorial_mono_ion_regions_restored
            ),
            TutorialCompletion.REGION_DETAIL_OPENED: self._tutorial_region_detail_opened,
            TutorialCompletion.REGION_HAS_COMPONENT: self._tutorial_region_has_component,
            TutorialCompletion.TUTORIAL_MULTI_ION_REGION_OPENED: (
                self._tutorial_multi_ion_region_opened
            ),
            TutorialCompletion.FE2_COMPONENT_EXISTS: (
                lambda: self._tutorial_species_has_component("Fe II")
            ),
            TutorialCompletion.MG2_COMPONENT_EXISTS: (
                lambda: self._tutorial_species_has_component("Mg II")
            ),
            TutorialCompletion.FE2_AND_MG2_HAVE_THREE_COMPONENTS: (
                self._tutorial_each_ion_has_three_components
            ),
            TutorialCompletion.CROSS_ION_Z_TIE_EXISTS: (
                self._tutorial_cross_ion_redshift_tie_exists
            ),
            TutorialCompletion.REGION_FIT_APPLIED: self._tutorial_region_fit_applied,
            TutorialCompletion.MG2_LOGN_FIXED: self._tutorial_mg2_logn_fixed,
        }

    def _tutorial_completion_notes(self) -> dict[TutorialCompletion, Callable[[], str | None]]:
        """Return translated notes explaining a completion condition's verdict."""
        return {
            TutorialCompletion.REGION_FIT_APPLIED: self._tutorial_region_fit_note,
            TutorialCompletion.NEW_TUTORIAL_PRESET_SELECTED: (self._tutorial_editable_preset_note),
            TutorialCompletion.PRESET_HAS_TUTORIAL_LINES: self._tutorial_preset_lines_note,
            TutorialCompletion.PRESET_FE2_UNLINKED: self._tutorial_preset_fe2_unlinked_note,
            TutorialCompletion.PRESET_FE2_SINGLE_GROUP: (
                self._tutorial_preset_fe2_single_group_note
            ),
            TutorialCompletion.PRESET_BASELINE_IS_MG2796: self._tutorial_preset_baseline_note,
            TutorialCompletion.FE2_AND_MG2_REGIONS_EXIST: (
                self._tutorial_fe2_and_mg2_regions_note
            ),
            TutorialCompletion.MG2_LOGN_FIXED: self._tutorial_mg2_logn_fixed_note,
        }

    def _tutorial_unmet_note(self, condition: TutorialCompletion, *, met: bool) -> str | None:
        """Return the translated note for a closed gate, or None once it opened."""
        if met:
            return None
        return QCoreApplication.translate("Tutorial", COMPLETION_NOTE_SOURCES[condition])

    def _tutorial_editable_preset_note(self) -> str | None:
        """Return why the custom-preset gate is still closed."""
        return self._tutorial_unmet_note(
            TutorialCompletion.NEW_TUTORIAL_PRESET_SELECTED,
            met=self._tutorial_new_preset_is_selected(),
        )

    def _tutorial_preset_lines_note(self) -> str | None:
        """Return which tutorial lines the selected preset is still missing."""
        if self._tutorial_preset_has_tutorial_lines():
            return None
        species_counts = self._tutorial_preset_species_counts()
        template = QCoreApplication.translate(
            "Tutorial", COMPLETION_NOTE_SOURCES[TutorialCompletion.PRESET_HAS_TUTORIAL_LINES]
        )
        return template.format(
            fe2_count=species_counts.get("Fe II", 0), mg2_count=species_counts.get("Mg II", 0)
        )

    def _tutorial_preset_fe2_unlinked_note(self) -> str | None:
        """Return why the Fe II unlink gate is still closed."""
        return self._tutorial_unmet_note(
            TutorialCompletion.PRESET_FE2_UNLINKED, met=self._tutorial_preset_fe2_unlinked()
        )

    def _tutorial_preset_fe2_single_group_note(self) -> str | None:
        """Return why the single Fe II link gate is still closed."""
        return self._tutorial_unmet_note(
            TutorialCompletion.PRESET_FE2_SINGLE_GROUP,
            met=self._tutorial_preset_fe2_single_group(),
        )

    def _tutorial_preset_baseline_note(self) -> str | None:
        """Return why the reference-line gate is still closed."""
        return self._tutorial_unmet_note(
            TutorialCompletion.PRESET_BASELINE_IS_MG2796,
            met=self._tutorial_preset_baseline_is_mg2796(),
        )

    def _tutorial_fe2_and_mg2_regions_note(self) -> str | None:
        """Return why the Fe II / Mg II registration gate is still closed."""
        return self._tutorial_unmet_note(
            TutorialCompletion.FE2_AND_MG2_REGIONS_EXIST,
            met=self._tutorial_fe2_and_mg2_regions_exist(),
        )

    def _tutorial_mg2_logn_fixed_note(self) -> str | None:
        """Return why the Mg II logN fix gate is still closed."""
        return self._tutorial_unmet_note(
            TutorialCompletion.MG2_LOGN_FIXED, met=self._tutorial_mg2_logn_fixed()
        )

    def _tutorial_region_fit_note(self) -> str | None:
        """Return why the focused region's latest fit passed or failed the gate."""
        project = self.current_project
        region_id = self._analysis_navigation.state.focused_region_id
        if project is None or region_id is None:
            return None
        state = project.region_analysis_state(region_id)
        artifact = state.artifact if state is not None else None
        outcome = artifact.fit_summary.outcome if artifact is not None else None
        if outcome is None:
            return None
        return QCoreApplication.translate("Tutorial", FIT_OUTCOME_NOTE_SOURCES[outcome])

    def _current_tutorial_preset(self) -> Preset | None:
        """Return the currently selected preset, if any."""
        current_preset_id = self.preset_store.current_preset_id
        if current_preset_id is None:
            return None
        return self.preset_store.get_preset(current_preset_id)

    def _tutorial_preset_species_counts(self) -> dict[str, int]:
        """Return how many lines of each species the selected preset holds."""
        preset = self._current_tutorial_preset()
        if preset is None:
            return {}
        species_counts: dict[str, int] = {}
        for line_id in preset.line_ids:
            line = self._atomic_data.get_line_by_id(line_id)
            if line is None:
                continue
            species_counts[line.species] = species_counts.get(line.species, 0) + 1
        return species_counts

    def _tutorial_preset_has_tutorial_lines(self) -> bool:
        """Return whether the selected preset holds exactly the six requested line IDs."""
        preset = self._current_tutorial_preset()
        return (
            preset is not None
            and len(preset.line_ids) == len(_TUTORIAL_PRESET_LINE_IDS)
            and set(preset.line_ids) == _TUTORIAL_PRESET_LINE_IDS
        )

    def _tutorial_preset_species_line_ids(self, preset: Preset, species: str) -> set[str]:
        """Return the preset's line identifiers belonging to one ion species."""
        return {
            line_id
            for line_id in preset.line_ids
            if (line := self._atomic_data.get_line_by_id(line_id)) is not None
            and line.species == species
        }

    def _tutorial_preset_fe2_unlinked(self) -> bool:
        """Return whether the selected preset has no tie group containing Fe II lines."""
        preset = self._current_tutorial_preset()
        if preset is None:
            return False
        fe2_line_ids = self._tutorial_preset_species_line_ids(preset, "Fe II")
        return not any(fe2_line_ids.intersection(group.line_ids) for group in preset.tie_groups)

    def _tutorial_lines_form_one_tie_group(self, preset: Preset, line_ids: set[str]) -> bool:
        """Return whether the given lines are exactly one of the preset's tie groups."""
        touching = [group for group in preset.tie_groups if line_ids.intersection(group.line_ids)]
        return len(touching) == 1 and set(touching[0].line_ids) == line_ids

    def _tutorial_preset_fe2_single_group(self) -> bool:
        """Return whether the preset's 4 Fe II and 2 Mg II lines each share one link."""
        preset = self._current_tutorial_preset()
        if preset is None:
            return False
        fe2_line_ids = self._tutorial_preset_species_line_ids(preset, "Fe II")
        mg2_line_ids = self._tutorial_preset_species_line_ids(preset, "Mg II")
        if len(fe2_line_ids) != 4 or len(mg2_line_ids) != 2:
            return False
        return self._tutorial_lines_form_one_tie_group(
            preset, fe2_line_ids
        ) and self._tutorial_lines_form_one_tie_group(preset, mg2_line_ids)

    def _tutorial_preset_baseline_is_mg2796(self) -> bool:
        """Return whether the selected preset's baseline resolves to Mg II 2796."""
        preset = self._current_tutorial_preset()
        if preset is None or preset.baseline_id is None:
            return False
        baseline_line = self._atomic_data.get_line_by_id(preset.baseline_id)
        if baseline_line is None:
            return False
        return (
            baseline_line.species == "Mg II" and round(baseline_line.wavelength_angstrom) == 2796
        )

    def _tutorial_metal_lines_preset_selected(self) -> bool:
        """Return whether the built-in Metal Lines preset is the current selection."""
        return self.preset_store.current_preset_id == METAL_LINES_PRESET_ID

    def _tutorial_reference_line_is_civ1548(self) -> bool:
        """Return whether the reference line selector resolves to C IV 1548."""
        preset = self._current_tutorial_preset()
        if preset is None or preset.baseline_id is None:
            return False
        baseline_line = self._atomic_data.get_line_by_id(preset.baseline_id)
        if baseline_line is None:
            return False
        return baseline_line.species == "C IV" and round(baseline_line.wavelength_angstrom) == 1548

    def _tutorial_preset_is_selected(self) -> bool:
        """Return whether the currently selected preset is the tutorial's custom preset."""
        return self._tutorial_new_preset_is_selected()

    def _tutorial_velocity_plot_visible(self) -> bool:
        """Return whether the identify velocity plot is currently visible."""
        spectrum_view = self.view_stack.spectrum_view if self.view_stack is not None else None
        if spectrum_view is None:
            return False
        return spectrum_view.is_velocity_plot_visible()

    def _tutorial_velocity_slices_selected(self) -> bool:
        """Return whether the 4 Fe II and 2 Mg II tutorial slices are the checked ones."""
        spectrum_view = self.view_stack.spectrum_view if self.view_stack is not None else None
        velocity_view = spectrum_view.velocity_view if spectrum_view is not None else None
        if velocity_view is None:
            return False
        species_counts: dict[str, int] = {}
        for slice_info in velocity_view.get_selected_slices():
            if slice_info.line_id is None:
                continue
            line = self._atomic_data.get_line_by_id(slice_info.line_id)
            if line is None:
                continue
            species_counts[line.species] = species_counts.get(line.species, 0) + 1
        return species_counts == {"Fe II": 4, "Mg II": 2}

    def _tutorial_confirmed_region_species_counts(self) -> list[dict[str, int]]:
        """Return, per confirmed region, how many lines of each species it holds."""
        project = self.current_project
        if project is None:
            return []
        region_counts: list[dict[str, int]] = []
        for region_id, region in project.absorption_regions.items():
            if region_id == UNASSIGNED_REGION_ID:
                continue
            counts: dict[str, int] = {}
            for line_id in region.line_ids:
                line = project.absorption_lines.get(line_id)
                if line is None:
                    continue
                counts[line.species] = counts.get(line.species, 0) + 1
            region_counts.append(counts)
        return region_counts

    def _tutorial_fe2_and_mg2_regions_exist(self) -> bool:
        """Return whether the 4-line Fe II and 2-line Mg II regions were both registered."""
        region_counts = self._tutorial_confirmed_region_species_counts()
        return {"Fe II": 4} in region_counts and {"Mg II": 2} in region_counts

    def _tutorial_mono_ion_regions_restored(self) -> bool:
        """Return whether at least 2 confirmed regions exist and none mixes species."""
        project = self.current_project
        if project is None:
            return False
        confirmed_regions = [
            region
            for region_id, region in project.absorption_regions.items()
            if region_id != UNASSIGNED_REGION_ID
        ]
        if len(confirmed_regions) < 2:
            return False
        for region in confirmed_regions:
            species = {
                line.species
                for line_id in region.line_ids
                if (line := project.absorption_lines.get(line_id)) is not None
            }
            if len(species) >= 2:
                return False
        return True

    def _tutorial_region_transitions(self, region_id: str) -> frozenset[tuple[str, float]]:
        """Return stable species/wavelength identities for one project region."""
        project = self.current_project
        if project is None:
            return frozenset()
        lines = project.find_lines_for_region(region_id)
        if lines is None:
            return frozenset()
        return frozenset((line.species, round(line.rest_wavelength, 1)) for line in lines)

    def _tutorial_region_has_exact_transitions(self, region_id: str) -> bool:
        """Return whether a region contains only the six tutorial transitions."""
        project = self.current_project
        if project is None:
            return False
        lines = project.find_lines_for_region(region_id)
        return (
            lines is not None
            and len(lines) == len(_TUTORIAL_REGION_LINES)
            and self._tutorial_region_transitions(region_id) == _TUTORIAL_REGION_LINES
        )

    def _tutorial_multi_ion_region_opened(self) -> bool:
        """Return whether Detail is focused on exactly the merged tutorial region."""
        if not self._tutorial_region_detail_opened():
            return False
        region_id = self._analysis_navigation.state.focused_region_id
        return region_id is not None and self._tutorial_region_has_exact_transitions(region_id)

    def _tutorial_focused_region_lines(self, species: str) -> tuple[AbsorptionLine, ...]:
        """Return focused-region absorption lines for one ion species."""
        project = self.current_project
        region_id = self._analysis_navigation.state.focused_region_id
        if project is None or region_id is None:
            return ()
        lines = project.find_lines_for_region(region_id)
        if lines is None:
            return ()
        return tuple(line for line in lines if line.species == species)

    def _tutorial_species_has_component(self, species: str) -> bool:
        """Return whether every focused-region line of an ion has a component."""
        lines = self._tutorial_focused_region_lines(species)
        return bool(lines) and all(line.model_ids for line in lines)

    def _tutorial_species_component_count_at_least(self, species: str, count: int) -> bool:
        """Return whether every focused-region line of an ion has ``count`` models."""
        lines = self._tutorial_focused_region_lines(species)
        return bool(lines) and all(len(line.model_ids) >= count for line in lines)

    def _tutorial_each_ion_has_three_components(self) -> bool:
        """Return whether Fe II and Mg II each have at least three tied components."""
        return self._tutorial_species_component_count_at_least(
            "Fe II", 3
        ) and self._tutorial_species_component_count_at_least("Mg II", 3)

    def _tutorial_region_has_component(self) -> bool:
        """Return whether the focused region has at least one modeled line."""
        project = self.current_project
        region_id = self._analysis_navigation.state.focused_region_id
        if project is None or region_id is None:
            return False
        lines = project.find_lines_for_region(region_id)
        if lines is None:
            return False
        return any(line.model_ids for line in lines)

    def _tutorial_cross_ion_redshift_tie_exists(self) -> bool:
        """Return whether the focused region has a redshift-only tie across species."""
        project = self.current_project
        region_id = self._analysis_navigation.state.focused_region_id
        if project is None or region_id is None:
            return False
        lines = project.find_lines_for_region(region_id)
        if lines is None:
            return False
        checked_tie_uids: set[str] = set()
        for line in lines:
            for model_id in line.model_ids:
                component = project.find_absorber_component(model_id)
                direct_tie_set = component.tie_set if component is not None else None
                if direct_tie_set is None:
                    continue
                # A cross-ion tie nests each ion's multiplet tie, so the shared
                # redshift lives on the parent rather than on component.tie_set.
                tie_set = direct_tie_set.parent_tie or direct_tie_set
                if tie_set.uid in checked_tie_uids:
                    continue
                checked_tie_uids.add(tie_set.uid)
                if tie_set.mask != frozenset({"redshift"}):
                    continue
                species = {
                    member.atomic_line.species
                    for member in tie_set.components
                    if member.atomic_line is not None
                }
                if len(species) >= 2:
                    return True
        return False

    def _tutorial_region_fit_applied(self) -> bool:
        """Return whether the focused region has an up-to-date applied fit."""
        project = self.current_project
        region_id = self._analysis_navigation.state.focused_region_id
        if project is None or region_id is None:
            return False
        readiness = DeriveAnalysisReadinessUseCase().execute(project, region_id)
        return readiness is AnalysisReadiness.LATEST

    def _tutorial_mg2_logn_fixed(self) -> bool:
        """Return whether a focused-region Mg II component holds its logN fixed."""
        project = self.current_project
        if project is None:
            return False
        for line in self._tutorial_focused_region_lines("Mg II"):
            for model_id in line.model_ids:
                component = project.find_absorber_component(model_id)
                if component is not None and component.parameters["column_density"].fixed:
                    return True
        return False

    def _set_tutorial_chapter_context(self, chapter_id: str | None) -> None:
        """Apply chapter-scoped walkthrough state without persisting it."""
        coordinator = self.identify_coordinator
        if coordinator is None:
            return
        coordinator.set_tutorial_sigma_threshold(50.0 if chapter_id == "identify" else None)

    def _switch_tutorial_analysis_surface(self, surface: AnalysisOperationSurface) -> bool:
        """Apply a tutorial Analysis surface; report whether it is now active."""
        coordinator = self._require_analysis_surface_coordinator()
        if surface is AnalysisOperationSurface.OVERVIEW:
            return self.back_to_analysis_overview()

        if coordinator.panel_state is PanelState.REGION_DETAIL:
            return True
        # Merge absorbs regions into the first id and split creates a new one,
        # so a focused id may name a region that no longer exists.
        region_id = self._analysis_navigation.state.focused_region_id
        if region_id is not None and not self._tutorial_region_exists(region_id):
            region_id = None
        if region_id is None:
            region_id = self._first_tutorial_region_id()
        if region_id is None:
            return False
        return coordinator.open_region(OpenAnalysisRegionIntent(region_id))

    def _tutorial_region_exists(self, region_id: str) -> bool:
        project = self.current_project
        return project is not None and region_id in project.absorption_regions

    def _first_tutorial_region_id(self) -> str | None:
        """Return a region the tutorial can open when none is focused yet."""
        project = self.current_project
        if project is None:
            return None
        return next(
            (
                region_id
                for region_id in project.absorption_regions
                if region_id != UNASSIGNED_REGION_ID
            ),
            None,
        )

    def _tutorial_region_detail_opened(self) -> bool:
        """Return whether Region Detail is open for the selected region."""
        return self._require_analysis_surface_coordinator().panel_state is PanelState.REGION_DETAIL

    def _switch_tutorial_analysis_panel(self, panel: AnalysisOperationPanel) -> bool:
        """Apply a tutorial Analysis panel; report whether it is now active."""
        coordinator = self._require_analysis_surface_coordinator()
        if panel is AnalysisOperationPanel.STRUCTURE:
            return self.open_analysis_structure()
        if panel is AnalysisOperationPanel.SUMMARY:
            if coordinator.panel_state is PanelState.OVERVIEW_STRUCTURE:
                return self.back_to_analysis_overview()
            return True
        return coordinator.panel_state is PanelState.REGION_DETAIL

    def maybe_show_first_run_welcome(self) -> None:
        """Show the welcome dialog once on the first application launch."""
        settings = QSettings("Chappy", "Chappy")
        if settings.value(_WELCOME_SHOWN_SETTINGS_KEY, False, type=bool):
            return
        settings.setValue(_WELCOME_SHOWN_SETTINGS_KEY, True)
        self.show_welcome_dialog()

    # Delegate UI creation to WindowBootstrapper
    def _setup_window(self) -> None:
        """Setup window properties."""
        self._window_bootstrapper.setup_window()

    def _create_menus(self) -> None:
        """Create menu bar."""
        self._window_bootstrapper.create_menus()

    def _create_status_bar(self) -> None:
        """Create status bar."""
        self._window_bootstrapper.create_status_bar()
        self._sync_bootstrap_parts()

    def _create_central_widget(self) -> None:
        """Create central widget."""
        self._window_bootstrapper.create_central_widget()
        self._sync_bootstrap_parts()
        layout_builder = self._require_layout_builder()
        self.central_widget = layout_builder.central_widget
        self.view_stack = layout_builder.view_stack

    def _create_dock_widgets(self) -> None:
        """Create dockable panels for component management."""
        self._window_bootstrapper.create_dock_widgets()
        self._sync_bootstrap_parts()
        dock_coordinator = self._require_dock_coordinator()
        editors = dock_coordinator.get_component_editors()
        self.absorber_editor = self._absorber_editor_port(editors[0])
        self.continuum_editor = editors[1]
        self.optimize_editor = editors[2]
        self._initialize_analysis_surface()
        self.range_dock = dock_coordinator.create_range_selector_dock()
        self.range_selector = dock_coordinator.range_selector
        self._sync_bootstrap_parts()

    def _initialize_analysis_surface(self) -> None:
        """Connect the concrete Analysis workspace to its surface owner."""
        dock = self._require_dock_coordinator()
        workspace = dock.analysis_workspace
        bottom_pane = dock._analysis_bottom_pane
        data_control = self.data_control_container
        spectrum_view = self.view_stack.spectrum_view if self.view_stack is not None else None
        detail = dock.region_detail_ui()
        overview = dock.structure_panel
        if (
            workspace is None
            or bottom_pane is None
            or data_control is None
            or spectrum_view is None
            or detail is None
            or overview is None
        ):
            msg = "Analysis surface requires workspace, pane, data controls, spectrum, and Detail"
            raise RuntimeError(msg)
        adapter = AnalysisSurfaceUiAdapter(
            AnalysisSurfaceUiPorts(
                workspace=workspace,
                spectrum_view=spectrum_view,
                bottom_pane=bottom_pane,
                data_control=data_control,
                actions=self.action_map,
                refresh_confirmed_line_overlays=self._refresh_analysis_line_overlays,
            )
        )
        guard = AnalysisTransitionGuardAdapter(
            fit_running=self._optimize_runtime.is_fit_running, detail_widget=detail.panel
        )
        presentation = AnalysisSurfacePresentationAdapter(
            overview_panel=overview, detail_panel=detail
        )
        self._analysis_surface_coordinator = AnalysisSurfaceCoordinator(
            navigation=self._analysis_navigation,
            workspace=workspace,
            policies=adapter,
            guard=guard,
            presentation=presentation,
        )
        spectrum_view.data_bridge.range_changed.connect(
            self._handle_analysis_spectrum_range_changed
        )
        self._analysis_navigation.focused_region_changed.connect(
            self._handle_analysis_focused_region_changed
        )
        self._sync_bootstrap_parts()

    def _handle_analysis_focused_region_changed(self, region_id: object) -> None:
        """Project canonical focused ID into the Detail panel and spectrum view."""
        if not isinstance(region_id, str):
            return
        project = self.current_project
        region = project.absorption_regions.get(region_id) if project is not None else None
        if region is None:
            return
        region_detail_ui = self._require_dock_coordinator().region_detail_ui()
        if region_detail_ui is not None:
            region_detail_ui.select_focused_region(region)
        self._require_dock_coordinator().refresh_analysis_bottom_pane_title()
        SpectrumRegionFocusController(
            project_provider=lambda: self.current_project,
            spectrum_view_provider=lambda: (
                self.view_stack.spectrum_view if self.view_stack is not None else None
            ),
        ).focus_region(region)
        if self.confirmed_line_overlay_region_id is not None:
            self._refresh_analysis_line_overlays()

    def _refresh_analysis_line_overlays(self) -> None:
        """Refresh confirmed line overlays through the Analysis lifecycle."""
        mode_shell = self.mode_shell_coordinator
        if mode_shell is None:
            msg = "Analysis line overlay refresh requires a mode shell coordinator."
            raise RuntimeError(msg)
        mode_shell.refresh_line_overlays_for_mode(EditingMode.ANALYSIS)

    def _reconcile_analysis_focus_with_selector(self, _event: object) -> None:
        """Settle canonical Analysis focus once a project context change completes.

        Runs after `AnalysisNavigationCoordinator.handle_project_context_changed`
        has restored/validated navigation state and released the
        context-switching guard, so a focus write-back is accepted.
        """
        region_detail_ui = self._require_dock_coordinator().region_detail_ui()
        if region_detail_ui is not None:
            region_detail_ui.reconcile_focus_with_selector()

    def _handle_analysis_spectrum_range_changed(
        self, minimum: float, maximum: float, _flux_minimum: float, _flux_maximum: float
    ) -> None:
        """Save the visible wavelength range only while Analysis owns the view."""
        if (
            self.mode_shell_coordinator is None
            or self.mode_shell_coordinator.get_current_mode() is not EditingMode.ANALYSIS
        ):
            return
        self._analysis_navigation.update_spectrum_wavelength_range((minimum, maximum))

    def _restore_analysis_spectrum_range(self) -> None:
        """Restore the project-key range after the Analysis surface is ready."""
        wavelength_range = self._analysis_navigation.state.spectrum_wavelength_range
        spectrum_view = self.view_stack.spectrum_view if self.view_stack is not None else None
        if wavelength_range is None or spectrum_view is None:
            return
        spectrum_view.set_wavelength_range(*wavelength_range)

    def open_analysis_region(self, region_id: str) -> bool:
        """Execute an explicit typed request to open Analysis Region Detail."""
        coordinator = self._require_analysis_surface_coordinator()
        return coordinator.open_region(OpenAnalysisRegionIntent(region_id))

    def handle_identify_open_analysis_region(self, intent: object) -> None:
        """Open Identify's confirmed region in the required focus-surface-mode order."""
        if not isinstance(intent, OpenAnalysisRegionIntent):
            msg = "Identify Analysis navigation requires OpenAnalysisRegionIntent"
            raise TypeError(msg)
        if not self._analysis_navigation.focus_region(intent.region_id):
            return
        self._analysis_navigation.set_surface(AnalysisSurface.REGION_DETAIL)
        if self.mode_shell_coordinator is None:
            msg = "Mode shell coordinator is required for Identify Analysis navigation"
            raise RuntimeError(msg)
        self.mode_shell_coordinator.switch_mode(EditingMode.ANALYSIS)

    def handle_identify_open_analysis_structure(self, intent: object) -> None:
        """Land Identify's confirmed region on the nested Overview structure editor."""
        if not isinstance(intent, OpenAnalysisStructureIntent):
            msg = "Identify Analysis navigation requires OpenAnalysisStructureIntent"
            raise TypeError(msg)
        if not self._analysis_navigation.focus_region(intent.region_id):
            return
        self._analysis_navigation.set_surface(AnalysisSurface.OVERVIEW)
        if self.mode_shell_coordinator is None:
            msg = "Mode shell coordinator is required for Identify Analysis navigation"
            raise RuntimeError(msg)
        self.mode_shell_coordinator.switch_mode(EditingMode.ANALYSIS)
        if not self.open_analysis_structure():
            return
        panel = self._require_dock_coordinator().structure_panel
        if panel is not None:
            panel.restore_selection((intent.region_id,), ())

    def back_to_analysis_overview(self) -> bool:
        """Return to Overview through the guarded surface transition."""
        changed = self._require_analysis_surface_coordinator().back_to_overview()
        if changed:
            panel = self._require_dock_coordinator().structure_panel
            if panel is not None:
                panel.set_structure_editor_visible(False)
                region_id = self._analysis_navigation.state.focused_region_id
                if region_id is not None:
                    panel.focus_review_region(region_id)
        return changed

    def open_analysis_structure(self) -> bool:
        """Open the nested Structure page without switching top-level mode."""
        if not self._require_analysis_surface_coordinator().open_structure_editor():
            return False
        panel = self._require_dock_coordinator().structure_panel
        if panel is not None:
            panel.set_structure_editor_visible(True)
        return True

    def delete_analysis_structure_selection(self) -> bool:
        """Execute Delete only while the nested Structure page owns the action."""
        if not self._require_analysis_surface_coordinator().structure_actions_enabled():
            return False
        return self._require_dock_coordinator()._execute_structure_delete()

    def _require_analysis_surface_coordinator(self) -> AnalysisSurfaceCoordinator:
        coordinator = self._analysis_surface_coordinator
        if coordinator is None:
            msg = "Analysis surface coordinator is not initialized"
            raise RuntimeError(msg)
        return coordinator

    def _absorber_editor_port(self, editor: object | None) -> AbsorberEditorSignalPort | None:
        """Return a validated absorber editor port."""
        if editor is None:
            return None
        if isinstance(editor, AbsorberEditorSignalPort):
            return editor
        msg = "Dock absorber editor does not implement the required absorber port."
        raise TypeError(msg)

    def _restore_settings(self) -> None:
        """Restore window settings."""
        self._window_bootstrapper.restore_settings()

    def _save_settings(self) -> None:
        """Save window settings."""
        self._window_bootstrapper.save_settings()

    def _update_window_title(self) -> None:
        """Update window title based on current project."""
        self._window_bootstrapper.update_window_title(self.current_project)

    # Delegate project operations to ProjectSessionController
    def _setup_project_handling(self) -> None:
        """Setup project handling."""
        self._require_project_session().setup_project_handling()

    def _wavelength_under_cursor(self) -> float | None:
        """Return the spectrum wavelength under the pointer."""
        if self.view_stack is None or self.view_stack.spectrum_view is None:
            msg = "Spectrum view is required to resolve the wavelength under the cursor."
            raise RuntimeError(msg)
        return self.view_stack.spectrum_view.wavelength_under_cursor()

    def _update_spectrum_plot_from_router(self) -> None:
        """Refresh spectrum plot after a routed mode action mutates model state."""
        if self.view_stack is None or self.view_stack.spectrum_view is None:
            msg = "Spectrum view is required for mode intent plot updates."
            raise RuntimeError(msg)
        self.view_stack.spectrum_view.update_plot()

    def _optimize_spectrum_integration(self) -> SpectrumModeIntegrationPort | None:
        """Return optimize spectrum integration if available."""
        dock_coordinator = self._require_dock_coordinator()
        dock_coordinator.setup_optimize_integration()
        return dock_coordinator.optimize_integration()

    def _on_history_state_changed(self, state: HistoryState) -> None:
        """Handle history state changes to update toolbar buttons.

        Args:
            state: New history state.
        """
        if self.mode_context_bar:
            self.mode_context_bar.set_tool_enabled(ShellActionId.UNDO, state.can_undo)
            self.mode_context_bar.set_tool_enabled(ShellActionId.REDO, state.can_redo)

    @Slot()
    def open_observation_data(self) -> None:
        """Create a new project."""
        self._require_project_session().open_observation_data()

    @Slot()
    def open_project(self) -> None:
        """Open an existing project."""
        self._require_project_session().open_project()

    @Slot()
    def save_project(self) -> None:
        """Save the current project."""
        self._require_project_session().save_project()

    @Slot()
    def save_project_as(self) -> None:
        """Save the current project with a new name."""
        self._require_project_session().save_project_as()

    @Slot()
    def close_project(self) -> None:
        """Close the active project session."""
        self._require_project_session().close_project()

    def set_current_project(self, project: SpectroscopyProject | None) -> None:
        """Switch the current project through the shell session coordinator.

        Args:
            project: Project to set as current (None to clear).
        """
        self._require_project_session().switch_project(project)

    def refresh_after_project_change(self, project: SpectroscopyProject | None) -> None:
        """Set the current project and update UI.

        Args:
            project: Project to set as current (None to clear)
        """
        self._project_switch_coordinator.switch_project(project)
        self._set_region_topology_project(project)

    def _set_region_topology_project(self, project: SpectroscopyProject | None) -> None:
        """Attach the shell topology observer to exactly the active project."""
        adapter = self._region_topology_event_adapter
        if adapter is not None:
            adapter.region_topology_changed.disconnect(self._on_region_topology_changed)
            adapter.close()
            self._region_topology_event_adapter = None

        if project is None:
            return

        adapter = SpectrumModelEventAdapter(project.model, self)
        adapter.region_topology_changed.connect(self._on_region_topology_changed)
        self._region_topology_event_adapter = adapter

    def _setup_coordinators(self) -> None:
        """Setup component coordinators."""
        if self.mode_shell_coordinator is None:
            msg = "Mode coordinator must be initialized before shell signal setup."
            raise RuntimeError(msg)

        self._signal_connector.bind_runtime_surfaces(
            ShellSignalConnectorBindings(
                absorber_editor=self.absorber_editor,
                continuum_editor=self.continuum_editor,
                optimize_editor=self.optimize_editor,
                view_stack=self.view_stack,
                identify_panel=self._require_dock_coordinator().identify_panel,
                optimize_panel=self._require_dock_coordinator().region_detail_ui(),
            )
        )

    def _setup_data_control_coordinator(self) -> None:
        """Create the shared data-control coordinator when UI parts are available."""
        if self.data_control_panel is None:
            self._data_control_coordinator = None
            return

        self._data_control_coordinator = DataControlCoordinator(
            DataControlCoordinatorPorts(
                panel=self.data_control_panel,
                spectrum_view_provider=lambda: (
                    self.view_stack.spectrum_view if self.view_stack is not None else None
                ),
                status_message=self.status_message.emit,
            ),
            parent=self,
        )
        self._setup_display_menu_controller(self.data_control_panel)

    def _setup_display_menu_controller(self, panel: DataControlPanel) -> None:
        """Attach the Display menu toggles to the panel and the spectrum view."""
        controller = DisplayMenuController(parent=self)
        self._display_menu_controller = controller
        panel.attach_display_menu(controller.actions())

        action_factory = self._window_bootstrapper.parts.action_factory
        if action_factory is not None:
            action_factory.register_external_action(
                ShellActionId.TOGGLE_COMPONENT_PROFILES,
                controller.component_profiles_action,
                include_in_shortcuts_doc=True,
            )

        controller.display_options_changed.connect(self._analysis_navigation.set_display_options)

        spectrum_view = self.view_stack.spectrum_view if self.view_stack is not None else None
        if spectrum_view is None:
            return
        controller.display_options_changed.connect(spectrum_view.apply_display_options)
        spectrum_view.model_display_supported_changed.connect(
            controller.set_component_profiles_supported
        )
        controller.set_options(spectrum_view.display_options)

    def display_menu_actions(self) -> tuple[QAction, ...]:
        """Return the shared display toggles for menus outside the data control panel."""
        if self._display_menu_controller is None:
            return ()
        return self._display_menu_controller.actions()

    def restore_display_options(self, options: SpectrumDisplayOptions) -> None:
        """Restore Display-menu checks and the plot after a project switch."""
        self.display_menu_controller.set_options(options)
        spectrum_view = self.view_stack.spectrum_view if self.view_stack is not None else None
        if spectrum_view is None:
            return
        spectrum_view.apply_display_options(options)

    def _connect_signals(self) -> None:
        """Connect internal signals.

        This method only handles local UI connections.
        Cross-component connections are delegated to the shell signal connector.
        """
        self._signal_connector.connect_signals()

        self.status_message.connect(self._handle_status_message)

        self.project_changed.connect(self._on_project_changed)
        if self._data_control_coordinator is not None:
            self._data_control_coordinator.connect_signals()

    @Slot(str, int)
    def _handle_status_message(self, message: str, timeout_ms: int = 3000) -> None:
        """Route status updates to the shared status bar controller."""
        if self.status_controller:
            self.status_controller.show_message(message, timeout_ms)
        else:
            self.statusBar().showMessage(message, timeout_ms)

    def _emit_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Emit a status message if one is provided."""
        if not message:
            return
        self.status_message.emit(message, timeout_ms)

    @property
    def dialog_commands(self) -> DialogWorkflowCoordinator:
        """Return the shell dialog command owner."""
        return self._dialog_workflow

    @property
    def preset_dialog_port(self) -> DialogWorkflowCoordinator:
        """Return the preset dialog owner used by identify workflows."""
        return self._dialog_workflow

    @property
    def continuum_history_recorder(self) -> ContinuumHistoryRecorder | None:
        """Return the continuum history recorder for mode workflow adapters."""
        return self._history_recorder

    @property
    def identify_history_recorder(self) -> HistoryRecorder:
        """Return the identify history recorder for mode workflow adapters."""
        return self._history_recorder

    def _current_editing_mode(self) -> EditingMode | None:
        """Return the current editing mode for mode-local controllers."""
        if self.mode_state_store is None:
            return None
        return self.mode_state_store.current_mode

    def _identify_velocity_range(self) -> IdentifyVelocityRangePort | None:
        """Return the spectrum range port used by identify velocity plotting."""
        view_stack = self.view_stack
        spectrum_view = view_stack.spectrum_view if view_stack is not None else None
        if spectrum_view is None:
            return None
        if not isinstance(spectrum_view, IdentifyVelocityRangePort):
            msg = (
                "Identify velocity plotting requires a spectrum view implementing "
                "IdentifyVelocityRangePort."
            )
            raise TypeError(msg)
        return spectrum_view

    def _identify_velocity_workflow(self) -> IdentifyVelocityWorkflowPort:
        """Return the identify workflow owner used by velocity plotting."""
        coordinator = self.identify_coordinator
        if coordinator is None:
            msg = "Identify velocity plotting requires an identify coordinator."
            raise RuntimeError(msg)
        return coordinator

    def _identify_velocity_range_view(self) -> SpectrumView | None:
        """Return the concrete spectrum view for shell-side rendering callbacks."""
        view_stack = self.view_stack
        spectrum_view = view_stack.spectrum_view if view_stack is not None else None
        return spectrum_view if isinstance(spectrum_view, SpectrumView) else None

    def _set_wavelength_fields_enabled(self, enabled: bool) -> None:
        """Set wavelength field availability when velocity plotting is active."""
        if self._data_control_coordinator is not None:
            self._data_control_coordinator.set_wavelength_fields_enabled(enabled)

    def set_wavelength_fields_enabled(self, enabled: bool) -> None:
        """Set wavelength field availability through the shared port interface."""
        self._set_wavelength_fields_enabled(enabled)

    def _analysis_current_region_id(self) -> str | None:
        """Return the region currently focused in Analysis Detail."""
        return self._require_dock_coordinator().analysis_current_region_id()

    def _is_velocity_plot_visible(self) -> bool:
        """Return whether the shared velocity plot is currently visible."""
        spectrum_view = self._identify_velocity_range_view()
        return bool(spectrum_view is not None and spectrum_view.is_velocity_plot_visible())

    def _set_optimize_velocity_action_checked(self, checked: bool) -> None:
        """Set the optimize velocity plot action check state."""
        action = self._require_action_factory().actions.get(
            ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS
        )
        if action is not None:
            action.setChecked(checked)

    @Slot()
    def zoom_in(self) -> None:
        """Zoom in on the active spectrum view via menu or shortcut."""
        self._emit_zoom_shortcut(1.2)

    @Slot()
    def zoom_out(self) -> None:
        """Zoom out on the active spectrum view via menu or shortcut."""
        self._emit_zoom_shortcut(0.8)

    def _emit_zoom_shortcut(self, factor: float) -> None:
        """Dispatch a zoom intent generated outside the interactor.

        Args:
            factor: Zoom factor (>1 for zoom in, <1 for zoom out)
        """
        if not self.view_stack or not self.view_stack.spectrum_view:
            return

        spectrum_view = self.view_stack.spectrum_view
        # Access coordinator directly; SpectrumView always has this attribute
        spectrum_view.coordinator.handle_navigation_intent(ZoomFactorIntent(factor=factor))

    # Delegate event handling to WindowLifecycleCoordinator
    def _setup_event_handling(self) -> None:
        """Setup event handling."""
        self._window_lifecycle.setup_event_handling()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter events.

        Args:
            event: Drag enter event
        """
        self._window_lifecycle.handle_drag_enter_event(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop events.

        Args:
            event: Drop event
        """
        self._window_lifecycle.handle_drop_event(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle close events.

        Args:
            event: Close event
        """
        self._window_lifecycle.handle_close_event(event)

    def _resolution_change_notifier(self) -> ResolutionChangeNotifier | None:
        """Return the active resolution change notifier."""
        coordinator = self.identify_coordinator
        if isinstance(coordinator, ResolutionChangeNotifier):
            return coordinator
        return None

    def _cosmology_change_notifier(self) -> CosmologyChangeNotifier | None:
        """Return the active cosmology change notifier."""
        if self._dock_coordinator is None:
            return None
        region_detail_ui = self._dock_coordinator.region_detail_ui()
        if isinstance(region_detail_ui, CosmologyChangeNotifier):
            return region_detail_ui
        return None

    @Slot(object)
    def _on_project_changed(self, project: SpectroscopyProject) -> None:
        """Handle project change events.

        Args:
            project: New current project
        """
        # Update range selector with spectrum data
        if self.range_selector and project and project.model.observed_spectrum:
            wavelength = project.model.observed_spectrum.wavelength
            flux = project.model.observed_spectrum.flux
            if wavelength is not None and flux is not None:
                self.range_selector.set_spectrum_data(wavelength.tolist(), flux.tolist())

        # Update history bridge with new project
        if self._history_bridge:
            self._history_bridge.set_project(project)

    @Slot(str, QWidget)
    def _emit_active_view_status(self, view_name: str, _view_widget: QWidget) -> None:
        """Emit a status update when the active view changes."""
        view_template = QCoreApplication.translate("MainWindow", "Switched to {name} view")
        self.status_message.emit(view_template.format(name=view_name), 1000)

    def handle_cursor_coordinates_changed(self, wavelength: float, flux: float) -> None:
        """Update status bar with latest cursor coordinates."""
        if self.status_controller:
            self.status_controller.update_coordinates(wavelength, flux)
            self.status_controller.set_coordinates_visible(True)

    def handle_cursor_coordinates_cleared(self) -> None:
        """Clear coordinate display when cursor exits the spectrum view."""
        if self.status_controller:
            self.status_controller.clear_coordinates()

    def switch_mode(self, mode: EditingMode) -> None:
        """Public API for switching to specified editing mode.

        Args:
            mode: Target editing mode
        """
        self._switch_mode(mode)

    @Slot()
    def _show_fit_started_status(self) -> None:
        """Update shell UI when optimize fitting starts."""
        self.status_message.emit(QCoreApplication.translate("MainWindow", "Fitting model..."), 0)
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate

        self._require_action_factory().set_fit_running(True)

    @Slot(dict)
    def _show_fit_completed_status(self, results: FitResultRawPayload) -> None:
        """Update shell UI when optimize fitting completes."""
        if self.progress_bar:
            self.progress_bar.setVisible(False)

        self._require_action_factory().set_fit_running(False)

        # Display results
        if results.get("success"):
            chi2 = results.get("chi_squared", 0)
            complete_template = QCoreApplication.translate(
                "MainWindow", "Fit completed: χ² = {value:.3f}"
            )
            self.status_message.emit(complete_template.format(value=chi2), 3000)
            self._optimize_runtime.refresh_visible_velocity_overlay()
        else:
            message = results.get("message", "Unknown error")
            failure_template = QCoreApplication.translate("MainWindow", "Fit failed: {error}")
            self.status_message.emit(failure_template.format(error=message), 5000)

    @Slot()
    def _switch_mode(self, mode: EditingMode) -> None:
        """Switch to specified editing mode.

        Args:
            mode: Target editing mode
        """
        if not self.mode_shell_coordinator:
            msg = "Mode shell coordinator is not initialized."
            raise RuntimeError(msg)

        if (
            self.mode_shell_coordinator.get_current_mode() is EditingMode.ANALYSIS
            and mode is not EditingMode.ANALYSIS
            and self._analysis_surface_coordinator is not None
            and not self._analysis_surface_coordinator.can_leave_analysis()
        ):
            return

        self.mode_shell_coordinator.switch_mode(mode)

    @Slot()
    def reset_view(self) -> None:
        """Public slot to reset spectrum view ranges."""
        if self._data_control_coordinator is not None:
            self._data_control_coordinator.reset_view()

    @Slot()
    def auto_adjust_flux(self) -> None:
        """Public slot to auto-adjust flux axis."""
        if self._data_control_coordinator is not None:
            self._data_control_coordinator.auto_adjust_flux()

    def _on_region_topology_changed(self, event: RegionTopologyChanged) -> None:
        """Recover removed Analysis focus and refresh topology-dependent overlays."""
        if not self.mode_shell_coordinator:
            return
        current_mode = self.mode_shell_coordinator.get_current_mode()
        if current_mode != EditingMode.ANALYSIS:
            return
        focused_region_id = self._analysis_navigation.state.focused_region_id
        if (
            focused_region_id is not None
            and focused_region_id in event.removed_region_ids
            and self._analysis_surface_coordinator is not None
        ):
            self._analysis_surface_coordinator.handle_focused_region_removed(focused_region_id)
        self.mode_shell_coordinator.refresh_line_overlays_for_mode(current_mode)

    # Coordinator callback methods
    def _on_optimize_region_changed(self, _event: OptimizeMaskGroupChange) -> None:
        """Handle optimize mode region selection change."""
        self._optimize_runtime.refresh_visible_velocity_overlay()

    def _on_coordinator_mode_changed(self, mode: EditingMode) -> None:
        """Handle mode change from coordinator.

        Args:
            mode: New editing mode
        """
        if mode is EditingMode.ANALYSIS and self._analysis_surface_coordinator is not None:
            self._handle_analysis_focused_region_changed(
                self._analysis_navigation.state.focused_region_id
            )
            self._analysis_surface_coordinator.restore()
            self._restore_analysis_spectrum_range()
        if mode != EditingMode.ANALYSIS:
            self._velocity_overlay_port.hide_velocity_overlay(context="optimize")
