"""Keyboard and mouse operation documentation for user manual."""

from __future__ import annotations

from collections.abc import Callable

from chappy_user_manual_generator.translations import translate_manual_text
from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy.gui.common.shared_operations import SHARED_OPERATIONS_TR_CONTEXT, get_shared_operation

_EXPORTER_CONTEXT = "ManualExporter"

_RowRenderer = Callable[[], str]

_shared_op_ids: list[str] = []


def _local_row(source: str) -> _RowRenderer:
    """Return a row renderer for text local to the manual (not shared)."""
    return lambda: translate_manual_text(_EXPORTER_CONTEXT, source)


def _shared_row(op_id: str) -> _RowRenderer:
    """Return a row renderer built from a shared operation's action/expected facts."""
    _shared_op_ids.append(op_id)

    def render() -> str:
        operation = get_shared_operation(op_id)
        action = translate_manual_text(SHARED_OPERATIONS_TR_CONTEXT, operation.action_source)
        expected = translate_manual_text(SHARED_OPERATIONS_TR_CONTEXT, operation.expected_source)
        return f"| {action} | {expected} |"

    return render


# Common operations (all modes)
COMMON_ROWS: tuple[_RowRenderer, ...] = (
    _local_row(QT_TRANSLATE_NOOP("ManualExporter", "| ↑/↓ | Zoom in/out |")),
    _local_row(QT_TRANSLATE_NOOP("ManualExporter", "| ←/→ | Pan left/right |")),
    _shared_row("zoom_rect"),
    _local_row(QT_TRANSLATE_NOOP("ManualExporter", "| Escape | Cancel operation |")),
)

# IDENTIFY mode specific
IDENTIFY_ROWS: tuple[_RowRenderer, ...] = (
    _shared_row("identify_toggle_velocity"),
    _shared_row("identify_shift_click"),
)

# Analysis Region Detail specific
ANALYSIS_DETAIL_ROWS: tuple[_RowRenderer, ...] = (
    _shared_row("analysis_fit"),
    _shared_row("analysis_toggle_velocity"),
    _shared_row("analysis_toggle_component_profiles"),
    _shared_row("optimize_shift_click"),
    _shared_row("optimize_velocity_shift_click"),
    _shared_row("optimize_drag_center"),
)

# CONTINUUM mode specific
CONTINUUM_ROWS: tuple[_RowRenderer, ...] = (
    _shared_row("continuum_add_point"),
    _shared_row("continuum_move_point"),
)

# Mapping scope names to their row definitions
_SCOPE_ROWS: dict[str, tuple[_RowRenderer, ...]] = {
    "common": COMMON_ROWS,
    "identify": IDENTIFY_ROWS,
    "analysis_region_detail": ANALYSIS_DETAIL_ROWS,
    "continuum": CONTINUUM_ROWS,
}

# Shared operation ids sourced into this module's rows, in declaration order.
# Exposed for cross-consumer regression tests (see tests/gui/shell).
SHARED_OPERATION_IDS_IN_USE: tuple[str, ...] = tuple(_shared_op_ids)


def render_keyboard_operations_table(scope: str) -> str:
    """Render keyboard/mouse operations table for given scope.

    Args:
        scope: The semantic destination name (common, identify,
            analysis_region_detail, continuum).

    Returns:
        Markdown table string, or empty string if scope has no operations.
    """
    rows = _SCOPE_ROWS.get(scope.lower())
    if not rows:
        return ""

    heading = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Keyboard & Mouse Operations")
    ).strip()
    header = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "| Operation | Description |")
    )
    divider = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "|------|------|")
    )

    translated_rows = [row() for row in rows]

    lines = [f"## {heading}", "", header, divider, *translated_rows]
    return "\n".join(lines)
