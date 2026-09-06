"""Typed contracts between optimize mode and shared spectrum surfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, TypedDict

if TYPE_CHECKING:
    from chappy.core.components.absorber import AbsorberComponent
    from chappy.gui.protocols.context_menu import (
        ContextMenuActionDescriptor,
        ContextMenuActionIntent,
    )
    from chappy.presentation.interaction.interaction_contracts import (
        InteractionStateSnapshot,
        MaskSelectionContext,
    )


class OptimizeLineInfo(TypedDict, total=False):
    """Supplementary information describing an optimize absorber component."""

    rest_wavelength: float
    lambda_range: tuple[float, float] | None


type OptimizeCursorMode = Literal["crosshair", "not-allowed", "default"]


class SpectrumModeIntegrationPort(Protocol):
    """Optimize integration operations used by the shared spectrum presenter."""

    def handle_mask_selection_snapshot(
        self, snapshot: InteractionStateSnapshot[MaskSelectionContext]
    ) -> None:
        """Handle mask selection state from the shared interaction controller."""
        ...

    def get_line_info_for_component(
        self, component: AbsorberComponent | None
    ) -> OptimizeLineInfo | None:
        """Return line information for an optimize component."""
        ...

    def focus_component(self, component_id: str) -> None:
        """Focus a component in optimize UI."""
        ...

    def update_tree_view(self) -> None:
        """Refresh optimize tree view from model state."""
        ...

    def handle_shift_click(self, wavelength: float, flux: float) -> bool:
        """Handle optimize-mode shift click in the shared spectrum."""
        ...

    def update_cursor_for_shift(
        self, wavelength: float, shift_pressed: bool
    ) -> OptimizeCursorMode:
        """Return cursor mode for optimize shift-click feedback."""
        ...

    def handle_cursor_position(self, wavelength: float, shift_pressed: bool) -> None:
        """Handle optimize cursor feedback for a raw cursor position."""
        ...

    def handle_velocity_shortcut(self) -> None:
        """Handle the optimize velocity shortcut."""
        ...

    def handle_context_menu_intent(self, intent: ContextMenuActionIntent) -> None:
        """Handle an optimize context-menu intent."""
        ...

    def context_menu_actions(self, wavelength: float) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return optimize context-menu actions for a wavelength."""
        ...
