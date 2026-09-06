"""Composition helpers for spectrum input interaction components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from chappy.gui.spectrum.interaction.channels.factory import (
    InteractionControllerFactory,
    InteractionControllerFactoryPorts,
)
from chappy.gui.spectrum.interaction.input.binding.spectrum_plot_input_binding import (
    SpectrumPlotInputBinding,
)
from chappy.gui.spectrum.interaction.input.controllers.absorber_drag_input_controller import (
    AbsorberDragInputController,
)
from chappy.gui.spectrum.interaction.input.controllers.cursor_wavelength_input_controller import (
    CursorWavelengthInputController,
)
from chappy.gui.spectrum.interaction.input.controllers.mask_selection_input_controller import (
    MaskSelectionInputController,
)
from chappy.gui.spectrum.interaction.input.controllers.pointer_input_controller import (
    PointerInputEmitters,
    SpectrumPointerInputController,
)
from chappy.gui.spectrum.interaction.input.controllers.rect_zoom_input_controller import (
    RectZoomInputController,
)
from chappy.gui.spectrum.interaction.input.controllers.velocity_shortcut_input_controller import (
    VelocityShortcutInputController,
)
from chappy.gui.spectrum.interaction.input.interaction_command_executor import (
    SpectrumInteractionCommandExecutor,
)
from chappy.gui.spectrum.interaction.input.mapping.pointer_coordinate_mapper import (
    SpectrumPointerCoordinateMapper,
)
from chappy.gui.spectrum.interaction.input.mapping.qt_input_mapper import KeyMouseIntentMapper
from chappy.gui.spectrum.interaction.input.routing.click_router import SpectrumClickRouter
from chappy.gui.spectrum.interaction.input.routing.shortcut_router import SpectrumShortcutRouter
from chappy.gui.spectrum.interaction.input.routing.wheel_router import SpectrumWheelRouter
from chappy.gui.spectrum.interaction.input.spectrum_interaction_runtime import (
    SpectrumInteractionRuntime,
)
from chappy.gui.spectrum.interaction.input.velocity_drag_interaction_adapter import (
    VelocityDragInteractionAdapter,
)

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable

    from chappy.gui.protocols.intent_types import (
        CenterOnWavelengthIntent,
        SpectrumInteractionIntent,
    )
    from chappy.gui.spectrum.interaction.channels.coordinator import InteractionChannelCoordinator
    from chappy.gui.spectrum.interaction.channels.ports import InteractionChannelControllerPort
    from chappy.gui.spectrum.interaction.input.owner_ports import (
        SpectrumInputCompositionOwnerPort,
        VelocityShortcutModeCapabilities,
    )
    from chappy.gui.spectrum.interaction.input.ports import SpectrumPlotWidgetPort
    from chappy.gui.utils.plot_coordinate_transform import PlotCoordinateTransform


@dataclass(frozen=True, slots=True)
class SpectrumInputCompositionCallbacks:
    """Callbacks required by the spectrum input component composition."""

    controller_ports: InteractionControllerFactoryPorts
    transform_provider: Callable[[], PlotCoordinateTransform | None]
    plot_widget_provider: Callable[[], SpectrumPlotWidgetPort | None]
    intent_emitter: Callable[[SpectrumInteractionIntent], None]
    mode_velocity_shortcut_emitter: Callable[[], None]
    mode_click_emitter: Callable[[tuple[float, float], int], None]
    cursor_position_emitter: Callable[[float, float, int], None]
    cursor_left_emitter: Callable[[], None]
    center_requested_emitter: Callable[[CenterOnWavelengthIntent], None]
    velocity_shortcut_mode_capabilities: VelocityShortcutModeCapabilities


@dataclass(frozen=True, slots=True)
class SpectrumInputComposition:
    """Components assembled for `SpectrumInputAdapter`."""

    plot_input_binding: SpectrumPlotInputBinding
    event_mapper: KeyMouseIntentMapper
    coordinate_mapper: SpectrumPointerCoordinateMapper
    shortcut_router: SpectrumShortcutRouter
    click_router: SpectrumClickRouter
    wheel_router: SpectrumWheelRouter
    rect_zoom_input_controller: RectZoomInputController
    absorber_drag_input_controller: AbsorberDragInputController
    channel_coordinator: InteractionChannelCoordinator
    rect_zoom_state_controller: InteractionChannelControllerPort
    absorber_state_controller: InteractionChannelControllerPort
    velocity_drag_adapter: VelocityDragInteractionAdapter
    velocity_shortcut_input_controller: VelocityShortcutInputController
    cursor_wavelength_input_controller: CursorWavelengthInputController
    mask_state_controller: InteractionChannelControllerPort
    mask_selection_input_controller: MaskSelectionInputController
    pointer_input_controller: SpectrumPointerInputController
    interaction_runtime: SpectrumInteractionRuntime
    command_executor: SpectrumInteractionCommandExecutor


def build_spectrum_input_composition(
    *,
    owner: SpectrumInputCompositionOwnerPort,
    callbacks: SpectrumInputCompositionCallbacks,
    logger: logging.Logger,
) -> SpectrumInputComposition:
    """Build the default input-side interaction component graph."""
    plot_input_binding = SpectrumPlotInputBinding()
    event_mapper = KeyMouseIntentMapper()
    coordinate_mapper = SpectrumPointerCoordinateMapper()

    # Qt's ControlModifier maps to the platform primary modifier:
    # Command on macOS and Ctrl on Windows/Linux.
    zoom_modifiers = (Qt.KeyboardModifier.ControlModifier,)
    shortcut_router = SpectrumShortcutRouter(mapper=event_mapper, zoom_modifiers=zoom_modifiers)
    click_router = SpectrumClickRouter()
    wheel_router = SpectrumWheelRouter()

    rect_zoom_input_controller = RectZoomInputController(owner=owner)
    absorber_drag_input_controller = AbsorberDragInputController(owner=owner)

    controller_bundle = InteractionControllerFactory(logger=logger).create(
        callbacks.controller_ports
    )
    velocity_drag_adapter = VelocityDragInteractionAdapter(
        owner=absorber_drag_input_controller,
        absorber_drag_controller=controller_bundle.absorber_drag,
    )
    cursor_wavelength_input_controller = CursorWavelengthInputController(
        coordinate_mapper=coordinate_mapper,
        transform_provider=callbacks.transform_provider,
        plot_widget_provider=callbacks.plot_widget_provider,
    )
    velocity_shortcut_input_controller = VelocityShortcutInputController(
        owner=owner, mode_capabilities=callbacks.velocity_shortcut_mode_capabilities, logger=logger
    )
    mask_selection_input_controller = MaskSelectionInputController(owner=owner)
    pointer_input_controller = SpectrumPointerInputController(
        owner=owner,
        coordinate_mapper=coordinate_mapper,
        rect_zoom_input_controller=rect_zoom_input_controller,
        absorber_drag_input_controller=absorber_drag_input_controller,
        mask_selection_input_controller=mask_selection_input_controller,
        emitters=PointerInputEmitters(
            cursor_position=callbacks.cursor_position_emitter,
            cursor_left=callbacks.cursor_left_emitter,
            center_requested=callbacks.center_requested_emitter,
        ),
    )
    interaction_runtime = SpectrumInteractionRuntime(
        intent_emitter=callbacks.intent_emitter,
        mode_velocity_shortcut_emitter=callbacks.mode_velocity_shortcut_emitter,
        mode_click_emitter=callbacks.mode_click_emitter,
        rect_zoom_input_controller=rect_zoom_input_controller,
        mask_selection_input_controller=mask_selection_input_controller,
    )
    command_executor = SpectrumInteractionCommandExecutor(port=interaction_runtime)

    return SpectrumInputComposition(
        plot_input_binding=plot_input_binding,
        event_mapper=event_mapper,
        coordinate_mapper=coordinate_mapper,
        shortcut_router=shortcut_router,
        click_router=click_router,
        wheel_router=wheel_router,
        rect_zoom_input_controller=rect_zoom_input_controller,
        absorber_drag_input_controller=absorber_drag_input_controller,
        channel_coordinator=controller_bundle.channel_coordinator,
        rect_zoom_state_controller=controller_bundle.rect_zoom,
        absorber_state_controller=controller_bundle.absorber_drag,
        velocity_drag_adapter=velocity_drag_adapter,
        velocity_shortcut_input_controller=velocity_shortcut_input_controller,
        cursor_wavelength_input_controller=cursor_wavelength_input_controller,
        mask_state_controller=controller_bundle.mask_selection,
        mask_selection_input_controller=mask_selection_input_controller,
        pointer_input_controller=pointer_input_controller,
        interaction_runtime=interaction_runtime,
        command_executor=command_executor,
    )
