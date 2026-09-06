"""Shell runtime entrypoint that hides the concrete main-window owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication

from chappy.gui.shell.dependencies import (
    DialogCommandPort,
    ModeCommandPort,
    ProjectCommandPort,
    SpectrumNavigationPort,
    StatusMessagePort,
    WindowChromePort,
)

if TYPE_CHECKING:
    from pathlib import Path

    from chappy.application.project_io_usecase import ProjectIOUseCase
    from chappy.core.editing_mode import EditingMode
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.shell.main_window import MainWindow


class ShellRuntime(
    WindowChromePort,
    StatusMessagePort,
    ProjectCommandPort,
    ModeCommandPort,
    DialogCommandPort,
    SpectrumNavigationPort,
):
    """External shell API that wraps the current concrete main window."""

    def __init__(
        self,
        main_window: MainWindow,
        *,
        project_io_usecase: ProjectIOUseCase,
        dialog_commands: DialogCommandPort,
    ) -> None:
        """Initialize the shell runtime.

        Args:
            main_window: Concrete top-level window currently owning shell workflows.
            project_io_usecase: Project I/O use case used by initial file load.
            dialog_commands: Dialog command owner used by shell entrypoints.
        """
        self._main_window = main_window
        self._project_io_usecase = project_io_usecase
        self._dialog_commands = dialog_commands

    @property
    def current_project(self) -> SpectroscopyProject | None:
        """Return the active project."""
        return self._main_window.current_project

    def show(self) -> None:
        """Show the shell window."""
        self._main_window.show()

    def maybe_show_first_run_welcome(self) -> None:
        """Show the welcome dialog once on the first application launch."""
        self._main_window.maybe_show_first_run_welcome()

    def close(self) -> bool:
        """Close the shell window."""
        return self._main_window.close()

    def show_status_message(self, message: str, timeout_ms: int = 3000) -> None:
        """Display a shell status message."""
        self._main_window.status_message.emit(message, timeout_ms)

    def open_observation_data(self) -> None:
        """Open observation data."""
        self._main_window.open_observation_data()

    def open_project(self) -> None:
        """Open a project."""
        self._main_window.open_project()

    def save_project(self) -> None:
        """Save the active project."""
        self._main_window.save_project()

    def save_project_as(self) -> None:
        """Save the active project with a new path."""
        self._main_window.save_project_as()

    def close_project(self) -> None:
        """Close the active project."""
        self._main_window.close_project()

    def set_current_project(self, project: SpectroscopyProject | None) -> None:
        """Replace the active project."""
        self._main_window.set_current_project(project)

    def switch_mode(self, mode: EditingMode) -> None:
        """Switch the active editing mode."""
        self._main_window.switch_mode(mode)

    def add_continuum(self) -> None:
        """Add a continuum component."""
        self._main_window.continuum_mode_runtime.add_continuum()

    def fit_model(self) -> None:
        """Run the optimize fit workflow."""
        self._main_window.optimize_velocity_runtime.fit_model()

    def back_to_analysis_overview(self) -> None:
        """Return to Analysis Overview."""
        self._main_window.back_to_analysis_overview()

    def delete_selection(self) -> None:
        """Delete the current Analysis Structure selection through the shell workflow."""
        coordinator = self._main_window._dock_coordinator
        if coordinator is None:
            msg = "Dock layout coordinator is required for Analysis Structure deletion."
            raise RuntimeError(msg)
        coordinator._execute_structure_delete()

    def open_user_manual(self) -> None:
        """Open the user manual."""
        self._dialog_commands.open_user_manual()

    def show_cosmology_dialog(self) -> None:
        """Open the cosmology settings dialog."""
        self._dialog_commands.show_cosmology_dialog()

    def show_resolution_dialog(self) -> None:
        """Open the resolution settings dialog."""
        self._dialog_commands.show_resolution_dialog()

    def open_line_database_folder(self) -> None:
        """Open the folder holding the spectral line CSV."""
        self._dialog_commands.open_line_database_folder()

    def show_language_dialog(self) -> None:
        """Open the language settings dialog."""
        self._dialog_commands.show_language_dialog()

    def show_preset_list_dialog(self) -> None:
        """Open the identify preset management dialog."""
        self._dialog_commands.show_preset_list_dialog()

    def zoom_in(self) -> None:
        """Zoom in on the active spectrum view."""
        self._main_window.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out on the active spectrum view."""
        self._main_window.zoom_out()

    def reset_view(self) -> None:
        """Reset the active spectrum view."""
        self._main_window.reset_view()

    def auto_adjust_flux(self) -> None:
        """Auto-adjust the active flux range."""
        self._main_window.auto_adjust_flux()

    def toggle_velocity_plot_optimize(self) -> None:
        """Toggle the optimize velocity plot."""
        self._main_window.optimize_velocity_runtime.toggle_velocity_overlay()

    def toggle_velocity_plot_identify(self) -> None:
        """Toggle Identify's velocity plot at the wavelength under the cursor."""
        self._main_window.identify_velocity_runtime.handle_mode_velocity_shortcut()

    def open_initial_file(self, file_path: Path, *, error_file: str | None = None) -> None:
        """Open an initial file passed at application startup.

        Args:
            file_path: Path supplied on the CLI.
            error_file: Optional error-spectrum file path for FITS loading.
        """
        if not file_path.exists():
            template = QCoreApplication.translate("ChappyMain", "File not found: {name}")
            self.show_status_message(template.format(name=file_path.name), 5000)
            return

        if file_path.suffix.lower() not in {".fits", ".fit"}:
            template = QCoreApplication.translate("ChappyMain", "Unknown file type: {suffix}")
            self.show_status_message(template.format(suffix=file_path.suffix), 3000)
            return

        project = self._project_io_usecase.create_from_fits(str(file_path), error_path=error_file)
        self.set_current_project(project)
