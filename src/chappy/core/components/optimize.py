"""Optimization component for fitting spectrum models."""

from __future__ import annotations

import dataclasses
import enum
import logging
import math
from copy import deepcopy
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np
from scipy.optimize import least_squares

from chappy.core.change_set import ChangeSet
from chappy.core.events import ComponentChanged, ModelInvalidated, ModelUpdated
from chappy.core.math.instrument_resolution import kernel_half_width_pixels
from chappy.core.optimizer_settings import (
    FIT_BOUNDARY_FRACTION,
    FIT_IMPROVEMENT_MIN,
    FIT_PLATEAU_IMPROVEMENT,
    MAX_OPTIMIZATION_ROUNDS,
)
from chappy.core.redshift_limits import calculate_dynamic_z_limits

from .base import ModelComponent, Parameter

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from numpy.typing import NDArray
    from scipy.optimize import OptimizeResult

    from chappy.core.components.absorber import AbsorberComponent
    from chappy.core.components.tie_set import ParameterTieSet, TieParameterName
    from chappy.core.spectrum_model import SpectrumModel, SpectrumModelDerivedStateSnapshot

    ResidualFunction = Callable[[NDArray[np.float64]], NDArray[np.float64]]

logger = logging.getLogger(__name__)


class FitCancelledError(RuntimeError):
    """Raised inside the optimizer when cooperative cancellation is requested."""


class FitCancellationToken:
    """Thread-safe cooperative cancellation token for one fit attempt."""

    def __init__(self) -> None:
        """Initialize a token in the active state."""
        self._cancelled = Event()

    def cancel(self) -> None:
        """Request cancellation from the owning UI thread."""
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled.is_set()

    def raise_if_cancelled(self) -> None:
        """Abort the current cooperative optimizer boundary when cancelled."""
        if self.is_cancelled:
            msg = "Fit cancelled"
            raise FitCancelledError(msg)


@dataclass(frozen=True, slots=True)
class _ParameterRuntimeSnapshot:
    """Exact runtime state for one retained parameter object."""

    parameter: Parameter
    value: float
    min_value: float
    max_value: float
    fixed: bool
    error: float
    unit: str | None


@dataclass(frozen=True, slots=True)
class _ComponentRuntimeSnapshot:
    """Exact parameter bindings for one retained model component."""

    component: ModelComponent
    parameter_bindings: tuple[tuple[str, Parameter], ...]


@dataclass(frozen=True, slots=True)
class _TieRuntimeSnapshot:
    """Exact nested and shared-parameter bindings for one tie set."""

    tie_set: ParameterTieSet
    components: tuple[AbsorberComponent, ...]
    parent_tie: ParameterTieSet | None
    member_uids: frozenset[str]
    shared_parameters: tuple[tuple[TieParameterName, Parameter], ...]


@dataclass(frozen=True, slots=True)
class _FitModelRuntimeSnapshot:
    """Complete live model state protected by one fit attempt."""

    component_order: tuple[ModelComponent, ...]
    components: tuple[_ComponentRuntimeSnapshot, ...]
    parameters: tuple[_ParameterRuntimeSnapshot, ...]
    ties: tuple[_TieRuntimeSnapshot, ...]
    derived_state: SpectrumModelDerivedStateSnapshot


@dataclass(frozen=True, slots=True)
class FitAttempt:
    """Detached optimizer input plus the live baseline required for commit."""

    source_model_identity: int
    working_model: SpectrumModel
    baseline: _FitModelRuntimeSnapshot
    wavelength_range: tuple[float, float] | None
    weights: NDArray[np.float64] | None
    target_component_ids: frozenset[str] | None
    mask_group_id: str | None
    line_constraints: tuple[LineConstraints, ...]
    free_parameter_keys: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class FitStorageCommit:
    """Notification payload for a successful fit storage commit."""

    changed_component_ids: tuple[str, ...]


@runtime_checkable
class TiedComponent(Protocol):
    """Protocol for components that can be part of a parameter tie set."""

    tie_set: Any


@dataclass(frozen=True)
class LineConstraints:
    """Line-based constraints for absorber components.

    This immutable container holds the information needed to calculate
    dynamic parameter bounds based on absorption line properties.

    Attributes:
        component_id: Unique identifier of the absorber component
        line_id: Unique identifier of the absorption line
        rest_wavelength: Rest wavelength of the absorption line (Angstrom)
        lambda_range: Observed wavelength range of the line (min, max) in Angstrom
    """

    component_id: str
    line_id: str
    rest_wavelength: float
    lambda_range: tuple[float, float] | None

    def calculate_z_bounds(self) -> tuple[float, float]:
        """Calculate redshift bounds from wavelength range.

        Uses the relationship: z = (λ_observed / λ_rest) - 1

        Returns:
            Tuple of (z_min, z_max)

        Raises:
            ValueError: If rest_wavelength is invalid or lambda_range is None
        """
        if self.lambda_range is None:
            msg = f"No wavelength range for line {self.line_id}"
            raise ValueError(msg)

        if self.rest_wavelength <= 0:
            msg = f"Invalid rest wavelength: {self.rest_wavelength}"
            raise ValueError(msg)

        return calculate_dynamic_z_limits(self.rest_wavelength, self.lambda_range)


class FitOutcome(enum.Enum):
    """Closed classification of one optimizer termination."""

    CONVERGED = "converged"
    CONVERGED_UNCERTAIN = "converged_uncertain"
    BUDGET_STOPPED_GOOD = "budget_stopped_good"
    BUDGET_STOPPED_STUCK = "budget_stopped_stuck"
    DEGENERATE = "degenerate"
    BOUNDARY = "boundary"
    NUMERICAL = "numerical"
    NO_FREE_PARAMS = "no_free_params"

    @property
    def applies(self) -> bool:
        """Whether a result with this outcome is committed to the live model."""
        return self in _APPLIED_OUTCOMES


_APPLIED_OUTCOMES = frozenset(
    {
        FitOutcome.CONVERGED,
        FitOutcome.CONVERGED_UNCERTAIN,
        FitOutcome.BUDGET_STOPPED_GOOD,
        FitOutcome.BOUNDARY,
    }
)


def _relative_chi_squared_improvement(initial: float, final: float) -> float:
    """Fractional reduction of chi-squared from the initial guess to the solution."""
    if not math.isfinite(initial) or initial <= 0.0:
        return math.inf if math.isfinite(final) and final < initial else 0.0
    return (initial - final) / initial


def _param_errors_reliable(param_errors: NDArray[np.float64] | None, n_free_params: int) -> bool:
    """Whether a 1-sigma error is finite and positive for every free parameter."""
    if param_errors is None or len(param_errors) < n_free_params:
        return False
    return all(math.isfinite(error) and error > 0.0 for error in param_errors[:n_free_params])


def _solution_at_boundary(
    best_params: NDArray[np.float64],
    lower_bounds: NDArray[np.float64],
    upper_bounds: NDArray[np.float64],
    fraction: float,
) -> bool:
    """Whether any parameter landed within ``fraction`` of its bound range from a bound."""
    for value, low, high in zip(best_params, lower_bounds, upper_bounds, strict=False):
        span = high - low
        if not math.isfinite(span) or span <= 0.0:
            continue
        tolerance = fraction * span
        if (value - low) <= tolerance or (high - value) <= tolerance:
            return True
    return False


def classify_fit_outcome(
    *,
    status: int,
    chi_squared: float,
    initial_chi_squared: float,
    param_errors: NDArray[np.float64] | None,
    best_params: NDArray[np.float64],
    lower_bounds: NDArray[np.float64],
    upper_bounds: NDArray[np.float64],
    n_free_params: int,
) -> FitOutcome:
    """Classify one least-squares termination into a fixed FitOutcome.

    Args:
        status: scipy ``least_squares`` termination status (-1..4; 0 = max_nfev).
        chi_squared: Weighted chi-squared at the solution.
        initial_chi_squared: Weighted chi-squared at the initial guess.
        param_errors: 1-sigma errors for the free parameters, or None if unavailable.
        best_params: Solution vector for the free parameters.
        lower_bounds: Lower bound per free parameter.
        upper_bounds: Upper bound per free parameter.
        n_free_params: Number of free parameters.

    Returns:
        The FitOutcome code for this termination.
    """
    if n_free_params == 0:
        return FitOutcome.NO_FREE_PARAMS
    if status == -1 or not math.isfinite(chi_squared):
        return FitOutcome.NUMERICAL

    improved = (
        _relative_chi_squared_improvement(initial_chi_squared, chi_squared) >= FIT_IMPROVEMENT_MIN
    )
    errors_reliable = _param_errors_reliable(param_errors, n_free_params)

    if not errors_reliable and not improved:
        return FitOutcome.DEGENERATE
    if status == 0:
        return FitOutcome.BUDGET_STOPPED_GOOD if improved else FitOutcome.BUDGET_STOPPED_STUCK
    if _solution_at_boundary(best_params, lower_bounds, upper_bounds, FIT_BOUNDARY_FRACTION):
        return FitOutcome.BOUNDARY
    if not errors_reliable:
        return FitOutcome.CONVERGED_UNCERTAIN
    return FitOutcome.CONVERGED


@dataclass(frozen=True)
class FitResult:
    """Outcome of one spectrum model optimization run."""

    success: bool
    message: str
    algorithm: str
    chi_squared: float
    reduced_chi_squared: float
    n_function_evaluations: int
    n_parameters: int
    best_params: NDArray[np.float64]
    param_errors: NDArray[np.float64] | None
    data_points: int = 0
    degrees_of_freedom: int = 0
    outcome: FitOutcome = FitOutcome.CONVERGED

    def to_legacy_payload(self) -> dict[str, Any]:
        """Convert to the legacy payload shape persisted in project documents."""
        return {
            "success": self.success,
            "message": self.message,
            "outcome": self.outcome.value,
            "algorithm": self.algorithm,
            "chi_squared": self.chi_squared,
            "reduced_chi_squared": self.reduced_chi_squared,
            "n_function_evaluations": self.n_function_evaluations,
            "n_parameters": self.n_parameters,
            "best_params": self.best_params.copy(),
            "param_errors": self.param_errors.copy() if self.param_errors is not None else None,
            "timestamp": np.datetime64("now"),
            "data_points": self.data_points,
            "degrees_of_freedom": self.degrees_of_freedom,
        }

    def to_signal_payload(self) -> dict[str, bool | int | float | str | None]:
        """Convert to the scalar-only payload emitted on the Qt fit-completed signal."""
        return {
            "success": self.success,
            "message": self.message,
            "outcome": self.outcome.value,
            "algorithm": self.algorithm,
            "chi_squared": self.chi_squared,
            "reduced_chi_squared": self.reduced_chi_squared,
            "n_function_evaluations": self.n_function_evaluations,
            "n_parameters": self.n_parameters,
            "data_points": self.data_points,
            "degrees_of_freedom": self.degrees_of_freedom,
        }


class OptimizeComponent(ModelComponent):
    """Component for optimizing model parameters.

    Parameters:
        algorithm: Optimization algorithm to use
        max_function_evaluations: Maximum number of residual evaluations
        tolerance: Convergence tolerance
    """

    def __init__(
        self,
        name: str = "Optimize",
        algorithm: str = "leastsq",
        max_function_evaluations: int = 1000,
        tolerance: float = 1e-10,
        auto_continue: bool = True,
    ) -> None:
        """Initialize optimization component.

        Args:
            name: Component name
            algorithm: Optimization algorithm
            max_function_evaluations: Maximum residual evaluations per round
            tolerance: Convergence tolerance
            auto_continue: Warm-restart a budget-stalled fit from its best point
        """
        super().__init__(name)

        # Hyperparameters for optimization algorithm (not optimized themselves)
        self.algorithm = algorithm
        self.max_function_evaluations = max_function_evaluations
        self.tolerance = tolerance
        self.auto_continue = auto_continue

        # Fitting results
        self.last_result: dict[str, Any] | None = None
        self.fit_history: list[dict[str, Any]] = []

    def calculate(self, wavelength: NDArray[np.float64]) -> NDArray[np.float64]:
        """Optimization component doesn't directly calculate spectrum.

        Returns unity array (no effect on model).
        """
        return np.ones_like(wavelength)

    def fit_model(
        self,
        spectrum_model: SpectrumModel,
        wavelength_range: tuple[float, float] | None = None,
        weights: NDArray[np.float64] | None = None,
        *,
        target_component_ids: set[str] | None = None,
        mask_group_id: str | None = None,
        line_constraints: Sequence[LineConstraints] | None = None,
        cancellation: FitCancellationToken | None = None,
    ) -> FitResult:
        """Fit and atomically commit a spectrum model on the calling thread.

        Args:
            spectrum_model: SpectrumModel instance to fit
            wavelength_range: Optional wavelength range for fitting
            weights: Optional weights for data points
            target_component_ids: Optional set of component identifiers to restrict fitting
            mask_group_id: Mask group identifier to apply during fitting
            line_constraints: Line-based constraints for absorber components.
                              If provided, dynamic bounds will be applied to redshift parameters.
            cancellation: Cooperative cancellation token checked by the optimizer.

        Returns:
            Fit result
        """
        attempt = self.create_fit_attempt(
            spectrum_model,
            wavelength_range=wavelength_range,
            weights=weights,
            target_component_ids=target_component_ids,
            mask_group_id=mask_group_id,
            line_constraints=line_constraints,
        )
        result = self.run_fit_attempt(attempt, cancellation=cancellation)
        if result.success:
            self.commit_fit_attempt(spectrum_model, attempt, result)
        return result

    def create_fit_attempt(
        self,
        spectrum_model: SpectrumModel,
        wavelength_range: tuple[float, float] | None = None,
        weights: NDArray[np.float64] | None = None,
        *,
        target_component_ids: set[str] | None = None,
        mask_group_id: str | None = None,
        line_constraints: Sequence[LineConstraints] | None = None,
    ) -> FitAttempt:
        """Capture the live baseline and build a detached optimizer working model."""
        self._validate_spectrum_model(spectrum_model)
        baseline = self._capture_runtime(spectrum_model)
        working_model = deepcopy(spectrum_model)
        working_free_params = self._get_free_parameters(
            working_model, target_component_ids=target_component_ids
        )
        copied_weights = (
            None if weights is None else np.array(weights, copy=True, dtype=np.float64)
        )
        return FitAttempt(
            source_model_identity=id(spectrum_model),
            working_model=working_model,
            baseline=baseline,
            wavelength_range=wavelength_range,
            weights=copied_weights,
            target_component_ids=(
                None if target_component_ids is None else frozenset(target_component_ids)
            ),
            mask_group_id=mask_group_id,
            line_constraints=tuple(line_constraints or ()),
            free_parameter_keys=tuple(
                (component.id, parameter_name)
                for component, parameter_name, _parameter in working_free_params
            ),
        )

    def run_fit_attempt(
        self, attempt: FitAttempt, *, cancellation: FitCancellationToken | None = None
    ) -> FitResult:
        """Run an optimizer against detached state without mutating the live model."""
        cancellation_token = cancellation or FitCancellationToken()
        cancellation_token.raise_if_cancelled()
        working_model = attempt.working_model
        self._validate_spectrum_model(working_model)

        logger.info("Starting detached fit with %s algorithm", self.algorithm)
        fitting_data = self._prepare_fitting_data(
            working_model, attempt.wavelength_range, attempt.weights, attempt.mask_group_id
        )
        free_params = self._get_free_parameters(
            working_model,
            target_component_ids=(
                None if attempt.target_component_ids is None else set(attempt.target_component_ids)
            ),
        )
        parameter_keys = tuple(
            (component.id, parameter_name) for component, parameter_name, _parameter in free_params
        )
        if parameter_keys != attempt.free_parameter_keys:
            msg = "Detached fit parameter topology changed after attempt capture."
            raise RuntimeError(msg)
        if not free_params:
            logger.warning("No free parameters to fit")
            return self._create_result(
                outcome=FitOutcome.NO_FREE_PARAMS,
                message="No free parameters",
                best_params=np.array([]),
            )

        logger.info(
            "Fitting %d parameters to %d data points", len(free_params), len(fitting_data["flux"])
        )
        constraint_map = self._build_constraint_map(attempt.line_constraints)
        result = self._run_optimization(
            working_model, fitting_data, free_params, constraint_map, cancellation_token
        )
        cancellation_token.raise_if_cancelled()

        data_points = len(fitting_data["flux"])
        degrees_of_freedom = max(data_points - len(free_params), 0)
        reduced_chi_squared = result.reduced_chi_squared
        if degrees_of_freedom > 0 and np.isfinite(result.chi_squared):
            reduced_chi_squared = result.chi_squared / degrees_of_freedom
        result = dataclasses.replace(
            result,
            data_points=data_points,
            degrees_of_freedom=degrees_of_freedom,
            reduced_chi_squared=reduced_chi_squared,
        )
        logger.info(
            "Detached fit completed: success=%s, chi2=%.3f", result.success, result.chi_squared
        )
        return result

    def commit_fit_attempt(
        self, spectrum_model: SpectrumModel, attempt: FitAttempt, result: FitResult
    ) -> None:
        """Apply and publish one successful result on the calling thread."""
        commit = self.commit_fit_attempt_storage(spectrum_model, attempt, result)
        self.finalize_fit_attempt(spectrum_model, attempt, result, commit)

    def commit_fit_attempt_storage(
        self, spectrum_model: SpectrumModel, attempt: FitAttempt, result: FitResult
    ) -> FitStorageCommit:
        """Apply successful fit storage without publishing or changing fit history."""
        if not result.outcome.applies:
            msg = "Only an applied fit result can be committed."
            raise ValueError(msg)
        if id(spectrum_model) != attempt.source_model_identity:
            msg = "Fit result belongs to a different spectrum model."
            raise ValueError(msg)
        self._assert_runtime_unchanged(spectrum_model, attempt.baseline)

        free_params = self._get_free_parameters(
            spectrum_model,
            target_component_ids=(
                None if attempt.target_component_ids is None else set(attempt.target_component_ids)
            ),
        )
        parameter_keys = tuple(
            (component.id, parameter_name) for component, parameter_name, _parameter in free_params
        )
        if parameter_keys != attempt.free_parameter_keys:
            msg = "Live fit parameter topology changed before result commit."
            raise RuntimeError(msg)

        try:
            with spectrum_model.suppress_scientific_notifications():
                self._update_model_parameters(free_params, result.best_params)
                self._assign_parameter_errors(free_params, result.param_errors)
                spectrum_model.invalidate_model()
                spectrum_model.update_model()
        except Exception:
            self._restore_runtime(spectrum_model, attempt.baseline)
            raise

        changed_component_ids = tuple(
            dict.fromkeys(component.id for component, _name, _parameter in free_params)
        )
        return FitStorageCommit(changed_component_ids=changed_component_ids)

    def rollback_fit_attempt(self, spectrum_model: SpectrumModel, attempt: FitAttempt) -> None:
        """Restore the complete live baseline before any post-commit publication."""
        if id(spectrum_model) != attempt.source_model_identity:
            msg = "Fit attempt belongs to a different spectrum model."
            raise ValueError(msg)
        self._restore_runtime(spectrum_model, attempt.baseline)

    def finalize_fit_attempt(
        self,
        spectrum_model: SpectrumModel,
        attempt: FitAttempt,
        result: FitResult,
        commit: FitStorageCommit,
    ) -> None:
        """Record transient optimizer state and isolate post-commit observers."""
        if id(spectrum_model) != attempt.source_model_identity:
            msg = "Fit attempt belongs to a different spectrum model."
            raise ValueError(msg)
        free_params = self._get_free_parameters(
            spectrum_model,
            target_component_ids=(
                None if attempt.target_component_ids is None else set(attempt.target_component_ids)
            ),
        )
        self._record_successful_result(free_params, result)
        spectrum_model.publish_storage_changes(
            ChangeSet.of(
                *(ComponentChanged(component_id=value) for value in commit.changed_component_ids),
                ModelInvalidated(),
                ModelUpdated(),
            )
        )

    def _validate_spectrum_model(self, spectrum_model: SpectrumModel) -> None:
        """Validate that the spectrum model has observed data.

        Args:
            spectrum_model: SpectrumModel to validate

        Raises:
            ValueError: If no observed spectrum is available
        """
        if spectrum_model.observed_spectrum is None:
            msg = "No observed spectrum available for fitting"
            raise ValueError(msg)

    def _capture_runtime(self, spectrum_model: SpectrumModel) -> _FitModelRuntimeSnapshot:
        """Capture exact live parameter, tie, binding, and derived-cache state."""
        component_states = tuple(
            _ComponentRuntimeSnapshot(
                component=component, parameter_bindings=tuple(component.parameters.items())
            )
            for component in spectrum_model.components
        )
        parameters_by_identity = {
            id(parameter): parameter
            for state in component_states
            for _name, parameter in state.parameter_bindings
        }
        tie_sets = tuple(spectrum_model.iter_tie_sets())
        parameters_by_identity.update(
            (id(parameter), parameter)
            for tie_set in tie_sets
            for parameter in tie_set.shared_parameters.values()
        )
        return _FitModelRuntimeSnapshot(
            component_order=tuple(spectrum_model.components),
            components=component_states,
            parameters=tuple(
                _ParameterRuntimeSnapshot(
                    parameter=parameter,
                    value=parameter.value,
                    min_value=parameter.min_val,
                    max_value=parameter.max_val,
                    fixed=parameter.fixed,
                    error=parameter.error,
                    unit=parameter.unit,
                )
                for parameter in parameters_by_identity.values()
            ),
            ties=tuple(
                _TieRuntimeSnapshot(
                    tie_set=tie_set,
                    components=tuple(tie_set.components),
                    parent_tie=tie_set.parent_tie,
                    member_uids=frozenset(tie_set.member_uids),
                    shared_parameters=tuple(tie_set.shared_parameters.items()),
                )
                for tie_set in tie_sets
            ),
            derived_state=spectrum_model.snapshot_derived_state_for_transaction(),
        )

    def _assert_runtime_unchanged(
        self, spectrum_model: SpectrumModel, baseline: _FitModelRuntimeSnapshot
    ) -> None:
        """Reject a result when live scientific state changed during its attempt."""
        current = self._capture_runtime(spectrum_model)
        if tuple(map(id, current.component_order)) != tuple(map(id, baseline.component_order)):
            msg = "Live model component order changed during fit."
            raise RuntimeError(msg)

        current_components = tuple(
            (
                id(state.component),
                tuple((name, id(parameter)) for name, parameter in state.parameter_bindings),
            )
            for state in current.components
        )
        baseline_components = tuple(
            (
                id(state.component),
                tuple((name, id(parameter)) for name, parameter in state.parameter_bindings),
            )
            for state in baseline.components
        )
        if current_components != baseline_components:
            msg = "Live model parameter bindings changed during fit."
            raise RuntimeError(msg)

        def parameter_facts(
            snapshot: _FitModelRuntimeSnapshot,
        ) -> tuple[tuple[int, float, float, float, bool, float, str | None], ...]:
            return tuple(
                (
                    id(state.parameter),
                    state.value,
                    state.min_value,
                    state.max_value,
                    state.fixed,
                    state.error,
                    state.unit,
                )
                for state in snapshot.parameters
            )

        if parameter_facts(current) != parameter_facts(baseline):
            msg = "Live model parameter state changed during fit."
            raise RuntimeError(msg)

        def tie_facts(snapshot: _FitModelRuntimeSnapshot) -> tuple[tuple[object, ...], ...]:
            return tuple(
                (
                    id(state.tie_set),
                    tuple(map(id, state.components)),
                    None if state.parent_tie is None else id(state.parent_tie),
                    state.member_uids,
                    tuple((name, id(parameter)) for name, parameter in state.shared_parameters),
                )
                for state in snapshot.ties
            )

        if tie_facts(current) != tie_facts(baseline):
            msg = "Live model tie topology changed during fit."
            raise RuntimeError(msg)
        if not self._derived_state_equal(current.derived_state, baseline.derived_state):
            msg = "Live model derived cache changed during fit."
            raise RuntimeError(msg)

    @staticmethod
    def _derived_state_equal(
        first: SpectrumModelDerivedStateSnapshot, second: SpectrumModelDerivedStateSnapshot
    ) -> bool:
        """Return whether two derived-cache snapshots are exactly equivalent."""

        def arrays_equal(
            left: NDArray[np.float64] | None, right: NDArray[np.float64] | None
        ) -> bool:
            if left is None or right is None:
                return left is right
            return bool(np.array_equal(left, right, equal_nan=True))

        return (
            first.model_valid == second.model_valid
            and arrays_equal(first.model_flux, second.model_flux)
            and arrays_equal(first.residuals, second.residuals)
            and arrays_equal(first.raw_model_flux, second.raw_model_flux)
        )

    def _restore_runtime(
        self, spectrum_model: SpectrumModel, snapshot: _FitModelRuntimeSnapshot
    ) -> None:
        """Restore exact live state after an interrupted result commit."""
        with spectrum_model.suppress_scientific_notifications(snapshot.component_order):
            spectrum_model.restore_component_order_for_transaction(snapshot.component_order)
            spectrum_model.restore_tie_set_order_for_transaction(
                tuple(state.tie_set for state in snapshot.ties)
            )
            for tie_state in snapshot.ties:
                tie_state.tie_set.components[:] = tie_state.components
                tie_state.tie_set.parent_tie = tie_state.parent_tie
                tie_state.tie_set.member_uids = set(tie_state.member_uids)
                tie_state.tie_set.shared_parameters = dict(tie_state.shared_parameters)
            for component_state in snapshot.components:
                component_state.component.parameters = dict(component_state.parameter_bindings)
            for parameter_state in snapshot.parameters:
                parameter_state.parameter.min_val = parameter_state.min_value
                parameter_state.parameter.max_val = parameter_state.max_value
                parameter_state.parameter.set_value(parameter_state.value)
                parameter_state.parameter.fixed = parameter_state.fixed
                parameter_state.parameter.error = parameter_state.error
                parameter_state.parameter.unit = parameter_state.unit
            spectrum_model.restore_derived_state_for_transaction(snapshot.derived_state)

    def _prepare_fitting_data(
        self,
        spectrum_model: SpectrumModel,
        wavelength_range: tuple[float, float] | None,
        weights: NDArray[np.float64] | None,
        mask_group_id: str | None,
    ) -> dict[str, NDArray[np.float64]]:
        """Prepare data for fitting by applying masks and weights.

        Args:
            spectrum_model: SpectrumModel instance
            wavelength_range: Optional wavelength range for fitting
            weights: Optional weights for data points
            mask_group_id: Mask group identifier to apply during fitting

        Returns:
            Dictionary with wavelength, flux, and weights arrays

        Raises:
            ValueError: If no data points remain after masking
        """
        # Get raw data
        observed_spectrum = spectrum_model.observed_spectrum
        if observed_spectrum is None:
            msg = "observed_spectrum should not be None after validation"
            raise ValueError(msg)
        wavelength = observed_spectrum.wavelength
        observed_flux = observed_spectrum.flux

        # Create data mask
        if mask_group_id is None:
            masked_regions = spectrum_model.mask_ranges()
        else:
            masked_regions = spectrum_model.mask_ranges_for_group(mask_group_id)

        mask = self._create_data_mask(wavelength, wavelength_range, masked_regions)

        # Exclude pixels without valid uncertainty (e.g. UVES SQUAD gap markers
        # with sigma=-1e32, flux=1.0) so they cannot bias the fit.
        if observed_spectrum.error is not None:
            error = observed_spectrum.error
            mask &= np.isfinite(error) & (error > 0)

        if not np.any(mask):
            msg = "No data points available for fitting after masking"
            raise ValueError(msg)

        # Extract masked data
        fit_wavelength = wavelength[mask]
        fit_flux = observed_flux[mask]

        # Setup weights
        fit_weights = self._setup_weights(spectrum_model, mask, weights)

        # Convolution must run on a contiguous grid, not the concatenated fit pixels:
        # split windows (e.g. a doublet) otherwise share one log-lambda grid whose points
        # are wasted across the gap, wrecking the LSF within each window. Convolve on the
        # observed pixels spanning the fit region (gap included) plus an LSF-width margin,
        # then extract the fit pixels.
        selected = np.flatnonzero(mask)
        start, stop = int(selected[0]), int(selected[-1]) + 1
        state = spectrum_model.resolution_state
        if state is not None and state.enabled and state.value > 0:
            pad = kernel_half_width_pixels(wavelength[start:stop], float(state.value)) + 1
        else:
            pad = 0
        lo = max(0, start - pad)
        hi = min(len(wavelength), stop + pad)
        conv_wavelength = wavelength[lo:hi]
        select_index = np.flatnonzero(mask[lo:hi])

        return {
            "wavelength": fit_wavelength,
            "flux": fit_flux,
            "weights": fit_weights,
            "conv_wavelength": conv_wavelength,
            "select_index": select_index.astype(np.int64),
        }

    def _create_data_mask(
        self,
        wavelength: NDArray[np.float64],
        wavelength_range: tuple[float, float] | None,
        masked_regions: list[tuple[float, float]],
    ) -> NDArray[np.bool_]:
        """Create data mask for fitting.

        Args:
            wavelength: Wavelength array
            wavelength_range: Optional wavelength range
            masked_regions: List of masked regions

        Returns:
            Boolean mask array
        """
        # Apply wavelength range if specified
        if wavelength_range:
            mask = (wavelength >= wavelength_range[0]) & (wavelength <= wavelength_range[1])
        else:
            mask = np.ones(len(wavelength), dtype=bool)

        # Apply masks from model
        for min_wave, max_wave in masked_regions:
            mask &= ~((wavelength >= min_wave) & (wavelength <= max_wave))

        return mask

    def _setup_weights(
        self,
        spectrum_model: SpectrumModel,
        mask: NDArray[np.bool_],
        weights: NDArray[np.float64] | None,
    ) -> NDArray[np.float64]:
        """Setup weights for fitting.

        Args:
            spectrum_model: SpectrumModel instance
            mask: Data mask
            weights: Optional provided weights

        Returns:
            Weight array for fitting
        """
        if weights is not None:
            return weights[mask]

        observed_spectrum = spectrum_model.observed_spectrum
        if observed_spectrum is None:
            msg = "observed_spectrum should not be None after validation"
            raise ValueError(msg)

        if observed_spectrum.error is not None:
            return 1.0 / observed_spectrum.error[mask]

        fit_flux = observed_spectrum.flux[mask]
        return np.ones_like(fit_flux)

    def _build_constraint_map(
        self, line_constraints: Sequence[LineConstraints] | None
    ) -> dict[str, LineConstraints]:
        """Build a mapping from component ID to line constraints.

        Args:
            line_constraints: Sequence of line constraints

        Returns:
            Dictionary mapping component_id to LineConstraints
        """
        if not line_constraints:
            return {}
        return {constraint.component_id: constraint for constraint in line_constraints}

    def _calculate_dynamic_bounds(
        self,
        free_params: list[tuple[ModelComponent, str, Parameter]],
        constraint_map: dict[str, LineConstraints],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Calculate dynamic parameter bounds based on line constraints.

        For redshift parameters with associated line constraints, this method
        calculates bounds from the line's wavelength range. For other parameters
        or components without constraints, default bounds from the Parameter object
        are used.

        Args:
            free_params: List of (component, param_name, Parameter) tuples
            constraint_map: Mapping from component_id to LineConstraints

        Returns:
            Tuple of (lower_bounds, upper_bounds) arrays
        """

        def _validate_z_bounds(z_min: float, z_max: float) -> None:
            """Validate calculated redshift bounds.

            Args:
                z_min: Minimum redshift value
                z_max: Maximum redshift value

            Raises:
                ValueError: If bounds are invalid (non-finite or min >= max)
            """
            if not (math.isfinite(z_min) and math.isfinite(z_max)):
                msg = f"Non-finite bounds: z_min={z_min}, z_max={z_max}"
                raise ValueError(msg)
            if z_min >= z_max:
                msg = f"Invalid bounds: z_min={z_min} >= z_max={z_max}"
                raise ValueError(msg)

        lower_bounds = []
        upper_bounds = []

        for component, param_name, param in free_params:
            # Default bounds from parameter
            min_val = param.min_val
            max_val = param.max_val

            # Apply dynamic bounds for redshift parameters with constraints
            if param_name == "redshift" and component.id in constraint_map:
                constraints = constraint_map[component.id]
                z_min, z_max = constraints.calculate_z_bounds()

                # Validate calculated bounds
                _validate_z_bounds(z_min, z_max)

                # Take intersection with parameter bounds (stricter constraint wins)
                min_val = max(param.min_val, z_min)
                max_val = min(param.max_val, z_max)

                # Verify intersection is valid
                if min_val >= max_val:
                    msg = (
                        f"Dynamic bounds [{z_min:.4f}, {z_max:.4f}] are incompatible with "
                        f"parameter bounds [{param.min_val:.4f}, {param.max_val:.4f}] "
                        f"for {component.name}"
                    )
                    raise ValueError(msg)

                logger.debug(
                    "Applied dynamic z bounds for %s: [%.4f, %.4f]",
                    component.name,
                    min_val,
                    max_val,
                )

            lower_bounds.append(min_val)
            upper_bounds.append(max_val)

        return np.array(lower_bounds), np.array(upper_bounds)

    def _run_optimization(
        self,
        spectrum_model: SpectrumModel,
        fitting_data: dict[str, NDArray[np.float64]],
        free_params: list[tuple[ModelComponent, str, Parameter]],
        constraint_map: dict[str, LineConstraints],
        cancellation: FitCancellationToken,
    ) -> FitResult:
        """Run the selected optimization algorithm.

        Args:
            spectrum_model: SpectrumModel instance
            fitting_data: Prepared fitting data
            free_params: Free parameters for fitting
            constraint_map: Line constraints mapping
            cancellation: Cooperative cancellation token.

        Returns:
            Optimization result

        Raises:
            ValueError: If algorithm is unknown
        """
        flux = fitting_data["flux"]
        weights = fitting_data["weights"]
        conv_wavelength = fitting_data["conv_wavelength"]
        select_index = np.asarray(fitting_data["select_index"], dtype=np.int64)

        if self.algorithm == "leastsq":
            return self._fit_least_squares(
                spectrum_model,
                conv_wavelength,
                select_index,
                flux,
                weights,
                free_params,
                constraint_map,
                cancellation,
            )
        msg = f"Unknown optimization algorithm: {self.algorithm}"
        raise ValueError(msg)

    def _record_successful_result(
        self, free_params: list[tuple[ModelComponent, str, Parameter]], result: FitResult
    ) -> None:
        """Store optimizer-local history only after the live commit succeeds."""
        payload = result.to_legacy_payload()
        fit_history = [*self.fit_history, dict(payload)]
        self.last_result = payload
        self.fit_history = fit_history
        self._log_fit_parameters(free_params, result)

    def _get_free_parameters(
        self, spectrum_model: SpectrumModel, *, target_component_ids: set[str] | None = None
    ) -> list[tuple[ModelComponent, str, Parameter]]:
        """Get list of free parameters from all components.

        For components in a parameter tie set, shared parameters are only
        included once to avoid duplicate optimization variables.

        Args:
            spectrum_model: SpectrumModel instance
            target_component_ids: Optional set of component identifiers to include

        Returns:
            List of (component, param_name, Parameter) tuples
        """
        free_params: list[tuple[ModelComponent, str, Parameter]] = []
        processed_shared_params = set()  # Track shared parameters by object id

        for component in spectrum_model.components:
            if not component.enabled:
                continue

            if target_component_ids is not None and component.id not in target_component_ids:
                continue

            # Check if component is part of a parameter tie set
            tie_set = component.tie_set if isinstance(component, TiedComponent) else None

            for param_name, param in component.parameters.items():
                if param.fixed:
                    continue

                # Skip shared parameters that have already been processed
                if tie_set is not None and param_name in tie_set.mask:
                    param_id = id(param)  # Use object id to identify shared parameters
                    if param_id in processed_shared_params:
                        continue
                    processed_shared_params.add(param_id)

                free_params.append((component, param_name, param))

        return free_params

    def _fit_least_squares(
        self,
        spectrum_model: SpectrumModel,
        conv_wavelength: NDArray[np.float64],
        select_index: NDArray[np.int64],
        observed_flux: NDArray[np.float64],
        weights: NDArray[np.float64],
        free_params: list[tuple[ModelComponent, str, Parameter]],
        constraint_map: dict[str, LineConstraints],
        cancellation: FitCancellationToken,
    ) -> FitResult:
        """Fit using least squares optimization.

        Args:
            spectrum_model: Spectrum model
            conv_wavelength: Contiguous grid the model is built/convolved on
            select_index: Indices of the fit pixels within ``conv_wavelength``
            observed_flux: Observed flux array (fit pixels)
            weights: Weight array (fit pixels)
            free_params: Free parameters
            constraint_map: Line constraints mapping
            cancellation: Cooperative cancellation token.

        Returns:
            Fit result
        """
        # Initial parameter values
        initial_values = np.array([param.value for _, _, param in free_params])

        # Calculate dynamic bounds based on line constraints
        lower_bounds, upper_bounds = self._calculate_dynamic_bounds(free_params, constraint_map)

        # Residual function for least_squares
        def residual_func(param_values: NDArray[np.float64]) -> NDArray[np.float64]:
            cancellation.raise_if_cancelled()
            try:
                self._update_model_parameters(free_params, param_values)

                # Build and convolve on the contiguous window, then pick the fit pixels.
                raw_flux = spectrum_model.raw_model_flux_on(conv_wavelength)
                convolved = spectrum_model.convolve_model_flux(
                    conv_wavelength, raw_flux, spectrum_model.raw_model_flux_on
                )
                model_flux = convolved[select_index]

                # Use error-based residuals for consistency with objective function
                errors_for_calc = 1.0 / weights  # Convert weights back to errors
                return (observed_flux - model_flux) / errors_for_calc

            except FitCancelledError:
                raise
            except (ValueError, TypeError, IndexError, ArithmeticError):
                return np.full_like(observed_flux, 1e6)

        # Baseline for the improvement signal used to classify the outcome.
        initial_chi2 = float(np.sum(residual_func(initial_values) ** 2))

        opt_result, total_nfev = self._run_least_squares(
            residual_func, initial_values, lower_bounds, upper_bounds, cancellation
        )
        cancellation.raise_if_cancelled()

        # Calculate final chi-squared
        final_chi2 = np.sum(opt_result.fun**2)

        # Calculate parameter errors from covariance matrix
        param_errors = np.zeros_like(opt_result.x)
        try:
            # least_squares always returns jac attribute, but it can be None
            if opt_result.jac is not None:
                jac = opt_result.jac
                cov = np.linalg.inv(jac.T @ jac)
                param_errors = np.sqrt(np.diag(cov))
        except (ValueError, TypeError, AttributeError, np.linalg.LinAlgError):
            logger.debug("Could not calculate parameter errors")

        outcome = classify_fit_outcome(
            status=int(opt_result.status),
            chi_squared=float(final_chi2),
            initial_chi_squared=initial_chi2,
            param_errors=param_errors,
            best_params=opt_result.x,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            n_free_params=len(free_params),
        )
        return self._create_result(
            outcome=outcome,
            message=opt_result.message,
            best_params=opt_result.x,
            chi_squared=final_chi2,
            n_function_evaluations=total_nfev,
            param_errors=param_errors,
        )

    def _run_least_squares(
        self,
        residual_func: ResidualFunction,
        initial_values: NDArray[np.float64],
        lower_bounds: NDArray[np.float64],
        upper_bounds: NDArray[np.float64],
        cancellation: FitCancellationToken,
    ) -> tuple[OptimizeResult, int]:
        """Run least squares, warm-restarting a budget-stalled fit from its best point.

        Restarting resets the trust-region radius, which lets a fit whose steps have
        collapsed (max_nfev with a large gradient) resume progress. Returns the final
        optimizer result and the total residual evaluations across rounds.
        """
        current = initial_values
        total_nfev = 0
        previous_cost: float | None = None
        rounds = 0
        while True:
            cancellation.raise_if_cancelled()
            opt_result = least_squares(
                residual_func,
                current,
                bounds=(lower_bounds, upper_bounds),
                x_scale="jac",
                max_nfev=int(self.max_function_evaluations),
                ftol=self.tolerance,
                xtol=self.tolerance,
            )
            total_nfev += int(opt_result.nfev)
            rounds += 1
            if (
                opt_result.status != 0
                or not self.auto_continue
                or rounds >= MAX_OPTIMIZATION_ROUNDS
            ):
                break
            cost = float(opt_result.cost)
            if (
                previous_cost is not None
                and previous_cost > 0
                and (previous_cost - cost) / previous_cost < FIT_PLATEAU_IMPROVEMENT
            ):
                break
            previous_cost = cost
            current = opt_result.x
        return opt_result, total_nfev

    def _update_model_parameters(  # Complex parameter update logic required for shared/individual params
        self,
        free_params: list[tuple[ModelComponent, str, Parameter]],
        param_values: NDArray[np.float64],
    ) -> None:
        """Update model parameters with new values.

        For shared parameters in a parameter tie set, updates the shared
        parameter directly to avoid multiple redundant updates.

        Args:
            free_params: Free parameter list
            param_values: New parameter values
        """
        updated_shared_params = set()  # Track updated shared parameters by object id

        for i, (component, param_name, param) in enumerate(free_params):
            # Check if this is a shared parameter in a parameter tie set
            tie_set = component.tie_set if isinstance(component, TiedComponent) else None

            if tie_set is not None and param_name in tie_set.mask:
                param_id = id(param)
                if param_id in updated_shared_params:
                    continue  # Skip if already updated
                updated_shared_params.add(param_id)

                # Update shared parameter directly
                new_value = param_values[i]
                # Clip to bounds if necessary
                if new_value < param.min_val or new_value > param.max_val:
                    new_value = np.clip(new_value, param.min_val, param.max_val)
                tie_set.set_shared_parameter(param_name, new_value)
            else:
                # Update individual component parameter
                try:
                    component.set_parameter(param_name, param_values[i])
                except ValueError:
                    # Parameter outside bounds, clip it
                    clipped_value = np.clip(param_values[i], param.min_val, param.max_val)
                    component.set_parameter(param_name, clipped_value)

    def _create_result(  # Result needs all optimization result fields; uses keyword-only args
        self,
        *,
        outcome: FitOutcome,
        message: str,
        best_params: NDArray[np.float64],
        chi_squared: float = np.inf,
        n_function_evaluations: int = 0,
        param_errors: NDArray[np.float64] | None = None,
    ) -> FitResult:
        """Create a standardized fit result.

        Returns:
            Fit result
        """
        return FitResult(
            success=outcome.applies,
            message=message,
            outcome=outcome,
            algorithm=self.algorithm,
            chi_squared=chi_squared,
            reduced_chi_squared=np.inf,
            n_function_evaluations=n_function_evaluations,
            n_parameters=len(best_params),
            best_params=best_params,
            param_errors=param_errors,
        )

    def get_fit_statistics(self) -> dict[str, float]:
        """Get detailed fit statistics.

        Returns:
            Dictionary with fit statistics
        """
        if self.last_result is None:
            return {}

        stats = {
            "chi_squared": self.last_result["chi_squared"],
            "reduced_chi_squared": self.last_result.get("reduced_chi_squared", np.inf),
            "degrees_of_freedom": self.last_result.get("degrees_of_freedom"),
            "n_parameters": self.last_result["n_parameters"],
            "n_function_evaluations": self.last_result["n_function_evaluations"],
        }

        # Add AIC and BIC if possible
        n_data = self.last_result.get("data_points")
        if isinstance(n_data, int | float) and n_data > 0:
            chi2 = self.last_result["chi_squared"]
            k = self.last_result["n_parameters"]

            stats["aic"] = chi2 + 2 * k
            stats["bic"] = chi2 + k * np.log(n_data)

        return stats

    def _log_fit_parameters(
        self, free_params: list[tuple[ModelComponent, str, Parameter]], result: FitResult
    ) -> None:
        """Log fitted parameter values and errors.

        Args:
            free_params: List of fitted parameters
            result: Fit result
        """
        logger.info("=== Fit Results ===")
        logger.info("Algorithm: %s", self.algorithm)
        logger.info("Chi-squared: %.6f", result.chi_squared)
        logger.info("Function evaluations: %d", result.n_function_evaluations)
        logger.info("Parameters fitted:")

        param_errors = result.param_errors
        for i, (component, param_name, param) in enumerate(free_params):
            value = result.best_params[i]
            unit_str = f" {param.unit}" if param.unit else ""

            if param_errors is not None and len(param_errors) > i:
                error = param_errors[i]
                logger.info(
                    "  %s.%s = %.6f ± %.6f%s", component.name, param_name, value, error, unit_str
                )
            else:
                logger.info("  %s.%s = %.6f%s", component.name, param_name, value, unit_str)
        logger.info("==================")

    def _assign_parameter_errors(
        self,
        free_params: list[tuple[ModelComponent, str, Parameter]],
        param_errors: NDArray[np.float64] | None,
    ) -> None:
        """Attach uncertainty estimates to fitted parameters."""
        if param_errors is None or len(param_errors) == 0:
            return

        for index, (_, _, param) in enumerate(free_params):
            if index >= len(param_errors):
                break

            error_value = float(param_errors[index])
            if not math.isfinite(error_value):
                continue
            param.error = abs(error_value)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizeComponent:
        """Create optimize component from dictionary."""
        algorithm = data.get("algorithm", "leastsq")
        name = data.get("name", "Optimize")
        max_function_evaluations = data.get("max_function_evaluations", 1000)
        tolerance = data.get("tolerance", 1e-8)
        auto_continue = data.get("auto_continue", True)

        # Create component with hyperparameters
        component = cls(
            name=name,
            algorithm=algorithm,
            max_function_evaluations=max_function_evaluations,
            tolerance=tolerance,
            auto_continue=auto_continue,
        )

        # Restore fit results
        component.last_result = data.get("last_result")

        # Set enabled state
        component.enabled = data.get("enabled", True)

        return component
