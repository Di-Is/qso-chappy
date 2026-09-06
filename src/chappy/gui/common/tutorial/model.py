"""Data model for guided-tour chapters and steps.

Text fields hold untranslated source strings registered with
``QT_TRANSLATE_NOOP("Tutorial", ...)``; rendering widgets translate them
via ``QCoreApplication.translate("Tutorial", source)`` so language changes
apply immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy.core.components.optimize import FitOutcome
from chappy.core.editing_mode import EditingMode
from chappy.gui.common.shared_operations import (
    AnalysisOperationPanel,
    AnalysisOperationSurface,
    OperationScope,
)

if TYPE_CHECKING:
    from chappy.gui.common.shared_operations import SharedOperation

TUTORIAL_TR_CONTEXT = "Tutorial"


class AdvanceTrigger(Enum):
    """How a tutorial step advances to the next one."""

    NEXT_BUTTON = auto()
    MODE_CHANGE = auto()
    DIALOG_SHOWN = auto()
    DIALOG_HIDDEN = auto()


_DIALOG_TRIGGERS = frozenset({AdvanceTrigger.DIALOG_SHOWN, AdvanceTrigger.DIALOG_HIDDEN})


class TutorialCompletion(Enum):
    """Declarative condition proving a required step's action was performed.

    The predicate behind each member is injected into the tour controller as
    a resolution table; this model layer never inspects application state.
    """

    METAL_LINES_PRESET_SELECTED = auto()
    REFERENCE_LINE_IS_CIV1548 = auto()
    CONFIRMED_REGION_EXISTS = auto()
    NEW_TUTORIAL_PRESET_SELECTED = auto()
    PRESET_HAS_TUTORIAL_LINES = auto()
    PRESET_FE2_UNLINKED = auto()
    PRESET_FE2_SINGLE_GROUP = auto()
    PRESET_BASELINE_IS_MG2796 = auto()
    TUTORIAL_PRESET_SELECTED = auto()
    VELOCITY_PLOT_VISIBLE = auto()
    VELOCITY_SLICES_SELECTED = auto()
    FE2_AND_MG2_REGIONS_EXIST = auto()
    MULTI_ION_REGION_EXISTS = auto()
    MONO_ION_REGIONS_RESTORED = auto()
    REGION_DETAIL_OPENED = auto()
    REGION_HAS_COMPONENT = auto()
    TUTORIAL_MULTI_ION_REGION_OPENED = auto()
    FE2_COMPONENT_EXISTS = auto()
    MG2_COMPONENT_EXISTS = auto()
    FE2_AND_MG2_HAVE_THREE_COMPONENTS = auto()
    CROSS_ION_Z_TIE_EXISTS = auto()
    REGION_FIT_APPLIED = auto()
    MG2_LOGN_FIXED = auto()


FIT_OUTCOME_NOTE_SOURCES: dict[FitOutcome, str] = {
    FitOutcome.CONVERGED: str(QT_TRANSLATE_NOOP("Tutorial", "The fit converged.")),
    FitOutcome.CONVERGED_UNCERTAIN: str(
        QT_TRANSLATE_NOOP(
            "Tutorial", "The fit converged, but the parameter uncertainties are large."
        )
    ),
    FitOutcome.BUDGET_STOPPED_GOOD: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "The fit stopped at the iteration limit with a usable result."
            " Selecting [Fit] again resumes from here.",
        )
    ),
    FitOutcome.BOUNDARY: str(
        QT_TRANSLATE_NOOP(
            "Tutorial", "A parameter settled on its bound. The next step addresses this."
        )
    ),
    FitOutcome.DEGENERATE: str(
        QT_TRANSLATE_NOOP(
            "Tutorial", "The parameters are degenerate, so the result was not applied."
        )
    ),
    FitOutcome.NUMERICAL: str(
        QT_TRANSLATE_NOOP("Tutorial", "The fit failed numerically, so the result was not applied.")
    ),
    FitOutcome.BUDGET_STOPPED_STUCK: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "The fit stopped at the iteration limit without improving, so the"
            " result was not applied.",
        )
    ),
    FitOutcome.NO_FREE_PARAMS: str(
        QT_TRANSLATE_NOOP("Tutorial", "There is no free parameter to fit.")
    ),
}


COMPLETION_NOTE_SOURCES: dict[TutorialCompletion, str] = {
    TutorialCompletion.NEW_TUTORIAL_PRESET_SELECTED: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "No new preset from this tour is selected yet. Create one with [New]"
            " so it becomes the selected preset.",
        )
    ),
    TutorialCompletion.PRESET_HAS_TUTORIAL_LINES: str(
        #: Keep {fe2_count} and {mg2_count} unchanged; they are replaced with live counts.
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "This step needs exactly 4 Fe II lines and 2 Mg II lines in the preset"
            " (it currently holds Fe II {fe2_count}, Mg II {mg2_count}). Reopen"
            " [Add Line] to add the missing ones, or remove the extra rows.",
        )
    ),
    TutorialCompletion.PRESET_FE2_UNLINKED: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "At least one Fe II line still belongs to a link. Select the four Fe II"
            " rows and click [Unlink].",
        )
    ),
    TutorialCompletion.PRESET_FE2_SINGLE_GROUP: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "The four Fe II lines must share one link, and the two Mg II lines"
            " another. Select the four Fe II rows and click [Link selected lines];"
            " if the Mg II link is gone, select the two Mg II rows and link them"
            " the same way.",
        )
    ),
    TutorialCompletion.PRESET_BASELINE_IS_MG2796: str(
        QT_TRANSLATE_NOOP(
            "Tutorial", "[Reference line] must be Mg II 2796; choose it in the selector."
        )
    ),
    TutorialCompletion.FE2_AND_MG2_REGIONS_EXIST: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "Confirmed Regions does not yet hold both a 4-line Fe II region and a"
            " 2-line Mg II region. Registration makes one region per preset link,"
            " so check that all four Fe II lines were added to the temporary list"
            " and that they share one link in the preset.",
        )
    ),
    TutorialCompletion.MG2_LOGN_FIXED: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "Mg II's logN is not fixed yet. Right-click the main Mg II component"
            " in the parameter tree and tick the entry that starts with [Fix logN].",
        )
    ),
}


class TutorialPrerequisite(Enum):
    """Declarative project-state condition a chapter expects on entry.

    The predicate behind each member is injected into the tour controller
    as a resolution table; this model layer never inspects project state.
    """

    HAS_CONFIRMED_REGION = auto()
    HAS_TOUR_CREATED_PRESET = auto()
    HAS_TWO_REGIONS = auto()
    HAS_TUTORIAL_MULTI_ION_REGION = auto()


PREREQUISITE_WARNING_SOURCES: dict[TutorialPrerequisite, str] = {
    TutorialPrerequisite.HAS_CONFIRMED_REGION: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "This chapter works on a registered absorption region, but"
            " none has been registered yet.",
        )
    ),
    TutorialPrerequisite.HAS_TOUR_CREATED_PRESET: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "This chapter works on the custom preset created during this tour,"
            " but it is not selected or no longer exists.",
        )
    ),
    TutorialPrerequisite.HAS_TWO_REGIONS: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "This chapter works on the Fe II and Mg II regions, but fewer"
            " than two absorption regions are registered.",
        )
    ),
    TutorialPrerequisite.HAS_TUTORIAL_MULTI_ION_REGION: str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "This chapter works on the merged region containing the six tutorial"
            " lines, but that region is not available.",
        )
    ),
}


class TutorialTargetRole(Enum):
    """How a highlighted widget contributes to a tutorial step."""

    INTERACT = auto()
    OBSERVE = auto()
    CONTEXT = auto()


class TutorialTargetProminence(Enum):
    """Visual importance of a highlighted widget."""

    PRIMARY = auto()
    RELATED = auto()


@dataclass(frozen=True, slots=True)
class TutorialTarget:
    """Semantic reference to one widget highlighted by a tutorial step.

    Attributes:
        object_name: Preferred widget object name.
        fallback_object_names: Object names tried, in order, when
            ``object_name`` resolves to no reachable widget, so a step whose
            target lives in a dialog the user closed keeps a visible anchor.
        role: How the widget contributes to the step.
        prominence: Visual importance of the widget.
    """

    object_name: str
    role: TutorialTargetRole
    prominence: TutorialTargetProminence
    fallback_object_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject names and enum values that cannot be resolved safely."""
        if not isinstance(self.fallback_object_names, tuple):
            msg = "Tutorial target fallback_object_names must be a tuple."
            raise TypeError(msg)
        for name in (self.object_name, *self.fallback_object_names):
            if not name or name != name.strip():
                msg = "Tutorial target object names must be non-empty trimmed strings."
                raise ValueError(msg)
        if not isinstance(self.role, TutorialTargetRole):
            msg = "Tutorial target role must be a TutorialTargetRole."
            raise TypeError(msg)
        if not isinstance(self.prominence, TutorialTargetProminence):
            msg = "Tutorial target prominence must be a TutorialTargetProminence."
            raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class TutorialDestination:
    """Semantic workspace destination applied before a tutorial chapter."""

    mode: EditingMode | None = None
    surface: AnalysisOperationSurface | None = None
    panel: AnalysisOperationPanel | None = None

    def __post_init__(self) -> None:
        """Reject incomplete or contradictory Analysis destinations."""
        has_analysis_location = self.surface is not None or self.panel is not None
        if self.mode is not EditingMode.ANALYSIS:
            if has_analysis_location:
                msg = "Only an Analysis tutorial destination may define surface or panel."
                raise ValueError(msg)
            return
        if self.surface is None or self.panel is None:
            msg = "An Analysis tutorial destination requires both surface and panel."
            raise ValueError(msg)

        expected_surface = {
            AnalysisOperationPanel.SUMMARY: AnalysisOperationSurface.OVERVIEW,
            AnalysisOperationPanel.STRUCTURE: AnalysisOperationSurface.OVERVIEW,
            AnalysisOperationPanel.DETAIL: AnalysisOperationSurface.REGION_DETAIL,
        }[self.panel]
        if self.surface is not expected_surface:
            msg = (
                f"Analysis tutorial panel {self.panel.value!r} requires "
                f"surface {expected_surface.value!r}."
            )
            raise ValueError(msg)

    def operation_scope(self) -> OperationScope:
        """Return the corresponding shared-operation scope."""
        return OperationScope(
            mode=self.mode, analysis_surface=self.surface, analysis_panel=self.panel
        )


@dataclass(frozen=True, slots=True)
class TutorialStep:
    """One coach-mark step with semantically described highlighted widgets.

    Attributes:
        targets: Widgets involved in this step. An empty tuple produces a
            centered, target-less bubble. A non-empty tuple must contain
            exactly one primary target, which anchors the bubble.
        action_source: Untranslated instruction text.
        expected_source: Untranslated expected-result text.
        domain_note_source: Optional untranslated "What is this?" note.
        advance: How the step advances.
        advance_mode: Editing mode whose activation advances the step when
            ``advance`` is ``MODE_CHANGE``.
        advance_dialog: Object name of the modal dialog whose show or hide
            advances the step when ``advance`` is ``DIALOG_SHOWN`` or
            ``DIALOG_HIDDEN``.
        requires: Optional completion condition proving the step's action was
            performed. It gates every way out of the step: a ``NEXT_BUTTON``
            step keeps its button disabled while unmet, and a signal-driven
            step stays put when its mode or dialog trigger fires too early.
            A met condition never advances the step on its own, so the user
            can read the confirmation before moving on.
        checkpoint_source: Optional untranslated checkpoint question shown
            with this step, asking whether the work it completes succeeded.
        operation: Optional shared operation this step also documents in the
            user manual's operation tables. Its facts (target/action/expected)
            are single-sourced from ``chappy.gui.common.shared_operations``;
            this step's own text fields are unaffected.
    """

    targets: tuple[TutorialTarget, ...]
    action_source: str
    expected_source: str
    domain_note_source: str | None = None
    advance: AdvanceTrigger = AdvanceTrigger.NEXT_BUTTON
    advance_mode: EditingMode | None = None
    advance_dialog: str | None = None
    requires: TutorialCompletion | None = None
    checkpoint_source: str | None = None
    operation: SharedOperation | None = None

    def __post_init__(self) -> None:
        """Validate target and trigger invariants."""
        if not isinstance(self.targets, tuple):
            msg = "Tutorial step targets must be a tuple."
            raise TypeError(msg)
        if any(not isinstance(target, TutorialTarget) for target in self.targets):
            msg = "Tutorial step targets must contain only TutorialTarget values."
            raise TypeError(msg)
        duplicate_names = {
            target.object_name
            for target in self.targets
            if sum(item.object_name == target.object_name for item in self.targets) > 1
        }
        if duplicate_names:
            duplicates = ", ".join(sorted(duplicate_names))
            msg = f"Tutorial step target object names must be unique: {duplicates}."
            raise ValueError(msg)
        primary_count = sum(
            target.prominence is TutorialTargetProminence.PRIMARY for target in self.targets
        )
        if self.targets and primary_count != 1:
            msg = "A tutorial step with targets must define exactly one PRIMARY target."
            raise ValueError(msg)
        if (self.advance is AdvanceTrigger.MODE_CHANGE) != (self.advance_mode is not None):
            msg = "advance_mode must be set exactly when advance is MODE_CHANGE"
            raise ValueError(msg)
        if (self.advance in _DIALOG_TRIGGERS) != (self.advance_dialog is not None):
            msg = "advance_dialog must be set exactly when advance is DIALOG_SHOWN/DIALOG_HIDDEN"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class TutorialChapter:
    """A walkthrough chapter tied to one editing mode.

    Attributes:
        chapter_id: Stable identifier used for progress persistence.
        title_source: Untranslated chapter title.
        destination: Semantic mode/surface/panel applied before the chapter.
        steps: Ordered steps of the chapter.
        prerequisite: Optional project-state condition evaluated before the
            chapter's destination is applied; when unmet the tour shows a
            soft-block warning instead of starting the chapter.
    """

    chapter_id: str
    title_source: str
    destination: TutorialDestination
    steps: tuple[TutorialStep, ...]
    prerequisite: TutorialPrerequisite | None = None

    def __post_init__(self) -> None:
        """Validate that the chapter has content."""
        if not self.steps:
            msg = f"chapter {self.chapter_id} has no steps"
            raise ValueError(msg)
        global_scope = OperationScope.global_scope()
        destination_scope = self.destination.operation_scope()
        for step in self.steps:
            if step.operation is None or step.operation.scope == global_scope:
                continue
            if step.operation.scope == destination_scope:
                continue
            same_analysis_surface = (
                step.operation.scope.mode is destination_scope.mode is EditingMode.ANALYSIS
                and step.operation.scope.analysis_surface is destination_scope.analysis_surface
            )
            if not same_analysis_surface:
                msg = (
                    f"chapter {self.chapter_id!r} destination does not match shared "
                    f"operation {step.operation.op_id!r} scope"
                )
                raise ValueError(msg)
