"""Tests for the developer environment-variable tutorial start override."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtWidgets import QWidget

from chappy.core.editing_mode import EditingMode
from chappy.gui.common.shared_operations import AnalysisOperationPanel, AnalysisOperationSurface
from chappy.gui.common.tutorial import TutorialChapter, TutorialPrerequisite
from chappy.gui.dialogs.welcome_dialog import WelcomeDialog
from chappy.gui.shell import main_window as main_window_module
from chappy.gui.shell.main_window import MainWindow
from chappy.gui.shell.tutorial_chapters import (
    build_advanced_walkthrough_chapters,
    build_essential_walkthrough_chapters,
)
from chappy.gui.shell.tutorial_start_override import (
    START_CHAPTER_ENV,
    WALKTHROUGH_ENV,
    resolve_tutorial_start_chapters,
)
from chappy.gui.shell.tutorial_tour_controller import TutorialTourController


@pytest.fixture(autouse=True)
def _clear_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(WALKTHROUGH_ENV, raising=False)
    monkeypatch.delenv(START_CHAPTER_ENV, raising=False)


def _set_override(monkeypatch: pytest.MonkeyPatch, walkthrough: str, chapter_id: str) -> None:
    monkeypatch.setenv(WALKTHROUGH_ENV, walkthrough)
    monkeypatch.setenv(START_CHAPTER_ENV, chapter_id)


def _controller(host: QWidget, chapters: tuple[TutorialChapter, ...]) -> TutorialTourController:
    def switch_surface(_surface: AnalysisOperationSurface) -> bool:
        return True

    def switch_panel(_panel: AnalysisOperationPanel) -> bool:
        return True

    def switch_mode(_mode: EditingMode) -> None:
        return

    return TutorialTourController(
        host,
        chapters=chapters,
        switch_mode=switch_mode,
        switch_analysis_surface=switch_surface,
        switch_analysis_panel=switch_panel,
        prerequisite_checks={TutorialPrerequisite.HAS_TUTORIAL_MULTI_ION_REGION: lambda: False},
    )


def test_unset_environment_keeps_the_welcome_dialog_flow() -> None:
    assert resolve_tutorial_start_chapters() is None


def test_advanced_walkthrough_is_cut_to_the_requested_chapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_override(monkeypatch, "advanced", "joint_fit")
    full = build_advanced_walkthrough_chapters()
    full_ids = [chapter.chapter_id for chapter in full]

    chapters = resolve_tutorial_start_chapters()

    assert chapters is not None
    assert chapters == full[full_ids.index("joint_fit") :]
    assert [chapter.chapter_id for chapter in chapters] == ["joint_fit", "continuum", "save"]


def test_essential_walkthrough_is_cut_to_the_requested_chapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_ids = [chapter.chapter_id for chapter in build_essential_walkthrough_chapters()]
    _set_override(monkeypatch, "essential", full_ids[-2])

    chapters = resolve_tutorial_start_chapters()

    assert chapters is not None
    assert [chapter.chapter_id for chapter in chapters] == full_ids[-2:]


def test_walkthrough_name_ignores_case_and_surrounding_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_override(monkeypatch, "  Advanced  ", " joint_fit ")

    chapters = resolve_tutorial_start_chapters()

    assert chapters is not None
    assert chapters[0].chapter_id == "joint_fit"


def test_unknown_walkthrough_name_falls_back_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _set_override(monkeypatch, "expert", "joint_fit")

    with caplog.at_level(logging.WARNING):
        assert resolve_tutorial_start_chapters() is None

    assert "unknown CHAPPY_TUTORIAL_WALKTHROUGH value 'expert'" in caplog.text


def test_unknown_chapter_id_falls_back_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _set_override(monkeypatch, "advanced", "nowhere")

    with caplog.at_level(logging.WARNING):
        assert resolve_tutorial_start_chapters() is None

    assert "unknown CHAPPY_TUTORIAL_START_CHAPTER value 'nowhere'" in caplog.text
    assert "joint_fit" in caplog.text


def test_chapter_of_another_walkthrough_falls_back_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _set_override(monkeypatch, "essential", "joint_fit")

    with caplog.at_level(logging.WARNING):
        assert resolve_tutorial_start_chapters() is None

    assert "unknown CHAPPY_TUTORIAL_START_CHAPTER value 'joint_fit'" in caplog.text


@pytest.mark.parametrize(
    ("walkthrough", "chapter_id"), [("advanced", ""), ("", "joint_fit"), ("advanced", "   ")]
)
def test_half_configured_override_falls_back_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    walkthrough: str,
    chapter_id: str,
) -> None:
    _set_override(monkeypatch, walkthrough, chapter_id)

    with caplog.at_level(logging.WARNING):
        assert resolve_tutorial_start_chapters() is None

    assert "must both be set" in caplog.text


def test_override_chapters_soft_block_on_an_unmet_prerequisite(
    monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:
    _set_override(monkeypatch, "advanced", "joint_fit")
    chapters = resolve_tutorial_start_chapters()
    assert chapters is not None
    host = QWidget()
    qtbot.addWidget(host)
    controller = _controller(host, chapters)

    controller.start()

    assert controller._awaiting_prerequisite
    assert controller._bubble is not None
    assert controller._bubble._warning_source is not None

    controller._bubble.next_requested.emit()

    assert not controller._awaiting_prerequisite
    assert controller._current_chapter().chapter_id == "joint_fit"
    assert controller._step_index == 0
    assert controller._bubble._warning_source is None
    assert controller._bubble._action_label.text() == controller._bubble._translated_text(
        chapters[0].steps[0].action_source
    )
    controller.stop()


class _TutorialStartSpy:
    def __init__(self) -> None:
        self.started: list[tuple[TutorialChapter, ...]] = []

    def _start_tutorial_walkthrough(self, chapters: tuple[TutorialChapter, ...]) -> None:
        self.started.append(chapters)


class _DismissingWelcomeDialog:
    Choice = WelcomeDialog.Choice
    instances = 0

    def __init__(self, _parent: object, *, sample_available: bool) -> None:
        type(self).instances += 1
        self.sample_available = sample_available
        self.choice = WelcomeDialog.Choice.DISMISS

    def exec(self) -> int:
        return 0


def test_help_tutorial_starts_the_override_without_showing_the_welcome_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_override(monkeypatch, "advanced", "joint_fit")
    _DismissingWelcomeDialog.instances = 0
    monkeypatch.setattr(main_window_module, "WelcomeDialog", _DismissingWelcomeDialog)
    spy = _TutorialStartSpy()

    MainWindow.show_welcome_dialog(spy)  # type: ignore[arg-type]

    assert _DismissingWelcomeDialog.instances == 0
    assert [chapter.chapter_id for chapter in spy.started[0]] == ["joint_fit", "continuum", "save"]


def test_unset_environment_still_shows_the_welcome_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    _DismissingWelcomeDialog.instances = 0
    monkeypatch.setattr(main_window_module, "WelcomeDialog", _DismissingWelcomeDialog)
    spy = _TutorialStartSpy()

    MainWindow.show_welcome_dialog(spy)  # type: ignore[arg-type]

    assert _DismissingWelcomeDialog.instances == 1
    assert spy.started == []
