"""Tests for history GUI refresh adapter boundaries."""

from __future__ import annotations

import pytest

from chappy.core.editing_mode import EditingMode
from chappy.gui.history.refresh_adapter import HistoryRefreshAdapter


class _ModeShell:
    """Mode shell fake returning a configured mode."""

    def __init__(self, mode: EditingMode | None) -> None:
        """Initialize mode state."""
        self.mode = mode
        self.refreshed_modes: list[EditingMode] = []

    def get_current_mode(self) -> EditingMode | None:
        """Return the configured current mode."""
        return self.mode

    def refresh_line_overlays_for_mode(self, mode: EditingMode) -> None:
        """Record overlay refreshes."""
        self.refreshed_modes.append(mode)


class _MainWindow:
    """Main-window refresh surface fake."""

    def __init__(self, mode: EditingMode | None = None) -> None:
        """Initialize refresh surface state."""
        self.identify_coordinator = None
        self.mode_shell_coordinator = _ModeShell(mode)


class _Model:
    """Refreshable model fake."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.invalidations = 0
        self.updates = 0

    def invalidate_model(self) -> None:
        """Record invalidation."""
        self.invalidations += 1

    def update_model(self) -> None:
        """Record update."""
        self.updates += 1


class _Project:
    """Project fake with a model."""

    def __init__(self) -> None:
        """Initialize model."""
        self.model = _Model()


class _DockLayout:
    """Dock layout refresh surface fake."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.structure_refreshes = 0
        self.optimize_refreshes: list[str | None] = []
        self.invalidated_groups: list[str | None] = []
        self.optimize_velocity_plot_refreshes = 0
        self.optimize_wavelength_refreshes: list[str] = []

    def refresh_structure_panel(self) -> None:
        """Record structure panel refresh."""
        self.structure_refreshes += 1

    def refresh_optimize_panel_for_history(self, region_id: str | None) -> None:
        """Record optimize panel refresh."""
        self.optimize_refreshes.append(region_id)

    def invalidate_optimize_group_analysis(self, region_id: str | None) -> None:
        """Record optimize analysis invalidation."""
        self.invalidated_groups.append(region_id)

    def refresh_visible_optimize_velocity_plot(self) -> None:
        """Record an Optimize velocity plot refresh."""
        self.optimize_velocity_plot_refreshes += 1

    def refresh_optimize_wavelength_model_residual(self, region_id: str) -> bool:
        """Record a selected-region wavelength curve refresh."""
        self.optimize_wavelength_refreshes.append(region_id)
        return True


def test_refresh_model_without_project_remains_noop() -> None:
    """No project is still a recoverable no-refresh state."""
    adapter = HistoryRefreshAdapter(_MainWindow())

    adapter.refresh_model(None, None)


def test_refresh_model_requires_dock_layout_when_project_exists() -> None:
    """Model refresh with an active project requires the dock layout refresh port."""
    adapter = HistoryRefreshAdapter(_MainWindow())

    with pytest.raises(RuntimeError, match="dock layout refresh port"):
        adapter.refresh_model(_Project(), None)


def test_refresh_velocity_window_requires_dock_for_structure_mode() -> None:
    """Structure velocity-window refresh requires the dock layout refresh port."""
    adapter = HistoryRefreshAdapter(_MainWindow(EditingMode.ANALYSIS))

    with pytest.raises(RuntimeError, match="dock layout refresh port"):
        adapter.refresh_velocity_window(None, "region-1")


def test_refresh_optimize_velocity_plot_is_read_only() -> None:
    """Plot refresh must not own scientific analysis invalidation."""
    main_window = _MainWindow(EditingMode.ANALYSIS)
    adapter = HistoryRefreshAdapter(main_window)
    dock = _DockLayout()

    adapter.refresh_optimize_velocity_plot(dock)

    assert dock.invalidated_groups == []
    assert dock.optimize_velocity_plot_refreshes == 1


def test_refresh_optimize_wavelength_plot_does_not_touch_model() -> None:
    """Scientific window history should delegate display slicing without model updates."""
    adapter = HistoryRefreshAdapter(_MainWindow(EditingMode.ANALYSIS))
    dock = _DockLayout()
    project = _Project()

    assert adapter.refresh_optimize_wavelength_model_residual(dock, "region-1") is True

    assert dock.optimize_wavelength_refreshes == ["region-1"]
    assert project.model.invalidations == 0
    assert project.model.updates == 0
