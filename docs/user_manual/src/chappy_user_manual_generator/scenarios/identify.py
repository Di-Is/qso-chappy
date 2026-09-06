"""Identify mode operation scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy_user_manual_generator.translations import translate_manual_text

if TYPE_CHECKING:
    from chappy_user_manual_generator.models import OperationFlow, ScenarioContext

_EXPORTER_CONTEXT = "ManualExporter"


def _tr(source_text: str) -> str:
    return translate_manual_text(_EXPORTER_CONTEXT, source_text)


def identify_candidate_workflow(context: ScenarioContext) -> OperationFlow:
    """Workflow for reviewing candidates and registering regions in Identify mode."""
    context.add_prerequisite(_tr(QT_TRANSLATE_NOOP("ManualExporter", "Identify mode is active.")))
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "High-S/N spectra can produce so many detection candidates that"
                " interaction slows down. Adjust the detection threshold.",
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter", "The temporary line list is sorted by ascending redshift."
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Candidates whose ranges overlap a confirmed region show the"
                " Registered status, so the candidate table doubles as a to-do"
                " list of unassigned features.",
            )
        )
    )
    context.add_related_link(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Identify Mode Screen")),
        "../screens/main_window/mode_identify/MainWindow.md",
    )
    context.add_related_link(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Common Screen Elements")),
        "../screens/main_window/common/MainWindow.md",
    )
    context.add_related_link(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Adding Spectral Lines to a Preset")),
        "../menus/main_window/dialogs/PresetListDialog.md",
    )

    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Choose an absorption-line preset with the Preset selector in the"
                " setup header at the top of the Identify side panel.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The Reference line selector, the candidate list, and the velocity"
                " plot update to match the selected preset. The setup header stays"
                " visible at all times, so the active preset and reference line are"
                " always in view.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "If the spectral line species you want to detect is not in the preset,"
                " open the [Preset Management dialog]"
                "(../menus/main_window/dialogs/PresetListDialog.md) with the Manage"
                " button and add the line to the preset in use. Link lines that should"
                " be identified and fitted together.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The added species appears in the Reference line selector's popup,"
                " and linked lines share the same Link label in the dialog. Built-in"
                " presets cannot be modified, so copy one or create a new preset"
                " when needed.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Select the species to use as the identification anchor with the"
                " Reference line selector in the setup header. The popup lists"
                " every line in the preset.",
            )
        ),
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "The anchor line is updated.")),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "To change the scientific interval for upcoming candidates, set"
                " New-candidate range on the second row of the setup header.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The value is used by the next Shift preview and by candidates"
                " added afterward. Existing temporary lines, registration grouping,"
                " and the Velocity Plot view range do not change.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Review the detection candidate table. The σ threshold slider and numeric"
                " input are always visible on one row and stay synchronized. Each row shows"
                " the wavelength range, σ score, and"
                " status: Unassigned, Tentative, or Registered.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Lowering the σ threshold adds weaker candidates to the table;"
                " the section heading reports the current count.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Search for absorption lines by zooming with the Up/Down keys,"
                " panning with the Left/Right keys, or double-clicking a candidate"
                " row (pressing Enter on the selected row works the same way).",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter", "These operations bring the absorption region into view."
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Hold Shift and place the cursor over an absorption region in the"
                " spectrum view to preview the anchor line and the candidate positions"
                " of the other preset lines.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The preview range is drawn according to New-candidate range, and"
                " candidate positions of the other preset species are overlaid. The"
                " spectrum also reports the current range and shows V: Verify in"
                " Velocity Plot while this Shift preview is active.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "(Identifying on the spectrum) When the preview sits at the intended"
                " position, Shift-click the spectrum view to add it as a temporary line.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "A new row is added to the Temporary Lines section of the side"
                " panel and the preview colours update to the matching species."
                " When the anchor line belongs to a link group in the active"
                " preset, a temporary line is created for every line in that"
                " group.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "(Identifying on the velocity plot) Place the cursor over the intended"
                " absorption region and press V. Hold Shift beforehand when you want to"
                " confirm the all-species preview first.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The velocity plot opens immediately at the exact cursor wavelength,"
                " whether or not the Shift preview is visible. Dashed boundaries show"
                " New-candidate range. Display range initially includes those"
                " boundaries with margin; six preset species are shown per page, with"
                " arrow buttons for later pages.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "On the Velocity Plot, edit Display range to reframe every"
                " subplot and page. Press Fit view to analysis ranges to restore a"
                " view derived from New-candidate range.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Only the Velocity Plot view changes. New-candidate range,"
                " existing temporary lines, registration grouping, and scientific"
                " Undo history remain unchanged.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "(Identifying on the velocity plot) Click the top-left corner of the"
                " velocity plot for each species you want to identify to check it,"
                " then press Add selected lines to temporary list.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "A blue check mark selects each species, and temporary lines for"
                " the checked species are added to the Temporary Lines section. Their"
                " ranges use New-candidate range, not Display range.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Review the grouping shown in the Temporary Lines section. Each"
                " group heading tells you where the lines will go on"
                " registration: a new region, or an existing region named in the"
                " heading.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The grouping is re-evaluated whenever temporary lines are added"
                " or removed. A warning mark on a heading means the lines"
                " overlap multiple existing regions; check the assignment in"
                " Analysis Structure after registering.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Press Register all (N groups) to save every temporary group to the project."
                " To register only some groups, select their rows first; the button"
                " changes to Register selected (N groups).",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The lines are saved immediately: they leave the temporary list,"
                " appear under Confirmed Regions, and the status bar reports the"
                " created or extended regions. Undo (Ctrl+Z, ⌘Z on macOS)"
                " reverts the registration. Lines created from the same link"
                " group remain linked in the project.",
            )
        ),
    )

    return context.build_flow()
