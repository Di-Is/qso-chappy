"""GUI refresh adapter for history command application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from chappy.application.history import HistoryRefreshTarget
from chappy.core.components.continuum import ContinuumComponent
from chappy.core.editing_mode import EditingMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.application.history import ChangeSet
    from chappy.core.spectroscopy_project import SpectroscopyProject


class SpectrumRangeUpdatePort(Protocol):
    """Spectrum range-apply surface needed by history range replay."""

    def coordinate_range_update(
        self,
        source: str,
        min_wave: float,
        max_wave: float,
        *,
        flux_range: tuple[float, float] | None = None,
        record_history: bool = True,
    ) -> None:
        """Apply a wavelength/flux range change originating from ``source``."""


class _ContinuumUpdatedSignal(Protocol):
    """Qt signal-instance surface used to notify continuum refresh."""

    def emit(self, continuum: ContinuumComponent) -> None:
        """Emit the updated continuum component."""


class ContinuumHistoryRefreshPort(Protocol):
    """Continuum editor surface needed by history refresh."""

    @property
    def current_project(self) -> SpectroscopyProject | None:
        """Return the continuum editor's current project."""

    @property
    def current_continuum(self) -> ContinuumComponent | None:
        """Return the continuum editor's current continuum component."""

    @property
    def continuum_updated(self) -> _ContinuumUpdatedSignal:
        """Return the Qt signal emitted after a continuum refresh."""


class _IdentifyModeCoordinatorPort(Protocol):
    """Identify coordinator refresh surface."""

    def refresh(self) -> None:
        """Refresh identify UI."""


class _ModeShellCoordinatorPort(Protocol):
    """Mode coordinator refresh surface."""

    def get_current_mode(self) -> EditingMode | None:
        """Return the current mode."""

    def refresh_line_overlays_for_mode(self, mode: EditingMode) -> None:
        """Refresh line overlays for a mode.

        Args:
            mode: Active mode.
        """


class DockLayoutRefreshPort(Protocol):
    """Dock layout refresh surface needed by history operations."""

    def refresh_structure_panel(self) -> None:
        """Refresh the structure panel."""

    def refresh_optimize_panel_for_history(self, region_id: str | None) -> None:
        """Refresh optimize UI after a history operation.

        Args:
            region_id: Optional region ID for targeted refresh.
        """

    def refresh_visible_optimize_velocity_plot(self) -> None:
        """Refresh the visible Optimize velocity plot from current project state."""

    def refresh_optimize_wavelength_model_residual(self, region_id: str) -> bool:
        """Refresh selected-region wavelength curves from existing model data."""


@runtime_checkable
class HistoryMainWindowPort(Protocol):
    """Main-window surface needed by history refresh adapter."""

    identify_coordinator: _IdentifyModeCoordinatorPort | None
    mode_shell_coordinator: _ModeShellCoordinatorPort | None


class HistoryRefreshAdapter:
    """Apply GUI refresh targets after history operations."""

    def __init__(self, main_window: HistoryMainWindowPort) -> None:
        """Initialize the adapter.

        Args:
            main_window: Main-window refresh surface.
        """
        self._main_window = main_window

    def refresh_continuum(
        self, continuum_editor: ContinuumHistoryRefreshPort | None, continuum: ContinuumComponent
    ) -> None:
        """Refresh continuum UI after a history operation.

        Args:
            continuum_editor: Continuum editor to refresh.
            continuum: Modified continuum component.
        """
        if continuum_editor is None:
            return

        project = continuum_editor.current_project
        if project:
            project.model.update_model()
        continuum_editor.continuum_updated.emit(continuum)

    def refresh_identify(self) -> None:
        """Refresh identify coordinator via the main window."""
        identify_coordinator = self._main_window.identify_coordinator
        if identify_coordinator is not None:
            identify_coordinator.refresh()

    def refresh_model(
        self,
        project: SpectroscopyProject | None,
        dock_layout_coordinator: DockLayoutRefreshPort | None,
        region_id: str | None = None,
    ) -> None:
        """Refresh model-dependent UI after undo/redo.

        Args:
            project: Current project.
            dock_layout_coordinator: Dock layout coordinator containing optimize UI.
            region_id: Optional region ID for targeted refresh.
        """
        if project is None or project.model is None:
            return

        project.model.invalidate_model()
        project.model.update_model()

        dock_layout_coordinator = self._required_dock_layout(dock_layout_coordinator)
        dock_layout_coordinator.refresh_optimize_panel_for_history(region_id)

    def refresh_optimize_panel(
        self, dock_layout_coordinator: DockLayoutRefreshPort | None, region_id: str | None
    ) -> None:
        """Refresh Optimize panel state without touching the scientific model."""
        dock = self._required_dock_layout(dock_layout_coordinator)
        dock.refresh_optimize_panel_for_history(region_id)

    def refresh_velocity_window(
        self, dock_layout_coordinator: DockLayoutRefreshPort | None, region_id: str | None
    ) -> None:
        """Refresh velocity-window related UI after history operations.

        Args:
            dock_layout_coordinator: Dock layout coordinator containing mode panels.
            region_id: Affected region ID.
        """
        _ = region_id
        main_window = self._main_window
        current_mode = self._current_mode(main_window)

        if current_mode == EditingMode.ANALYSIS:
            dock_layout_coordinator = self._required_dock_layout(dock_layout_coordinator)
            dock_layout_coordinator.refresh_structure_panel()

        if current_mode is not None:
            mode_shell_coordinator = main_window.mode_shell_coordinator
            if mode_shell_coordinator is not None:
                mode_shell_coordinator.refresh_line_overlays_for_mode(current_mode)

    def refresh_optimize_velocity_plot(
        self, dock_layout_coordinator: DockLayoutRefreshPort | None
    ) -> None:
        """Refresh the plot from already-committed scientific state."""
        dock = self._required_dock_layout(dock_layout_coordinator)
        dock.refresh_visible_optimize_velocity_plot()

    def refresh_optimize_wavelength_model_residual(
        self, dock_layout_coordinator: DockLayoutRefreshPort | None, region_id: str | None
    ) -> bool:
        """Refresh selected wavelength curves without model invalidation or update."""
        if region_id is None:
            return False
        dock = self._required_dock_layout(dock_layout_coordinator)
        return dock.refresh_optimize_wavelength_model_residual(region_id)

    @staticmethod
    def _required_dock_layout(
        dock_layout_coordinator: DockLayoutRefreshPort | None,
    ) -> DockLayoutRefreshPort:
        """Return the required dock layout refresh port."""
        if dock_layout_coordinator is None:
            msg = "History refresh requires a dock layout refresh port."
            raise RuntimeError(msg)
        return dock_layout_coordinator

    def _current_mode(self, main_window: HistoryMainWindowPort | None) -> EditingMode | None:
        """Return the current mode from the main window.

        Args:
            main_window: Main window object.

        Returns:
            Current editing mode, if available.
        """
        if main_window is None:
            return None
        mode_shell_coordinator = main_window.mode_shell_coordinator
        if mode_shell_coordinator is None:
            return None
        return mode_shell_coordinator.get_current_mode()


class HistoryBridgeRefreshPort:
    """Implement ``HistoryRefreshPort`` by dispatching to ``HistoryRefreshAdapter``."""

    def __init__(
        self,
        adapter: HistoryRefreshAdapter,
        project_provider: Callable[[], SpectroscopyProject | None],
        continuum_editor_provider: Callable[[], ContinuumHistoryRefreshPort | None],
        dock_layout_coordinator_provider: Callable[[], DockLayoutRefreshPort | None],
    ) -> None:
        """Initialize with the refresh adapter and GUI-owned state providers."""
        self._adapter = adapter
        self._project_provider = project_provider
        self._continuum_editor_provider = continuum_editor_provider
        self._dock_layout_coordinator_provider = dock_layout_coordinator_provider

    def refresh(self, target: HistoryRefreshTarget, change_set: ChangeSet) -> None:
        """Refresh the GUI surface associated with one committed refresh target."""
        dock_layout_coordinator = self._dock_layout_coordinator_provider()
        if target is HistoryRefreshTarget.MODEL:
            region_id = change_set.changed_region_ids[0] if change_set.changed_region_ids else None
            self._adapter.refresh_model(
                self._project_provider(), dock_layout_coordinator, region_id
            )
        elif target is HistoryRefreshTarget.OPTIMIZE_PANEL:
            region_id = change_set.changed_region_ids[0] if change_set.changed_region_ids else None
            self._adapter.refresh_optimize_panel(dock_layout_coordinator, region_id)
        if target is HistoryRefreshTarget.IDENTIFY_PANEL:
            self._adapter.refresh_identify()
        if target is HistoryRefreshTarget.LINE_OVERLAYS:
            region_id = change_set.changed_region_ids[0] if change_set.changed_region_ids else None
            self._adapter.refresh_velocity_window(dock_layout_coordinator, region_id)
        if target is HistoryRefreshTarget.VELOCITY_PLOT:
            self._adapter.refresh_optimize_velocity_plot(dock_layout_coordinator)
        if target is HistoryRefreshTarget.OPTIMIZE_WAVELENGTH_MODEL_RESIDUAL:
            region_id = change_set.changed_region_ids[0] if change_set.changed_region_ids else None
            self._adapter.refresh_optimize_wavelength_model_residual(
                dock_layout_coordinator, region_id
            )
        if target is HistoryRefreshTarget.CONTINUUM_EDITOR:
            continuum = None
            if change_set.changed_continuum_ids:
                continuum = self._find_continuum(change_set.changed_continuum_ids[0])
            continuum_editor = self._continuum_editor_provider()
            if continuum is None and continuum_editor is not None:
                continuum = continuum_editor.current_continuum
            if continuum is not None:
                self._adapter.refresh_continuum(continuum_editor, continuum)

    def _find_continuum(self, continuum_id: str) -> ContinuumComponent | None:
        """Find a continuum component by ID from the project or the open editor.

        Args:
            continuum_id: The continuum ID to find.

        Returns:
            ContinuumComponent if found, None otherwise.
        """
        project = self._project_provider()
        if project is not None:
            component = project.model.get_component_by_id(continuum_id)
            if isinstance(component, ContinuumComponent):
                return component

        continuum_editor = self._continuum_editor_provider()
        if continuum_editor is not None:
            current = continuum_editor.current_continuum
            if current and current.id == continuum_id:
                return current

        return None
