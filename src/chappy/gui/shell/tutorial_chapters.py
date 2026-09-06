"""Walkthrough chapter definitions for the guided tour.

Step texts follow docs/task/onboarding-tutorial/steps.md. The bundled
sample (Q0329-385) is opened by the welcome dialog before the tour
starts, so chapter 1 explains the loaded data instead of the load
operation itself.
"""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy.core.editing_mode import EditingMode
from chappy.gui.common.shared_operations import (
    AnalysisOperationPanel,
    AnalysisOperationSurface,
    get_shared_operation,
)
from chappy.gui.common.tutorial import (
    AdvanceTrigger,
    TutorialChapter,
    TutorialCompletion,
    TutorialDestination,
    TutorialPrerequisite,
    TutorialStep,
    TutorialTarget,
    TutorialTargetProminence,
    TutorialTargetRole,
)

_NO_DESTINATION = TutorialDestination()
_IDENTIFY_DESTINATION = TutorialDestination(mode=EditingMode.IDENTIFY)
_CONTINUUM_DESTINATION = TutorialDestination(mode=EditingMode.CONTINUUM)
_ANALYSIS_OVERVIEW_DESTINATION = TutorialDestination(
    mode=EditingMode.ANALYSIS,
    surface=AnalysisOperationSurface.OVERVIEW,
    panel=AnalysisOperationPanel.SUMMARY,
)
_ANALYSIS_DETAIL_DESTINATION = TutorialDestination(
    mode=EditingMode.ANALYSIS,
    surface=AnalysisOperationSurface.REGION_DETAIL,
    panel=AnalysisOperationPanel.DETAIL,
)


def _primary_target(object_name: str, *fallback_object_names: str) -> TutorialTarget:
    """Return a single primary interactive target with optional resolution fallbacks."""
    return TutorialTarget(
        object_name=object_name,
        role=TutorialTargetRole.INTERACT,
        prominence=TutorialTargetProminence.PRIMARY,
        fallback_object_names=fallback_object_names,
    )


def _primary_observe_target(object_name: str) -> TutorialTarget:
    """Return a single primary observation target."""
    return TutorialTarget(
        object_name=object_name,
        role=TutorialTargetRole.OBSERVE,
        prominence=TutorialTargetProminence.PRIMARY,
    )


def _target(
    object_name: str, role: TutorialTargetRole, *, primary: bool = False
) -> TutorialTarget:
    """Return a tutorial target with an explicit semantic role."""
    return TutorialTarget(
        object_name=object_name,
        role=role,
        prominence=(
            TutorialTargetProminence.PRIMARY if primary else TutorialTargetProminence.RELATED
        ),
    )


def build_essential_walkthrough_chapters() -> tuple[TutorialChapter, ...]:
    """Return the essential walkthrough: the minimal load-identify-fit-save loop.

    Returns:
        Chapters of the essential guided walkthrough.
    """
    return (
        _chapter_getting_started(),
        _chapter_identify(),
        _chapter_analysis_overview(),
        _chapter_optimize(),
        _chapter_save(
            str(
                QT_TRANSLATE_NOOP(
                    "Tutorial",
                    "That's the core workflow: load, identify, review in Analysis,"
                    " fit Region Detail, then save. The same steps apply to your own data.",
                )
            )
        ),
    )


def build_advanced_walkthrough_chapters() -> tuple[TutorialChapter, ...]:
    """Return the advanced walkthrough continuing from the essential one.

    It covers custom presets, the velocity plot, region editing, ties across
    ions, and continuum correction.

    Returns:
        Chapters of the advanced guided walkthrough.
    """
    return (
        _chapter_advanced_intro(),
        _chapter_preset_build(),
        _chapter_velocity_identify(),
        _chapter_organize(),
        _chapter_joint_fit(),
        _chapter_continuum(),
        _chapter_save(
            str(
                QT_TRANSLATE_NOOP(
                    "Tutorial",
                    "That's the advanced workflow: build a custom preset, identify"
                    " with the velocity plot, merge and split regions, tie ions and"
                    " fit them together, correct the continuum, then save. The same"
                    " steps apply to your own data.",
                )
            )
        ),
    )


def _chapter_getting_started() -> TutorialChapter:
    introduction_source = str(
        QT_TRANSLATE_NOOP(
            "Tutorial",
            "The bundled sample spectrum of quasar Q0329-385 has been"
            " loaded. This tour walks you through identifying and"
            " fitting one absorption line using it.",
        )
    )
    return TutorialChapter(
        chapter_id="getting_started",
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Getting Started")),
        destination=_NO_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE, primary=True),
                    _target("modeButton_IDENTIFY", TutorialTargetRole.CONTEXT),
                ),
                action_source=introduction_source,
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The spectrum is displayed and chappy is in identify mode."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Observation data is a pair of FITS files: the observed"
                        " flux and its error. A quasar spectrum shows dips where"
                        " intervening gas absorbs the light.",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_observe_target("modeContextBar_open_observation_data"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Use this button when you want to analyze your own data;"
                        " it selects the flux/error FITS pair.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "When used, it opens a file dialog; after loading, chappy"
                        " switches to identify mode automatically.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "After loading your own data, chappy asks for the"
                        " instrument's resolving power (R), which sets how much"
                        " the instrument blurs the spectrum. The sample already"
                        " has R = 54,000 applied from the survey catalogue.",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_target("spectrumPlotContainer"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Zoom with the mouse wheel or the Up/Down arrow keys:"
                        " the view scales around the cursor. Pan left and right"
                        " with a horizontal scroll or the Left/Right arrow keys.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The visible range zooms around the cursor position and"
                        " shifts sideways as you pan.",
                    )
                ),
                operation=get_shared_operation("wheel_zoom_pan"),
            ),
            TutorialStep(
                targets=(
                    _primary_target("modeContextBar_zoom_rect"),
                    _target("spectrumPlotContainer", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "To zoom into an exact region, first click this Zoom button,"
                        " then drag a rectangle around the spectrum area you want to"
                        " inspect.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The view zooms to the dragged rectangle, and zoom mode"
                        " turns off automatically.",
                    )
                ),
                operation=get_shared_operation("zoom_rect"),
            ),
            TutorialStep(
                targets=(
                    _primary_target("modeContextBar_undo"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Undo] to reverse the rectangle zoom. The shortcut"
                        " is {undo_shortcut}.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The spectrum returns to the wavelength and flux ranges"
                        " shown before the rectangle zoom.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Undo reverses one recorded action at a time. Spectrum"
                        " navigation and later scientific edits use the same history.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("modeContextBar_redo"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {redo_shortcut} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Redo] to apply the rectangle zoom again. The"
                        " shortcut is {redo_shortcut}.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The spectrum returns to the zoomed wavelength and flux ranges.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Undo and Redo move through recent actions one step at a"
                        " time. [Reset View] instead jumps directly to the current"
                        " context's baseline view.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("dataControlPanel_wavelengthMinField"),
                    _target("dataControlPanel_wavelengthMaxField", TutorialTargetRole.INTERACT),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "You can also type an exact wavelength range here: enter"
                        " the lower value in the left wavelength field and the"
                        " upper value in the right field, then press Enter.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The spectrum view updates to the entered range."
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("autoAdjustButton"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {auto_adjust_flux_shortcut} unchanged; it is replaced for the OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "After changing the wavelength range, click [Auto Adjust]"
                        " to fit the flux axis to the visible data. The shortcut is"
                        " {auto_adjust_flux_shortcut}.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The wavelength range stays unchanged while the flux"
                        " minimum and maximum update to frame the visible data.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Use Auto Adjust whenever a zoom or navigation action"
                        " leaves an absorption line too small or vertically clipped.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("resetViewButton"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {reset_view_shortcut} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Reset View] to return from zooming or manual range"
                        " edits to the baseline view. The shortcut is"
                        " {reset_view_shortcut}.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The wavelength and flux ranges return to the current"
                        " context's baseline; when no baseline is stored, the"
                        " entire spectrum is fitted into view.",
                    )
                ),
            ),
        ),
    )


def _chapter_advanced_intro() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="advanced_intro",
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Continuing from the Essentials")),
        destination=_NO_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE, primary=True),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The bundled sample spectrum of quasar Q0329-385 has been"
                        " loaded again. This tour continues from the essential"
                        " workflow and covers building a custom preset, identifying"
                        " with the velocity plot, merging and splitting regions,"
                        " tying redshifts across ions, and correcting the continuum.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The spectrum is displayed and the project starts fresh,"
                        " with no regions from an earlier tour.",
                    )
                ),
            ),
            TutorialStep(
                targets=(),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "This tour assumes you can already identify an absorption"
                        " line, review it in Analysis, and fit it in Region Detail."
                        " If you have not done that yet, run"
                        " [Try the Essential Workflow] first.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Once those basics are familiar, you are ready for the advanced steps.",
                    )
                ),
            ),
        ),
    )


def _chapter_analysis_overview() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="analysis",
        prerequisite=TutorialPrerequisite.HAS_CONFIRMED_REGION,
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Reviewing Analysis Readiness")),
        destination=_ANALYSIS_OVERVIEW_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target(
                        "analysisOverviewReviewWidget", TutorialTargetRole.INTERACT, primary=True
                    ),
                    _target("analysisOverviewStatusCard", TutorialTargetRole.OBSERVE),
                    _target("analysisOverviewOpenRegionButton", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Select the region you want to analyze in the region list,"
                        " read its Analysis status and Next action columns, then"
                        " click [Open region]. Double-clicking the row, pressing"
                        " Enter, or right-clicking it does the same.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Region Detail opens with the region's lines and components."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Not analyzed means the region is ready but not fitted"
                        " yet; stale means a fit exists but its inputs changed"
                        " afterwards, so it has to be run again. Click a count to"
                        " filter the list by that status.",
                    )
                ),
                requires=TutorialCompletion.REGION_DETAIL_OPENED,
            ),
        ),
    )


def _chapter_preset_build() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="preset_build",
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Building a Custom Preset")),
        destination=_IDENTIFY_DESTINATION,
        steps=(
            TutorialStep(
                targets=(_primary_target("identifyManagePresetButton"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The sample hides a second absorber at z ≈ 0.7627 where"
                        " several ions absorb together. Build a custom preset for"
                        " it: click this preset management button.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The Absorption Preset Management dialog opens and the"
                        " tour continues inside it.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Fitting lines of several ions together constrains the"
                        " gas better than any single line. A custom preset"
                        " collects exactly the lines you expect from one"
                        " absorber.",
                    )
                ),
                advance=AdvanceTrigger.DIALOG_SHOWN,
                advance_dialog="presetListDialog",
            ),
            TutorialStep(
                targets=(
                    _primary_target("presetNewButton"),
                    _target("presetListView", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        'Click [New], type a name such as "Low-z absorber" in'
                        " the prompt, and confirm with [OK].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The new empty preset appears selected in the preset list."
                    )
                ),
                requires=TutorialCompletion.NEW_TUTORIAL_PRESET_SELECTED,
            ),
            TutorialStep(
                targets=(_primary_target("presetAddLineButton"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Click [Add Line] to pick transitions from the line database."
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "The line database search dialog opens.")
                ),
                advance=AdvanceTrigger.DIALOG_SHOWN,
                advance_dialog="spectralDatabaseDialog",
            ),
            TutorialStep(
                targets=(
                    _primary_target("filterWavelengthRange"),
                    _target("filterElementCombo", TutorialTargetRole.INTERACT),
                    _target("filterStageCombo", TutorialTargetRole.INTERACT),
                    _target("lineResultTable", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Filter by rest wavelength instead of typing names:"
                        " enter 2370 and 2810 as the wavelength range and set"
                        " the element to Fe with ion stage II. Check"
                        " Fe II 2382.8 and Fe II 2600.2 — each check also"
                        " selects its multiplet partner. Then switch the"
                        " element to Mg and check Mg II 2796.4 the same way.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "Six lines are listed in the selection summary.")
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The catalog stores rest wavelengths. Divide an observed"
                        " wavelength by (1 + z) to know where to look: the"
                        " troughs near 4929 and 4942 Å at z = 0.7627 point to"
                        " rest 2796 and 2803 Å.",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_target("lineSelectionApplyButton", "presetAddLineButton"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Add selected lines] to add them to the preset. If the"
                        " dialog closed with lines missing, reopen [Add Line] and"
                        " check the remaining ones.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The dialog closes; the preset now lists six lines with"
                        " database-derived links.",
                    )
                ),
                advance=AdvanceTrigger.DIALOG_HIDDEN,
                advance_dialog="spectralDatabaseDialog",
                requires=TutorialCompletion.PRESET_HAS_TUTORIAL_LINES,
            ),
            TutorialStep(
                targets=(_primary_target("presetLineTable"),),
                action_source=str(
                    #: Keep {primary_modifier} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "In the line table, select all four Fe II rows: click"
                        " the first row, then {primary_modifier}+click the other"
                        " three.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The Link column shows Fe II split across two links:"
                        " 2374/2382 and 2586/2600 are separate multiplets in the"
                        " database.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Linked lines are later registered into one shared"
                        " analysis region. Left as two links, Fe II would split"
                        " into two regions.",
                    )
                ),
                requires=TutorialCompletion.PRESET_HAS_TUTORIAL_LINES,
            ),
            TutorialStep(
                targets=(
                    _primary_target("presetRemoveTieGroupButton"),
                    _target("presetLineTable", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Unlink] and confirm the prompt to remove both Fe II links.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The Link column of the four Fe II rows becomes empty."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "[Link selected lines] refuses rows that already belong"
                        " to another link, so unlink first when regrouping.",
                    )
                ),
                requires=TutorialCompletion.PRESET_FE2_UNLINKED,
            ),
            TutorialStep(
                targets=(
                    _primary_target("presetAddTieGroupButton"),
                    _target("presetLineTable", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "With the four Fe II rows still selected, click [Link selected lines].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "All four Fe II rows now share a single link; Mg II"
                        " keeps its automatic link.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Keep the Mg II link: without it, each Mg II line would"
                        " later register as its own region.",
                    )
                ),
                requires=TutorialCompletion.PRESET_FE2_SINGLE_GROUP,
            ),
            TutorialStep(
                targets=(_primary_target("presetBaselineCombo"),),
                action_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "Check that [Reference line] shows Mg II 2796.")
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "[Reference line] shows Mg II 2796.")
                ),
                requires=TutorialCompletion.PRESET_BASELINE_IS_MG2796,
            ),
            TutorialStep(
                targets=(_primary_target("presetCloseButton"),),
                action_source=str(QT_TRANSLATE_NOOP("Tutorial", "Click [Close].")),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The dialog closes and the new preset is ready to use."
                    )
                ),
                advance=AdvanceTrigger.DIALOG_HIDDEN,
                advance_dialog="presetListDialog",
                checkpoint_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Does the preset hold six lines with one Fe II link"
                        " covering all four Fe II lines?",
                    )
                ),
            ),
        ),
    )


def _chapter_velocity_identify() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="velocity_identify",
        prerequisite=TutorialPrerequisite.HAS_TOUR_CREATED_PRESET,
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Identifying with the Velocity Plot")),
        destination=_IDENTIFY_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _primary_target("identifyPresetCombo"),
                    _target("identifyReferenceLineCombo", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Select your new preset with this preset selector."
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The candidate list updates and the reference line"
                        " becomes Mg II 2796 automatically.",
                    )
                ),
                requires=TutorialCompletion.TUTORIAL_PRESET_SELECTED,
            ),
            TutorialStep(
                targets=(
                    _primary_target("spectrumPlotContainer"),
                    _target("dataControlPanel_wavelengthMinField", TutorialTargetRole.INTERACT),
                    _target("dataControlPanel_wavelengthMaxField", TutorialTargetRole.INTERACT),
                    _target("modeContextBar_zoom_rect", TutorialTargetRole.INTERACT),
                    _target("autoAdjustButton", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Bring the absorber near 4929 Å into view with any"
                        " navigation route from the first chapter; typing 4900 and"
                        " 4970 into the wavelength fields is the quickest, and"
                        " [Auto Adjust] reframes the flux axis.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Two deep absorption troughs are visible near 4929 and"
                        " 4942 Å — the Mg II 2796/2803 pair.",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_target("spectrumPlotContainer"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Hover the cursor over the deep trough near 4929 Å and"
                        " press V to open the velocity plot.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The spectrum is replaced by stacked velocity slices,"
                        " one per preset line, centered on the hovered feature.",
                    )
                ),
                requires=TutorialCompletion.VELOCITY_PLOT_VISIBLE,
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The velocity plot converts each line's wavelength axis"
                        " into velocity relative to a common redshift, so lines"
                        " of the same absorber align vertically.",
                    )
                ),
                operation=get_shared_operation("identify_toggle_velocity"),
            ),
            TutorialStep(
                targets=(_primary_observe_target("velocityPlotContainer"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Compare the slices: the deep trough and the two weaker"
                        " dips 70–120 km/s to its right repeat in every ion.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Fe II and Mg II share the same velocity structure —"
                        " strong evidence they trace the same absorber.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Alignment is what justifies tying redshifts across ions"
                        " later. It is not guaranteed: ions in different"
                        " ionization states can live in physically separate gas"
                        " even at a similar redshift.",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_target("velocityPlotContainer"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Tick the checkbox on each of the four Fe II slices;"
                        " only Mg II is preselected.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "Six slices are checked in total.")
                ),
                requires=TutorialCompletion.VELOCITY_SLICES_SELECTED,
            ),
            TutorialStep(
                targets=(
                    _primary_target("velocityPlotCreateButton"),
                    _target("identifyTemporarySection", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "Click [Add selected lines to temporary list].")
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "All six lines appear in the Temporary Lines section of the side panel.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("identifyTemporaryRegisterButton"),
                    _target("identifyConfirmedSection", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Click [Register] to confirm all six lines at once."
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Confirmed Regions gains a four-line Fe II region and a"
                        " two-line Mg II region.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Registration groups lines by preset link, one region"
                        " per link. Unlinked lines would each get their own"
                        " region.",
                    )
                ),
                requires=TutorialCompletion.FE2_AND_MG2_REGIONS_EXIST,
                checkpoint_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Do Confirmed Regions show a 4-line Fe II region"
                        " and a 2-line Mg II region at z ≈ 0.7627?",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_target("modeButton_ANALYSIS"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Analysis] to organize the Fe II and Mg II regions"
                        " you just registered.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Analysis mode opens with the new low-redshift regions"
                        " listed in the overview.",
                    )
                ),
                advance=AdvanceTrigger.MODE_CHANGE,
                advance_mode=EditingMode.ANALYSIS,
            ),
        ),
    )


def _chapter_organize() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="analysis_structure",
        prerequisite=TutorialPrerequisite.HAS_TWO_REGIONS,
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Merging Regions")),
        destination=_ANALYSIS_OVERVIEW_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target(
                        "analysisOverviewReviewWidget", TutorialTargetRole.INTERACT, primary=True
                    ),
                    _target("analysisOverviewEditStructureButton", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Back in Analysis, the overview lists the Fe II and Mg II"
                        " regions. Select one of them.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The summary updates for the selected region and [Edit region] is ready.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A region is the bundle of lines fitted together; a tie"
                        " declares that parameters are shared. The two are"
                        " orthogonal: merging or splitting regions never touches"
                        " ties.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisOverviewEditStructureButton"),
                    _target("analysisStructureTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "Click [Edit region] for the selected region.")
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The side panel switches to the region editor: regions as"
                        " parent rows with their absorption lines underneath.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisStructureTree"),
                    _target("analysisOverviewMergeButton", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {primary_modifier} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Select the Fe II region row, then {primary_modifier}+click"
                        " the Mg II region row.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Both region rows are selected and [Merge] becomes available."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "You will later tie the redshift across both ions. If"
                        " they stayed in separate regions, fitting one region"
                        " alone would adjust the shared redshift using only that"
                        " region's data.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisOverviewMergeButton"),
                    _target("analysisStructureTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(QT_TRANSLATE_NOOP("Tutorial", "Click [Merge].")),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "A single region now holds all six lines.")
                ),
                operation=get_shared_operation("analysis_structure_merge"),
                requires=TutorialCompletion.MULTI_ION_REGION_EXISTS,
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisOverviewSplitButton"),
                    _target("analysisStructureTree", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Merging is not one-way: select one Mg II line inside"
                        " the merged region and click [Split].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The whole Mg II multiplet moves into a new region — the"
                        " original two regions are back.",
                    )
                ),
                operation=get_shared_operation("analysis_structure_split"),
                requires=TutorialCompletion.MONO_ION_REGIONS_RESTORED,
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisOverviewMergeButton"),
                    _target("analysisStructureTree", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Select the two regions again and click [Merge] to"
                        " restore the merged region.",
                    )
                ),
                expected_source=str(
                    #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "All six lines are in one region again; {undo_shortcut}"
                        " would also undo any of these edits.",
                    )
                ),
                operation=get_shared_operation("analysis_structure_merge"),
                requires=TutorialCompletion.MULTI_ION_REGION_EXISTS,
            ),
            TutorialStep(
                targets=(_primary_target("structureSidePanelBackButton"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Click [Back to Overview] to leave the region editor."
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The summary panel returns with the merged region listed."
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _target(
                        "analysisOverviewReviewWidget", TutorialTargetRole.INTERACT, primary=True
                    ),
                    _target("analysisOverviewStatusCard", TutorialTargetRole.OBSERVE),
                    _target("analysisOverviewOpenRegionButton", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Select the merged six-line region in the region list,"
                        " then click [Open region].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Region Detail opens with all four Fe II and both Mg II"
                        " lines in its parameter tree.",
                    )
                ),
                requires=TutorialCompletion.TUTORIAL_MULTI_ION_REGION_OPENED,
                checkpoint_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Is there one merged region containing all four Fe II and both Mg II lines?",
                    )
                ),
            ),
        ),
    )


def _chapter_joint_fit() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="joint_fit",
        prerequisite=TutorialPrerequisite.HAS_TUTORIAL_MULTI_ION_REGION,
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Tying Ions and Fitting Together")),
        destination=_ANALYSIS_DETAIL_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target(
                        "analysisDetailRegionSelector", TutorialTargetRole.CONTEXT, primary=True
                    ),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The region you just opened is shown here; this selector"
                        " switches to another region without going back.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The spectrum view moves to the region and the panel lists"
                        " its lines and components.",
                    )
                ),
            ),
            TutorialStep(
                targets=(_primary_target("spectrumPlotContainer"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The combined region is too wide for the wavelength"
                        " plot to separate the closely spaced troughs you are"
                        " about to model. Press V (or right-click the spectrum"
                        " and choose [Show Velocity Plot (V)]).",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "All six lines are stacked vertically on a velocity"
                        " axis, making their repeated trough structure easier"
                        " to compare.",
                    )
                ),
                operation=get_shared_operation("analysis_toggle_velocity"),
                requires=TutorialCompletion.VELOCITY_PLOT_VISIBLE,
            ),
            TutorialStep(
                targets=(
                    _primary_target("velocityPlotContainer"),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Shift+click the deepest trough on the Fe II 2382.8"
                        " slice to place the ion's main component.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A tied component appears under every Fe II line:"
                        " multiplet lines of one ion always share all"
                        " parameters.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Full sharing (logN included) exists only within one ion"
                        " species: its lines probe the same column density,"
                        " while different ions have physically different ones."
                        " That is why cross-ion sharing is limited to z (and b)."
                        " Shift+click also starts the component at the clicked"
                        " velocity, whereas [Add Component] starts it at the"
                        " redshift frozen during identification.",
                    )
                ),
                operation=get_shared_operation("optimize_velocity_shift_click"),
                requires=TutorialCompletion.FE2_COMPONENT_EXISTS,
            ),
            TutorialStep(
                targets=(
                    _primary_target("velocityPlotContainer"),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Now Shift+click the deepest trough on the Mg II 2796.4 slice."
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "A tied component pair appears under the Mg II lines as well."
                    )
                ),
                operation=get_shared_operation("optimize_velocity_shift_click"),
                requires=TutorialCompletion.MG2_COMPONENT_EXISTS,
            ),
            TutorialStep(
                targets=(
                    _primary_target("velocityPlotContainer"),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "On the Fe II 2382.8 and Mg II 2796.4 slices,"
                        " Shift+click each of the two shallow dips to the right"
                        " of the deepest trough. Use their alignment across"
                        " both ions as the guide rather than aiming for exact"
                        " displayed velocities.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Each ion now has three components, mirrored across all"
                        " of its multiplet lines.",
                    )
                ),
                operation=get_shared_operation("optimize_velocity_shift_click"),
                requires=TutorialCompletion.FE2_AND_MG2_HAVE_THREE_COMPONENTS,
            ),
            TutorialStep(
                targets=(_primary_target("analysisDetailParameterTree"),),
                action_source=str(
                    #: Keep {primary_modifier} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Tie the ions together: {primary_modifier}+click the main"
                        " Fe II component and the main Mg II component,"
                        " right-click, and choose [Share z].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Both components now show a shared-z marker: one"
                        " redshift parameter drives both ions.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The tie shares only z; logN and b stay independent per"
                        " ion. [Share all parameters] is disabled across"
                        " different species by design. Dragging any tied"
                        " component's center line on the spectrum moves every"
                        " member together.",
                    )
                ),
                requires=TutorialCompletion.CROSS_ION_Z_TIE_EXISTS,
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisDetailFitButton"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailResultsCard", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Fit] (or press F5) to fit all six lines"
                        " simultaneously. Run it again if it stops before"
                        " converging.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The shared redshift settles near z ≈ 0.76273 and the"
                        " main Fe II component near logN ≈ 13.24 with"
                        " b ≈ 4.9 km/s.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Thanks to the tie, every ion's data constrains the same"
                        " redshift at once — the reason the regions were merged"
                        " before fitting.",
                    )
                ),
                operation=get_shared_operation("analysis_fit"),
                requires=TutorialCompletion.REGION_FIT_APPLIED,
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisDetailParameterTree"),
                    _target("analysisDetailResultsCard", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Mg II is saturated, so its logN is unreliable:"
                        " right-click the main Mg II component and tick the"
                        " entry that starts with [Fix logN]. The two Mg II"
                        " lines are tied as a multiplet, so the entry also"
                        " names the shared tie and how many components it"
                        " covers.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Mg II's logN is marked fixed, and the applied fit"
                        " becomes out of date because the model changed.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A saturated line absorbs nearly all light at its"
                        " center, so the profile barely changes as logN grows:"
                        " the fit can wander to extreme logN with tiny b."
                        " Fixing logN for saturated lines is standard practice.",
                    )
                ),
                requires=TutorialCompletion.MG2_LOGN_FIXED,
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisDetailFitButton"),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailResultsCard", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Fit] once more so the remaining parameters"
                        " settle with Mg II's logN held fixed.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The fit converges with Mg II's logN held fixed; quote"
                        " such values as lower limits, not measurements.",
                    )
                ),
                checkpoint_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Did the joint fit converge near z ≈ 0.76273 with"
                        " Fe II logN ≈ 13.24 and b ≈ 4.9 km/s?",
                    )
                ),
                operation=get_shared_operation("analysis_fit"),
                requires=TutorialCompletion.REGION_FIT_APPLIED,
            ),
            TutorialStep(
                targets=(_primary_target("modeButton_CONTINUUM"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Click [Continuum] to inspect the continuum controls."
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "Continuum mode opens with its control point table."
                    )
                ),
                advance=AdvanceTrigger.MODE_CHANGE,
                advance_mode=EditingMode.CONTINUUM,
            ),
        ),
    )


def _chapter_continuum() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="continuum",
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Correcting the Continuum")),
        destination=_CONTINUUM_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target("continuumPointsTable", TutorialTargetRole.CONTEXT, primary=True),
                    _target("modeButton_CONTINUUM", TutorialTargetRole.CONTEXT),
                ),
                action_source=str(
                    #: Keep {continuum_mode_shortcut} unchanged; it is replaced for the OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Continuum mode is active. You can return with"
                        " {continuum_mode_shortcut} or this button.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The context bar turns green and the control point table panel appears.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The continuum is the quasar's intrinsic light without"
                        " absorption. Line depths are measured relative to it."
                        " This mode is normally unnecessary for already-normalized"
                        " spectra; use it when fit residuals from Region Detail reveal"
                        " a continuum error. The sample data is already"
                        " normalized, so the continuum is nearly flat at 1.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("continuumAutoEstimateButton"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                    _target("continuumPointsTable", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(QT_TRANSLATE_NOOP("Tutorial", "Click [Auto Estimate].")),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The continuum curve and the control point list update with the estimate.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("spectrumPlotContainer"),
                    _target("continuumPointsTable", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Double-click on the spectrum to add a control point where"
                        " the continuum needs adjustment, then drag it into place.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The new point appears immediately in the view and in the"
                        " control point table.",
                    )
                ),
                operation=get_shared_operation("continuum_add_point"),
            ),
            TutorialStep(
                targets=(_primary_target("spectrumPlotContainer"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Remove an unneeded point: right-click it on the spectrum"
                        " and choose [Delete Control Point].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The point disappears and the continuum curve is recalculated."
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("modeContextBar_undo"),
                    _target("continuumPointsTable", TutorialTargetRole.OBSERVE),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The sample needs no continuum correction, so undo the edits"
                        " you just made: press {undo_shortcut} until the control point"
                        " table returns to the state before [Auto Estimate].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The added and deleted points are restored and the continuum"
                        " is flat at 1 again, so the fit you ran stays valid.",
                    )
                ),
            ),
        ),
    )


def _chapter_identify() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="identify",
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Identifying Absorption Lines")),
        destination=_IDENTIFY_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target("modeButton_IDENTIFY", TutorialTargetRole.CONTEXT, primary=True),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Identify mode is active; this badge shows the current mode."
                        " Select [Next] to choose a preset.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "The Identify badge is highlighted.")
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("identifyPresetCombo"),
                    _target("identifyReferenceLineCombo", TutorialTargetRole.OBSERVE),
                    _target("identifyCandidateTable", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        'Choose the built-in preset "Metal Lines" with this preset selector.',
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The reference line and candidate list update for the preset."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "A preset is a reusable set of spectral line species."
                    )
                ),
                requires=TutorialCompletion.METAL_LINES_PRESET_SELECTED,
            ),
            TutorialStep(
                targets=(_primary_target("identifyReferenceLineCombo"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Select C IV 1548.204 as the reference line with this selector.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "The reference line changes to C IV 1548.204.")
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Some species split into several wavelengths (multiplets),"
                        " shown grouped under a representative line.",
                    )
                ),
                requires=TutorialCompletion.REFERENCE_LINE_IS_CIV1548,
            ),
            TutorialStep(
                targets=(
                    _primary_target("spectrumPlotContainer"),
                    _target("dataControlPanel_wavelengthMinField", TutorialTargetRole.INTERACT),
                    _target("dataControlPanel_wavelengthMaxField", TutorialTargetRole.INTERACT),
                    _target("modeContextBar_zoom_rect", TutorialTargetRole.INTERACT),
                    _target("autoAdjustButton", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Bring the 4755-4780 Å range into view with any zoom you"
                        " like, or by typing the two values into the wavelength"
                        " fields, then click [Auto Adjust].",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "A pair of absorption dips is visible near 4763 and 4771 Å."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "An absorption line is a narrow dip where intervening gas"
                        " absorbs the background light at a specific wavelength.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _primary_target("spectrumPlotContainer"),
                    _target("identifyTemporarySection", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Hold Shift and hover over the left, deeper dip near"
                        " 4763 Å to preview the candidate positions, then"
                        " Shift+click to register it as a temporary line.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A new row appears in the Temporary Lines section of the"
                        " side panel, with a heading showing where it will be"
                        " registered.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A temporary line links a species to an absorption feature"
                        " but is not saved yet; registering turns it into a line.",
                    )
                ),
                operation=get_shared_operation("identify_shift_click"),
            ),
            TutorialStep(
                targets=(
                    _primary_target("identifyTemporaryRegisterButton"),
                    _target("identifyTemporarySection", TutorialTargetRole.OBSERVE),
                    _target("identifyConfirmedSection", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Register] to save the line immediately; Undo"
                        " ({undo_shortcut}) reverts it if needed.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The temporary line leaves the list, and Confirmed Regions"
                        " opens to show its region with the measured redshift.",
                    )
                ),
                requires=TutorialCompletion.CONFIRMED_REGION_EXISTS,
                checkpoint_source=str(
                    QT_TRANSLATE_NOOP("Tutorial", "Did you identify the C IV line at z ≈ 2.076?")
                ),
            ),
            TutorialStep(
                targets=(_primary_target("modeButton_ANALYSIS"),),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Analysis] to review the absorption regions you identified.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Analysis mode opens with an overview of the identified regions.",
                    )
                ),
                advance=AdvanceTrigger.MODE_CHANGE,
                advance_mode=EditingMode.ANALYSIS,
            ),
        ),
    )


def _chapter_optimize() -> TutorialChapter:
    return TutorialChapter(
        chapter_id="analysis_detail",
        prerequisite=TutorialPrerequisite.HAS_CONFIRMED_REGION,
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Fitting a Region in Detail")),
        destination=_ANALYSIS_DETAIL_DESTINATION,
        steps=(
            TutorialStep(
                targets=(
                    _target(
                        "analysisDetailRegionSelector", TutorialTargetRole.CONTEXT, primary=True
                    ),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The region you just opened is shown here; this selector"
                        " switches to another region without going back.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The spectrum view moves to the region and the panel lists"
                        " its lines and components.",
                    )
                ),
            ),
            TutorialStep(
                targets=(
                    _target(
                        "analysisDetailParameterTree", TutorialTargetRole.INTERACT, primary=True
                    ),
                    _target("analysisDetailAddModelButton", TutorialTargetRole.INTERACT),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Select the C IV 1548/1551 row in this tree, then click"
                        " [Add Component] to add a model to it.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "A component row appears under the selected line."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A component describes one absorbing gas cloud with"
                        " parameters: column density (logN), Doppler width (b),"
                        " redshift (z), and covering factor (Cf). You can also add"
                        " one at a chosen wavelength by Shift+clicking the spectrum"
                        " or using [Add Component Here] in its right-click menu.",
                    )
                ),
                operation=get_shared_operation("optimize_shift_click"),
                requires=TutorialCompletion.REGION_HAS_COMPONENT,
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisDetailParameterTree"),
                    _target("spectrumPlotContainer", TutorialTargetRole.INTERACT),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Give the fit a starting point: drag the component's"
                        " dashed center line onto the dip you are modeling, or"
                        " double-click a z, logN, b, or Cf cell to type a value"
                        " you already know.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "The model profile follows your edits in real time."
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The line shape is modeled with a Voigt profile computed"
                        " from these parameters. The fit starts from the values you"
                        " leave here, so they need not be exact: the dashed center"
                        " near the middle of the dip is enough. A starting point too"
                        " far off can settle on a different solution — move the"
                        " center back onto the dip and fit again.",
                    )
                ),
                operation=get_shared_operation("optimize_drag_center"),
            ),
            TutorialStep(
                targets=(
                    _primary_target("analysisDetailFitButton"),
                    _target("spectrumPlotContainer", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailParameterTree", TutorialTargetRole.OBSERVE),
                    _target("analysisDetailResultsCard", TutorialTargetRole.OBSERVE),
                ),
                action_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Click [Fit] (or press F5). If it stops without"
                        " converging, run it once more: it continues from the"
                        " current values. Once it converges, [Export Results]"
                        " writes the fitted parameters to CSV.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "The model traces both dips and the statistics settle"
                        " near z ≈ 2.0764, logN ≈ 13.7, b ≈ 7 km/s.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Fitting starts from the values you placed and adjusts"
                        " them to minimize the difference between data and model.",
                    )
                ),
                operation=get_shared_operation("analysis_fit"),
                requires=TutorialCompletion.REGION_FIT_APPLIED,
                checkpoint_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Did the fit converge near z ≈ 2.0764 with logN ≈ 13.7 and b ≈ 7 km/s?",
                    )
                ),
            ),
        ),
    )


def _chapter_save(conclusion_source: str) -> TutorialChapter:
    return TutorialChapter(
        chapter_id="save",
        title_source=str(QT_TRANSLATE_NOOP("Tutorial", "Saving Your Work")),
        destination=_NO_DESTINATION,
        steps=(
            TutorialStep(
                targets=(_primary_target("modeContextBar_save_project"),),
                action_source=str(
                    #: Keep {save_project_shortcut} unchanged; it is replaced for the OS.
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "Save your project: press {save_project_shortcut} or click this button.",
                    )
                ),
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A save dialog asks for a location; the project is written as an .h5 file.",
                    )
                ),
                domain_note_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial",
                        "A project file (.h5) stores your spectrum, regions,"
                        " lines, components, and settings in one place.",
                    )
                ),
            ),
            TutorialStep(
                targets=(),
                action_source=conclusion_source,
                expected_source=str(
                    QT_TRANSLATE_NOOP(
                        "Tutorial", "You can restart this tour anytime from Help > Tutorial."
                    )
                ),
            ),
        ),
    )
