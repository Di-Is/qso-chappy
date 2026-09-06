"""Consistency checks between tutorial documentation and runtime chapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from chappy_user_manual_generator.tutorial_guide import (
    _ADVANCED_CHAPTERS,
    _ESSENTIAL_CHAPTERS,
    _PREREQUISITES,
    _WALKTHROUGHS,
)

from chappy.gui.shell.tutorial_chapters import (
    build_advanced_walkthrough_chapters,
    build_essential_walkthrough_chapters,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy_user_manual_generator.tutorial_guide import _ChapterSummary, _WalkthroughSummary

    from chappy.gui.common.tutorial import TutorialChapter

_WALKTHROUGH_TABLES: tuple[
    tuple[Callable[[], tuple[TutorialChapter, ...]], tuple[_ChapterSummary, ...]], ...
] = (
    (build_essential_walkthrough_chapters, _ESSENTIAL_CHAPTERS),
    (build_advanced_walkthrough_chapters, _ADVANCED_CHAPTERS),
)
_WALKTHROUGH_SUMMARIES = tuple(
    (build_chapters, documented, summary)
    for (build_chapters, documented), summary in zip(
        _WALKTHROUGH_TABLES, _WALKTHROUGHS, strict=True
    )
)


@pytest.mark.parametrize(("build_chapters", "documented", "summary"), _WALKTHROUGH_SUMMARIES)
def test_walkthrough_chapter_counts_match_runtime(
    build_chapters: Callable[[], tuple[TutorialChapter, ...]],
    documented: tuple[_ChapterSummary, ...],
    summary: _WalkthroughSummary,
) -> None:
    """Keep each displayed chapter count synchronized with its builder and table."""
    chapters = build_chapters()

    assert len(chapters) == summary.chapter_count
    assert len(chapters) == len(documented)


@pytest.mark.parametrize(("build_chapters", "documented"), _WALKTHROUGH_TABLES)
def test_chapter_ids_and_order_match_runtime(
    build_chapters: Callable[[], tuple[TutorialChapter, ...]],
    documented: tuple[_ChapterSummary, ...],
) -> None:
    """Keep each documented chapter table synchronized with its walkthrough."""
    documented_ids = tuple(chapter.chapter_id for chapter in documented)

    assert tuple(chapter.chapter_id for chapter in build_chapters()) == documented_ids


@pytest.mark.parametrize(("build_chapters", "documented"), _WALKTHROUGH_TABLES)
def test_chapter_prerequisite_presence_matches_runtime(
    build_chapters: Callable[[], tuple[TutorialChapter, ...]],
    documented: tuple[_ChapterSummary, ...],
) -> None:
    """Keep each table's per-chapter prerequisite markers synchronized with runtime."""
    runtime_presence = tuple(
        (chapter.chapter_id, chapter.prerequisite is not None) for chapter in build_chapters()
    )
    documented_presence = tuple(
        (chapter.chapter_id, chapter.has_prerequisite) for chapter in documented
    )

    assert runtime_presence == documented_presence


def test_prerequisite_rows_match_runtime_across_both_walkthroughs() -> None:
    """The single prerequisite table lists every gated chapter, in walkthrough order."""
    runtime_prerequisite_ids = tuple(
        chapter.chapter_id
        for chapter in build_essential_walkthrough_chapters()
        + build_advanced_walkthrough_chapters()
        if chapter.prerequisite is not None
    )
    documented_prerequisite_ids = tuple(prerequisite.chapter_id for prerequisite in _PREREQUISITES)

    assert runtime_prerequisite_ids == documented_prerequisite_ids
