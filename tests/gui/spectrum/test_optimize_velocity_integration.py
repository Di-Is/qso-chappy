"""Integration tests for optimize mode velocity plot functionality.

Tests cover:
1. Velocity plot toggle (show/hide)
2. D&D coordinate conversion (velocity -> wavelength)
3. Mask editing restriction when velocity plot is visible
4. Context switching between identify and optimize modes
"""

from __future__ import annotations

import contextlib
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import pytest
from PySide6.QtWidgets import QPushButton

from chappy.application.history import ComponentParameterState
from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.gui.modes.analysis.region_detail import (
    OptimizeVelocityOverlayContext,
    OptimizeVelocityPlotController,
    OptimizeVelocityPlotPorts,
)
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragPayload,
    InteractionChannel,
    InteractionEvent,
    MaskSelectionRequest,
)
from chappy.application.spectrum.range_usecase import RangeNavigationUseCase
from chappy.gui.shell.absorber_model_mutation_controller import (
    AbsorberModelMutationController,
    AbsorberModelMutationPorts,
)
from chappy.gui.spectrum.interaction_controller_factory import SpectrumInteractionControllerFactory
from chappy.gui.spectrum.navigation_controller import SpectrumNavigationControllerFactory
from chappy.gui.spectrum.spectrum_plot import create_default_spectrum_plot_host_factory
from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
from chappy.gui.spectrum.spectrum_view import SpectrumView
from chappy.gui.spectrum.spectrum_view_components import SpectrumViewComponents
from chappy.presentation.velocity import (
    VelocityDisplayScopeKey,
    VelocityDragRequest,
    VelocityOverlayInfo,
    VelocitySliceInfo,
)
from chappy.gui.spectrum.velocity import VelocityGridWidget
from scripts.i18n_lupdate import run_lupdate

from .fixtures.mock_spectrum_view import MockSignal, MockSpectrumDataBridge

if TYPE_CHECKING:
    from chappy.gui.spectrum.interaction.input.ports import VelocityDragSignalPort
    from chappy.gui.spectrum.interaction.channels.ports import InteractionChannelControllerPort
    from pytestqt.qtbot import QtBot


class _History:
    """No-op scientific history owner for velocity drag integration tests."""

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


@pytest.mark.usefixtures("qapp")
class TestVelocityDragCoordinateConversion:
    """Velocity drag behavior should convert velocity coordinates through public intents."""

    def test_convert_zero_velocity_returns_rest_observed(self) -> None:
        """Zero-velocity drag update should move the marker to observed line center."""
        presenter, _, _, plot = _make_drag_presenter(center_z=0.25)

        _start_velocity_drag(presenter, velocity=0.0)
        _update_velocity_drag(presenter, velocity=0.0)

        expected = REST_WAVELENGTH * (1.0 + 0.25)
        assert plot.dragging_positions == [("test_absorber", pytest.approx(expected))]

    def test_convert_positive_velocity_redshifts(self) -> None:
        """Positive velocity drag should place the marker at a longer wavelength."""
        presenter, _, _, plot = _make_drag_presenter(center_z=0.25)
        velocity = 100.0  # 100 km/s receding

        _start_velocity_drag(presenter, velocity=0.0)
        _update_velocity_drag(presenter, velocity=velocity)

        rest_observed = REST_WAVELENGTH * (1.0 + 0.25)
        expected = rest_observed * (velocity / LIGHT_SPEED_KMS + 1.0)
        assert plot.dragging_positions == [("test_absorber", pytest.approx(expected))]
        assert plot.dragging_positions[0][1] > rest_observed

    def test_convert_negative_velocity_blueshifts(self) -> None:
        """Negative velocity drag should place the marker at a shorter wavelength."""
        presenter, _, _, plot = _make_drag_presenter(center_z=0.25)
        velocity = -100.0  # 100 km/s approaching

        _start_velocity_drag(presenter, velocity=0.0)
        _update_velocity_drag(presenter, velocity=velocity)

        rest_observed = REST_WAVELENGTH * (1.0 + 0.25)
        expected = rest_observed * (velocity / LIGHT_SPEED_KMS + 1.0)
        assert plot.dragging_positions == [("test_absorber", pytest.approx(expected))]
        assert plot.dragging_positions[0][1] < rest_observed

    def test_velocity_conversion_symmetry(self) -> None:
        """Symmetric velocity drag updates should produce symmetric wavelength offsets."""
        presenter, _, _, plot = _make_drag_presenter(rest_wavelength=1550.0, center_z=0.1)
        velocity = 150.0

        _start_velocity_drag(presenter, velocity=0.0)
        _update_velocity_drag(presenter, velocity=velocity)
        _update_velocity_drag(presenter, velocity=-velocity)
        _update_velocity_drag(presenter, velocity=0.0)

        result_pos = plot.dragging_positions[0][1]
        result_neg = plot.dragging_positions[1][1]
        result_zero = plot.dragging_positions[2][1]

        delta_pos = result_pos - result_zero
        delta_neg = result_zero - result_neg
        assert delta_pos == pytest.approx(delta_neg)

    def test_marker_update_requires_rest_wavelength(self) -> None:
        """A malformed marker must not reject an otherwise committed drag."""
        presenter, _, absorber, plot = _make_drag_presenter(center_z=0.25)
        plot.plot_widget.absorption_markers["test_absorber"] = {"wavelength": REST_WAVELENGTH}

        _start_velocity_drag(presenter, velocity=0.0)
        _end_velocity_drag(presenter, velocity=100.0)

        assert absorber.parameters["redshift"].value != pytest.approx(0.25)
        assert "redshift" not in plot.plot_widget.absorption_markers["test_absorber"]


class TestVelocityPlotContextSwitching:
    """Tests for velocity plot context switching between identify and optimize modes."""

    @pytest.mark.usefixtures("qtbot")
    def test_velocity_view_set_mode_stores_optimize(self, qtbot: QtBot) -> None:
        """set_mode should store 'optimize' mode value."""
        view = VelocityGridWidget()
        qtbot.addWidget(view)

        view.set_mode("optimize")
        assert view._mode == "optimize"

    @pytest.mark.usefixtures("qtbot")
    def test_velocity_view_set_mode_stores_identify(self, qtbot: QtBot) -> None:
        """set_mode should store 'identify' mode value."""
        view = VelocityGridWidget()
        qtbot.addWidget(view)

        view.set_mode("identify")
        assert view._mode == "identify"

    @pytest.mark.usefixtures("qtbot")
    def test_spectrum_view_set_velocity_plot_active_passes_context(self, qtbot: QtBot) -> None:
        """set_velocity_plot_active should pass context to VelocityGridWidget."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        # Create velocity overlay info
        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    analysis_half_width_kms=150.0,
                )
            ],
        )

        # Activate with optimize context
        view.set_velocity_plot_active(True, overlay_info, context="optimize")

        # Verify mode was set
        assert view.velocity_view is not None
        assert view.velocity_view._mode == "optimize"
        assert view.is_velocity_plot_visible() is True

    @pytest.mark.usefixtures("qtbot")
    def test_spectrum_view_velocity_plot_requires_wavelength_fields_callback(
        self, qtbot: QtBot
    ) -> None:
        """Velocity overlay activation requires an explicit shell field-control port."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    analysis_half_width_kms=150.0,
                )
            ],
        )

        with pytest.raises(RuntimeError, match="wavelength fields enabled callback"):
            view.set_velocity_plot_active(True, overlay_info, context="optimize")

    @pytest.mark.usefixtures("qtbot")
    def test_spectrum_view_deactivate_clears_velocity_state(self, qtbot: QtBot) -> None:
        """Deactivating velocity plot should clear visibility flag."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        # First activate
        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    analysis_half_width_kms=150.0,
                )
            ],
        )
        view.set_velocity_plot_active(True, overlay_info, context="optimize")
        assert view.is_velocity_plot_visible() is True

        # Then deactivate
        view.set_velocity_plot_active(False)
        assert view.is_velocity_plot_visible() is False
        assert view.get_velocity_overlay_info() is None

    @pytest.mark.usefixtures("qtbot")
    def test_spectrum_view_velocity_flux_sync_follows_overlay_lifetime(self, qtbot: QtBot) -> None:
        """The flux-sync connection should exist only while the overlay is shown."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)
        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    analysis_half_width_kms=150.0,
                )
            ],
        )

        view.set_velocity_plot_active(True, overlay_info, context="optimize")
        assert view._velocity_flux_sync_connected is True

        view.set_velocity_plot_active(False)
        assert view._velocity_flux_sync_connected is False
        assert view.velocity_view is not None
        assert view.velocity_view.is_manual_y_range_active() is False

    @pytest.mark.usefixtures("qtbot")
    def test_spectrum_view_deactivate_cancels_active_velocity_drag(self, qtbot: QtBot) -> None:
        """Closing the velocity plot should release active velocity drag state."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    center_z=0.25,
                    analysis_half_width_kms=150.0,
                )
            ],
        )
        view.set_velocity_plot_active(True, overlay_info, context="optimize")
        view.spectrum_input_adapter.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )

        assert view.velocity_view is not None
        view.velocity_view.sig_velocity_drag_requested.emit(
            VelocityDragRequest("abs_001", 0.0, 1215.67, 0.5, 0.25)
        )

        assert view.coordinator._absorber_drag_coordinator.has_active_drag("abs_001")
        assert view.spectrum_input_adapter.dragging_absorber_id() == "abs_001"
        assert (
            view.spectrum_input_adapter.active_interaction_channel()
            is InteractionChannel.ABSORBER_DRAG
        )

        view.set_velocity_plot_active(False, context="optimize")

        assert not view.coordinator._absorber_drag_coordinator.has_active_drag("abs_001")
        assert view.spectrum_input_adapter.dragging_absorber_id() is None
        assert view.spectrum_input_adapter.active_interaction_channel() is None
        assert view.spectrum_input_adapter.begin_mask_selection_interaction(
            MaskSelectionRequest(
                selection_mode="create",
                group_id="group-1",
                mask_id=None,
                initial_range=None,
                existing_mask=None,
            )
        )


class TestSelectionControlsVisibility:
    """Tests for selection controls (checkboxes) visibility based on context."""

    @pytest.mark.usefixtures("qtbot")
    def test_optimize_mode_hides_selection_controls(self, qtbot: QtBot) -> None:
        """In optimize mode, selection checkboxes should be hidden."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    analysis_half_width_kms=150.0,
                )
            ],
        )

        # Activate with optimize context
        view.set_velocity_plot_active(True, overlay_info, context="optimize")

        # Use hidden state because the parent may not be shown in tests.
        button = view.findChild(QPushButton, "velocityPlotCreateButton")
        assert (True if button is None else button.isHidden()) is True

    @pytest.mark.usefixtures("qtbot")
    def test_identify_mode_shows_selection_controls(self, qtbot: QtBot) -> None:
        """In identify mode, selection checkboxes should be visible."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        overlay_info = VelocityOverlayInfo(
            display_range_scope_key=VelocityDisplayScopeKey("identify:test"),
            center_z=0.25,
            rest_wavelength=1215.67,
            analysis_half_widths_kms=(200.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67, label="Lyα", tie_group_key="", line_id="lya"
                )
            ],
        )

        # Activate with identify context (default)
        view.set_velocity_plot_active(True, overlay_info, context="identify")

        # Use hidden state because the parent may not be shown in tests.
        button = view.findChild(QPushButton, "velocityPlotCreateButton")
        assert (True if button is None else button.isHidden()) is False


class TestGetVelocityOverlayInfo:
    """Tests for get_velocity_overlay_info method."""

    @pytest.mark.usefixtures("qtbot")
    def test_returns_none_when_velocity_plot_not_visible(self, qtbot: QtBot) -> None:
        """Should return None when velocity plot is not active."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        result = view.get_velocity_overlay_info()
        assert result is None

    @pytest.mark.usefixtures("qtbot")
    def test_returns_info_when_velocity_plot_visible(self, qtbot: QtBot) -> None:
        """Should return overlay info when velocity plot is active."""
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        view.set_wavelength_fields_enabled_callback(lambda _enabled: None)

        overlay_info = VelocityOverlayInfo(
            center_z=0.25,
            rest_wavelength=1215.67,
            display_range_scope_key=VelocityDisplayScopeKey("optimize:region-1"),
            analysis_half_widths_kms=(150.0,),
            slices=[
                VelocitySliceInfo(
                    rest_wavelength=1215.67,
                    label="Lyα",
                    tie_group_key="",
                    line_id="lya",
                    analysis_half_width_kms=150.0,
                )
            ],
        )

        view.set_velocity_plot_active(True, overlay_info, context="optimize")

        result = view.get_velocity_overlay_info()
        assert result is not None
        assert result.center_z == 0.25
        assert result.rest_wavelength == 1215.67


class TestDragAndDropVelocityConversion:
    """Tests for D&D coordinate conversion in velocity plot mode."""

    def test_drag_start_detects_velocity_mode(self) -> None:
        """A velocity-mode drag should update marker position in wavelength space."""
        presenter, _, _, plot = _make_drag_presenter(center_z=0.25)

        _start_velocity_drag(presenter, velocity=0.0)
        _update_velocity_drag(presenter, velocity=100.0)

        rest_observed = REST_WAVELENGTH * (1.0 + 0.25)
        expected_wavelength = rest_observed * (100.0 / LIGHT_SPEED_KMS + 1.0)
        assert plot.dragging_positions == [("test_absorber", pytest.approx(expected_wavelength))]

    def test_drag_start_stores_wavelength_mode_when_no_velocity(self) -> None:
        """A wavelength-mode drag should keep wavelength coordinates unchanged."""
        presenter, _, _, plot = _make_drag_presenter(velocity_info=None)

        _start_velocity_drag(presenter, velocity=1519.59)
        _update_velocity_drag(presenter, velocity=1521.0)

        assert plot.dragging_positions == [("test_absorber", pytest.approx(1521.0))]

    def test_drag_update_converts_velocity_to_wavelength(self) -> None:
        """Drag update should convert velocity to wavelength in velocity mode."""
        presenter, _, _, plot = _make_drag_presenter(center_z=0.25)

        _start_velocity_drag(presenter, velocity=0.0)
        _update_velocity_drag(presenter, velocity=100.0)

        rest_observed = REST_WAVELENGTH * (1.0 + 0.25)
        expected_wavelength = rest_observed * (100.0 / LIGHT_SPEED_KMS + 1.0)
        assert plot.dragging_positions == [("test_absorber", pytest.approx(expected_wavelength))]

    def test_drag_end_converts_and_calculates_redshift(self) -> None:
        """Drag end should convert velocity and store the new redshift on the absorber."""
        presenter, project, absorber, plot = _make_drag_presenter(center_z=0.25)

        emissions: list[bool] = []
        assert isinstance(presenter.data_bridge, MockSpectrumDataBridge)
        presenter.data_bridge.data_updated.connect(lambda: emissions.append(True))

        _start_velocity_drag(presenter, velocity=0.0)
        _end_velocity_drag(presenter, velocity=100.0)

        rest_observed = REST_WAVELENGTH * (1.0 + 0.25)
        final_wavelength = rest_observed * (100.0 / LIGHT_SPEED_KMS + 1.0)
        expected_redshift = (final_wavelength / REST_WAVELENGTH) - 1.0

        assert absorber.get_parameter_value("redshift") == pytest.approx(expected_redshift)
        assert project.model.model_spectrum is not None
        assert emissions == [True]
        assert plot.finished_absorber_ids == ["test_absorber"]
        assert plot.updated_projects == [project]


# Helper functions

REST_WAVELENGTH = 1215.67
INITIAL_REDSHIFT = 0.25


@dataclass(slots=True)
class _VelocityTestView:
    """Small stateful SpectrumView substitute for velocity drag tests."""

    current_project: SpectroscopyProject
    velocity_info: VelocityOverlayInfo | None
    data_changed: MockSignal = field(default_factory=MockSignal)
    update_plot_count: int = 0

    def get_velocity_overlay_info(self) -> VelocityOverlayInfo | None:
        """Return current velocity overlay information."""
        return self.velocity_info

    def get_velocity_plot_y_range(self) -> tuple[float, float] | None:
        """Return no override flux range."""
        return None

    def update_plot(self) -> None:
        """Record that a plot update was requested."""
        self.update_plot_count += 1


@dataclass(slots=True)
class _RecordingDragPlot:
    """Plot widget fake that stores drag updates as observable state."""

    dragging_positions: list[tuple[str, float]] = field(default_factory=list)
    finished_absorber_ids: list[str] = field(default_factory=list)
    absorption_markers: dict[str, dict[str, float]] = field(default_factory=dict)
    renderer: _RecordingMarkerRenderer = field(default_factory=lambda: _RecordingMarkerRenderer())
    canvas: _RecordingCanvas = field(default_factory=lambda: _RecordingCanvas())

    def update_dragging_absorber_position(self, absorber_id: str, wavelength: float) -> None:
        """Store the latest wavelength for a dragged absorber.

        Args:
            absorber_id: Absorber identifier.
            wavelength: Wavelength coordinate sent to the plot.
        """
        self.dragging_positions.append((absorber_id, wavelength))

    def finish_absorber_drag(self, absorber_id: str) -> None:
        """Store that the drag finished for an absorber.

        Args:
            absorber_id: Absorber identifier.
        """
        self.finished_absorber_ids.append(absorber_id)

    def update_absorption_marker_redshift(self, absorber_id: str, redshift: float) -> None:
        """Update a stored absorption marker redshift."""
        marker_data = self.absorption_markers.get(absorber_id)
        if marker_data is None:
            return
        if "rest_wavelength" not in marker_data:
            msg = f"Absorption marker {absorber_id} is missing required value: rest_wavelength"
            raise RuntimeError(msg)
        marker_data["redshift"] = redshift
        wavelength = marker_data["rest_wavelength"] * (1.0 + redshift)
        if self.renderer.update_vertical_line_position(f"marker_{absorber_id}", wavelength):
            self.canvas.draw_idle()


@dataclass(slots=True)
class _RecordingMarkerRenderer:
    """Renderer fake recording vertical marker updates."""

    marker_updates: list[tuple[str, float]] = field(default_factory=list)

    def update_vertical_line_position(self, marker_name: str, position: float) -> bool:
        """Record a marker position update."""
        self.marker_updates.append((marker_name, position))
        return True


@dataclass(slots=True)
class _RecordingCanvas:
    """Canvas fake recording redraw requests."""

    draw_idle_count: int = 0

    def draw_idle(self) -> None:
        """Record a deferred redraw request."""
        self.draw_idle_count += 1


@dataclass(slots=True)
class _RecordingPlotHost:
    """Plot host fake that exposes a plot widget and records project refreshes."""

    plot_widget: _RecordingDragPlot
    updated_projects: list[SpectroscopyProject] = field(default_factory=list)

    @property
    def dragging_positions(self) -> list[tuple[str, float]]:
        """Return recorded drag positions from the plot widget."""
        return self.plot_widget.dragging_positions

    @property
    def finished_absorber_ids(self) -> list[str]:
        """Return absorber identifiers whose drag was finished."""
        return self.plot_widget.finished_absorber_ids

    def update_from_project(self, project: SpectroscopyProject) -> None:
        """Record the project used to refresh the plot.

        Args:
            project: Project passed by the presenter.
        """
        self.updated_projects.append(project)


class _RangeInput:
    """Small range input fake."""

    def __init__(self) -> None:
        """Initialize the input."""
        self.wavelength_range_changed = MockSignal()


class _Interactor:
    """Small interactor fake."""

    def __init__(self) -> None:
        """Initialize the interactor."""
        self.sig_interaction_snapshot = MockSignal()
        self.sig_cursor_position_changed = MockSignal()
        self.rect_zoom_enabled = False

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Record rectangle zoom mode."""
        self.rect_zoom_enabled = enabled

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return rectangle zoom mode."""
        return self.rect_zoom_enabled

    def set_selected_line_absorbers(self, _absorber_ids: set[str] | None) -> None:
        """Accept selected absorber updates."""


def _make_drag_presenter(
    *,
    rest_wavelength: float = REST_WAVELENGTH,
    center_z: float = INITIAL_REDSHIFT,
    velocity_info: VelocityOverlayInfo | None | bool = True,
) -> tuple[
    SpectrumInteractionCoordinator, SpectroscopyProject, AbsorberComponent, _RecordingPlotHost
]:
    """Create a real presenter wired to real project data and stateful fakes.

    Returns:
        Presenter, project, absorber, and plot host used by drag tests.
    """
    project = SpectroscopyProject(name="Velocity Drag Test")
    wavelength = np.linspace(1450.0, 1580.0, 501)
    flux = np.ones_like(wavelength)
    error = np.full_like(wavelength, 0.05)
    project.model.set_observed_spectrum(Spectrum(wavelength=wavelength, flux=flux, error=error))
    absorber = AbsorberComponent(
        name="Test Absorber",
        wavelength=rest_wavelength,
        column_density=13.5,
        b_parameter=20.0,
        redshift=center_z,
        component_id="test_absorber",
    )
    project.model.add_component(absorber)

    if velocity_info is True:
        overlay_info = VelocityOverlayInfo(
            center_z=center_z, rest_wavelength=rest_wavelength, slices=[]
        )
    elif velocity_info is False:
        overlay_info = None
    else:
        overlay_info = velocity_info

    view = _VelocityTestView(current_project=project, velocity_info=overlay_info)
    data_bridge = MockSpectrumDataBridge(project=project)
    plot = _RecordingPlotHost(plot_widget=_RecordingDragPlot())
    presenter = SpectrumInteractionCoordinator(
        cast(SpectrumView, view),
        SpectrumNavigationControllerFactory(RangeNavigationUseCase()),
        SpectrumInteractionControllerFactory(),
        SpectrumViewComponents(
            data_bridge=cast("SpectrumDataBridge", data_bridge),
            plot_host=cast("SpectrumPlotHost", plot),
            range_input_controls=cast("SpectrumRangeInputControls", _RangeInput()),
            interactor=cast("SpectrumInputFacadePort", _Interactor()),
        ),
    )
    presenter.attach_absorber_model_mutation_owner(
        AbsorberModelMutationController(
            ports=AbsorberModelMutationPorts(
                project_provider=lambda: project,
                line_info_provider=presenter._get_line_info_for_component,
                history_provider=_History,
                plot_widget_provider=lambda: plot.plot_widget,
                plot_refresh_callback=view.update_plot,
                data_updated_callback=presenter.data_bridge.data_updated.emit,
                refresh_optimize_callback=presenter._refresh_optimize_tree_view,
                focus_component_callback=presenter._focus_optimize_component,
                refresh_velocity_overlay_callback=lambda: None,
            )
        )
    )
    return presenter, project, absorber, plot


def _start_velocity_drag(presenter: SpectrumInteractionCoordinator, *, velocity: float) -> None:
    """Start an absorber drag through the public absorber intent dispatcher.

    Args:
        presenter: Presenter under test.
        velocity: Initial drag coordinate. In velocity mode this is km/s.
    """
    from chappy.gui.protocols.intent_types import StartAbsorberDragIntent

    presenter.coordinate_absorber_intent(
        StartAbsorberDragIntent(
            absorber_id="test_absorber",
            initial_wavelength=velocity,
            initial_position=(100.0, 100.0),
        )
    )


def _update_velocity_drag(presenter: SpectrumInteractionCoordinator, *, velocity: float) -> None:
    """Update an absorber drag through the public absorber intent dispatcher.

    Args:
        presenter: Presenter under test.
        velocity: Current drag coordinate. In velocity mode this is km/s.
    """
    from chappy.gui.protocols.intent_types import UpdateAbsorberDragIntent

    presenter.coordinate_absorber_intent(
        UpdateAbsorberDragIntent(absorber_id="test_absorber", current_wavelength=velocity)
    )


def _end_velocity_drag(presenter: SpectrumInteractionCoordinator, *, velocity: float) -> None:
    """End an absorber drag through the public absorber intent dispatcher.

    Args:
        presenter: Presenter under test.
        velocity: Final drag coordinate. In velocity mode this is km/s.
    """
    from chappy.gui.protocols.intent_types import EndAbsorberDragIntent

    presenter.coordinate_absorber_intent(
        EndAbsorberDragIntent(
            absorber_id="test_absorber", final_wavelength=velocity, calculate_redshift=True
        )
    )


def test_lupdate_extracts_optimize_integration_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated OptimizeSpectrumIntegration sources."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "chappy_ja.ts"
    run_lupdate(
        source_dirs=[
            Path("src/chappy/gui/modes/analysis/region_detail/spectrum_integration.py"),
            Path("src/chappy/gui/modes/analysis/region_detail/context_menu_controller.py"),
        ],
        ts_output=ts_path,
        extensions="py",
    )
    root = ET.parse(ts_path).getroot()
    sources = {
        source.text for source in root.findall(".//message/source") if source.text is not None
    }

    assert {
        "Add Component Here",
        "Out of selected line range",
        "Show Velocity Plot (V)",
        "Please select a region",
    } <= sources
    assert all("GUI__" not in source for source in sources)


@dataclass(slots=True)
class _OptimizeVelocityControllerHarness:
    """Container for an optimize velocity controller and captured shell state."""

    controller: OptimizeVelocityPlotController
    shown_contexts: list[OptimizeVelocityOverlayContext]
    checked_states: list[bool]


def _build_optimize_velocity_controller(
    project: SpectroscopyProject,
    region_id: str,
    *,
    mode: EditingMode = EditingMode.ANALYSIS,
    visible: bool = False,
) -> _OptimizeVelocityControllerHarness:
    """Build an optimize velocity controller with typed shell callbacks."""
    shown_contexts: list[OptimizeVelocityOverlayContext] = []
    checked_states: list[bool] = []

    controller = OptimizeVelocityPlotController(
        OptimizeVelocityPlotPorts(
            current_mode_provider=lambda: mode,
            project_provider=lambda: project,
            selected_region_id_provider=lambda: region_id,
            velocity_visible_provider=lambda: visible,
            show_velocity_plot_callback=shown_contexts.append,
            hide_velocity_plot_callback=lambda: None,
            action_checked_callback=checked_states.append,
        )
    )
    return _OptimizeVelocityControllerHarness(
        controller=controller, shown_contexts=shown_contexts, checked_states=checked_states
    )


def _project_with_mgii_region() -> tuple[SpectroscopyProject, str]:
    """Create a project with a two-line Mg II region."""
    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion

    project = SpectroscopyProject()
    region_id = "region_mg2"
    line_2796 = AbsorptionLine(
        line_id="mg2_2796",
        species="Mg II",
        rest_wavelength=2796.35,
        center_z=1.5,
        window_kms=150.0,
        region_id=region_id,
        multiplet_ids=[],
        model_ids=[],
        multiplet_label="",
        transition_name="Mg II 2796.4",
        oscillator_strength=0.1,
        gamma_value=1e8,
    )
    line_2803 = AbsorptionLine(
        line_id="mg2_2803",
        species="Mg II",
        rest_wavelength=2803.53,
        center_z=1.5,
        window_kms=150.0,
        region_id=region_id,
        multiplet_ids=[],
        model_ids=[],
        multiplet_label="",
        transition_name="Mg II 2803.5",
        oscillator_strength=0.1,
        gamma_value=1e8,
    )
    project.absorption_lines[line_2796.line_id] = line_2796
    project.absorption_lines[line_2803.line_id] = line_2803
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=[line_2796.line_id, line_2803.line_id]
    )
    return project, region_id


class TestVelocityOverlayInfoOptimizeRegionId:
    """Tests for optimize velocity overlay context assembly."""

    def test_slices_have_region_id_from_absorption_line(self) -> None:
        """Velocity slice context should carry the absorption line region id."""
        project, region_id = _project_with_mgii_region()
        harness = _build_optimize_velocity_controller(project, region_id)

        overlay_info = harness.controller.build_context()

        assert overlay_info is not None
        assert len(overlay_info.slices) == 2
        assert [slice_info.region_id for slice_info in overlay_info.slices] == [
            region_id,
            region_id,
        ]

    def test_optimize_mode_slices_have_no_primary(self) -> None:
        """Optimize velocity slices are converted to non-primary shared slices.

        Optimize mode has no baseline-line concept, so MainWindow conversion
        marks every shared VelocitySliceInfo as non-primary.
        """
        from chappy.gui.shell.velocity_overlay_adapter import optimize_velocity_overlay_info

        project, region_id = _project_with_mgii_region()
        harness = _build_optimize_velocity_controller(project, region_id)
        context = harness.controller.build_context()

        assert context is not None
        overlay_info = optimize_velocity_overlay_info(context)

        assert overlay_info is not None
        assert len(overlay_info.slices) == 2
        assert [slice_info.is_primary for slice_info in overlay_info.slices] == [False, False]


@dataclass(slots=True)
class _InteractorView:
    """Minimal view dependency for SpectrumInputAdapter velocity tests."""

    wavelength_range: tuple[float, float] = (4000.0, 5000.0)

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the configured wavelength range."""
        return self.wavelength_range


@dataclass(slots=True)
class _RecordingInteractionController:
    """Interaction controller fake that records processed events."""

    events: list[InteractionEvent] = field(default_factory=list)

    def process_event(self, event: InteractionEvent) -> bool:
        """Record an event sent by SpectrumInputAdapter."""
        self.events.append(event)
        return True


class _VelocityDragSignal:
    """Small callback signal used by velocity drag port tests."""

    def __init__(self) -> None:
        """Initialize the signal."""
        self._callbacks: list[Callable[[object], None]] = []

    def connect(self, callback: Callable[[object], None]) -> None:
        """Register a callback."""
        self._callbacks.append(callback)

    def emit(self, payload: object) -> None:
        """Emit the signal to registered callbacks."""
        for callback in list(self._callbacks):
            callback(payload)


class _VelocityView:
    """Minimal velocity drag signal port fake."""

    def __init__(self) -> None:
        """Initialize the fake velocity view."""
        self.sig_velocity_drag_requested = _VelocityDragSignal()
        self.sig_velocity_drag_update = _VelocityDragSignal()
        self.sig_velocity_drag_complete = _VelocityDragSignal()


class TestVelocityPlotDragAndDropIntegration:
    """Integration tests for D&D support in velocity plot.

    TDD Step 6: End-to-end integration tests for velocity D&D bugfix.
    """

    @pytest.mark.usefixtures("qtbot")
    def test_velocity_view_to_interactor_signal_flow(self, qtbot: QtBot) -> None:
        """VelocityGridWidget signal should reach SpectrumInputAdapter handler.

        Tests the full signal path:
        VelocityGridWidget.sig_velocity_drag_requested → SpectrumInputAdapter velocity drag adapter
        """
        from chappy.presentation.interaction.interaction_contracts import InteractionEvent
        from chappy.gui.spectrum.interaction.input.spectrum_input_adapter import (
            SpectrumInputAdapter,
        )

        velocity_view = _VelocityView()

        interactor = SpectrumInputAdapter(view=_InteractorView())
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        recorder = _RecordingInteractionController()
        interactor.set_absorber_drag_state_controller(
            cast("InteractionChannelControllerPort", recorder)
        )

        interactor.connect_velocity_view(cast("VelocityDragSignalPort", velocity_view))
        velocity_view.sig_velocity_drag_requested.emit(
            VelocityDragRequest("abs_001", 100.0, 1215.67, 0.5, 1.5)
        )

        assert len(recorder.events) == 1
        event = recorder.events[0]
        assert isinstance(event, InteractionEvent)
        assert event.payload == AbsorberDragPayload(absorber_id="abs_001")
        expected_wavelength = 1215.67 * (1.0 + 1.5) * (1.0 + 100.0 / LIGHT_SPEED_KMS)
        assert event.position == (pytest.approx(expected_wavelength), 0.5)

    def test_analysis_overview_ignores_velocity_drag_requests(self) -> None:
        """Overview neutral policy must not start Region Detail drag interactions."""
        from chappy.gui.spectrum.interaction.input.spectrum_input_adapter import (
            SpectrumInputAdapter,
        )

        velocity_view = _VelocityView()
        interactor = SpectrumInputAdapter(view=_InteractorView())
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.OVERVIEW).input_capabilities
        )
        recorder = _RecordingInteractionController()
        interactor.set_absorber_drag_state_controller(
            cast("InteractionChannelControllerPort", recorder)
        )
        interactor.connect_velocity_view(cast("VelocityDragSignalPort", velocity_view))

        velocity_view.sig_velocity_drag_requested.emit(
            VelocityDragRequest("abs_001", 100.0, 1215.67, 0.5, 1.5)
        )

        assert recorder.events == []
        assert interactor.dragging_absorber_id() is None
        assert interactor.active_interaction_channel() is None

    def test_velocity_subplot_component_detection_integration(self) -> None:
        """VelocitySubplot should correctly detect components for D&D.

        Tests component detection with tolerance-based matching.
        Note: This test doesn't need qtbot as it only tests pure logic.
        """
        from chappy.presentation.velocity import VelocityComponentInfo

        # Test component detection logic without creating the actual widget
        # Create the data structures and test the detection algorithm
        components = [
            VelocityComponentInfo(
                component_id="comp_1", velocity=-50.0, rest_wavelength=1215.67, label="Component 1"
            ),
            VelocityComponentInfo(
                component_id="comp_2", velocity=0.0, rest_wavelength=1215.67, label="Component 2"
            ),
            VelocityComponentInfo(
                component_id="comp_3", velocity=75.0, rest_wavelength=1215.67, label="Component 3"
            ),
        ]

        # Test the detection algorithm directly (same logic as VelocitySubplot)
        def get_component_at_velocity(
            comps: list[VelocityComponentInfo], velocity: float, tolerance: float = 50.0
        ) -> VelocityComponentInfo | None:
            if not comps:
                return None
            closest = None
            min_distance = float("inf")
            for comp in comps:
                distance = abs(velocity - comp.velocity)
                if distance <= tolerance and distance < min_distance:
                    closest = comp
                    min_distance = distance
            return closest

        # Test detection at various velocities
        # Near comp_1 (-50 km/s)
        result = get_component_at_velocity(components, -45.0, tolerance=50.0)
        assert result is not None
        assert result.component_id == "comp_1"

        # Near comp_2 (0 km/s)
        result = get_component_at_velocity(components, 10.0, tolerance=50.0)
        assert result is not None
        assert result.component_id == "comp_2"

        # Near comp_3 (75 km/s)
        result = get_component_at_velocity(components, 80.0, tolerance=50.0)
        assert result is not None
        assert result.component_id == "comp_3"

        # Far from all components
        result = get_component_at_velocity(components, 200.0, tolerance=50.0)
        assert result is None

    def test_interactor_drag_via_interaction_controller(self) -> None:
        """SpectrumInputAdapter should route velocity drag via the absorber drag controller port.

        Tests velocity to wavelength conversion and proper event routing.
        """
        from chappy.presentation.interaction.interaction_contracts import (
            InteractionChannel,
            InteractionEvent,
            InteractionEventKind,
        )
        from chappy.gui.spectrum.interaction.input.spectrum_input_adapter import (
            SpectrumInputAdapter,
        )

        interactor = SpectrumInputAdapter(view=_InteractorView())
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        recorder = _RecordingInteractionController()
        interactor.set_absorber_drag_state_controller(
            cast("InteractionChannelControllerPort", recorder)
        )

        velocity_view = _VelocityView()
        interactor.connect_velocity_view(cast("VelocityDragSignalPort", velocity_view))

        velocity_view.sig_velocity_drag_requested.emit(
            VelocityDragRequest(
                "test_absorber",
                100.0,  # 100 km/s
                1215.67,  # Lyman-alpha
                0.5,
                1.72,
            )
        )

        assert len(recorder.events) == 1
        event = recorder.events[0]
        assert isinstance(event, InteractionEvent)
        assert event.channel is InteractionChannel.ABSORBER_DRAG
        assert event.kind is InteractionEventKind.ABSORBER_DRAG_BEGIN
        assert event.payload == AbsorberDragPayload(absorber_id="test_absorber")

        # Verify velocity to wavelength conversion in position
        # λ_obs = λ_rest × (1 + z_center) × (1 + v/c)
        expected_wavelength = 1215.67 * (1.0 + 1.72) * (1.0 + 100.0 / LIGHT_SPEED_KMS)
        assert event.position is not None
        assert abs(event.position[0] - expected_wavelength) < 1e-6
        assert abs(event.position[1] - 0.5) < 1e-6  # flux

        # Verify drag state was set
        assert interactor.dragging_absorber_id() == "test_absorber"
