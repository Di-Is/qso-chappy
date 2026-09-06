"""Confirmation dialog for unlinking structure linked lines."""

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


_CONTEXT = "StructureUnlinkConfirmation"
_TITLE_SOURCE = str(
    QT_TRANSLATE_NOOP("StructureUnlinkConfirmation", "Unlink selected linked lines?")
)
_BODY_SOURCE = str(
    QT_TRANSLATE_NOOP(
        "StructureUnlinkConfirmation",
        "This keeps the lines, components, and masks, but removes the links between the lines.",
    )
)
_UNLINK_SOURCE = str(QT_TRANSLATE_NOOP("StructureUnlinkConfirmation", "Unlink"))
_CANCEL_SOURCE = str(QT_TRANSLATE_NOOP("StructureUnlinkConfirmation", "Cancel"))


def confirm_structure_unlink(
    parent: QWidget, preview: StructureImpactPreview, project: SpectroscopyProject
) -> bool:
    """Show the unlink confirmation and return user acceptance."""
    if not preview.changed:
        return False

    message_box, unlink_button = create_structure_unlink_confirmation(parent, preview, project)
    message_box.exec()
    return message_box.clickedButton() is unlink_button


def create_structure_unlink_confirmation(
    parent: QWidget, preview: StructureImpactPreview, project: SpectroscopyProject
) -> tuple[QMessageBox, QPushButton]:
    """Build the unlink confirmation for composition and visual tests."""
    if not preview.changed:
        msg = "An unlink confirmation requires a changed structure impact."
        raise ValueError(msg)
    message_box = QMessageBox(parent)
    message_box.setIcon(QMessageBox.Icon.Question)
    message_box.setWindowTitle(_tr(_TITLE_SOURCE))
    message_box.setText(_tr(_BODY_SOURCE))
    message_box.setInformativeText(format_structure_impact(preview, project))
    unlink_button = message_box.addButton(_tr(_UNLINK_SOURCE), QMessageBox.ButtonRole.AcceptRole)
    cancel_button = message_box.addButton(_tr(_CANCEL_SOURCE), QMessageBox.ButtonRole.RejectRole)
    unlink_button.setObjectName("structureUnlinkConfirmButton")
    cancel_button.setObjectName("structureUnlinkCancelButton")
    apply_button_variant(unlink_button, "primary")
    apply_button_variant(cancel_button, "secondary")
    message_box.setDefaultButton(cancel_button)
    message_box.setEscapeButton(cancel_button)
    enforce_translated_minimum_size(message_box, floor=QSize(520, 280))
    return message_box, unlink_button


def _tr(source: str) -> str:
    """Translate unlink confirmation text in one stable Qt context."""
    return QCoreApplication.translate(_CONTEXT, source)


__all__ = ["confirm_structure_unlink", "create_structure_unlink_confirmation"]
