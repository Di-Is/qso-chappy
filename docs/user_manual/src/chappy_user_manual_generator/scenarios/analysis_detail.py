"""Analysis Region Detail operation scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QT_TRANSLATE_NOOP

from chappy_user_manual_generator.translations import translate_manual_text

if TYPE_CHECKING:
    from chappy_user_manual_generator.models import OperationFlow, ScenarioContext

_EXPORTER_CONTEXT = "ManualExporter"


def _tr(source_text: str) -> str:
    return translate_manual_text(_EXPORTER_CONTEXT, source_text)


def analysis_region_detail_workflow(context: ScenarioContext) -> OperationFlow:
    """Workflow for preparing and executing a fit in Region Detail."""
    context.add_prerequisite(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Regions have been created in Identify mode."))
    )
    context.add_prerequisite(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter", "Analysis Region Detail is open for a target region."
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "A region showing the needs-optimization badge requires re-analysis,"
                " for example after continuum model changes or manual component edits.",
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "To exclude wavelength ranges from the analysis, set masks in the"
                " exclusion regions.",
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                'Each absorption line has an "Analysis range [km/s]" value that'
                " defines its analysis interval. The Velocity Plot's \"Display"
                ' range" changes only the view and is not recorded in scientific'
                " Undo.",
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Selecting multiple components and choosing delete from the context"
                " menu removes all selected components at once.",
            )
        )
    )
    context.add_note(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                '"Share z" and "Share all parameters" require two or more components'
                " that are not already in a shared group; a component already in a"
                ' shared group must use "Remove from shared group" first before it can'
                " be regrouped.",
            )
        )
    )
    context.add_related_link(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Analysis Region Detail Screen")),
        "../screens/main_window/mode_analysis_region_detail/MainWindow.md",
    )
    context.add_related_link(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Common Screen Elements")),
        "../screens/main_window/common/MainWindow.md",
    )

    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP("ManualExporter", "Select the region to analyse in the side panel.")
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The spectrum view moves to fit the region, and the side panel and the"
                " parameter table in the bottom pane update to the selected region.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Use the side panel's exclusion-region settings to exclude unwanted"
                " wavelength ranges from the optimization.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The region list updates and the exclusion regions are reflected on the spectrum.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "In the parameter table in the bottom pane, select the line to which"
                " you want to add absorption components.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The selected line is highlighted and the add-component button is enabled.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Add a component by clicking the add-component button, right-clicking"
                " the selected line's region on the spectrum, or Shift+clicking it.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Click-added components appear at the clicked position; button-added"
                " ones appear at the line centre. A component row is added under the"
                " selected line in the parameter table.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "To adjust components while comparing several lines in velocity space,"
                ' right-click the spectrum with a line selected and choose "Show'
                ' Velocity Plot".',
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The velocity plot window opens, where you can add components with"
                " Shift+Click and adjust the redshift by dragging the centre line.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                'Edit "Analysis range [km/s]" on a line or multiplet row to change'
                " the interval used for analysis.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The analysis interval updates for the affected linked lines and the"
                " region is marked for re-analysis. If the requested interval would"
                " exclude a model centre, the applied minimum and reason are shown.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                'In the Velocity Plot, edit "Display range" to reframe every'
                ' subplot, or choose "Fit view to analysis ranges" to derive the view'
                " from the current region.",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Every subplot and page uses the same symmetric display range. The"
                " project, analysis intervals, and scientific Undo history remain unchanged.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "To change parameters manually, drag the component's centre dashed line"
                " (yellow for the target line, orange for other lines; redshift z"
                " only), or click and edit the component's parameter cells"
                " (z, logN, b, Cf).",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Dragging moves the component to the drop position and updates the"
                " redshift value in the parameter table; editing a cell reshapes the"
                " component after the change.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "For fine slider-based adjustment, right-click the component row and"
                ' choose "Adjust Parameters…" to open the parameter adjustment dialog.',
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The dialog lets you adjust each parameter (logN, b, z, Cf) intuitively"
                " with sliders and numeric input; changes are applied to the model"
                " immediately.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Right-click a component row to toggle parameter fixing as needed."
                " Select multiple components with Ctrl+Click (⌘+Click on macOS) or"
                ' Shift+Click to toggle fixing in bulk. The "Fixed" checkbox in the'
                " parameter adjustment dialog also toggles it (single selection only).",
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter", "Cells of fixed parameters change colour in the table."
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "To fit several components together, select two or more components"
                ' and right-click to choose "Share z" (redshift only) or "Share all'
                ' parameters" (z, b, logN, Cf; requires the same ion). Choose "Remove'
                ' from shared group" to detach the selected components again.',
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "Shared parameter cells show a bracketed label such as [A] before the"
                " value, and editing one shared cell updates every component in the"
                " group. If the selected components' redshifts differ, a confirmation"
                " dialog appears before aligning them; each action can be undone with"
                " Ctrl+Z (⌘Z on macOS).",
            )
        ),
    )
    context.add_step(
        _tr(QT_TRANSLATE_NOOP("ManualExporter", "Press Run fit to fit the current region.")),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "The model (red) and residual (yellow) on the spectrum change according"
                " to the fit result.",
            )
        ),
    )
    context.add_step(
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter", "Use Export Results to save the analysis results as CSV."
            )
        ),
        _tr(
            QT_TRANSLATE_NOOP(
                "ManualExporter",
                "When the save dialog completes, the file is created at the chosen"
                " path. On Windows you can choose the encoding (UTF-8 BOM / UTF-8);"
                " pick UTF-8 BOM if characters such as Å appear garbled in Excel.",
            )
        ),
    )

    return context.build_flow()
