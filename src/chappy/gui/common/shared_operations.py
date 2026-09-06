"""Single source of truth for operations described in both the tutorial and the manual.

Each :class:`SharedOperation` captures the facts of one interaction (target
widget, action, and expected result) that are otherwise hand-written twice:
once as tutorial guidance (``gui.shell.tutorial_chapters``) and once as a
user-manual operation-table row
(``chappy_user_manual_generator.data.keyboard_operations`` /
``.data.analysis_structure_operations``). English source text is registered with
``QT_TRANSLATE_NOOP("SharedOperations", ...)`` so it is extracted into the
main Qt catalog (``chappy_ja.ts``) alongside tutorial and menu strings; the
manual generator reads the same catalog through its chappy-catalog
passthrough (see ``chappy_user_manual_generator.translations``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy.core.editing_mode import EditingMode

SHARED_OPERATIONS_TR_CONTEXT = "SharedOperations"


class AnalysisOperationSurface(StrEnum):
    """Analysis workspace surfaces used by shared-operation availability."""

    OVERVIEW = "overview"
    REGION_DETAIL = "region_detail"


class AnalysisOperationPanel(StrEnum):
    """Nested Analysis panels that further restrict operation availability."""

    SUMMARY = "summary"
    STRUCTURE = "structure"
    DETAIL = "detail"


@dataclass(frozen=True, slots=True)
class OperationScope:
    """Semantic destination where a shared operation is available.

    An empty scope is global. Analysis surface and panel values are deliberately
    represented without importing a concrete Analysis widget or coordinator so
    this common registry remains independent from mode packages.
    """

    mode: EditingMode | None = None
    analysis_surface: AnalysisOperationSurface | None = None
    analysis_panel: AnalysisOperationPanel | None = None

    def __post_init__(self) -> None:
        """Reject incomplete or contradictory Analysis destinations."""
        has_analysis_destination = (
            self.analysis_surface is not None or self.analysis_panel is not None
        )
        if has_analysis_destination and self.mode is not EditingMode.ANALYSIS:
            msg = "Analysis operation destinations require EditingMode.ANALYSIS."
            raise ValueError(msg)
        if self.analysis_panel is not None and self.analysis_surface is None:
            msg = "An Analysis operation panel requires an Analysis surface."
            raise ValueError(msg)
        if self.analysis_panel is None:
            return

        expected_surface = {
            AnalysisOperationPanel.SUMMARY: AnalysisOperationSurface.OVERVIEW,
            AnalysisOperationPanel.STRUCTURE: AnalysisOperationSurface.OVERVIEW,
            AnalysisOperationPanel.DETAIL: AnalysisOperationSurface.REGION_DETAIL,
        }[self.analysis_panel]
        if self.analysis_surface is not expected_surface:
            msg = (
                f"Analysis panel {self.analysis_panel.value!r} requires "
                f"surface {expected_surface.value!r}."
            )
            raise ValueError(msg)

    @classmethod
    def global_scope(cls) -> OperationScope:
        """Return the mode-independent global operation scope."""
        return cls()


@dataclass(frozen=True, slots=True)
class SharedOperation:
    """One operation shared between the tutorial and the manual operation tables.

    Attributes:
        op_id: Stable identifier used to look up this operation.
        scope: Exact semantic destination for the operation, or the global
            scope when it applies everywhere.
        target_object_name: ``objectName`` of the widget the operation acts
            on or through, or None when there is no single target widget.
        action_source: Untranslated text describing the action (for example
            ``"Shift+Click"``).
        expected_source: Untranslated text describing the expected result.
        note_source: Optional untranslated supplementary note.
    """

    op_id: str
    scope: OperationScope
    target_object_name: str | None
    action_source: str
    expected_source: str
    note_source: str | None = None


SHARED_OPERATIONS: tuple[SharedOperation, ...] = (
    SharedOperation(
        op_id="zoom_rect",
        scope=OperationScope.global_scope(),
        target_object_name="modeContextBar_zoom_rect",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "[Zoom] button + drag")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Rectangle zoom")),
    ),
    SharedOperation(
        op_id="wheel_zoom_pan",
        scope=OperationScope.global_scope(),
        target_object_name="spectrumPlotContainer",
        action_source=str(
            QT_TRANSLATE_NOOP(
                "SharedOperations",
                "Zoom with the mouse wheel or the Up/Down arrow keys:"
                " the view scales around the cursor. Pan left and right"
                " with a horizontal scroll or the Left/Right arrow keys.",
            )
        ),
        expected_source=str(
            QT_TRANSLATE_NOOP(
                "SharedOperations",
                "The visible range zooms around the cursor position and"
                " shifts sideways as you pan.",
            )
        ),
    ),
    SharedOperation(
        op_id="continuum_add_point",
        scope=OperationScope(mode=EditingMode.CONTINUUM),
        target_object_name="spectrumPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Double-click")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Add continuum control point")),
    ),
    SharedOperation(
        op_id="continuum_move_point",
        scope=OperationScope(mode=EditingMode.CONTINUUM),
        target_object_name="spectrumPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Drag")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Move continuum control point")),
    ),
    SharedOperation(
        op_id="identify_shift_click",
        scope=OperationScope(mode=EditingMode.IDENTIFY),
        target_object_name="spectrumPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Shift+Click")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Add line")),
    ),
    SharedOperation(
        op_id="identify_toggle_velocity",
        scope=OperationScope(mode=EditingMode.IDENTIFY),
        target_object_name="spectrumPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "V")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Toggle velocity plot")),
    ),
    SharedOperation(
        op_id="optimize_shift_click",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.REGION_DETAIL,
            analysis_panel=AnalysisOperationPanel.DETAIL,
        ),
        target_object_name="spectrumPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Shift+Click")),
        expected_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Add component (when line selected)")
        ),
    ),
    SharedOperation(
        op_id="optimize_velocity_shift_click",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.REGION_DETAIL,
            analysis_panel=AnalysisOperationPanel.DETAIL,
        ),
        target_object_name="velocityPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Shift+Click")),
        expected_source=str(
            QT_TRANSLATE_NOOP(
                "SharedOperations",
                "Add component at velocity position (no line selection required)",
            )
        ),
    ),
    SharedOperation(
        op_id="optimize_drag_center",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.REGION_DETAIL,
            analysis_panel=AnalysisOperationPanel.DETAIL,
        ),
        target_object_name="spectrumPlotContainer",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Drag")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Adjust component center (z)")),
    ),
    SharedOperation(
        op_id="analysis_fit",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.REGION_DETAIL,
            analysis_panel=AnalysisOperationPanel.DETAIL,
        ),
        target_object_name=None,
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "F5")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Run fit")),
    ),
    SharedOperation(
        op_id="analysis_toggle_velocity",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.REGION_DETAIL,
            analysis_panel=AnalysisOperationPanel.DETAIL,
        ),
        target_object_name=None,
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "V")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Toggle velocity plot")),
    ),
    SharedOperation(
        op_id="analysis_toggle_component_profiles",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.REGION_DETAIL,
            analysis_panel=AnalysisOperationPanel.DETAIL,
        ),
        target_object_name=None,
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "M")),
        expected_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Toggle component profiles")),
    ),
    SharedOperation(
        op_id="analysis_structure_move",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.OVERVIEW,
            analysis_panel=AnalysisOperationPanel.STRUCTURE,
        ),
        target_object_name="analysisStructureTree",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Move absorption lines")),
        expected_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Drag and drop lines onto the target region")
        ),
        note_source=str(
            QT_TRANSLATE_NOOP(
                "SharedOperations", "The drop target highlights, and multi-select moves together."
            )
        ),
    ),
    SharedOperation(
        op_id="analysis_structure_split",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.OVERVIEW,
            analysis_panel=AnalysisOperationPanel.STRUCTURE,
        ),
        target_object_name="analysisStructureTree",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Split lines into a new region")),
        expected_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Use Split for the selected lines")
        ),
        note_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Creates a dedicated region immediately.")
        ),
    ),
    SharedOperation(
        op_id="analysis_structure_merge",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.OVERVIEW,
            analysis_panel=AnalysisOperationPanel.STRUCTURE,
        ),
        target_object_name="analysisStructureTree",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Merge absorption regions")),
        expected_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Select multiple regions, then use Merge")
        ),
        note_source=str(
            QT_TRANSLATE_NOOP(
                "SharedOperations", "Review the resulting region name and contents afterwards."
            )
        ),
    ),
    SharedOperation(
        op_id="analysis_structure_unlink",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.OVERVIEW,
            analysis_panel=AnalysisOperationPanel.STRUCTURE,
        ),
        target_object_name="analysisStructureTree",
        action_source=str(QT_TRANSLATE_NOOP("SharedOperations", "Unlink linked lines")),
        expected_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Select the linked line, then use Unlink")
        ),
        note_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Only the selected scientific link is removed.")
        ),
    ),
    SharedOperation(
        op_id="analysis_structure_delete",
        scope=OperationScope(
            mode=EditingMode.ANALYSIS,
            analysis_surface=AnalysisOperationSurface.OVERVIEW,
            analysis_panel=AnalysisOperationPanel.STRUCTURE,
        ),
        target_object_name="analysisStructureTree",
        action_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Delete absorption regions or lines")
        ),
        expected_source=str(
            QT_TRANSLATE_NOOP("SharedOperations", "Select the items, then use Delete")
        ),
        note_source=str(
            QT_TRANSLATE_NOOP(
                "SharedOperations", "Review the impact confirmation before deleting."
            )
        ),
    ),
)

_BY_OP_ID: dict[str, SharedOperation] = {
    operation.op_id: operation for operation in SHARED_OPERATIONS
}


def get_shared_operation(op_id: str) -> SharedOperation:
    """Return the shared operation registered under ``op_id``.

    Args:
        op_id: Stable identifier of the operation.

    Returns:
        The matching shared operation.

    Raises:
        KeyError: When no operation is registered under ``op_id``.
    """
    return _BY_OP_ID[op_id]


def shared_operations_for_scope(scope: OperationScope) -> tuple[SharedOperation, ...]:
    """Return global operations followed by operations for one exact scope.

    Args:
        scope: Exact semantic destination being rendered or queried.

    Returns:
        Global operations and operations whose scope exactly matches ``scope``.
    """
    global_scope = OperationScope.global_scope()
    return tuple(
        operation for operation in SHARED_OPERATIONS if operation.scope in {global_scope, scope}
    )


__all__ = [
    "SHARED_OPERATIONS",
    "SHARED_OPERATIONS_TR_CONTEXT",
    "AnalysisOperationPanel",
    "AnalysisOperationSurface",
    "OperationScope",
    "SharedOperation",
    "get_shared_operation",
    "shared_operations_for_scope",
]
