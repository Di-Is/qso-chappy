"""Runtime command port for spectrum interaction input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QCursor

from chappy.gui.protocols.intent_types import ShowContextMenuIntent

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.protocols.intent_types import SpectrumInteractionIntent
    from chappy.gui.spectrum.interaction.input.controllers.mask_selection_input_controller import (
        MaskSelectionInputController,
    )
    from chappy.gui.spectrum.interaction.input.controllers.rect_zoom_input_controller import (
        RectZoomInputController,
    )


class SpectrumInteractionRuntime:
    """Execute routed spectrum interaction commands against input controllers."""

    def __init__(
        self,
        *,
        intent_emitter: Callable[[SpectrumInteractionIntent], None],
        mode_velocity_shortcut_emitter: Callable[[], None],
        mode_click_emitter: Callable[[tuple[float, float], int], None],
        rect_zoom_input_controller: RectZoomInputController,
        mask_selection_input_controller: MaskSelectionInputController,
    ) -> None:
        """Initialize the runtime."""
        self._intent_emitter = intent_emitter
        self._mode_velocity_shortcut_emitter = mode_velocity_shortcut_emitter
        self._mode_click_emitter = mode_click_emitter
        self._rect_zoom_input_controller = rect_zoom_input_controller
        self._mask_selection_input_controller = mask_selection_input_controller

    def emit_interaction_intent(self, intent: SpectrumInteractionIntent) -> None:
        """Emit a typed spectrum interaction intent."""
        self._intent_emitter(intent)

    def cancel_rect_zoom_interaction(self, *, reason: str) -> bool:
        """Cancel the rectangle zoom interaction."""
        return self._rect_zoom_input_controller.cancel_interaction(reason=reason)

    def emit_mode_velocity_shortcut(self) -> None:
        """Route a velocity shortcut to the active mode owner."""
        self._mode_velocity_shortcut_emitter()

    def emit_mode_click(self, position: tuple[float, float], modifiers: int) -> None:
        """Route a raw mode click to the active mode owner."""
        self._mode_click_emitter(position, modifiers)

    def cancel_mask_selection(self, *, reason: str) -> bool:
        """Cancel mask selection."""
        return self._mask_selection_input_controller.cancel_interaction(reason=reason)

    def begin_rect_zoom_interaction(self, position: tuple[float, float], modifiers: int) -> None:
        """Begin rectangle zoom interaction."""
        self._rect_zoom_input_controller.begin_interaction(position, modifiers)

    def show_context_menu(self, position: tuple[float, float]) -> bool:
        """Show the spectrum context menu."""
        global_pos = QCursor.pos()
        self._intent_emitter(
            ShowContextMenuIntent(
                wavelength=position[0],
                flux=position[1],
                global_x=global_pos.x(),
                global_y=global_pos.y(),
            )
        )
        return True
