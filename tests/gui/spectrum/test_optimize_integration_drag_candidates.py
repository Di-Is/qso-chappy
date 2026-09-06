"""Regression tests for dragging multiplet-tie members in Region Detail."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import pytest

from chappy.application.history.recorder import HistoryRecorder
from chappy.application.optimize.model_addition_usecase import AddOptimizeModelComponentsUseCase
from chappy.application.optimize.models import ModelAdditionRequest
from chappy.core.absorption.multiplet_service import setup_multiplet_cross_references
from chappy.core.absorption_display import group_lines_by_multiplet, sort_lines_for_display
from chappy.core.atomic_data import AtomicLineData
from chappy.core.components.tie_set import effective_tie_set_for_parameter
from chappy.core.history.command_history import CommandHistory
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.region_detail.spectrum_integration import (
    OptimizeSpectrumIntegration,
)
from chappy.gui.protocols.intent_types import EndAbsorberDragIntent, StartAbsorberDragIntent
from chappy.gui.protocols.optimize_spectrum import OptimizeLineInfo
from chappy.gui.shell.absorber_model_mutation_controller import (
    AbsorberModelMutationController,
    AbsorberModelMutationPorts,
)
from chappy.gui.spectrum.absorber_drag_coordinator import SpectrumAbsorberDragCoordinator
from chappy.gui.spectrum.interaction.input.controllers.absorber_drag_input_controller import (
    AbsorberDragInputController,
)
from chappy.presentation.interaction.interaction_contracts import OptimizeLineSelectionChange

if TYPE_CHECKING:
    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.components.absorber import AbsorberComponent
    from chappy.gui.modes.analysis.region_detail.panel import RegionDetailPanel
    from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator

CENTER_Z = 0.7627
FE_II_LINES = ((2374.460, 0.0313), (2382.764, 0.320), (2586.649, 0.0691), (2600.172, 0.239))


class _Signal:
    """Signal stand-in recording connected slots."""

    def __init__(self) -> None:
        self._slots: list[Callable[..., None]] = []

    def connect(self, slot: Callable[..., None]) -> None:
        """Register a slot."""
        self._slots.append(slot)

    def emit(self, *args: object) -> None:
        """Invoke connected slots."""
        for slot in self._slots:
            slot(*args)


class _ParentView:
    """Context-menu parent stand-in."""


class _RecordingCoordinator:
    """Spectrum coordinator fake recording drag candidate updates."""

    def __init__(self) -> None:
        self.view = _ParentView()
        self.drag_candidates: set[str] | None = None
        self.active_mask_group: str | None = None
        self.selected_component_id: str | None = None

    def set_absorber_drag_candidates(self, absorber_ids: set[str] | None) -> None:
        """Record selected absorber ids."""
        self.drag_candidates = absorber_ids

    def set_active_mask_group(self, group_id: str | None) -> None:
        """Record active mask group synchronization."""
        self.active_mask_group = group_id

    def set_selected_component_id(self, component_id: str | None) -> None:
        """Record the component whose marker label is emphasised."""
        self.selected_component_id = component_id


class _TieAwarePanel:
    """Panel fake resolving redshift ties against a real project model."""

    def __init__(self, project: SpectroscopyProject) -> None:
        self._project = project
        self.line_selected = _Signal()
        self.mask_selection_requested = _Signal()
        self.mask_focus_changed = _Signal()
        self.mask_cancel_requested = _Signal()
        self.mask_group_changed = _Signal()

    def add_model_at_wavelength(self, _wavelength: float) -> None:
        """Accept model-add signal connections."""

    def current_region_id(self) -> str | None:
        """Return no focused region."""
        return None

    def get_line_wavelength_range(self) -> tuple[float, float] | None:
        """Return no selected range."""
        return None

    def tie_member_ids_for_redshift(self, component_id: str) -> frozenset[str]:
        """Return the ids of components sharing redshift with the component."""
        component = self._project.find_absorber_component(component_id)
        if component is None:
            return frozenset()
        tie_set = effective_tie_set_for_parameter(component, "redshift")
        if tie_set is None:
            return frozenset()
        return frozenset(member.id for member in tie_set.components)


class _DragInputOwner:
    """Absorber drag input owner fake that always permits dragging."""

    def require_absorber_drag_controller(self) -> object:
        """Unused by eligibility checks."""
        raise AssertionError

    def active_input_channel(self) -> None:
        """Return no active channel."""
        return None

    def can_start_absorber_drag(self) -> bool:
        """Allow drag interactions."""
        return True

    def absorber_drag_enabled(self) -> bool:
        """Enable absorber drag."""
        return True

    def active_absorber_drag_id(self) -> None:
        """Return no active drag."""
        return None

    def acquire_absorber_drag(self, absorber_id: str) -> None:
        """Accept channel ownership."""

    def clear_absorber_drag(self) -> None:
        """Release channel ownership."""

    def absorber_at_wavelength(self, wavelength: float) -> None:
        """Return no marker hit."""
        return None


def _build_project_with_full_tie() -> tuple[SpectroscopyProject, list[AbsorptionLine]]:
    """Create a project holding one 4-line Fe II full multiplet tie."""
    project = SpectroscopyProject("tie-drag-test")
    region_id = project.create_absorption_region("R1").region_id

    lines = []
    for rest_wavelength, oscillator_strength in FE_II_LINES:
        observed = rest_wavelength * (1.0 + CENTER_Z)
        lines.append(
            project.add_absorption_line(
                species="Fe II",
                rest_wavelength=rest_wavelength,
                center_z=CENTER_Z,
                window_kms=500.0,
                multiplet_label="Fe II",
                transition_name=f"Fe II {rest_wavelength:.0f}",
                oscillator_strength=oscillator_strength,
                gamma_value=3e8,
                lambda_range=(observed - 20.0, observed + 20.0),
                region_id=region_id,
            )
        )
    setup_multiplet_cross_references({"FeII_UV": lines})

    usecase = AddOptimizeModelComponentsUseCase(lambda: AtomicLineData())
    request = ModelAdditionRequest(
        redshift=CENTER_Z, column_density=14.0, b_parameter=10.0, covering_factor=1.0
    )
    result = usecase.add_components(project, lines[0], request)
    assert len(result.tie_sets) == 1
    assert len(result.tie_sets[0].components) == 4

    display_lines = sort_lines_for_display(project.list_absorption_lines())
    group = group_lines_by_multiplet(display_lines)[0]
    return project, list(group)


def _build_integration(
    coordinator: _RecordingCoordinator, panel: _TieAwarePanel
) -> OptimizeSpectrumIntegration:
    """Assemble the integration under test around fakes."""
    return OptimizeSpectrumIntegration(
        spectrum_interaction_coordinator=cast("SpectrumInteractionCoordinator", coordinator),
        optimize_panel=cast("RegionDetailPanel", panel),
        velocity_visible_provider=lambda: False,
        velocity_toggle_callback=lambda: None,
        cursor_feedback_callback=lambda _cursor_mode: None,
    )


def _mutation_controller(project: SpectroscopyProject) -> AbsorberModelMutationController:
    """Create a mutation controller wired to a real history recorder."""
    history = HistoryRecorder(CommandHistory(), lambda: project)

    def line_info(component: AbsorberComponent) -> OptimizeLineInfo | None:
        owner = next(
            (line for line in project.list_absorption_lines() if component.id in line.model_ids),
            None,
        )
        if owner is None:
            return None
        return OptimizeLineInfo(
            rest_wavelength=float(owner.rest_wavelength), lambda_range=owner.lambda_range
        )

    return AbsorberModelMutationController(
        ports=AbsorberModelMutationPorts(
            project_provider=lambda: project,
            line_info_provider=line_info,
            history_provider=lambda: history,
            plot_widget_provider=lambda: None,
            plot_refresh_callback=lambda: None,
            data_updated_callback=lambda: None,
            refresh_optimize_callback=lambda: None,
            focus_component_callback=lambda _component_id: None,
            refresh_velocity_overlay_callback=lambda: None,
        )
    )


def test_group_selection_allows_dragging_every_tie_member() -> None:
    """Selecting the group row must make all four tied components draggable."""
    project, group = _build_project_with_full_tie()
    coordinator = _RecordingCoordinator()
    integration = _build_integration(coordinator, _TieAwarePanel(project))

    selected_component_id = group[0].model_ids[0]
    integration._on_line_selected(
        OptimizeLineSelectionChange(line=group[0], component_id=selected_component_id)
    )

    assert coordinator.selected_component_id == selected_component_id
    all_component_ids = {model_id for line in group for model_id in line.model_ids}
    assert coordinator.drag_candidates == all_component_ids

    drag_input = AbsorberDragInputController(owner=_DragInputOwner())
    drag_input.set_selected_line_absorbers(coordinator.drag_candidates)
    for line in group:
        for model_id in line.model_ids:
            assert drag_input.can_drag_absorber(model_id), line.transition_name


def test_dragging_non_primary_member_moves_whole_four_member_tie() -> None:
    """Dragging a sibling-line marker must move the shared tie redshift."""
    project, group = _build_project_with_full_tie()
    non_primary_line = group[-1]
    component_id = non_primary_line.model_ids[0]
    component = project.find_absorber_component(component_id)
    assert component is not None

    controller = _mutation_controller(project)
    drag_coordinator = SpectrumAbsorberDragCoordinator(
        absorber_provider=controller.resolve_absorber,
        velocity_overlay_provider=lambda: None,
        plot_widget_provider=lambda: None,
        drag_apply_callback=controller.apply_drag,
        cursor_reset_callback=lambda: None,
    )

    z_before = component.parameters["redshift"].value
    observed = component.wavelength * (1.0 + z_before)
    drag_coordinator.handle_drag_start(
        StartAbsorberDragIntent(
            absorber_id=component_id,
            initial_wavelength=observed,
            initial_position=(observed, 0.5),
            wavelength_already_converted=True,
        )
    )
    drag_coordinator.handle_drag_end(
        EndAbsorberDragIntent(
            absorber_id=component_id, final_wavelength=observed + 5.0, calculate_redshift=True
        )
    )

    z_after = component.parameters["redshift"].value
    assert z_after == pytest.approx((observed + 5.0) / component.wavelength - 1.0)

    tie_set = effective_tie_set_for_parameter(component, "redshift")
    assert tie_set is not None
    assert len(tie_set.components) == 4
    for member in tie_set.components:
        assert member.parameters["redshift"].value == pytest.approx(z_after)
