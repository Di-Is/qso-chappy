"""Contract tests for neutral shared-spectrum policies."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy


@pytest.mark.parametrize(
    ("mode", "model", "mask", "cursor", "drag", "marker", "fit", "velocity"),
    (
        (EditingMode.START, False, False, False, False, False, False, False),
        (EditingMode.ANALYSIS, False, False, False, False, True, False, False),
        (EditingMode.IDENTIFY, False, False, False, False, False, False, True),
        (EditingMode.CONTINUUM, False, False, False, False, False, False, False),
    ),
)
def test_top_level_modes_map_to_complete_neutral_policy(
    mode: EditingMode,
    model: bool,
    mask: bool,
    cursor: bool,
    drag: bool,
    marker: bool,
    fit: bool,
    velocity: bool,
) -> None:
    """Top-level modes map to their neutral shared-spectrum capabilities."""
    policy = spectrum_interaction_mode_policy(mode)

    assert policy.plot_policy.show_model_and_residual is model
    assert policy.plot_policy.show_mask_regions is mask
    assert policy.cursor_enabled is cursor
    assert policy.input_capabilities.absorber_drag_enabled is drag
    assert policy.plot_policy.show_absorption_line_markers is marker
    assert policy.fit_model_enabled is fit
    assert (
        policy.input_capabilities.identify_velocity_shortcut_enabled
        or policy.input_capabilities.detail_velocity_shortcut_enabled
    ) is velocity
    assert policy.transition_cleanup.cancel_mask_selection
    assert policy.transition_cleanup.cancel_absorber_drag
    assert policy.transition_cleanup.clear_interaction_mode


def test_analysis_detail_profile_enables_scientific_interactions() -> None:
    """Region Detail, not the top-level Analysis mode alone, enables fit interactions."""
    policy = analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL)

    assert policy.plot_policy.show_model_and_residual
    assert policy.plot_policy.show_mask_regions
    assert policy.cursor_enabled
    assert policy.input_capabilities.absorber_drag_enabled
    assert policy.plot_policy.show_absorption_line_markers
    assert policy.fit_model_enabled
    assert policy.input_capabilities.detail_velocity_shortcut_enabled


def test_spectrum_policy_is_immutable() -> None:
    """A policy cannot be partially changed after the transition begins."""
    policy = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)

    with pytest.raises(FrozenInstanceError):
        policy.fit_model_enabled = False  # type: ignore[misc]
