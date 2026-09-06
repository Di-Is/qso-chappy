"""Factory for spectrum interaction state controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.gui.spectrum.interaction.channels.absorber_drag.interaction_controller import (
    AbsorberDragInteractionController,
)
from chappy.gui.spectrum.interaction.channels.absorber_drag.state_controller import (
    AbsorberDragIntent,
    AbsorberDragStateController,
)
from chappy.gui.spectrum.interaction.channels.coordinator import InteractionChannelCoordinator
from chappy.gui.spectrum.interaction.channels.mask_selection.interaction_controller import (
    MaskSelectionInteractionController,
)
from chappy.gui.spectrum.interaction.channels.mask_selection.state_controller import (
    MaskSelectionStateController,
)
from chappy.gui.spectrum.interaction.channels.rect_zoom.interaction_controller import (
    RectZoomInteractionController,
)
from chappy.gui.spectrum.interaction.channels.rect_zoom.state_controller import (
    RectZoomStateController,
)
from chappy.gui.spectrum.interaction.support.logging import InteractionLogEmitter
from chappy.presentation.interaction.interaction_contracts import (
    InteractionChannel,
    InteractionStateSnapshot,
)

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable

    from chappy.gui.protocols.intent_types import ZoomRectIntent
    from chappy.gui.protocols.interaction_overlay import InteractionOverlayProtocol
    from chappy.gui.spectrum.interaction.support.contexts import SnapshotContext


@dataclass(frozen=True, slots=True)
class InteractionControllerBundle:
    """Controllers and channel coordinator required by `SpectrumInputAdapter`."""

    channel_coordinator: InteractionChannelCoordinator
    rect_zoom: RectZoomStateController
    absorber_drag: AbsorberDragStateController
    mask_selection: MaskSelectionStateController


@dataclass(frozen=True, slots=True)
class InteractionControllerFactoryPorts:
    """Callbacks required to compose interaction controllers."""

    snapshot_consumer: Callable[[InteractionStateSnapshot[SnapshotContext]], None]
    overlay_provider: Callable[[], InteractionOverlayProtocol | None]
    zoom_intent_emitter: Callable[[ZoomRectIntent], None]
    absorber_drag_intent_emitter: Callable[[AbsorberDragIntent], None]
    absorber_drag_state_tracker: Callable[[str | None], None]


class InteractionControllerFactory:
    """Build the default spectrum interaction controller set."""

    def __init__(self, *, logger: logging.Logger) -> None:
        """Initialize the factory."""
        self._logger = logger

    def create(self, ports: InteractionControllerFactoryPorts) -> InteractionControllerBundle:
        """Create and register all default interaction controllers."""
        channel_coordinator = InteractionChannelCoordinator()

        rect_zoom = self._create_rect_zoom_interaction_controller(ports)

        absorber_drag = self._create_absorber_drag_interaction_controller(ports)

        mask_selection = self._create_mask_selection_interaction_controller(ports)

        return InteractionControllerBundle(
            channel_coordinator=channel_coordinator,
            rect_zoom=rect_zoom,
            absorber_drag=absorber_drag,
            mask_selection=mask_selection,
        )

    def _create_rect_zoom_interaction_controller(
        self, ports: InteractionControllerFactoryPorts
    ) -> RectZoomStateController:
        """Create the rectangle zoom state controller."""
        log_emitter = InteractionLogEmitter(
            channel=InteractionChannel.RECT_ZOOM, logger=self._logger
        )
        rect_zoom_interaction_controller = RectZoomInteractionController(
            overlay_provider=ports.overlay_provider, log_emitter=log_emitter
        )
        return RectZoomStateController(
            snapshot_consumer=ports.snapshot_consumer,
            rect_zoom_interaction_controller=rect_zoom_interaction_controller,
            zoom_intent_emitter=ports.zoom_intent_emitter,
            logger=self._logger,
        )

    def _create_absorber_drag_interaction_controller(
        self, ports: InteractionControllerFactoryPorts
    ) -> AbsorberDragStateController:
        """Create the absorber drag state controller."""
        log_emitter = InteractionLogEmitter(
            channel=InteractionChannel.ABSORBER_DRAG, logger=self._logger
        )
        absorber_controller = AbsorberDragInteractionController(log_emitter=log_emitter)
        return AbsorberDragStateController(
            snapshot_consumer=ports.snapshot_consumer,
            absorber_drag_interaction_controller=absorber_controller,
            absorber_drag_intent_emitter=ports.absorber_drag_intent_emitter,
            absorber_drag_state_tracker=ports.absorber_drag_state_tracker,
            logger=self._logger,
        )

    def _create_mask_selection_interaction_controller(
        self, ports: InteractionControllerFactoryPorts
    ) -> MaskSelectionStateController:
        """Create the mask selection state controller."""
        log_emitter = InteractionLogEmitter(
            channel=InteractionChannel.MASK_SELECTION, logger=self._logger
        )
        mask_controller = MaskSelectionInteractionController(
            log_emitter=log_emitter, overlay_provider=ports.overlay_provider
        )
        return MaskSelectionStateController(
            snapshot_consumer=ports.snapshot_consumer,
            mask_selection_interaction_controller=mask_controller,
            logger=self._logger,
        )
