"""Semantic destination tests for the guided tutorial."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea, QWidget

from chappy.core.editing_mode import EditingMode
from chappy.gui.common.shared_operations import (
    AnalysisOperationPanel,
    AnalysisOperationSurface,
    get_shared_operation,
)
from chappy.gui.common.tutorial import (
    AdvanceTrigger,
    TutorialChapter,
    TutorialDestination,
    TutorialStep,
    TutorialTarget,
    TutorialTargetProminence,
    TutorialTargetRole,
)
from chappy.gui.shell.tutorial_tour_controller import TutorialTourController
from tests.helpers.tutorial_chapters import all_walkthrough_chapters


def _step() -> TutorialStep:
    return TutorialStep(targets=(), action_source="Action", expected_source="Result")


def _target(
    object_name: str, prominence: TutorialTargetProminence = TutorialTargetProminence.PRIMARY
) -> TutorialTarget:
    return TutorialTarget(
        object_name=object_name, role=TutorialTargetRole.INTERACT, prominence=prominence
    )


def _target_step(*targets: TutorialTarget) -> TutorialStep:
    return TutorialStep(
        targets=targets,
        action_source="Inspect the target",
        expected_source="The target is visible",
    )


def _target_intersects_viewport(widget: QWidget, scroll: QScrollArea) -> bool:
    viewport = scroll.viewport()
    rect = QRect(widget.mapTo(viewport, QPoint(0, 0)), widget.size())
    return not rect.intersected(viewport.rect()).isEmpty()


def _click_topmost_widget_at(target: QWidget, qtbot) -> QWidget:
    global_position = target.mapToGlobal(target.rect().center())
    receiver = QApplication.widgetAt(global_position)
    assert receiver is not None
    qtbot.mouseClick(
        receiver, Qt.MouseButton.LeftButton, pos=receiver.mapFromGlobal(global_position)
    )
    return receiver


def test_controller_reports_chapter_lifecycle_and_clears_context_on_stop(qtbot) -> None:
    """Chapter-scoped state is cleared when the walkthrough advances or exits."""
    contexts: list[str | None] = []
    chapters = tuple(
        TutorialChapter(
            chapter_id=chapter_id,
            title_source=chapter_id,
            destination=TutorialDestination(mode=mode),
            steps=(_step(),),
        )
        for chapter_id, mode in (
            ("identify", EditingMode.IDENTIFY),
            ("continuum", EditingMode.CONTINUUM),
        )
    )
    host = QWidget()
    qtbot.addWidget(host)
    controller = TutorialTourController(
        host,
        chapters=chapters,
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
        chapter_context_changed=contexts.append,
    )

    controller.start()
    controller._advance()
    controller.stop()

    assert contexts == ["identify", "continuum", None]


@pytest.mark.parametrize("mode", [None, EditingMode.IDENTIFY, EditingMode.CONTINUUM])
def test_non_analysis_destination_rejects_surface_and_panel(mode: EditingMode | None) -> None:
    with pytest.raises(ValueError, match="Only an Analysis"):
        TutorialDestination(
            mode=mode,
            surface=AnalysisOperationSurface.OVERVIEW,
            panel=AnalysisOperationPanel.SUMMARY,
        )


@pytest.mark.parametrize(
    ("surface", "panel"),
    [
        (AnalysisOperationSurface.OVERVIEW, None),
        (None, AnalysisOperationPanel.SUMMARY),
        (None, None),
    ],
)
def test_analysis_destination_requires_surface_and_panel(
    surface: AnalysisOperationSurface | None, panel: AnalysisOperationPanel | None
) -> None:
    with pytest.raises(ValueError, match="requires both surface and panel"):
        TutorialDestination(mode=EditingMode.ANALYSIS, surface=surface, panel=panel)


@pytest.mark.parametrize(
    ("surface", "panel"),
    [
        (AnalysisOperationSurface.REGION_DETAIL, AnalysisOperationPanel.SUMMARY),
        (AnalysisOperationSurface.REGION_DETAIL, AnalysisOperationPanel.STRUCTURE),
        (AnalysisOperationSurface.OVERVIEW, AnalysisOperationPanel.DETAIL),
    ],
)
def test_analysis_destination_rejects_panel_on_wrong_surface(
    surface: AnalysisOperationSurface, panel: AnalysisOperationPanel
) -> None:
    with pytest.raises(ValueError, match="requires surface"):
        TutorialDestination(mode=EditingMode.ANALYSIS, surface=surface, panel=panel)


def test_chapter_rejects_shared_operation_outside_destination_scope() -> None:
    step = TutorialStep(
        targets=(),
        action_source="Action",
        expected_source="Result",
        operation=get_shared_operation("optimize_shift_click"),
    )

    with pytest.raises(ValueError, match="does not match shared operation"):
        TutorialChapter(
            chapter_id="analysis_structure",
            title_source="Structure",
            destination=TutorialDestination(
                mode=EditingMode.ANALYSIS,
                surface=AnalysisOperationSurface.OVERVIEW,
                panel=AnalysisOperationPanel.STRUCTURE,
            ),
            steps=(step,),
        )


def test_chapter_accepts_shared_operation_after_nested_panel_navigation() -> None:
    step = TutorialStep(
        targets=(),
        action_source="Merge regions",
        expected_source="Regions merge",
        operation=get_shared_operation("analysis_structure_merge"),
    )

    chapter = TutorialChapter(
        chapter_id="analysis_structure",
        title_source="Structure",
        destination=TutorialDestination(
            mode=EditingMode.ANALYSIS,
            surface=AnalysisOperationSurface.OVERVIEW,
            panel=AnalysisOperationPanel.SUMMARY,
        ),
        steps=(step,),
    )

    assert chapter.steps[0].operation is get_shared_operation("analysis_structure_merge")


def test_step_rejects_duplicate_target_names() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        TutorialStep(
            targets=(_target("same"), _target("same", TutorialTargetProminence.RELATED)),
            action_source="Action",
            expected_source="Result",
        )


@pytest.mark.parametrize(
    "targets",
    [
        (_target("related", TutorialTargetProminence.RELATED),),
        (_target("first"), _target("second")),
    ],
)
def test_step_requires_exactly_one_primary_target(targets: tuple[TutorialTarget, ...]) -> None:
    with pytest.raises(ValueError, match="exactly one PRIMARY"):
        TutorialStep(targets=targets, action_source="Action", expected_source="Result")


def test_controller_applies_mode_surface_panel_in_order(qtbot) -> None:
    calls: list[object] = []

    def record_surface(surface: AnalysisOperationSurface) -> bool:
        calls.append(surface)
        return True

    def record_panel(panel: AnalysisOperationPanel) -> bool:
        calls.append(panel)
        return True

    chapter = TutorialChapter(
        chapter_id="analysis_structure",
        title_source="Structure",
        destination=TutorialDestination(
            mode=EditingMode.ANALYSIS,
            surface=AnalysisOperationSurface.OVERVIEW,
            panel=AnalysisOperationPanel.STRUCTURE,
        ),
        steps=(_step(),),
    )
    host = QWidget()
    qtbot.addWidget(host)
    controller = TutorialTourController(
        host,
        chapters=(chapter,),
        switch_mode=lambda mode: calls.append(mode),
        switch_analysis_surface=record_surface,
        switch_analysis_panel=record_panel,
    )

    controller.start()

    assert calls == [
        EditingMode.ANALYSIS,
        AnalysisOperationSurface.OVERVIEW,
        AnalysisOperationPanel.STRUCTURE,
    ]


def test_controller_scrolls_primary_target_into_view_and_preserves_its_priority(qtbot) -> None:
    """A RELATED target in the same viewport must not displace PRIMARY."""
    host = QWidget()
    host.resize(320, 220)
    qtbot.addWidget(host)
    scroll = QScrollArea(host)
    scroll.setGeometry(20, 20, 200, 150)
    content = QWidget()
    content.resize(180, 600)
    primary = QWidget(content)
    primary.setObjectName("primaryTarget")
    primary.setGeometry(20, 20, 120, 40)
    related = QWidget(content)
    related.setObjectName("relatedTarget")
    related.setGeometry(20, 520, 120, 40)
    scroll.setWidget(content)
    host.show()
    qtbot.waitExposed(host)
    QApplication.processEvents()
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())

    chapter = TutorialChapter(
        chapter_id="scroll_priority",
        title_source="Scroll priority",
        destination=TutorialDestination(mode=EditingMode.IDENTIFY),
        steps=(
            _target_step(
                _target("primaryTarget"),
                _target("relatedTarget", TutorialTargetProminence.RELATED),
            ),
        ),
    )
    controller = TutorialTourController(
        host,
        chapters=(chapter,),
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )

    controller.start()
    QApplication.processEvents()

    assert _target_intersects_viewport(primary, scroll)
    assert not _target_intersects_viewport(related, scroll)
    assert controller._overlay is not None
    assert controller._overlay.primary_spotlight_rect() is not None
    assert len(controller._overlay.spotlight_rects()) == 1


def test_controller_reveals_related_target_without_moving_visible_primary(qtbot) -> None:
    """Targets in independent areas should both remain visible."""
    host = QWidget()
    host.resize(520, 240)
    qtbot.addWidget(host)
    primary = QWidget(host)
    primary.setObjectName("fixedPrimaryTarget")
    primary.setGeometry(300, 30, 160, 50)
    scroll = QScrollArea(host)
    scroll.setGeometry(20, 20, 220, 160)
    content = QWidget()
    content.resize(200, 600)
    related = QWidget(content)
    related.setObjectName("scrolledRelatedTarget")
    related.setGeometry(20, 520, 150, 40)
    scroll.setWidget(content)
    host.show()
    qtbot.waitExposed(host)
    QApplication.processEvents()
    assert not _target_intersects_viewport(related, scroll)

    chapter = TutorialChapter(
        chapter_id="independent_targets",
        title_source="Independent targets",
        destination=TutorialDestination(mode=EditingMode.IDENTIFY),
        steps=(
            _target_step(
                _target("fixedPrimaryTarget"),
                _target("scrolledRelatedTarget", TutorialTargetProminence.RELATED),
            ),
        ),
    )
    controller = TutorialTourController(
        host,
        chapters=(chapter,),
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )

    controller.start()
    QApplication.processEvents()

    assert _target_intersects_viewport(related, scroll)
    assert controller._overlay is not None
    assert len(controller._overlay.spotlight_rects()) == 2


def test_controller_does_not_scroll_for_already_visible_or_hidden_targets(qtbot) -> None:
    """Target preparation must not cause unrelated viewport jumps."""
    host = QWidget()
    host.resize(320, 220)
    qtbot.addWidget(host)
    scroll = QScrollArea(host)
    scroll.setGeometry(20, 20, 200, 150)
    content = QWidget()
    content.resize(180, 700)
    visible = QWidget(content)
    visible.setGeometry(20, 300, 120, 40)
    hidden = QWidget(content)
    hidden.setGeometry(20, 620, 120, 40)
    hidden.hide()
    scroll.setWidget(content)
    host.show()
    qtbot.waitExposed(host)
    QApplication.processEvents()
    scroll.verticalScrollBar().setValue(270)
    original_position = scroll.verticalScrollBar().value()
    assert _target_intersects_viewport(visible, scroll)

    controller = TutorialTourController(
        host,
        chapters=(
            TutorialChapter(
                chapter_id="no_jump",
                title_source="No jump",
                destination=TutorialDestination(mode=EditingMode.IDENTIFY),
                steps=(_step(),),
            ),
        ),
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )

    controller._ensure_target_visible(visible)
    controller._ensure_target_visible(hidden)

    assert scroll.verticalScrollBar().value() == original_position


def test_analysis_surface_transition_does_not_repeat_top_level_mode(qtbot) -> None:
    modes: list[EditingMode] = []
    surfaces: list[AnalysisOperationSurface] = []
    chapters = tuple(
        TutorialChapter(
            chapter_id=panel.value,
            title_source=panel.value,
            destination=TutorialDestination(
                mode=EditingMode.ANALYSIS, surface=surface, panel=panel
            ),
            steps=(_step(),),
        )
        for surface, panel in (
            (AnalysisOperationSurface.OVERVIEW, AnalysisOperationPanel.SUMMARY),
            (AnalysisOperationSurface.REGION_DETAIL, AnalysisOperationPanel.DETAIL),
        )
    )
    host = QWidget()
    qtbot.addWidget(host)

    def record_surface(surface: AnalysisOperationSurface) -> bool:
        surfaces.append(surface)
        return True

    controller = TutorialTourController(
        host,
        chapters=chapters,
        switch_mode=modes.append,
        switch_analysis_surface=record_surface,
        switch_analysis_panel=lambda _panel: True,
    )

    controller.start()
    controller._advance()

    assert modes == [EditingMode.ANALYSIS]
    assert surfaces == [AnalysisOperationSurface.OVERVIEW, AnalysisOperationSurface.REGION_DETAIL]


def _analysis_chapter(chapter_id: str, panel: AnalysisOperationPanel) -> TutorialChapter:
    surface = (
        AnalysisOperationSurface.REGION_DETAIL
        if panel is AnalysisOperationPanel.DETAIL
        else AnalysisOperationSurface.OVERVIEW
    )
    return TutorialChapter(
        chapter_id=chapter_id,
        title_source=chapter_id,
        destination=TutorialDestination(mode=EditingMode.ANALYSIS, surface=surface, panel=panel),
        steps=(_step(),),
    )


def test_unreachable_chapter_is_skipped(qtbot, monkeypatch) -> None:
    """A chapter whose destination cannot be applied must not be shown."""
    shown: list[str] = []
    chapters = (
        _analysis_chapter("detail", AnalysisOperationPanel.DETAIL),
        _analysis_chapter("structure", AnalysisOperationPanel.STRUCTURE),
    )
    host = QWidget()
    qtbot.addWidget(host)
    controller = TutorialTourController(
        host,
        chapters=chapters,
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda surface: surface is AnalysisOperationSurface.OVERVIEW,
        switch_analysis_panel=lambda _panel: True,
    )
    original_show = TutorialTourController._show_current_step

    def record_show(self: TutorialTourController) -> None:
        shown.append(self._current_chapter().chapter_id)
        original_show(self)

    monkeypatch.setattr(TutorialTourController, "_show_current_step", record_show)

    controller.start()

    assert shown == ["structure"]
    assert controller.is_active


def test_tour_stops_when_all_remaining_chapters_are_unreachable(qtbot) -> None:
    """The tour must end instead of showing chapters on an unreachable screen."""
    host = QWidget()
    qtbot.addWidget(host)
    controller = TutorialTourController(
        host,
        chapters=(_analysis_chapter("detail", AnalysisOperationPanel.DETAIL),),
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: False,
        switch_analysis_panel=lambda _panel: True,
    )

    controller.start()

    assert not controller.is_active


def test_reentrant_mode_change_during_chapter_transition(qtbot) -> None:
    """The shell echoes switch_mode back synchronously; step state must already be reset."""
    long_chapter = TutorialChapter(
        chapter_id="long",
        title_source="Long",
        destination=TutorialDestination(mode=EditingMode.IDENTIFY),
        steps=(_step(), _step(), _step()),
    )
    short_chapter = TutorialChapter(
        chapter_id="short",
        title_source="Short",
        destination=TutorialDestination(mode=EditingMode.CONTINUUM),
        steps=(_step(),),
    )
    host = QWidget()
    qtbot.addWidget(host)
    controller = TutorialTourController(
        host,
        chapters=(long_chapter, short_chapter),
        switch_mode=lambda mode: controller.notify_mode_changed(mode),
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )

    controller.start()
    controller._advance()
    controller._advance()
    controller._advance()

    assert controller._current_chapter().chapter_id == "short"
    assert controller._step_index == 0


def test_analysis_mode_button_click_advances_but_next_and_wrong_mode_do_not(qtbot) -> None:
    """The Identify boundary must advance only after the real Analysis mode change."""
    host = QWidget()
    host.resize(700, 420)
    qtbot.addWidget(host)
    analysis_button = QPushButton("Analysis", host)
    analysis_button.setObjectName("modeButton_ANALYSIS")
    analysis_button.setGeometry(500, 30, 120, 40)
    identify = TutorialChapter(
        chapter_id="identify",
        title_source="Identify",
        destination=TutorialDestination(mode=EditingMode.IDENTIFY),
        steps=(
            TutorialStep(
                targets=(_target("modeButton_ANALYSIS"),),
                action_source="Click Analysis",
                expected_source="Analysis opens",
                advance=AdvanceTrigger.MODE_CHANGE,
                advance_mode=EditingMode.ANALYSIS,
            ),
        ),
    )
    analysis = TutorialChapter(
        chapter_id="analysis",
        title_source="Analysis",
        destination=TutorialDestination(
            mode=EditingMode.ANALYSIS,
            surface=AnalysisOperationSurface.OVERVIEW,
            panel=AnalysisOperationPanel.SUMMARY,
        ),
        steps=(_step(),),
    )
    applied_modes: list[EditingMode] = []
    controller = TutorialTourController(
        host,
        chapters=(identify, analysis),
        switch_mode=applied_modes.append,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )
    analysis_button.clicked.connect(lambda: controller.notify_mode_changed(EditingMode.ANALYSIS))
    host.show()
    qtbot.waitExposed(host)
    controller.start()
    QApplication.processEvents()

    assert applied_modes == [EditingMode.IDENTIFY]
    assert controller._current_chapter().chapter_id == "identify"
    assert controller._bubble is not None
    assert not controller._bubble._next_button.isEnabled()

    qtbot.mouseClick(controller._bubble._next_button, Qt.MouseButton.LeftButton)
    controller._bubble.next_requested.emit()
    controller.notify_mode_changed(EditingMode.CONTINUUM)
    assert controller._current_chapter().chapter_id == "identify"

    global_position = analysis_button.mapToGlobal(analysis_button.rect().center())
    receiver = QApplication.widgetAt(global_position)
    assert receiver is analysis_button
    qtbot.mouseClick(
        receiver, Qt.MouseButton.LeftButton, pos=receiver.mapFromGlobal(global_position)
    )

    assert controller._current_chapter().chapter_id == "analysis"
    assert controller._step_index == 0


def test_getting_started_own_data_observe_step_blocks_real_new_button_click(qtbot) -> None:
    """Clicking the highlighted New position must not emit its file-dialog action."""
    source_chapter = next(
        chapter
        for chapter in all_walkthrough_chapters()
        if chapter.chapter_id == "getting_started"
    )
    own_data_step = next(
        step
        for step in source_chapter.steps
        if "Use this button when you want" in step.action_source
    )
    chapter = TutorialChapter(
        chapter_id="own_data_acceptance",
        title_source="Getting Started",
        destination=TutorialDestination(),
        steps=(own_data_step,),
    )
    host = QWidget()
    host.resize(600, 360)
    qtbot.addWidget(host)
    new_button = QPushButton("New", host)
    new_button.setObjectName("modeContextBar_open_observation_data")
    new_button.setGeometry(30, 30, 100, 40)
    controller = TutorialTourController(
        host,
        chapters=(chapter,),
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )
    host.show()
    qtbot.waitExposed(host)
    controller.start()
    QApplication.processEvents()

    with qtbot.assertNotEmitted(new_button.clicked):
        receiver = _click_topmost_widget_at(new_button, qtbot)

    assert receiver is controller._overlay


def test_getting_started_interact_step_delivers_click_to_real_sample_button(qtbot) -> None:
    """A real walkthrough INTERACT definition must expose its button's clicked signal."""
    source_chapter = next(
        chapter
        for chapter in all_walkthrough_chapters()
        if chapter.chapter_id == "getting_started"
    )
    zoom_step = next(
        step
        for step in source_chapter.steps
        if "first click this Zoom button" in step.action_source
    )
    chapter = TutorialChapter(
        chapter_id="zoom_acceptance",
        title_source="Getting Started",
        destination=TutorialDestination(),
        steps=(zoom_step,),
    )
    host = QWidget()
    host.resize(600, 360)
    qtbot.addWidget(host)
    zoom_button = QPushButton("Zoom", host)
    zoom_button.setObjectName("modeContextBar_zoom_rect")
    zoom_button.setGeometry(30, 30, 100, 40)
    controller = TutorialTourController(
        host,
        chapters=(chapter,),
        switch_mode=lambda _mode: None,
        switch_analysis_surface=lambda _surface: True,
        switch_analysis_panel=lambda _panel: True,
    )
    host.show()
    qtbot.waitExposed(host)
    controller.start()
    QApplication.processEvents()

    with qtbot.waitSignal(zoom_button.clicked):
        receiver = _click_topmost_widget_at(zoom_button, qtbot)

    assert receiver is zoom_button
    controller.stop()
