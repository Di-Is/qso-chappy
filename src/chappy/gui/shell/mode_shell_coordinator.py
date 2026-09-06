"""Mode management coordination and UI state control for main window."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP, QObject, Signal
from PySide6.QtWidgets import QWidget

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.analysis.lifecycle import AnalysisLifecycleCoordinator
from chappy.gui.modes.continuum import ContinuumModeLifecycle
from chappy.gui.modes.identify import IdentifyModeLifecycle
from chappy.gui.modes.mode_state_store import ModeStateStore
from chappy.gui.shell.interaction_mode_coordinator import InteractionModeCoordinator
from chappy.gui.shell.mode_context_bar import ModeContextBar
from chappy.gui.shell.mode_continuum_adapter import ModeContinuumAdapter
from chappy.gui.shell.mode_identify_workflow_adapter import ModeIdentifyWorkflowAdapter
from chappy.gui.shell.mode_lifecycle_router import ModeLifecycleRouter
from chappy.gui.shell.mode_line_overlay_adapter import ModeLineOverlayAdapter
from chappy.gui.shell.mode_toolbar_controller import ModeToolbarController
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.gui.shell.spectrum_region_focus_controller import SpectrumRegionFocusController
from chappy.gui.shell.status_bar import StatusBarController

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from PySide6.QtGui import QAction

    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.common import ModeLifecycle, ModeRuntime
    from chappy.gui.shell.actions.ids import ShellActionId
    from chappy.gui.shell.dock_layout_coordinator import DockLayoutCoordinator
    from chappy.gui.shell.main_window import MainWindow
    from chappy.gui.shell.menu_action_factory import MenuActionFactory
    from chappy.gui.shell.mode_context_bar import ModeContextConfig
    from chappy.gui.shell.view_stack import ViewStack
    from chappy.gui.spectrum.interaction_state_coordinator import SpectrumInteractionSnapshot
    from chappy.gui.spectrum.policy import SpectrumPolicy
    from chappy.gui.spectrum.spectrum_view import SpectrumView

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _ContextTextSource:
    """Qt source text for a mode context bar field."""

    text: str
    disambiguation: str | None = None


@dataclass(frozen=True, slots=True)
class ModeShellUiParts:
    """Typed shell UI references used by the mode coordinator."""

    view_stack: ViewStack | None = None
    mode_context_bar: ModeContextBar | None = None
    action_factory: MenuActionFactory | None = None
    action_map_provider: Callable[[], Mapping[ShellActionId, QAction]] | None = None
    dock_coordinator: DockLayoutCoordinator | None = None
    data_control_panel: QWidget | None = None
    status_controller: StatusBarController | None = None
    range_dock: QWidget | None = None
    current_project_provider: Callable[[], SpectroscopyProject | None] | None = None
    hide_velocity_plot: Callable[[], None] | None = None
    analysis_detail_active_provider: Callable[[], bool] | None = None


_CONTEXT_TEXT_SOURCES: dict[str, _ContextTextSource] = {
    "start.subtitle": _ContextTextSource(
        text=str(
            QT_TRANSLATE_NOOP(
                "ModeShellCoordinator", "Load observation data or a project to continue"
            )
        )
    ),
    "analysis.title": _ContextTextSource(
        text=str(QT_TRANSLATE_NOOP("ModeShellCoordinator", "Analysis"))
    ),
    "analysis.subtitle": _ContextTextSource(
        text=str(QT_TRANSLATE_NOOP("ModeShellCoordinator", "Review and analyze regions"))
    ),
    "identify.title": _ContextTextSource(
        text=str(QT_TRANSLATE_NOOP("ModeShellCoordinator", "Identify"))
    ),
    "identify.subtitle_default": _ContextTextSource(
        text=str(
            QT_TRANSLATE_NOOP(
                "ModeShellCoordinator", "Associate detected regions with absorption lines"
            )
        )
    ),
    "continuum.title": _ContextTextSource(
        text=str(QT_TRANSLATE_NOOP("ModeShellCoordinator", "Continuum Editing"))
    ),
    "continuum.subtitle": _ContextTextSource(
        text=str(QT_TRANSLATE_NOOP("ModeShellCoordinator", "Edit continuum control points"))
    ),
}


class ModeShellCoordinator(QObject):
    """Coordinates editing modes and UI state transitions.

    This class coordinates all mode-related functionality including
    mode switching, UI updates, and state synchronization.
    """

    # Signals
    mode_changed = Signal(EditingMode)
    status_message = Signal(str)  # message

    def __init__(self, main_window: MainWindow) -> None:
        """Initialize mode shell coordinator.

        Args:
            main_window: Parent main window instance
        """
        super().__init__()
        self.main_window = main_window
        self.mode_state_store: ModeStateStore | None = None
        self._continuum_adapter = ModeContinuumAdapter(main_window)
        self._identify_workflow_adapter = ModeIdentifyWorkflowAdapter(main_window)
        self._line_overlay_adapter = ModeLineOverlayAdapter(main_window)
        self._mode_lifecycles: dict[EditingMode, ModeLifecycle] = {
            EditingMode.ANALYSIS: AnalysisLifecycleCoordinator(
                self._line_overlay_adapter, self._continuum_adapter
            ),
            EditingMode.IDENTIFY: IdentifyModeLifecycle(
                self._line_overlay_adapter,
                self._continuum_adapter,
                self._identify_workflow_adapter,
            ),
            EditingMode.CONTINUUM: ContinuumModeLifecycle(
                self._line_overlay_adapter, self._continuum_adapter
            ),
        }
        self._lifecycle_router = ModeLifecycleRouter(self._mode_lifecycles)
        self._ui_parts = ModeShellUiParts()
        self._mode_runtimes: dict[EditingMode, ModeRuntime] = {}
        self._interaction_mode_coordinator = InteractionModeCoordinator(
            spectrum_view_provider=self._require_spectrum_view,
            current_mode_provider=lambda: self._require_mode_state_store().current_mode,
            zoom_button_callback=self._set_zoom_button_checked,
            mode_display_callback=self._update_mode_display,
        )
        self._toolbar_controller = ModeToolbarController(
            action_map_provider=self._shell_action_map,
            zoom_rect_toggle_callback=self._interaction_mode_coordinator.handle_zoom_rect_mode,
        )

    def _require_mode_state_store(self) -> ModeStateStore:
        """Return the configured mode state store or fail fast."""
        if self.mode_state_store is None:
            msg = "Mode state store is required for mode shell coordination."
            raise RuntimeError(msg)
        return self.mode_state_store

    def lifecycle_for_mode(self, mode: EditingMode) -> ModeLifecycle:
        """Return the required lifecycle for a mode.

        Args:
            mode: Editing mode whose lifecycle is required.

        Returns:
            Lifecycle registered for the mode.

        Raises:
            RuntimeError: If the mode has no registered lifecycle.
        """
        return self._lifecycle_router.lifecycle_for_mode(mode)

    def setup_mode_state_store(self) -> None:
        """Initialize the mode state store and connect to views."""
        self.mode_state_store = ModeStateStore()
        logger.debug("Mode state store initialized")

        # Connect mode state store to views
        view_stack = self._view_stack()
        if view_stack is not None:
            self._connect_presenter_signals()
            self._require_spectrum_view().policy_applied.connect(self._on_spectrum_policy_applied)
            self._require_spectrum_view().policy_invalidated.connect(
                self._on_spectrum_policy_invalidated
            )

        # Connect context bar signals
        context_bar = self._mode_context_bar()
        if context_bar is not None:
            self._connect_context_bar_signals(context_bar)

        # Connect signals
        mode_state_store = self._require_mode_state_store()
        mode_state_store.mode_changed.connect(self._on_mode_changed)

        # Ensure application starts in start mode when no project is active
        if self._current_project() is None:
            mode_state_store.switch_mode(EditingMode.START)
            return

        # Apply initial UI state based on current mode
        self._on_mode_changed(mode_state_store.current_mode)

    def _connect_presenter_signals(self) -> None:
        """Connect spectrum presenter signals to coordinator handlers."""
        self._interaction_mode_coordinator.connect_presenter()

    def _on_spectrum_policy_applied(self, policy: SpectrumPolicy) -> None:
        """Apply shell action capabilities after the spectrum policy commits."""
        run_postcommit_actions_isolated(
            lambda: self._interaction_mode_coordinator.handle_policy_committed(policy)
        )
        action_factory = self._action_factory()
        if action_factory is not None:
            run_postcommit_actions_isolated(lambda: action_factory.update_spectrum_policy(policy))

    def _on_spectrum_policy_invalidated(self) -> None:
        """Disable shell commands after an unrecoverable view policy rollback."""
        run_postcommit_actions_isolated(
            self._interaction_mode_coordinator.handle_policy_invalidated
        )
        action_factory = self._action_factory()
        if action_factory is not None:
            run_postcommit_actions_isolated(action_factory.clear_spectrum_policy)

    def _require_spectrum_view(self) -> SpectrumView:
        """Return the required spectrum view for shell mode coordination."""
        view_stack = self._view_stack()
        if view_stack is None:
            msg = "View stack is required for mode shell coordination."
            raise RuntimeError(msg)

        spectrum_view = view_stack.spectrum_view
        if spectrum_view is None:
            msg = "Spectrum view is required for mode shell coordination."
            raise RuntimeError(msg)
        return spectrum_view

    def set_ui_parts(self, ui_parts: ModeShellUiParts) -> None:
        """Inject typed UI parts built by the shell bootstrap process."""
        self._ui_parts = ui_parts

    def set_mode_runtime(self, mode: EditingMode, runtime: ModeRuntime) -> None:
        """Register the shared spectrum runtime for a mode."""
        self._mode_runtimes[mode] = runtime

    def set_mode_runtimes(self, runtimes: Mapping[EditingMode, ModeRuntime]) -> None:
        """Register the shared spectrum runtimes for multiple modes."""
        self._mode_runtimes.update(runtimes)

    def active_mode_runtime(self) -> ModeRuntime | None:
        """Return the registered runtime for the active mode, if any."""
        mode_state_store = self.mode_state_store
        if mode_state_store is None:
            return None
        mode = mode_state_store.current_mode
        if mode is EditingMode.ANALYSIS:
            provider = self._ui_parts.analysis_detail_active_provider
            if provider is None or not provider():
                return None
        return self._mode_runtimes.get(mode)

    def _view_stack(self) -> ViewStack | None:
        """Return the configured view stack."""
        return self._ui_parts.view_stack or self.main_window.view_stack

    def _current_spectrum_view(self) -> SpectrumView | None:
        """Return the current spectrum view when available."""
        view_stack = self._view_stack()
        return view_stack.spectrum_view if view_stack is not None else None

    def _current_project(self) -> SpectroscopyProject | None:
        """Return the configured current project."""
        provider = self._ui_parts.current_project_provider
        if provider is not None:
            return provider()
        return self.main_window.current_project

    def _mode_context_bar(self) -> ModeContextBar | None:
        """Return the configured context bar."""
        return self._ui_parts.mode_context_bar or self.main_window.mode_context_bar

    def _action_factory(self) -> MenuActionFactory | None:
        """Return the configured action factory."""
        return self._ui_parts.action_factory or self.main_window.action_factory

    def _shell_action_map(self) -> Mapping[ShellActionId, QAction]:
        """Return the registered shell action map."""
        action_map_provider = self._ui_parts.action_map_provider
        if action_map_provider is not None:
            return action_map_provider()

        action_factory = self._action_factory()
        if action_factory is None:
            msg = "Shell action map requires a registered action factory."
            raise RuntimeError(msg)
        return action_factory.get_all_actions()

    def _dock_coordinator(self) -> DockLayoutCoordinator | None:
        """Return the configured dock coordinator."""
        return self._ui_parts.dock_coordinator or self.main_window.dock_coordinator

    def _data_control_panel(self) -> QWidget | None:
        """Return the configured data-control panel."""
        return self._ui_parts.data_control_panel or self.main_window.data_control_panel

    def _status_controller(self) -> StatusBarController | None:
        """Return the configured status controller."""
        return self._ui_parts.status_controller or self.main_window.status_controller

    def _range_dock(self) -> QWidget | None:
        """Return the configured range dock."""
        return self._ui_parts.range_dock or self.main_window.range_dock

    def _hide_velocity_plot(self) -> None:
        """Hide the shared velocity plot via the configured callback."""
        callback = self._ui_parts.hide_velocity_plot
        if callback is not None:
            callback()
            return
        self.main_window.identify_velocity_runtime.hide_velocity_plot()

    @property
    def _latest_interaction_snapshot(self) -> SpectrumInteractionSnapshot | None:
        """Compatibility accessor for tests migrating off coordinator-owned interaction state."""
        return self._interaction_mode_coordinator.latest_interaction_snapshot

    @property
    def _requested_interaction_mode(self) -> str | None:
        """Compatibility accessor for tests migrating off coordinator-owned interaction state."""
        return self._interaction_mode_coordinator.requested_interaction_mode

    def _set_zoom_button_checked(self, checked: bool) -> None:
        """Synchronize zoom button checked state across UI components."""
        self._toolbar_controller.set_zoom_button_checked(checked)
        if self._toolbar_controller.has_bound_context_bar:
            return
        context_bar = self._mode_context_bar()
        if context_bar is not None:
            context_bar.set_zoom_mode_active(checked)

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Set the current project for the mode state store.

        Args:
            project: Project instance to associate with the mode state store
        """
        mode_state_store = self._require_mode_state_store()
        mode_state_store.set_project(project)
        self._set_lifecycle_project(project)

    def enter_project_mode(self, mode: EditingMode) -> None:
        """Enter the resolver-selected mode after project and path setup completes."""
        mode_state_store = self._require_mode_state_store()
        if mode_state_store.current_mode != mode:
            self.switch_mode(mode)
            return
        self._activate_mode_lifecycle(mode, reason="project-entry")
        self._interaction_mode_coordinator.apply_policy(spectrum_interaction_mode_policy(mode))
        self._update_ui_for_mode(mode)
        self._update_mode_display(mode)

    def switch_mode(self, mode: EditingMode) -> None:
        """Switch to specified editing mode.

        Args:
            mode: Target editing mode
        """
        self._require_mode_state_store().switch_mode(mode)

    def get_current_mode(self) -> EditingMode:
        """Get the current editing mode.

        Returns:
            Current editing mode.
        """
        return self._require_mode_state_store().current_mode

    def _connect_context_bar_signals(self, context_bar: ModeContextBar | None) -> None:
        """Connect to mode context bar signals.

        Args:
            context_bar: Mode context bar widget
        """
        self._toolbar_controller.bind_context_bar(context_bar)

    def _trigger_shell_action(self, action_id: ShellActionId) -> None:
        """Execute a toolbar command through the shared shell action system."""
        self._toolbar_controller.trigger_shell_action(action_id)

    def _on_mode_changed(self, mode: EditingMode) -> None:
        """Handle mode change events.

        Args:
            mode: New editing mode
        """
        self._activate_mode_lifecycle(mode, reason="mode-changed")

        # Update action states through action factory
        action_factory = self._action_factory()
        if action_factory is not None:
            action_factory.update_mode_actions(mode)

        if mode != EditingMode.IDENTIFY:
            self._hide_velocity_plot()

        # Update UI for mode
        self._update_ui_for_mode(mode)

        # Notify spectrum plot host of mode change
        view_stack = self._view_stack()
        if view_stack is not None:
            self._interaction_mode_coordinator.apply_policy(spectrum_interaction_mode_policy(mode))

        # Update status and mode label
        self._update_mode_display(mode)

        # Emit signals
        self.mode_changed.emit(mode)

        if mode == EditingMode.START:
            self.status_message.emit(self.tr("Start mode ready"))
        else:
            mode_name = self._status_mode_label(mode)
            self.status_message.emit(self.tr("Switched to {mode} mode").format(mode=mode_name))
        logger.info("Mode changed to: %s", mode.value)

        if action_factory is not None:
            action_factory.set_mode_actions_enabled(self._current_project() is not None)

    def _set_lifecycle_project(self, project: SpectroscopyProject | None) -> None:
        """Propagate the active project to mode lifecycle objects."""
        self._lifecycle_router.set_project(project)

    def _activate_mode_lifecycle(self, mode: EditingMode, *, reason: str) -> None:
        """Activate the lifecycle controller for the current editing mode."""
        self._lifecycle_router.sync_mode(mode, reason=reason)

    def _update_ui_for_mode(self, mode: EditingMode) -> None:
        """Update UI elements based on current mode."""
        dock_coordinator = self._dock_coordinator()
        data_control_panel = self._data_control_panel()
        view_stack = self._view_stack()
        spectrum_view = view_stack.spectrum_view if view_stack is not None else None

        if mode == EditingMode.START:
            self._apply_start_mode_ui(dock_coordinator, data_control_panel, spectrum_view)
            return

        self._apply_active_mode_ui(mode, dock_coordinator, data_control_panel, spectrum_view)

    def _update_mode_display(self, mode: EditingMode) -> None:
        """Update mode label with color coding."""
        context_bar = self._mode_context_bar()
        if isinstance(context_bar, ModeContextBar):
            config = self._context_config_for_mode(mode)
            self._toolbar_controller.apply_mode(
                mode=mode, config=config, current_project=self._current_project()
            )

        controller = self._status_controller()
        if isinstance(controller, StatusBarController):
            controller.update_mode(self._status_mode_label(mode))
            controller.set_coordinates_visible(mode != EditingMode.START)

    def _context_config_for_mode(self, mode: EditingMode) -> ModeContextConfig | None:
        if mode == EditingMode.START:
            title = self._context_text("start.title")
            subtitle = self._context_text("start.subtitle")
            return ModeContextBar.start_mode(title, subtitle)

        return self._context_config_non_start(mode)

    def _context_config_non_start(self, mode: EditingMode) -> ModeContextConfig | None:
        # Existing logic moved into helper to keep _context_config_for_mode readable

        if mode == EditingMode.ANALYSIS:
            title = self._context_text("analysis.title")
            subtitle = self._context_text("analysis.subtitle")
            return ModeContextBar.analysis_mode(title, subtitle)

        if mode == EditingMode.IDENTIFY:
            title = self._context_text("identify.title")
            subtitle = self._context_text("identify.subtitle_default")
            return ModeContextBar.identify_mode(title, subtitle)

        if mode == EditingMode.CONTINUUM:
            title = self._context_text("continuum.title")
            subtitle = self._context_text("continuum.subtitle")
            return ModeContextBar.continuum_mode(title, subtitle)

        return None

    def _context_text(self, context_id: str) -> str:
        if context_id == "start.title":
            return self.tr("Start", "context bar title")

        source = _CONTEXT_TEXT_SOURCES.get(context_id)
        if source is not None:
            return self.tr(source.text, source.disambiguation)

        msg = f"Unknown context bar translation token: {context_id}"
        raise KeyError(msg)

    def retranslate_context_bar(self) -> None:
        """Reapply context bar configuration using the current language."""
        current_mode = self._require_mode_state_store().current_mode
        self._toolbar_controller.apply_mode(
            mode=current_mode,
            config=self._context_config_for_mode(current_mode),
            current_project=self._current_project(),
        )

    def _apply_start_mode_ui(
        self,
        dock_coordinator: DockLayoutCoordinator | None,
        data_control_panel: QWidget | None,
        spectrum_view: SpectrumView | None,
    ) -> None:
        if dock_coordinator:
            dock_coordinator.set_panel_active(False)
            dock_coordinator.activate_mode(None)
        if isinstance(data_control_panel, QWidget):
            data_control_panel.setVisible(False)
        if spectrum_view:
            spectrum_view.set_start_mode_active(True)

    def _apply_active_mode_ui(
        self,
        mode: EditingMode,
        dock_coordinator: DockLayoutCoordinator | None,
        data_control_panel: QWidget | None,
        spectrum_view: SpectrumView | None,
    ) -> None:
        if dock_coordinator:
            dock_coordinator.set_panel_active(True)
            dock_coordinator.activate_mode(mode)
        if isinstance(data_control_panel, QWidget):
            data_control_panel.setVisible(True)
        if spectrum_view:
            spectrum_view.set_start_mode_active(False)

        range_dock = self._range_dock()
        if range_dock:
            range_dock.setVisible(False)
            logger.debug("Range dock permanently disabled (mode: %s)", mode)

    def _status_mode_label(self, mode: EditingMode) -> str:
        if mode == EditingMode.START:
            return self.tr("Start", "mode name")
        if mode == EditingMode.ANALYSIS:
            return self.tr("Analysis")
        if mode == EditingMode.IDENTIFY:
            return self.tr("Identify")
        if mode == EditingMode.CONTINUUM:
            return self.tr("Continuum")

        return self.tr("Analysis")

    @staticmethod
    def _line_wavelength_bounds(line: AbsorptionLine | None) -> tuple[float, float] | None:
        """Compatibility shim for region-focus wavelength bounds."""
        return SpectrumRegionFocusController._line_wavelength_bounds(line)

    @staticmethod
    def _compute_flux_range(
        project: SpectroscopyProject, min_wave: float, max_wave: float
    ) -> tuple[float, float] | None:
        """Compatibility shim for region-focus flux range calculation."""
        return SpectrumRegionFocusController._compute_flux_range(project, min_wave, max_wave)

    def refresh_line_overlays_for_mode(self, mode: EditingMode) -> None:
        """Refresh line overlays for a mode.

        Args:
            mode: Mode whose line overlays should be refreshed.
        """
        self._lifecycle_router.refresh_line_overlays(mode)
