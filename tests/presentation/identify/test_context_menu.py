"""Tests for identify context menu presentation helpers."""

from __future__ import annotations

from chappy.presentation.identify import (
    IdentifyContextMenuActionKind,
    IdentifyContextMenuMessages,
    IdentifyContextMenuState,
    build_identify_context_menu_actions,
)

_MESSAGES = IdentifyContextMenuMessages(
    always_show_candidate_overlay="Always show candidate overlay",
    show_velocity_plot="Show Velocity Plot (V)",
    baseline_required="Select a baseline line before opening the velocity plot.",
)


def test_build_identify_context_menu_actions_disables_unavailable_preview_lock() -> None:
    """The preview lock descriptor should expose availability and checked state."""
    actions = build_identify_context_menu_actions(
        state=IdentifyContextMenuState(
            preview_lock_enabled=False, preview_lock_available=False, baseline_line_selected=True
        ),
        messages=_MESSAGES,
    )

    preview_action = actions[0]

    assert preview_action.kind is IdentifyContextMenuActionKind.TOGGLE_PREVIEW_LOCK
    assert preview_action.label == "Always show candidate overlay"
    assert preview_action.checkable is True
    assert preview_action.enabled is False
    assert preview_action.checked is False


def test_build_identify_context_menu_actions_enables_velocity_plot_with_baseline() -> None:
    """The velocity plot descriptor should be enabled once a baseline line exists."""
    actions = build_identify_context_menu_actions(
        state=IdentifyContextMenuState(
            preview_lock_enabled=False, preview_lock_available=True, baseline_line_selected=True
        ),
        messages=_MESSAGES,
    )

    velocity_action = actions[1]

    assert velocity_action.kind is IdentifyContextMenuActionKind.TOGGLE_VELOCITY_PLOT
    assert velocity_action.label == "Show Velocity Plot (V)"
    assert velocity_action.checkable is False
    assert velocity_action.enabled is True
    assert velocity_action.tooltip is None


def test_build_identify_context_menu_actions_explains_missing_baseline_line() -> None:
    """Without a baseline line the velocity plot entry is disabled with a reason."""
    actions = build_identify_context_menu_actions(
        state=IdentifyContextMenuState(
            preview_lock_enabled=False, preview_lock_available=True, baseline_line_selected=False
        ),
        messages=_MESSAGES,
    )

    velocity_action = actions[1]

    assert velocity_action.enabled is False
    assert velocity_action.tooltip == "Select a baseline line before opening the velocity plot."
