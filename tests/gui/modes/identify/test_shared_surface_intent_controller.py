"""Tests for identify shared-spectrum velocity routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from chappy.gui.modes.identify.shared_surface_intent_controller import (
    IdentifySharedSurfaceIntentController,
)
from chappy.gui.protocols.context_menu import ContextMenuTriggerAction
from chappy.gui.protocols.intent_types import ShowContextMenuIntent, ToggleVelocityPlotIntent


@dataclass
class _Workflow:
    """Minimal workflow exposing typed identify preview state."""

    preview_lock: bool = False
    baseline_line: bool = True
    cleared_previews: int = 0
    manual_temporary_lines: list[tuple[float, int, str]] = field(default_factory=list)

    def handle_manual_temporary_line(
        self, *, observed_wavelength: float, modifiers: int, source: str
    ) -> None:
        self.manual_temporary_lines.append((observed_wavelength, modifiers, source))

    def set_preview_always_on(self, enabled: bool) -> None:
        self.preview_lock = enabled

    def preview_always_on(self) -> bool:
        return self.preview_lock

    def baseline_line_selected(self) -> bool:
        return self.baseline_line

    def clear_cursor_preview(self) -> None:
        self.cleared_previews += 1


def _controller(
    workflow: _Workflow, cursor_wavelength: float | None
) -> tuple[IdentifySharedSurfaceIntentController, list[float | None]]:
    toggles: list[float | None] = []
    controller = IdentifySharedSurfaceIntentController(
        workflow_provider=lambda: workflow,
        velocity_toggle_callback=toggles.append,
        cursor_wavelength_provider=lambda: cursor_wavelength,
    )
    return controller, toggles


def test_velocity_shortcut_uses_exact_cursor_wavelength() -> None:
    """The shortcut opens velocity at the exact wavelength under the cursor."""
    workflow = _Workflow()
    controller, toggles = _controller(workflow, 4527.125)

    controller.handle_mode_velocity_shortcut()

    assert toggles == [4527.125]
    assert workflow.cleared_previews == 1


def test_velocity_shortcut_without_shift_preview_still_toggles() -> None:
    """The shortcut no longer depends on an active Shift preview."""
    workflow = _Workflow()
    controller, toggles = _controller(workflow, 4100.5)

    controller.handle_mode_velocity_shortcut()

    assert toggles == [4100.5]
    assert workflow.cleared_previews == 1


def test_preview_lock_does_not_block_velocity_shortcut() -> None:
    """A forced preview lock does not change how the shortcut resolves its wavelength."""
    workflow = _Workflow(preview_lock=True)
    controller, toggles = _controller(workflow, 4300.25)

    controller.handle_mode_velocity_shortcut()

    assert toggles == [4300.25]
    assert workflow.cleared_previews == 1


def test_velocity_shortcut_off_axis_cursor_forwards_none() -> None:
    """A cursor outside the wavelength axis still reaches the velocity toggle."""
    workflow = _Workflow()
    controller, toggles = _controller(workflow, None)

    controller.handle_mode_velocity_shortcut()

    assert toggles == [None]
    assert workflow.cleared_previews == 1


def test_context_menu_velocity_action_uses_the_right_clicked_wavelength() -> None:
    """The context-menu entry centres velocity on the right-clicked wavelength."""
    workflow = _Workflow()
    controller, _ = _controller(workflow, 4100.0)

    actions = controller.context_menu_actions(
        ShowContextMenuIntent(wavelength=4931.75, flux=0.4, global_x=10, global_y=20)
    )

    velocity_action = actions[1]

    assert isinstance(velocity_action, ContextMenuTriggerAction)
    assert isinstance(velocity_action.intent, ToggleVelocityPlotIntent)
    assert velocity_action.intent.wavelength == 4931.75


def test_context_menu_velocity_action_disabled_without_baseline_line() -> None:
    """A preset without a baseline line disables the context-menu entry."""
    workflow = _Workflow(baseline_line=False)
    controller, _ = _controller(workflow, 4100.0)

    actions = controller.context_menu_actions(
        ShowContextMenuIntent(wavelength=4931.75, flux=0.4, global_x=10, global_y=20)
    )

    velocity_action = actions[1]

    assert isinstance(velocity_action, ContextMenuTriggerAction)
    assert velocity_action.enabled is False
    assert velocity_action.intent is None
    assert velocity_action.tooltip is not None


def test_context_menu_velocity_intent_toggles_at_that_wavelength() -> None:
    """Triggering the context-menu intent forwards its wavelength to the toggle."""
    workflow = _Workflow()
    controller, toggles = _controller(workflow, None)

    controller.handle_context_menu_intent(ToggleVelocityPlotIntent(wavelength=4931.75))

    assert toggles == [4931.75]
    assert workflow.cleared_previews == 1
