"""Operation identifiers for history events.

This module defines the OperationId enum used to identify different types
of undoable operations in the application. The naming follows the HIS.01.02.G02
convention: namespace.action format.

Namespaces:
    - ident: Identify mode operations
    - structure: Analysis Structure operations
    - mask: Wavelength-mask operations
    - cont: Continuum mode operations
    - model: Model editing operations
    - draw: Display range operations
"""

from __future__ import annotations

from enum import StrEnum


class OperationId(StrEnum):
    """Operation identifier for history events.

    Naming convention (HIS.01.02.G02):
        namespace.action

    The qualifier (e.g., "nav", "manual") is stored separately in HistoryEvent
    to form the full operation ID: namespace.action[.qualifier]
    """

    # Identify mode operations (ident.*)
    IDENT_ADD_TEMPORARY_LINE = "ident.add_temporary_line"
    IDENT_REMOVE_TEMPORARY_LINE = "ident.remove_temporary_line"
    IDENT_CLEAR_TEMPORARY_LINES = "ident.clear_temporary_lines"
    IDENT_REGISTER_SELECTED = "ident.register_selected"

    # Analysis Structure operations (structure.*)
    STRUCTURE_MOVE_LINKED_LINES = "structure.move_linked_lines"
    STRUCTURE_SPLIT = "structure.split"
    STRUCTURE_MERGE = "structure.merge"
    STRUCTURE_DELETE = "structure.delete"
    STRUCTURE_UNLINK_LINKED_LINES = "structure.unlink_linked_lines"

    # Mask operations (mask.*)
    MASK_CREATE = "mask.create"
    MASK_DELETE = "mask.delete"
    MASK_EDIT = "mask.edit"

    # Continuum mode operations (cont.*)
    CONT_ADD_COMPONENT = "cont.add_component"
    CONT_ADD_POINT = "cont.add_point"
    CONT_DELETE_POINT = "cont.delete_point"
    CONT_MOVE_POINT = "cont.move_point"
    CONT_RESET = "cont.reset"

    # Model operations (model.*)
    MODEL_ADD = "model.add"
    MODEL_DELETE = "model.delete"
    MODEL_BULK_ADD = "model.bulk_add"
    MODEL_BULK_DELETE = "model.bulk_delete"
    MODEL_EDIT_PARAMS = "model.edit_params"
    MODEL_EDIT_RESOLUTION = "model.edit_resolution"
    MODEL_EDIT_LINE_ANALYSIS_HALF_WIDTH = "model.edit_line_analysis_half_width"
    MODEL_BULK_ADD_MULTIPLET = "model.bulk_add_multiplet"
    MODEL_BULK_DELETE_MULTIPLET = "model.bulk_delete_multiplet"
    MODEL_OPTIMIZE_APPLY = "model.optimize_apply"
    MODEL_TIE_SET_CREATE = "model.tie_set_create"
    MODEL_TIE_SET_REMOVE = "model.tie_set_remove"
    MODEL_TIE_SET_DISSOLVE = "model.tie_set_dissolve"

    # Display range operations (draw.*)
    DRAW_RANGE_CHANGE = "draw.range_change"
