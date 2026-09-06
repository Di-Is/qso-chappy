"""Shell-owned absorber model mutation controller."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.application.history import component_parameter_state
from chappy.application.spectrum.absorber_edit_usecase import (
    AbsorberEditTarget,
    AbsorberEditUseCase,
    AbsorberEditValidationError,
    RedshiftConstraintContext,
)
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.tie_set import effective_tie_set_for_parameter

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from chappy.application.history import ComponentParameterState
    from chappy.core.components.base import ModelComponent
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.protocols.optimize_spectrum import OptimizeLineInfo

logger = logging.getLogger(__name__)


class AbsorberEditHistoryPort(Protocol):
    """History operations required by absorber edits."""

    def atomic_recording(self) -> AbstractContextManager[None]:
        """Return a scope that restores history state when recording fails."""
        ...

    def record_model_edit_params(
        self,
        component_ids: list[str],
        param_name: str,
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        region_id: str | None,
    ) -> None:
        """Record a model parameter edit."""
        ...


@runtime_checkable
class AbsorptionMarkerPlotPort(Protocol):
    """Plot widget that can update absorber marker state."""

    def update_absorption_marker_redshift(self, component_id: str, redshift: float) -> None:
        """Update a marker to match a redshift edit."""
        ...


@dataclass(frozen=True, slots=True)
class AbsorberModelMutationPorts:
    """Collaborators required by absorber model mutation."""

    project_provider: Callable[[], SpectroscopyProject | None]
    line_info_provider: Callable[[AbsorberComponent], OptimizeLineInfo | None]
    history_provider: Callable[[], AbsorberEditHistoryPort]
    plot_widget_provider: Callable[[], object | None]
    plot_refresh_callback: Callable[[], None]
    data_updated_callback: Callable[[], None]
    refresh_optimize_callback: Callable[[], None]
    focus_component_callback: Callable[[str], None]
    refresh_velocity_overlay_callback: Callable[[], None]


class AbsorberModelMutationController:
    """Apply absorber model mutations outside the shared spectrum facade."""

    def __init__(
        self, *, ports: AbsorberModelMutationPorts, edit_usecase: AbsorberEditUseCase | None = None
    ) -> None:
        """Initialize the controller."""
        self._ports = ports
        self._edit_usecase = edit_usecase or AbsorberEditUseCase()

    def update_parameter(
        self, absorber: AbsorberEditTarget, parameter_name: str, value: float
    ) -> None:
        """Apply a parameter edit from UI controls."""
        project = self._ports.project_provider()
        if project is None:
            logger.warning("No project available to update absorber")
            return

        component = self._edit_usecase.resolve_component(project, absorber)
        if component is None:
            logger.warning("Absorber %s not found in model", absorber)
            return
        if not isinstance(component, AbsorberComponent):
            logger.warning("Model component %s is not an absorber", component.id)
            return

        before_states = self._parameter_states(component, parameter_name)
        history = self._require_history()

        def record_parameter_history() -> None:
            self._record_parameter_history(
                history, project, parameter_name=parameter_name, before_states=before_states
            )

        try:
            result = self._edit_usecase.update_parameter(
                project,
                component,
                parameter_name,
                value,
                self._constraint_context(component),
                record_history=record_parameter_history,
                history_scope=history.atomic_recording,
            )
        except AbsorberEditValidationError as error:
            logger.warning(
                "Failed to set parameter %s on absorber %s: %s",
                parameter_name,
                component.id,
                error,
            )
            return

        if result is None:
            logger.warning(
                "Failed to update absorber %s parameter %s", component.id, parameter_name
            )
            return

        if result.impact.changed:
            run_postcommit_actions_isolated(
                self._ports.data_updated_callback,
                self._ports.refresh_optimize_callback,
                self._ports.refresh_velocity_overlay_callback,
                self._ports.plot_refresh_callback,
            )

    def apply_drag(
        self,
        component_id: str,
        new_redshift: float,
        before_states: tuple[ComponentParameterState, ...],
    ) -> None:
        """Apply a completed absorber drag to the active model."""
        project = self._ports.project_provider()
        if project is None:
            logger.warning("No project available to update absorber")
            return

        component = self.resolve_absorber(component_id)
        if component is None:
            logger.warning("Absorber %s not found in model", component_id)
            return
        if not before_states:
            logger.warning("Skipped absorber drag without a captured before-state")
            return

        history = self._require_history()

        def record_parameter_history() -> None:
            self._record_parameter_history(
                history, project, parameter_name="redshift", before_states=before_states
            )

        result = self._edit_usecase.update_redshift(
            project,
            component_id,
            new_redshift,
            self._constraint_context(component),
            record_history=record_parameter_history,
            history_scope=history.atomic_recording,
        )
        if result is None:
            logger.warning("Absorber %s not found in model", component_id)
            return

        if result.impact.changed:

            def update_plot_marker() -> None:
                """Update the drag marker when the active plot supports it."""
                plot_widget = self._ports.plot_widget_provider()
                if isinstance(plot_widget, AbsorptionMarkerPlotPort):
                    plot_widget.update_absorption_marker_redshift(
                        component_id, result.applied_value
                    )

            run_postcommit_actions_isolated(
                self._ports.data_updated_callback,
                self._ports.refresh_optimize_callback,
                self._ports.refresh_velocity_overlay_callback,
                lambda: self._ports.focus_component_callback(component_id),
                update_plot_marker,
                self._ports.plot_refresh_callback,
            )

    def resolve_absorber(self, absorber_id: str) -> AbsorberComponent | None:
        """Resolve an absorber by identifier from the current project."""
        project = self._ports.project_provider()
        if project is None:
            logger.warning("No current project to search for absorber")
            return None

        for component in project.model.components:
            if isinstance(component, AbsorberComponent) and component.id == absorber_id:
                return component
        logger.warning("Absorber with ID %s not found in model", absorber_id)
        return None

    def _constraint_context(self, component: ModelComponent) -> RedshiftConstraintContext | None:
        """Return redshift constraints for an absorber component."""
        if not isinstance(component, AbsorberComponent):
            return None

        line_info = self._ports.line_info_provider(component)
        if line_info is None:
            return RedshiftConstraintContext()

        return RedshiftConstraintContext(
            rest_wavelength=line_info.get("rest_wavelength"),
            lambda_range=line_info.get("lambda_range"),
        )

    def _record_parameter_history(
        self,
        history: AbsorberEditHistoryPort,
        project: SpectroscopyProject,
        *,
        parameter_name: str,
        before_states: tuple[ComponentParameterState, ...],
    ) -> None:
        """Record one parameter edit inside the scientific transaction."""
        if not before_states:
            msg = "Absorber scientific history requires a captured before-state."
            raise RuntimeError(msg)

        target_ids = [state.component_id for state in before_states]
        after_states: list[ComponentParameterState] = []
        for component_id in target_ids:
            component = self._edit_usecase.resolve_component(project, component_id)
            if isinstance(component, AbsorberComponent):
                after_states.append(component_parameter_state(component))

        if len(after_states) != len(target_ids):
            msg = (
                "Cannot record absorber parameter history because "
                f"{len(after_states)} of {len(target_ids)} after-states were resolved."
            )
            raise RuntimeError(msg)

        history.record_model_edit_params(
            target_ids, parameter_name, before_states, tuple(after_states), None
        )

    def _require_history(self) -> AbsorberEditHistoryPort:
        """Return the required scientific history owner before mutation begins."""
        history = self._ports.history_provider()
        if history is None:
            msg = "Absorber scientific mutations require a history owner."
            raise RuntimeError(msg)
        return history

    @staticmethod
    def _parameter_states(
        component: AbsorberComponent, parameter_name: str
    ) -> tuple[ComponentParameterState, ...]:
        """Capture all absorber components sharing the edited parameter."""
        tie_set = effective_tie_set_for_parameter(component, parameter_name)
        targets = tuple(tie_set.components) if tie_set is not None else (component,)
        return tuple(component_parameter_state(target) for target in targets)
