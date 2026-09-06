"""Public workflow ports exposed by identify mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from PySide6.QtCore import SignalInstance

    from chappy.core.editing_mode import EditingMode
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
    from chappy.gui.utils.absorption_overlays import RegionPayload
    from chappy.presentation.identify import (
        IdentifyVelocityPlotContext,
        IdentifyVelocitySelectionPort,
    )


class IdentifyModeCoordinatorPort(Protocol):
    """Shell-facing identify mode operations."""

    def connect_status_message(self, callback: Callable[[str], None]) -> None:
        """Connect a status message callback."""
        ...

    def set_panel(self, panel: IdentifySidePanel | None) -> None:
        """Attach or detach the identify side panel."""
        ...

    def refresh(self) -> None:
        """Refresh identify UI state."""
        ...

    def set_tutorial_sigma_threshold(self, value: float | None) -> None:
        """Apply or clear a non-persistent tutorial detection threshold."""
        ...

    def set_preview_always_on(self, enabled: bool) -> None:
        """Enable or disable identify preview lock."""
        ...

    def preview_always_on(self) -> bool:
        """Return whether identify preview lock is active."""
        ...

    def notify_resolution_changed(self) -> None:
        """React to instrumental resolution changes."""
        ...

    def build_line_overlay_payload(self, *, include_temporary: bool) -> list[RegionPayload]:
        """Build line overlay payloads."""
        ...

    def handle_cursor_position(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Handle cursor movement over the spectrum surface."""
        ...

    def handle_cursor_left(self) -> None:
        """Handle cursor leave events from the spectrum surface."""
        ...

    def handle_preview_shift_released(self) -> None:
        """Handle release of the transient Identify Shift preview input."""
        ...

    def handle_manual_temporary_line(
        self, *, observed_wavelength: float, modifiers: int = 0, source: str = "click"
    ) -> None:
        """Create manual temporary lines."""
        ...

    def on_mode_changed(self, mode: EditingMode) -> None:
        """React to shell mode changes."""
        ...

    def set_identify_active(self, active: bool) -> None:
        """Activate or deactivate the Identify workflow semantically."""
        ...

    def handle_project_changed(self, project: SpectroscopyProject | None) -> None:
        """React to shell project changes."""
        ...

    def request_velocity_plot(
        self, observed_wavelength: float
    ) -> IdentifyVelocityPlotContext | None:
        """Build velocity plot context."""
        ...

    def handle_velocity_plot_closed(self) -> None:
        """Handle velocity plot close events."""
        ...

    def report_invalid_wavelength(self) -> None:
        """Report that a valid wavelength position must be specified."""
        ...

    def confirm_velocity_plot_selection(
        self, *, center_z: float | None, slices: Sequence[IdentifyVelocitySelectionPort]
    ) -> None:
        """Create temporary lines from velocity plot selections."""
        ...

    open_analysis_region_requested: SignalInstance
