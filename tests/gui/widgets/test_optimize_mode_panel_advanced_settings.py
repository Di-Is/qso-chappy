"""Tests for the RegionDetailPanel advanced settings card."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QObject, QSettings

from chappy.application.project_mapper import project_from_document, project_to_document
from chappy.core.absorption.models import AbsorptionRegion
from chappy.core.optimizer_settings import (
    DEFAULT_AUTO_CONTINUE,
    DEFAULT_MAX_FUNCTION_EVALUATIONS,
    DEFAULT_TOLERANCE,
)
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.region_detail.adapters import (
    settings_adapter as settings_adapter_module,
)
from chappy.gui.modes.analysis.region_detail.adapters.settings_adapter import (
    ADVANCED_SETTINGS_EXPANDED_KEY,
)
from chappy.gui.modes.analysis.region_detail.editor import OptimizeEditor
from chappy.gui.modes.analysis.region_detail.panel import RegionDetailPanel
from tests.gui.widgets.optimize_panel_helpers import (
    AnalysisFocusRecorder,
    NoOpModelAdditionUseCase,
    build_region_detail_usecases,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def _add_test_line(project: SpectroscopyProject, *, center_z: float) -> str:
    line = project.add_absorption_line(
        species="C IV",
        rest_wavelength=1548.195,
        center_z=center_z,
        window_kms=150.0,
        multiplet_label="",
        transition_name="C IV 1548",
        oscillator_strength=0.19,
        gamma_value=2.65e8,
        lambda_range=(1500.0, 1600.0),
    )
    return line.line_id


def _two_region_project() -> tuple[SpectroscopyProject, AbsorptionRegion, AbsorptionRegion]:
    """Build a project with two selectable regions, each carrying one line."""
    project = SpectroscopyProject()
    region_a = project.create_region_with_lines([_add_test_line(project, center_z=0.5)])
    region_b = project.create_region_with_lines([_add_test_line(project, center_z=0.6)])
    return project, region_a, region_b


class _ModeState(QObject):
    """Mode state test double that enables group selection."""


@pytest.fixture(autouse=True)
def _isolated_qsettings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the settings adapter's QSettings("Chappy", "Chappy") calls to a scratch ini file."""
    ini_path = tmp_path / "chappy_test_settings.ini"

    def _isolated_factory(_organization: str, _application: str) -> QSettings:
        return QSettings(str(ini_path), QSettings.Format.IniFormat)

    monkeypatch.setattr(settings_adapter_module, "QSettings", _isolated_factory)


@pytest.fixture
def panel(qtbot: "QtBot") -> RegionDetailPanel:
    """Create an optimize panel for advanced-settings tests."""
    editor = OptimizeEditor()
    qtbot.addWidget(editor)
    parameter_mutation_usecase, tie_set_edit_usecase = build_region_detail_usecases()
    widget = RegionDetailPanel(
        optimize_editor=editor,
        analysis_focus=AnalysisFocusRecorder(),
        mode_state=_ModeState(),
        model_addition_usecase=NoOpModelAdditionUseCase(),
        parameter_mutation_usecase=parameter_mutation_usecase,
        tie_set_edit_usecase=tie_set_edit_usecase,
        velocity_plot_active_provider=lambda: False,
        project_file_path_provider=lambda: None,
    )
    qtbot.addWidget(widget)
    return widget


def test_advanced_card_is_collapsed_by_default(panel: RegionDetailPanel) -> None:
    """The advanced settings content is hidden until the user expands it."""
    assert panel._advanced_settings_view.toggle_button().isChecked() is False
    assert panel._advanced_settings_view.content_widget().isHidden() is True


def test_expanding_toggle_shows_controls(panel: RegionDetailPanel) -> None:
    """Checking the toggle reveals the max-evaluations and tolerance controls."""
    panel._advanced_settings_view.toggle_button().setChecked(True)

    assert panel._advanced_settings_view.content_widget().isHidden() is False


def test_widgets_initialize_from_editor_defaults(panel: RegionDetailPanel) -> None:
    """Spin/combo widgets start at the editor's default optimizer settings."""
    assert (
        panel._advanced_settings_view.max_nfev_spin().value() == DEFAULT_MAX_FUNCTION_EVALUATIONS
    )
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(
        DEFAULT_TOLERANCE
    )


def test_changing_max_nfev_pushes_to_optimize_component(panel: RegionDetailPanel) -> None:
    """Editing the spin box updates the live OptimizeComponent via the editor port."""
    panel._advanced_settings_view.max_nfev_spin().setValue(4200)

    assert panel.optimize_editor.optimize_component is not None
    assert panel.optimize_editor.optimize_component.max_function_evaluations == 4200
    assert panel.optimize_editor.current_optimizer_settings(None)[0] == 4200


def test_toggling_auto_continue_pushes_to_optimize_component(panel: RegionDetailPanel) -> None:
    """Unchecking auto-continue updates the live OptimizeComponent via the editor port."""
    panel._advanced_settings_view.auto_continue_check().setChecked(False)

    assert panel.optimize_editor.optimize_component is not None
    assert panel.optimize_editor.optimize_component.auto_continue is False
    assert panel.optimize_editor.current_optimizer_settings(None)[2] is False


def test_changing_tolerance_pushes_to_optimize_component(panel: RegionDetailPanel) -> None:
    """Selecting a different tolerance updates the live OptimizeComponent via the port."""
    index = panel._advanced_settings_view._tolerance_index_for(1e-12)
    panel._advanced_settings_view.tolerance_combo().setCurrentIndex(index)

    assert panel.optimize_editor.optimize_component is not None
    assert panel.optimize_editor.optimize_component.tolerance == pytest.approx(1e-12)
    assert panel.optimize_editor.current_optimizer_settings(None)[1] == pytest.approx(1e-12)


def test_reset_restores_defaults(panel: RegionDetailPanel) -> None:
    """Reset restores both widgets and the editor port to the built-in defaults."""
    panel._advanced_settings_view.max_nfev_spin().setValue(9999)
    panel._advanced_settings_view.tolerance_combo().setCurrentIndex(
        panel._advanced_settings_view._tolerance_index_for(1e-12)
    )

    panel._advanced_settings_view.reset_button().click()

    assert (
        panel._advanced_settings_view.max_nfev_spin().value() == DEFAULT_MAX_FUNCTION_EVALUATIONS
    )
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(
        DEFAULT_TOLERANCE
    )
    assert panel.optimize_editor.current_optimizer_settings(None) == (
        DEFAULT_MAX_FUNCTION_EVALUATIONS,
        DEFAULT_TOLERANCE,
        DEFAULT_AUTO_CONTINUE,
    )


def test_toggling_persists_expanded_state_in_qsettings(panel: RegionDetailPanel) -> None:
    """Expanding the card persists the expanded flag to QSettings."""
    panel._advanced_settings_view.toggle_button().setChecked(True)

    settings = settings_adapter_module.QSettings("Chappy", "Chappy")
    assert bool(settings.value(ADVANCED_SETTINGS_EXPANDED_KEY, defaultValue=False, type=bool))


def test_set_project_initializes_widgets_from_region_settings(panel: RegionDetailPanel) -> None:
    """Loading a project applies the selected region's persisted optimizer settings."""
    project, region_a, _region_b = _two_region_project()
    project.set_region_optimizer_settings(region_a.region_id, 7500, 1e-6)
    panel.optimize_editor.set_project(project)
    panel.set_project(project)
    panel.select_focused_region(region_a)

    assert panel._advanced_settings_view.max_nfev_spin().value() == 7500
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(1e-6)


def test_current_region_id_reads_canonical_focus_not_selector(panel: RegionDetailPanel) -> None:
    """`current_region_id` reflects canonical Analysis focus, not selector state alone.

    The selector auto-selects a region as soon as `set_project` populates it, but
    canonical focus is a separate write that only lands once something calls
    `analysis_focus.focus_region` (as the shell does after a user-driven combo
    change or an explicit Overview "open region" intent). Until that write
    happens, `current_region_id` reports no focus even though the selector
    already shows a region — this is the one legitimate transient divergence
    between the two, not a wiring bug.
    """
    project, region_a, region_b = _two_region_project()
    panel.optimize_editor.set_project(project)
    panel.set_project(project)

    assert panel.current_region_id() is None

    panel.analysis_focus.focus_region(region_b.region_id)
    panel.select_focused_region(region_b)

    assert panel.current_region_id() == region_b.region_id

    panel.analysis_focus.focus_region(region_a.region_id)
    panel.render_focused_region(region_a.region_id)

    assert panel.current_region_id() == region_a.region_id


def test_region_switch_swaps_displayed_values(panel: RegionDetailPanel) -> None:
    """Selecting a different region re-initializes the widgets from its own settings."""
    project, region_a, region_b = _two_region_project()
    project.set_region_optimizer_settings(region_a.region_id, 7500, 1e-6)
    project.set_region_optimizer_settings(region_b.region_id, 2500, 1e-10)
    panel.optimize_editor.set_project(project)
    panel.set_project(project)
    panel.select_focused_region(region_a)

    assert panel._advanced_settings_view.max_nfev_spin().value() == 7500
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(1e-6)

    panel.select_focused_region(region_b)

    assert panel._advanced_settings_view.max_nfev_spin().value() == 2500
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(1e-10)


def test_editing_one_region_does_not_affect_sibling_region(panel: RegionDetailPanel) -> None:
    """Changing the active region's settings leaves an untouched sibling region alone."""
    project, region_a, region_b = _two_region_project()
    panel.optimize_editor.set_project(project)
    panel.set_project(project)
    panel.analysis_focus.focus_region(region_a.region_id)
    panel.select_focused_region(region_a)

    panel._advanced_settings_view.max_nfev_spin().setValue(9000)

    assert project.region_optimizer_settings(region_a.region_id).max_function_evaluations == 9000
    assert (
        project.region_optimizer_settings(region_b.region_id).max_function_evaluations
        == DEFAULT_MAX_FUNCTION_EVALUATIONS
    )


def test_reset_only_affects_current_region(panel: RegionDetailPanel) -> None:
    """Reset restores only the currently selected region, not other regions."""
    project, region_a, region_b = _two_region_project()
    project.set_region_optimizer_settings(region_a.region_id, 9000, 1e-12)
    project.set_region_optimizer_settings(region_b.region_id, 8000, 1e-10)
    panel.optimize_editor.set_project(project)
    panel.set_project(project)
    panel.analysis_focus.focus_region(region_a.region_id)
    panel.select_focused_region(region_a)

    panel._advanced_settings_view.reset_button().click()

    assert (
        project.region_optimizer_settings(region_a.region_id).max_function_evaluations
        == DEFAULT_MAX_FUNCTION_EVALUATIONS
    )
    assert project.region_optimizer_settings(region_b.region_id).max_function_evaluations == 8000
    assert project.region_optimizer_settings(region_b.region_id).tolerance == pytest.approx(1e-10)


def test_persistence_round_trip_with_multiple_regions(panel: RegionDetailPanel) -> None:
    """Saving and reloading a project preserves per-region settings and untouched defaults."""
    project, region_a, region_b = _two_region_project()
    region_c = project.create_region_with_lines([_add_test_line(project, center_z=0.7)])
    project.set_region_optimizer_settings(region_a.region_id, 2500, 1e-10)
    project.set_region_optimizer_settings(region_b.region_id, 5000, 1e-6)

    restored = project_from_document(project_to_document(project)).project
    panel.optimize_editor.set_project(restored)
    panel.set_project(restored)

    panel.select_focused_region(region_a)
    assert panel._advanced_settings_view.max_nfev_spin().value() == 2500
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(1e-10)

    panel.select_focused_region(region_b)
    assert panel._advanced_settings_view.max_nfev_spin().value() == 5000
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(1e-6)

    panel.select_focused_region(region_c)
    assert (
        panel._advanced_settings_view.max_nfev_spin().value() == DEFAULT_MAX_FUNCTION_EVALUATIONS
    )
    assert panel._advanced_settings_view.tolerance_combo().currentData() == pytest.approx(
        DEFAULT_TOLERANCE
    )
