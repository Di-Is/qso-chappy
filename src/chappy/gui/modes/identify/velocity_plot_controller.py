"""Identify-mode velocity plot workflow controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from chappy.core.editing_mode import EditingMode

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from chappy.presentation.identify import (
        IdentifyVelocityPlotContext,
        IdentifyVelocitySelectionPort,
    )


@runtime_checkable
class IdentifyVelocityRangePort(Protocol):
    """Spectrum range query required by identify velocity plotting."""

    def is_velocity_plot_visible(self) -> bool:
        """Return whether the velocity plot is visible."""
        ...


class IdentifyVelocityWorkflowPort(Protocol):
    """Identify workflow operations required by velocity plot routing."""

    def request_velocity_plot(
        self, observed_wavelength: float
    ) -> IdentifyVelocityPlotContext | None:
        """Build velocity plot context for the observed wavelength."""
        ...

    def handle_velocity_plot_closed(self) -> None:
        """Notify the workflow that the velocity plot was closed."""
        ...

    def report_invalid_wavelength(self) -> None:
        """Report that a valid wavelength position must be specified."""
        ...

    def confirm_velocity_plot_selection(
        self, *, center_z: float | None, slices: Sequence[IdentifyVelocitySelectionPort]
    ) -> None:
        """Create temporary lines from selected velocity slices."""
        ...


class VelocitySelectionOverlayPort(Protocol):
    """Overlay metadata required to confirm velocity plot selections."""

    center_z: float | None


@dataclass(frozen=True, slots=True)
class IdentifyVelocityPlotPorts:
    """Shell callbacks required by the identify velocity plot controller."""

    current_mode_provider: Callable[[], EditingMode | None]
    range_provider: Callable[[], IdentifyVelocityRangePort | None]
    workflow_provider: Callable[[], IdentifyVelocityWorkflowPort]
    show_velocity_plot_callback: Callable[[IdentifyVelocityPlotContext], None]
    hide_velocity_plot_callback: Callable[[], None]
    wavelength_fields_enabled_callback: Callable[[bool], None]


class IdentifyVelocityPlotController:
    """Coordinate identify velocity plot show, hide, refresh, and confirm workflows."""

    def __init__(self, ports: IdentifyVelocityPlotPorts) -> None:
        """Initialize the controller.

        Args:
            ports: Shell callbacks for spectrum, workflow, and UI state.
        """
        self._ports = ports
        self._last_request_wavelength: float | None = None

    def toggle(self, wavelength: float | None) -> None:
        """Toggle the identify-mode velocity plot."""
        if self._ports.current_mode_provider() is not EditingMode.IDENTIFY:
            return

        spectrum_view = self._ports.range_provider()
        if spectrum_view is None:
            return
        workflow = self._workflow()

        if spectrum_view.is_velocity_plot_visible():
            self.hide()
            return

        target_wavelength = wavelength
        if target_wavelength is None:
            workflow.report_invalid_wavelength()
            return

        context = workflow.request_velocity_plot(target_wavelength)
        if context is None:
            return

        self._ports.show_velocity_plot_callback(context)
        self._last_request_wavelength = target_wavelength
        self._ports.wavelength_fields_enabled_callback(False)

    def hide(self) -> None:
        """Hide the identify velocity plot and notify the workflow."""
        spectrum_view = self._ports.range_provider()
        if spectrum_view is None or not spectrum_view.is_velocity_plot_visible():
            self._ports.wavelength_fields_enabled_callback(True)
            self._last_request_wavelength = None
            return

        workflow = self._workflow()
        self._ports.hide_velocity_plot_callback()
        self._ports.wavelength_fields_enabled_callback(True)
        workflow.handle_velocity_plot_closed()
        self._last_request_wavelength = None

    def refresh(self) -> None:
        """Rebuild the identify velocity plot from the last requested wavelength."""
        spectrum_view = self._ports.range_provider()
        if spectrum_view is None or not spectrum_view.is_velocity_plot_visible():
            return

        if self._last_request_wavelength is None:
            return
        workflow = self._workflow()

        context = workflow.request_velocity_plot(self._last_request_wavelength)
        if context is None:
            self.hide()
            return

        self._ports.show_velocity_plot_callback(context)

    def confirm_selection(
        self,
        overlay_info: VelocitySelectionOverlayPort | None,
        selections: Sequence[IdentifyVelocitySelectionPort],
    ) -> None:
        """Create temporary lines from selected velocity slices."""
        workflow = self._workflow()

        center_z = overlay_info.center_z if overlay_info is not None else None
        workflow.confirm_velocity_plot_selection(center_z=center_z, slices=selections)

    def _workflow(self) -> IdentifyVelocityWorkflowPort:
        """Return the required velocity workflow."""
        workflow = self._ports.workflow_provider()
        if workflow is None:
            msg = "Identify velocity workflow is not configured."
            raise RuntimeError(msg)
        return workflow
