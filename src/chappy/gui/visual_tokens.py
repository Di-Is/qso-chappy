"""Visual design tokens aligned with SCR-COM shared UI specification.

This module centralizes size, color, and timing constants referenced
throughout the GUI so that layout code can depend on a single source
of truth instead of duplicating literal values.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DialogMetrics",
    "LayoutMetrics",
    "ModeContextColors",
    "NotificationColors",
    "SidePanelMetrics",
]


@dataclass(frozen=True)
class LayoutMetrics:
    """Shared layout metrics pulled from SCR-COM visual constants."""

    CTXBAR_HEIGHT: int = 50
    STATUSBAR_HEIGHT: int = 25
    DATACONTROL_HEIGHT: int = 48

    SIDEPANEL_WIDTH: int = 540

    # Normative Analysis right-stack minimum width (visual_constants.md
    # SIZE.ANALYSIS.RIGHT.MIN.WIDTH).
    ANALYSIS_RIGHT_MIN_WIDTH: int = 220

    SPECTRUM_MIN_HEIGHT: int = 240
    SPECTRUM_MIN_WIDTH: int = 240

    NUMERIC_INPUT_WIDTH: int = 80
    NUMERIC_INPUT_MIN_WIDTH: int = 76
    SEPARATOR_THIN: int = 1


@dataclass(frozen=True)
class SidePanelMetrics:
    """Standardized layout values for side panel widgets."""

    OUTER_MARGIN: tuple[int, int, int, int] = (12, 12, 12, 12)
    OUTER_SPACING: int = 12
    SECTION_SPACING: int = 12
    CARD_CONTENT_MARGIN: tuple[int, int, int, int] = (12, 12, 12, 12)
    BUTTON_ROW_SPACING: int = 8
    PLACEHOLDER_PADDING: int = 24
    PRIMARY_BUTTON_WIDTH: int = 156
    SECONDARY_BUTTON_MIN_WIDTH: int = 120
    ACTION_CARD_COMPACT_SPACING: int = 8
    COLLAPSIBLE_HEADER_SPACING: int = 8
    SPLITTER_HANDLE_WIDTH: int = 6
    IDENTIFY_SPLITTER_RATIO: tuple[int, int, int] = (6, 3, 2)
    IDENTIFY_TEMPORARY_MIN_VISIBLE_ROWS: int = 3


class ModeContextColors:
    """Mode-tinted surface colors.

    The context bar no longer tints per mode (its info pill uses a neutral
    surface); only the start-mode structure overlay keeps a mode tint.
    """

    ORGANIZE = "#3C4248"


class NotificationColors:
    """Status/notification color tokens."""

    INFO = "#17A2B8"
    WARNING = "#FFA500"
    ERROR = "#DC3545"
    SUCCESS = "#28A745"


class DialogMetrics:
    """Dialog size constraints from SCR-COM visual constants.

    Also includes measured content floors for dialogs whose content exceeds
    the shared tokens.
    """

    MIN_WIDTH_SMALL: int = 360
    MIN_HEIGHT_SMALL: int = 200
    MIN_WIDTH_DEFAULT: int = 400
    MIN_HEIGHT_DEFAULT: int = 250

    MIN_SIZE_FILE_TYPE_SELECTION: tuple[int, int] = (600, 400)
    MIN_SIZE_MASTER_DATABASE_LIST: tuple[int, int] = (640, 480)
    MIN_SIZE_MASTER_DATABASE_DETAIL: tuple[int, int] = (700, 500)
    MIN_SIZE_PARAMETER_ADJUSTMENT: tuple[int, int] = (700, 300)
    MIN_SIZE_PRESET_LIST: tuple[int, int] = (840, 560)
    INITIAL_SIZE_PRESET_LIST: tuple[int, int] = (960, 640)
    MIN_SIZE_LINE_SELECTION: tuple[int, int] = (1060, 640)
