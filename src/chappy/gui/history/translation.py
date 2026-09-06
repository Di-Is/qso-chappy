"""Translation utilities for history operation names."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

from chappy.core.history import OperationId

if TYPE_CHECKING:
    from chappy.i18n.language_switcher import LanguageSwitcher

_TRANSLATION_CONTEXT = "HistoryOperation"
_OPERATION_SOURCES: dict[str, str] = {
    "ident.add_temporary_line": str(QT_TRANSLATE_NOOP("HistoryOperation", "Add Temporary Line")),
    "ident.remove_temporary_line": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Remove Temporary Line")
    ),
    "ident.clear_temporary_lines": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Clear Temporary Lines")
    ),
    "ident.register_selected": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Register Selected Lines")
    ),
    "structure.move_linked_lines": str(QT_TRANSLATE_NOOP("HistoryOperation", "Move Lines")),
    "structure.split": str(QT_TRANSLATE_NOOP("HistoryOperation", "Split Region")),
    "structure.merge": str(QT_TRANSLATE_NOOP("HistoryOperation", "Merge Regions")),
    "structure.delete": str(QT_TRANSLATE_NOOP("HistoryOperation", "Delete Region")),
    "structure.unlink_linked_lines": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Unlink Linked Lines")
    ),
    "mask.create": str(QT_TRANSLATE_NOOP("HistoryOperation", "Create Mask")),
    "mask.delete": str(QT_TRANSLATE_NOOP("HistoryOperation", "Delete Mask")),
    "mask.edit": str(QT_TRANSLATE_NOOP("HistoryOperation", "Edit Mask")),
    "cont.add_component": str(QT_TRANSLATE_NOOP("HistoryOperation", "Add Component")),
    "cont.add_point": str(QT_TRANSLATE_NOOP("HistoryOperation", "Add Continuum Point")),
    "cont.delete_point": str(QT_TRANSLATE_NOOP("HistoryOperation", "Delete Continuum Point")),
    "cont.move_point": str(QT_TRANSLATE_NOOP("HistoryOperation", "Move Continuum Point")),
    "cont.reset": str(QT_TRANSLATE_NOOP("HistoryOperation", "Reset Continuum")),
    "model.add": str(QT_TRANSLATE_NOOP("HistoryOperation", "Add Component")),
    "model.delete": str(QT_TRANSLATE_NOOP("HistoryOperation", "Delete Component")),
    "model.bulk_add": str(QT_TRANSLATE_NOOP("HistoryOperation", "Bulk Add Components")),
    "model.bulk_delete": str(QT_TRANSLATE_NOOP("HistoryOperation", "Bulk Delete Components")),
    "model.edit_params": str(QT_TRANSLATE_NOOP("HistoryOperation", "Edit Parameters")),
    "model.edit_resolution": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Edit Spectral Resolution")
    ),
    "model.edit_line_analysis_half_width": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Edit Line Analysis Range")
    ),
    "model.bulk_add_multiplet": str(QT_TRANSLATE_NOOP("HistoryOperation", "Bulk Add Multiplet")),
    "model.bulk_delete_multiplet": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Bulk Delete Multiplet")
    ),
    "model.optimize_apply": str(QT_TRANSLATE_NOOP("HistoryOperation", "Apply Optimization")),
    "model.tie_set_create": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Create shared parameter group")
    ),
    "model.tie_set_remove": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Remove from shared parameter group")
    ),
    "model.tie_set_dissolve": str(
        QT_TRANSLATE_NOOP("HistoryOperation", "Dissolve shared parameter group")
    ),
    "draw.range_change": str(QT_TRANSLATE_NOOP("HistoryOperation", "Change Display Range")),
}

_MISSING_OPERATION_SOURCES = {
    operation_id.value for operation_id in OperationId
} - _OPERATION_SOURCES.keys()
if _MISSING_OPERATION_SOURCES:
    msg = (
        "History operation translation catalog is missing entries: "
        f"{sorted(_MISSING_OPERATION_SOURCES)}"
    )
    raise RuntimeError(msg)


def normalize_operation_id(full_operation_id: str) -> str:
    """Normalize an operation ID to namespace.action.

    Args:
        full_operation_id: Full operation ID, e.g. ``cont.add_point.nav``.

    Returns:
        Normalized operation ID, e.g. ``cont.add_point``.

    Raises:
        ValueError: If the operation ID does not contain namespace and action.
    """
    parts = full_operation_id.split(".")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        msg = f"Malformed history operation ID: {full_operation_id!r}"
        raise ValueError(msg)

    return f"{parts[0]}.{parts[1]}"


def translate_operation(full_operation_id: str, language_switcher: LanguageSwitcher) -> str:
    """Translate operation ID to a human-readable name.

    Args:
        full_operation_id: Full operation ID, e.g. ``cont.add_point.nav``.
        language_switcher: Kept for compatibility with existing callers.

    Returns:
        Translated operation name for UI display.

    Raises:
        KeyError: If the operation ID is not part of the translation catalog.
    """
    _ = language_switcher
    operation_id = normalize_operation_id(full_operation_id)
    source_text = _OPERATION_SOURCES.get(operation_id)

    if source_text is None:
        msg = f"Missing history operation source text: {full_operation_id}"
        raise KeyError(msg)

    return QCoreApplication.translate(_TRANSLATION_CONTEXT, source_text)
