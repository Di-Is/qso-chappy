"""Typed action and menu definitions for the shell."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy.gui.shell.actions.ids import ShellActionId


@dataclass(frozen=True)
class ActionTextSource:
    """English source text for one QAction."""

    text: str
    status_tip: str | None = None


@dataclass(frozen=True)
class MenuTextSource:
    """English source title for one QMenu."""

    title: str


@dataclass(frozen=True)
class ActionDefinition:
    """Static action definition used by shell action construction."""

    action_id: ShellActionId
    source: ActionTextSource


@dataclass(frozen=True)
class MenuDefinition:
    """Static menu definition and its ordered action IDs."""

    name: str
    source: MenuTextSource
    entries: tuple[ShellActionId | None, ...]


class ActionRegistry:
    """Registry of shell action and menu definitions."""

    def __init__(
        self, *, actions: tuple[ActionDefinition, ...], menus: tuple[MenuDefinition, ...]
    ) -> None:
        """Store static action and menu definitions."""
        self._actions = actions
        self._menus = menus
        self.action_sources = {definition.action_id: definition.source for definition in actions}
        self.menu_sources = {definition.name: definition.source for definition in menus}

    @property
    def actions(self) -> tuple[ActionDefinition, ...]:
        """Return the registered action definitions."""
        return self._actions

    @property
    def menus(self) -> tuple[MenuDefinition, ...]:
        """Return the registered menu definitions."""
        return self._menus

    @classmethod
    def default(cls) -> ActionRegistry:
        """Build the default shell action registry."""
        return cls(actions=_DEFAULT_ACTIONS, menus=_DEFAULT_MENUS)


_DEFAULT_ACTIONS = (
    ActionDefinition(
        ShellActionId.OPEN_OBSERVATION_DATA,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Open Observation Data...")),
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Load observed flux and error FITS files")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.OPEN_PROJECT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Open Project...")),
            #: Keep {open_project_shortcut} unchanged; it is replaced for the running OS.
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Open project ({open_project_shortcut})")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.SAVE_PROJECT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Save Project")),
            #: Keep {save_project_shortcut} unchanged; it is replaced for the running OS.
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Save project ({save_project_shortcut})")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.SAVE_PROJECT_AS,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Save Project &As...")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Save project with new name")),
        ),
    ),
    ActionDefinition(
        ShellActionId.CLOSE_PROJECT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Close Project")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Close the current project")),
        ),
    ),
    ActionDefinition(
        ShellActionId.QUIT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Quit")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Exit the application")),
        ),
    ),
    ActionDefinition(
        ShellActionId.UNDO,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Undo")),
            #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Undo last action ({undo_shortcut})")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.REDO,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Redo")),
            #: Keep {redo_shortcut} unchanged; it is replaced for the running OS.
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Redo last undone action ({redo_shortcut})")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.COPY,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Copy")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Copy selection")),
        ),
    ),
    ActionDefinition(
        ShellActionId.PASTE,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Paste")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Paste from clipboard")),
        ),
    ),
    ActionDefinition(
        ShellActionId.DELETE,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Delete")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Delete selection")),
        ),
    ),
    ActionDefinition(
        ShellActionId.ZOOM_IN,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Zoom &In")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Zoom into spectrum")),
        ),
    ),
    ActionDefinition(
        ShellActionId.ZOOM_OUT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Zoom &Out")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Zoom out of spectrum")),
        ),
    ),
    ActionDefinition(
        ShellActionId.RESET_VIEW,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Reset View")),
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Reset spectrum ranges to defaults")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.AUTO_ADJUST_FLUX,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Auto Adjust Flux")),
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Auto-adjust flux axis to fit data")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.TOGGLE_VELOCITY_PLOT_IDENTIFY,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Show Spectrum in Velocity Space"))
        ),
    ),
    ActionDefinition(
        ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Show Spectrum in Velocity Space"))
        ),
    ),
    ActionDefinition(
        ShellActionId.FIT_MODEL,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Fit Model")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Fit model to observed data")),
        ),
    ),
    ActionDefinition(
        ShellActionId.IDENTIFY_MODE,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Identify Mode")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Identify mode")),
        ),
    ),
    ActionDefinition(
        ShellActionId.ANALYSIS_MODE,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Analysis Mode")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Analysis workspace")),
        ),
    ),
    ActionDefinition(
        ShellActionId.ANALYSIS_BACK,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Back to Analysis Overview")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Return to Analysis Overview")),
        ),
    ),
    ActionDefinition(
        ShellActionId.CONTINUUM_MODE,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Continuum Mode")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Continuum editing mode")),
        ),
    ),
    ActionDefinition(
        ShellActionId.OPEN_LINE_DATABASE_FOLDER,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Open Line &Database Folder")),
            status_tip=str(
                QT_TRANSLATE_NOOP(
                    "MenuActionFactory", "Open the folder holding the spectral line CSV"
                )
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.COSMOLOGY_SETTINGS,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Cosmology...")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Adjust cosmology parameters")),
        ),
    ),
    ActionDefinition(
        ShellActionId.RESOLUTION_SETTINGS,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Resolution...")),
            status_tip=str(
                QT_TRANSLATE_NOOP("MenuActionFactory", "Configure spectral resolution settings")
            ),
        ),
    ),
    ActionDefinition(
        ShellActionId.LANGUAGE_SETTINGS,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Language...")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Change display language")),
        ),
    ),
    ActionDefinition(
        ShellActionId.PRESET_MANAGEMENT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Preset Management...")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Manage preset configurations")),
        ),
    ),
    ActionDefinition(
        ShellActionId.HELP,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&User Guide")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Open user guide (F1)")),
        ),
    ),
    ActionDefinition(
        ShellActionId.TUTORIAL,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Tutorial")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "Start guided tutorial")),
        ),
    ),
    ActionDefinition(
        ShellActionId.ABOUT,
        ActionTextSource(
            text=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&About chappy")),
            status_tip=str(QT_TRANSLATE_NOOP("MenuActionFactory", "About this application")),
        ),
    ),
)

_DEFAULT_MENUS = (
    MenuDefinition(
        "file",
        MenuTextSource(title=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&File"))),
        (
            ShellActionId.OPEN_OBSERVATION_DATA,
            ShellActionId.OPEN_PROJECT,
            None,
            ShellActionId.SAVE_PROJECT,
            ShellActionId.SAVE_PROJECT_AS,
            ShellActionId.CLOSE_PROJECT,
            None,
            ShellActionId.QUIT,
        ),
    ),
    MenuDefinition(
        "edit",
        MenuTextSource(title=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Edit"))),
        (
            ShellActionId.UNDO,
            ShellActionId.REDO,
            None,
            ShellActionId.COPY,
            ShellActionId.PASTE,
            ShellActionId.DELETE,
        ),
    ),
    MenuDefinition(
        "view",
        MenuTextSource(title=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&View"))),
        (
            ShellActionId.ZOOM_IN,
            ShellActionId.ZOOM_OUT,
            None,
            ShellActionId.RESET_VIEW,
            ShellActionId.AUTO_ADJUST_FLUX,
            None,
            ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS,
        ),
    ),
    MenuDefinition(
        "mode",
        MenuTextSource(title=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Mode"))),
        (ShellActionId.IDENTIFY_MODE, ShellActionId.ANALYSIS_MODE, ShellActionId.CONTINUUM_MODE),
    ),
    MenuDefinition(
        "settings",
        MenuTextSource(title=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Settings"))),
        (
            ShellActionId.OPEN_LINE_DATABASE_FOLDER,
            ShellActionId.RESOLUTION_SETTINGS,
            ShellActionId.COSMOLOGY_SETTINGS,
            ShellActionId.LANGUAGE_SETTINGS,
            ShellActionId.PRESET_MANAGEMENT,
        ),
    ),
    MenuDefinition(
        "help",
        MenuTextSource(title=str(QT_TRANSLATE_NOOP("MenuActionFactory", "&Help"))),
        (ShellActionId.HELP, ShellActionId.TUTORIAL, None, ShellActionId.ABOUT),
    ),
)

DEFAULT_ACTION_REGISTRY = ActionRegistry.default()
ACTION_SOURCES: dict[ShellActionId, ActionTextSource] = DEFAULT_ACTION_REGISTRY.action_sources
MENU_SOURCES: dict[str, MenuTextSource] = DEFAULT_ACTION_REGISTRY.menu_sources
