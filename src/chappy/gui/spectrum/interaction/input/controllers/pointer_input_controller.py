"""Pointer input orchestration for spectrum plot events."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QWheelEvent

from chappy.gui.protocols.intent_types import CenterOnWavelengthIntent
from chappy.gui.spectrum.interaction.input.mapping.qt_input_mapper import KeyMouseIntentMapper
from chappy.presentation.interaction.interaction_contracts import InteractionChannel

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QMouseEvent

    from chappy.gui.spectrum.interaction.input.controllers.absorber_drag_input_controller import (
        AbsorberDragInputController,
    )
    from chappy.gui.spectrum.interaction.input.controllers.mask_selection_input_controller import (
        MaskSelectionInputController,
    )
    from chappy.gui.spectrum.interaction.input.controllers.rect_zoom_input_controller import (
        RectZoomInputController,
    )
    from chappy.gui.spectrum.interaction.input.mapping.pointer_coordinate_mapper import (
        SpectrumPointerCoordinateMapper,
    )
    from chappy.gui.spectrum.interaction.input.owner_ports import SpectrumPointerInputOwnerPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PointerInputEmitters:
    """Callbacks used by pointer input orchestration."""

    cursor_position: Callable[[float, float, int], None]
    cursor_left: Callable[[], None]
    center_requested: Callable[[CenterOnWavelengthIntent], None]


class SpectrumPointerInputController:
    """Coordinate pointer events from the plot event sink."""

    def __init__(
        self,
        *,
        owner: SpectrumPointerInputOwnerPort,
        coordinate_mapper: SpectrumPointerCoordinateMapper,
        rect_zoom_input_controller: RectZoomInputController,
        absorber_drag_input_controller: AbsorberDragInputController,
        mask_selection_input_controller: MaskSelectionInputController,
        emitters: PointerInputEmitters,
    ) -> None:
        """Initialize the controller."""
        self._owner = owner
        self._coordinate_mapper = coordinate_mapper
        self._rect_zoom_input_controller = rect_zoom_input_controller
        self._absorber_drag_input_controller = absorber_drag_input_controller
        self._mask_selection_input_controller = mask_selection_input_controller
        self._emitters = emitters

    def handle_mouse_move_event(self, event: QMouseEvent) -> bool:
        """Handle mouse move events."""
        data_position = self._coordinate_mapper.optional_event_data_position(
            self._owner.coord_transform, event
        )
        data_pos = data_position.as_tuple() if data_position is not None else None

        handled = False
        modifiers_int = 0
        if data_pos is not None:
            wavelength, flux = data_pos
            modifiers_int = KeyMouseIntentMapper.modifier_mask(event.modifiers())
            self._emitters.cursor_position(wavelength, flux, modifiers_int)
            handled = True

        active_channel = self._owner.active_input_channel()
        if active_channel is InteractionChannel.RECT_ZOOM and data_pos is not None:
            self._rect_zoom_input_controller.update_interaction(data_pos, modifiers_int)
            return True

        if (
            active_channel is InteractionChannel.MASK_SELECTION
            and data_pos is not None
            and self._mask_selection_input_controller.active
        ):
            return self._mask_selection_input_controller.update_active_selection(
                wavelength=float(data_pos[0])
            )

        if self._owner.dragging_absorber_id() is not None and data_pos is not None:
            self._absorber_drag_input_controller.update_drag_at(
                position=data_pos, modifiers=modifiers_int
            )
            return True

        return handled

    def handle_mouse_release_event(self, event: QMouseEvent) -> bool:
        """Handle mouse release events."""
        active_channel = self._owner.active_input_channel()
        if (
            active_channel is InteractionChannel.MASK_SELECTION
            and event.button() == Qt.MouseButton.LeftButton
        ):
            return self._handle_mask_selection_complete(event)

        if (
            active_channel is InteractionChannel.RECT_ZOOM
            and event.button() == Qt.MouseButton.LeftButton
        ):
            return self._complete_rect_zoom(event)

        if (
            self._owner.dragging_absorber_id() is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            return self._complete_absorber_drag(event)

        return False

    def handle_mouse_leave(self) -> None:
        """Notify listeners that the cursor left the plot region."""
        self._emitters.cursor_left()

    def handle_double_click_center(self, wavelength: float) -> None:
        """Handle double-click to center spectrum on wavelength."""
        self._emitters.center_requested(CenterOnWavelengthIntent(wavelength=wavelength))

    def handle_mouse_press_event(self, event: QMouseEvent) -> bool:
        """Handle mouse press events from the plot bridge."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._owner.active_input_channel() is InteractionChannel.MASK_SELECTION
        ):
            return self._handle_mask_selection_press(event)

        if event.button() == Qt.MouseButton.LeftButton and self._owner.coord_transform:
            data_position = self._coordinate_mapper.require_event_data_position(
                self._owner.coord_transform, event
            )
            data_pos = data_position.as_tuple()

            modifiers_int = KeyMouseIntentMapper.modifier_mask(event.modifiers())
            if self._absorber_drag_input_controller.begin_drag_at(
                position=data_pos, modifiers=modifiers_int
            ):
                return True

        self.process_mouse_event(event)
        return True

    def process_mouse_event(self, event: QMouseEvent | QWheelEvent) -> None:
        """Process Qt mouse event and generate routed commands."""
        if self._owner.coord_transform is None:
            logger.warning("No coordinate transform available")
            return

        if isinstance(event, QWheelEvent):
            data_position = self._coordinate_mapper.require_event_data_position(
                self._owner.coord_transform, event
            )
            delta = event.angleDelta()
            if delta.isNull():
                pixel_delta = event.pixelDelta()
                if not pixel_delta.isNull():
                    delta = pixel_delta
            self._owner.handle_wheel(data_position.as_tuple(), (delta.x(), delta.y()))
            return

        data_position = self._coordinate_mapper.require_event_data_position(
            self._owner.coord_transform, event
        )
        wavelength = data_position.wavelength
        flux = data_position.flux

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._owner.handle_mouse_click(
                    (wavelength, flux),
                    "left",
                    KeyMouseIntentMapper.modifier_mask(event.modifiers()),
                )
            elif event.button() == Qt.MouseButton.RightButton:
                self._owner.handle_mouse_click((wavelength, flux), "right")

    def _complete_rect_zoom(self, event: QMouseEvent) -> bool:
        """Complete rectangle zoom or cancel when coordinates are unavailable."""
        modifiers_int = KeyMouseIntentMapper.modifier_mask(event.modifiers())
        if self._owner.coord_transform is None:
            self._rect_zoom_input_controller.cancel_unresolved_drag(reason="missing-transform")
            return True

        end_position = self._coordinate_mapper.optional_event_data_position(
            self._owner.coord_transform, event
        )
        end_pos = end_position.as_tuple() if end_position is not None else None

        if end_pos is not None:
            self._rect_zoom_input_controller.complete_interaction(end_pos, modifiers_int)
            return True

        self._rect_zoom_input_controller.cancel_unresolved_drag(reason="transform-failed")
        return True

    def _complete_absorber_drag(self, event: QMouseEvent) -> bool:
        """Complete absorber drag or cancel when coordinates are unavailable."""
        modifiers_int = KeyMouseIntentMapper.modifier_mask(event.modifiers())
        reason: str | None = None
        if self._owner.coord_transform is not None:
            data_position = self._coordinate_mapper.optional_event_data_position(
                self._owner.coord_transform, event
            )
            data_pos = data_position.as_tuple() if data_position is not None else None
            if data_pos is not None:
                self._absorber_drag_input_controller.complete_drag_at(
                    position=data_pos, modifiers=modifiers_int
                )
                return True
            reason = "transform-failed"
        else:
            reason = "missing-transform"

        self._absorber_drag_input_controller.cancel_active_drag(
            reason=reason, position=None, modifiers=modifiers_int, raise_on_rejected=True
        )
        return True

    def _handle_mask_selection_complete(self, event: QMouseEvent) -> bool:
        """Handle completion of a mask selection gesture."""
        if not self._mask_selection_input_controller.active:
            return True

        if self._owner.coord_transform is None:
            self._owner.cancel_mask_selection_interaction(reason="missing-transform")
            return True

        data_position = self._coordinate_mapper.optional_event_data_position(
            self._owner.coord_transform, event
        )
        data_pos = data_position.as_tuple() if data_position is not None else None

        if data_pos is None:
            self._owner.cancel_mask_selection_interaction(reason="transform-failed")
            return True

        return self._mask_selection_input_controller.complete_drag_at(
            wavelength=float(data_pos[0])
        )

    def _handle_mask_selection_press(self, event: QMouseEvent) -> bool:
        """Handle the first mouse press when mask selection is active."""
        if self._mask_selection_input_controller.active:
            return True

        if self._owner.coord_transform is None:
            self._owner.cancel_mask_selection_interaction(reason="missing-transform")
            return True

        data_position = self._coordinate_mapper.optional_event_data_position(
            self._owner.coord_transform, event
        )
        data_pos = data_position.as_tuple() if data_position is not None else None

        if data_pos is None:
            self._owner.cancel_mask_selection_interaction(reason="transform-failed")
            return True

        return self._mask_selection_input_controller.begin_drag_at(wavelength=float(data_pos[0]))
