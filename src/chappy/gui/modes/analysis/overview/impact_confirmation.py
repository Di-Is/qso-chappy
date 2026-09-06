"""Shared structure-impact presentation for structure confirmations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

from chappy.presentation.analysis.structure.impact_display_presenter import (
    build_structure_impact_display,
)

if TYPE_CHECKING:
    from chappy.application.structure import StructureImpactPreview
    from chappy.core.spectroscopy_project import SpectroscopyProject


_CONTEXT = "StructureImpactConfirmation"
_AFFECTED_REGIONS_SOURCE = str(
    QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Affected regions")
)
_DELETED_REGIONS_SOURCE = str(QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Deleted regions"))
_AFFECTED_LINES_SOURCE = str(QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Affected lines"))
_DELETED_LINES_SOURCE = str(QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Deleted lines"))
_AFFECTED_COMPONENTS_SOURCE = str(
    QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Affected components")
)
_DELETED_COMPONENTS_SOURCE = str(
    QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Deleted components")
)
_AFFECTED_MASKS_SOURCE = str(QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Affected masks"))
_DELETED_MASKS_SOURCE = str(QT_TRANSLATE_NOOP("StructureImpactConfirmation", "Deleted masks"))
_NONE_SOURCE = str(QT_TRANSLATE_NOOP("StructureImpactConfirmation", "none"))
#: {label} is an impact category; keep {count} and {identities} unchanged.
_ROW_TEMPLATE_SOURCE = str(
    QT_TRANSLATE_NOOP("StructureImpactConfirmation", "{label} ({count}): {identities}")
)


def format_structure_impact(preview: StructureImpactPreview, project: SpectroscopyProject) -> str:
    """Format all changed and removed structure identities consistently."""
    display = build_structure_impact_display(
        changed_region_ids=preview.changed_region_ids,
        removed_region_ids=preview.removed_region_ids,
        changed_line_ids=preview.changed_line_ids,
        removed_line_ids=preview.removed_line_ids,
        changed_model_ids=preview.changed_model_ids,
        removed_model_ids=preview.removed_model_ids,
        changed_mask_ids=preview.changed_mask_ids,
        removed_mask_ids=preview.removed_mask_ids,
        project=project,
    )
    rows = (
        (_tr(_AFFECTED_REGIONS_SOURCE), display.regions.changed),
        (_tr(_DELETED_REGIONS_SOURCE), display.regions.removed),
        (_tr(_AFFECTED_LINES_SOURCE), display.lines.changed),
        (_tr(_DELETED_LINES_SOURCE), display.lines.removed),
        (_tr(_AFFECTED_COMPONENTS_SOURCE), display.components.changed),
        (_tr(_DELETED_COMPONENTS_SOURCE), display.components.removed),
        (_tr(_AFFECTED_MASKS_SOURCE), display.masks.changed),
        (_tr(_DELETED_MASKS_SOURCE), display.masks.removed),
    )
    empty = _tr(_NONE_SOURCE)
    row_template = _tr(_ROW_TEMPLATE_SOURCE)
    return "\n".join(
        row_template.format(
            label=label,
            count=len(identities),
            identities=", ".join(identities) if identities else empty,
        )
        for label, identities in rows
    )


def _tr(source: str) -> str:
    """Translate impact labels in one stable Qt context."""
    return QCoreApplication.translate(_CONTEXT, source)


__all__ = ["format_structure_impact"]
