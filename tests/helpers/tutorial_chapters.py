"""Chapter collections spanning both guided walkthroughs.

The essential and advanced walkthroughs are built separately, so tests that
must not miss a chapter (target resolution, destinations, shared operations,
completion coverage) walk the concatenation instead of a single builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.gui.shell.tutorial_chapters import (
    build_advanced_walkthrough_chapters,
    build_essential_walkthrough_chapters,
)

if TYPE_CHECKING:
    from chappy.gui.common.tutorial import TutorialChapter, TutorialStep


def all_walkthrough_chapters() -> tuple[TutorialChapter, ...]:
    """Return every chapter of the essential walkthrough followed by the advanced one."""
    return build_essential_walkthrough_chapters() + build_advanced_walkthrough_chapters()


def all_walkthrough_steps() -> tuple[TutorialStep, ...]:
    """Return every step of both walkthroughs, in chapter order."""
    return tuple(step for chapter in all_walkthrough_chapters() for step in chapter.steps)


def chapter_steps_by_id() -> dict[str, tuple[TutorialStep, ...]]:
    """Return each chapter id mapped to its steps, concatenated across both walkthroughs."""
    grouped: dict[str, tuple[TutorialStep, ...]] = {}
    for chapter in all_walkthrough_chapters():
        grouped[chapter.chapter_id] = grouped.get(chapter.chapter_id, ()) + chapter.steps
    return grouped
