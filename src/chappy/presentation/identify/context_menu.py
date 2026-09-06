"""Qt-free identify context menu presentation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IdentifyContextMenuActionKind(StrEnum):
    """Identify context menu action kind."""

    TOGGLE_PREVIEW_LOCK = "toggle-preview-lock"
    TOGGLE_VELOCITY_PLOT = "toggle-velocity-plot"


@dataclass(frozen=True, slots=True)
class IdentifyContextMenuMessages:
    """Labels used by identify context menu actions."""

    always_show_candidate_overlay: str
    show_velocity_plot: str
    baseline_required: str


@dataclass(frozen=True, slots=True)
class IdentifyContextMenuState:
    """State required to build identify context menu actions."""

    preview_lock_enabled: bool
    preview_lock_available: bool
    baseline_line_selected: bool


@dataclass(frozen=True, slots=True)
class IdentifyContextMenuAction:
    """Qt-free identify context menu action descriptor."""

    label: str
    kind: IdentifyContextMenuActionKind
    enabled: bool = True
    checkable: bool = False
    checked: bool = False
    preview_lock_enabled: bool | None = None
    tooltip: str | None = None


def build_identify_context_menu_actions(
    *, state: IdentifyContextMenuState, messages: IdentifyContextMenuMessages
) -> tuple[IdentifyContextMenuAction, ...]:
    """Build identify context menu action descriptors.

    Args:
        state: Identify context menu state.
        messages: Labels for actions.

    Returns:
        Context menu action descriptors.
    """
    return (
        IdentifyContextMenuAction(
            label=messages.always_show_candidate_overlay,
            kind=IdentifyContextMenuActionKind.TOGGLE_PREVIEW_LOCK,
            enabled=state.preview_lock_available,
            checkable=True,
            checked=state.preview_lock_enabled,
            preview_lock_enabled=not state.preview_lock_enabled,
        ),
        IdentifyContextMenuAction(
            label=messages.show_velocity_plot,
            kind=IdentifyContextMenuActionKind.TOGGLE_VELOCITY_PLOT,
            enabled=state.baseline_line_selected,
            tooltip=None if state.baseline_line_selected else messages.baseline_required,
        ),
    )
