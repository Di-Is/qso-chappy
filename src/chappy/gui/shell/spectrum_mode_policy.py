"""Shell-owned mapping from editing modes to shared spectrum policies."""

from __future__ import annotations

from chappy.core.editing_mode import EditingMode
from chappy.gui.spectrum.policy import (
    AbsorptionMarkerScope,
    SpectrumInputCapabilities,
    SpectrumPlotPolicy,
    SpectrumPolicy,
    SpectrumTransitionCleanup,
)
from chappy.presentation.spectrum import SpectrumPlotDisplayCommand


def spectrum_interaction_mode_policy(mode: EditingMode) -> SpectrumPolicy:
    """Return the shared spectrum policy for a GUI editing mode."""
    optimize = False
    identify = mode is EditingMode.IDENTIFY
    analysis = mode is EditingMode.ANALYSIS
    continuum = mode is EditingMode.CONTINUUM
    start = mode is EditingMode.START
    return SpectrumPolicy(
        input_capabilities=SpectrumInputCapabilities(
            identify_velocity_shortcut_enabled=identify,
            detail_velocity_shortcut_enabled=optimize,
            identify_click_enabled=identify,
            optimize_shift_click_enabled=optimize,
            absorber_drag_enabled=optimize,
        ),
        plot_policy=SpectrumPlotPolicy(
            display_command=SpectrumPlotDisplayCommand(
                use_normalized_observed=not continuum,
                render_absorption_line_labels=analysis or identify,
            ),
            show_model_and_residual=optimize,
            show_mask_regions=optimize,
            show_absorption_line_markers=analysis,
            absorption_marker_scope=AbsorptionMarkerScope.ALL_REGIONS,
        ),
        cursor_enabled=optimize,
        fit_model_enabled=optimize,
        start_overlay_active=start,
        transition_cleanup=SpectrumTransitionCleanup(),
    )
