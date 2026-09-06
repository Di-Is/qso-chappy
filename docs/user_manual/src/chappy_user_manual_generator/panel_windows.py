"""Specialised lightweight windows for panel-focused documentation."""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from chappy.core.absorption import AbsorptionLine
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.base import Parameter
from chappy.gui.dialogs.parameter_adjustment_dialog import ParameterAdjustmentDialog
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from chappy.gui.modes.analysis.overview.review_controller import AnalysisOverviewReviewController
from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
from chappy.gui.modes.identify.panel.panel_models import (
    CandidateRow,
    ConfirmedLineRow,
    ConfirmedRegionRow,
    LineListItem,
    RegionPreviewRow,
    TemporaryLineRow,
)
from chappy.gui.spectrum.velocity import SpectrumVelocityOverlayWidget, VelocityGridWidget
from chappy.gui.theme import Colors, get_application_stylesheet
from chappy.presentation.velocity import (
    VelocityComponentInfo,
    VelocitySliceInfo,
    build_velocity_view_data,
)
from chappy_user_manual_generator.fixtures import create_analysis_demo_project
from chappy_user_manual_generator.translations import translate_manual_text

_EXPORTER_CONTEXT = "ManualExporter"


def _create_sample_absorber_component() -> AbsorberComponent:
    """Create a sample AbsorberComponent for documentation preview."""
    component = AbsorberComponent(wavelength=1548.195, oscillator_strength=0.1908, gamma=2.65e8)
    # Set realistic sample parameter values
    component.parameters["redshift"] = Parameter(
        name="redshift", value=1.29, min_val=1.28, max_val=1.30, fixed=False
    )
    component.parameters["column_density"] = Parameter(
        name="column_density", value=13.5, min_val=10.0, max_val=22.0, fixed=False
    )
    component.parameters["b_parameter"] = Parameter(
        name="b_parameter", value=15.0, min_val=1.0, max_val=200.0, fixed=False
    )
    component.parameters["covering_factor"] = Parameter(
        name="covering_factor", value=1.0, min_val=0.0, max_val=1.0, fixed=True
    )
    return component


def _create_sample_absorption_line() -> AbsorptionLine:
    """Create a sample AbsorptionLine for documentation preview."""
    return AbsorptionLine(
        line_id="line_civ_1548",
        species="C IV",
        rest_wavelength=1548.195,
        center_z=1.29,
        window_kms=500.0,
        multiplet_label="C IV λ1548",
        transition_name="λ1548",
        oscillator_strength=0.1908,
        gamma_value=2.65e8,
    )


class AnalysisStructureDocWindow(QMainWindow):
    """Minimal window hosting Analysis Structure for documentation capture."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Analysis Structure (Doc Preview)")
        self.setProperty(
            "doc.windowTitle",
            translate_manual_text(
                _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Analysis Structure panel")
            ),
        )
        self.setProperty(
            "doc.summary",
            translate_manual_text(
                _EXPORTER_CONTEXT,
                QT_TRANSLATE_NOOP(
                    "ManualExporter",
                    "Hub for reviewing absorption region and line attributes while keeping the spectrum overlays aligned. It corresponds to callout",
                ),
            ),
        )

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        panel = StructureSidePanel(container)
        panel.setProperty("doc.include", True)
        panel.setProperty("doc.scope", "analysis_structure")
        panel.resize(420, 700)

        layout.addWidget(panel)
        self.setCentralWidget(container)

        project = create_analysis_demo_project()
        review_controller = AnalysisOverviewReviewController(
            view=panel, project_provider=lambda: project, parent=panel
        )
        panel.review_refresh_requested.connect(review_controller.refresh)
        panel.set_project(project)

        tree = getattr(panel, "_tree", None)
        if tree is not None and hasattr(tree, "expandAll"):
            tree.expandAll()

        panel.update()
        self.panel = panel
        self.project = project
        self.review_controller = review_controller


class IdentifyPanelDocWindow(QMainWindow):
    """Standalone identify side panel preview for documentation."""

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(get_application_stylesheet())
        self.setWindowTitle("Identify Panel (Doc Preview)")
        self.setProperty(
            "doc.windowTitle",
            translate_manual_text(
                _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Identify side panel")
            ),
        )
        self.setProperty(
            "doc.summary",
            translate_manual_text(
                _EXPORTER_CONTEXT,
                QT_TRANSLATE_NOOP(
                    "ManualExporter",
                    "Keeps candidate review and region registration tools in view for the entire identify workflow.",
                ),
            ),
        )

        container = QWidget(self)
        container.setObjectName("sidePanelActiveState")
        container.setStyleSheet(
            "#sidePanelActiveState {"
            f" background-color: {Colors.BACKGROUND_PANEL};"
            f" border-left: 1px solid {Colors.BORDER_DEFAULT};"
            "}"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        panel = IdentifySidePanel(container)
        panel.setProperty("doc.include", True)
        panel.setProperty("doc.scope", "identify")
        panel.resize(480, 760)

        layout.addWidget(panel)
        self.setCentralWidget(container)

        project = create_analysis_demo_project()
        panel.set_project(project)

        sample_presets = (
            (
                "preset_metals",
                translate_manual_text(
                    _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Metal doublet preset")
                ),
            ),
            (
                "preset_lya",
                translate_manual_text(
                    _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Lyman series preset")
                ),
            ),
        )
        panel.set_presets(sample_presets, current="preset_metals")

        panel.set_line_items(
            [
                LineListItem(
                    identifier="CIV1548",
                    reference="C IV",
                    name="C IV λ1548",
                    wavelength=1548.19,
                    oscillator_strength=0.1908,
                    is_reference=True,
                ),
                LineListItem(
                    identifier="CIV1550",
                    reference="C IV",
                    name="C IV λ1550",
                    wavelength=1550.77,
                    oscillator_strength=0.0952,
                ),
                LineListItem(
                    identifier="SiIV1393",
                    reference="Si IV",
                    name="Si IV λ1393",
                    wavelength=1393.76,
                    oscillator_strength=0.514,
                ),
            ]
        )

        panel.set_candidates(
            [
                CandidateRow(
                    identifier="cand_001",
                    lambda_start=3544.8,
                    lambda_end=3545.6,
                    sigma=11.2,
                    status="candidate",
                ),
                CandidateRow(
                    identifier="cand_002",
                    lambda_start=3550.0,
                    lambda_end=3550.8,
                    sigma=7.5,
                    status="unused",
                ),
                CandidateRow(
                    identifier="cand_003",
                    lambda_start=3556.2,
                    lambda_end=3557.0,
                    sigma=9.8,
                    status="identified",
                ),
            ]
        )
        panel.set_sigma_threshold(5.0)

        panel.set_temporary_lines(
            [
                TemporaryLineRow(
                    temporary_line_ids=("temp_civ",),
                    species="C IV",
                    lambda_start=3544.8,
                    lambda_end=3546.3,
                    creation_method="auto-detect",
                    transition_name="λ1548 + λ1550",
                    redshift=1.2913,
                    display_id=1,
                )
            ],
            [
                RegionPreviewRow(
                    group_id="grp_preview",
                    label="C IV 3544.8–3546.3 Å",
                    member_count=1,
                    warning=False,
                    is_existing_group=False,
                    new_lines_count=1,
                    member_temporary_line_ids=["temp_civ"],
                )
            ],
        )

        panel.set_confirmed_regions(
            [
                ConfirmedRegionRow(
                    group_id="region_001",
                    label=translate_manual_text(
                        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Region 1")
                    ),
                    lines=[
                        ConfirmedLineRow(
                            line_id="civ_1548",
                            species="C IV",
                            redshift=1.292,
                            lambda_start=3548.0,
                            lambda_end=3549.0,
                            transition_name="C IV λ1548",
                            display_id=1,
                        )
                    ],
                    is_expanded=True,
                )
            ]
        )

        confirmed_collapsible = getattr(panel, "_confirmed_collapsible", None)
        if confirmed_collapsible is not None:
            confirmed_collapsible.set_collapsed(False)

        panel.update()
        self.panel = panel
        self.project = project


class ParameterAdjustmentDocDialog(ParameterAdjustmentDialog):
    """Parameter adjustment dialog with sample data for documentation capture."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowTitle("Parameter Adjustment (Doc Preview)")
        self.setProperty(
            "doc.windowTitle",
            translate_manual_text(
                _EXPORTER_CONTEXT,
                QT_TRANSLATE_NOOP("ManualExporter", "Detailed Parameter Adjustment"),
            ),
        )
        self.setProperty(
            "doc.summary",
            translate_manual_text(
                _EXPORTER_CONTEXT,
                QT_TRANSLATE_NOOP(
                    "ManualExporter",
                    "A dialog for adjusting absorber component parameters in real-time using sliders and numeric inputs.",
                ),
            ),
        )
        self.setProperty("doc.include", True)
        self.setProperty("doc.scope", "analysis_detail_dialog")

        component = _create_sample_absorber_component()
        line = _create_sample_absorption_line()
        z_bounds = (1.28, 1.30)

        self.set_component(
            component, line=line, z_bounds=z_bounds, line_display_id=1, component_index=1
        )
        self._sample_component = component
        self._sample_line = line

        # Exclude sliders, spin boxes, and fix checkboxes from documentation table
        # (they are visually self-explanatory and the parameter labels describe their purpose)
        # The fix checkboxes are mentioned in the intro text instead
        for widget in (
            self._logn_slider,
            self._logn_spin,
            self._logn_fix,
            self._b_slider,
            self._b_spin,
            self._b_fix,
            self._z_slider,
            self._z_spin,
            self._z_fix,
            self._cf_slider,
            self._cf_spin,
            self._cf_fix,
        ):
            widget.setProperty("doc.include", False)


def _create_sample_velocity_slices() -> list[VelocitySliceInfo]:
    """Create sample velocity slices for documentation preview."""
    # Create sample components for each slice
    civ_components = [
        VelocityComponentInfo(
            component_id="comp_civ_1", velocity=-50.0, rest_wavelength=1548.195, label="C IV #1"
        ),
        VelocityComponentInfo(
            component_id="comp_civ_2", velocity=30.0, rest_wavelength=1548.195, label="C IV #2"
        ),
    ]
    siiv_components = [
        VelocityComponentInfo(
            component_id="comp_siiv_1", velocity=-50.0, rest_wavelength=1393.755, label="Si IV #1"
        )
    ]

    return [
        VelocitySliceInfo(
            rest_wavelength=1548.195,
            label="C IV λ1548",
            tie_group_key="doc:civ",
            center_z=1.292,
            line_id="line_civ_1548",
            region_id="region_001",
            is_primary=True,
            default_selected=True,
            selected=True,
            analysis_half_width_kms=150.0,
            components=civ_components,
        ),
        VelocitySliceInfo(
            rest_wavelength=1550.770,
            label="C IV λ1550",
            tie_group_key="doc:civ",
            center_z=1.292,
            line_id="line_civ_1550",
            region_id="region_001",
            is_primary=False,
            default_selected=True,
            selected=True,
            analysis_half_width_kms=150.0,
            components=civ_components,
        ),
        VelocitySliceInfo(
            rest_wavelength=1393.755,
            label="Si IV λ1393",
            tie_group_key="doc:siiv",
            center_z=1.292,
            line_id="line_siiv_1393",
            region_id="region_001",
            is_primary=False,
            default_selected=True,
            selected=True,
            analysis_half_width_kms=200.0,
            components=siiv_components,
        ),
        VelocitySliceInfo(
            rest_wavelength=1402.770,
            label="Si IV λ1402",
            tie_group_key="doc:siiv",
            center_z=1.292,
            line_id="line_siiv_1402",
            region_id="region_001",
            is_primary=False,
            default_selected=True,
            selected=True,
            analysis_half_width_kms=200.0,
            components=siiv_components,
        ),
    ]


class VelocityPlotDocWindow(QMainWindow):
    """Velocity plot window with sample data for documentation capture."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Velocity Plot (Doc Preview)")
        self.resize(1100, 720)
        self.setProperty(
            "doc.windowTitle",
            translate_manual_text(
                _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Velocity Plot")
            ),
        )
        self.setProperty(
            "doc.summary",
            translate_manual_text(
                _EXPORTER_CONTEXT,
                QT_TRANSLATE_NOOP(
                    "ManualExporter",
                    "A view that compares absorption lines in velocity space, with a"
                    " display range independent from each line's analysis range.",
                ),
            ),
        )

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        velocity_overlay = SpectrumVelocityOverlayWidget(container)
        velocity_overlay.setProperty("doc.include", False)
        velocity_overlay.setProperty("doc.scope", "analysis_detail_velocity")
        velocity_overlay.set_mode("optimize")
        velocity_overlay.set_create_visible(False)
        velocity_overlay.set_context_parts(("Region 1", "C IV / Si IV"))
        velocity_overlay.activate_display_range(
            scope_key="optimize:region_001", analysis_half_widths_kms=(150.0, 150.0, 200.0, 200.0)
        )
        velocity_overlay.resize(900, 640)
        velocity_view = velocity_overlay.grid_widget

        layout.addWidget(velocity_overlay)
        self.setCentralWidget(container)

        # Set up sample data
        project = create_analysis_demo_project()
        velocity_view.set_mode("optimize")
        velocity_view.set_center_redshift(1.29)

        # Set sample slices
        slices = _create_sample_velocity_slices()
        velocity_view.apply_view_data(
            build_velocity_view_data(
                project,
                slices,
                display_half_width_kms=velocity_view.display_half_width.value,
                include_optimize_overlays=True,
            )
        )

        # Hide selection controls (checkboxes) for cleaner documentation screenshot
        velocity_view.set_selection_controls_visible(False)

        velocity_view.refresh_plot()
        velocity_view.update()

        # Set doc properties on internal widgets for annotation
        self._apply_doc_properties(velocity_view)

        self.velocity_overlay = velocity_overlay
        self.velocity_view = velocity_view
        self.project = project

    def _apply_doc_properties(self, velocity_view: VelocityGridWidget) -> None:
        """Apply documentation properties to velocity view widgets."""
        scope = "analysis_detail_velocity"

        # Context label at the top - hidden in optimize mode (external label is used)
        # So we don't include it in the documentation

        # Subplot widgets - annotate the first one as representative
        subplot_widgets = getattr(velocity_view, "_subplot_widgets", [])
        if subplot_widgets:
            first_subplot = subplot_widgets[0]
            # Annotate the subplot's plot widget
            plot_widget = getattr(first_subplot, "_plot_widget", None)
            if plot_widget is not None:
                plot_widget.setProperty("doc.include", True)
                plot_widget.setProperty("doc.scope", scope)
                plot_widget.setProperty("doc.order", 1)
                plot_widget.setProperty(
                    "doc.label",
                    translate_manual_text(
                        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Velocity plot")
                    ),
                )
                plot_widget.setProperty(
                    "doc.desc",
                    translate_manual_text(
                        _EXPORTER_CONTEXT,
                        QT_TRANSLATE_NOOP(
                            "ManualExporter",
                            "Displays observed data, model, and residuals in velocity"
                            " space. Dashed boundaries mark the line analysis range;"
                            " a text notice appears when that range extends beyond the"
                            " view. Shift+click to add components, and drag centre lines"
                            " to adjust redshifts.",
                        ),
                    ),
                )

            # Annotate the title label
            title_label = getattr(first_subplot, "_title_label", None)
            if title_label is not None:
                title_label.setProperty("doc.include", True)
                title_label.setProperty("doc.scope", scope)
                title_label.setProperty("doc.order", 2)
                title_label.setProperty(
                    "doc.label",
                    translate_manual_text(
                        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Line name label")
                    ),
                )
                title_label.setProperty(
                    "doc.desc",
                    translate_manual_text(
                        _EXPORTER_CONTEXT,
                        QT_TRANSLATE_NOOP(
                            "ManualExporter",
                            "Shows the ion species and transition name for each subplot.",
                        ),
                    ),
                )

        # Pagination controls
        prev_button = getattr(velocity_view, "_prev_button", None)
        if prev_button is not None:
            prev_button.setProperty("doc.include", True)
            prev_button.setProperty("doc.scope", scope)
            prev_button.setProperty("doc.order", 3)
            prev_button.setProperty(
                "doc.label",
                translate_manual_text(
                    _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Previous page button")
                ),
            )
            prev_button.setProperty(
                "doc.desc",
                translate_manual_text(
                    _EXPORTER_CONTEXT,
                    QT_TRANSLATE_NOOP("ManualExporter", "Navigate to the previous page."),
                ),
            )

        page_label = getattr(velocity_view, "_page_label", None)
        if page_label is not None:
            page_label.setProperty("doc.include", True)
            page_label.setProperty("doc.scope", scope)
            page_label.setProperty("doc.order", 4)
            page_label.setProperty(
                "doc.label",
                translate_manual_text(
                    _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Page indicator")
                ),
            )
            page_label.setProperty(
                "doc.desc",
                translate_manual_text(
                    _EXPORTER_CONTEXT,
                    QT_TRANSLATE_NOOP(
                        "ManualExporter", "Shows the current page number and total pages."
                    ),
                ),
            )

        next_button = getattr(velocity_view, "_next_button", None)
        if next_button is not None:
            next_button.setProperty("doc.include", True)
            next_button.setProperty("doc.scope", scope)
            next_button.setProperty("doc.order", 5)
            next_button.setProperty(
                "doc.label",
                translate_manual_text(
                    _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Next page button")
                ),
            )
            next_button.setProperty(
                "doc.desc",
                translate_manual_text(
                    _EXPORTER_CONTEXT,
                    QT_TRANSLATE_NOOP("ManualExporter", "Navigate to the next page."),
                ),
            )
