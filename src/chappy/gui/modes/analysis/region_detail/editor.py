"""Editor for optimization and fitting controls."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget

from chappy.application.analysis_artifacts import RecordSuccessfulAnalysisUseCase
from chappy.application.history import (
    ComponentParameterState,
    LineOptimizationStateSnapshot,
    NamedParameterState,
)
from chappy.application.optimize import (
    CaptureOptimizeHistorySnapshotUseCase,
    ComponentParameterSnapshot,
    FitResultRawPayload,
    LineOptimizationInputSnapshot,
    OptimizeHistorySnapshot,
    ParameterStateSnapshot,
)
from chappy.application.optimize.group_range_resolver import OptimizeGroupRangeResolver
from chappy.core.analysis import FitSummary
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.optimize import (
    FitAttempt,
    FitCancellationToken,
    FitCancelledError,
    FitResult,
    LineConstraints,
    OptimizeComponent,
)
from chappy.core.editing_mode import EditingMode
from chappy.core.optimizer_settings import (
    DEFAULT_AUTO_CONTINUE,
    DEFAULT_MAX_FUNCTION_EVALUATIONS,
    DEFAULT_TOLERANCE,
)
from chappy.gui.utils.fit_requirements import region_has_models

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from datetime import datetime

    from PySide6.QtGui import QCloseEvent

    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.analysis import RegionAnalysisState
    from chappy.core.components.base import ModelComponent
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.mode_state_store import ModeStateStore


logger = logging.getLogger(__name__)


class OptimizeEditorHistoryRecorder(Protocol):
    """History recording operation required by the optimize editor."""

    def record_model_optimize_apply(
        self,
        target_component_ids: list[str],
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        region_id: str | None,
        needs_optimization_before: tuple[LineOptimizationStateSnapshot, ...],
    ) -> None:
        """Record optimization result application."""
        ...

    def atomic_recording(self) -> AbstractContextManager[None]:
        """Return a rollback scope for the fit history entry."""
        ...


@dataclass(frozen=True, slots=True)
class _FitProjectSnapshot:
    """Exact project-owned facts protected by a successful fit commit."""

    modified: datetime
    analysis_states: tuple[RegionAnalysisState, ...]
    optimization_flags: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class _ActiveFit:
    """UI-owned state retained while a detached fit runs in its worker."""

    project: SpectroscopyProject
    optimizer: OptimizeComponent
    attempt: FitAttempt
    cancellation: FitCancellationToken
    target_component_ids: frozenset[str]
    region_id: str
    before_history: OptimizeHistorySnapshot


class _FitWorker(QObject):
    """Run one detached optimizer attempt without accessing Qt widgets."""

    succeeded = Signal(object)
    failed = Signal(object)
    cancelled = Signal()
    done = Signal()

    def __init__(
        self, optimizer: OptimizeComponent, attempt: FitAttempt, cancellation: FitCancellationToken
    ) -> None:
        """Initialize one worker-owned fit invocation."""
        super().__init__()
        self._optimizer = optimizer
        self._attempt = attempt
        self._cancellation = cancellation

    @Slot()
    def run(self) -> None:
        """Execute the detached fit and transport its typed outcome to the UI thread."""
        try:
            result = self._optimizer.run_fit_attempt(
                self._attempt, cancellation=self._cancellation
            )
        except FitCancelledError:
            self.cancelled.emit()
        except Exception as error:  # noqa: BLE001 - transport worker failure to UI boundary
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.done.emit()
            QThread.currentThread().quit()


class OptimizeEditor(QWidget):
    """Fit backend behind RegionDetailPanel's ports.

    Runs optimizer attempts on a worker thread, commits successful results
    through the project's history/rollback machinery, and exposes region-scoped
    optimizer convergence settings. Built headless (no parent, never added to a
    layout) and driven entirely through its ports and Qt signals.

    Signals:
        fit_started: Emitted when fitting begins
        fit_completed: Emitted when fitting completes with results
        parameter_changed: Emitted when optimization parameters change
    """

    # Qt signals
    fit_started = Signal()  # Qt signal follows framework naming convention
    fit_completed = Signal(  # Qt signal follows framework naming convention
        dict
    )  # fit_results
    parameter_changed = Signal(  # Qt signal follows framework naming convention
        str, float
    )  # param_name, value

    def __init__(
        self,
        parent: QWidget | None = None,
        project: SpectroscopyProject | None = None,
        mode_state_store: ModeStateStore | None = None,
    ) -> None:
        """Initialize optimize editor.

        Args:
            parent: Parent widget
            project: Current project
            mode_state_store: Mode state store instance
        """
        super().__init__(parent)

        # State
        self.current_project: SpectroscopyProject | None = project
        self.optimize_component: OptimizeComponent | None = None
        self.mode_state_store: ModeStateStore | None = mode_state_store
        self._history_recorder: OptimizeEditorHistoryRecorder | None = None
        self._fit_in_progress = False
        self._history_snapshot_usecase = CaptureOptimizeHistorySnapshotUseCase()
        self._record_successful_analysis = RecordSuccessfulAnalysisUseCase()
        self._active_fit: _ActiveFit | None = None
        self._fit_thread: QThread | None = None
        self._fit_worker: _FitWorker | None = None
        self._active_region_id_provider: Callable[[], str | None] | None = None

        # Initialize optimize component
        self._create_optimize_component()

        logger.debug("OptimizeEditor initialized")

    def _create_optimize_component(self) -> None:
        """Create default optimization component."""
        self.optimize_component = OptimizeComponent(
            name="Optimizer",
            algorithm="leastsq",
            max_function_evaluations=DEFAULT_MAX_FUNCTION_EVALUATIONS,
            tolerance=DEFAULT_TOLERANCE,
        )

    def apply_optimizer_settings(
        self,
        region_id: str | None,
        max_function_evaluations: int,
        tolerance: float,
        auto_continue: bool,
    ) -> None:
        """Persist optimizer convergence settings for one region and sync the live component.

        Args:
            region_id: Region the settings apply to, or ``None`` when no region is selected.
            max_function_evaluations: Maximum residual evaluations allowed per round.
            tolerance: Convergence tolerance applied to both ftol and xtol.
            auto_continue: Warm-restart a budget-stalled fit from its best point.
        """
        if self.current_project is not None and region_id is not None:
            self.current_project.set_region_optimizer_settings(
                region_id, max_function_evaluations, tolerance, auto_continue
            )
        if self.optimize_component is not None:
            self.optimize_component.max_function_evaluations = max_function_evaluations
            self.optimize_component.tolerance = tolerance
            self.optimize_component.auto_continue = auto_continue

    def current_optimizer_settings(self, region_id: str | None) -> tuple[int, float, bool]:
        """Return the optimizer convergence settings in effect for one region.

        Args:
            region_id: Region to read settings for, or ``None`` when no region is selected.
        """
        if self.current_project is not None and region_id is not None:
            settings = self.current_project.region_optimizer_settings(region_id)
            return (settings.max_function_evaluations, settings.tolerance, settings.auto_continue)
        if self.optimize_component is not None:
            return (
                self.optimize_component.max_function_evaluations,
                self.optimize_component.tolerance,
                self.optimize_component.auto_continue,
            )
        return (DEFAULT_MAX_FUNCTION_EVALUATIONS, DEFAULT_TOLERANCE, DEFAULT_AUTO_CONTINUE)

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Set current project and update optimization context.

        Args:
            project: Project to set (None to clear)
        """
        project_changed = project is not self.current_project
        if project_changed and self._active_fit is not None:
            self._active_fit.cancellation.cancel()
        self.current_project = project

        if project is None:
            return

        if project_changed:
            self._create_optimize_component()

    def set_history_recorder(self, recorder: OptimizeEditorHistoryRecorder | None) -> None:
        """Set history recorder for undo/redo recording."""
        self._history_recorder = recorder

    def _capture_optimize_history_snapshot(
        self, component_ids: set[str], region_id: str | None
    ) -> OptimizeHistorySnapshot:
        """Capture typed optimize history snapshot for target components.

        Args:
            component_ids: Component IDs whose parameters should be captured.
            region_id: Region ID whose line optimization flags should be captured.

        Returns:
            Typed optimize history snapshot detached from mutable project objects.
        """
        if not self.current_project or not self.current_project.model:
            return OptimizeHistorySnapshot(component_states=(), line_optimization_states=())

        components = tuple(
            ComponentParameterSnapshot(
                component_id=component.id,
                parameters=tuple(
                    ParameterStateSnapshot(
                        name=name,
                        value=parameter.value,
                        fixed=parameter.fixed,
                        error=parameter.error,
                    )
                    for name, parameter in component.parameters.items()
                ),
            )
            for component in self.current_project.model.components
            if isinstance(component, AbsorberComponent)
        )
        lines = tuple(
            LineOptimizationInputSnapshot(
                line_id=line.line_id,
                region_id=line.region_id,
                needs_optimization=line.needs_optimization,
            )
            for line in self.current_project.absorption_lines.values()
        )
        return self._history_snapshot_usecase.capture(
            components=components,
            component_ids=frozenset(component_ids),
            lines=lines,
            region_id=region_id,
        )

    def _component_states_from_snapshot(
        self, snapshot: OptimizeHistorySnapshot
    ) -> tuple[ComponentParameterState, ...]:
        """Convert optimize component snapshots to typed history parameter states."""
        return tuple(
            ComponentParameterState(
                component_id=component.component_id,
                parameters=tuple(
                    NamedParameterState(
                        name=parameter.name,
                        value=parameter.value,
                        vary=not parameter.fixed,
                        min_value=None,
                        max_value=None,
                        error=parameter.error,
                    )
                    for parameter in component.parameters
                ),
            )
            for component in snapshot.component_states
        )

    def _line_optimization_states_from_snapshot(
        self, snapshot: OptimizeHistorySnapshot
    ) -> tuple[LineOptimizationStateSnapshot, ...]:
        """Convert optimize line snapshots to typed history optimization states."""
        return tuple(
            LineOptimizationStateSnapshot(
                line_id=line.line_id, needs_optimization=line.needs_optimization
            )
            for line in snapshot.line_optimization_states
        )

    @Slot()
    def start_fit(self) -> None:
        """Start model fitting process."""
        if not self.current_project or self._fit_in_progress:
            return

        if not self.current_project.model.observed_spectrum:
            logger.warning("No observed spectrum available for fitting")
            return

        if not region_has_models(self.current_project, self._resolve_active_region_id()):
            logger.warning("Fit prerequisites not satisfied for the selected group")
            return

        target_component_ids = self._collect_target_component_ids()
        if not target_component_ids:
            logger.warning("No absorber components available for selected group")
            return

        # Check for free parameters
        free_params = self._count_free_parameters(target_component_ids)
        if free_params == 0:
            return

        try:
            # Update optimize component with current settings
            self._update_optimize_component()

            # Determine wavelength range for fitting
            wavelength_range = self._get_fitting_wavelength_range()

            # Collect line constraints for target components
            line_constraints = []
            if target_component_ids:
                line_constraints = self._collect_line_constraints(target_component_ids)
                if line_constraints:
                    logger.info(
                        "Collected %d line constraint(s) for optimization", len(line_constraints)
                    )

            logger.info("Starting fit with %d free parameters", free_params)
            if wavelength_range:
                logger.info(
                    "Fitting range: %.1f - %.1f Å", wavelength_range[0], wavelength_range[1]
                )

            mask_region_id = self._resolve_active_region_id()
            if mask_region_id is None:
                msg = "An active region is required before starting a fit."
                raise RuntimeError(msg)  # noqa: TRY301 - handled at this UI intent boundary
            before_snapshot = self._capture_optimize_history_snapshot(
                target_component_ids, mask_region_id
            )
            component = self.optimize_component
            if component is None:
                msg = "Optimize component disappeared before fit attempt capture."
                raise RuntimeError(msg)  # noqa: TRY301 - handled at this UI intent boundary
            project = self.current_project
            attempt = component.create_fit_attempt(
                project.model,
                wavelength_range=wavelength_range,
                target_component_ids=target_component_ids,
                mask_group_id=mask_region_id,
                line_constraints=line_constraints,
            )
            cancellation = FitCancellationToken()
            thread = QThread(self)
            worker = _FitWorker(component, attempt, cancellation)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_fit_succeeded)
            worker.failed.connect(self._on_fit_failed)
            worker.cancelled.connect(self._on_fit_cancelled)
            worker.done.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(self._on_fit_thread_finished)

            self._active_fit = _ActiveFit(
                project=project,
                optimizer=component,
                attempt=attempt,
                cancellation=cancellation,
                target_component_ids=frozenset(target_component_ids),
                region_id=mask_region_id,
                before_history=before_snapshot,
            )
            self._fit_thread = thread
            self._fit_worker = worker
            self._fit_in_progress = True
            self.fit_started.emit()
            thread.start()

        except Exception as error:  # noqa: BLE001 - GUI user-intent recovery boundary
            self._handle_fit_error(error)

    @Slot()
    def stop_fit(self) -> None:
        """Request cooperative cancellation of the current worker-owned fit."""
        active = self._active_fit
        if not self._fit_in_progress or active is None:
            return
        active.cancellation.cancel()
        logger.info("Fit cancellation requested by user")

    @Slot(object)
    def _on_fit_succeeded(self, raw_result: object) -> None:
        """Commit one detached successful result on the UI owner thread."""
        if not isinstance(raw_result, FitResult):
            msg = "Fit worker emitted an invalid success result."
            raise TypeError(msg)
        active = self._require_active_fit()
        if active.cancellation.is_cancelled or self.current_project is not active.project:
            self._on_fit_cancelled()
            return
        if not raw_result.success:
            self._complete_failed_fit(raw_result)
            return

        try:
            self._commit_successful_fit(active, raw_result)
        except Exception as error:  # noqa: BLE001 - GUI user-intent recovery boundary
            self._handle_fit_error(error)
            return

        payload: FitResultRawPayload = raw_result.to_signal_payload()
        self._finish_fit_attempt()
        self.fit_completed.emit(payload)
        logger.info("Fit completed: success=True")

    @Slot(object)
    def _on_fit_failed(self, raw_error: object) -> None:
        """Surface a worker backend failure while preserving the live baseline."""
        if not isinstance(raw_error, Exception):
            msg = "Fit worker emitted an invalid failure payload."
            raise TypeError(msg)
        self._handle_fit_error(raw_error)

    @Slot()
    def _on_fit_cancelled(self) -> None:
        """Finish a cooperatively cancelled attempt without committing any state."""
        if self._active_fit is None:
            return
        self._finish_fit_attempt()
        self.fit_completed.emit({"success": False, "message": self.tr("Fit stopped by user")})
        logger.info("Fit stopped by user")

    @Slot()
    def _on_fit_thread_finished(self) -> None:
        """Release worker references after its event loop has stopped."""
        self._fit_worker = None
        self._fit_thread = None

    def _complete_failed_fit(self, result: FitResult) -> None:
        """Apply a typed unsuccessful optimizer outcome without a scientific commit."""
        payload: FitResultRawPayload = result.to_signal_payload()
        self._finish_fit_attempt()
        self.fit_completed.emit(payload)
        logger.info("Fit completed: success=False")

    def _handle_fit_error(self, error: Exception) -> None:
        """Recover one fit failure at the editor's user-intent boundary."""
        self._finish_fit_attempt()
        self.fit_completed.emit({"success": False, "message": str(error)})
        logger.error("Fitting failed", exc_info=(type(error), error, error.__traceback__))

    def _finish_fit_attempt(self) -> None:
        """Clear UI-owned attempt state without touching the worker thread lifecycle."""
        if self._active_fit is None and not self._fit_in_progress:
            return
        self._active_fit = None
        self._fit_in_progress = False

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel and join the fit worker before Qt destroys its thread owner."""
        active = self._active_fit
        if active is not None:
            active.cancellation.cancel()
        thread = self._fit_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait()
        super().closeEvent(event)

    def _require_active_fit(self) -> _ActiveFit:
        """Return the active fit or fail on an impossible worker callback."""
        active = self._active_fit
        if active is None:
            msg = "Fit worker completed without an active attempt."
            raise RuntimeError(msg)
        return active

    def _commit_successful_fit(self, active: _ActiveFit, result: FitResult) -> None:
        """Commit model, evidence, freshness, and history through one rollback scope."""
        project = active.project
        project_snapshot = self._capture_fit_project_snapshot(project)
        history_scope = (
            self._history_recorder.atomic_recording()
            if self._history_recorder is not None
            else contextlib.nullcontext()
        )
        try:
            with history_scope:
                storage_commit = active.optimizer.commit_fit_attempt_storage(
                    project.model, active.attempt, result
                )
                summary = FitSummary(
                    chi_squared=result.chi_squared,
                    reduced_chi_squared=result.reduced_chi_squared,
                    degrees_of_freedom=float(result.degrees_of_freedom),
                    n_parameters=result.n_parameters,
                    n_function_evaluations=result.n_function_evaluations,
                    outcome=result.outcome,
                )
                self._record_successful_analysis.execute(project, active.region_id, summary)
                if self._history_recorder is not None:
                    after_snapshot = self._capture_optimize_history_snapshot(
                        set(active.target_component_ids), active.region_id
                    )
                    self._history_recorder.record_model_optimize_apply(
                        list(active.target_component_ids),
                        self._component_states_from_snapshot(active.before_history),
                        self._component_states_from_snapshot(after_snapshot),
                        active.region_id,
                        self._line_optimization_states_from_snapshot(active.before_history),
                    )
                active.optimizer.finalize_fit_attempt(
                    project.model, active.attempt, result, storage_commit
                )
        except Exception as original_error:
            self._attempt_fit_restore(
                original_error,
                "model parameter and derived state",
                lambda: active.optimizer.rollback_fit_attempt(project.model, active.attempt),
            )
            self._attempt_fit_restore(
                original_error,
                "project analysis evidence and freshness",
                lambda: self._restore_fit_project_snapshot(project, project_snapshot),
            )
            raise

    @staticmethod
    def _capture_fit_project_snapshot(project: SpectroscopyProject) -> _FitProjectSnapshot:
        """Capture all project-owned facts that a successful fit may change."""
        return _FitProjectSnapshot(
            modified=project.modified,
            analysis_states=project.stored_region_analysis_states_for_transaction(),
            optimization_flags=tuple(
                (line_id, line.needs_optimization)
                for line_id, line in project.absorption_lines.items()
            ),
        )

    @staticmethod
    def _restore_fit_project_snapshot(
        project: SpectroscopyProject, snapshot: _FitProjectSnapshot
    ) -> None:
        """Restore exact project evidence, freshness flags, and modified time."""
        project.replace_region_analysis_states_for_transaction(snapshot.analysis_states)
        current_line_ids = set(project.absorption_lines)
        snapshot_line_ids = {line_id for line_id, _flag in snapshot.optimization_flags}
        if current_line_ids != snapshot_line_ids:
            msg = "Fit rollback line identities do not match the project snapshot."
            raise RuntimeError(msg)
        for line_id, needs_optimization in snapshot.optimization_flags:
            project.absorption_lines[line_id].needs_optimization = needs_optimization
        project.modified = snapshot.modified

    @staticmethod
    def _attempt_fit_restore(
        original_error: Exception, label: str, restore: Callable[[], None]
    ) -> None:
        """Attempt one rollback stage without hiding the triggering failure."""
        try:
            restore()
        except Exception as rollback_error:  # noqa: BLE001 - preserve original failure
            original_error.add_note(
                f"Failed to restore {label}: {type(rollback_error).__name__}: {rollback_error}"
            )

    def _update_optimize_component(self) -> None:
        """Update optimize component with the active region's optimizer settings."""
        if not self.optimize_component:
            return
        max_function_evaluations, tolerance, auto_continue = self.current_optimizer_settings(
            self._resolve_active_region_id()
        )
        self.optimize_component.max_function_evaluations = max_function_evaluations
        self.optimize_component.tolerance = tolerance
        self.optimize_component.auto_continue = auto_continue

    def _count_free_parameters(self, target_component_ids: set[str] | None = None) -> int:
        """Count free parameters in current model.

        Returns:
            Number of free parameters
        """
        if not self.current_project:
            return 0

        count = 0
        for component in self.current_project.model.components:
            if not component.enabled:
                continue

            if target_component_ids is not None and component.id not in target_component_ids:
                continue

            for param in component.parameters.values():
                if not param.fixed:
                    count += 1

        return count

    def _collect_target_component_ids(self) -> set[str]:
        """Collect component identifiers associated with the active absorption region."""
        if not self.current_project:
            return set()

        region_id = self._resolve_active_region_id()
        if not region_id:
            return set()

        target_ids = self._component_ids_from_absorption_region(region_id)
        if target_ids:
            logger.debug(
                "Collected %d target components for region '%s'", len(target_ids), region_id
            )
            return target_ids

        fallback_ids = self._component_ids_from_region_assignment(region_id)
        if fallback_ids:
            logger.debug(
                "Falling back to absorber component assignments for region '%s'", region_id
            )
            return fallback_ids

        logger.warning(
            "No absorber components mapped to region '%s'; falling back to global fit", region_id
        )
        return set()

    def _component_ids_from_absorption_region(self, region_id: str) -> set[str]:
        project = self.current_project
        if not project:
            return set()

        absorption_region = project.absorption_regions.get(region_id)
        if not absorption_region:
            return set()

        component_ids: set[str] = set()
        for line_id in absorption_region.line_ids:
            line = project.absorption_lines.get(line_id)
            if not line:
                continue
            for model_id in line.model_ids:
                if isinstance(model_id, str):
                    component_ids.add(model_id)
        return component_ids

    def _component_ids_from_region_assignment(self, region_id: str) -> set[str]:
        project = self.current_project
        if not project:
            return set()

        component_ids: set[str] = set()
        for component in project.model.components:
            if not isinstance(component, AbsorberComponent):
                continue
            if component.group_id == region_id:
                component_ids.add(component.id)
        return component_ids

    def set_active_region_id_provider(self, provider: Callable[[], str | None] | None) -> None:
        """Inject the external owner of the selected region identifier.

        The editor has no widgets of its own; region selection lives in the
        Region Detail panel and must be supplied through this provider.

        Args:
            provider: Callable returning the selected region id, or ``None``.
        """
        self._active_region_id_provider = provider

    def _resolve_active_region_id(self) -> str | None:
        """Return the identifier for the currently selected absorption region."""
        provider = self._active_region_id_provider
        if provider is not None:
            external = provider()
            if isinstance(external, str) and external:
                return external

        return None

    def get_fit_statistics(self) -> dict[str, float]:
        """Get fit statistics for current model.

        Returns:
            Dictionary with fit statistics
        """
        component = self.optimize_component
        if component is None:
            msg = "Optimize component is required before reading fit statistics."
            raise RuntimeError(msg)
        if self.current_project is None:
            msg = "Current project is required before reading fit statistics."
            raise RuntimeError(msg)
        return component.get_fit_statistics()

    def is_fitting(self) -> bool:
        """Check if fitting is currently in progress.

        Returns:
            True if fitting is in progress
        """
        return self._fit_in_progress

    def _get_fitting_wavelength_range(self) -> tuple[float, float] | None:
        """Get wavelength range for current fitting operation.

        Returns:
            Wavelength range tuple or None for full spectrum
        """
        if not self.mode_state_store or self.mode_state_store.current_mode != EditingMode.ANALYSIS:
            return None

        project = self.current_project
        region_id = self._resolve_active_region_id()
        if not project or not region_id:
            return None

        region = project.absorption_regions.get(region_id)
        return OptimizeGroupRangeResolver(project.absorption_lines).resolve(region)

    def _find_component_by_id(self, component_id: str) -> ModelComponent | None:
        """Find a component by its ID.

        Args:
            component_id: Component identifier

        Returns:
            Component or None if not found
        """
        if not self.current_project or not self.current_project.model:
            return None

        for component in self.current_project.model.components:
            if component.id == component_id:
                return component
        return None

    def _find_line_for_component(self, component_id: str) -> AbsorptionLine | None:
        """Find the absorption line that contains the given component.

        Args:
            component_id: Component identifier

        Returns:
            AbsorptionLine or None if not found
        """
        if not self.current_project:
            return None

        # Search through all lines for the component
        for line in self.current_project.absorption_lines.values():
            if component_id in line.model_ids:
                return line

        return None

    def _collect_line_constraints(self, target_component_ids: set[str]) -> list[LineConstraints]:
        """Collect line constraints for target components.

        Args:
            target_component_ids: Set of component IDs to collect constraints for

        Returns:
            List of LineConstraints objects
        """
        if not self.current_project:
            return []

        constraints: list[LineConstraints] = []

        for component_id in target_component_ids:
            # Find the component
            component = self._find_component_by_id(component_id)
            if not isinstance(component, AbsorberComponent):
                continue

            # Find the line that contains this component
            line = self._find_line_for_component(component_id)
            if not line:
                logger.debug("No line found for component %s, using default bounds", component_id)
                continue

            # Create line constraint
            constraint = LineConstraints(
                component_id=component_id,
                line_id=line.line_id,
                rest_wavelength=component.wavelength,
                lambda_range=line.lambda_range,
            )
            constraints.append(constraint)

            logger.debug(
                "Added constraint for %s: line %s, λ_rest=%.2f, λ_range=%s",
                component.name,
                line.line_id,
                component.wavelength,
                line.lambda_range,
            )

        return constraints
