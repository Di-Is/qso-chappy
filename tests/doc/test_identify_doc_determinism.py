from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QToolButton, QWidget

from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.identify.panel.candidate_section import IdentifyCandidateSection
from chappy.gui.modes.identify.panel.new_candidate_half_width_spinbox import (
    NewCandidateAnalysisHalfWidthSpinBox,
)
from chappy.gui.spectrum.velocity import (
    SpectrumVelocityOverlayWidget,
    VelocityDisplayHalfWidthSpinBox,
)
from chappy.gui.theme import Colors
from chappy_user_manual_generator import pipeline as doc_pipeline
from chappy_user_manual_generator.annotations import apply_doc_annotations
from chappy_user_manual_generator.exporter import resolve_section
from chappy_user_manual_generator.fixtures import apply_fixture
from chappy_user_manual_generator.panel_windows import IdentifyPanelDocWindow


def test_identify_capture_pins_sigma_threshold_and_candidate_count(qtbot) -> None:
    """Identify mode's detection must be deterministic across doc-generation runs (F-02).

    ``analysis-demo`` pre-registers its only spectral feature into a
    confirmed region, so detection under the pinned representative threshold
    (5.0 sigma) yields zero candidates deterministically — a legitimate,
    reproducible outcome rather than a fixture defect.
    """
    app = QCoreApplication.instance()
    assert app is not None
    QCoreApplication.setOrganizationName("Chappy")
    QCoreApplication.setApplicationName("Chappy")

    with doc_pipeline._doc_environment(headless=True):
        window = doc_pipeline._create_window("main", headless=True)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)

        apply_fixture("analysis-demo", app, window)
        doc_pipeline._switch_mode(window, EditingMode.IDENTIFY)
        qtbot.wait(0)

        panel = window.findChild(QWidget, "modeSidePanel_identify")
        section = window.findChild(IdentifyCandidateSection, "identifyCandidateSection")
        assert panel is not None
        assert section is not None

        assert section.current_sigma_value == doc_pipeline.IDENTIFY_DOC_SIGMA_THRESHOLD
        assert len(panel.current_candidates) == 0

        window.close()


def test_identify_demo_fixture_shows_all_candidate_statuses(qtbot) -> None:
    """``identify-demo`` must deterministically show every candidate status.

    The doc fixture seeds a registered doublet, one temporary line, and one
    unclaimed feature so identify screenshots display identified, candidate,
    and unused rows under the pinned 5.0 sigma threshold.
    """
    app = QCoreApplication.instance()
    assert app is not None
    QCoreApplication.setOrganizationName("Chappy")
    QCoreApplication.setApplicationName("Chappy")

    with doc_pipeline._doc_environment(headless=True):
        window = doc_pipeline._create_window("main", headless=True)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)

        apply_fixture("identify-demo", app, window)
        doc_pipeline._switch_mode(window, EditingMode.IDENTIFY)
        qtbot.wait(0)

        panel = window.findChild(QWidget, "modeSidePanel_identify")
        assert panel is not None

        candidates = panel.current_candidates
        assert len(candidates) == 4
        statuses = sorted(row.status for row in candidates)
        assert statuses == ["candidate", "identified", "identified", "unused"]

        window.close()


def test_identify_velocity_capture_shows_overlay_headers_subplot_and_annotations(qtbot) -> None:
    """The custom capture must traverse the typed runtime and document visible velocity UI."""
    app = QCoreApplication.instance()
    assert app is not None

    with doc_pipeline._doc_environment(headless=True):
        window = doc_pipeline._create_window("main", headless=True)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)
        try:
            apply_fixture("identify-demo", app, window)
            doc_pipeline._switch_mode(window, EditingMode.IDENTIFY)
            qtbot.wait(0)

            capture = next(
                spec
                for spec in doc_pipeline._identify_custom_captures(window, app)
                if spec.suffix == "_velocity"
            )
            assert capture.pre_capture is not None
            capture.pre_capture(window)
            apply_doc_annotations(window)
            assert capture.post_annotation is not None
            capture.post_annotation(window)
            qtbot.wait(0)

            operations_by_scope = window.property("doc.operationsByScopeKey")
            assert isinstance(operations_by_scope, dict)
            assert (
                "Place the cursor over an absorption feature and press V to verify that "
                "exact position in the Velocity Plot; hold Shift first when you want to "
                "see the all-species preview before deciding. Right-clicking the spectrum "
                "and selecting [Show Velocity Plot (V)] opens the plot at the position you "
                "right-clicked." in operations_by_scope["identify"]
            )

            overlay = window.findChild(SpectrumVelocityOverlayWidget, "velocityPlotContainer")
            info_label = window.findChild(QLabel, "velocityPlotInfo")
            add_button = window.findChild(QPushButton, "velocityPlotCreateButton")
            exit_button = window.findChild(QPushButton, "velocityPlotExitButton")
            display_spinbox = window.findChild(
                VelocityDisplayHalfWidthSpinBox, "velocityDisplayHalfWidthSpinBox"
            )
            fit_button = window.findChild(QPushButton, "velocityFitViewToAnalysisRangesButton")
            analysis_summary = window.findChild(QLabel, "velocityAnalysisRangeSummary")
            assert overlay is not None
            assert info_label is not None
            assert add_button is not None
            assert exit_button is not None
            assert display_spinbox is not None
            assert fit_button is not None
            assert analysis_summary is not None
            assert overlay.isVisibleTo(window)
            assert Colors.TEXT_SECONDARY in info_label.styleSheet()
            assert add_button.text() in {
                "Add selected lines to temporary list",
                "選択した線を一時ラインに追加",
            }
            assert exit_button.text().endswith(("Back to Spectrum", "スペクトルに戻る"))
            assert add_button.property("doc.include") is True
            assert exit_button.property("doc.include") is True
            assert add_button.property("doc.section") == "identify_velocity"
            assert resolve_section(exit_button, "identify") == "identify_velocity"
            assert resolve_section(display_spinbox, "identify") == "identify_velocity"
            assert resolve_section(fit_button, "identify") == "identify_velocity"
            assert resolve_section(analysis_summary, "identify") == "identify_velocity"
            assert display_spinbox.accepted_value.value == 225.0
            assert "200" in analysis_summary.text()

            velocity_view = overlay.grid_widget
            assert velocity_view._slice_meta
            first_subplot = velocity_view._subplot_widgets[0]
            assert first_subplot.isVisibleTo(overlay)
            assert first_subplot.render_state().placeholder_visible is False
            assert first_subplot.property("doc.include") is True
            assert first_subplot.property("doc.section") == "identify_velocity"
        finally:
            window.identify_velocity_runtime.hide_velocity_plot()
            window.close()
            app.processEvents()


def test_identify_panel_doc_window_uses_application_side_panel_surface(qtbot) -> None:
    """The standalone panel capture must preserve the dark production dock surface."""
    window = IdentifyPanelDocWindow()
    qtbot.addWidget(window)
    window.resize(480, 760)
    window.show()
    qtbot.waitExposed(window)

    surface = window.findChild(QWidget, "sidePanelActiveState")
    preset_combo = window.findChild(QComboBox, "identifyPresetCombo")
    reference_combo = window.findChild(QComboBox, "identifyReferenceLineCombo")
    confirmed_header = window.findChild(QToolButton, "identifyConfirmedCollapsibleHeader")
    candidate_section = window.findChild(IdentifyCandidateSection, "identifyCandidateSection")
    half_width_spinbox = window.findChild(
        NewCandidateAnalysisHalfWidthSpinBox, "identifyNewCandidateAnalysisHalfWidthSpinBox"
    )
    assert surface is not None
    assert preset_combo is not None
    assert reference_combo is not None
    assert confirmed_header is not None
    assert candidate_section is not None
    assert half_width_spinbox is not None
    assert window.findChild(QWidget, "identifyPresetCollapsible") is None
    assert Colors.BACKGROUND_PANEL in surface.styleSheet()
    assert Colors.TEXT_PRIMARY in window.styleSheet()
    apply_doc_annotations(window)
    assert preset_combo.property("doc.labelKey") == "Preset selector"
    assert reference_combo.property("doc.labelKey") == "Reference line selector"
    assert confirmed_header.property("doc.labelKey") == "Confirmed Regions section header"
    assert candidate_section.property("doc.labelKey") == "Detection candidates"
    assert half_width_spinbox.property("doc.labelKey") == "New-candidate range"
    assert candidate_section._sigma_label.isVisibleTo(window)
    assert candidate_section._sigma_slider.isVisibleTo(window)
    assert candidate_section._sigma_spin.isVisibleTo(window)
    assert window.findChild(QWidget, "identifyCandidateFrame") is None
    assert window.findChild(QWidget, "identifySigmaAdjustButton") is None

    window.close()
