"""Tests for identify coordinator provider boundary validation."""

from __future__ import annotations

import pytest

from chappy.core.atomic_data import AtomicLineData
from chappy.gui.modes.identify.coordinator import IdentifyModeCoordinator
from chappy.gui.modes.identify.shell_ports import IdentifyShellPorts


class _MainWindow:
    """Minimal main-window surface for provider boundary tests."""

    def __init__(self) -> None:
        """Initialize optional provider attributes."""
        self.mode_state_store = None
        self.history_recorder: object | None = None
        self.identify_velocity_runtime = _IdentifyVelocityRuntime()

    @property
    def identify_history_recorder(self) -> object | None:
        """Return configured history recorder."""
        return self.history_recorder

    @property
    def preset_dialog_port(self) -> _MainWindow:
        """Return the preset dialog port used by the coordinator."""
        return self

    def show_preset_list_dialog(self) -> None:
        """No-op preset hook."""


class _IdentifyVelocityRuntime:
    """No-op identify velocity runtime double."""

    def hide_velocity_plot(self) -> None:
        """No-op velocity hook."""

    def refresh_velocity_overlay(self) -> None:
        """No-op velocity hook."""


class _NonQObjectMainWindow:
    """Main-window-shaped object that is not safe as a Qt parent."""


class _Settings:
    """Minimal settings double retaining the user's saved threshold."""

    def value(self, _key: str, default: float) -> float:
        """Return a stable saved threshold."""
        return 73.0 if default == 50.0 else default


class _Panel:
    """Record threshold values presented by the coordinator."""

    def __init__(self) -> None:
        self.values: list[float] = []

    def set_sigma_threshold(self, value: float) -> None:
        self.values.append(value)


def _coordinator_with_main_window(window: _MainWindow) -> IdentifyModeCoordinator:
    """Build a coordinator instance for provider helper tests only."""
    coordinator = IdentifyModeCoordinator.__new__(IdentifyModeCoordinator)
    coordinator._shell_ports = _shell_ports(window)
    return coordinator


def _shell_ports(window: _MainWindow) -> IdentifyShellPorts:
    """Build shell ports around the boundary-test window double."""

    return IdentifyShellPorts(
        current_project_provider=lambda: None,
        spectrum_view_provider=lambda: None,
        mode_state_provider=lambda: window.mode_state_store,
        preset_store_setter=lambda _store: None,
        history_recorder_provider=lambda: window.identify_history_recorder,
        velocity_runtime_provider=lambda: window.identify_velocity_runtime,
        preset_dialog_provider=lambda: window.preset_dialog_port,
        undo_shortcut_provider=lambda: "Ctrl+Z",
    )


def test_non_qobject_main_window_fails_before_qt_parent_abort() -> None:
    """A non-QObject parent should fail in Python before reaching PySide."""
    window = _MainWindow()
    with pytest.raises(TypeError, match="must be a QObject"):
        IdentifyModeCoordinator(
            _NonQObjectMainWindow(),
            shell_ports=_shell_ports(window),
            atomic_data=AtomicLineData(),
            preset_store=None,
        )


def test_invalid_history_recorder_provider_fails_fast() -> None:
    """A non-recorder object should not be accepted through a cast boundary."""
    window = _MainWindow()
    window.history_recorder = object()
    coordinator = _coordinator_with_main_window(window)

    with pytest.raises(TypeError, match="Identify history recorder"):
        coordinator._identify_temporary_line_history_recorder()


def test_invalid_current_mode_provider_fails_fast() -> None:
    """A non-mode-state object should not be accepted through a cast boundary."""
    window = _MainWindow()
    window.mode_state_store = object()
    coordinator = _coordinator_with_main_window(window)

    with pytest.raises(TypeError, match="Identify mode state store"):
        coordinator._current_editing_mode()


def test_tutorial_sigma_override_refreshes_without_writing_saved_settings() -> None:
    """Temporary tutorial detection state restores the persisted user value."""
    coordinator = IdentifyModeCoordinator.__new__(IdentifyModeCoordinator)
    panel = _Panel()
    refreshes: list[None] = []
    coordinator._settings = _Settings()
    coordinator._sigma_settings_key = "identify_panel/sigma_threshold"
    coordinator._tutorial_sigma_threshold = None
    coordinator._panel = panel
    coordinator._refresh_candidates = lambda: refreshes.append(None)

    coordinator.set_tutorial_sigma_threshold(50.0)
    assert coordinator._load_sigma_threshold() == 50.0
    coordinator.set_tutorial_sigma_threshold(None)

    assert coordinator._load_sigma_threshold() == 73.0
    assert panel.values == [50.0, 73.0]
    assert len(refreshes) == 2
