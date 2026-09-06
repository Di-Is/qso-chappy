"""Composition helpers for building the shell runtime."""

from __future__ import annotations

import logging
from functools import partial
from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from PySide6.QtCore import QCoreApplication

from chappy.core.editing_mode import EditingMode
from chappy.gui.adapters.analysis_navigation_settings import QSettingsAnalysisNavigationAdapter
from chappy.gui.modes.analysis.region_detail import OptimizeModeRuntime, OptimizeModeRuntimePorts
from chappy.gui.modes.analysis.region_detail.composition import build_region_detail
from chappy.gui.modes.common.analysis_navigation import (
    AnalysisNavigationPersistenceIssue,
    AnalysisNavigationPersistenceOperation,
)
from chappy.gui.modes.continuum.coordinator import ContinuumCoordinator
from chappy.gui.modes.continuum.shared_surface_context_controller import (
    ContinuumSharedSurfaceContextController,
    ContinuumSharedSurfaceEditorPort,
)
from chappy.gui.modes.identify import IdentifyModeRuntime
from chappy.gui.modes.identify.coordinator import IdentifyModeCoordinator
from chappy.gui.shell.absorber_coordinator import AbsorberCoordinator
from chappy.gui.shell.actions.dispatcher import ActionDispatcher
from chappy.gui.shell.analysis_navigation_coordinator import AnalysisNavigationCoordinator
from chappy.gui.shell.dependencies import (
    ModeCommandPort,
    ShellRuntimeParts,
    SpectrumNavigationPort,
)
from chappy.gui.shell.dialog_coordinator import ResolutionDialogAdapter, UserManualDialogAdapter
from chappy.gui.shell.dialog_workflow_coordinator import (
    DialogWorkflowCoordinator,
    DialogWorkflowPorts,
)
from chappy.gui.shell.history_wiring_coordinator import (
    HistoryWiringCoordinator,
    HistoryWiringPorts,
)
from chappy.gui.shell.identify_shell_adapter import build_identify_shell_ports
from chappy.gui.shell.mode_shell_coordinator import ModeShellCoordinator
from chappy.gui.shell.project_session_controller import ProjectSessionController
from chappy.gui.shell.runtime import ShellRuntime
from chappy.gui.shell.signal_connector import ShellSignalConnector
from chappy.gui.shell.spectrum_surface_coordinator import (
    SpectrumSurfaceCoordinator,
    SpectrumSurfacePorts,
)
from chappy.gui.shell.user_manual_controller import UserManualController
from chappy.gui.shell.velocity_overlay_port_adapter import SpectrumVelocityOverlayPort
from chappy.gui.shell.window_bootstrapper import WindowBootstrapper, WindowLifecycleCoordinator

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.modes.continuum.coordinator import ContinuumCoordinatorShell
    from chappy.gui.shell.dependencies import ShellDependencies
    from chappy.gui.shell.main_window import MainWindow


@runtime_checkable
class _ContinuumEditorOwner(Protocol):
    """Plot widget exposing a continuum editor for shared-surface commands."""

    continuum_editor: ContinuumSharedSurfaceEditorPort | None


@runtime_checkable
class _PlotWidgetOwner(Protocol):
    """Plot host exposing the active plot widget."""

    plot_widget: _ContinuumEditorOwner | None


class _ShellModeCommands(ModeCommandPort):
    """Mode command adapter built from composition-owned collaborators."""

    def __init__(
        self, *, main_window: MainWindow, mode_shell_coordinator: ModeShellCoordinator
    ) -> None:
        """Store the collaborators required for mode-owned commands."""
        self._main_window = main_window
        self._mode_shell_coordinator = mode_shell_coordinator

    def switch_mode(self, mode: EditingMode) -> None:
        """Switch the active editing mode."""
        self._main_window.switch_mode(mode)

    def add_continuum(self) -> None:
        """Add a continuum component through the continuum owner."""
        self._main_window.continuum_mode_runtime.add_continuum()

    def fit_model(self) -> None:
        """Run the optimize fit workflow."""
        self._main_window.optimize_velocity_runtime.fit_model()

    def back_to_analysis_overview(self) -> None:
        """Return to Overview through the Analysis surface owner."""
        self._main_window.back_to_analysis_overview()

    def delete_selection(self) -> None:
        """Delete Structure selection through its guarded common path."""
        if self._mode_shell_coordinator.get_current_mode() is not EditingMode.ANALYSIS:
            return
        self._main_window.delete_analysis_structure_selection()


class _ShellSpectrumNavigationCommands(SpectrumNavigationPort):
    """Navigation command adapter built from composition-owned collaborators."""

    def __init__(self, *, main_window: MainWindow) -> None:
        """Store the collaborators required for spectrum navigation commands."""
        self._main_window = main_window

    def zoom_in(self) -> None:
        """Zoom in on the active spectrum view."""
        self._main_window.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out on the active spectrum view."""
        self._main_window.zoom_out()

    def reset_view(self) -> None:
        """Reset the active spectrum ranges."""
        self._main_window.reset_view()

    def auto_adjust_flux(self) -> None:
        """Auto-adjust the active flux range."""
        self._main_window.auto_adjust_flux()

    def toggle_velocity_plot_optimize(self) -> None:
        """Toggle the optimize velocity overlay."""
        self._main_window.optimize_velocity_runtime.toggle_velocity_overlay()

    def toggle_velocity_plot_identify(self) -> None:
        """Toggle Identify's velocity plot at the wavelength under the cursor."""
        self._main_window.identify_velocity_runtime.handle_mode_velocity_shortcut()


def create_shell_runtime(deps: ShellDependencies) -> ShellRuntime:
    """Create the shell runtime entrypoint.

    Args:
        deps: Dependency bundle required to compose the shell.

    Returns:
        Runtime wrapper hiding the concrete main-window owner.
    """
    main_window = create_main_window(deps)
    return ShellRuntime(
        main_window,
        project_io_usecase=deps.project_io_usecase,
        dialog_commands=main_window.dialog_commands,
    )


def create_main_window(deps: ShellDependencies) -> MainWindow:
    """Build the current concrete main-window implementation."""
    shell_parts_factory = partial(build_shell_runtime_parts, deps=deps)
    return _create_main_window(deps, shell_parts_factory=shell_parts_factory)


def build_shell_runtime_parts(
    main_window: MainWindow, deps: ShellDependencies
) -> ShellRuntimeParts:
    """Create the shell-owned collaborators for a main window instance."""
    window_bootstrapper = WindowBootstrapper(
        main_window,
        optimize_model_addition_usecase=deps.optimize_model_addition_usecase,
        region_detail_factory=build_region_detail,
    )
    project_session = ProjectSessionController(
        main_window,
        project_io=deps.project_io_usecase,
        refresh_callback=main_window.refresh_after_project_change,
    )
    signal_connector = ShellSignalConnector(main_window)
    window_lifecycle = WindowLifecycleCoordinator(main_window)
    mode_shell_coordinator = ModeShellCoordinator(main_window)
    analysis_navigation = AnalysisNavigationCoordinator(
        settings=QSettingsAnalysisNavigationAdapter(),
        enter_mode=mode_shell_coordinator.enter_project_mode,
        parent=main_window,
    )
    project_session.project_context_changing.connect(
        analysis_navigation.handle_project_context_changing
    )
    project_session.project_context_changed.connect(
        analysis_navigation.handle_project_context_changed
    )
    analysis_navigation.display_options_changed.connect(main_window.restore_display_options)
    project_session.project_context_changed.connect(
        main_window._reconcile_analysis_focus_with_selector
    )
    analysis_navigation.persistence_error.connect(
        partial(_show_analysis_navigation_persistence_error, main_window=main_window)
    )
    dialog_workflow = DialogWorkflowCoordinator(
        DialogWorkflowPorts(
            parent=main_window,
            language_switcher=main_window._language_switcher,
            language_changed_signal=main_window._language_switcher.language_changed,
            project_changed_signal=main_window.project_changed,
            user_manual_controller=UserManualController(
                UserManualDialogAdapter(), main_window._language_switcher
            ),
            resolution_dialogs=ResolutionDialogAdapter(),
            resolution_updates=main_window._resolution_updates,
            current_project_provider=lambda: main_window.current_project,
            project_file_path_provider=lambda: main_window.project_file_path,
            resolution_change_notifier_provider=main_window._resolution_change_notifier,
            resolution_history_recorder_provider=lambda: main_window._history_recorder,
            cosmology_change_notifier_provider=main_window._cosmology_change_notifier,
            action_factory_provider=lambda: main_window.action_factory,
            mode_shell_coordinator_provider=lambda: main_window.mode_shell_coordinator,
            status_message=main_window.show_status_message,
            preset_store=deps.preset_store,
            atomic_data=deps.atomic_data,
        )
    )
    mode_commands = _ShellModeCommands(
        main_window=main_window, mode_shell_coordinator=mode_shell_coordinator
    )
    navigation_commands = _ShellSpectrumNavigationCommands(main_window=main_window)
    action_dispatcher = ActionDispatcher(
        project_commands=main_window,
        mode_commands=mode_commands,
        dialog_commands=dialog_workflow,
        navigation_commands=navigation_commands,
        window_commands=main_window,
        status_emitter=main_window.show_status_message,
        tutorial_callback=main_window.show_welcome_dialog,
        about_callback=main_window.show_about_dialog,
        spectrum_policy_provider=lambda: (
            main_window.view_stack.spectrum_view.current_policy
            if main_window.view_stack is not None
            and main_window.view_stack.spectrum_view is not None
            else None
        ),
        # Resolve after OptimizeModeRuntime is initialized below.
        fit_running_provider=lambda: optimize_runtime.is_fit_running(),  # noqa: PLW0108
    )
    absorber_coordinator = AbsorberCoordinator(main_window)
    continuum_coordinator = ContinuumCoordinator(
        cast("ContinuumCoordinatorShell", main_window), main_window
    )
    identify_coordinator = IdentifyModeCoordinator(
        main_window,
        shell_ports=build_identify_shell_ports(main_window),
        atomic_data=deps.atomic_data,
        preset_store=deps.preset_store,
    )
    main_window.project_changed.connect(identify_coordinator.handle_project_changed)
    identify_coordinator.open_analysis_region_requested.connect(
        main_window.handle_identify_open_analysis_region
    )
    identify_coordinator.open_analysis_structure_requested.connect(
        main_window.handle_identify_open_analysis_structure
    )
    velocity_overlay_port = SpectrumVelocityOverlayPort(
        spectrum_view_provider=main_window._identify_velocity_range_view
    )
    identify_runtime = IdentifyModeRuntime(
        current_mode_provider=main_window._current_editing_mode,
        workflow_provider=lambda: identify_coordinator,
        velocity_workflow_provider=main_window._identify_velocity_workflow,
        velocity_range_provider=main_window._identify_velocity_range,
        cursor_wavelength_provider=main_window._wavelength_under_cursor,
        velocity_overlay_port=velocity_overlay_port,
        wavelength_field_availability_port=main_window,
    )
    optimize_runtime = OptimizeModeRuntime(
        OptimizeModeRuntimePorts(
            current_mode_provider=main_window._current_editing_mode,
            integration_provider=main_window._optimize_spectrum_integration,
            spectrum_update_callback=main_window._update_spectrum_plot_from_router,
            project_provider=lambda: main_window.current_project,
            optimize_editor_provider=lambda: main_window.optimize_editor,
            selected_region_id_provider=main_window._analysis_current_region_id,
            velocity_visible_provider=velocity_overlay_port.is_velocity_overlay_visible,
            velocity_overlay_port=velocity_overlay_port,
            action_checked_callback=main_window._set_optimize_velocity_action_checked,
            status_message_callback=main_window.show_status_message,
            context_menu_action_provider=lambda wavelength: (
                main_window._require_dock_coordinator().optimize_context_menu_actions(wavelength)
            ),
        )
    )
    continuum_runtime = ContinuumSharedSurfaceContextController(
        editor_provider=lambda: _continuum_context_editor(main_window),
        add_continuum_callback=continuum_coordinator.add_continuum,
    )
    history_wiring = HistoryWiringCoordinator(
        HistoryWiringPorts(
            history_bridge=main_window._history_bridge,
            history_recorder=main_window._history_recorder,
            view_stack_provider=lambda: main_window.view_stack,
            continuum_editor_provider=lambda: main_window.continuum_editor,
            dock_coordinator_provider=main_window._require_dock_coordinator,
            current_project_provider=lambda: main_window.current_project,
            action_factory_provider=lambda: main_window.action_factory,
            state_changed_callback=main_window._on_history_state_changed,
        )
    )
    spectrum_surface = SpectrumSurfaceCoordinator(
        SpectrumSurfacePorts(
            project_provider=lambda: main_window.current_project,
            history_provider=lambda: main_window._history_recorder,
            view_stack_provider=lambda: main_window.view_stack,
            active_runtime_provider=lambda: (
                main_window.mode_shell_coordinator.active_mode_runtime()
                if main_window.mode_shell_coordinator is not None
                else None
            ),
            # Late binding: the optimize runtime is assigned to the window only
            # after this composition returns its ShellRuntimeParts.
            refresh_velocity_overlay=(
                lambda: main_window.optimize_velocity_runtime.refresh_visible_velocity_overlay()  # noqa: PLW0108
            ),
            display_actions_provider=main_window.display_menu_actions,
        )
    )
    return ShellRuntimeParts(
        window_bootstrapper=window_bootstrapper,
        project_session=project_session,
        signal_connector=signal_connector,
        window_lifecycle=window_lifecycle,
        action_dispatcher=action_dispatcher,
        mode_shell_coordinator=mode_shell_coordinator,
        analysis_navigation=analysis_navigation,
        absorber_coordinator=absorber_coordinator,
        continuum_coordinator=continuum_coordinator,
        identify_coordinator=identify_coordinator,
        dialog_workflow=dialog_workflow,
        history_wiring=history_wiring,
        spectrum_surface=spectrum_surface,
        velocity_overlay_port=velocity_overlay_port,
        continuum_mode_runtime=continuum_runtime,
        identify_velocity_runtime=identify_runtime,
        optimize_velocity_runtime=optimize_runtime,
        mode_runtimes={
            EditingMode.ANALYSIS: optimize_runtime,
            EditingMode.IDENTIFY: identify_runtime,
            EditingMode.CONTINUUM: continuum_runtime,
        },
    )


def _continuum_context_editor(main_window: MainWindow) -> ContinuumSharedSurfaceEditorPort | None:
    """Resolve the active continuum editor from the current spectrum view."""
    view_stack = main_window.view_stack
    if view_stack is None or view_stack.spectrum_view is None:
        return None

    plot_host = view_stack.spectrum_view.plot_host
    if not isinstance(plot_host, _PlotWidgetOwner):
        return None

    plot_widget = plot_host.plot_widget
    if not isinstance(plot_widget, _ContinuumEditorOwner):
        return None

    return plot_widget.continuum_editor


def _show_analysis_navigation_persistence_error(issue: object, *, main_window: MainWindow) -> None:
    """Report a non-fatal local UI-state persistence failure in shell status."""
    if not isinstance(issue, AnalysisNavigationPersistenceIssue):
        message = "Unexpected Analysis navigation persistence issue payload"
        raise TypeError(message)
    logger.warning(
        "Analysis navigation %s failed for %s: %s",
        issue.operation.value,
        issue.project_key.value,
        issue.message,
    )
    status = _analysis_navigation_persistence_status(issue.operation)
    main_window.show_status_message(status, 5000)


def _analysis_navigation_persistence_status(
    operation: AnalysisNavigationPersistenceOperation,
) -> str:
    """Return a translated, user-facing recovery message for local view state."""
    if operation is AnalysisNavigationPersistenceOperation.LOAD:
        return QCoreApplication.translate(
            "MainWindow",
            "Previous Analysis view settings could not be restored. Overview is shown; project data is unchanged.",
        )
    if operation is AnalysisNavigationPersistenceOperation.SAVE:
        return QCoreApplication.translate(
            "MainWindow",
            "Analysis view settings could not be saved. You can keep working; project data is unchanged, but this view may not be restored next time.",
        )
    if operation is AnalysisNavigationPersistenceOperation.MIGRATE:
        return QCoreApplication.translate(
            "MainWindow",
            "Analysis view settings could not be saved for the new file. You can keep working; project data is unchanged, but this view may not be restored next time.",
        )
    message = f"Unsupported Analysis navigation persistence operation: {operation}"
    raise ValueError(message)


def _create_main_window(
    deps: ShellDependencies, *, shell_parts_factory: Callable[[MainWindow], ShellRuntimeParts]
) -> MainWindow:
    """Instantiate the concrete main window with composition-owned collaborators."""
    main_window_module = import_module("chappy.gui.shell.main_window")
    main_window_class = cast("type[MainWindow]", main_window_module.MainWindow)

    return main_window_class(
        project_io_usecase=deps.project_io_usecase,
        atomic_data=deps.atomic_data,
        preset_store=deps.preset_store,
        optimize_model_addition_usecase=deps.optimize_model_addition_usecase,
        shell_parts_factory=shell_parts_factory,
    )
