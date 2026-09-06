"""Menu action factory for main window."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP, QObject, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QMessageBox

from chappy.gui.shell.actions import (
    ACTION_SOURCES,
    DEFAULT_ACTION_REGISTRY,
    ActionStateController,
    ActionTextSource,
    MenuBarBuilder,
    MenuTextSource,
)
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.shortcuts import format_runtime_shortcuts, get_shortcut_key

logger = logging.getLogger(__name__)

NOT_IMPLEMENTED_TITLE_SOURCE = str(QT_TRANSLATE_NOOP("MenuActionFactory", "Not Implemented"))
NOT_IMPLEMENTED_BODY_SOURCES: dict[ShellActionId, str] = {
    ShellActionId.UNDO: str(
        QT_TRANSLATE_NOOP("MenuActionFactory", "Undo is currently under development.")
    ),
    ShellActionId.REDO: str(
        QT_TRANSLATE_NOOP("MenuActionFactory", "Redo is currently under development.")
    ),
    ShellActionId.COPY: str(
        QT_TRANSLATE_NOOP("MenuActionFactory", "Copy is currently under development.")
    ),
    ShellActionId.PASTE: str(
        QT_TRANSLATE_NOOP("MenuActionFactory", "Paste is currently under development.")
    ),
}
ABOUT_BODY_SOURCE = str(
    QT_TRANSLATE_NOOP(
        "MenuActionFactory",
        "chappy - Code for Handling Absorption Profiles with PYthon\n\n"
        "Astrophysical absorption line analysis workstation",
    )
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.core.editing_mode import EditingMode
    from chappy.core.history import HistoryState
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.history.bridge import HistoryBridge
    from chappy.gui.shell.actions.dispatcher import ActionDispatcher
    from chappy.gui.spectrum.policy import SpectrumPolicy
    from chappy.i18n.language_switcher import LanguageSwitcher


class MenuActionFactory(QObject):
    """Manages creation and organization of menu actions and shortcuts.

    This class is responsible for creating all application actions,
    managing their state, and providing a clean interface for menu
    and toolbar integration.
    """

    def __init__(self, main_window: QMainWindow, dispatcher: ActionDispatcher) -> None:
        """Initialize action factory.

        Args:
            main_window: Parent main window instance.
            dispatcher: Typed action dispatcher used by all created actions.
        """
        super().__init__()
        self.main_window = main_window
        self._dispatcher = dispatcher
        self.actions: dict[ShellActionId, QAction] = {}
        self.menus: dict[str, QMenu] = {}
        self.mode_action_group: QActionGroup | None = None
        self._action_sources: dict[ShellActionId, ActionTextSource] = {}
        self._menu_sources: dict[str, MenuTextSource] = {}
        self._state_controller = ActionStateController(self.actions)

    def create_all_actions(self) -> None:
        """Create all application actions."""
        self._create_file_actions()
        self._create_edit_actions()  # New edit actions for menu
        self._create_view_actions()
        self._create_model_actions()
        self._create_mode_actions()
        self._create_tools_actions()
        self._create_help_actions()

    def set_history_bridge(self, bridge: HistoryBridge) -> None:
        """Set the history bridge and connect undo/redo actions.

        Args:
            bridge: The history bridge instance.
        """
        self._dispatcher.set_history_bridge(bridge)

        # Subscribe to state changes
        bridge.state_changed.connect(self._on_history_state_changed)

        # Initialize state
        self._state_controller.sync_history_state(bridge.get_state())

    def _on_history_state_changed(self, state: HistoryState) -> None:
        """Handle history state changes to update action enable states.

        Args:
            state: New history state.
        """
        self._state_controller.sync_history_state(state)

    def _register_action_source(self, name: ShellActionId, source: ActionTextSource) -> None:
        """Register source text for a created action.

        Args:
            name: Action registry name.
            source: English source text for the action.
        """
        self._action_sources[name] = source

    def _register_menu_source(self, name: str, source: MenuTextSource) -> None:
        """Register source text for a created menu.

        Args:
            name: Menu registry name.
            source: English source text for the menu.
        """
        self._menu_sources[name] = source

    def _build_action(self, source: ActionTextSource) -> QAction:
        """Build a QAction from Qt-translatable source text.

        Args:
            source: English source text for the action.

        Returns:
            Created action using the current Qt translator.
        """
        action = QAction(self.tr(source.text), self.main_window)
        if source.status_tip is not None:
            action.setStatusTip(format_runtime_shortcuts(self.tr(source.status_tip)))
        return action

    def _translate_source(self, source_text: str) -> str:
        """Translate a static source string in the factory context."""
        return self.tr(source_text)

    def _show_not_implemented(self, body_source: str) -> None:
        """Display a placeholder dialog for not-yet-implemented actions."""
        QMessageBox.information(
            self.main_window, self.tr(NOT_IMPLEMENTED_TITLE_SOURCE), self.tr(body_source)
        )

    def _apply_shortcut(self, action: QAction, action_key: ShellActionId) -> None:
        """Apply shortcut from centralized definition and tag for documentation."""
        shortcut_key = get_shortcut_key(action_key)
        if shortcut_key is not None:
            if isinstance(shortcut_key, QKeySequence.StandardKey):
                action.setShortcut(shortcut_key)
            else:
                action.setShortcut(shortcut_key)
        action.setProperty("shortcut.key", str(action_key))

    @dataclass(slots=True)
    class _ActionBuildOptions:
        """Configuration for one registered action build."""

        enabled: bool = True
        checkable: bool = False
        checked: bool = False
        visible: bool = True
        shortcut_visible_in_context_menu: bool = False
        include_in_shortcuts_doc: bool = False
        shortcut_applier: Callable[[QAction], None] | None = None
        trigger_handler: Callable[[], None] | None = None
        action_group: QActionGroup | None = None

    def _create_registered_action(
        self, action_id: ShellActionId, *, options: _ActionBuildOptions | None = None
    ) -> QAction:
        """Create and register one action from the shared action registry."""
        spec = ACTION_SOURCES[action_id]
        action = self._build_action(spec)
        resolved = options or self._ActionBuildOptions()
        if resolved.shortcut_applier is None:
            self._apply_shortcut(action, action_id)
        else:
            resolved.shortcut_applier(action)
        action.setEnabled(resolved.enabled)
        action.setCheckable(resolved.checkable)
        if resolved.checkable:
            action.setChecked(resolved.checked)
        action.setVisible(resolved.visible)
        action.setShortcutVisibleInContextMenu(resolved.shortcut_visible_in_context_menu)
        if resolved.include_in_shortcuts_doc:
            action.setProperty("doc.includeInShortcuts", True)
        if resolved.action_group is not None:
            resolved.action_group.addAction(action)

        handler = resolved.trigger_handler or (lambda: self._dispatcher.dispatch(action_id))
        action.triggered.connect(handler)
        self.actions[action_id] = action
        self._register_action_source(action_id, spec)
        return action

    def _create_file_actions(self) -> None:
        """Create file-related actions."""
        self._create_registered_action(ShellActionId.OPEN_OBSERVATION_DATA)
        self._create_registered_action(ShellActionId.OPEN_PROJECT)
        self._create_registered_action(
            ShellActionId.SAVE_PROJECT, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(
            ShellActionId.SAVE_PROJECT_AS, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(
            ShellActionId.CLOSE_PROJECT, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(ShellActionId.QUIT)

    def _create_edit_actions(self) -> None:
        """Create edit-related actions."""
        self._create_registered_action(
            ShellActionId.UNDO, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(
            ShellActionId.REDO, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(
            ShellActionId.COPY,
            options=self._ActionBuildOptions(
                enabled=False,
                trigger_handler=lambda: self._show_not_implemented(
                    NOT_IMPLEMENTED_BODY_SOURCES[ShellActionId.COPY]
                ),
            ),
        )
        self._create_registered_action(
            ShellActionId.PASTE,
            options=self._ActionBuildOptions(
                enabled=False,
                trigger_handler=lambda: self._show_not_implemented(
                    NOT_IMPLEMENTED_BODY_SOURCES[ShellActionId.PASTE]
                ),
            ),
        )
        self._create_registered_action(
            ShellActionId.DELETE, options=self._ActionBuildOptions(enabled=False)
        )

    def _create_view_actions(self) -> None:
        """Create view-related actions."""
        self._create_registered_action(
            ShellActionId.ZOOM_IN,
            options=self._ActionBuildOptions(
                enabled=False,
                shortcut_applier=lambda action: self._assign_zoom_shortcuts(action, zoom_in=True),
            ),
        )
        self.actions[ShellActionId.ZOOM_IN].setProperty("shortcut.key", str(ShellActionId.ZOOM_IN))

        self._create_registered_action(
            ShellActionId.ZOOM_OUT,
            options=self._ActionBuildOptions(
                enabled=False,
                shortcut_applier=lambda action: self._assign_zoom_shortcuts(action, zoom_in=False),
            ),
        )
        self.actions[ShellActionId.ZOOM_OUT].setProperty(
            "shortcut.key", str(ShellActionId.ZOOM_OUT)
        )

        self._create_registered_action(
            ShellActionId.RESET_VIEW, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(
            ShellActionId.AUTO_ADJUST_FLUX, options=self._ActionBuildOptions(enabled=False)
        )
        identify_velocity_action = self._create_registered_action(
            ShellActionId.TOGGLE_VELOCITY_PLOT_IDENTIFY,
            options=self._ActionBuildOptions(
                enabled=False, visible=False, include_in_shortcuts_doc=True
            ),
        )
        # Identify's velocity toggle has no menu entry, so the window must own its V shortcut.
        self.main_window.addAction(identify_velocity_action)
        self._create_registered_action(
            ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS,
            options=self._ActionBuildOptions(
                enabled=False,
                checkable=True,
                checked=False,
                visible=False,
                include_in_shortcuts_doc=True,
            ),
        )

    def _assign_zoom_shortcuts(self, action: QAction, *, zoom_in: bool) -> None:
        """Assign consistent zoom shortcuts (Cmd on macOS, Ctrl elsewhere).

        Note: Qt.ControlModifier automatically maps to Command (⌘) on macOS and
        Ctrl on other platforms, so no platform-specific branching is needed.
        """
        action.setShortcuts(self._zoom_shortcut_sequences(zoom_in))

    @staticmethod
    def _zoom_shortcut_sequences(zoom_in: bool) -> tuple[QKeySequence, ...]:
        """Build QKeySequence tuples for zoom actions.

        We use explicit modifier+key construction instead of StandardKey.ZoomIn/ZoomOut
        because StandardKey allows modifier-less shortcuts (e.g., bare +/- keys),
        which conflicts with our requirement to only zoom when the primary modifier
        is held (Cmd on macOS, Ctrl elsewhere).

        Qt automatically displays and handles the shortcuts correctly on each platform:
        - macOS: Menu shows "⌘+" and responds to Command key
        - Others: Menu shows "Ctrl+" and responds to Ctrl key

        Reference: https://doc.qt.io/qt-6/qt.html#KeyboardModifier-enum
        """
        modifier = Qt.KeyboardModifier.ControlModifier
        keys = (Qt.Key.Key_Plus, Qt.Key.Key_Equal) if zoom_in else (Qt.Key.Key_Minus,)
        return tuple(QKeySequence(modifier.value | key.value) for key in keys)

    def _create_model_actions(self) -> None:
        """Create model-related actions."""
        self._create_registered_action(
            ShellActionId.FIT_MODEL, options=self._ActionBuildOptions(enabled=False)
        )
        self._create_registered_action(
            ShellActionId.ANALYSIS_BACK,
            options=self._ActionBuildOptions(enabled=False, visible=False),
        )

    def _create_mode_actions(self) -> None:
        """Create mode switching actions."""
        if self.mode_action_group is None:
            self.mode_action_group = QActionGroup(self.main_window)
            self.mode_action_group.setExclusive(True)

        for action_id in (
            ShellActionId.IDENTIFY_MODE,
            ShellActionId.ANALYSIS_MODE,
            ShellActionId.CONTINUUM_MODE,
        ):
            self._create_registered_action(
                action_id,
                options=self._ActionBuildOptions(
                    checkable=True, action_group=self.mode_action_group
                ),
            )

    def _create_tools_actions(self) -> None:
        """Create tools-related actions."""
        for action_id in (
            ShellActionId.OPEN_LINE_DATABASE_FOLDER,
            ShellActionId.COSMOLOGY_SETTINGS,
            ShellActionId.RESOLUTION_SETTINGS,
            ShellActionId.LANGUAGE_SETTINGS,
        ):
            self._create_registered_action(
                action_id, options=self._ActionBuildOptions(shortcut_visible_in_context_menu=True)
            )
        self._create_registered_action(ShellActionId.PRESET_MANAGEMENT)

    def _create_help_actions(self) -> None:
        """Create help and about actions."""
        self._create_registered_action(ShellActionId.HELP)
        self._create_registered_action(ShellActionId.TUTORIAL)
        self._create_registered_action(ShellActionId.ABOUT)

    def _show_about_dialog(self) -> None:
        """Display About dialog with dynamically retrieved version."""
        app = QApplication.instance()
        if app is None:
            msg = "QApplication instance is required to show the About dialog"
            raise RuntimeError(msg)

        version = app.applicationVersion()
        body = self.tr(ABOUT_BODY_SOURCE)
        QMessageBox.about(
            self.main_window,
            self.tr(ACTION_SOURCES[ShellActionId.ABOUT].text),
            f"{body}\n\nVersion: {version}",
        )

    def retranslate(self, language_switcher: LanguageSwitcher | None = None) -> None:
        """Update menu titles and actions with the active Qt translator.

        Args:
            language_switcher: Accepted for compatibility with existing main
                window callers. Menu and action labels ignore this value and
                use Qt translators instead.
        """
        del language_switcher

        for menu_name, menu_source in self._menu_sources.items():
            menu = self.menus.get(menu_name)
            if not menu:
                continue
            menu.setTitle(self.tr(menu_source.title))

        for action_name, action_source in self._action_sources.items():
            action = self.actions.get(action_name)
            if not action:
                continue
            action.setText(self.tr(action_source.text))
            if action_source.status_tip is not None:
                action.setStatusTip(format_runtime_shortcuts(self.tr(action_source.status_tip)))

    def register_external_action(
        self, action_id: ShellActionId, action: QAction, *, include_in_shortcuts_doc: bool = False
    ) -> None:
        """Register an action built outside the factory for lookup and docs.

        Args:
            action_id: Identifier the action is registered under.
            action: Action instance owned and translated elsewhere.
            include_in_shortcuts_doc: Whether the manual's shortcut table
                should list this action even though it is not attached to
                one of the factory's own menus.
        """
        if include_in_shortcuts_doc:
            action.setProperty("doc.includeInShortcuts", True)
        self.actions[action_id] = action

    def get_all_actions(self) -> dict[ShellActionId, QAction]:
        """Get all created actions.

        Returns:
            Dictionary of all actions keyed by name
        """
        return self.actions.copy()

    def update_action_states(self, project: SpectroscopyProject | None) -> None:
        """Update action enabled states based on project status.

        Args:
            project: Current project instance or None
        """
        self._state_controller.sync_project_state(project)

    def update_mode_actions(self, current_mode: EditingMode) -> None:
        """Update mode action checked states.

        Args:
            current_mode: Currently active editing mode
        """
        self._state_controller.sync_mode_state(current_mode)

    def update_spectrum_policy(self, policy: SpectrumPolicy) -> None:
        """Synchronize global spectrum action capabilities after policy commit."""
        self._state_controller.sync_spectrum_policy(policy)

    def clear_spectrum_policy(self) -> None:
        """Disable policy-controlled actions after unrecoverable rollback."""
        self._state_controller.clear_spectrum_policy()

    def set_fit_running(self, running: bool) -> None:
        """Update fit busy state without bypassing policy capabilities."""
        self._state_controller.set_fit_running(running)

    def set_mode_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable mode-switching related actions."""
        self._state_controller.set_mode_actions_enabled(enabled)

    def create_menu_bar(self) -> QMenuBar:
        """Create and return a fully configured menu bar.

        Returns:
            Configured QMenuBar with all menus
        """
        menubar, created_menus = MenuBarBuilder(
            main_window=self.main_window,
            menus=DEFAULT_ACTION_REGISTRY.menus,
            actions=self.actions,
            translator=self._translate_source,
        ).build()
        self.menus = created_menus
        for menu_definition in DEFAULT_ACTION_REGISTRY.menus:
            self._register_menu_source(menu_definition.name, menu_definition.source)
        return menubar
