"""Tests for resolution settings restoration at the application/core boundary.

Pins the behavior described in docs/task/core-project-refactor/plan.md, Phase 1
(P1-SETTINGS-BOUNDARY): settings-key fallback and bool coercion live in
``chappy.application.project_mapper``, while ``SpectroscopyProject.set_resolution`` only
applies a typed ``ResolutionState``.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from chappy.application.project_mapper import project_from_document, project_to_document
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.resolution import SETTINGS_RESOLUTION_ENABLED_KEY, SETTINGS_RESOLUTION_VALUE_KEY

_WAVELENGTH = np.linspace(1000.0, 1010.0, 64, dtype=np.float64)


def _spike_flux() -> np.ndarray:
    flux = np.ones_like(_WAVELENGTH)
    flux[len(flux) // 2] = 5.0
    return flux


def _resolution_effect_changes_flux(project: SpectroscopyProject) -> bool:
    """Return True when the project's configured resolution alters flux."""
    flux = _spike_flux()
    result = project.model.apply_resolution_effect(_WAVELENGTH, flux)
    return not np.allclose(result, flux)


def _document_with_settings(settings: dict[str, object]):
    document = project_to_document(SpectroscopyProject())
    return dataclasses.replace(document, settings=settings)


def test_no_resolution_keys_present_leaves_default_state() -> None:
    """Without canonical or legacy keys, restoration is a no-op."""
    document = _document_with_settings({})

    project = project_from_document(document).project

    assert _resolution_effect_changes_flux(project) is False


def test_legacy_keys_are_honored() -> None:
    """Legacy 'resolution'/'resolution_enabled' keys apply."""
    document = _document_with_settings({"resolution": 45000.0, "resolution_enabled": True})

    project = project_from_document(document).project

    assert _resolution_effect_changes_flux(project) is True
    assert project.resolution_state.value == pytest.approx(45000.0)
    assert project.resolution_state.enabled is True


def test_canonical_keys_take_precedence_over_legacy() -> None:
    """When both canonical and legacy keys exist, canonical values win."""
    document = _document_with_settings(
        {
            "resolution": 10000.0,
            "resolution_enabled": False,
            SETTINGS_RESOLUTION_VALUE_KEY: 45000.0,
            SETTINGS_RESOLUTION_ENABLED_KEY: True,
        }
    )

    project = project_from_document(document).project

    assert project.resolution_state.value == pytest.approx(45000.0)
    assert project.resolution_state.enabled is True
    # Legacy False would leave resolution disabled; canonical True must win.
    assert _resolution_effect_changes_flux(project) is True


def test_non_numeric_value_is_skipped_and_state_unchanged() -> None:
    """A non-numeric resolution value is skipped without side effects."""
    document = _document_with_settings({SETTINGS_RESOLUTION_VALUE_KEY: "abc"})

    project = project_from_document(document).project

    assert _resolution_effect_changes_flux(project) is False


def test_set_resolution_with_identical_state_skips_recompute(monkeypatch) -> None:
    """Calling set_resolution twice with the same value/enabled recomputes only once."""
    project = SpectroscopyProject()
    call_count = 0
    original_update_model = project.model.update_model

    def spy_update_model():
        nonlocal call_count
        call_count += 1
        return original_update_model()

    monkeypatch.setattr(project.model, "update_model", spy_update_model)

    project.set_resolution(45000.0, True)
    project.set_resolution(45000.0, True)

    assert call_count == 1
