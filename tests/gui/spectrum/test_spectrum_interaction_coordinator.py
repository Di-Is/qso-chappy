"""Tests for SpectrumInteractionCoordinator."""

from __future__ import annotations

import contextlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import numpy as np
import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from chappy.application.history import ComponentParameterState
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.editing_mode import EditingMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumContext,
    InteractionChannel,
    InteractionId,
    InteractionPhase,
    InteractionStateSnapshot,
    RectZoomContext,
)
from chappy.presentation.spectrum import AbsorptionMarkerInput
from chappy.gui.protocols.intent_types import (
    AddContinuumPointIntent,
    DeleteContinuumPointIntent,
    PanIntent,
    ToggleIdentifyPreviewLockIntent,
    ToggleVelocityPlotIntent,
)
from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.spectrum.policy import SpectrumInputCapabilities
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.application.spectrum.range_usecase import RangeNavigationUseCase
from chappy.gui.shell.absorber_model_mutation_controller import (
    AbsorberModelMutationController,
    AbsorberModelMutationPorts,
)
from chappy.gui.spectrum.interaction_controller_factory import SpectrumInteractionControllerFactory
from chappy.gui.spectrum.navigation_controller import SpectrumNavigationControllerFactory
from chappy.gui.spectrum.spectrum_plot import SpectrumPlotHost
from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
from chappy.gui.spectrum.spectrum_view_components import SpectrumViewComponents
from chappy.plotting.components.continuum_editor import ContinuumContextState
from chappy.presentation.spectrum import ModelWindowBuilder, SpectrumRenderDTOAssembler
from scripts.i18n_lupdate import run_lupdate
from .fixtures.mock_spectrum_view import (
    MockSignal,
    MockSpectrumDataBridge,
    MockSpectrumView,
    StateRecordingPlotComponent,
    StateRecordingRangeComponent,
)

SPECTRUM_PRESENTER_SOURCES = {
    "Add Control Point",
    "Delete Control Point",
    "Always show candidate overlay",
}


class _History:
    """No-op scientific history owner for presenter integration tests."""

    def atomic_recording(self) -> contextlib.AbstractContextManager[None]:
        """Return a valid history transaction scope."""
        return contextlib.nullcontext()

    def record_model_edit_params(
        self,
        component_ids: list[str],
        param_name: str,
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        region_id: str | None,
    ) -> None:
        """Accept one parameter history record."""
        _ = component_ids, param_name, before_states, after_states, region_id


def _read_ts_sources(ts_path: Path) -> set[str]:
    """Return source strings extracted into a Qt TS file.

    Args:
        ts_path: Path to the generated TS catalog.

    Returns:
        Extracted source text values.
    """
    tree = ET.parse(ts_path)
    root = tree.getroot()
    return {source.text for source in root.findall(".//message/source") if source.text is not None}


class _PresenterView:
    """Minimal view dependency for SpectrumInteractionCoordinator tests."""

    def get_velocity_plot_y_range(self) -> tuple[float, float] | None:
        """Return no override flux range."""
        return None


class _CursorWidget:
    """Record cursor updates requested by presenter feedback."""

    def __init__(self) -> None:
        self.cursors: list[Qt.CursorShape] = []

    def setCursor(self, cursor: Qt.CursorShape) -> None:  # noqa: N802
        """Record the requested cursor shape."""
        self.cursors.append(cursor)


class _ContinuumEditor:
    """Record continuum editor context menu requests."""

    def __init__(self) -> None:
        self.add_requests: list[tuple[float, float]] = []
        self.delete_requests: list[int] = []
        self.context_state = ContinuumContextState(
            wavelength=1215.67, flux=0.8, nearest_index=2, can_add=True, can_delete=True
        )

    def get_context_state(self, wavelength: float, flux: float | None) -> ContinuumContextState:
        """Return the configured continuum context state."""
        return self.context_state

    def request_add_point(self, wavelength: float, flux: float) -> None:
        """Record an add point request."""
        self.add_requests.append((wavelength, flux))

    def request_delete_point(self, index: int) -> None:
        """Record a delete point request."""
        self.delete_requests.append(index)


class _ContinuumPlotWidget:
    """Expose a continuum editor through the plot widget contract."""

    def __init__(self, continuum_editor: _ContinuumEditor) -> None:
        self.continuum_editor = continuum_editor


class _ModeIntentSink:
    """Record mode-specific spectrum intents delegated by the facade."""

    def __init__(self) -> None:
        self.mode_clicks: list[tuple[float, float, int]] = []
        self.velocity_shortcut_count = 0
        self.context_menu_intents: list[object] = []
        self.continuum_intents: list[object] = []
        self.identify_intents: list[object] = []

    def handle_mode_click(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Record a raw mode click."""
        self.mode_clicks.append((wavelength, flux, modifiers))

    def handle_mode_velocity_shortcut(self) -> None:
        """Record a velocity shortcut."""
        self.velocity_shortcut_count += 1

    def handle_context_menu_intent(self, intent: object) -> None:
        """Record a context menu intent."""
        self.context_menu_intents.append(intent)

    def handle_continuum_intent(self, intent: object) -> None:
        """Record a continuum intent."""
        self.continuum_intents.append(intent)

    def handle_identify_intent(self, intent: object) -> None:
        """Record an identify intent."""
        self.identify_intents.append(intent)


class _RangeCoordinatorRecorder:
    """Range coordinator fake that records delegated calls."""

    def __init__(self) -> None:
        self.range_updates: list[tuple[str, float, float, tuple[float, float] | None, bool]] = []
        self.auto_flux_count = 0
        self.disable_auto_adjust_count = 0
        self.reset_requests: list[
            tuple[tuple[float, float] | None, tuple[float, float] | None]
        ] = []
        self.data_bridge_range_changes: list[tuple[float, float, float, float]] = []

    def coordinate_range_update(
        self,
        source: str,
        min_wave: float,
        max_wave: float,
        *,
        flux_range: tuple[float, float] | None = None,
        record_history: bool = True,
        old_wave_range: tuple[float, float] | None = None,
        old_flux_range: tuple[float, float] | None = None,
    ) -> None:
        """Record a delegated range update."""
        assert old_wave_range is None
        assert old_flux_range is None
        self.range_updates.append((source, min_wave, max_wave, flux_range, record_history))

    def handle_auto_flux_range_request(self) -> None:
        """Record a delegated auto-flux request."""
        self.auto_flux_count += 1

    def disable_auto_adjust_y(self) -> None:
        """Record a delegated auto-adjust disable request."""
        self.disable_auto_adjust_count += 1

    def reset_view_ranges(
        self,
        *,
        wavelength_range: tuple[float, float] | None = None,
        flux_range: tuple[float, float] | None = None,
    ) -> None:
        """Record delegated reset bounds."""
        self.reset_requests.append((wavelength_range, flux_range))

    def handle_data_bridge_range_changed(
        self, min_wave: float, max_wave: float, min_flux: float, max_flux: float
    ) -> None:
        """Record delegated data-bridge range changes."""
        self.data_bridge_range_changes.append((min_wave, max_wave, min_flux, max_flux))


class _OptimizeIntegration:
    """Optimize integration fake for absorber intent routing tests."""

    def __init__(self) -> None:
        self.cursor_mode = "crosshair"
        self.cursor_requests: list[tuple[float, bool]] = []
        self.velocity_shortcut_count = 0

    def update_cursor_for_shift(self, wavelength: float, shift_pressed: bool) -> str:
        """Record optimize cursor feedback requests."""
        self.cursor_requests.append((wavelength, shift_pressed))
        return self.cursor_mode

    def handle_cursor_position(self, wavelength: float, shift_pressed: bool) -> None:
        """Record routed cursor events."""
        self.cursor_requests.append((wavelength, shift_pressed))

    def handle_velocity_shortcut(self) -> None:
        """Record optimize velocity shortcut requests."""
        self.velocity_shortcut_count += 1


class _InteractorComponent:
    """Minimal interactor dependency for composition lifecycle tests."""

    def __init__(self) -> None:
        self.sig_interaction_snapshot = MockSignal()
        self.sig_cursor_position_changed = MockSignal()
        self.rect_zoom_enabled = False

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Record rectangle zoom mode."""
        self.rect_zoom_enabled = enabled

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return the recorded rectangle zoom mode."""
        return self.rect_zoom_enabled

    def set_selected_line_absorbers(self, _absorber_ids: set[str] | None) -> None:
        """Accept selected absorber updates."""

    def cancel_mask_selection_interaction(self, *, reason: str | None = None) -> bool:
        """Accept mask cleanup."""
        _ = reason
        return False


class _ModeAwareInteractorComponent(_InteractorComponent):
    """Interactor double that records public capability updates."""

    def __init__(self) -> None:
        super().__init__()
        self.capabilities: list[SpectrumInputCapabilities] = []

    def set_mode_capabilities(self, capabilities: SpectrumInputCapabilities) -> None:
        """Record capability updates sent through the public interactor API."""
        self.capabilities.append(capabilities)


def _make_presenter_components(
    *,
    data_bridge: MockSpectrumDataBridge,
    plot_host: object | None = None,
    range_input: object | None = None,
    interactor: object | None = None,
) -> SpectrumViewComponents:
    """Build required Facade components for direct presenter tests."""
    return SpectrumViewComponents(
        data_bridge=cast("SpectrumDataBridge", data_bridge),
        plot_host=cast("SpectrumPlotHost", plot_host or StateRecordingPlotComponent()),
        range_input_controls=cast(
            "SpectrumRangeInputControls", range_input or StateRecordingRangeComponent()
        ),
        interactor=cast("SpectrumInputFacadePort", interactor or _InteractorComponent()),
    )


class _MarkerPlotWidget:
    """Plot widget fake recording absorption marker updates."""

    def __init__(self) -> None:
        self.markers: list[AbsorptionMarkerInput] = []
        self.clear_count = 0

    def add_absorption_marker(self, marker: AbsorptionMarkerInput) -> None:
        """Record an absorption marker request."""
        self.markers.append(marker)

    def clear_absorption_line_markers(self) -> None:
        """Record a marker clear request."""
        self.clear_count += 1

    def refresh_absorption_marker_labels(self) -> None:
        """Accept the post-add label refresh request."""

    def toggle_absorption_line_markers(self, show: bool) -> None:
        """Record the post-rebuild visibility sync."""
        self.marker_visibility = show


def _make_project_with_absorber() -> tuple[SpectroscopyProject, AbsorberComponent]:
    """Create a small real project with one absorber component."""
    wavelength = np.linspace(1200.0, 1240.0, 401)
    flux = np.ones_like(wavelength)
    error = np.full_like(wavelength, 0.05)
    project = SpectroscopyProject(name="Presenter Test")
    project.model.set_observed_spectrum(Spectrum(wavelength=wavelength, flux=flux, error=error))
    absorber = AbsorberComponent(
        name="test_absorber",
        wavelength=1215.67,
        column_density=13.5,
        b_parameter=20.0,
        redshift=0.0,
        component_id="test_id",
    )
    project.model.add_component(absorber)
    return project, absorber


def _plot_host_with_marker_widget(qtbot: "QtBot") -> tuple[SpectrumPlotHost, _MarkerPlotWidget]:
    """Create a spectrum plot host with a marker-recording plot widget."""
    parent = QWidget()
    qtbot.addWidget(parent)
    plot_host = SpectrumPlotHost(parent, SpectrumRenderDTOAssembler(ModelWindowBuilder()))
    marker_widget = _MarkerPlotWidget()
    plot_host.plot_widget = cast("SpectrumPlotSurfaceProtocol", marker_widget)
    return plot_host, marker_widget


def _attach_absorber_model_mutation_owner(presenter: SpectrumInteractionCoordinator) -> None:
    """Attach a shell-owned absorber mutation controller for tests."""

    def refresh_plot() -> None:
        plot_host = presenter.plot_host
        data_bridge = presenter.data_bridge
        if plot_host is not None and data_bridge is not None and data_bridge.project:
            plot_host.update_from_project(data_bridge.project)

    def emit_data_updated() -> None:
        if presenter.data_bridge is not None:
            presenter.data_bridge.data_updated.emit()

    owner = AbsorberModelMutationController(
        ports=AbsorberModelMutationPorts(
            project_provider=lambda: (
                presenter.data_bridge.project if presenter.data_bridge is not None else None
            ),
            line_info_provider=presenter._get_line_info_for_component,
            history_provider=_History,
            plot_widget_provider=lambda: (
                presenter.plot_host.plot_widget
                if isinstance(presenter.plot_host, SpectrumPlotHost)
                else None
            ),
            plot_refresh_callback=refresh_plot,
            data_updated_callback=emit_data_updated,
            refresh_optimize_callback=presenter._refresh_optimize_tree_view,
            focus_component_callback=presenter._focus_optimize_component,
            refresh_velocity_overlay_callback=lambda: None,
        )
    )
    presenter.attach_absorber_model_mutation_owner(owner)


class TestSpectrumInteractionCoordinator:
    """Test suite for SpectrumInteractionCoordinator."""

    @pytest.fixture
    def mock_view(self) -> MockSpectrumView:
        """Create mock spectrum view."""
        return MockSpectrumView()

    @pytest.fixture
    def mock_data_bridge(self) -> MockSpectrumDataBridge:
        """Create mock data bridge."""
        return MockSpectrumDataBridge()

    @pytest.fixture
    def presenter(
        self, mock_view: MockSpectrumView, mock_data_bridge: MockSpectrumDataBridge
    ) -> SpectrumInteractionCoordinator:
        """Create presenter with mocks."""
        _ = mock_view
        actual_view = _PresenterView()
        presenter = SpectrumInteractionCoordinator(
            actual_view,
            SpectrumNavigationControllerFactory(RangeNavigationUseCase()),
            SpectrumInteractionControllerFactory(),
            _make_presenter_components(data_bridge=mock_data_bridge),
        )
        _attach_absorber_model_mutation_owner(presenter)
        return presenter

    def test_initialization(self, presenter: SpectrumInteractionCoordinator) -> None:
        """Test presenter initialization."""
        assert presenter is not None
        assert presenter.data_bridge is not None

    def test_absorber_parameter_change_no_project(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Test parameter change without project."""
        presenter.data_bridge = None

        # Should not raise error
        presenter.update_absorber_param("test_absorber", "column_density", 14.0)

    def test_absorber_parameter_change_with_project(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Parameter changes should update a real absorber and refresh model data."""
        project, absorber = _make_project_with_absorber()
        plot = StateRecordingPlotComponent()
        presenter.data_bridge.project = project
        presenter.plot_host = cast("SpectrumPlotHost", plot)

        emissions: list[bool] = []
        presenter.data_bridge.data_updated.connect(lambda: emissions.append(True))

        # Execute parameter change
        presenter.update_absorber_param("test_absorber", "column_density", 14.0)

        assert absorber.get_parameter_value("column_density") == pytest.approx(14.0)
        assert project.model.model_spectrum is not None
        np.testing.assert_allclose(
            project.model.model_spectrum.flux,
            absorber.calculate(project.model.observed_spectrum.wavelength),
        )
        assert emissions == [True]
        assert plot.updated_project is project

    def test_coordinate_range_update(self, presenter: SpectrumInteractionCoordinator) -> None:
        """Range updates should delegate to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.coordinate_range_update("test", 3000.0, 5000.0)

        assert range_coordinator.range_updates == [("test", 3000.0, 5000.0, None, True)]

    def test_coordinate_range_update_syncs_velocity_flux_range(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Flux range updates should delegate flux limits to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.coordinate_range_update("manual", 3000.0, 5000.0, flux_range=(-0.25, 1.25))

        assert range_coordinator.range_updates == [("manual", 3000.0, 5000.0, (-0.25, 1.25), True)]

    def test_coordinate_identify_preview_lock_intent_updates_coordinator(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Identify intents should delegate to the attached mode sink."""
        sink = _ModeIntentSink()
        presenter.attach_mode_intent_sink(sink)
        intent = ToggleIdentifyPreviewLockIntent(enabled=True)

        presenter.coordinate_identify_intent(intent)

        assert sink.identify_intents == [intent]

    def test_coordinate_continuum_add_intent_updates_editor(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Continuum add intents should delegate to the attached mode sink."""
        sink = _ModeIntentSink()
        presenter.attach_mode_intent_sink(sink)
        intent = AddContinuumPointIntent(wavelength=1215.67, flux=0.8)

        presenter.coordinate_continuum_intent(intent)

        assert sink.continuum_intents == [intent]

    def test_coordinate_continuum_delete_intent_updates_editor(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Continuum delete intents should delegate to the attached mode sink."""
        sink = _ModeIntentSink()
        presenter.attach_mode_intent_sink(sink)
        intent = DeleteContinuumPointIntent(index=2)

        presenter.coordinate_continuum_intent(intent)

        assert sink.continuum_intents == [intent]

    def test_coordinate_context_menu_intent_delegates_to_mode_sink(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Context menu intents should delegate to the attached mode sink."""
        sink = _ModeIntentSink()
        presenter.attach_mode_intent_sink(sink)
        intent = ToggleVelocityPlotIntent(wavelength=1215.67)

        presenter.coordinate_context_menu_intent(intent)

        assert sink.context_menu_intents == [intent]

    def test_coordinate_mode_click_delegates_to_mode_sink(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Raw mode clicks should delegate to the attached mode sink."""
        sink = _ModeIntentSink()
        presenter.attach_mode_intent_sink(sink)

        presenter.coordinate_mode_click(1215.67, 0.8, 4)

        assert sink.mode_clicks == [(1215.67, 0.8, 4)]

    def test_mode_intent_methods_require_attached_sink(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Mode-specific intent routing should fail fast without a shell sink."""
        with pytest.raises(RuntimeError, match="Mode intent sink is required"):
            presenter.coordinate_continuum_intent(
                AddContinuumPointIntent(wavelength=1215.67, flux=0.8)
            )

    def test_handle_navigation_intent_delegates_to_navigation_controller(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Navigation handling should stay a thin controller delegation."""
        handled_intents: list[PanIntent] = []

        def handle_navigation_intent(intent: PanIntent) -> None:
            """Record delegated navigation intents."""
            handled_intents.append(intent)

        presenter._navigation_controller = cast(
            "object", SimpleNamespace(handle_navigation_intent=handle_navigation_intent)
        )

        intent = PanIntent(fraction=0.2)
        presenter.handle_navigation_intent(intent)

        assert handled_intents == [intent]

    def test_reset_view_ranges_auto_scales_when_no_bounds(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Reset requests should delegate to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.reset_view_ranges()

        assert range_coordinator.reset_requests == [(None, None)]

    def test_reset_view_ranges_applies_explicit_bounds(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Explicit reset bounds should delegate to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.reset_view_ranges(wavelength_range=(1200.0, 2200.0), flux_range=(-0.2, 0.8))

        assert range_coordinator.reset_requests == [((1200.0, 2200.0), (-0.2, 0.8))]

    def test_reset_view_ranges_without_flux_uses_plot_bounds(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Reset without flux bounds should delegate missing flux to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.reset_view_ranges(wavelength_range=(1100.0, 1900.0))

        assert range_coordinator.reset_requests == [((1100.0, 1900.0), None)]

    def test_auto_flux_range_requires_data_bridge(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Auto flux requests should delegate to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.handle_auto_flux_range_request()

        assert range_coordinator.auto_flux_count == 1

    def test_auto_flux_range_without_spectrum_uses_plot_fallback(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Auto-adjust disabling should delegate to RangeCoordinator."""
        range_coordinator = _RangeCoordinatorRecorder()
        presenter._range_coordinator = cast("object", range_coordinator)

        presenter.disable_auto_adjust_y()

        assert range_coordinator.disable_auto_adjust_count == 1

    def test_optimize_integration_attach_rejects_none(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Optimize integration attachment requires an explicit dependency."""
        with pytest.raises(TypeError, match="Optimize integration is required"):
            presenter.attach_optimize_integration(None)  # type: ignore[arg-type]

    def test_optimize_velocity_shortcut_requires_attached_integration(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Velocity shortcut routing should fail fast without a shell sink."""

        with pytest.raises(RuntimeError, match="Mode intent sink is required"):
            presenter.coordinate_mode_velocity_shortcut()

    def test_optimize_velocity_shortcut_uses_attached_integration(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Velocity shortcuts should delegate to the attached mode sink."""
        sink = _ModeIntentSink()
        presenter.attach_mode_intent_sink(sink)

        presenter.coordinate_mode_velocity_shortcut()

        assert sink.velocity_shortcut_count == 1

    def test_absorption_marker_payload_uses_required_component_values(
        self, qtbot: "QtBot"
    ) -> None:
        """Absorption marker payload should use component values without defaults."""
        project, absorber = _make_project_with_absorber()
        absorber.oscillator_strength = 0.6123
        absorber.gamma = 2.6e8
        plot_host, marker_widget = _plot_host_with_marker_widget(qtbot)

        plot_host.update_absorption_line_markers(project)

        assert marker_widget.clear_count == 1
        assert len(marker_widget.markers) == 1
        marker = marker_widget.markers[0]
        assert marker.name == "test_absorber"
        assert marker.rest_wavelength == pytest.approx(1215.67)
        assert marker.redshift == pytest.approx(0.0)
        assert marker.column_density == pytest.approx(13.5)
        assert marker.b_parameter == pytest.approx(20.0)
        assert marker.oscillator_strength == pytest.approx(0.6123)
        assert marker.gamma == pytest.approx(2.6e8)
        assert marker.component_id == "test_id"

    def test_absorption_marker_payload_requires_component_parameters(self, qtbot: "QtBot") -> None:
        """Missing marker parameters should fail fast instead of using physical defaults."""
        project, absorber = _make_project_with_absorber()
        del absorber.parameters["column_density"]
        plot_host, _ = _plot_host_with_marker_widget(qtbot)

        with pytest.raises(RuntimeError, match="column_density"):
            plot_host.update_absorption_line_markers(project)

    def test_cursor_signal_updates_optimize_cursor_feedback(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Interactor cursor signals should drive optimize cursor feedback."""
        cursor_widget = _CursorWidget()
        presenter.plot_host = SimpleNamespace(plot_widget=cursor_widget)  # type: ignore[assignment]
        presenter._current_policy = analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL)
        integration = _OptimizeIntegration()
        presenter.attach_optimize_integration(cast("SpectrumModeIntegrationPort", integration))

        class DummyInteractor:
            def __init__(self) -> None:
                self.sig_interaction_snapshot = MockSignal()
                self.sig_cursor_position_changed = MockSignal()

        interactor = DummyInteractor()
        presenter._connect_interactor_signals(interactor)  # type: ignore[arg-type]
        shift_value = Qt.KeyboardModifier.ShiftModifier.value
        assert isinstance(shift_value, int)

        interactor.sig_cursor_position_changed.emit(1215.67, 0.8, shift_value)

        assert integration.cursor_requests == [(1215.67, True)]

    def test_policy_updates_interactor_through_public_api(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Neutral policies should use the interactor public capability API."""
        interactor = _ModeAwareInteractorComponent()
        presenter.interactor = cast("SpectrumInputFacadePort", interactor)
        presenter.commit_policy(spectrum_interaction_mode_policy(EditingMode.ANALYSIS))

        assert interactor.capabilities == [
            spectrum_interaction_mode_policy(EditingMode.ANALYSIS).input_capabilities
        ]

    def test_policy_transition_runs_pending_mask_and_drag_cleanup(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Policy application must cancel incomplete mutable interactions first."""
        interactor = _ModeAwareInteractorComponent()
        presenter.interactor = cast("SpectrumInputFacadePort", interactor)

        with (
            patch.object(
                presenter._mask_interaction_controller, "cancel_mask_selection"
            ) as cancel_mask,
            patch.object(
                presenter._absorber_interaction_controller, "cancel_active_drags"
            ) as cancel_drag,
        ):
            presenter.cleanup_for_policy(spectrum_interaction_mode_policy(EditingMode.IDENTIFY))

        cancel_mask.assert_called_once_with()
        cancel_drag.assert_called_once_with()

    def test_apply_interaction_state_snapshot_emits_signal(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Presenter should store snapshots and notify interested observers."""
        emissions: list[InteractionStateSnapshot[RectZoomContext | AbsorberDragContext]] = []
        presenter.interaction_snapshot_applied.connect(emissions.append)

        snapshot = InteractionStateSnapshot(
            interaction_id=InteractionId("rect-zoom-1"),
            channel=InteractionChannel.RECT_ZOOM,
            phase=InteractionPhase.ARMED,
            context=RectZoomContext(
                start=(4100.0, 0.2), current=(4200.0, 0.25), end=None, bounds=None
            ),
        )

        presenter.apply_interaction_state_snapshot(snapshot)

        assert presenter._latest_interaction_snapshot == snapshot
        assert emissions == [snapshot]

    def test_apply_absorber_drag_snapshot_handles_channel(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Presenter should handle absorber drag snapshots."""
        emissions: list[InteractionStateSnapshot[AbsorberDragContext]] = []
        presenter.interaction_snapshot_applied.connect(emissions.append)

        snapshot = InteractionStateSnapshot(
            interaction_id=InteractionId("abs-drag-1"),
            channel=InteractionChannel.ABSORBER_DRAG,
            phase=InteractionPhase.ACTIVE,
            context=AbsorberDragContext(
                absorber_id="abs-123",
                start=(4200.0, 0.3),
                current=(4250.0, 0.32),
                end=None,
                modifiers=0,
                cancel_reason=None,
            ),
        )

        presenter.apply_interaction_state_snapshot(snapshot)

        assert presenter._latest_interaction_snapshot == snapshot
        assert emissions == [snapshot]

    def test_apply_interaction_state_snapshot_failure_propagates(
        self, presenter: SpectrumInteractionCoordinator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Snapshot handler failures are internal state errors and must propagate."""
        monkeypatch.setattr(
            presenter._interaction_state_coordinator,
            "apply_interaction_state_snapshot",
            lambda _snapshot: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        snapshot = InteractionStateSnapshot(
            interaction_id=InteractionId("rect-zoom-2"),
            channel=InteractionChannel.RECT_ZOOM,
            phase=InteractionPhase.ACTIVE,
            context=RectZoomContext(start=None, current=None, end=None, bounds=None),
        )

        with pytest.raises(RuntimeError, match="boom"):
            presenter.apply_interaction_state_snapshot(snapshot)

    def test_apply_continuum_snapshot_handles_channel(
        self, presenter: SpectrumInteractionCoordinator
    ) -> None:
        """Presenter should handle continuum editing snapshots."""
        emissions: list[InteractionStateSnapshot[ContinuumContext]] = []
        presenter.interaction_snapshot_applied.connect(emissions.append)

        snapshot = InteractionStateSnapshot(
            interaction_id=InteractionId("continuum-add-1"),
            channel=InteractionChannel.CONTINUUM,
            phase=InteractionPhase.IDLE,
            context=ContinuumContext(
                operation_type="add",
                point_index=None,
                start_position=(4200.0, 1.0),
                current_position=(4200.0, 1.0),
                end_position=(4200.0, 1.0),
                validation_result=None,
                cancel_reason=None,
            ),
        )

        presenter.apply_interaction_state_snapshot(snapshot)

        assert presenter._latest_interaction_snapshot == snapshot
        assert emissions == [snapshot]


def test_lupdate_extracts_spectrum_interaction_coordinator_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated SpectrumInteractionCoordinator user-facing sources."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "chappy_ja.ts"
    run_lupdate(
        source_dirs=[
            Path("src/chappy/gui/spectrum/spectrum_interaction_coordinator.py"),
            Path("src/chappy/gui/spectrum/context_menu_controller.py"),
            Path("src/chappy/gui/modes/continuum/context_menu_controller.py"),
            Path("src/chappy/gui/modes/identify/context_menu_controller.py"),
        ],
        ts_output=ts_path,
        extensions="py",
    )

    sources = _read_ts_sources(ts_path)

    assert SPECTRUM_PRESENTER_SOURCES <= sources
    assert all("GUI__" not in source for source in sources)
