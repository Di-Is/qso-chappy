"""Tests for identify context menu controller."""

from __future__ import annotations

from chappy.gui.modes.identify import IdentifyContextMenuController, IdentifyContextMenuRequest
from chappy.gui.protocols.context_menu import ContextMenuToggleAction, ContextMenuTriggerAction
from chappy.gui.protocols.intent_types import (
    ToggleIdentifyPreviewLockIntent,
    ToggleVelocityPlotIntent,
)


def test_actions_for_request_builds_preview_lock_toggle_intents() -> None:
    """The preview lock menu action should expose checked and unchecked intents."""
    controller = IdentifyContextMenuController()

    actions = controller.actions_for_request(
        IdentifyContextMenuRequest(
            wavelength=4929.0,
            preview_lock_enabled=True,
            preview_lock_available=True,
            baseline_line_selected=True,
        )
    )

    preview_action = actions[0]

    assert isinstance(preview_action, ContextMenuToggleAction)
    assert preview_action.label == "Always show candidate overlay"
    assert preview_action.checked is True
    assert isinstance(preview_action.intent_when_checked, ToggleIdentifyPreviewLockIntent)
    assert isinstance(preview_action.intent_when_unchecked, ToggleIdentifyPreviewLockIntent)
    assert preview_action.intent_when_checked.enabled is True
    assert preview_action.intent_when_unchecked.enabled is False


def test_actions_for_request_targets_the_right_clicked_wavelength() -> None:
    """The velocity plot action centres on the wavelength under the context menu."""
    controller = IdentifyContextMenuController()

    actions = controller.actions_for_request(
        IdentifyContextMenuRequest(
            wavelength=4929.5,
            preview_lock_enabled=False,
            preview_lock_available=True,
            baseline_line_selected=True,
        )
    )

    velocity_action = actions[1]

    assert isinstance(velocity_action, ContextMenuTriggerAction)
    assert velocity_action.label == "Show Velocity Plot (V)"
    assert velocity_action.enabled is True
    assert velocity_action.tooltip is None
    assert isinstance(velocity_action.intent, ToggleVelocityPlotIntent)
    assert velocity_action.intent.wavelength == 4929.5


def test_actions_for_request_disables_velocity_plot_without_baseline_line() -> None:
    """Without a baseline line the velocity plot action carries no intent."""
    controller = IdentifyContextMenuController()

    actions = controller.actions_for_request(
        IdentifyContextMenuRequest(
            wavelength=4929.5,
            preview_lock_enabled=False,
            preview_lock_available=True,
            baseline_line_selected=False,
        )
    )

    velocity_action = actions[1]

    assert isinstance(velocity_action, ContextMenuTriggerAction)
    assert velocity_action.enabled is False
    assert velocity_action.intent is None
    assert velocity_action.tooltip == "Select a baseline line before opening the velocity plot."
