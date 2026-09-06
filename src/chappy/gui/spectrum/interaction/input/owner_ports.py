"""Owner ports required by spectrum input controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from chappy.gui.spectrum.interaction.channels.ports import InteractionChannelControllerPort
    from chappy.gui.utils.plot_coordinate_transform import PlotCoordinateTransform
    from chappy.presentation.interaction.interaction_contracts import InteractionChannel

type WheelDelta = float | tuple[int | float, int | float]


class AbsorberDragInputOwnerPort(Protocol):
    """Owner operations required by absorber drag input."""

    def require_absorber_drag_controller(self) -> InteractionChannelControllerPort:
        """Return the absorber drag state controller."""
        ...

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the currently active input channel."""
        ...

    def can_start_absorber_drag(self) -> bool:
        """Return whether an absorber drag interaction can start."""
        ...

    def absorber_drag_enabled(self) -> bool:
        """Return whether absorber drag is enabled for current input state."""
        ...

    def active_absorber_drag_id(self) -> str | None:
        """Return the active absorber drag id, if any."""
        ...

    def acquire_absorber_drag(self, absorber_id: str) -> None:
        """Mark the absorber drag channel as active for the absorber."""
        ...

    def clear_absorber_drag(self) -> None:
        """Clear absorber drag channel ownership."""
        ...

    def absorber_at_wavelength(self, wavelength: float) -> str | None:
        """Return the absorber at a wavelength, if any."""
        ...


class MaskSelectionInputOwnerPort(Protocol):
    """Owner operations required by mask selection input."""

    def require_mask_selection_controller(self) -> InteractionChannelControllerPort:
        """Return the mask selection state controller."""
        ...

    def can_start_mask_selection(self) -> bool:
        """Return whether mask selection can start."""
        ...

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the currently active input channel."""
        ...

    def acquire_mask_selection(self) -> None:
        """Acquire mask selection channel ownership."""
        ...

    def clear_mask_selection(self) -> None:
        """Clear mask selection channel ownership."""
        ...

    def set_mask_selection_cursor(self, active: bool) -> None:
        """Apply mask selection cursor feedback."""
        ...


class RectZoomInputOwnerPort(Protocol):
    """Owner operations required by rectangle zoom input."""

    def require_rect_zoom_controller(self) -> InteractionChannelControllerPort:
        """Return the rectangle zoom state controller."""
        ...

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the currently active input channel."""
        ...

    def acquire_rect_zoom(self) -> None:
        """Acquire rectangle zoom channel ownership."""
        ...

    def clear_rect_zoom(self) -> None:
        """Clear rectangle zoom channel ownership."""
        ...

    def set_rect_zoom_cursor(self, active: bool) -> None:
        """Apply rectangle zoom cursor feedback."""
        ...


class SpectrumPointerInputOwnerPort(Protocol):
    """Owner operations required by plot pointer input."""

    @property
    def coord_transform(self) -> PlotCoordinateTransform | None:
        """Return the current plot coordinate transform."""
        ...

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the current active input channel."""
        ...

    def dragging_absorber_id(self) -> str | None:
        """Return the active absorber drag id, if any."""
        ...

    def cancel_mask_selection_interaction(self, *, reason: str | None = None) -> bool:
        """Cancel the active mask selection interaction if present."""
        ...

    def handle_mouse_click(
        self, position: tuple[float, float], button: str, modifiers: int = 0
    ) -> bool:
        """Route a click at a data-space position."""
        ...

    def handle_wheel(self, pos: tuple[float, float], delta: WheelDelta) -> bool:
        """Route a wheel event at a data-space position."""
        ...


class VelocityShortcutModeCapabilities(Protocol):
    """Mode-derived capabilities required for velocity shortcut routing."""

    def identify_velocity_shortcut_enabled(self) -> bool:
        """Return whether the Identify velocity shortcut is enabled."""
        ...

    def detail_velocity_shortcut_enabled(self) -> bool:
        """Return whether velocity shortcut should be routed to Region Detail."""
        ...


class VelocityShortcutOwnerPort(Protocol):
    """Owner operations required by velocity shortcut input."""

    def active_input_channel(self) -> InteractionChannel | None:
        """Return the current active input channel."""
        ...

    def cancel_rect_zoom_interaction(self, *, reason: str) -> bool:
        """Cancel rectangle zoom interaction."""
        ...

    def emit_mode_velocity_shortcut(self) -> None:
        """Route a velocity shortcut to the active mode owner."""
        ...


class SpectrumInputCompositionOwnerPort(
    AbsorberDragInputOwnerPort,
    MaskSelectionInputOwnerPort,
    RectZoomInputOwnerPort,
    SpectrumPointerInputOwnerPort,
    VelocityShortcutOwnerPort,
    Protocol,
):
    """Owner surface required to compose spectrum input controllers."""
