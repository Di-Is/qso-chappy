"""Developer override that starts the guided tour at a chosen walkthrough chapter.

``CHAPPY_TUTORIAL_WALKTHROUGH`` selects ``essential`` or ``advanced`` and
``CHAPPY_TUTORIAL_START_CHAPTER`` names the chapter to start from, so a
developer can debug a late chapter against an already prepared project
instead of replaying every earlier step.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from chappy.gui.shell.tutorial_chapters import (
    build_advanced_walkthrough_chapters,
    build_essential_walkthrough_chapters,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.common.tutorial import TutorialChapter

logger = logging.getLogger(__name__)

WALKTHROUGH_ENV = "CHAPPY_TUTORIAL_WALKTHROUGH"
START_CHAPTER_ENV = "CHAPPY_TUTORIAL_START_CHAPTER"

_WALKTHROUGH_BUILDERS: dict[str, Callable[[], tuple[TutorialChapter, ...]]] = {
    "essential": build_essential_walkthrough_chapters,
    "advanced": build_advanced_walkthrough_chapters,
}


def resolve_tutorial_start_chapters() -> tuple[TutorialChapter, ...] | None:
    """Return the chapters to run from the requested start chapter.

    Returns:
        The selected walkthrough truncated to begin at the requested chapter,
        or ``None`` when neither environment variable is set or their values
        cannot be resolved, in which case the caller keeps its normal flow.
    """
    walkthrough_name = (os.getenv(WALKTHROUGH_ENV) or "").strip()
    chapter_id = (os.getenv(START_CHAPTER_ENV) or "").strip()
    if not walkthrough_name and not chapter_id:
        return None
    if not walkthrough_name or not chapter_id:
        logger.warning(
            "Tutorial start override ignored: %s and %s must both be set (got %s=%r, %s=%r)",
            WALKTHROUGH_ENV,
            START_CHAPTER_ENV,
            WALKTHROUGH_ENV,
            walkthrough_name,
            START_CHAPTER_ENV,
            chapter_id,
        )
        return None

    build_chapters = _WALKTHROUGH_BUILDERS.get(walkthrough_name.lower())
    if build_chapters is None:
        logger.warning(
            "Tutorial start override ignored: unknown %s value %r (expected one of %s)",
            WALKTHROUGH_ENV,
            walkthrough_name,
            ", ".join(sorted(_WALKTHROUGH_BUILDERS)),
        )
        return None

    chapters = build_chapters()
    for index, chapter in enumerate(chapters):
        if chapter.chapter_id == chapter_id:
            logger.info(
                "Tutorial start override active: walkthrough %s from chapter %s",
                walkthrough_name.lower(),
                chapter_id,
            )
            return chapters[index:]

    logger.warning(
        "Tutorial start override ignored: unknown %s value %r in walkthrough %s"
        " (known chapters: %s)",
        START_CHAPTER_ENV,
        chapter_id,
        walkthrough_name.lower(),
        ", ".join(chapter.chapter_id for chapter in chapters),
    )
    return None


__all__ = ["START_CHAPTER_ENV", "WALKTHROUGH_ENV", "resolve_tutorial_start_chapters"]
