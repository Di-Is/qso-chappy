"""Tests for region-scoped optimizer convergence settings restoration.

Mirrors ``tests/core/test_project_resolution_settings.py``: settings-key parsing and
fallback-to-default live in ``chappy.application.project_mapper``, while
``SpectroscopyProject.set_region_optimizer_settings`` only applies a typed
``OptimizerSettingsState`` to one region.
"""

from __future__ import annotations

from chappy.application.project_mapper import project_from_document, project_to_document
from chappy.core.optimizer_settings import DEFAULT_MAX_FUNCTION_EVALUATIONS, DEFAULT_TOLERANCE
from chappy.core.spectroscopy_project import SpectroscopyProject


def _add_test_line(project: SpectroscopyProject, *, center_z: float = 0.5) -> str:
    line = project.add_absorption_line(
        species="C IV",
        rest_wavelength=1548.195,
        center_z=center_z,
        window_kms=150.0,
        multiplet_label="",
        transition_name="C IV 1548",
        oscillator_strength=0.19,
        gamma_value=2.65e8,
        lambda_range=(1500.0, 1600.0),
    )
    return line.line_id


def test_untouched_region_falls_back_to_defaults() -> None:
    """A region without an explicit override reports the built-in defaults."""
    project = SpectroscopyProject()
    region = project.create_region_with_lines([_add_test_line(project)])

    settings = project.region_optimizer_settings(region.region_id)

    assert settings.max_function_evaluations == DEFAULT_MAX_FUNCTION_EVALUATIONS
    assert settings.tolerance == DEFAULT_TOLERANCE


def test_set_region_optimizer_settings_scopes_to_one_region() -> None:
    """Overriding one region's settings does not affect a sibling region."""
    project = SpectroscopyProject()
    region_a = project.create_region_with_lines([_add_test_line(project, center_z=0.5)])
    region_b = project.create_region_with_lines([_add_test_line(project, center_z=0.6)])

    project.set_region_optimizer_settings(region_a.region_id, 2500, 1e-10)

    settings_a = project.region_optimizer_settings(region_a.region_id)
    settings_b = project.region_optimizer_settings(region_b.region_id)
    assert settings_a.max_function_evaluations == 2500
    assert settings_a.tolerance == 1e-10
    assert settings_b.max_function_evaluations == DEFAULT_MAX_FUNCTION_EVALUATIONS
    assert settings_b.tolerance == DEFAULT_TOLERANCE


def test_region_settings_round_trip_and_untouched_region_stays_default() -> None:
    """Persisted regions restore their own settings; an untouched region restores defaults."""
    project = SpectroscopyProject()
    region_a = project.create_region_with_lines([_add_test_line(project, center_z=0.5)])
    region_b = project.create_region_with_lines([_add_test_line(project, center_z=0.6)])
    region_c = project.create_region_with_lines([_add_test_line(project, center_z=0.7)])

    project.set_region_optimizer_settings(region_a.region_id, 2500, 1e-10)
    project.set_region_optimizer_settings(region_b.region_id, 5000, 1e-6)

    document = project_to_document(project)
    restored = project_from_document(document).project

    settings_a = restored.region_optimizer_settings(region_a.region_id)
    settings_b = restored.region_optimizer_settings(region_b.region_id)
    settings_c = restored.region_optimizer_settings(region_c.region_id)
    assert settings_a.max_function_evaluations == 2500
    assert settings_a.tolerance == 1e-10
    assert settings_b.max_function_evaluations == 5000
    assert settings_b.tolerance == 1e-6
    assert settings_c.max_function_evaluations == DEFAULT_MAX_FUNCTION_EVALUATIONS
    assert settings_c.tolerance == DEFAULT_TOLERANCE
    assert restored.region_optimizer_settings_overrides().keys() == {
        region_a.region_id,
        region_b.region_id,
    }
