"""Shell adapter for identify mode ports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.gui.modes.identify.shell_ports import IdentifyShellPorts
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.shortcuts import get_runtime_shortcut_display

if TYPE_CHECKING:
    from chappy.gui.modes.identify.shell_ports import IdentifySpectrumView
    from chappy.gui.shell.main_window import MainWindow


def build_identify_shell_ports(main_window: MainWindow) -> IdentifyShellPorts:
    """Build operation-specific shell ports for identify mode."""

    def spectrum_view() -> IdentifySpectrumView | None:
        view_stack = main_window.view_stack
        if view_stack is None:
            return None
        return view_stack.spectrum_view

    return IdentifyShellPorts(
        current_project_provider=lambda: main_window.current_project,
        spectrum_view_provider=spectrum_view,
        mode_state_provider=lambda: main_window.mode_state_store,
        preset_store_setter=lambda store: setattr(main_window, "preset_store", store),
        history_recorder_provider=lambda: main_window.identify_history_recorder,
        velocity_runtime_provider=lambda: main_window.identify_velocity_runtime,
        preset_dialog_provider=lambda: main_window.preset_dialog_port,
        undo_shortcut_provider=lambda: get_runtime_shortcut_display(ShellActionId.UNDO),
    )
