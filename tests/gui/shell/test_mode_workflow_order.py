"""Regression tests for the single-sourced mode workflow order.

D3 of docs/adr/mode-naming-and-ordering.md requires
``core.editing_mode.MODE_WORKFLOW_ORDER`` to be the sole source of the
Identify -> Analysis -> Continuum ordering. These tests guard the
consumers that were previously hardcoded independently and drifted apart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtWidgets import QPushButton

from chappy.core.editing_mode import MODE_WORKFLOW_ORDER, EditingMode
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.actions.registry import ActionRegistry
from chappy.gui.shell.mode_context_bar import ModeContextBar
from chappy.gui.shell.shortcuts import SHORTCUTS
from chappy.gui.shell.tutorial_chapters import (
    build_advanced_walkthrough_chapters,
    build_essential_walkthrough_chapters,
)
from tests.helpers.tutorial_chapters import all_walkthrough_chapters

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.common.tutorial import TutorialChapter

_MODE_ACTION_BY_MODE: dict[EditingMode, ShellActionId] = {
    EditingMode.IDENTIFY: ShellActionId.IDENTIFY_MODE,
    EditingMode.ANALYSIS: ShellActionId.ANALYSIS_MODE,
    EditingMode.CONTINUUM: ShellActionId.CONTINUUM_MODE,
}
_MODE_ACTION_NAMES: dict[ShellActionId, str] = {
    ShellActionId.IDENTIFY_MODE: "IDENTIFY",
    ShellActionId.ANALYSIS_MODE: "ANALYSIS",
    ShellActionId.CONTINUUM_MODE: "CONTINUUM",
}


def test_mode_workflow_order_excludes_start_and_covers_switchable_modes() -> None:
    assert EditingMode.START not in MODE_WORKFLOW_ORDER
    assert set(MODE_WORKFLOW_ORDER) == {
        EditingMode.IDENTIFY,
        EditingMode.ANALYSIS,
        EditingMode.CONTINUUM,
    }


def test_context_bar_mode_buttons_follow_workflow_order(qtbot) -> None:
    bar = ModeContextBar()
    qtbot.addWidget(bar)

    buttons = [
        button
        for button in bar.findChildren(QPushButton)
        if button.objectName().startswith("modeButton_")
    ]
    button_order = [button.objectName() for button in buttons]

    expected_order = [
        f"modeButton_{_MODE_ACTION_NAMES[_MODE_ACTION_BY_MODE[mode]]}"
        for mode in MODE_WORKFLOW_ORDER
    ]
    assert button_order == expected_order


def test_mode_menu_follows_workflow_order() -> None:
    registry = ActionRegistry.default()
    mode_menu = next(menu for menu in registry.menus if menu.name == "mode")

    expected_order = tuple(_MODE_ACTION_BY_MODE[mode] for mode in MODE_WORKFLOW_ORDER)
    assert mode_menu.entries == expected_order


def test_walkthrough_chapters_follow_workflow_order() -> None:
    mode_values = {mode.value for mode in MODE_WORKFLOW_ORDER}
    chapter_ids = [
        chapter.chapter_id
        for chapter in all_walkthrough_chapters()
        if chapter.chapter_id in mode_values
    ]

    assert chapter_ids == [mode.value for mode in MODE_WORKFLOW_ORDER]


@pytest.mark.parametrize(
    "build_chapters", [build_essential_walkthrough_chapters, build_advanced_walkthrough_chapters]
)
def test_walkthrough_destinations_follow_workflow_order(
    build_chapters: Callable[[], tuple[TutorialChapter, ...]],
) -> None:
    modes = list(
        dict.fromkeys(
            chapter.destination.mode
            for chapter in build_chapters()
            if chapter.destination.mode is not None
        )
    )

    assert modes == [mode for mode in MODE_WORKFLOW_ORDER if mode in modes]


def test_mode_switch_shortcuts_are_numbered_by_workflow_order() -> None:
    expected_numbers = {
        _MODE_ACTION_BY_MODE[mode]: index + 1 for index, mode in enumerate(MODE_WORKFLOW_ORDER)
    }

    for action_id, number in expected_numbers.items():
        shortcut = SHORTCUTS[action_id]
        assert shortcut.win == f"Ctrl+{number}"
        assert shortcut.mac == f"Cmd+{number}"
