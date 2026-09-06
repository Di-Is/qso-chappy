"""Tests for identify velocity plot workflow controller."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.identify.velocity_plot_controller import (
    IdentifyVelocityPlotController,
    IdentifyVelocityPlotPorts,
)
from chappy.presentation.identify import (
    IdentifyVelocityPlotContext,
    IdentifyVelocitySelectionPort,
    IdentifyVelocitySliceDescriptor,
)
from chappy.presentation.velocity import VelocityOverlayInfo


@dataclass
class _SpectrumPort:
    """Record spectrum velocity plot calls."""

    visible: bool = False
    wavelength_range: tuple[float, float] = (1000.0, 1200.0)
    show_calls: list[IdentifyVelocityPlotContext] = field(default_factory=list)
    hide_count: int = 0

    def is_velocity_plot_visible(self) -> bool:
        """Return whether the plot is visible."""
        return self.visible

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the configured wavelength range."""
        return self.wavelength_range


@dataclass
class _WorkflowPort:
    """Record identify velocity workflow calls."""

    requested_wavelengths: list[float] = field(default_factory=list)
    closed_count: int = 0
    invalid_wavelength_reports: int = 0
    confirmed: list[tuple[float | None, tuple[IdentifyVelocitySelectionPort, ...]]] = field(
        default_factory=list
    )

    def request_velocity_plot(self, observed_wavelength: float) -> IdentifyVelocityPlotContext:
        """Return a minimal velocity plot context."""
        self.requested_wavelengths.append(observed_wavelength)
        return IdentifyVelocityPlotContext(
            center_z=1.0,
            rest_wavelength=500.0,
            observed_wavelength=observed_wavelength,
            species_label="C IV",
            new_candidate_analysis_half_width_kms=120.0,
            slices=(
                IdentifyVelocitySliceDescriptor(
                    rest_wavelength=500.0,
                    label="C IV 500",
                    line_id="line-1",
                    is_primary=True,
                    default_selected=True,
                    tie_group_key="",
                ),
            ),
        )

    def handle_velocity_plot_closed(self) -> None:
        """Record close notifications."""
        self.closed_count += 1

    def report_invalid_wavelength(self) -> None:
        """Record invalid wavelength reports."""
        self.invalid_wavelength_reports += 1

    def confirm_velocity_plot_selection(
        self, *, center_z: float | None, slices: list[IdentifyVelocitySelectionPort]
    ) -> None:
        """Record confirmed selections."""
        self.confirmed.append((center_z, tuple(slices)))


@dataclass(frozen=True, slots=True)
class _SelectedVelocitySlice:
    """Selected velocity slice used by controller tests."""

    rest_wavelength: float
    label: str
    center_z: float | None
    line_id: str | None
    is_primary: bool
    tie_group_key: str


@dataclass
class _Harness:
    """Objects used by controller tests."""

    controller: IdentifyVelocityPlotController
    spectrum: _SpectrumPort
    workflow: _WorkflowPort
    wavelength_enabled: list[bool]


def _harness(mode: EditingMode | None = EditingMode.IDENTIFY) -> _Harness:
    """Create a controller with recording ports."""
    spectrum = _SpectrumPort()
    workflow = _WorkflowPort()
    wavelength_enabled: list[bool] = []

    def show_velocity_plot(context: IdentifyVelocityPlotContext) -> None:
        spectrum.visible = True
        spectrum.show_calls.append(context)

    def hide_velocity_plot() -> None:
        spectrum.visible = False
        spectrum.hide_count += 1

    controller = IdentifyVelocityPlotController(
        IdentifyVelocityPlotPorts(
            current_mode_provider=lambda: mode,
            range_provider=lambda: spectrum,
            workflow_provider=lambda: workflow,
            show_velocity_plot_callback=show_velocity_plot,
            hide_velocity_plot_callback=hide_velocity_plot,
            wavelength_fields_enabled_callback=wavelength_enabled.append,
        )
    )
    return _Harness(controller, spectrum, workflow, wavelength_enabled)


def test_toggle_without_wavelength_does_not_guess_view_center() -> None:
    """A missing cursor wavelength never opens at an inferred center."""
    harness = _harness()

    harness.controller.toggle(None)

    assert harness.workflow.requested_wavelengths == []
    assert harness.spectrum.visible is False
    assert harness.wavelength_enabled == []


def test_toggle_without_wavelength_reports_invalid_wavelength() -> None:
    """A cursor outside the wavelength axis asks the user for a valid position."""
    harness = _harness()

    harness.controller.toggle(None)

    assert harness.workflow.invalid_wavelength_reports == 1


def test_toggle_without_wavelength_closes_visible_plot_silently() -> None:
    """Closing the visible plot never asks for a wavelength position."""
    harness = _harness()
    harness.spectrum.visible = True

    harness.controller.toggle(None)

    assert harness.spectrum.visible is False
    assert harness.spectrum.hide_count == 1
    assert harness.workflow.invalid_wavelength_reports == 0


def test_toggle_outside_identify_mode_reports_nothing() -> None:
    """Other modes own their own velocity shortcuts and stay silent."""
    harness = _harness(EditingMode.ANALYSIS)

    harness.controller.toggle(None)

    assert harness.workflow.invalid_wavelength_reports == 0


def test_toggle_hides_an_existing_velocity_plot() -> None:
    """The shared toggle contract closes an already-visible plot."""
    harness = _harness()
    harness.spectrum.visible = True

    harness.controller.toggle(1111.0)

    assert harness.spectrum.visible is False
    assert harness.spectrum.hide_count == 1
    assert harness.workflow.requested_wavelengths == []


def test_toggle_ignores_non_identify_mode() -> None:
    """Toggle does nothing outside identify mode."""
    harness = _harness(EditingMode.ANALYSIS)

    harness.controller.toggle(1100.0)

    assert harness.workflow.requested_wavelengths == []
    assert harness.spectrum.show_calls == []


def test_toggle_missing_workflow_fails_fast() -> None:
    """Missing velocity workflow is a composition error."""
    spectrum = _SpectrumPort()
    controller = IdentifyVelocityPlotController(
        IdentifyVelocityPlotPorts(
            current_mode_provider=lambda: EditingMode.IDENTIFY,
            range_provider=lambda: spectrum,
            workflow_provider=lambda: None,
            show_velocity_plot_callback=lambda _context: None,
            hide_velocity_plot_callback=lambda: None,
            wavelength_fields_enabled_callback=lambda _enabled: None,
        )
    )

    with pytest.raises(RuntimeError, match="velocity workflow"):
        controller.toggle(1100.0)


def test_refresh_reuses_last_request_wavelength() -> None:
    """Refresh rebuilds the visible plot from the last requested wavelength."""
    harness = _harness()
    harness.controller.toggle(1111.0)

    harness.controller.refresh()

    assert harness.workflow.requested_wavelengths == [1111.0, 1111.0]
    assert len(harness.spectrum.show_calls) == 2


def test_refresh_without_last_request_is_user_state_noop() -> None:
    """Refreshing a visible plot without a previous request remains a no-op."""
    harness = _harness()
    harness.spectrum.visible = True

    harness.controller.refresh()

    assert harness.workflow.requested_wavelengths == []
    assert harness.spectrum.show_calls == []


def test_hide_closes_plot_and_reenables_wavelength_fields() -> None:
    """Hide closes the spectrum plot and notifies identify workflow."""
    harness = _harness()
    harness.controller.toggle(1111.0)

    harness.controller.hide()

    assert harness.spectrum.visible is False
    assert harness.spectrum.hide_count == 1
    assert harness.workflow.closed_count == 1
    assert harness.wavelength_enabled == [False, True]


def test_hide_missing_workflow_fails_fast() -> None:
    """Hiding without the required workflow is a composition error."""
    spectrum = _SpectrumPort(visible=True)
    controller = IdentifyVelocityPlotController(
        IdentifyVelocityPlotPorts(
            current_mode_provider=lambda: EditingMode.IDENTIFY,
            range_provider=lambda: spectrum,
            workflow_provider=lambda: None,
            show_velocity_plot_callback=lambda _context: None,
            hide_velocity_plot_callback=lambda: None,
            wavelength_fields_enabled_callback=lambda _enabled: None,
        )
    )

    with pytest.raises(RuntimeError, match="velocity workflow"):
        controller.hide()


def test_confirm_selection_forwards_overlay_center_only() -> None:
    """Confirm forwards the center while candidate width remains workflow-owned."""
    harness = _harness()
    slice_info = _SelectedVelocitySlice(
        rest_wavelength=500.0,
        label="C IV 500",
        center_z=1.0,
        line_id="line-1",
        is_primary=True,
        tie_group_key="",
    )
    overlay = VelocityOverlayInfo(center_z=1.0)

    harness.controller.confirm_selection(overlay, [slice_info])

    assert harness.workflow.confirmed == [(1.0, (slice_info,))]


def test_confirm_selection_missing_workflow_fails_fast() -> None:
    """Confirming selected velocity slices requires the workflow."""
    controller = IdentifyVelocityPlotController(
        IdentifyVelocityPlotPorts(
            current_mode_provider=lambda: EditingMode.IDENTIFY,
            range_provider=lambda: _SpectrumPort(),
            workflow_provider=lambda: None,
            show_velocity_plot_callback=lambda _context: None,
            hide_velocity_plot_callback=lambda: None,
            wavelength_fields_enabled_callback=lambda _enabled: None,
        )
    )

    with pytest.raises(RuntimeError, match="velocity workflow"):
        controller.confirm_selection(None, [])
