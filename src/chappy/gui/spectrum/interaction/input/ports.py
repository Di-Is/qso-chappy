"""Typed ports required by spectrum interaction adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint, QPointF, Qt, SignalInstance
    from PySide6.QtGui import QMouseEvent, QWheelEvent

    from chappy.presentation.interaction.interaction_contracts import (
        InteractionEvent,
        MaskSelectionRequest,
    )

from chappy.gui.protocols.velocity_mode import VelocityInteractionProvider
from chappy.gui.utils.plot_coordinate_transform import CoordinateTransformPlotWidget


class SpectrumInputAdapterViewPort(Protocol):
    """View surface required by `SpectrumInputAdapter`."""

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the currently visible wavelength range."""
        ...


class SpectrumInputAdapterEventSink(Protocol):
    """Interactor event sink installed on the plot widget."""

    def process_mouse_event(self, event: QMouseEvent | QWheelEvent) -> None:
        """Process mouse or wheel events forwarded from the plot."""
        ...

    def handle_mouse_leave(self) -> None:
        """Handle cursor leave events."""
        ...

    def handle_double_click_center(self, wavelength: float) -> None:
        """Center the viewport on a wavelength."""
        ...

    def handle_mouse_press_event(self, event: QMouseEvent) -> bool:
        """Handle a Qt mouse press event."""
        ...

    def handle_mouse_release_event(self, event: QMouseEvent) -> bool:
        """Handle a Qt mouse release event."""
        ...

    def handle_mouse_move_event(self, event: QMouseEvent) -> bool:
        """Handle a Qt mouse move event."""
        ...


class ContinuumInteractionEventSink(Protocol):
    """Continuum interaction sink installed on the plot widget."""

    def can_process_continuum_event(self) -> bool:
        """Return whether a continuum event may be processed."""
        ...

    def process_continuum_interaction_event(self, event: InteractionEvent) -> bool:
        """Process a continuum interaction event."""
        ...


class SpectrumInputPorts(SpectrumInputAdapterEventSink, ContinuumInteractionEventSink, Protocol):
    """Complete input surface supplied by the spectrum input adapter."""


@runtime_checkable
class SpectrumPlotWidgetPort(CoordinateTransformPlotWidget, Protocol):
    """Plot widget surface required by `SpectrumInputAdapter`."""

    def set_input_ports(
        self,
        *,
        mouse: SpectrumInputAdapterEventSink | None,
        continuum: ContinuumInteractionEventSink | None,
    ) -> None:
        """Atomically attach or detach the plot input ports."""
        ...

    def continuum_points(self) -> list[tuple[float, float]]:
        """Return current continuum points."""
        ...

    def get_absorber_at_position(self, wavelength: float) -> str | None:
        """Return the absorber at a wavelength, if any."""
        ...

    def setCursor(self, cursor: Qt.CursorShape) -> None:  # noqa: N802 - Qt API
        """Set the widget cursor shape."""
        ...

    def mapFromGlobal(self, position: QPoint) -> QPoint | QPointF:  # noqa: N802 - Qt API
        """Map a global cursor position to widget-local coordinates."""
        ...


class VelocityDragSignalPort(Protocol):
    """Velocity view signal surface required by `SpectrumInputAdapter`."""

    sig_velocity_drag_requested: SignalInstance
    sig_velocity_drag_update: SignalInstance
    sig_velocity_drag_complete: SignalInstance


class SpectrumInputFacadePort(VelocityInteractionProvider, Protocol):
    """Spectrum input surface required by the shared spectrum facade."""

    sig_interaction_snapshot: SignalInstance
    sig_cursor_position_changed: SignalInstance

    def begin_mask_selection_interaction(self, request: MaskSelectionRequest) -> bool:
        """Prime mask selection using a typed request."""
        ...

    def cancel_mask_selection_interaction(self, *, reason: str | None = None) -> bool:
        """Cancel an active mask selection interaction."""
        ...

    def set_selected_line_absorbers(self, absorber_ids: set[str] | None) -> None:
        """Set absorbers that can be dragged in optimize mode."""
        ...

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Enable or disable rectangle zoom interaction mode."""
        ...

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return whether rectangle zoom mode is active."""
        ...
