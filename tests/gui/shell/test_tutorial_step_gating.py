"""Tests for tutorial step-gating: REQUIRED completion conditions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from chappy.core.editing_mode import EditingMode
from chappy.gui.common.tutorial import (
    AdvanceTrigger,
    TutorialBubble,
    TutorialChapter,
    TutorialCompletion,
    TutorialDestination,
    TutorialPrerequisite,
    TutorialStep,
)
from chappy.gui.shell.tutorial_tour_controller import TutorialTourController

if TYPE_CHECKING:
    from collections.abc import Callable


def _step(
    *,
    requires: TutorialCompletion | None = None,
    advance: AdvanceTrigger = AdvanceTrigger.NEXT_BUTTON,
) -> TutorialStep:
    return TutorialStep(
        targets=(),
        action_source="Action",
        expected_source="Result",
        advance=advance,
        requires=requires,
    )


def _chapter(
    chapter_id: str,
    *,
    steps: tuple[TutorialStep, ...],
    prerequisite: TutorialPrerequisite | None = None,
) -> TutorialChapter:
    return TutorialChapter(
        chapter_id=chapter_id,
        title_source=chapter_id,
        destination=TutorialDestination(mode=EditingMode.IDENTIFY),
        steps=steps,
        prerequisite=prerequisite,
    )


def _controller(
    host: QWidget,
    chapters: tuple[TutorialChapter, ...],
    *,
    completion_checks: dict[TutorialCompletion, Callable[[], bool]] | None = None,
    completion_notes: dict[TutorialCompletion, Callable[[], str | None]] | None = None,
    prerequisite_checks: dict[TutorialPrerequisite, Callable[[], bool]] | None = None,
) -> TutorialTourController:
    return TutorialTourController(
        host,
        chapters=chapters,
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
        prerequisite_checks=prerequisite_checks,
        completion_checks=completion_checks,
        completion_notes=completion_notes,
    )


def test_gated_step_keeps_next_disabled_while_unmet(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: False},
    )

    controller.start()

    assert controller._bubble is not None
    assert not controller._bubble._next_button.isEnabled()
    controller._bubble._next_button.click()
    assert controller._step_index == 0


def test_unmet_gate_blocks_a_next_request_raised_outside_the_button(qtbot) -> None:
    """The gate lives in the controller, not only in the button's enabled state."""
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: False},
    )

    controller.start()
    assert controller._bubble is not None
    controller._bubble.next_requested.emit()

    assert controller._step_index == 0
    assert controller.is_active


def test_completion_met_enables_next_but_does_not_auto_advance(qtbot) -> None:
    """The single most important gating behaviour: enable, but never advance on your own."""
    host = QWidget()
    qtbot.addWidget(host)
    met = False
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host, chapters, completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: met}
    )

    controller.start()
    assert controller._bubble is not None
    assert not controller._bubble._next_button.isEnabled()

    met = True
    controller._poll_step_completion()

    assert controller._bubble._next_button.isEnabled()
    assert controller._step_index == 0
    assert controller._current_chapter().chapter_id == "identify"


def test_completion_met_via_real_poll_timer_still_does_not_auto_advance(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    met = False
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host, chapters, completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: met}
    )

    controller.start()
    met = True

    qtbot.waitUntil(
        lambda: controller._bubble is not None and controller._bubble._next_button.isEnabled(),
        timeout=2000,
    )

    assert controller._step_index == 0


def test_step_already_met_when_shown_is_enabled_immediately(qtbot) -> None:
    """Back-into-a-done-step case: no waiting for the poll timer."""
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter(
            "identify", steps=(_step(), _step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS))
        ),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: True},
    )

    controller.start()
    controller._advance()

    assert controller._bubble is not None
    assert controller._bubble._next_button.isEnabled()


def test_missing_completion_check_counts_as_unmet(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(host, chapters)

    controller.start()

    assert controller._bubble is not None
    assert not controller._bubble._next_button.isEnabled()


def test_poll_timer_does_not_run_for_an_ungated_step(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (_chapter("identify", steps=(_step(),)),)
    controller = _controller(host, chapters)

    controller.start()

    assert not controller._completion_poll_timer.isActive()


def test_poll_timer_runs_for_a_gated_unsatisfied_step(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: False},
    )

    controller.start()

    assert controller._completion_poll_timer.isActive()


def test_poll_timer_keeps_running_for_an_already_met_gated_step(qtbot) -> None:
    """A met condition may close again, so the step keeps watching it."""
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: True},
    )

    controller.start()

    assert controller._completion_poll_timer.isActive()


def test_reclosed_gate_disables_next_again(qtbot) -> None:
    """Next never stays enabled on a condition that stopped holding."""
    host = QWidget()
    qtbot.addWidget(host)
    met = True
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host, chapters, completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: met}
    )

    controller.start()
    assert controller._bubble is not None
    assert controller._bubble._next_button.isEnabled()
    assert controller._bubble._expected_label.text().startswith("\u2713")

    met = False
    qtbot.waitUntil(
        lambda: controller._bubble is not None and not controller._bubble._next_button.isEnabled(),
        timeout=2000,
    )

    assert not controller._bubble._expected_label.text().startswith("\u2713")


def test_poll_timer_stops_when_the_step_changes(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter(
            "identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS), _step())
        ),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: False},
    )

    controller.start()
    assert controller._completion_poll_timer.isActive()

    controller._advance()

    assert controller._step_index == 1
    assert not controller._completion_poll_timer.isActive()


def test_poll_timer_stops_on_controller_stop(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter("identify", steps=(_step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS),)),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: False},
    )

    controller.start()
    assert controller._completion_poll_timer.isActive()

    controller.stop()

    assert not controller._completion_poll_timer.isActive()


def test_expected_source_shows_checkmark_when_completion_met(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    bubble = TutorialBubble(host)
    step = _step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS)

    bubble.show_step(
        step, chapter_title_source="chapter", progress_text="1/1", completion_met=True
    )

    assert bubble._expected_label.text() == "✓ Result"


def test_expected_source_has_no_checkmark_when_completion_unmet(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    bubble = TutorialBubble(host)
    step = _step(requires=TutorialCompletion.CONFIRMED_REGION_EXISTS)

    bubble.show_step(
        step, chapter_title_source="chapter", progress_text="1/1", completion_met=False
    )

    assert bubble._expected_label.text() == "Result"


def test_completion_note_shown_when_provided(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    bubble = TutorialBubble(host)
    step = _step(requires=TutorialCompletion.REGION_FIT_APPLIED)

    bubble.show_step(
        step,
        chapter_title_source="c",
        progress_text="1/1",
        completion_met=True,
        completion_note="The fit converged.",
    )

    assert bubble._completion_note_label.isVisibleTo(bubble)
    assert bubble._completion_note_label.text() == "The fit converged."


def test_completion_note_hidden_when_none(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    bubble = TutorialBubble(host)
    step = _step(requires=TutorialCompletion.REGION_FIT_APPLIED)

    bubble.show_step(
        step,
        chapter_title_source="c",
        progress_text="1/1",
        completion_met=True,
        completion_note=None,
    )

    assert not bubble._completion_note_label.isVisibleTo(bubble)


def _mode_change_step(requires: TutorialCompletion | None) -> TutorialStep:
    return TutorialStep(
        targets=(),
        action_source="Action",
        expected_source="Result",
        advance=AdvanceTrigger.MODE_CHANGE,
        advance_mode=EditingMode.ANALYSIS,
        requires=requires,
    )


def test_mode_change_trigger_does_not_advance_while_the_gate_is_unmet(qtbot) -> None:
    """A signal-driven step must not bypass its own completion condition."""
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (
        _chapter(
            "identify",
            steps=(_mode_change_step(TutorialCompletion.CONFIRMED_REGION_EXISTS), _step()),
        ),
    )
    controller = _controller(
        host,
        chapters,
        completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: False},
    )

    controller.start()
    controller.notify_mode_changed(EditingMode.ANALYSIS)

    assert controller._step_index == 0


def test_mode_change_trigger_advances_once_the_gate_is_met(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    met = False
    chapters = (
        _chapter(
            "identify",
            steps=(_mode_change_step(TutorialCompletion.CONFIRMED_REGION_EXISTS), _step()),
        ),
    )
    controller = _controller(
        host, chapters, completion_checks={TutorialCompletion.CONFIRMED_REGION_EXISTS: lambda: met}
    )

    controller.start()
    controller.notify_mode_changed(EditingMode.ANALYSIS)
    assert controller._step_index == 0

    met = True
    controller.notify_mode_changed(EditingMode.ANALYSIS)

    assert controller._step_index == 1


def test_ungated_mode_change_step_still_advances(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    chapters = (_chapter("identify", steps=(_mode_change_step(None), _step())),)
    controller = _controller(host, chapters)

    controller.start()
    controller.notify_mode_changed(EditingMode.ANALYSIS)

    assert controller._step_index == 1
