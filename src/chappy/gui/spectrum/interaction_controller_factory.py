"""Factories for spectrum interaction controller composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.gui.spectrum.absorber_drag_coordinator import SpectrumAbsorberDragCoordinator
from chappy.gui.spectrum.absorber_interaction_controller import (
    SpectrumAbsorberInteractionController,
)
from chappy.gui.spectrum.context_menu_controller import SpectrumContextMenuController
from chappy.gui.spectrum.mask_interaction_controller import SpectrumMaskInteractionController
from chappy.gui.spectrum.range_coordinator import RangeCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QWidget

    from chappy.core.components.absorber import AbsorberComponent
    from chappy.gui.protocols.context_menu import ContextMenuActionIntent
    from chappy.gui.protocols.optimize_spectrum import SpectrumModeIntegrationPort
    from chappy.gui.spectrum.absorber_drag_coordinator import AbsorberDragApplyPort
    from chappy.gui.spectrum.absorber_interaction_controller import AbsorberModelMutationPort
    from chappy.gui.spectrum.context_menu_controller import ContextMenuActionProvider
    from chappy.gui.spectrum.mask_interaction_controller import (
        MaskOverlayPlotPort,
        MaskSelectionInteractorPort,
    )
    from chappy.gui.spectrum.range_coordinator import RangeHistoryRecorder, RangeInputSyncPort
    from chappy.gui.spectrum.spectrum_data_bridge import SpectrumDataBridge
    from chappy.gui.spectrum.spectrum_plot import SpectrumPlotHost, SpectrumPlotSurfaceProtocol
    from chappy.presentation.interaction.interaction_contracts import (
        InteractionStateSnapshot,
        MaskSelectionContext,
    )
    from chappy.presentation.velocity import VelocityOverlayInfo


@dataclass(frozen=True, slots=True)
class SpectrumInteractionControllerFactory:
    """Factory for shared spectrum interaction controllers."""

    def create_range_coordinator(
        self,
        *,
        data_bridge_provider: Callable[[], SpectrumDataBridge | None],
        plot_host_provider: Callable[[], SpectrumPlotHost | None],
        range_input_provider: Callable[[], RangeInputSyncPort | None],
        history_recorder_provider: Callable[[], RangeHistoryRecorder | None],
        flux_range_override_provider: Callable[[], tuple[float, float] | None],
    ) -> RangeCoordinator:
        """Create the range coordinator."""
        return RangeCoordinator(
            data_bridge_provider=data_bridge_provider,
            plot_host_provider=plot_host_provider,
            range_input_provider=range_input_provider,
            history_recorder_provider=history_recorder_provider,
            flux_range_override_provider=flux_range_override_provider,
        )

    def create_absorber_drag_coordinator(
        self,
        *,
        absorber_provider: Callable[[str], AbsorberComponent | None],
        velocity_overlay_provider: Callable[[], VelocityOverlayInfo | None],
        plot_widget_provider: Callable[[], SpectrumPlotSurfaceProtocol | None],
        drag_apply_callback: AbsorberDragApplyPort,
        cursor_reset_callback: Callable[[], None],
    ) -> SpectrumAbsorberDragCoordinator:
        """Create the absorber drag coordinator."""
        return SpectrumAbsorberDragCoordinator(
            absorber_provider=absorber_provider,
            velocity_overlay_provider=velocity_overlay_provider,
            plot_widget_provider=plot_widget_provider,
            drag_apply_callback=drag_apply_callback,
            cursor_reset_callback=cursor_reset_callback,
        )

    def create_absorber_interaction_controller(
        self,
        *,
        mutation_provider: Callable[[], AbsorberModelMutationPort | None],
        selection_callback: Callable[[str], None],
        drag_coordinator: SpectrumAbsorberDragCoordinator,
    ) -> SpectrumAbsorberInteractionController:
        """Create the absorber interaction controller."""
        return SpectrumAbsorberInteractionController(
            mutation_provider=mutation_provider,
            selection_callback=selection_callback,
            drag_coordinator=drag_coordinator,
        )

    def create_mask_interaction_controller(
        self,
        *,
        interactor_provider: Callable[[], MaskSelectionInteractorPort | None],
        plot_host_provider: Callable[[], MaskOverlayPlotPort | None],
        integration_provider: Callable[[], SpectrumModeIntegrationPort | None],
        snapshot_callback: Callable[[InteractionStateSnapshot[MaskSelectionContext]], None],
    ) -> SpectrumMaskInteractionController:
        """Create the mask interaction controller."""
        return SpectrumMaskInteractionController(
            interactor_provider=interactor_provider,
            plot_host_provider=plot_host_provider,
            integration_provider=integration_provider,
            snapshot_callback=snapshot_callback,
        )

    def create_context_menu_controller(
        self,
        *,
        view_provider: Callable[[], QWidget],
        action_provider: ContextMenuActionProvider,
        intent_handler: Callable[[ContextMenuActionIntent], None],
        parent: QObject,
    ) -> SpectrumContextMenuController:
        """Create the context menu controller."""
        return SpectrumContextMenuController(
            view_provider=view_provider,
            action_provider=action_provider,
            intent_handler=intent_handler,
            parent=parent,
        )
