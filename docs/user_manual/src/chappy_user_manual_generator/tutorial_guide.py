"""Reference page describing the in-app guided tutorial (tutorial tour)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy_user_manual_generator.markdown import MarkdownTableBuilder, format_markdown_text
from chappy_user_manual_generator.translations import translate_manual_text

if TYPE_CHECKING:
    from pathlib import Path

_EXPORTER_CONTEXT = "ManualExporter"
_TUTORIAL_CONTEXT = "Tutorial"


@dataclass(frozen=True, slots=True)
class _WalkthroughSummary:
    button_source: str
    coverage_source: str
    chapter_count: int


@dataclass(frozen=True, slots=True)
class _ChapterSummary:
    chapter_id: str
    title_source: str
    learn_source: str
    has_prerequisite: bool


@dataclass(frozen=True, slots=True)
class _PrerequisiteSummary:
    chapter_id: str
    chapter_source: str
    needs_source: str


PAGE_RELATIVE_PATH = "reference/tutorial.md"

TITLE_SOURCE = QT_TRANSLATE_NOOP("ManualExporter", "Guided Tutorial")
SUMMARY_SOURCE = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "What the in-app guided tour teaches, how it starts, and how to run it again from the"
    " Help menu.",
)

_INTRO = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "chappy includes a guided tour: coach-mark bubbles that highlight one widget at a time and"
    " walk you through the analysis workflow on the bundled sample spectrum of quasar"
    " Q0329-385. It never touches your own data, because it opens the sample spectrum itself"
    " before it starts.",
)

_STARTING_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Starting the Tour")
_STARTING_INTRO = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "The tour is offered through the same [Welcome to chappy] dialog on both occasions below.",
)
_STARTING_ITEMS = (
    QT_TRANSLATE_NOOP(
        "ManualExporter",
        "On the very first launch, chappy shows the dialog automatically, once. If the bundled"
        " sample spectrum is not part of this installation, the dialog still appears but its"
        " two walkthrough buttons are disabled; you can still open your own data from [File] >"
        " [Open Observation Data].",
    ),
    QT_TRANSLATE_NOOP(
        "ManualExporter",
        "Afterward, select [Help] > [Tutorial] to reopen the same dialog at any time and start"
        " the tour again.",
    ),
)
_STARTING_NOTE = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "Choosing a walkthrough opens the sample spectrum (flux and error FITS pair, resolving"
    " power already set) before the first coach mark appears, replacing whatever project was"
    " open.",
)

_WALKTHROUGHS_HEADING = QT_TRANSLATE_NOOP(
    "ManualExporter", "Essential Walkthrough or Advanced Walkthrough"
)
_WALKTHROUGHS_INTRO = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "The dialog offers two separate walkthroughs. The advanced walkthrough continues from"
    " where the essential one leaves off, with no overlap between the two. Each reopens the"
    " sample spectrum and starts independently, so you can run them in separate sessions.",
)
_WALKTHROUGH_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Dialog Button")
_COVERAGE_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Coverage")
_CHAPTER_COUNT_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Chapters")
_WALKTHROUGHS = (
    _WalkthroughSummary(
        QT_TRANSLATE_NOOP("ManualExporter", "[Try the Essential Workflow]"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "The minimal loop: load data, identify one absorption line, fit it, save the project.",
        ),
        5,
    ),
    _WalkthroughSummary(
        QT_TRANSLATE_NOOP("ManualExporter", "[Continue with Advanced Topics]"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Continuing from the essentials: building a custom preset, identifying with the"
            " velocity plot, merging and splitting regions, tying ions together in a joint fit,"
            " and continuum correction.",
        ),
        7,
    ),
)

_CHAPTERS_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Chapters")
_CHAPTERS_INTRO = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "The essential and advanced walkthroughs each run their own chapters, in the order shown"
    " in the two tables below.",
)
_ESSENTIAL_CHAPTERS_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Essential Walkthrough")
_ADVANCED_CHAPTERS_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Advanced Walkthrough")
_NUMBER_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "No.")
_CHAPTER_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Chapter")
_LEARN_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "What You Learn")
_ESSENTIAL_CHAPTERS = (
    _ChapterSummary(
        "getting_started",
        QT_TRANSLATE_NOOP("ManualExporter", "Getting Started"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Navigating the loaded spectrum: wheel/keyboard zoom and pan, rectangle zoom,"
            " undo/redo, typing an exact wavelength range, [Auto Adjust], [Reset View], and"
            " where to open your own data instead.",
        ),
        False,
    ),
    _ChapterSummary(
        "identify",
        QT_TRANSLATE_NOOP("ManualExporter", "Identifying Absorption Lines"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            'Selecting the built-in "Metal Lines" preset, choosing a reference line, marking'
            " a candidate absorption line on the spectrum, and confirming it as a region.",
        ),
        False,
    ),
    _ChapterSummary(
        "analysis",
        QT_TRANSLATE_NOOP("ManualExporter", "Reviewing Analysis Readiness"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Selecting the confirmed region in Analysis Overview and reading its fit readiness.",
        ),
        True,
    ),
    _ChapterSummary(
        "analysis_detail",
        QT_TRANSLATE_NOOP("ManualExporter", "Fitting a Region in Detail"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Opening Analysis Region Detail, adding a fit component to a line, running the"
            " optimizer, and reading the fit outcome.",
        ),
        True,
    ),
    _ChapterSummary(
        "save",
        QT_TRANSLATE_NOOP("ManualExporter", "Saving Your Work"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Saving the project, and a recap of the load, identify, review, fit, and save"
            " loop just completed.",
        ),
        False,
    ),
)
_ADVANCED_CHAPTERS = (
    _ChapterSummary(
        "advanced_intro",
        QT_TRANSLATE_NOOP("ManualExporter", "Continuing from the Essentials"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "That the sample spectrum has been reopened for this walkthrough, replacing"
            " whatever project was open, and what lies ahead: building a custom preset,"
            " identifying with the velocity plot, merging and splitting regions, tying"
            " redshifts together across ions, and correcting the continuum. Completing the"
            " essential walkthrough first is recommended, though not required.",
        ),
        False,
    ),
    _ChapterSummary(
        "preset_build",
        QT_TRANSLATE_NOOP("ManualExporter", "Building a Custom Preset"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Creating a named preset, adding Fe II and Mg II lines to it, linking and"
            " unlinking lines into tie groups, and choosing its reference line.",
        ),
        False,
    ),
    _ChapterSummary(
        "velocity_identify",
        QT_TRANSLATE_NOOP("ManualExporter", "Identifying with the Velocity Plot"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Selecting the custom preset, moving to a second, hidden absorption line in the"
            " sample, and using the velocity plot to identify and confirm it.",
        ),
        True,
    ),
    _ChapterSummary(
        "analysis_structure",
        QT_TRANSLATE_NOOP("ManualExporter", "Merging Regions"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Opening Analysis Structure for two regions, merging them so one region spans more"
            " than one ion species, splitting the Mg II multiplet back out, and re-merging the"
            " regions.",
        ),
        True,
    ),
    _ChapterSummary(
        "joint_fit",
        QT_TRANSLATE_NOOP("ManualExporter", "Tying Ions and Fitting Together"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Building three-component models for both ions, tying their main components'"
            " redshift together, running a joint fit, and fixing the saturated Mg II logN"
            " before fitting again.",
        ),
        True,
    ),
    _ChapterSummary(
        "continuum",
        QT_TRANSLATE_NOOP("ManualExporter", "Correcting the Continuum"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Switching to Continuum mode and running [Auto Estimate] to fit the continuum"
            " around the spectrum, adding and moving a control point, deleting a point, and"
            " undoing those edits.",
        ),
        False,
    ),
    _ChapterSummary(
        "save",
        QT_TRANSLATE_NOOP("ManualExporter", "Saving Your Work"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Saving the project, and a recap of the preset-building, velocity-plot"
            " identification, region-editing, cross-ion tying, and continuum-correction work"
            " just completed.",
        ),
        False,
    ),
)

_PREREQUISITES_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Chapter Prerequisites")
_PREREQUISITES_INTRO = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "Five chapters open only after earlier chapters have left the project in the state they"
    " need. When a chapter's prerequisite is unmet, the tour shows a warning bubble instead of"
    " that chapter's first step, offering [Back] to return to the previous step or [Continue"
    " anyway] to ignore the prerequisite and start that chapter from its first step.",
)
_PREREQ_CHAPTER_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Chapter")
_PREREQ_CONDITION_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Needs")
_PREREQUISITES = (
    _PrerequisiteSummary(
        "analysis",
        QT_TRANSLATE_NOOP("ManualExporter", "Reviewing Analysis Readiness"),
        QT_TRANSLATE_NOOP("ManualExporter", "At least one confirmed absorption region."),
    ),
    _PrerequisiteSummary(
        "analysis_detail",
        QT_TRANSLATE_NOOP("ManualExporter", "Fitting a Region in Detail"),
        QT_TRANSLATE_NOOP("ManualExporter", "At least one confirmed absorption region."),
    ),
    _PrerequisiteSummary(
        "velocity_identify",
        QT_TRANSLATE_NOOP("ManualExporter", "Identifying with the Velocity Plot"),
        QT_TRANSLATE_NOOP("ManualExporter", "A custom preset created in an earlier chapter."),
    ),
    _PrerequisiteSummary(
        "analysis_structure",
        QT_TRANSLATE_NOOP("ManualExporter", "Merging Regions"),
        QT_TRANSLATE_NOOP("ManualExporter", "At least two confirmed absorption regions."),
    ),
    _PrerequisiteSummary(
        "joint_fit",
        QT_TRANSLATE_NOOP("ManualExporter", "Tying Ions and Fitting Together"),
        QT_TRANSLATE_NOOP("ManualExporter", "A region that combines two or more ion species."),
    ),
)

_CONTROLS_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Step Controls")
_CONTROLS_INTRO = QT_TRANSLATE_NOOP(
    "ManualExporter",
    "Every coach-mark bubble carries the same controls, alongside the step's instruction and"
    " expected result.",
)
_CONTROL_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Control")
_EFFECT_COLUMN = QT_TRANSLATE_NOOP("ManualExporter", "Effect")
_CONTROL_LABEL_FORMAT = QT_TRANSLATE_NOOP("ManualExporter", "[{label}]")
_CONTROLS = (
    (
        QT_TRANSLATE_NOOP("Tutorial", "Next"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Advances to the next step. On a step that checks for a specific action (for"
            " example, confirming a region or linking preset lines), [Next] stays disabled and"
            " the expected-result line stays unchecked until that action is performed;"
            " performing it enables [Next] without advancing automatically, so you can read the"
            " confirmation first.",
        ),
    ),
    (
        QT_TRANSLATE_NOOP("Tutorial", "Back"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Returns to the previous step, or to the previous chapter's last step at a"
            " chapter's first step. It does not undo anything you did in the application.",
        ),
    ),
    (
        QT_TRANSLATE_NOOP("Tutorial", "Exit Tour"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Closes the tour immediately, keeping whatever the tour has done to the project so"
            " far.",
        ),
    ),
    (
        QT_TRANSLATE_NOOP("Tutorial", "What is this?"),
        QT_TRANSLATE_NOOP(
            "ManualExporter",
            "Shown only on steps that carry background information beyond the instruction"
            " itself; expands or collapses that note in place.",
        ),
    ),
)

_ENDING_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Ending and Restarting")
_ENDING_NOTES = (
    QT_TRANSLATE_NOOP(
        "ManualExporter",
        "> [!NOTE]\n> The tour keeps no memory of where you stopped. Whether you close it with"
        " [Exit Tour] or quit chappy, the next walkthrough you start from [Help] > [Tutorial]"
        " begins again at its own first chapter and reopens the sample spectrum. Switching"
        " modes yourself does not end the tour, but the widget the current step points at is"
        " no longer on screen; switch back to the mode the chapter is guiding to see the coach"
        " mark again.",
    ),
)

_NOTES_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Tips and Best Practices")
_NOTES = (
    QT_TRANSLATE_NOOP(
        "ManualExporter",
        "> [!TIP]\n> The tour targets specific widgets by name. If a step's highlighted area"
        " looks empty, the window may be too narrow to show that widget; enlarge the window or"
        " reveal the collapsed panel it belongs to.",
    ),
)

_RELATED_HEADING = QT_TRANSLATE_NOOP("ManualExporter", "Related References")
_RELATED_MENU_LABEL = QT_TRANSLATE_NOOP("ManualExporter", "Menu List")
_RELATED_MENU_PATH = "../menus/main_window/menus.md"
_RELATED_START_LABEL = QT_TRANSLATE_NOOP("ManualExporter", "Load Data into the Application")
_RELATED_START_PATH = "../operations/start-data-import.md"


def export_tutorial_guide(*, out_dir: Path) -> Path:
    """Write the guided-tutorial reference page under ``out_dir`` and return its path."""

    def tr(source_text: str) -> str:
        return translate_manual_text(_EXPORTER_CONTEXT, source_text)

    lines: list[str] = [f"# {tr(TITLE_SOURCE)}", "", tr(_INTRO), ""]

    lines.extend([f"## {tr(_STARTING_HEADING)}", "", tr(_STARTING_INTRO), ""])
    lines.extend(f"- {tr(item)}" for item in _STARTING_ITEMS)
    lines.extend(["", tr(_STARTING_NOTE)])

    lines.extend(["", f"## {tr(_WALKTHROUGHS_HEADING)}", "", tr(_WALKTHROUGHS_INTRO)])
    walkthrough_table = MarkdownTableBuilder(
        [tr(_WALKTHROUGH_COLUMN), tr(_COVERAGE_COLUMN), tr(_CHAPTER_COUNT_COLUMN)]
    )
    walkthrough_table.extend(
        (tr(row.button_source), tr(row.coverage_source), str(row.chapter_count))
        for row in _WALKTHROUGHS
    )
    lines.extend(walkthrough_table.lines())

    lines.extend(["", f"## {tr(_CHAPTERS_HEADING)}", "", tr(_CHAPTERS_INTRO)])
    for heading, chapters in (
        (_ESSENTIAL_CHAPTERS_HEADING, _ESSENTIAL_CHAPTERS),
        (_ADVANCED_CHAPTERS_HEADING, _ADVANCED_CHAPTERS),
    ):
        lines.extend(["", f"### {tr(heading)}", ""])
        chapters_table = MarkdownTableBuilder(
            [tr(_NUMBER_COLUMN), tr(_CHAPTER_COLUMN), tr(_LEARN_COLUMN)]
        )
        chapters_table.extend(
            (str(number), tr(chapter.title_source), tr(chapter.learn_source))
            for number, chapter in enumerate(chapters, 1)
        )
        lines.extend(chapters_table.lines())

    lines.extend(["", f"## {tr(_PREREQUISITES_HEADING)}", "", tr(_PREREQUISITES_INTRO)])
    prereq_table = MarkdownTableBuilder([tr(_PREREQ_CHAPTER_COLUMN), tr(_PREREQ_CONDITION_COLUMN)])
    prereq_table.extend(
        (tr(prerequisite.chapter_source), tr(prerequisite.needs_source))
        for prerequisite in _PREREQUISITES
    )
    lines.extend(prereq_table.lines())

    lines.extend(["", f"## {tr(_CONTROLS_HEADING)}", "", tr(_CONTROLS_INTRO)])
    controls_table = MarkdownTableBuilder([tr(_CONTROL_COLUMN), tr(_EFFECT_COLUMN)])
    controls_table.extend(
        (
            tr(_CONTROL_LABEL_FORMAT).format(
                label=translate_manual_text(_TUTORIAL_CONTEXT, control_source)
            ),
            tr(effect),
        )
        for control_source, effect in _CONTROLS
    )
    lines.extend(controls_table.lines())

    lines.extend(["", f"## {tr(_ENDING_HEADING)}", ""])
    for index, note in enumerate(_ENDING_NOTES):
        if index:
            lines.append("")
        lines.append(tr(note))

    lines.extend(["", f"## {tr(_NOTES_HEADING)}", ""])
    for index, note in enumerate(_NOTES):
        if index:
            lines.append("")
        lines.append(tr(note))

    lines.extend(
        [
            "",
            f"## {tr(_RELATED_HEADING)}",
            "",
            f"- [{tr(_RELATED_START_LABEL)}]({_RELATED_START_PATH})",
            f"- [{tr(_RELATED_MENU_LABEL)}]({_RELATED_MENU_PATH})",
            "",
        ]
    )

    path = out_dir / "tutorial.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = format_markdown_text("\n".join(lines) + "\n")
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")
    return path
