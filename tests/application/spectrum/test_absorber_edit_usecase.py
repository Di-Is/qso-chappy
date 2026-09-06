"""Tests for absorber edit use cases."""

from __future__ import annotations

import contextlib

import numpy as np
import pytest

from chappy.application.spectrum import (
    AbsorberEditContractError,
    AbsorberEditModelStateError,
    AbsorberEditUseCase,
    AbsorberEditValidationError,
    RedshiftConstraintContext,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisRevision
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum


@contextlib.contextmanager
def _atomic_history_scope():
    """Provide a rollback-capable no-op history scope for focused tests."""
    yield


def _project_with_absorber() -> tuple[SpectroscopyProject, AbsorberComponent]:
    """Create a project containing one absorber and an observed spectrum."""
    wavelength = np.linspace(1200.0, 1240.0, 401)
    flux = np.ones_like(wavelength)
    error = np.full_like(wavelength, 0.05)
    project = SpectroscopyProject(name="Absorber Edit UseCase Test")
    project.model.set_observed_spectrum(Spectrum(wavelength=wavelength, flux=flux, error=error))
    absorber = AbsorberComponent(
        name="H I",
        wavelength=1215.67,
        column_density=13.5,
        b_parameter=20.0,
        redshift=2.0,
        component_id="comp-alpha",
    )
    project.model.add_component(absorber)
    return project, absorber


def _add_region(project: SpectroscopyProject, region_id: str) -> None:
    """Add one analysis-capable region whose line starts fresh."""
    line_id = f"line-{region_id}"
    project.absorption_lines[line_id] = AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=1215.67,
        center_z=2.0,
        window_kms=100.0,
        multiplet_label="Ly alpha",
        transition_name="Ly alpha",
        oscillator_strength=0.4,
        gamma_value=1e8,
        region_id=region_id,
        needs_optimization=False,
    )
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=[line_id]
    )


def test_update_parameter_refreshes_model() -> None:
    """A non-redshift edit should update the component and recalculate the model."""
    project, absorber = _project_with_absorber()
    usecase = AbsorberEditUseCase()

    result = usecase.update_parameter(project, absorber.id, "column_density", 14.0)

    assert result is not None
    assert result.component is absorber
    assert result.applied_value == pytest.approx(14.0)
    assert absorber.get_parameter_value("column_density") == pytest.approx(14.0)
    assert project.model.model_spectrum is not None


def test_update_parameter_invalidates_every_analysis_capable_region() -> None:
    """A direct application edit should stale all analysis-capable regions."""
    project, absorber = _project_with_absorber()
    _add_region(project, "region-1")
    _add_region(project, "region-2")

    result = AbsorberEditUseCase().update_parameter(project, absorber.id, "column_density", 14.0)

    assert result is not None
    assert result.impact.changed is True
    assert result.impact.affected_region_ids == ("region-1", "region-2")
    assert all(
        state.current_revision == AnalysisRevision(1) for state in project.region_analysis_states()
    )
    assert all(line.needs_optimization for line in project.absorption_lines.values())


def test_update_parameter_identical_value_is_no_change() -> None:
    """An identical direct application edit should preserve freshness and history."""
    project, absorber = _project_with_absorber()
    _add_region(project, "region-1")
    history_calls = 0

    def record_history() -> None:
        nonlocal history_calls
        history_calls += 1

    result = AbsorberEditUseCase().update_parameter(
        project,
        absorber.id,
        "column_density",
        absorber.parameters["column_density"].value,
        record_history=record_history,
        history_scope=_atomic_history_scope,
    )

    assert result is not None
    assert result.impact.changed is False
    assert history_calls == 0
    assert project.region_analysis_states()[0].current_revision == AnalysisRevision(0)
    assert project.absorption_lines["line-region-1"].needs_optimization is False


def test_update_parameter_history_failure_rolls_back_all_scientific_state() -> None:
    """A failed direct history write should restore value, freshness, and modified time."""
    project, absorber = _project_with_absorber()
    _add_region(project, "region-1")
    modified_before = project.modified

    def fail_history() -> None:
        raise RuntimeError("injected direct absorber history failure")

    with pytest.raises(RuntimeError, match="injected direct absorber history failure"):
        AbsorberEditUseCase().update_parameter(
            project,
            absorber.id,
            "column_density",
            14.0,
            record_history=fail_history,
            history_scope=_atomic_history_scope,
        )

    assert absorber.parameters["column_density"].value == pytest.approx(13.5)
    assert project.region_analysis_states()[0].current_revision == AnalysisRevision(0)
    assert project.absorption_lines["line-region-1"].needs_optimization is False
    assert project.modified == modified_before


def test_update_redshift_clamps_to_supplied_wavelength_range() -> None:
    """Redshift edits should use the supplied line wavelength constraints."""
    project, absorber = _project_with_absorber()
    usecase = AbsorberEditUseCase()

    result = usecase.update_redshift(
        project,
        absorber.id,
        1.5,
        RedshiftConstraintContext(rest_wavelength=1215.67, lambda_range=(3500.0, 4000.0)),
    )

    assert result is not None
    assert result.applied_value == pytest.approx(1.8791, abs=0.001)
    assert absorber.get_parameter_value("redshift") == pytest.approx(1.8791, abs=0.001)


def test_update_redshift_rejects_invalid_rest_wavelength() -> None:
    """Redshift validation should reject invalid rest wavelengths."""
    project, absorber = _project_with_absorber()
    absorber.wavelength = float("nan")
    usecase = AbsorberEditUseCase()

    with pytest.raises(AbsorberEditModelStateError, match="rest_wavelength"):
        usecase.update_redshift(project, absorber.id, 0.01)


def test_update_parameter_returns_none_for_missing_component() -> None:
    """Missing targets should not mutate the model."""
    project, _absorber = _project_with_absorber()
    usecase = AbsorberEditUseCase()

    result = usecase.update_parameter(project, "missing", "column_density", 14.0)

    assert result is None


def test_update_parameter_rejects_unknown_parameter_as_contract_error() -> None:
    """Unknown parameter names should fail fast as caller contract errors."""
    project, absorber = _project_with_absorber()
    usecase = AbsorberEditUseCase()

    with pytest.raises(AbsorberEditContractError, match="Unsupported absorber parameter"):
        usecase.update_parameter(project, absorber.id, "not_a_parameter", 14.0)


def test_update_parameter_reports_out_of_range_value_as_validation_error() -> None:
    """Out-of-range parameter values should be classified as user validation errors."""
    project, absorber = _project_with_absorber()
    usecase = AbsorberEditUseCase()

    with pytest.raises(AbsorberEditValidationError, match="Invalid value"):
        usecase.update_parameter(project, absorber.id, "column_density", 99.0)
