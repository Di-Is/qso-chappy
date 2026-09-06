"""Coordinate shell-owned spectrum surface wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.gui.shell.absorber_model_mutation_controller import (
    AbsorberModelMutationController,
    AbsorberModelMutationPorts,
)
from chappy.gui.shell.spectrum_mode_intent_router import (
    SpectrumModeIntentRouter,
    SpectrumModeIntentRouterPorts,
)
from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QAction

    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.common import ModeRuntime
    from chappy.gui.shell.absorber_model_mutation_controller import AbsorberEditHistoryPort
    from chappy.gui.shell.view_stack import ViewStack
    from chappy.gui.spectrum.spectrum_view import SpectrumView


@dataclass(frozen=True, slots=True)
class SpectrumSurfacePorts:
    """Dependencies required to wire the shell spectrum surface."""

    project_provider: Callable[[], SpectroscopyProject | None]
    history_provider: Callable[[], AbsorberEditHistoryPort]
    view_stack_provider: Callable[[], ViewStack | None]
    active_runtime_provider: Callable[[], ModeRuntime | None]
    refresh_velocity_overlay: Callable[[], None]
    display_actions_provider: Callable[[], tuple[QAction, ...]]


class SpectrumSurfaceCoordinator:
    """Attach shell-owned spectrum routing and mutation owners."""

    def __init__(self, ports: SpectrumSurfacePorts) -> None:
        """Store surface wiring dependencies."""
        self._ports = ports
        self._spectrum_mode_intent_router: SpectrumModeIntentRouter | None = None
        self._absorber_model_mutation_controller: AbsorberModelMutationController | None = None

    def setup(self) -> None:
        """Attach mutation owner and mode-intent routing to the spectrum surface."""
        presenter = self._require_presenter()
        spectrum_view = self._require_spectrum_view()

        self._absorber_model_mutation_controller = AbsorberModelMutationController(
            ports=AbsorberModelMutationPorts(
                project_provider=self._ports.project_provider,
                line_info_provider=presenter.line_info_for_component,
                history_provider=self._ports.history_provider,
                plot_widget_provider=presenter.plot_widget,
                plot_refresh_callback=spectrum_view.update_plot,
                data_updated_callback=presenter.emit_data_updated,
                refresh_optimize_callback=presenter.refresh_optimize_tree_view,
                focus_component_callback=presenter.focus_optimize_component,
                refresh_velocity_overlay_callback=self._ports.refresh_velocity_overlay,
            )
        )
        presenter.attach_absorber_model_mutation_owner(self._absorber_model_mutation_controller)

        self._spectrum_mode_intent_router = SpectrumModeIntentRouter(
            SpectrumModeIntentRouterPorts(
                active_runtime_provider=self._ports.active_runtime_provider
            )
        )
        presenter.attach_mode_intent_sink(self._spectrum_mode_intent_router)
        presenter.set_context_menu_action_provider(
            self._spectrum_mode_intent_router.context_menu_actions
        )
        presenter.set_context_menu_shared_actions(self._ports.display_actions_provider)

    def _require_spectrum_view(self) -> SpectrumView:
        view_stack = self._ports.view_stack_provider()
        if view_stack is None or view_stack.spectrum_view is None:
            msg = "Spectrum surface setup requires a spectrum view."
            raise RuntimeError(msg)
        return view_stack.spectrum_view

    def _require_presenter(self) -> SpectrumInteractionCoordinator:
        presenter = self._require_spectrum_view().coordinator
        if not isinstance(presenter, SpectrumInteractionCoordinator):
            msg = (
                "Spectrum surface setup requires SpectrumInteractionCoordinator, "
                f"got {type(presenter).__name__}."
            )
            raise TypeError(msg)
        return presenter
