"""Generated lupdate extraction bridge for annotations_map.yaml.

Do not edit manually: regenerate with
``uv run python scripts/i18n_manual_annotations_bridge.py``.
This module is never imported at runtime; it only exists so that
``pyside6-lupdate`` can discover the English strings declared as data in
``annotations_map.yaml``.
"""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP

_SOURCE_STRINGS = (
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Analysis Structure panel**: Collapse the tree while reviewing each line’s type, wavelength span, redshift, velocity window, and Needs badge. The colour chip beside each region matches the spectrum overlay; see [Analysis Structure panel](#analysis-structure-panel) for a quick reference.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Colour indicator**: The colour chip beside each region matches the vertical band in the spectrum. Double-click when you need to refocus on the matching range.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Edit regions**: Rearrange lines and use the visible Structure actions or context menu to merge, split, unlink, or delete items (see [Analysis Structure](../../../operations/analysis-structure.md)). Press Back to Overview at the top of the panel to return to Analysis Overview.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Fitting linked lines**: When you add a model to one linked line, components are created for every line in the link. By default, redshift, column density, b parameter, and covering factor are shared; changing one updates all linked components.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Link groups**: When you add a candidate using a line in a link group, a temporary line is created for every line in that group. After you register them, those lines remain linked in the project.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Linked-line display**: Lines registered from the same preset link group are displayed as a single representative line with the highest f-value.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Spectrum display**: Double-click an absorption region (region) to jump the spectrum to the wavelength span that contains all of its absorption lines (lines); the coloured bands highlight that range.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "**Velocity window**: Each line heading in the tree shows its velocity window inline (±… km/s).",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "A Needs badge marks regions that still require optimisation."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "A component that needs re-optimization shows its value without an uncertainty, since the previous fit's uncertainty no longer applies; hover the cell to see that previous value in the tooltip.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "A link group contains at least two lines of the same ion, and each line can belong to only one link group.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "A warning shown when the filter conditions conflict, such as an invalid wavelength range. It hides automatically once the conditions are fixed.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Absorber tree"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Add component"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Add lines with Add Line and remove them with Remove Selected."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Add new presets, edit membership (lines in or out), or delete unused presets.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Add selected lines to temporary list"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Add temporary lines for the selected velocity slices; use the side panel's Register action to save them to confirmed regions.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Add the selected lines to the calling preset and close the dialog."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Additional Notes"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Adjust only the flux axis to fit the observed data in the currently visible wavelength range.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Adjust the continuum curve with control points."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Adjust the wavelength and flux ranges with the data control panel. Velocity controls depend on the active mode.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Adjust the ΛCDM parameters used to compute comoving distance and lookback time in the analysis.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Analysis Mode"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Analysis Overview reviews every region's readiness, fit result, and next action.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Analysis Region Detail panel"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Analysis Region Detail prepares fitting conditions, runs the optimiser, and reviews one region's result.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Analysis Structure edits the region and line hierarchy from Overview.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Analysis Structure panel"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Analysis review table"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Analysis-range summary"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Anchor line"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Appears when further adjustments are required for a region, highlighting items that need optimization.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Apply all currently valid link suggestions to the custom preset."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Apply the Planck 2018 recommended parameters (67.4, 0.315, 0.685) to the fields.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Auto Adjust"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Auto Estimate"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Auto estimation overwrites existing control points; save the current state first.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Back to Overview"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Back to Spectrum"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Bottom pane"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Built-in presets cannot be edited; duplicate one and save it as a custom preset.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Cancel"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Central canvas that shows the observed spectrum and fitted models with zoom and measurement tools.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Choose the display language of the application. The preview below updates to the selected language.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Choose the error FITS file from a file dialog."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Choose the flux FITS file from a file dialog."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Choose the preset's anchor line. When set, it is selected as the default anchor in Identify mode.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Choose the single line used as the identification anchor. The popup lists every line in the preset with its rest wavelength; hover an item to see its oscillator strength and full-precision wavelength.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Choosing a language from the list updates the preview to that language.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Clear Control Points"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Clear the selected list at once when you want to start over."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Click a status count in the summary panel to filter the region list."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Click to expand or collapse the confirmed-region list. While collapsed, the summary shows the region count and a representative region and line.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Close Project"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Close the Velocity Plot and return to the standard spectrum view."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Close the dialog without applying the search results."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Compare the current region's lines on a shared velocity axis. Display range reframes every subplot and page without changing the line analysis ranges.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Component parameter table"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Confirm what happens to unsaved changes before the current project is closed.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Confirmed Regions section header"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Confirmed regions"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Continuum Mode"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Continuum mode shapes the continuum curve so later analysis stays stable.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Control Point List"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Control Point Table"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Controls for adjusting the spectrum view range and scaling."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Coordinate Readout"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Create a link group from two or more selected lines of the same ion."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Create an empty preset ready for any line composition."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Create an empty workspace with “New Project” when starting from scratch.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Create and adjust wavelength masks to exclude regions from the fit."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Data Controls"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Delete"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Delete selected regions or lines after reviewing the impact confirmation.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Delete selection"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Delete the selected custom preset."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Detail preview"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Detection candidate table"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Detection candidates"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Discard the changes and close the dialog."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Discard the unsaved changes and close the project."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Display"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Display language"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Display range"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Displays application status, messages, and cursor readouts."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Displays the current mode and project state."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Displays wavelength, flux, and action columns for every control point; double-click to edit values.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Don't Save"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Double-click on the spectrum view to center the display on that wavelength (zoom level is preserved).",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Drag a rectangle to zoom into that region of the spectrum."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Drag and drop the flux/error FITS pair or a .h5 project onto the main view.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Duplicate the selected preset into an editable copy."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Each row shows a candidate's wavelength range, σ score, and status (Unassigned, Tentative, or Registered). A single click only selects a row; double-click it or press Enter to move to the candidate position, then Shift+click the absorption center to add temporary lines.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Edit Analysis range [km/s] on a line or multiplet row to set the interval used for analysis.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Edit presets with the New / Duplicate / Rename / Delete buttons."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Edit region"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Editing H₀, Ωm, or ΩΛ immediately recomputes Ωk and the flatness indicator.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Element"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Enter an element symbol, line ID, transition name, or similar for partial-match search.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Enter the instrument's resolution in the Spectral Resolution R field.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Enter the matter density Ωm in the range 0.000–1.000. Changing it updates Ωk.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Enter the minimum and maximum within 0–50000 Å to narrow the searched wavelength band. An empty field removes the limit on that side.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Enter the path of the FITS file containing the observed flux. Browse... also opens a file picker.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Enter the percentile threshold for automatic continuum estimation. The spectrum is divided into 100Å bins, and the flux value at the specified percentile within each bin is used as a control point. Higher values (closer to 99%) avoid absorption lines and capture peaks; lower values (closer to 50%) capture the median.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Entered values are stored in the user settings and restored on the next launch.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Explain that closing returns to Start mode and that the project can be reopened from File > Open Project.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Export results"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Export the selected preset as JSON."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Filter candidates by element in atomic-number order. Type an element symbol to select it from the suggestions; an empty field removes the restriction.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Filter review rows by region identity or analysis state."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Filter warning"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Fit view to analysis ranges"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Flux Range"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Flux/error FITS files that follow the `*_f.fits` and `*_e.fits` pattern are paired automatically; when you pick files with other names, use the prompt to assign flux and error roles.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Hierarchical view of regions, lines, and components with drag-and-drop editing and double-click focusing.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "High-S/N spectra can produce many absorption-region candidates and slow down interaction; adjust the detection threshold to keep the list manageable.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Hosts the component parameter table while Region Detail is open. Drag the splitter handle above it to resize.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Hosts the region list below the spectrum. Drag the splitter handle above it to resize.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Identify Mode"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Identify absorption lines and assign them to line species and regions.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Identify mode focuses on reviewing detections and assigning absorption lines to species and regions.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Identify side panel"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Indicates the current subplot page and the total number of pages."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Insert a new component at the selected wavelength or region."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Inspect observed flux, model, and residuals in the spectrum view."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Ionisation stage"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Keep the project open and leave it unchanged."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Key Operations"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Keyword"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Latest count"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Line species list"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Lines already in the preset are tagged as selected, and duplicate additions are prevented automatically.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Link suggestions are not applied automatically."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Linked lines and lines"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Lists temporary lines grouped by the registration result. Group headings show whether the lines will create a new region or be added to an existing one; a warning mark flags overlaps with multiple existing regions.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Lists the lines scheduled for addition; select unwanted ones to remove them.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Lists the preset's absorption lines and shows their link-group membership in the Link column. Wavelengths, f-values, and link labels are read-only.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Load a preset JSON file and add it to the current list."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Load an existing project file."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Load observed flux and error FITS files to start a new project."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Loading resources can take a few seconds after changing the language.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Lock or unlock parameters in the parameter table shown in the bottom pane to define the search space.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Manage absorption-line presets and choose which lines should be identified and fitted together.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Manage presets"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Mask panel"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Merge"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Merge the selected regions after reviewing the impact confirmation."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Message Area"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Mode Bar"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Mode Indicator"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Mode Info Area"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Mode Subtitle"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "More actions"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Narrow down the candidates with filters for keyword, element, ionisation stage, and wavelength range.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Needs optimization badge"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "New-candidate range"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Next page"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "No Control Points Yet"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "No control points are registered. Right-click the spectrum or use the buttons to add new ones.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "No spectrum is shown in this mode. Drag and drop two FITS files (observed flux and error) or a project file (.h5) here. You can also use File > Open. The data control panel is hidden in Start mode, but it appears beneath the spectrum view after you switch to another mode.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "No spectrum or data controls appear until data has been loaded."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Not analyzed count"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Notes & Caveats"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Number of regions that have not been fitted yet. Click to filter the region list.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Number of regions whose fit result is outdated. Click to filter the region list.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Number of regions whose fit result is up to date. Click to filter the region list.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Open Analysis Structure without leaving the Analysis workspace."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Open Display in the data control panel or right-click the spectrum, or press M, to show Component profiles; each component draws its own curve in the colour of its marker and label, and this toggle is disabled outside Region Detail.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Open Display in the data control panel to show or hide the error spectrum.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Open Observation Data"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Open Project"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        'Open a popup with two checkable display toggles, "Error spectrum" (on by default) and "Component profiles" (off by default). Error spectrum shows or hides the error spectrum in the spectrum view and velocity subplots. Component profiles draws each absorption component\'s own profile curve in its identity colour, matching that component\'s marker line and label; it is available only in Analysis Region Detail and is disabled elsewhere with the tooltip "Available in Analysis region detail". Component profiles has the shortcut M. Both toggles also appear in the spectrum view\'s right-click menu.',
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        'Open existing projects through the context bar\'s "Open Project" action.',
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Open region"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Open the absorption-line database search dialog and add new absorption lines to the preset.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Open the low-emphasis actions menu. Choose Clear All to empty the temporary line list.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Open the selected region in Analysis Region Detail."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Organise the additions in the selected list and press Add Lines to apply them to the calling preset.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Page status"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Percentile"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Pick a preset in the setup header at the top of the side panel, and use the manage button to open the [Preset Management dialog](../../../menus/main_window/dialogs/PresetListDialog.md) so you can add, edit, or remove presets.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Place the cursor over an absorption feature and press V to verify that exact position in the Velocity Plot; hold Shift first when you want to see the all-species preview before deciding. Right-clicking the spectrum and selecting [Show Velocity Plot (V)] opens the plot at the position you right-clicked.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Preset list"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Preset selector"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Press Apply Planck2018 to reset the fields to the Planck 2018 recommended values.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Press Cancel to close without changing anything."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Press Cancel to keep working in the current project."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Press Don't Save to close the project and lose the unsaved changes."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Press Enter or double-click a row in the region list to open the region in Region Detail.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Press OK to apply the selected language immediately."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Press OK to confirm the value, or Cancel to keep the existing setting.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Press OK to save the settings and apply them to the main window."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Press OK to validate the selected files and load them into the project.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Press Register all (N groups), or select rows and press Register selected (N groups), to save temporary groups immediately; the status bar reports the created or extended regions, and Undo reverts the registration.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Press Run fit and adjust masks to refine residuals."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Press Save to write the project to disk and then close it."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Press V with the cursor over an absorption feature to open the plot immediately at that exact wavelength, or right-click the spectrum and select [Show Velocity Plot (V)]. Press V again or select [Back to Spectrum] to return. Dashed boundaries show the New-candidate analysis range; Display range reframes every subplot without changing candidate data.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Pressing Register saves the temporary lines to regions immediately without a confirmation step; use Undo when you need to revert a registration.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Previous page"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Quick Actions"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Readiness filter"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Recalculate Display range from New-candidate range. This action changes only the Velocity Plot view.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Recalculate Display range from the current region's line analysis ranges. This action changes only the Velocity Plot view.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Recalculates control points from the current spectrum and replaces existing points with the new estimate.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Redo"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Reference line selector"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Region filter"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Region review rows"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Region selector"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Register"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Registration result"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Remove every link group containing one of the selected rows. The lines remain in the preset.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Remove only the selected scientific link while keeping the lines."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Remove the absorption lines selected in the table from the preset."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Remove the highlighted temporary lines from the list."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Remove the line species highlighted in the selected list."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Removes every registered control point and returns the continuum to a flat baseline.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Rename the preset. Only custom presets can be edited."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Repeat the last undone action."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Reports the New-candidate analysis range represented by the dashed boundaries. Edit the value in the setup header of the Identify side panel.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Reports the current line analysis ranges represented by dashed boundaries.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Reports the cursor position in wavelength or velocity."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Reset"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Reset all entered filter conditions and return the search results to the initial state.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Restore the wavelength and flux ranges saved for the current view. If no view range is saved, show the full spectrum.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Results summary"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Return to Analysis Overview (Alt+Left)."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Return to the standard spectrum view and re-enable wavelength controls.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Revert the last action."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Review all regions in Overview, edit Structure, and analyze one region in Detail.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Review database-derived link suggestions and use Apply all to accept every valid suggestion.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Review each control point's wavelength and flux, then edit or delete entries as needed.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Review every region's analysis status, fit result, and next action."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Review the selected line's transition levels, oscillator strength, references, and other details as text.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Review the shared context bar, spectrum view, and status bar that appear in every mode.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        'Right-click a row in the region list and choose "Delete region…", or press the Delete key, to remove a region after a confirmation.',
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Right-click the spectrum to add a control point, and drag existing points to shape the continuum curve.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Run fit"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Save"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Save optimization results and statistics as CSV."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Save temporary groups to regions immediately. With no selection, the label is Register all (N groups); with selected rows, it is Register selected (N groups). Registration can be undone.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Save the current project state to disk."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Save the current settings and close the dialog."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Save the project, then close it and return to Start mode."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Search results"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Search the absorption-line database for lines and bring them into presets or Identify mode.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Select a line in the result list and check its transition data and f-value in the detail preview on the right.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Select a row for its summary; press Enter or double-click to open Region Detail.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Select a row in the parameter table to emphasise that component in the spectrum view; its label reads bold and keeps the full name on the top row, while crowded neighbours shorten and alternate onto a second row.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Select the error FITS file as well if needed."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Select the flux FITS file with the Browse... button."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Select two or more rows and use Link selected lines to create a link group; select a linked row and use Unlink to remove its group.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Selected Line List"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Selected lines"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Selected region summary"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Selecting a preset in the left list shows its composition on the right.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Selecting or clearing any member of a multiplet applies the same state to every member. When opened from preset management, an explicitly selected multiplet is also proposed as a preset link group.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Selection area"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Set the dark-energy density ΩΛ in the range 0.000–1.000. It feeds into the Ωk calculation.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Set the instrument's spectral resolution R and choose how it is applied to model calculations.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Set the lower and upper flux limits."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Set the minimum and maximum wavelengths shown."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Set the symmetric analysis range used by the next Shift preview and candidates added afterward. Existing temporary lines, registration grouping, and Velocity Plot Display range do not change.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Set the symmetric view range shared by every Identify Velocity Plot subplot and page. This display-only value does not change New-candidate range, temporary lines, grouping, or scientific Undo history.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Set the symmetric view range shared by every Velocity Plot subplot and page. This display-only value does not change line analysis ranges or scientific Undo history.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Share presets as JSON files with Import... / Export...."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shift+click an absorption feature on the spectrum to add temporary lines; the temporary line list always shows how they will be grouped into regions.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shortcuts for estimating or resetting continuum control points without leaving the panel.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Show a sample of how menus and buttons appear in the selected language.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Show all regions or limit the table to one readiness category."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Show the name of the project that is about to be closed."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shown in the bottom pane while Region Detail is open. Edit component parameters and each line's Analysis range [km/s] for the selected region. Component rows leave the analysis-range cell empty. Each parameter value cell combines the shared tie label, fitted value, and uncertainty in one display; right-click a column header to show or hide columns, and drag a header to reorder columns (visibility, order, and width are remembered for next time).",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Shows a short description of the active mode."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows link groups suggested from multiplets in the line database. Suggestions remain pending until applied.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Shows progress and notification messages."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows readiness counts, the read-only structure of the selected region, and actions to open or edit it.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Shows supplemental context for the active mode."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Shows the absorption region currently open in Region Detail."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the absorption-line candidates with wavelength, type, f-value, and more. Click a column header to change the sort order.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the current region and line context for the active Velocity Plot.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the fit status, χ² statistics, and component count for the region. A note explains the next step while fitting is unavailable.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the hierarchy of confirmed regions and their lines. A single click only selects a row and does not move the spectrum view; press Enter or double-click a region or line to move the spectrum view to its range while Identify mode stays active. Right-click a region or line row to select it and choose Open region to open the region in Analysis Region Detail, or Edit region to open it in Analysis Structure; a right-click on a line row targets its parent region.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the linked-line and line counts for the selected region. When there are six or fewer linked lines, it also shows each redshift and transition name.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the result after a successful registration. The message clears when the temporary-line workflow changes again.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Shows the target line, redshift, and observed wavelength for the active Velocity Plot.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Side Panel"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Side panel for maintaining the tree of absorption regions and absorption lines.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Single-column panel ordered along the identify workflow — the preset setup header, detection candidates, temporary lines with registration, and confirmed regions. Drag the grip handles between sections to resize them. See “Side Panel Details” below for control-by-control guidance.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Slide the detection threshold to rebuild the hit list."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Specify the FITS files for the observed flux and error and load them into the project.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Specify the Hubble constant H₀ in the range 50.0–100.0 km/s/Mpc. Step 0.1, default 67.4.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Specify the ionisation stage for the selected element. Changing the element updates the available stages.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Specify the path of the FITS file containing the observed error. When omitted, the data is treated as having no error.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Specify the resolution R = λ/Δλ in the range 10–100000. Up to two decimal places are accepted.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Spectrum View"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Split"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Split selected lines into a new region."),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Stale count"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Start mode is the landing screen where you load observation data or an existing project.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Start the fit with the current configuration and update the results."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "State that the current project has unsaved changes and ask whether to save them.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Status Bar"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Subplot selector"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Suggested links"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Supplementary panel with mode-specific controls and information."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Supported FITS inputs are 1D primary HDUs (with optional WCS), binary tables containing WAVELENGTH/WAVE/LAMBDA/WL and FLUX/INTENSITY/COUNTS/DATA columns, or multi-extension files with WAVELENGTH and FLUX (and optionally ERROR/ERR/SIGMA) extensions. Files whose column or extension names do not match cannot be loaded.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Switch the active candidate preset from the dropdown in the always-visible setup header.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Switch the display language of the whole application and check the wording in the preview.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Temporary lines"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The area that lists the selected lines. Guidance text is shown while nothing is selected.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "The area where the selected line species are shown."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The available presets. Selecting one updates the details and the state of the edit buttons.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The confirmed regions in the side panel are the same regions that Analysis Overview lists in its region list. To delete, merge, split, or unlink one, right-click its row and choose Edit region to open Analysis Structure, then follow [Analysis Structure](../../../operations/analysis-structure.md).",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "The data control panel is hidden while you stay in Start mode."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The dialog only appears while the project has unsaved changes; otherwise the project closes straight away.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The error file is optional, but providing it enables uncertainty-aware analysis.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The lookback time and comoving distance columns are hidden by default; enable them from the column header's right-click menu. Both are recalculated immediately when you apply new parameters in the Cosmology Settings dialog.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "The supported extension is .fits."),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "The valid range is 10–100000; values outside it show an error."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "The σ threshold slider and numeric input are always visible on one row and stay synchronized. The heading reports the current candidate count.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "To change a link group's members, unlink the group and then link the intended rows again.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Toggle whether the subplot’s slice will be promoted into the final grouping.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Top bar for switching modes and accessing common actions."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Turning on Apply Instrument Resolution convolves the resolution into candidate detection in Identify mode and model calculations in Analysis Region Detail.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Undo"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Unlink linked lines"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Unlocking too many parameters can destabilise convergence; introduce changes gradually.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Use Auto Estimate in the side panel to rebuild control points from the current spectrum.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Use Display range in the Velocity Plot to reframe all subplots without changing the analysis interval.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Use mouse wheel vertical scroll to zoom and horizontal scroll to pan.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "Use the context bar to switch modes and invoke shared actions."
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Velocity Plot"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Velocity plot info"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Wavelength Range"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Wavelength range"),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "When a group heading in the temporary line list carries a warning mark, the lines overlap multiple existing regions; check the assignment in Analysis Structure after registering.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "When checked, the instrument resolution is convolved into the analysis model. When unchecked, the value is stored but not applied.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "When dragging FITS files, select both flux and error files together so they are paired automatically.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "When more than six slices are available, advance to the next subplot page.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "When more than six slices are available, move back to the earlier subplot page.",
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations", "When Ωm + ΩΛ exceeds 1, Ωk shows the sign of the curvature."
    ),
    QT_TRANSLATE_NOOP(
        "ManualAnnotations",
        "Workspace for one selected region, including masks, component parameters, fitting, and export.",
    ),
    QT_TRANSLATE_NOOP("ManualAnnotations", "Zoom Area"),
    QT_TRANSLATE_NOOP("ManualAnnotations", "chappy User Manual"),
)
