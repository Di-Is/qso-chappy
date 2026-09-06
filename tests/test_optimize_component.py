from __future__ import annotations

import dataclasses
from collections.abc import Callable
from types import SimpleNamespace

import numpy as np
import pytest
from numpy.typing import NDArray

from chappy.core.components.absorber import AbsorberComponent
from chappy.core.change_set import ChangeSet
from chappy.core.components.optimize import (
    FitCancellationToken,
    FitCancelledError,
    FitOutcome,
    OptimizeComponent,
    LineConstraints,
    classify_fit_outcome,
)
import chappy.core.components.optimize as optimize_module
from chappy.core.components.tie_set import ParameterTieSet
from chappy.core.masking import MaskDefinition
from chappy.core.spectrum import Spectrum
from chappy.core.spectrum_model import SpectrumModel


def _build_flat_spectrum(wavelength: NDArray[np.float64]) -> Spectrum:
    """Build a normalized spectrum on the supplied wavelength grid."""
    flux = np.ones_like(wavelength)
    error = np.full_like(wavelength, 0.1)
    return Spectrum(wavelength=wavelength, flux=flux, error=error, header={})


def _build_observed_spectrum() -> Spectrum:
    """Build a small deterministic spectrum for metadata-oriented fit checks."""
    return _build_flat_spectrum(np.linspace(5000.0, 5005.0, 10))


def _fix_parameters(component: AbsorberComponent, free_parameter: str) -> None:
    """Fix all component parameters except one requested fitting parameter."""
    for parameter_name, parameter in component.parameters.items():
        parameter.fixed = parameter_name != free_parameter


def _build_absorber_model(
    *,
    observed_absorber: AbsorberComponent,
    fitting_absorber: AbsorberComponent,
    wavelength: NDArray[np.float64],
    free_parameter: str,
    error_value: float = 0.02,
) -> SpectrumModel:
    """Build a model whose observed spectrum comes from a known absorber."""
    observed_flux = observed_absorber.calculate(wavelength)
    observed_spectrum = Spectrum(
        wavelength=wavelength,
        flux=observed_flux,
        error=np.full_like(wavelength, error_value),
        header={},
    )
    _fix_parameters(fitting_absorber, free_parameter)

    model = SpectrumModel()
    model.set_observed_spectrum(observed_spectrum)
    model.add_component(fitting_absorber)
    return model


def test_fit_model_updates_duplicate_named_components_independently() -> None:
    """Fit updates each duplicate-named component through the model result."""
    wavelength = np.linspace(4998.0, 5016.0, 160)
    absorber_a_truth = AbsorberComponent(
        name="Mg II 2796", wavelength=5000.0, column_density=12.8, b_parameter=8.0, redshift=0.0
    )
    absorber_b_truth = AbsorberComponent(
        name="Mg II 2796", wavelength=5014.0, column_density=13.0, b_parameter=9.0, redshift=0.0
    )
    observed_flux = absorber_a_truth.calculate(wavelength) * absorber_b_truth.calculate(wavelength)
    observed_spectrum = Spectrum(
        wavelength=wavelength, flux=observed_flux, error=np.full_like(wavelength, 0.02), header={}
    )

    absorber_a = AbsorberComponent(
        name="Mg II 2796", wavelength=5000.0, column_density=12.0, b_parameter=8.0, redshift=0.0
    )
    absorber_b = AbsorberComponent(
        name="Mg II 2796", wavelength=5014.0, column_density=12.0, b_parameter=9.0, redshift=0.0
    )
    _fix_parameters(absorber_a, "column_density")
    _fix_parameters(absorber_b, "column_density")

    model = SpectrumModel()
    model.set_observed_spectrum(observed_spectrum)
    model.add_component(absorber_a)
    model.add_component(absorber_b)

    result = OptimizeComponent(max_function_evaluations=80).fit_model(model)

    assert result.success is True
    assert result.n_parameters == 2
    assert absorber_a.get_parameter_value("column_density") == pytest.approx(12.8, abs=0.08)
    assert absorber_b.get_parameter_value("column_density") == pytest.approx(13.0, abs=0.08)


def test_fit_model_assigns_parameter_errors_to_fitted_parameter() -> None:
    """A successful fit stores finite uncertainty on the fitted parameter."""
    wavelength = np.linspace(4996.0, 5004.0, 120)
    truth = AbsorberComponent(
        wavelength=5000.0, column_density=12.6, b_parameter=8.0, redshift=0.0
    )
    fitted = AbsorberComponent(
        wavelength=5000.0, column_density=12.1, b_parameter=8.0, redshift=0.0
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitted,
        wavelength=wavelength,
        free_parameter="column_density",
    )

    result = OptimizeComponent(max_function_evaluations=80).fit_model(model)

    fitted_error = fitted.parameters["column_density"].error
    assert result.success is True
    assert fitted_error > 0.0
    assert np.isfinite(fitted_error)


def test_fit_model_records_group_degrees_of_freedom() -> None:
    """Fit results expose data point and degree-of-freedom counts."""
    model = SpectrumModel()
    model.set_observed_spectrum(_build_observed_spectrum())
    absorber = AbsorberComponent()
    _fix_parameters(absorber, "column_density")
    model.add_component(absorber)

    result = OptimizeComponent(max_function_evaluations=5).fit_model(model)

    expected_points = len(model.observed_spectrum.flux)
    expected_dof = expected_points - 1
    assert result.data_points == expected_points
    assert result.degrees_of_freedom == expected_dof
    assert result.reduced_chi_squared == pytest.approx(result.chi_squared / expected_dof)


def test_fit_model_respects_mask_group() -> None:
    """Only masks for the requested group reduce the fitted data points."""
    model = SpectrumModel()
    spectrum = _build_observed_spectrum()
    model.set_observed_spectrum(spectrum)

    absorber = AbsorberComponent()
    _fix_parameters(absorber, "column_density")
    model.add_component(absorber)

    group_mask = MaskDefinition.from_range(5001.0, 5001.5).with_group_id("group_a")
    other_group_mask = MaskDefinition.from_range(5002.0, 5002.5).with_group_id("group_b")
    model.mask_definitions = [group_mask, other_group_mask]

    result = OptimizeComponent(max_function_evaluations=20).fit_model(
        model, mask_group_id="group_a"
    )

    wavelength = spectrum.wavelength
    expected_points = int(np.count_nonzero((wavelength < 5001.0) | (wavelength > 5001.5)))
    assert result.success is True
    assert result.data_points == expected_points
    assert result.degrees_of_freedom == expected_points - 1


def test_fit_model_propagates_optimizer_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected optimizer failures should not become failed fit results."""
    model = SpectrumModel()
    model.set_observed_spectrum(_build_observed_spectrum())
    absorber = AbsorberComponent()
    _fix_parameters(absorber, "column_density")
    model.add_component(absorber)

    def fail_least_squares(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("optimizer backend unavailable")

    monkeypatch.setattr(optimize_module, "least_squares", fail_least_squares)

    with pytest.raises(RuntimeError, match="optimizer backend unavailable"):
        OptimizeComponent(max_function_evaluations=5).fit_model(model)


def test_backend_failure_after_candidate_evaluation_preserves_complete_live_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend exception after residual evaluation must not leak candidate state."""
    model = SpectrumModel()
    model.set_observed_spectrum(_build_observed_spectrum())
    first = AbsorberComponent(component_id="first", column_density=14.0)
    second = AbsorberComponent(component_id="second", column_density=14.0)
    for component in (first, second):
        _fix_parameters(component, "column_density")
    tie_set = ParameterTieSet("shared-column", mask=frozenset({"column_density"}))
    tie_set.add_component(first)
    tie_set.add_component(second)
    model.add_component(first)
    model.add_component(second)
    model.add_tie_set(tie_set)
    model.update_model()
    derived_before = model.snapshot_derived_state_for_transaction()
    binding_before = first.parameters["column_density"]
    optimizer = OptimizeComponent(max_function_evaluations=5)
    optimizer.last_result = {"sentinel": True}
    optimizer.fit_history = [{"sentinel": True}]
    notifications: list[ChangeSet] = []
    model.events.subscribe(notifications.append)

    def fail_after_residual(
        residual: Callable[[NDArray[np.float64]], NDArray[np.float64]],
        initial: NDArray[np.float64],
        **_kwargs: object,
    ) -> object:
        residual(initial + 0.25)
        raise RuntimeError("optimizer backend unavailable")

    monkeypatch.setattr(optimize_module, "least_squares", fail_after_residual)

    with pytest.raises(RuntimeError, match="optimizer backend unavailable"):
        optimizer.fit_model(model)

    assert first.parameters["column_density"] is binding_before
    assert second.parameters["column_density"] is binding_before
    assert binding_before.value == pytest.approx(14.0)
    assert binding_before.error == 0.0
    assert tuple(model.iter_tie_sets()) == (tie_set,)
    derived_after = model.snapshot_derived_state_for_transaction()
    assert derived_after.model_valid == derived_before.model_valid
    np.testing.assert_array_equal(derived_after.model_flux, derived_before.model_flux)
    np.testing.assert_array_equal(derived_after.residuals, derived_before.residuals)
    np.testing.assert_array_equal(derived_after.raw_model_flux, derived_before.raw_model_flux)
    assert optimizer.last_result == {"sentinel": True}
    assert optimizer.fit_history == [{"sentinel": True}]
    assert notifications == []


def test_cooperative_cancel_after_candidate_evaluation_preserves_live_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation at a residual boundary must leave parameters and cache untouched."""
    model = SpectrumModel()
    model.set_observed_spectrum(_build_observed_spectrum())
    absorber = AbsorberComponent(column_density=14.0)
    _fix_parameters(absorber, "column_density")
    model.add_component(absorber)
    model.update_model()
    derived_before = model.snapshot_derived_state_for_transaction()
    token = FitCancellationToken()
    optimizer = OptimizeComponent(max_function_evaluations=5)

    def cancel_after_residual(
        residual: Callable[[NDArray[np.float64]], NDArray[np.float64]],
        initial: NDArray[np.float64],
        **_kwargs: object,
    ) -> object:
        residual(initial + 0.25)
        token.cancel()
        residual(initial + 0.5)
        return SimpleNamespace()

    monkeypatch.setattr(optimize_module, "least_squares", cancel_after_residual)

    with pytest.raises(FitCancelledError, match="Fit cancelled"):
        optimizer.fit_model(model, cancellation=token)

    assert absorber.parameters["column_density"].value == pytest.approx(14.0)
    derived_after = model.snapshot_derived_state_for_transaction()
    assert derived_after.model_valid == derived_before.model_valid
    np.testing.assert_array_equal(derived_after.model_flux, derived_before.model_flux)
    np.testing.assert_array_equal(derived_after.residuals, derived_before.residuals)
    np.testing.assert_array_equal(derived_after.raw_model_flux, derived_before.raw_model_flux)
    assert optimizer.last_result is None
    assert optimizer.fit_history == []


def test_successful_fit_is_not_rejected_by_failing_postcommit_observer() -> None:
    """Post-commit observer failures must not undo a successful scientific fit."""
    wavelength = np.linspace(4996.0, 5004.0, 120)
    truth = AbsorberComponent(
        wavelength=5000.0, column_density=12.6, b_parameter=8.0, redshift=0.0
    )
    fitted = AbsorberComponent(
        wavelength=5000.0, column_density=12.1, b_parameter=8.0, redshift=0.0
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitted,
        wavelength=wavelength,
        free_parameter="column_density",
    )
    notifications: list[ChangeSet] = []

    def failing_observer(change_set: ChangeSet) -> None:
        notifications.append(change_set)
        raise RuntimeError("observer unavailable")

    model.events.subscribe(failing_observer)

    result = OptimizeComponent(max_function_evaluations=80).fit_model(model)

    assert result.success is True
    assert fitted.parameters["column_density"].value == pytest.approx(12.6, abs=0.08)
    assert len(notifications) == 1


def test_get_free_parameters_deduplicates_partial_tie_mask() -> None:
    """A redshift-only tie set shares z once while column density stays per-ion."""
    model = SpectrumModel()
    first = AbsorberComponent(component_id="first", redshift=1.0, column_density=13.0)
    second = AbsorberComponent(component_id="second", redshift=1.0, column_density=14.0)
    for component in (first, second):
        component.parameters["b_parameter"].fixed = True
        component.parameters["covering_factor"].fixed = True
    tie_set = ParameterTieSet("shared-z", mask=frozenset({"redshift"}))
    tie_set.add_component(first)
    tie_set.add_component(second)
    model.add_component(first)
    model.add_component(second)

    free_params = OptimizeComponent()._get_free_parameters(model)

    redshift_entries = [entry for entry in free_params if entry[1] == "redshift"]
    column_density_entries = [entry for entry in free_params if entry[1] == "column_density"]
    assert len(redshift_entries) == 1
    assert len(column_density_entries) == 2


def test_get_free_parameters_deduplicates_redshift_and_b_tie_mask() -> None:
    """A redshift-and-b tie set shares z and b once while column density stays per-ion."""
    model = SpectrumModel()
    first = AbsorberComponent(
        component_id="first", redshift=1.0, b_parameter=10.0, column_density=13.0
    )
    second = AbsorberComponent(
        component_id="second", redshift=1.0, b_parameter=10.0, column_density=14.0
    )
    for component in (first, second):
        component.parameters["covering_factor"].fixed = True
    tie_set = ParameterTieSet("shared-z-b", mask=frozenset({"redshift", "b_parameter"}))
    tie_set.add_component(first)
    tie_set.add_component(second)
    model.add_component(first)
    model.add_component(second)

    free_params = OptimizeComponent()._get_free_parameters(model)

    redshift_entries = [entry for entry in free_params if entry[1] == "redshift"]
    b_parameter_entries = [entry for entry in free_params if entry[1] == "b_parameter"]
    column_density_entries = [entry for entry in free_params if entry[1] == "column_density"]
    assert len(redshift_entries) == 1
    assert len(b_parameter_entries) == 1
    assert len(column_density_entries) == 2


def test_get_free_parameters_deduplicates_nested_redshift_tie_mask() -> None:
    """Nested redshift sharing has one z, inner logN, and per-unit b parameters."""
    model = SpectrumModel()
    multiplet_first = AbsorberComponent(component_id="multiplet-first", redshift=1.0)
    multiplet_second = AbsorberComponent(component_id="multiplet-second", redshift=1.0)
    direct = AbsorberComponent(component_id="direct", redshift=1.0)
    for component in (multiplet_first, multiplet_second, direct):
        component.parameters["covering_factor"].fixed = True
    inner = ParameterTieSet("inner")
    inner.add_component(multiplet_first)
    inner.add_component(multiplet_second)
    outer = ParameterTieSet("outer", mask=frozenset({"redshift"}), origin="user")
    outer.add_component(direct)
    outer.attach_tie_set(inner)
    for component in (multiplet_first, multiplet_second, direct):
        model.add_component(component)

    free_params = OptimizeComponent()._get_free_parameters(model)

    redshift_entries = [entry for entry in free_params if entry[1] == "redshift"]
    column_density_entries = [entry for entry in free_params if entry[1] == "column_density"]
    b_parameter_entries = [entry for entry in free_params if entry[1] == "b_parameter"]
    assert len(redshift_entries) == 1
    assert len(column_density_entries) == 2
    assert len(b_parameter_entries) == 2


def test_get_free_parameters_deduplicates_nested_redshift_and_b_tie_mask() -> None:
    """Nested redshift-and-b sharing has one z, one b, and per-unit logN."""
    model = SpectrumModel()
    multiplet_first = AbsorberComponent(component_id="multiplet-first", redshift=1.0)
    multiplet_second = AbsorberComponent(component_id="multiplet-second", redshift=1.0)
    direct = AbsorberComponent(component_id="direct", redshift=1.0)
    for component in (multiplet_first, multiplet_second, direct):
        component.parameters["covering_factor"].fixed = True
    inner = ParameterTieSet("inner")
    inner.add_component(multiplet_first)
    inner.add_component(multiplet_second)
    outer = ParameterTieSet("outer", mask=frozenset({"redshift", "b_parameter"}), origin="user")
    outer.add_component(direct)
    outer.attach_tie_set(inner)
    for component in (multiplet_first, multiplet_second, direct):
        model.add_component(component)

    free_params = OptimizeComponent()._get_free_parameters(model)

    redshift_entries = [entry for entry in free_params if entry[1] == "redshift"]
    b_parameter_entries = [entry for entry in free_params if entry[1] == "b_parameter"]
    column_density_entries = [entry for entry in free_params if entry[1] == "column_density"]
    assert len(redshift_entries) == 1
    assert len(b_parameter_entries) == 1
    assert len(column_density_entries) == 2


def test_update_model_parameters_propagates_covering_factor_for_full_mask_tie_set() -> None:
    """Full-mask tie sets should propagate covering_factor writes to every member."""
    model = SpectrumModel()
    first = AbsorberComponent(component_id="first")
    second = AbsorberComponent(component_id="second")
    tie_set = ParameterTieSet("full-share")
    tie_set.add_component(first)
    tie_set.add_component(second)
    model.add_component(first)
    model.add_component(second)
    for component in (first, second):
        for name, param in component.parameters.items():
            param.fixed = name != "covering_factor"

    optimizer = OptimizeComponent()
    free_params = optimizer._get_free_parameters(model)
    assert len(free_params) == 1

    optimizer._update_model_parameters(free_params, np.array([0.42]))

    assert first.get_parameter_value("covering_factor") == pytest.approx(0.42)
    assert second.get_parameter_value("covering_factor") == pytest.approx(0.42)


def test_line_constraints_calculate_z_bounds() -> None:
    """Line constraints calculate redshift bounds from wavelength span."""
    constraints = LineConstraints(
        component_id="test_comp",
        line_id="test_line",
        rest_wavelength=1215.67,
        lambda_range=(4500.0, 4600.0),
    )

    z_min, z_max = constraints.calculate_z_bounds()

    assert z_min == pytest.approx(4500.0 / 1215.67 - 1.0)
    assert z_max == pytest.approx(4600.0 / 1215.67 - 1.0)


def test_line_constraints_raises_on_invalid_wavelength() -> None:
    """Line constraints reject invalid rest wavelength values."""
    constraints = LineConstraints(
        component_id="test_comp",
        line_id="test_line",
        rest_wavelength=-100.0,
        lambda_range=(4500.0, 4600.0),
    )

    with pytest.raises(ValueError, match="Invalid rest wavelength"):
        constraints.calculate_z_bounds()


def test_line_constraints_raises_on_none_range() -> None:
    """Line constraints reject missing wavelength ranges."""
    constraints = LineConstraints(
        component_id="test_comp", line_id="test_line", rest_wavelength=1215.67, lambda_range=None
    )

    with pytest.raises(ValueError, match="No wavelength range"):
        constraints.calculate_z_bounds()


def test_fit_model_applies_line_constraints_to_redshift() -> None:
    """Constrained redshift fitting keeps the component inside the line span."""
    rest_wavelength = 1215.67
    target_redshift = 2.742
    wavelength = np.linspace(4500.0, 4600.0, 180)
    truth = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.0, b_parameter=25.0, redshift=target_redshift
    )
    fitted = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.0, b_parameter=25.0, redshift=2.72
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitted,
        wavelength=wavelength,
        free_parameter="redshift",
        error_value=0.03,
    )
    constraints = [
        LineConstraints(
            component_id=fitted.id,
            line_id="lya_line",
            rest_wavelength=rest_wavelength,
            lambda_range=(4500.0, 4600.0),
        )
    ]

    result = OptimizeComponent(max_function_evaluations=120).fit_model(
        model, line_constraints=constraints
    )

    z_min = 4500.0 / rest_wavelength - 1.0
    z_max = 4600.0 / rest_wavelength - 1.0
    fitted_redshift = fitted.get_parameter_value("redshift")
    assert result.success is True
    assert z_min <= fitted_redshift <= z_max


def test_fit_model_uses_default_redshift_bounds_without_constraints() -> None:
    """Unconstrained redshift fitting can fit a line outside a constrained span."""
    rest_wavelength = 1215.67
    target_redshift = 2.64
    wavelength = np.linspace(4410.0, 4440.0, 140)
    truth = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.0, b_parameter=20.0, redshift=target_redshift
    )
    fitted = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.0, b_parameter=20.0, redshift=2.65
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitted,
        wavelength=wavelength,
        free_parameter="redshift",
        error_value=0.03,
    )

    result = OptimizeComponent(max_function_evaluations=120).fit_model(model)

    constrained_min = 4500.0 / rest_wavelength - 1.0
    fitted_redshift = fitted.get_parameter_value("redshift")
    assert result.success is True
    assert fitted_redshift < constrained_min


def test_fit_model_keeps_non_redshift_parameters_with_line_constraints() -> None:
    """Line constraints do not prevent fitting non-redshift parameters."""
    rest_wavelength = 1215.67
    wavelength = np.linspace(4500.0, 4600.0, 180)
    redshift = 4505.0 / rest_wavelength - 1.0
    truth = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.2, b_parameter=25.0, redshift=redshift
    )
    fitted = AbsorberComponent(
        wavelength=rest_wavelength, column_density=12.5, b_parameter=25.0, redshift=redshift
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitted,
        wavelength=wavelength,
        free_parameter="column_density",
        error_value=0.03,
    )
    constraints = [
        LineConstraints(
            component_id=fitted.id,
            line_id="lya_line",
            rest_wavelength=rest_wavelength,
            lambda_range=(4500.0, 4600.0),
        )
    ]

    result = OptimizeComponent(max_function_evaluations=120).fit_model(
        model, line_constraints=constraints
    )

    assert result.success is True
    assert fitted.get_parameter_value("column_density") == pytest.approx(13.2, abs=0.08)


def test_fit_model_rejects_invalid_line_constraint() -> None:
    """Invalid line constraints should not fall back to parameter bounds."""
    rest_wavelength = 1215.67
    target_redshift = 2.64
    wavelength = np.linspace(4410.0, 4440.0, 140)
    truth = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.0, b_parameter=20.0, redshift=target_redshift
    )
    fitted = AbsorberComponent(
        wavelength=rest_wavelength, column_density=13.0, b_parameter=20.0, redshift=2.65
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitted,
        wavelength=wavelength,
        free_parameter="redshift",
        error_value=0.03,
    )
    constraints = [
        LineConstraints(
            component_id=fitted.id,
            line_id="broken_line",
            rest_wavelength=rest_wavelength,
            lambda_range=None,
        )
    ]

    with pytest.raises(ValueError, match="No wavelength range"):
        OptimizeComponent(max_function_evaluations=120).fit_model(
            model, line_constraints=constraints
        )


def test_fit_model_accepts_multiple_line_constraints() -> None:
    """Multiple line constraints can be supplied to one fit call."""
    rest_wavelength = 1215.67
    target_redshift = 2.742
    wavelength = np.linspace(4500.0, 4600.0, 180)
    constrained_truth = AbsorberComponent(
        wavelength=rest_wavelength,
        column_density=13.0,
        b_parameter=25.0,
        redshift=target_redshift,
        component_id="component-a",
    )
    free_truth = AbsorberComponent(
        wavelength=1302.17,
        column_density=10.0,
        b_parameter=25.0,
        redshift=2.48,
        component_id="component-b",
    )
    observed_flux = constrained_truth.calculate(wavelength) * free_truth.calculate(wavelength)

    constrained_fit = AbsorberComponent(
        wavelength=rest_wavelength,
        column_density=13.0,
        b_parameter=25.0,
        redshift=2.72,
        component_id="component-a",
    )
    free_fit = AbsorberComponent(
        wavelength=1302.17,
        column_density=10.0,
        b_parameter=25.0,
        redshift=2.48,
        component_id="component-b",
    )
    _fix_parameters(constrained_fit, "redshift")
    _fix_parameters(free_fit, "redshift")

    model = SpectrumModel()
    model.set_observed_spectrum(
        Spectrum(
            wavelength=wavelength,
            flux=observed_flux,
            error=np.full_like(wavelength, 0.03),
            header={},
        )
    )
    model.add_component(constrained_fit)
    model.add_component(free_fit)
    constraints = [
        LineConstraints("component-a", "line-a", rest_wavelength, (4500.0, 4600.0)),
        LineConstraints("component-b", "line-b", 1302.17, (4500.0, 4600.0)),
    ]

    result = OptimizeComponent(max_function_evaluations=120).fit_model(
        model, target_component_ids={constrained_fit.id}, line_constraints=constraints
    )

    z_min = 4500.0 / rest_wavelength - 1.0
    z_max = 4600.0 / rest_wavelength - 1.0
    fitted_redshift = constrained_fit.get_parameter_value("redshift")
    assert result.success is True
    assert result.n_parameters == 1
    assert z_min <= fitted_redshift <= z_max


def _classify(**overrides: object) -> FitOutcome:
    """Classify with a converged, improved, well-constrained baseline case."""
    kwargs: dict[str, object] = {
        "status": 2,
        "chi_squared": 1.0,
        "initial_chi_squared": 100.0,
        "param_errors": np.array([0.1, 0.1]),
        "best_params": np.array([5.0, 5.0]),
        "lower_bounds": np.array([0.0, 0.0]),
        "upper_bounds": np.array([10.0, 10.0]),
        "n_free_params": 2,
    }
    kwargs.update(overrides)
    return classify_fit_outcome(**kwargs)  # type: ignore[arg-type]


def test_classify_converged() -> None:
    """A converged, improved fit with reliable errors is CONVERGED."""
    assert _classify() is FitOutcome.CONVERGED


def test_classify_no_free_params() -> None:
    """Zero free parameters classify as NO_FREE_PARAMS."""
    assert _classify(n_free_params=0) is FitOutcome.NO_FREE_PARAMS


def test_classify_numerical() -> None:
    """Improper input status or non-finite chi-squared classify as NUMERICAL."""
    assert _classify(status=-1) is FitOutcome.NUMERICAL
    assert _classify(chi_squared=np.inf) is FitOutcome.NUMERICAL


def test_classify_budget_stopped_good() -> None:
    """max_nfev with meaningful improvement is BUDGET_STOPPED_GOOD (applied)."""
    outcome = _classify(status=0)
    assert outcome is FitOutcome.BUDGET_STOPPED_GOOD
    assert outcome.applies is True


def test_classify_budget_stopped_stuck() -> None:
    """max_nfev without improvement is BUDGET_STOPPED_STUCK (not applied)."""
    outcome = _classify(status=0, initial_chi_squared=1.0)
    assert outcome is FitOutcome.BUDGET_STOPPED_STUCK
    assert outcome.applies is False


def test_classify_degenerate() -> None:
    """Unusable errors with no improvement classify as DEGENERATE."""
    assert _classify(param_errors=None, initial_chi_squared=1.0) is FitOutcome.DEGENERATE


def test_classify_boundary() -> None:
    """A parameter resting on its bound classifies as BOUNDARY."""
    assert _classify(best_params=np.array([0.0, 5.0])) is FitOutcome.BOUNDARY


def test_classify_converged_uncertain() -> None:
    """Improvement with unusable errors classifies as CONVERGED_UNCERTAIN."""
    assert _classify(param_errors=np.array([np.nan, 0.1])) is FitOutcome.CONVERGED_UNCERTAIN


def test_outcome_applies_mapping() -> None:
    """Exactly the four applied codes commit their result."""
    applied = {
        FitOutcome.CONVERGED,
        FitOutcome.CONVERGED_UNCERTAIN,
        FitOutcome.BUDGET_STOPPED_GOOD,
        FitOutcome.BOUNDARY,
    }
    for outcome in FitOutcome:
        assert outcome.applies is (outcome in applied)


def test_non_applied_result_is_rejected_by_commit() -> None:
    """Commit accepts an applied outcome and rejects a non-applied one."""
    wavelength = np.linspace(4998.0, 5016.0, 160)
    truth = AbsorberComponent(
        name="Mg II 2796", wavelength=5000.0, column_density=12.8, b_parameter=8.0, redshift=0.0
    )
    fitting = AbsorberComponent(
        name="Mg II 2796", wavelength=5000.0, column_density=12.0, b_parameter=8.0, redshift=0.0
    )
    model = _build_absorber_model(
        observed_absorber=truth,
        fitting_absorber=fitting,
        wavelength=wavelength,
        free_parameter="column_density",
    )
    optimizer = OptimizeComponent()
    attempt = optimizer.create_fit_attempt(model)
    result = optimizer.run_fit_attempt(attempt)

    assert result.outcome is FitOutcome.CONVERGED
    assert result.success is True

    stuck = dataclasses.replace(result, outcome=FitOutcome.BUDGET_STOPPED_STUCK, success=False)
    with pytest.raises(ValueError, match="applied"):
        optimizer.commit_fit_attempt_storage(model, attempt, stuck)

    optimizer.commit_fit_attempt_storage(model, attempt, result)


class _StubOptimizeResult:
    """Minimal least_squares result stand-in for warm-restart tests."""

    def __init__(self, *, x, status, nfev, cost, fun, jac=None) -> None:
        self.x = np.asarray(x, dtype=float)
        self.status = status
        self.nfev = nfev
        self.cost = cost
        self.fun = np.asarray(fun, dtype=float)
        self.jac = jac
        self.message = "stub"
        self.optimality = 0.0
        self.success = status > 0


def _run_component_least_squares(monkeypatch, component, statuses, *, costs=None):
    """Drive _run_least_squares with a scripted sequence of round results."""
    costs = costs or [1.0] * len(statuses)
    calls: list = []

    def fake_least_squares(fun, x0, **_kwargs):
        i = len(calls)
        calls.append(x0)
        return _StubOptimizeResult(
            x=np.asarray(x0, dtype=float) + 1.0,
            status=statuses[i],
            nfev=1000,
            cost=costs[i],
            fun=np.zeros(3),
        )

    monkeypatch.setattr(optimize_module, "least_squares", fake_least_squares)
    token = FitCancellationToken()
    result, total = component._run_least_squares(
        lambda x: np.zeros(3), np.zeros(2), np.zeros(2), np.full(2, 10.0), token
    )
    return result, total, calls


def test_warm_restart_continues_until_convergence(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stalled round warm-restarts from its best point until a round converges."""
    component = OptimizeComponent(max_function_evaluations=1000, auto_continue=True)
    _result, total, calls = _run_component_least_squares(
        monkeypatch, component, statuses=[0, 0, 2], costs=[10.0, 5.0, 4.0]
    )
    assert len(calls) == 3
    assert total == 3000
    # each restart begins from the previous round's best point (+1 per round)
    assert calls[1].tolist() == [1.0, 1.0]
    assert calls[2].tolist() == [2.0, 2.0]


def test_warm_restart_disabled_runs_single_round(monkeypatch: pytest.MonkeyPatch) -> None:
    """With auto_continue off, a stalled fit is not restarted."""
    component = OptimizeComponent(max_function_evaluations=1000, auto_continue=False)
    _result, total, calls = _run_component_least_squares(
        monkeypatch, component, statuses=[0, 0, 0]
    )
    assert len(calls) == 1
    assert total == 1000


def test_warm_restart_stops_on_plateau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restarting stops once per-round improvement falls below the plateau threshold."""
    component = OptimizeComponent(max_function_evaluations=1000, auto_continue=True)
    # cost barely moves after round 1 -> plateau stops before the round cap
    _result, total, calls = _run_component_least_squares(
        monkeypatch, component, statuses=[0, 0, 0, 0], costs=[10.0, 5.0, 4.9999, 4.9]
    )
    assert len(calls) == 3
    assert total == 3000
