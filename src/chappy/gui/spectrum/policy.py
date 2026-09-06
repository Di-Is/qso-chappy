"""Neutral immutable policy for the shared spectrum surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from chappy.presentation.spectrum import SpectrumPlotDisplayCommand


class AbsorptionMarkerScope(StrEnum):
    """Component scope used for absorption markers and profile curves."""

    ALL_REGIONS = "ALL_REGIONS"
    SELECTED_REGION = "SELECTED_REGION"


@dataclass(frozen=True, slots=True)
class SpectrumInputCapabilities:
    """Keyboard, pointer, and drag capabilities exposed by the surface."""

    identify_velocity_shortcut_enabled: bool
    detail_velocity_shortcut_enabled: bool
    identify_click_enabled: bool
    optimize_shift_click_enabled: bool
    absorber_drag_enabled: bool


@dataclass(frozen=True, slots=True)
class SpectrumPlotPolicy:
    """Plot layers selected for one spectrum surface state."""

    display_command: SpectrumPlotDisplayCommand
    show_model_and_residual: bool
    show_mask_regions: bool
    show_absorption_line_markers: bool
    absorption_marker_scope: AbsorptionMarkerScope


@dataclass(frozen=True, slots=True)
class SpectrumTransitionCleanup:
    """Pending interaction state cancelled before applying a new policy."""

    cancel_mask_selection: bool = True
    cancel_absorber_drag: bool = True
    clear_interaction_mode: bool = True
    clear_reset_ranges: bool = True


class SpectrumPolicyCleanupError(RuntimeError):
    """Aggregated failures from the irreversible transition cleanup boundary."""

    def __init__(self, errors: tuple[Exception, ...]) -> None:
        if not errors:
            msg = "Spectrum policy cleanup failure requires at least one cause."
            raise ValueError(msg)
        self.errors = errors
        super().__init__("; ".join(f"{type(error).__name__}: {error}" for error in errors))


@dataclass(frozen=True, slots=True)
class SpectrumPolicy:
    """Complete neutral state applied atomically to the shared spectrum view."""

    input_capabilities: SpectrumInputCapabilities
    plot_policy: SpectrumPlotPolicy
    cursor_enabled: bool
    fit_model_enabled: bool
    start_overlay_active: bool
    transition_cleanup: SpectrumTransitionCleanup


def neutral_spectrum_policy() -> SpectrumPolicy:
    """Return the fail-safe policy used before composition and after rollback failure."""
    return SpectrumPolicy(
        input_capabilities=SpectrumInputCapabilities(
            identify_velocity_shortcut_enabled=False,
            detail_velocity_shortcut_enabled=False,
            identify_click_enabled=False,
            optimize_shift_click_enabled=False,
            absorber_drag_enabled=False,
        ),
        plot_policy=SpectrumPlotPolicy(
            display_command=SpectrumPlotDisplayCommand(
                use_normalized_observed=True, render_absorption_line_labels=False
            ),
            show_model_and_residual=False,
            show_mask_regions=False,
            show_absorption_line_markers=False,
            absorption_marker_scope=AbsorptionMarkerScope.ALL_REGIONS,
        ),
        cursor_enabled=False,
        fit_model_enabled=False,
        start_overlay_active=True,
        transition_cleanup=SpectrumTransitionCleanup(
            cancel_mask_selection=False,
            cancel_absorber_drag=False,
            clear_interaction_mode=False,
            clear_reset_ranges=False,
        ),
    )


__all__ = [
    "AbsorptionMarkerScope",
    "SpectrumInputCapabilities",
    "SpectrumPlotPolicy",
    "SpectrumPolicy",
    "SpectrumPolicyCleanupError",
    "SpectrumTransitionCleanup",
    "neutral_spectrum_policy",
]
