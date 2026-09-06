"""Guided-tour orchestration: chapter sequencing over the coach-mark widgets."""

from __future__ import annotations

import contextlib
import logging
import weakref
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QScrollArea, QWidget

from chappy.gui.common.collapsible_section import CollapsibleSection
from chappy.gui.common.tutorial import (
    PREREQUISITE_WARNING_SOURCES,
    AdvanceTrigger,
    TutorialBubble,
    TutorialSpotlightOverlay,
    TutorialSpotlightTarget,
    TutorialTargetProminence,
)
from chappy.gui.shell.shortcuts import format_runtime_shortcuts

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from chappy.core.editing_mode import EditingMode
    from chappy.gui.common.shared_operations import (
        AnalysisOperationPanel,
        AnalysisOperationSurface,
    )
    from chappy.gui.common.tutorial import (
        TutorialChapter,
        TutorialCompletion,
        TutorialDestination,
        TutorialPrerequisite,
        TutorialStep,
        TutorialTarget,
    )

logger = logging.getLogger(__name__)

_TARGET_SCROLL_MARGIN = 8
_COMPLETION_POLL_INTERVAL_MS = 250


def _ancestor_scroll_areas(widget: QWidget, host: QWidget) -> tuple[QScrollArea, ...]:
    """Return scroll areas containing ``widget``, from inner to outer."""
    scroll_areas: list[QScrollArea] = []
    ancestor = widget.parentWidget()
    while ancestor is not None and ancestor is not host:
        if isinstance(ancestor, QScrollArea):
            scroll_areas.append(ancestor)
        ancestor = ancestor.parentWidget()
    return tuple(scroll_areas)


def _intersects_viewport(widget: QWidget, scroll: QScrollArea) -> bool:
    """Return whether any real part of ``widget`` is inside the viewport."""
    viewport = scroll.viewport()
    rect = QRect(widget.mapTo(viewport, QPoint(0, 0)), widget.size())
    return not rect.intersected(viewport.rect()).isEmpty()


def _expand_ancestor_sections(widget: QWidget, host: QWidget) -> None:
    """Expand collapsed disclosure sections that hide a tour target."""
    ancestor = widget.parentWidget()
    while ancestor is not None and ancestor is not host:
        if isinstance(ancestor, CollapsibleSection) and ancestor.is_collapsed():
            ancestor.set_collapsed(False)
        ancestor = ancestor.parentWidget()


def _is_tutorial_target_visible(widget: QWidget, host: QWidget) -> bool:
    """Return whether a target is visible through every ancestor scroll area."""
    if not widget.isVisibleTo(host):
        return False
    host_rect = QRect(widget.mapTo(host, QPoint(0, 0)), widget.size()).intersected(host.rect())
    return not host_rect.isEmpty() and all(
        _intersects_viewport(widget, scroll) for scroll in _ancestor_scroll_areas(widget, host)
    )


def _resolve_in_window(window: QWidget, object_name: str) -> QWidget | None:
    if window.objectName() == object_name:
        return window
    return window.findChild(QWidget, object_name)


class TutorialTourController(QObject):
    """Drive the walkthrough: switch modes per chapter and step the coach marks."""

    def __init__(  # noqa: PLR0913 - collaborators are injected explicitly, one per responsibility
        self,
        main_window: QWidget,
        *,
        chapters: Sequence[TutorialChapter],
        switch_mode: Callable[[EditingMode], None],
        switch_analysis_surface: Callable[[AnalysisOperationSurface], bool],
        switch_analysis_panel: Callable[[AnalysisOperationPanel], bool],
        chapter_context_changed: Callable[[str | None], None] | None = None,
        prerequisite_checks: Mapping[TutorialPrerequisite, Callable[[], bool]] | None = None,
        completion_checks: Mapping[TutorialCompletion, Callable[[], bool]] | None = None,
        completion_notes: Mapping[TutorialCompletion, Callable[[], str | None]] | None = None,
    ) -> None:
        """Initialize the controller.

        Args:
            main_window: Top-level window hosting the overlay and targets.
            chapters: Ordered walkthrough chapters.
            switch_mode: Callable that activates an editing mode.
            switch_analysis_surface: Callable that activates an Analysis surface
                and reports whether it is now active.
            switch_analysis_panel: Callable that activates an Analysis nested
                panel and reports whether it is now active.
            chapter_context_changed: Optional lifecycle hook receiving the active
                chapter id, or ``None`` when the tour stops.
            prerequisite_checks: Predicates resolving each chapter prerequisite
                against live project state; a missing entry counts as unmet.
            completion_checks: Predicates resolving each step completion
                condition against live project state; a missing entry counts
                as unmet.
            completion_notes: Optional predicates returning an already-
                translated note explaining a gated step's completion state,
                shown under the expected-result line.
        """
        super().__init__(main_window)
        self._main_window = main_window
        self._chapters = tuple(chapters)
        self._switch_mode = switch_mode
        self._switch_analysis_surface = switch_analysis_surface
        self._switch_analysis_panel = switch_analysis_panel
        self._chapter_context_changed = chapter_context_changed
        self._prerequisite_checks = dict(prerequisite_checks or {})
        self._completion_checks = dict(completion_checks or {})
        self._completion_notes = dict(completion_notes or {})

        self._overlay: TutorialSpotlightOverlay | None = None
        self._bubble: TutorialBubble | None = None
        self._chapter_index = 0
        self._step_index = 0
        self._awaiting_prerequisite = False
        self._active = False
        self._applied_mode: EditingMode | None = None
        self._step_refresh_timer = QTimer(self)
        self._step_refresh_timer.setSingleShot(True)
        self._step_refresh_timer.timeout.connect(self._refresh_current_step)
        self._completion_poll_timer = QTimer(self)
        self._completion_poll_timer.setInterval(_COMPLETION_POLL_INTERVAL_MS)
        self._completion_poll_timer.timeout.connect(self._poll_step_completion)
        self._step_completion_met = False
        self._step_completion_note: str | None = None
        self._triggered_step: tuple[int, int] | None = None
        self._completed_dialog_trigger_steps: set[tuple[int, int]] = set()
        self._dialog_trigger_sources: dict[tuple[int, int], weakref.ReferenceType[QDialog]] = {}

    @property
    def is_active(self) -> bool:
        """Return whether the tour is currently shown."""
        return self._active

    def start(self) -> None:
        """Start the walkthrough from the first chapter."""
        if self._active:
            self.stop()
        self._active = True
        self._chapter_index = 0
        self._step_index = 0
        self._awaiting_prerequisite = False
        self._applied_mode = None
        self._triggered_step = None
        self._completed_dialog_trigger_steps.clear()
        self._dialog_trigger_sources.clear()
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        self._begin_chapter()

    def stop(self) -> None:
        """Dismiss the tour widgets."""
        was_active = self._active
        self._active = False
        self._step_refresh_timer.stop()
        self._completion_poll_timer.stop()
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        if was_active and self._chapter_context_changed is not None:
            self._chapter_context_changed(None)
        self._teardown_widgets()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Re-anchor the active step when a dialog window opens or closes.

        A dialog's visibility only re-resolves host and targets; it advances
        the tour solely through the gated trigger path below.
        """
        if (
            self._active
            and event.type() in (QEvent.Type.Show, QEvent.Type.Hide)
            and isinstance(watched, QDialog)
        ):
            if (
                event.type() == QEvent.Type.Hide
                and self._overlay is not None
                and self._overlay.window() is watched
            ):
                self._teardown_widgets()
            if not self._awaiting_prerequisite:
                self._advance_on_dialog_event(watched, shown=event.type() == QEvent.Type.Show)
            if self._active and not self._step_refresh_timer.isActive():
                self._step_refresh_timer.start(0)
        return super().eventFilter(watched, event)

    def _advance_on_dialog_event(self, dialog: QDialog, *, shown: bool) -> None:
        """Advance the step whose dialog trigger this visibility change matches."""
        step = self._current_step()
        expected_trigger = AdvanceTrigger.DIALOG_SHOWN if shown else AdvanceTrigger.DIALOG_HIDDEN
        if step.advance is expected_trigger and step.advance_dialog == dialog.objectName():
            self._advance_when_completed(dialog=dialog)

    def notify_mode_changed(self, mode: EditingMode) -> None:
        """Advance a signal-driven step when its expected mode activates.

        Args:
            mode: Newly activated editing mode.
        """
        self._applied_mode = mode
        if not self._active or self._awaiting_prerequisite:
            return
        step = self._current_step()
        if step.advance is AdvanceTrigger.MODE_CHANGE and step.advance_mode == mode:
            self._advance_when_completed()

    def _advance_when_completed(self, *, dialog: QDialog | None = None) -> None:
        """Advance a signal-driven step, holding the trigger until its gate opens."""
        step = self._current_step()
        position = (self._chapter_index, self._step_index)
        if dialog is not None:
            self._dialog_trigger_sources[position] = weakref.ref(dialog)
        if step.requires is not None and not self._check_completion(step.requires):
            # Dialogs hide before their result is applied, so the trigger waits for the gate.
            self._triggered_step = position
            logger.info(
                "Tutorial step trigger held; completion condition unmet: %s", step.requires.name
            )
            return
        if step.advance in (AdvanceTrigger.DIALOG_SHOWN, AdvanceTrigger.DIALOG_HIDDEN):
            self._completed_dialog_trigger_steps.add(position)
        self._advance()

    def _advance_held_trigger(self) -> bool:
        """Advance the current step when its already-fired trigger's gate has opened."""
        if self._triggered_step != (self._chapter_index, self._step_index):
            return False
        step = self._current_step()
        if step.requires is None or not self._check_completion(step.requires):
            return False
        if step.advance in (AdvanceTrigger.DIALOG_SHOWN, AdvanceTrigger.DIALOG_HIDDEN):
            self._completed_dialog_trigger_steps.add((self._chapter_index, self._step_index))
        self._advance()
        return True

    def _current_step_allows_next(self) -> bool:
        """Return whether Next may replay the current step's consumed trigger."""
        step = self._current_step()
        return step.advance is AdvanceTrigger.NEXT_BUTTON or (
            step.advance in (AdvanceTrigger.DIALOG_SHOWN, AdvanceTrigger.DIALOG_HIDDEN)
            and (self._chapter_index, self._step_index) in self._completed_dialog_trigger_steps
        )

    def _ensure_widgets(self, host: QWidget) -> None:
        if self._overlay is not None and self._overlay.window() is not host:
            self._teardown_widgets()
        if self._overlay is None:
            self._overlay = TutorialSpotlightOverlay(host)
            self._overlay.spotlight_changed.connect(self._reposition_bubble)
            self._overlay.destroyed.connect(self._forget_overlay)
        if self._bubble is None:
            self._bubble = TutorialBubble(host, text_formatter=format_runtime_shortcuts)
            self._bubble.next_requested.connect(self._advance_from_next_button)
            self._bubble.back_requested.connect(self._go_back)
            self._bubble.close_requested.connect(self.stop)
            self._bubble.destroyed.connect(self._forget_bubble)

    def _teardown_widgets(self) -> None:
        self._completion_poll_timer.stop()
        if self._overlay is not None:
            with contextlib.suppress(RuntimeError):
                self._overlay.destroyed.disconnect(self._forget_overlay)
                self._overlay.set_targets(())
                self._overlay.hide()
                self._overlay.deleteLater()
            self._overlay = None
        if self._bubble is not None:
            with contextlib.suppress(RuntimeError):
                self._bubble.destroyed.disconnect(self._forget_bubble)
                self._bubble.hide()
                self._bubble.deleteLater()
            self._bubble = None

    def _forget_overlay(self) -> None:
        self._overlay = None

    def _forget_bubble(self) -> None:
        self._bubble = None
        self._completion_poll_timer.stop()

    def _refresh_current_step(self) -> None:
        if not self._active:
            return
        if self._awaiting_prerequisite:
            self._show_prerequisite_warning(self._current_chapter())
            return
        if self._advance_held_trigger():
            return
        self._show_current_step()

    def _resolve_target_widget(self, object_name: str) -> QWidget | None:
        """Return a reachable widget for ``object_name``, never one in a hidden window."""
        main_host = self._main_window.window()
        candidates = self._main_window.findChildren(QWidget, object_name)
        for widget in candidates:
            if widget.window() is main_host:
                return widget
        modal = QApplication.activeModalWidget()
        if modal is not None and modal.isVisible():
            resolved = _resolve_in_window(modal, object_name)
            if resolved is not None and resolved.window().isVisible():
                return resolved
        for widget in candidates:
            if widget.window().isVisible():
                return widget
        return None

    def _resolve_target(self, target: TutorialTarget) -> QWidget | None:
        """Return the first reachable widget among a target's names, in order."""
        for object_name in (target.object_name, *target.fallback_object_names):
            widget = self._resolve_target_widget(object_name)
            if widget is not None:
                return widget
        return None

    def _select_host_window(self, targets: Sequence[TutorialSpotlightTarget]) -> QWidget:
        """Return the top-level window the coach marks are built on.

        A step without any reachable target anchors on the active modal
        window, so the bubble never lands behind the dialog the user is in.
        """
        windows = {id(target.widget.window()): target.widget.window() for target in targets}
        if len(windows) > 1:
            logger.warning(
                "Tutorial step targets span multiple windows; keeping the primary target's "
                "window: %s",
                tuple(
                    (target.widget.objectName(), target.widget.window().objectName())
                    for target in targets
                ),
            )
        primary = next(
            (
                target
                for target in targets
                if target.prominence is TutorialTargetProminence.PRIMARY
            ),
            None,
        )
        if primary is not None:
            return primary.widget.window()
        if len(windows) == 1:
            return next(iter(windows.values()))
        modal = QApplication.activeModalWidget()
        if modal is not None and modal.isVisible():
            return modal.window()
        return self._main_window.window()

    def _current_chapter(self) -> TutorialChapter:
        return self._chapters[self._chapter_index]

    def _current_step(self) -> TutorialStep:
        return self._current_chapter().steps[self._step_index]

    def _begin_chapter(self, *, skip_prerequisite: bool = False) -> None:
        """Start the current chapter, skipping chapters whose destination is unavailable.

        Args:
            skip_prerequisite: Whether the current chapter's prerequisite was
                already acknowledged via [Continue anyway].
        """
        while True:
            chapter = self._current_chapter()
            # Reset before applying: mode switches re-enter notify_mode_changed
            # synchronously, which must not read the previous chapter's index.
            self._step_index = 0
            if not skip_prerequisite and not self._prerequisite_met(chapter):
                self._show_prerequisite_warning(chapter)
                return
            skip_prerequisite = False
            if self._apply_destination(chapter.destination):
                break
            logger.warning(
                "Tutorial chapter skipped (destination unavailable): %s", chapter.chapter_id
            )
            if self._chapter_index + 1 >= len(self._chapters):
                self.stop()
                return
            self._chapter_index += 1
        logger.info("Tutorial chapter started: %s", chapter.chapter_id)
        if self._chapter_context_changed is not None:
            self._chapter_context_changed(chapter.chapter_id)
        self._show_current_step()

    def _prerequisite_met(self, chapter: TutorialChapter) -> bool:
        """Return whether the chapter's prerequisite currently holds."""
        if chapter.prerequisite is None:
            return True
        check = self._prerequisite_checks.get(chapter.prerequisite)
        return check is not None and check()

    def _check_completion(self, condition: TutorialCompletion) -> bool:
        """Return whether a gated step's completion condition currently holds."""
        check = self._completion_checks.get(condition)
        return check is not None and check()

    def _completion_note_for(self, condition: TutorialCompletion) -> str | None:
        """Return the optional already-translated note for a completion condition."""
        note_check = self._completion_notes.get(condition)
        return note_check() if note_check is not None else None

    def _poll_step_completion(self) -> None:
        """Track the active gated step's condition, which may open and close again."""
        if not self._active or self._awaiting_prerequisite or self._bubble is None:
            return
        step = self._current_step()
        if step.requires is None:
            self._completion_poll_timer.stop()
            return
        met = self._check_completion(step.requires)
        note = self._completion_note_for(step.requires)
        if met == self._step_completion_met and note == self._step_completion_note:
            return
        self._step_completion_met = met
        self._step_completion_note = note
        self._bubble.set_completion_state(met=met, note=note)
        self._bubble.set_next_enabled(self._current_step_allows_next() and met)
        if met:
            self._advance_held_trigger()

    def _show_prerequisite_warning(self, chapter: TutorialChapter) -> None:
        """Soft-block the chapter behind a warning bubble on the main window."""
        prerequisite = chapter.prerequisite
        if prerequisite is None:
            return
        self._awaiting_prerequisite = True
        logger.info("Tutorial chapter prerequisite unmet: %s", chapter.chapter_id)
        host = self._main_window.window()
        self._ensure_widgets(host)
        overlay = self._overlay
        bubble = self._bubble
        if overlay is None or bubble is None:
            return
        overlay.set_targets(())
        overlay.show()
        overlay.raise_()
        bubble.show_prerequisite_warning(
            chapter_title_source=chapter.title_source,
            warning_source=PREREQUISITE_WARNING_SOURCES[prerequisite],
        )
        bubble.set_next_enabled(True)
        bubble.set_back_enabled(self._chapter_index > 0)
        bubble.show()
        bubble.raise_()
        self._reposition_bubble()

    def _apply_destination(self, destination: TutorialDestination) -> bool:
        """Apply one chapter destination in mode, surface, panel order.

        Returns:
            Whether the full destination is now active.
        """
        if destination.mode is not None and destination.mode is not self._applied_mode:
            self._applied_mode = destination.mode
            self._switch_mode(destination.mode)
        if destination.surface is not None and not self._switch_analysis_surface(
            destination.surface
        ):
            return False
        return destination.panel is None or self._switch_analysis_panel(destination.panel)

    def _advance(self) -> None:
        self._triggered_step = None
        chapter = self._current_chapter()
        if self._step_index + 1 < len(chapter.steps):
            self._step_index += 1
            self._show_current_step()
            return
        if self._chapter_index + 1 < len(self._chapters):
            self._chapter_index += 1
            self._begin_chapter()
            return
        logger.info("Tutorial walkthrough finished")
        self.stop()

    def _advance_from_next_button(self) -> None:
        """Advance only steps whose typed trigger permits the Next button."""
        if self._awaiting_prerequisite:
            self._awaiting_prerequisite = False
            self._begin_chapter(skip_prerequisite=True)
            return
        step = self._current_step()
        if not self._current_step_allows_next():
            return
        if step.requires is not None and not self._check_completion(step.requires):
            return
        self._advance()

    def _go_back(self) -> None:
        """Step backward without rewinding application state.

        A prerequisite warning and a chapter-head step both retreat into the
        previous chapter's last step, re-applying that chapter's destination.
        """
        self._triggered_step = None
        if not self._awaiting_prerequisite and self._step_index > 0:
            self._step_index -= 1
            self._restore_leading_mode_change_source()
            self._restore_dialog_trigger_source()
            self._show_current_step()
            return
        self._awaiting_prerequisite = False
        self._retreat_to_previous_chapter()

    def _restore_leading_mode_change_source(self) -> None:
        """Restore the prior chapter when Back lands on its already-completed handoff."""
        step = self._current_step()
        if (
            self._step_index != 0
            or self._chapter_index == 0
            or step.advance is not AdvanceTrigger.MODE_CHANGE
            or step.advance_mode is not self._applied_mode
        ):
            return
        previous_destination = self._chapters[self._chapter_index - 1].destination
        if not self._apply_destination(previous_destination):
            logger.warning(
                "Tutorial mode-change source could not be restored: %s",
                self._current_chapter().chapter_id,
            )

    def _dialog_for_current_step(self) -> QDialog | None:
        """Return the retained dialog instance named by the current step."""
        position = (self._chapter_index, self._step_index)
        source_ref = self._dialog_trigger_sources.get(position)
        if source_ref is not None:
            source = source_ref()
            if source is None:
                return None
            try:
                source.objectName()
            except RuntimeError:
                self._dialog_trigger_sources.pop(position, None)
                return None
            else:
                return source
        dialog_name = self._current_step().advance_dialog
        if dialog_name is None:
            return None
        candidates = self._main_window.findChildren(QDialog, dialog_name)
        active = QApplication.activeModalWidget()
        if isinstance(active, QDialog) and active.objectName() == dialog_name:
            return active
        return candidates[-1] if candidates else None

    def _restore_dialog_trigger_source(self) -> None:
        """Restore the pre-event dialog state when Back revisits a fired trigger."""
        step = self._current_step()
        position = (self._chapter_index, self._step_index)
        if (
            step.advance not in (AdvanceTrigger.DIALOG_SHOWN, AdvanceTrigger.DIALOG_HIDDEN)
            or position not in self._completed_dialog_trigger_steps
        ):
            return
        dialog = self._dialog_for_current_step()
        if dialog is None:
            return
        if step.advance is AdvanceTrigger.DIALOG_SHOWN:
            if dialog.isVisible():
                dialog.hide()
            self._completed_dialog_trigger_steps.discard(position)
            return
        if not dialog.isVisible():
            dialog.show()
        self._completed_dialog_trigger_steps.discard(position)

    def _retreat_to_previous_chapter(self) -> None:
        """Resume the nearest previous chapter whose destination still applies."""
        if self._chapter_index == 0:
            self._show_current_step()
            return
        for index in range(self._chapter_index - 1, -1, -1):
            chapter = self._chapters[index]
            # Set before applying: mode switches re-enter notify_mode_changed
            # synchronously, which must not read the abandoned chapter's index.
            self._chapter_index = index
            self._step_index = len(chapter.steps) - 1
            if self._apply_destination(chapter.destination):
                logger.info("Tutorial chapter resumed backward: %s", chapter.chapter_id)
                if self._chapter_context_changed is not None:
                    self._chapter_context_changed(chapter.chapter_id)
                self._restore_dialog_trigger_source()
                self._show_current_step()
                return
            logger.warning(
                "Tutorial chapter skipped backward (destination unavailable): %s",
                chapter.chapter_id,
            )
        self.stop()

    def _ensure_target_visible(self, widget: QWidget) -> None:
        """Scroll only hidden ancestor viewports enough to reveal a tour target."""
        host = widget.window()
        if not widget.isVisibleTo(host):
            return
        for scroll in _ancestor_scroll_areas(widget, host):
            if not _intersects_viewport(widget, scroll):
                scroll.ensureWidgetVisible(widget, _TARGET_SCROLL_MARGIN, _TARGET_SCROLL_MARGIN)

    def _ensure_step_targets_visible(self, targets: Sequence[TutorialSpotlightTarget]) -> None:
        """Reveal step targets without letting RELATED displace PRIMARY."""
        primary = next(
            (
                target
                for target in targets
                if target.prominence is TutorialTargetProminence.PRIMARY
            ),
            None,
        )
        if primary is not None:
            self._ensure_target_visible(primary.widget)
        protect_primary = primary is not None and _is_tutorial_target_visible(
            primary.widget, primary.widget.window()
        )

        for target in targets:
            if target is primary or not target.widget.isVisibleTo(target.widget.window()):
                continue
            scroll_areas = _ancestor_scroll_areas(target.widget, target.widget.window())
            positions = tuple(
                (scroll, scroll.horizontalScrollBar().value(), scroll.verticalScrollBar().value())
                for scroll in scroll_areas
            )
            self._ensure_target_visible(target.widget)
            if (
                protect_primary
                and primary is not None
                and not _is_tutorial_target_visible(primary.widget, primary.widget.window())
            ):
                for scroll, horizontal, vertical in positions:
                    scroll.horizontalScrollBar().setValue(horizontal)
                    scroll.verticalScrollBar().setValue(vertical)

    def _show_current_step(self) -> None:
        chapter = self._current_chapter()
        step = self._current_step()

        resolved_targets: list[TutorialSpotlightTarget] = []
        for target in step.targets:
            widget = self._resolve_target(target)
            if widget is None:
                logger.warning("Tutorial target widget not found: %s", target.object_name)
                continue
            resolved_targets.append(
                TutorialSpotlightTarget(
                    widget=widget, role=target.role, prominence=target.prominence
                )
            )

        host = self._select_host_window(resolved_targets)
        resolved_targets = [
            target for target in resolved_targets if target.widget.window() is host
        ]
        self._ensure_widgets(host)
        overlay = self._overlay
        bubble = self._bubble
        if overlay is None or bubble is None:
            return

        for resolved_target in resolved_targets:
            _expand_ancestor_sections(resolved_target.widget, host)
        self._ensure_step_targets_visible(resolved_targets)
        for resolved_target in resolved_targets:
            if not _is_tutorial_target_visible(resolved_target.widget, host):
                logger.warning(
                    "Tutorial target widget is not visible in its viewport: %s",
                    resolved_target.widget.objectName(),
                )

        overlay.set_targets(resolved_targets)
        overlay.show()
        overlay.raise_()

        progress = f"{self._step_index + 1}/{len(chapter.steps)}"
        self._completion_poll_timer.stop()
        completion_met = False
        completion_note: str | None = None
        if step.requires is not None:
            completion_met = self._check_completion(step.requires)
            completion_note = self._completion_note_for(step.requires)
        self._step_completion_met = completion_met
        self._step_completion_note = completion_note
        bubble.show_step(
            step,
            chapter_title_source=chapter.title_source,
            progress_text=progress,
            checkpoint_source=step.checkpoint_source,
            completion_met=completion_met,
            completion_note=completion_note,
        )
        bubble.set_next_enabled(
            self._current_step_allows_next() and (step.requires is None or completion_met)
        )
        bubble.set_back_enabled(self._chapter_index > 0 or self._step_index > 0)
        bubble.show()
        bubble.raise_()
        self._reposition_bubble()
        if step.requires is not None:
            self._completion_poll_timer.start()

    def _reposition_bubble(self) -> None:
        if self._overlay is None or self._bubble is None:
            return
        self._bubble.place_near(
            self._overlay.primary_spotlight_rect(), avoid_rects=self._overlay.spotlight_rects()
        )
