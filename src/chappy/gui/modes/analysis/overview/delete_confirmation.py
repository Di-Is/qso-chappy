"""Shared confirmation dialog for structure structure deletion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication, QSize
from PySide6.QtWidgets import QMessageBox, QPushButton

from chappy.gui.dialog_sizing import enforce_translated_minimum_size
from chappy.gui.modes.analysis.overview.impact_confirmation import format_structure_impact
from chappy.gui.theme import apply_button_variant

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from chappy.application.structure import StructureImpactPreview
    from chappy.core.spectroscopy_project import SpectroscopyProject


_CONTEXT = "StructureDeleteConfirmation"
_TITLE_SOURCE = str(QT_TRANSLATE_NOOP("StructureDeleteConfirmation", "Delete selected structure?"))
_BODY_SOURCE = str(
    #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
    QT_TRANSLATE_NOOP(
        "StructureDeleteConfirmation",
        "Deleted regions, lines, and components can be restored with Undo ({undo_shortcut}).",
    )
)
_DELETE_SOURCE = str(QT_TRANSLATE_NOOP("StructureDeleteConfirmation", "Delete"))
_CANCEL_SOURCE = str(QT_TRANSLATE_NOOP("StructureDeleteConfirmation", "Cancel"))


def confirm_structure_delete(
    parent: QWidget,
    preview: StructureImpactPreview,
    project: SpectroscopyProject,
    *,
    undo_shortcut: str,
) -> bool:
    """Show the common destructive confirmation and return user acceptance."""
    if not preview.changed:
        return False

    message_box, delete_button = create_structure_delete_confirmation(
        parent, preview, project, undo_shortcut=undo_shortcut
    )
    message_box.exec()
    return message_box.clickedButton() is delete_button


def create_structure_delete_confirmation(
    parent: QWidget,
    preview: StructureImpactPreview,
    project: SpectroscopyProject,
    *,
    undo_shortcut: str,
) -> tuple[QMessageBox, QPushButton]:
    """Build the shared confirmation dialog for composition and visual tests."""
    if not preview.changed:
        msg = "A delete confirmation requires a changed structure impact."
        raise ValueError(msg)
    if not undo_shortcut:
        msg = "A delete confirmation requires an undo shortcut display."
        raise ValueError(msg)
    message_box = QMessageBox(parent)
    message_box.setIcon(QMessageBox.Icon.Warning)
    message_box.setWindowTitle(_tr(_TITLE_SOURCE))
    message_box.setText(_tr(_BODY_SOURCE).format(undo_shortcut=undo_shortcut))
    message_box.setInformativeText(format_structure_impact(preview, project))
    delete_button = message_box.addButton(
        _tr(_DELETE_SOURCE), QMessageBox.ButtonRole.DestructiveRole
    )
    cancel_button = message_box.addButton(_tr(_CANCEL_SOURCE), QMessageBox.ButtonRole.RejectRole)
    delete_button.setObjectName("structureDeleteConfirmButton")
    cancel_button.setObjectName("structureDeleteCancelButton")
    apply_button_variant(delete_button, "danger")
    apply_button_variant(cancel_button, "secondary")
    message_box.setDefaultButton(cancel_button)
    message_box.setEscapeButton(cancel_button)
    enforce_translated_minimum_size(message_box, floor=QSize(520, 280))
    return message_box, delete_button


def _tr(source: str) -> str:
    """Translate confirmation text in one stable Qt context."""
    return QCoreApplication.translate(_CONTEXT, source)


__all__ = ["confirm_structure_delete", "create_structure_delete_confirmation"]
