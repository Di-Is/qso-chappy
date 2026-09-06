"""Qt adapters for project file dialogs, prompts, and persistent directories."""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from chappy.gui.dialogs.close_project_dialog import CloseProjectDialog, prompt_close_project


class SavePromptChoice(Enum):
    """User choice from an unsaved-project prompt."""

    SAVE = auto()
    DISCARD = auto()
    CANCEL = auto()


class RecentProjectDirectoryAdapter:
    """Persist recent project directories through QSettings."""

    _project_key = "recent_directories/project"
    _dragdrop_dialog_key = "dragdrop/always_show_file_dialog"

    def project_start_directory(self) -> str:
        """Return the last usable project directory path."""
        last_dir_raw = QSettings().value(self._project_key, defaultValue="", type=str)
        if isinstance(last_dir_raw, str) and last_dir_raw.strip():
            candidate_dir = Path(last_dir_raw).expanduser()
            if candidate_dir.exists():
                return str(candidate_dir)
        return ""

    def default_save_path(self, project_name: str) -> str:
        """Return a default save path for a project name."""
        start_dir = self.project_start_directory()
        if start_dir:
            return str(Path(start_dir) / f"{project_name}.h5")
        return f"{project_name}.h5"

    def store_project_directory(self, file_path: str) -> None:
        """Store the parent directory for a selected project path."""
        selected_path = Path(file_path)
        QSettings().setValue(self._project_key, str(selected_path.parent))

    def always_show_drop_file_dialog(self) -> bool:
        """Return whether drag/drop should always ask the user for file roles."""
        return bool(QSettings().value(self._dragdrop_dialog_key, defaultValue=False, type=bool))


class ProjectFileDialogAdapter(QObject):
    """Show project open/save file dialogs."""

    def open_project_path(self, parent: QWidget, start_dir: str) -> str:
        """Prompt for a project file to open.

        Args:
            parent: Parent widget.
            start_dir: Initial directory.

        Returns:
            Selected path, or an empty string when cancelled.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            self.tr("&Open Project..."),
            start_dir,
            "HDF5 project files (*.h5 *.hdf5);;All files (*.*)",
        )
        return file_path

    def save_project_path(self, parent: QWidget, default_path: str) -> str:
        """Prompt for a project save path.

        Args:
            parent: Parent widget.
            default_path: Default path shown by the dialog.

        Returns:
            Selected path, or an empty string when cancelled.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            self.tr("Save Project &As..."),
            default_path,
            "HDF5 project files (*.h5 *.hdf5);;All files (*.*)",
        )
        return file_path


class ProjectMessageDialogAdapter(QObject):
    """Show project file operation message boxes."""

    def show_error(self, parent: QWidget, title: str, message: str) -> None:
        """Show a blocking error dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            message: Dialog message.
        """
        QMessageBox.critical(parent, title, message)

    def show_save_error(self, parent: QWidget, message: str) -> None:
        """Show a project save failure dialog.

        Args:
            parent: Parent widget.
            message: Informative save failure message.
        """
        message_box = QMessageBox(parent)
        message_box.setIcon(QMessageBox.Icon.Critical)
        message_box.setWindowTitle(self.tr("Error"))
        message_box.setText(self.tr("Failed to save project"))
        message_box.setInformativeText(message)
        message_box.exec()

    def show_repair_notice(self, parent: QWidget, *, summary: str, details: str) -> None:
        """Show a blocking warning describing automatic project repairs."""
        message_box = QMessageBox(parent)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle(self.tr("Project data was repaired"))
        message_box.setText(summary)
        message_box.setInformativeText(
            self.tr("The project file can still be opened, but review the changes below.")
        )
        message_box.setDetailedText(details)
        message_box.exec()

    def confirm_unsaved_changes(
        self, parent: QWidget, *, project_name: str | None, reason: str
    ) -> SavePromptChoice:
        """Prompt the user for how to handle unsaved project changes.

        Args:
            parent: Parent widget.
            project_name: Current project name, when known.
            reason: Prompt context such as ``close`` or ``shutdown``.

        Returns:
            Normalized prompt choice.
        """
        if reason in {"close", "shutdown"}:
            choice = prompt_close_project(parent, project_name=project_name)
            if choice == CloseProjectDialog.Choice.SAVE:
                return SavePromptChoice.SAVE
            if choice == CloseProjectDialog.Choice.DISCARD:
                return SavePromptChoice.DISCARD
            return SavePromptChoice.CANCEL

        message_box = QMessageBox(parent)
        message_box.setWindowTitle(self.tr("Save Project?"))
        message_box.setText(
            self.tr("The current project has unsaved changes.\nDo you want to save them?")
        )
        message_box.setIcon(QMessageBox.Icon.Warning)

        save_button = message_box.addButton(self.tr("Save"), QMessageBox.ButtonRole.AcceptRole)
        discard_button = message_box.addButton(
            self.tr("Don't Save"), QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = message_box.addButton(self.tr("Cancel"), QMessageBox.ButtonRole.RejectRole)

        message_box.setDefaultButton(save_button)
        message_box.setEscapeButton(cancel_button)
        message_box.exec()

        clicked = message_box.clickedButton()
        if clicked is save_button:
            return SavePromptChoice.SAVE
        if clicked is discard_button:
            return SavePromptChoice.DISCARD
        return SavePromptChoice.CANCEL
