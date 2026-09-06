"""Coordinate project file operations for the GUI shell."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QMainWindow

from chappy.application.structure.region_line_topology import RegionLineTopologyIssueKind
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.absorption_display import format_region_display, sort_lines_for_display
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.dialogs.file_type_selection_dialog import FileTypeSelectionDialog
from chappy.gui.dialogs.observation_data_dialog import ObservationDataDialog
from chappy.gui.shell.project_file_classifier import (
    EXPECTED_FITS_PAIR_COUNT,
    PROJECT_EXTENSIONS,
    AmbiguousFITSFileSelectionError,
    ObservationFileClassifier,
)
from chappy.gui.shell.project_file_dialog_adapters import (
    ProjectFileDialogAdapter,
    ProjectMessageDialogAdapter,
    RecentProjectDirectoryAdapter,
    SavePromptChoice,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    from chappy.application.project_io_usecase import ProjectIOUseCase
    from chappy.application.structure.region_line_repair import RegionLineRepairReport
logger = logging.getLogger(__name__)

_RequiredDependency = TypeVar("_RequiredDependency")
_RECOVERABLE_PROJECT_FILE_ERRORS = (OSError, ValueError)


@runtime_checkable
class ProjectFileMainWindow(Protocol):
    """Required host surface for project-file operations."""

    @property
    def current_project(self) -> SpectroscopyProject | None:
        """Return the active project, if any."""


@runtime_checkable
class ProjectFilePathHost(Protocol):
    """Required host surface for reading the session-owned project file path."""

    @property
    def project_file_path(self) -> str | None:
        """Return the file path recorded for the active project, if any."""


class RequiredProjectFileDependencyError(RuntimeError):
    """Raised when a required project-file coordinator dependency is missing."""


def project_is_dirty(project: SpectroscopyProject, path: str | None) -> bool:
    """Return whether a project has unsaved changes relative to a session path.

    Args:
        project: Project to check.
        path: File path recorded for the project's session, or None if unsaved.

    Returns:
        True when the project should be treated as having unsaved changes.
    """
    if path is None:
        return True
    if not Path(path).exists():
        return True
    file_mtime = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=UTC)
    return project.modified > file_mtime


class ProjectFileCoordinator(QObject):
    """Coordinate all project file operations.

    This class manages creation, loading, and saving of project files,
    including FITS file loading and error file integration.
    """

    # Signals
    project_created = Signal(SpectroscopyProject)
    project_loaded = Signal(SpectroscopyProject)
    project_saved = Signal()
    project_path_recorded = Signal(object)  # str | None
    status_message = Signal(str)  # message

    def __init__(self, main_window: QMainWindow, *, project_io: ProjectIOUseCase) -> None:
        """Initialize the project file coordinator.

        Args:
            main_window: Parent main window instance
            project_io: Project I/O use case used for all project file I/O operations.
        """
        super().__init__()
        self.main_window = main_window
        self._pending_drop_event: QDropEvent | None = None
        self._project_io: ProjectIOUseCase = project_io
        self._file_dialogs: ProjectFileDialogAdapter | None = ProjectFileDialogAdapter(self)
        self._message_dialogs: ProjectMessageDialogAdapter | None = ProjectMessageDialogAdapter(
            self
        )
        self._recent_directories: RecentProjectDirectoryAdapter | None = (
            RecentProjectDirectoryAdapter()
        )
        self._file_classifier: ObservationFileClassifier | None = ObservationFileClassifier()

    def _require_dependency(
        self, dependency: _RequiredDependency | None, name: str
    ) -> _RequiredDependency:
        """Return a required dependency or fail fast on invalid wiring."""
        if dependency is None:
            message = f"Project file dependency is missing: {name}"
            raise RequiredProjectFileDependencyError(message)
        return dependency

    def _current_project(self) -> SpectroscopyProject | None:
        """Return the current project from the required main-window contract."""
        if not isinstance(self.main_window, ProjectFileMainWindow):
            message = "Project file dependency is missing: main_window.current_project"
            raise RequiredProjectFileDependencyError(message)
        project = self.main_window.current_project
        if project is not None and not isinstance(project, SpectroscopyProject):
            message = "main_window.current_project must be SpectroscopyProject or None"
            raise TypeError(message)
        return project

    def _current_project_file_path(self) -> str | None:
        """Return the session-owned project file path from the required contract."""
        if not isinstance(self.main_window, ProjectFilePathHost):
            message = "Project file dependency is missing: main_window.project_file_path"
            raise RequiredProjectFileDependencyError(message)
        path = self.main_window.project_file_path
        if path is not None and not isinstance(path, str):
            message = "main_window.project_file_path must be str or None"
            raise TypeError(message)
        return path

    def _require_dialog_path_list(self, value: object, name: str) -> list[str]:
        """Return a validated dialog-emitted path list."""
        if not isinstance(value, list | tuple):
            message = f"{name} must be a list or tuple of paths"
            raise TypeError(message)
        paths: list[str] = []
        for item in value:
            if not isinstance(item, (str, os.PathLike)):
                message = f"{name} must contain only path-like values"
                raise TypeError(message)
            path = os.fspath(item)
            if not isinstance(path, str):
                message = f"{name} must contain only string paths"
                raise TypeError(message)
            paths.append(path)
        return paths

    def open_observation_data(self) -> None:
        """Create a new project from FITS file."""
        # Check if current project needs saving
        if not self._check_save_current_project():
            return

        dialog = ObservationDataDialog(self.main_window)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        flux_path, error_path = dialog.selected_paths()
        if not flux_path or not error_path:
            logger.warning("Observation data dialog accepted without both files selected")
            return

        self._load_flux_error_pair(flux_path, error_path)

    def open_sample_data(self, flux_path: str, error_path: str, *, resolving_power: float) -> None:
        """Create a new project from the bundled sample FITS pair.

        Args:
            flux_path: Path to the sample flux spectrum.
            error_path: Path to the sample error spectrum.
            resolving_power: Known instrumental resolving power of the sample,
                applied so the resolution prompt is skipped.
        """
        if not self._check_save_current_project():
            return

        self._load_flux_error_pair(flux_path, error_path, resolving_power=resolving_power)

    def _load_flux_error_pair(
        self, flux_path: str, error_path: str, *, resolving_power: float | None = None
    ) -> None:
        """Create and publish a project from a flux/error FITS pair.

        Args:
            flux_path: Path to the flux spectrum.
            error_path: Path to the error spectrum.
            resolving_power: Instrumental resolving power to apply to the
                created project, when known in advance.
        """
        project_io = self._require_dependency(self._project_io, "_project_io")
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")

        try:
            flux_name = Path(flux_path).name
            error_name = Path(error_path).name

            loading_template = self.tr("Loading flux: {flux} with error: {error}...")
            self.status_message.emit(loading_template.format(flux=flux_name, error=error_name))

            project = project_io.create_from_fits(flux_path)
            self._merge_error_file(project, error_path)
            if resolving_power is not None:
                project.set_resolution(resolving_power, enabled=True)

            self.project_created.emit(project)
            self.project_path_recorded.emit(None)
            loaded_template = self.tr("✅ Loaded: {flux} with error: {error}")
            self.status_message.emit(loaded_template.format(flux=flux_name, error=error_name))

        except _RECOVERABLE_PROJECT_FILE_ERRORS as exc:  # pragma: no cover - Qt dialog path
            logger.exception("Failed to create project from observation data", exc_info=exc)
            message_dialogs.show_error(
                self.main_window,
                self.tr("Error"),
                self.tr("Failed to load observation data:\n{error}").format(error=exc),
            )
            self.status_message.emit(self.tr("Failed to load observation data"))

    def open_project(self) -> None:
        """Open an existing project file."""
        file_dialogs = self._require_dependency(self._file_dialogs, "_file_dialogs")
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        project_io = self._require_dependency(self._project_io, "_project_io")
        recent_directories = self._require_dependency(
            self._recent_directories, "_recent_directories"
        )

        # Check if current project needs saving
        if not self._check_save_current_project():
            return

        file_path = file_dialogs.open_project_path(
            self.main_window, recent_directories.project_start_directory()
        )

        if not file_path:
            return

        try:
            # Load project
            self.status_message.emit(self.tr("Loading project..."))
            load_result = project_io.load_project(file_path)
            project = load_result.project
            if load_result.repair_report.has_repairs:
                self._show_repair_notice(load_result.repair_report, project)

            # Emit signals for project loading
            self.project_loaded.emit(project)
            self.project_path_recorded.emit(file_path)
            project_name = Path(file_path).name
            opened_template = self.tr("Opened project: {name}")
            self.status_message.emit(opened_template.format(name=project_name))

            recent_directories.store_project_directory(file_path)

        except _RECOVERABLE_PROJECT_FILE_ERRORS as e:
            logger.exception("Failed to open project file", extra={"error": str(e)})
            message_dialogs.show_error(
                self.main_window,
                self.tr("Error"),
                self.tr("Failed to open project:\n{error}").format(error=e),
            )

    def save_project(self, project: SpectroscopyProject | None) -> bool:
        """Save current project.

        Args:
            project: Project to save

        Returns:
            True if saved successfully, False otherwise
        """
        if not project:
            return False

        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        project_io = self._require_dependency(self._project_io, "_project_io")

        current_path = self._current_project_file_path()

        try:
            if current_path:
                existing_ext = Path(current_path).suffix.lower()
                if existing_ext not in PROJECT_EXTENSIONS:
                    return self.save_project_as(project)
                # Save to existing file
                self.status_message.emit(self.tr("Saving project..."))
                project_io.save_project(project, current_path)
                self.status_message.emit(self.tr("Project saved"))
                self.project_saved.emit()
                return True
            # No filename - redirect to save as
            return self.save_project_as(project)

        except _RECOVERABLE_PROJECT_FILE_ERRORS as e:
            logger.exception("Failed to save project", extra={"error": str(e)})
            message_dialogs.show_save_error(
                self.main_window, self.tr("Failed to save project:\n{error}").format(error=e)
            )
            return False

    def save_project_as(self, project: SpectroscopyProject | None) -> bool:
        """Save project with new filename.

        Args:
            project: Project to save

        Returns:
            True if saved successfully, False otherwise
        """
        if not project:
            return False

        file_dialogs = self._require_dependency(self._file_dialogs, "_file_dialogs")
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        project_io = self._require_dependency(self._project_io, "_project_io")
        recent_directories = self._require_dependency(
            self._recent_directories, "_recent_directories"
        )

        file_path = file_dialogs.save_project_path(
            self.main_window, recent_directories.default_save_path(project.name)
        )

        if not file_path:
            return False

        selected_path = Path(file_path)

        try:
            # Save project with new filename
            self.status_message.emit(self.tr("Saving project..."))
            project_io.save_project(project, file_path)
            saved_name = selected_path.name
            saved_template = self.tr("Project saved as: {name}")
            self.status_message.emit(saved_template.format(name=saved_name))
            self.project_saved.emit()
            self.project_path_recorded.emit(file_path)

            recent_directories.store_project_directory(file_path)

            return True  # noqa: TRY300

        except _RECOVERABLE_PROJECT_FILE_ERRORS as e:
            logger.exception("Failed to save project as", extra={"error": str(e)})
            message_dialogs.show_error(
                self.main_window,
                self.tr("Error"),
                self.tr("Failed to save project:\n{error}").format(error=e),
            )
            return False

    def _check_save_current_project(self, reason: str = "generic") -> bool:
        """Check if current project needs saving.

        Args:
            reason: Context for the save check (e.g. "close").

        Returns:
            True if OK to continue, False if cancelled
        """
        if os.environ.get("CHAPPY_DOC_AUTO_DISCARD"):
            return True

        current_project = self._current_project()
        if not current_project or not project_is_dirty(
            current_project, self._current_project_file_path()
        ):
            return True

        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        choice = message_dialogs.confirm_unsaved_changes(
            self.main_window, project_name=current_project.name, reason=reason
        )
        if choice == SavePromptChoice.SAVE:
            return self.save_project(current_project)
        return choice == SavePromptChoice.DISCARD

    def _merge_error_file(self, project: SpectroscopyProject, error_file_path: str) -> None:
        """Merge error data from FITS file into project.

        Args:
            project: Project to merge error data into
            error_file_path: Path to error FITS file
        """
        project_io = self._require_dependency(self._project_io, "_project_io")
        project_io.merge_error_data(project, error_file_path)

    def handle_drag_enter_event(self, event: QDragEnterEvent) -> None:
        """Handle drag enter events for file drops.

        Args:
            event: Drag enter event
        """
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        urls = event.mimeData().urls()
        local_files = [url.toLocalFile() for url in urls if url.isLocalFile()]

        file_classifier = self._require_dependency(self._file_classifier, "_file_classifier")
        classification = file_classifier.classify_paths(local_files)

        if classification.has_mixed_supported_types:
            event.ignore()
            self.status_message.emit(
                self.tr("❌ Please drop either FITS files or a project file, not both.")
            )
            return

        if classification.project_files:
            project_name = Path(classification.project_files[0]).name
            self.status_message.emit(
                self.tr("✅ Ready to load project: {name}").format(name=project_name)
            )
            event.acceptProposedAction()
            return

        if classification.fits_files:
            project_io = self._require_dependency(self._project_io, "_project_io")
            first_file = classification.fits_files[0]
            try:
                is_valid, issues = project_io.validate_fits_spectrum(first_file)

                if is_valid:
                    fits_info = project_io.get_fits_info(first_file)
                    file_name = Path(first_file).name
                    primary_shape = fits_info.get("primary_shape")
                    pixel_suffix = ""
                    if isinstance(primary_shape, list | tuple) and primary_shape:
                        pixel_suffix = self.tr(" ({pixel_count} pixels)").format(
                            pixel_count=primary_shape[0]
                        )

                    event.acceptProposedAction()
                    self.status_message.emit(
                        self.tr("✅ Ready to load: {file_name}{pixel_suffix}").format(
                            file_name=file_name, pixel_suffix=pixel_suffix
                        )
                    )
                    logger.debug("Drag enter: accepting valid FITS file %s", file_name)
                else:
                    event.ignore()
                    issue_summary = issues[0] if issues else self.tr("Unknown validation error")
                    self.status_message.emit(
                        self.tr("❌ Invalid FITS file: {reason}").format(reason=issue_summary)
                    )
                    logger.warning("Drag rejected: FITS validation failed: %s", issues)

            except _RECOVERABLE_PROJECT_FILE_ERRORS as exc:
                event.ignore()
                self.status_message.emit(
                    self.tr("❌ Cannot read FITS file: {error}").format(error=exc)
                )
                logger.warning("Drag rejected: FITS read error: %s", exc)
            return

        event.ignore()
        self.status_message.emit(
            self.tr("❌ Only FITS (.fits, .fit) or project files are supported.")
        )

    def handle_drop_event(self, event: QDropEvent) -> None:
        """Handle drop events for FITS files.

        Args:
            event: Drop event
        """
        urls = event.mimeData().urls()
        local_files = [url.toLocalFile() for url in urls if url.isLocalFile()]
        file_classifier = self._require_dependency(self._file_classifier, "_file_classifier")
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        classification = file_classifier.classify_paths(local_files)
        fits_files = list(classification.fits_files)
        project_files = list(classification.project_files)

        if classification.has_mixed_supported_types:
            self.status_message.emit(
                self.tr(
                    "❌ Please drop either the flux/error pair or a single project file, not both."
                )
            )
            event.ignore()
            return

        if project_files:
            if len(project_files) > 1:
                self.status_message.emit(
                    self.tr("❌ Only one project file can be opened at a time.")
                )
                event.ignore()
                return

            if not self._check_save_current_project():
                event.ignore()
                return

            self._handle_project_file(project_files[0], event)
            return

        if not fits_files:
            self.status_message.emit(
                self.tr("❌ No valid FITS or project files found in the drop.")
            )
            event.ignore()
            return

        try:
            if not self._check_save_current_project():
                event.ignore()
                return

            if len(fits_files) > 1:
                self._handle_multiple_files_drop(fits_files, event)
            else:
                self._handle_single_file_drop(fits_files[0], event)

        except _RECOVERABLE_PROJECT_FILE_ERRORS as exc:
            message_dialogs.show_error(
                self.main_window,
                self.tr("Error"),
                self.tr("Could not load dropped files:\n{error}").format(error=exc),
            )
            self.status_message.emit(self.tr("❌ Failed to load dropped file."))
            logger.exception("Failed to load dropped files")

    def _find_error_file(self, fits_file: str) -> str | None:
        """Find corresponding error file for a FITS spectrum file.

        Args:
            fits_file: Path to the main FITS file

        Returns:
            Path to error file if found, None otherwise
        """
        fits_path = Path(fits_file)
        directory = fits_path.parent
        stem = fits_path.stem
        suffix = fits_path.suffix

        # Common error file naming patterns
        error_patterns = [
            f"{stem}_err{suffix}",
            f"{stem}_error{suffix}",
            f"{stem}.err{suffix}",
            f"{stem}.error{suffix}",
            f"{stem}_sigma{suffix}",
            f"{stem}.sigma{suffix}",
            f"{stem}_unc{suffix}",  # uncertainty
            f"{stem}.unc{suffix}",
            f"{stem}_noise{suffix}",
            f"{stem}.noise{suffix}",
        ]

        # Also try with different case variations
        for pattern in error_patterns.copy():
            error_patterns.extend(
                [
                    pattern.upper(),
                    pattern.lower(),
                    pattern.replace("_", "-"),  # dash instead of underscore
                ]
            )

        # Check each pattern
        for pattern in error_patterns:
            error_file_path = directory / pattern
            if error_file_path.exists() and error_file_path.is_file():
                # Verify it's a valid FITS file
                try:
                    project_io = self._require_dependency(self._project_io, "_project_io")
                    is_valid, _ = project_io.validate_fits_spectrum(str(error_file_path))
                    if is_valid:
                        logger.info("Found error file: %s", error_file_path)
                        return str(error_file_path)
                except _RECOVERABLE_PROJECT_FILE_ERRORS as e:
                    logger.debug("Error file validation failed for %s: %s", error_file_path, e)
                    continue

        logger.debug("No error file found for %s", fits_file)
        return None

    def _handle_single_file_drop(self, fits_file: str, event: QDropEvent) -> None:
        """Handle single file drop with auto-error detection.

        Args:
            fits_file: Path to the FITS file
            event: Drop event
        """
        # Auto-detect error file
        error_file = self._find_error_file(fits_file)
        flux_name = Path(fits_file).name

        if error_file:
            self.status_message.emit(
                self.tr("Loading flux {flux_name} with {count} error file(s)...").format(
                    flux_name=flux_name, count=1
                )
            )
        else:
            self.status_message.emit(
                self.tr("Loading flux file: {flux_name}...").format(flux_name=flux_name)
            )

        project_io = self._require_dependency(self._project_io, "_project_io")
        project = project_io.create_from_fits(fits_file)

        # If error file was found, try to load and merge error data
        if error_file:
            self._merge_error_file(project, error_file)

        # Set as current project through signal
        self.project_created.emit(project)
        self.project_path_recorded.emit(None)

        if error_file:
            success_msg = self.tr("✅ Loaded: {flux_name} with error: {error_name}").format(
                flux_name=flux_name, error_name=Path(error_file).name
            )
        else:
            success_msg = self.tr("✅ Loaded project from: {source}").format(source=flux_name)

        self.status_message.emit(success_msg)
        logger.info("Loaded project from dropped file: %s", fits_file)

        event.acceptProposedAction()

    def _handle_multiple_files_drop(self, fits_files: list[str], event: QDropEvent) -> None:
        """Handle multiple files drop with file type selection dialog.

        Args:
            fits_files: List of FITS file paths
            event: Drop event
        """
        recent_directories = self._require_dependency(
            self._recent_directories, "_recent_directories"
        )
        file_classifier = self._require_dependency(self._file_classifier, "_file_classifier")
        project_io = self._require_dependency(self._project_io, "_project_io")
        always_show_dialog = recent_directories.always_show_drop_file_dialog()

        if not always_show_dialog and len(fits_files) == EXPECTED_FITS_PAIR_COUNT:
            # Try automatic detection for two files
            try:
                flux_file, error_file = file_classifier.identify_flux_and_error_files(
                    fits_files, self._find_error_file
                )
            except AmbiguousFITSFileSelectionError:
                logger.info("FITS auto-detection was ambiguous; showing selection dialog")
            else:
                if error_file and flux_file != error_file:
                    # Successful automatic detection - proceed directly
                    flux_name = Path(flux_file).name
                    error_name = Path(error_file).name
                    self.status_message.emit(
                        self.tr("Auto-detected: flux={flux_name}, error={error_name}...").format(
                            flux_name=flux_name, error_name=error_name
                        )
                    )

                    project = project_io.create_from_fits(str(flux_file))
                    self._merge_error_file(project, error_file)
                    self.project_created.emit(project)
                    self.project_path_recorded.emit(None)

                    success_msg = self.tr(
                        "✅ Loaded: {flux_name} with error: {error_name}"
                    ).format(flux_name=flux_name, error_name=error_name)
                    self.status_message.emit(success_msg)
                    logger.info("Auto-loaded flux-error pair: %s, %s", flux_file, error_file)

                    event.acceptProposedAction()
                    return

        # Fallback to dialog (either setting enabled or auto-detection failed)
        dialog = FileTypeSelectionDialog(fits_files, self.main_window, project_io=project_io)
        dialog.files_selected.connect(self._on_files_selected_from_dialog)

        # Store event for later use
        self._pending_drop_event = event

        dialog.exec()

    def _on_files_selected_from_dialog(self, file_selections: dict[str, object]) -> None:
        """Handle file selections from the dialog.

        Args:
            file_selections: Dictionary with flux_file, error_files, ignored_files
        """
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        project_io = self._require_dependency(self._project_io, "_project_io")

        try:
            flux_file = file_selections["flux_file"]
            error_files = self._require_dialog_path_list(
                file_selections["error_files"], "error_files"
            )
            ignored_files = self._require_dialog_path_list(
                file_selections["ignored_files"], "ignored_files"
            )

            if not flux_file:
                self.status_message.emit(self.tr("❌ No flux file selected."))
                return

            if not isinstance(flux_file, (str, os.PathLike)):
                message = "flux_file must be path-like"
                raise TypeError(message)
            flux_path = os.fspath(flux_file)
            if not isinstance(flux_path, str):
                message = "flux_file must be a string path"
                raise TypeError(message)

            flux_name = Path(flux_path).name
            if error_files:
                self.status_message.emit(
                    self.tr("Loading flux {flux_name} with {count} error file(s)...").format(
                        flux_name=flux_name, count=len(error_files)
                    )
                )
            else:
                self.status_message.emit(
                    self.tr("Loading flux file: {flux_name}...").format(flux_name=flux_name)
                )

            project = project_io.create_from_fits(flux_path)

            # Merge error files
            for error_file in error_files:
                self._merge_error_file(project, error_file)

            # Set as current project through signal
            self.project_created.emit(project)
            self.project_path_recorded.emit(None)

            # Success message
            if error_files:
                if len(error_files) == 1:
                    success_msg = self.tr(
                        "✅ Loaded: {flux_name} with error: {error_name}"
                    ).format(flux_name=flux_name, error_name=Path(str(error_files[0])).name)
                else:
                    success_msg = self.tr(
                        "✅ Loaded: {flux_name} with {count} error files"
                    ).format(flux_name=flux_name, count=len(error_files))
            else:
                success_msg = self.tr("✅ Loaded project from: {source}").format(source=flux_name)

            if ignored_files:
                ignored_count = len(ignored_files)
                success_msg += self.tr(" • {count} file(s) ignored").format(count=ignored_count)

            self.status_message.emit(success_msg)
            logger.info(
                "Loaded project: flux=%s, errors=%d, ignored=%d",
                flux_name,
                len(error_files),
                len(ignored_files),
            )

            # Accept the drop event
            if self._pending_drop_event is not None:
                self._pending_drop_event.acceptProposedAction()
                self._pending_drop_event = None

        except _RECOVERABLE_PROJECT_FILE_ERRORS as e:
            message_dialogs.show_error(
                self.main_window,
                self.tr("Error"),
                self.tr("Could not load selected files:\n{error}").format(error=e),
            )
            self.status_message.emit(self.tr("❌ Failed to load selected files."))
            logger.exception("Failed to load files from dialog selection")

    def check_save_current_project(self, *, reason: str = "generic") -> bool:
        """Check if current project needs saving and handle user decision.

        This is a public API for the private _check_save_current_project method.

        Args:
            reason: Context for the save prompt (e.g. "close" when closing a project)

        Returns:
            True if OK to continue (no changes or user chose to discard/save),
            False if user cancelled the operation
        """
        return self._check_save_current_project(reason=reason)

    def _handle_project_file(self, project_path: str, event: QDropEvent) -> None:
        """Handle loading a dropped project file."""
        path_obj = Path(project_path)
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        project_io = self._require_dependency(self._project_io, "_project_io")

        try:
            self.status_message.emit(self.tr("Loading project..."))
            load_result = project_io.load_project(project_path)
            project = load_result.project
            if load_result.repair_report.has_repairs:
                self._show_repair_notice(load_result.repair_report, project)
            self.project_loaded.emit(project)
            self.project_path_recorded.emit(project_path)
            opened_template = self.tr("Opened project: {name}")
            self.status_message.emit(opened_template.format(name=path_obj.name))
            event.acceptProposedAction()
        except _RECOVERABLE_PROJECT_FILE_ERRORS as exc:
            message_dialogs.show_error(
                self.main_window,
                self.tr("Error"),
                self.tr("Failed to open project:\n{error}").format(error=exc),
            )
            self.status_message.emit(self.tr("Failed to open project"))
            logger.exception("Failed to load project file: %s", project_path)
            event.ignore()

    def _show_repair_notice(
        self, report: RegionLineRepairReport, project: SpectroscopyProject
    ) -> None:
        """Describe automatic repairs before publishing the loaded project."""
        message_dialogs = self._require_dependency(self._message_dialogs, "_message_dialogs")
        #: {count} is the number of automatically repaired line references.
        summary_template = self.tr(
            "{count} inconsistent line reference(s) were automatically fixed while opening "
            "this project."
        )
        detail_lines: list[str] = []

        def region_label(region_id: str) -> str:
            if region_id == UNASSIGNED_REGION_ID:
                return self.tr("Unassigned")
            region = project.absorption_regions.get(region_id)
            if region is None:
                return region_id[:8]
            lines = sort_lines_for_display(
                [
                    project.absorption_lines[line_id]
                    for line_id in region.line_ids
                    if line_id in project.absorption_lines
                ]
            )
            return (
                format_region_display(lines, region.analysis_range).display_name
                if lines
                else region_id[:8]
            )

        for action in report.actions:
            if action.kind is RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE:
                #: {region} is the display identity of an absorption region.
                template = self.tr('Region "{region}": a reference to a missing line was removed.')
                detail_lines.append(template.format(region=region_label(action.region_id)))
                continue

            line_label = f"{action.line_species} {action.line_transition}".strip()
            if not line_label:
                #: {region} is the display identity of an absorption region.
                template = self.tr('Region "{region}": an inconsistent line was reassigned.')
                detail_lines.append(template.format(region=region_label(action.region_id)))
                continue

            if action.kind is RegionLineTopologyIssueKind.DUPLICATE_MEMBERSHIP:
                #: {region} is a region label; {species} and {transition} identify a line.
                template = self.tr(
                    'Region "{region}": line "{species} {transition}" was removed from this '
                    "region because another region owns it."
                )
                detail_lines.append(
                    template.format(
                        region=region_label(action.region_id),
                        species=action.line_species,
                        transition=action.line_transition,
                    )
                )
                continue

            if action.kind is RegionLineTopologyIssueKind.REGION_LINE_MISMATCH:
                #: {region} is a region label; {species} and {transition} identify a line.
                template = self.tr(
                    'Region "{region}": line "{species} {transition}" was updated to reference '
                    "this region."
                )
                detail_lines.append(
                    template.format(
                        region=region_label(action.region_id),
                        species=action.line_species,
                        transition=action.line_transition,
                    )
                )
                continue

            #: {species} and {transition} identify a line; {unassigned} is a region label.
            template = self.tr(
                'Line "{species} {transition}" did not belong to any region and was moved to '
                "{unassigned}."
            )
            detail_lines.append(
                template.format(
                    species=action.line_species,
                    transition=action.line_transition,
                    unassigned=self.tr("Unassigned"),
                )
            )

        removed_region_ids = sorted(
            {
                action.region_id
                for action in report.actions
                if action.kind is not RegionLineTopologyIssueKind.UNLISTED_LINE
                and action.region_id != UNASSIGNED_REGION_ID
                and action.region_id not in project.absorption_regions
            }
        )
        for region_id in removed_region_ids:
            #: {region} is the display identity of an absorption region.
            template = self.tr('Region "{region}" no longer has any lines and was removed.')
            detail_lines.append(template.format(region=region_label(region_id)))

        message_dialogs.show_repair_notice(
            self.main_window,
            summary=summary_template.format(count=len(report.actions)),
            details="\n".join(detail_lines),
        )
