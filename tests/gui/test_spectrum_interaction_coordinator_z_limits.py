"""Test z-value restrictions in SpectrumInteractionCoordinator drag-and-drop operations."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from collections.abc import Callable, Iterable
from typing import cast

import pytest

from chappy.application.history import ComponentParameterState
from chappy.core.absorption.models import AbsorptionLine
from chappy.core.analysis import RegionAnalysisState
from chappy.core.components.absorber import AbsorberComponent
from chappy.application.spectrum.range_usecase import RangeNavigationUseCase
from chappy.gui.protocols.optimize_spectrum import OptimizeLineInfo
from chappy.gui.protocols.intent_types import EndAbsorberDragIntent, StartAbsorberDragIntent
from chappy.gui.shell.absorber_model_mutation_controller import (
    AbsorberModelMutationController,
    AbsorberModelMutationPorts,
)
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.gui.spectrum.interaction_controller_factory import SpectrumInteractionControllerFactory
from chappy.gui.spectrum.navigation_controller import SpectrumNavigationControllerFactory
from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
from chappy.gui.spectrum.spectrum_view_components import SpectrumViewComponents
from chappy.presentation.interaction.interaction_contracts import MaskSelectionRequest

type _SignalArgument = tuple[float, float] | MaskSelectionRequest | bool | None


@pytest.fixture
def view() -> SimpleNamespace:
    """Create spectrum view dependency."""
    return SimpleNamespace(window=lambda: None, get_velocity_plot_y_range=lambda: None)


class _Signal:
    """Small signal fake that records emissions."""

    def __init__(self) -> None:
        self.emissions: list[tuple[_SignalArgument, ...]] = []
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Register a callback."""
        self._callbacks.append(callback)

    def emit(self, *args: _SignalArgument) -> None:
        """Record and forward an emission."""
        self.emissions.append(args)
        for callback in list(self._callbacks):
            callback(*args)


@dataclass
class _Model:
    """Model fake with absorber components and update state."""

    components: list[AbsorberComponent] = field(default_factory=list)
    update_count: int = 0

    def update_model(self) -> None:
        """Record model updates."""
        self.update_count += 1

    def suppress_scientific_notifications(self) -> contextlib.AbstractContextManager[None]:
        """Expose the model transaction boundary used by scientific mutations."""
        return contextlib.nullcontext()

    def snapshot_derived_state_for_transaction(self) -> int:
        """Capture the focused fake's derived-state counter."""
        return self.update_count

    def restore_derived_state_for_transaction(self, snapshot: int) -> None:
        """Restore the focused fake's derived-state counter exactly."""
        self.update_count = snapshot

    def rebuild_model_storage(self) -> None:
        """Record the canonical derived-state rebuild."""
        self.update_model()

    def publish_storage_changes(self, _change_set: object) -> None:
        """Accept the isolated post-commit model notification."""


@dataclass
class _Project:
    """Project fake exposing model and empty analysis-artifact state."""

    model: _Model = field(default_factory=_Model)
    absorption_lines: dict[str, AbsorptionLine] = field(default_factory=dict)
    modified: datetime = field(default_factory=lambda: datetime.now(UTC))

    def region_analysis_state(self, _region_id: str) -> RegionAnalysisState | None:
        """Return no region analysis state."""
        return None

    def region_analysis_states(self) -> tuple[RegionAnalysisState, ...]:
        """Return the empty analysis-state collection."""
        return ()

    def stored_region_analysis_states_for_transaction(self) -> tuple[RegionAnalysisState, ...]:
        """Return the exact empty transaction snapshot."""
        return ()

    def replace_region_analysis_states_for_transaction(
        self, states: Iterable[RegionAnalysisState]
    ) -> None:
        """Restore the exact empty transaction snapshot."""
        assert tuple(states) == ()

    def set_region_analysis_state(self, _state: RegionAnalysisState) -> None:
        """Reject attempts to replace a nonexistent analysis state."""
        raise AssertionError("No analysis region exists in this fake")

    def set_region_analysis_states(self, states: Iterable[RegionAnalysisState]) -> None:
        """Accept only an empty atomic analysis-state replacement."""
        assert tuple(states) == ()

    def remove_region_analysis_state(self, _region_id: str) -> None:
        """Accept removal from the empty analysis-state collection."""

    def is_region_analysis_capable(self, _region_id: str) -> bool:
        """Return False because this focused fake contains no regions."""
        return False

    def region_requires_reanalysis(self, _region_id: str) -> bool:
        """Return False because this focused fake contains no regions."""
        return False

    def mark_region_needs_optimization(self, _region_id: str) -> int:
        """Return zero because this focused fake contains no regions."""
        return 0

    def mark_scientific_modified(self) -> None:
        """Record the accepted scientific mutation."""
        self.modified = datetime.now(UTC)


@dataclass
class _DataBridge:
    """Data bridge fake required by SpectrumInteractionCoordinator."""

    project: _Project = field(default_factory=_Project)
    project_changed: _Signal = field(default_factory=_Signal)
    data_updated: _Signal = field(default_factory=_Signal)
    range_changed: _Signal = field(default_factory=_Signal)


class _History:
    """No-op scientific history owner for interaction integration tests."""

    def atomic_recording(self) -> contextlib.AbstractContextManager[None]:
        """Return a valid history transaction scope."""
        return contextlib.nullcontext()

    def record_model_edit_params(
        self,
        component_ids: list[str],
        param_name: str,
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        region_id: str | None,
    ) -> None:
        """Accept one parameter history record."""
        _ = component_ids, param_name, before_states, after_states, region_id


class _RangeInput:
    """Small range input fake."""

    def __init__(self) -> None:
        """Initialize the input."""
        self.wavelength_range_changed = _Signal()


class _Interactor:
    """Small interactor fake."""

    def __init__(self) -> None:
        """Initialize the interactor."""
        self.sig_interaction_snapshot = _Signal()
        self.sig_cursor_position_changed = _Signal()
        self.rect_zoom_enabled = False

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Record rectangle zoom mode."""
        self.rect_zoom_enabled = enabled

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return rectangle zoom mode."""
        return self.rect_zoom_enabled

    def set_selected_line_absorbers(self, _absorber_ids: set[str] | None) -> None:
        """Accept selected absorber updates."""


@dataclass
class _OptimizeIntegration:
    """Optimize integration fake returning line info for components."""

    line_info: OptimizeLineInfo | None = None
    tree_update_count: int = 0
    focused_components: list[str] = field(default_factory=list)

    def get_line_info_for_component(
        self, _component: AbsorberComponent
    ) -> OptimizeLineInfo | None:
        """Return configured line information."""
        return self.line_info

    def update_tree_view(self) -> None:
        """Record tree refresh requests."""
        self.tree_update_count += 1

    def focus_component(self, component_id: str) -> None:
        """Record focused component ids."""
        self.focused_components.append(component_id)


class _OptimizePresenter:
    """Presenter dependency for OptimizeSpectrumIntegration tests."""

    def __init__(self) -> None:
        self.view = SimpleNamespace()
        self.active_mask_groups: list[str | None] = []
        self.selected_absorbers: set[str] | None = None
        self.highlighted_mask_id: str | None = None
        self.cancel_count = 0
        self.toggle_count = 0

    def set_absorber_drag_candidates(self, absorber_ids: set[str] | None) -> None:
        """Record selected absorber ids."""
        self.selected_absorbers = absorber_ids

    def request_mask_selection_interaction(self, _request: MaskSelectionRequest) -> bool:
        """Accept mask selection requests."""
        return True

    def highlight_mask(self, mask_id: str | None) -> None:
        """Record mask highlight requests."""
        self.highlighted_mask_id = mask_id

    def set_active_mask_group(self, group_id: str | None) -> None:
        """Record active mask group updates."""
        self.active_mask_groups.append(group_id)

    def cancel_mask_selection(self) -> None:
        """Record cancellation requests."""
        self.cancel_count += 1

    def context_menu_parent_widget(self) -> SimpleNamespace:
        """Return menu parent fake."""
        return self.view

    def is_velocity_overlay_visible(self) -> bool:
        """Return no velocity overlay for helper tests."""
        return False

    def toggle_velocity_plot(self) -> None:
        """Record optimize velocity toggles."""
        self.toggle_count += 1


class _OptimizePanel:
    """Panel fake returning a configured absorption line."""

    def __init__(self, line: AbsorptionLine | None) -> None:
        self.line = line
        self.line_selected = _Signal()
        self.mask_selection_requested = _Signal()
        self.mask_focus_changed = _Signal()
        self.mask_cancel_requested = _Signal()
        self.mask_group_changed = _Signal()
        self.added_wavelengths: list[float] = []

    def current_region_id(self) -> str | None:
        """Return no active group for helper tests."""
        return None

    def add_model_at_wavelength(self, wavelength: float) -> None:
        """Record model additions."""
        self.added_wavelengths.append(wavelength)

    def get_line_for_component(self, _component: AbsorberComponent) -> AbsorptionLine | None:
        """Return configured line information."""
        return self.line


def _build_optimize_spectrum_integration(
    presenter: _OptimizePresenter, panel: _OptimizePanel | None
) -> object:
    """Create optimize integration with explicit shell callbacks."""
    from chappy.gui.modes.analysis.region_detail.spectrum_integration import (
        OptimizeSpectrumIntegration,
    )

    return OptimizeSpectrumIntegration(
        presenter,
        panel,  # type: ignore[arg-type]
        velocity_visible_provider=lambda: False,
        velocity_toggle_callback=lambda: setattr(
            presenter, "toggle_count", presenter.toggle_count + 1
        ),
        cursor_feedback_callback=lambda _cursor_mode: None,
    )


@pytest.fixture
def data_bridge() -> _DataBridge:
    """Create data bridge with project."""
    return _DataBridge()


@pytest.fixture
def presenter(view: SimpleNamespace, data_bridge: _DataBridge) -> SpectrumInteractionCoordinator:
    """Create SpectrumInteractionCoordinator instance."""
    presenter = SpectrumInteractionCoordinator(
        view,
        SpectrumNavigationControllerFactory(RangeNavigationUseCase()),
        SpectrumInteractionControllerFactory(),
        SpectrumViewComponents(
            data_bridge=cast("SpectrumDataBridge", data_bridge),
            plot_host=cast("SpectrumPlotHost", SimpleNamespace(plot_widget=None)),
            range_input_controls=cast("SpectrumRangeInputControls", _RangeInput()),
            interactor=cast("SpectrumInputFacadePort", _Interactor()),
        ),
    )
    owner = AbsorberModelMutationController(
        ports=AbsorberModelMutationPorts(
            project_provider=lambda: data_bridge.project,  # type: ignore[return-value]
            line_info_provider=presenter._get_line_info_for_component,
            history_provider=_History,
            plot_widget_provider=lambda: None,
            plot_refresh_callback=lambda: None,
            data_updated_callback=data_bridge.data_updated.emit,
            refresh_optimize_callback=presenter._refresh_optimize_tree_view,
            focus_component_callback=presenter._focus_optimize_component,
            refresh_velocity_overlay_callback=lambda: None,
        )
    )
    presenter.attach_absorber_model_mutation_owner(owner)
    return presenter


@pytest.fixture
def optimize_integration() -> _OptimizeIntegration:
    """Create optimize integration fake."""
    return _OptimizeIntegration()


def _component(
    *,
    component_id: str = "test_comp",
    name: str = "H I",
    wavelength: float = 1215.67,
    redshift: float = 2.0,
) -> AbsorberComponent:
    """Create an absorber component with stable id."""
    component = AbsorberComponent(name=name, wavelength=wavelength, redshift=redshift)
    component.id = component_id
    return component


def _complete_drag(
    presenter: SpectrumInteractionCoordinator, component: AbsorberComponent, target_redshift: float
) -> None:
    """Complete one absorber drag through the formal begin/end intent route."""
    presenter.coordinate_absorber_intent(
        StartAbsorberDragIntent(
            absorber_id=component.id,
            initial_wavelength=component.wavelength
            * (1.0 + component.get_parameter_value("redshift")),
            initial_position=(0.0, 0.0),
        )
    )
    presenter.coordinate_absorber_intent(
        EndAbsorberDragIntent(
            absorber_id=component.id,
            final_wavelength=component.wavelength * (1.0 + target_redshift),
        )
    )


class TestDragAndDropZLimits:
    """Test z-value restrictions during drag-and-drop operations."""

    def test_drag_without_line_constraints(
        self, presenter: SpectrumInteractionCoordinator, data_bridge: _DataBridge
    ) -> None:
        """Test drag-and-drop without line constraints (no optimize integration)."""
        # Create test component
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=2.0)
        component.id = "test_comp"
        data_bridge.project.model.components = [component]

        # Drag to new redshift without optimize integration
        presenter.detach_optimize_integration()
        _complete_drag(presenter, component, 3.0)

        assert component.parameters["redshift"].value == 3.0  # No clamping

    def test_drag_with_line_constraints(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Test drag-and-drop with line constraints."""
        # Create test component
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=2.0)
        component.id = "test_comp"
        data_bridge.project.model.components = [component]

        # Setup optimize integration with line info
        optimize_integration.line_info = {
            "rest_wavelength": 1215.67,
            "lambda_range": (3500.0, 4000.0),  # z range: ~1.88 to ~2.29
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        # Drag to redshift within range
        _complete_drag(presenter, component, 2.1)
        assert component.parameters["redshift"].value == 2.1  # No clamping needed

    def test_drag_with_clamping_below_minimum(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Test drag-and-drop with clamping to minimum z value."""
        # Create test component
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=2.0)
        component.id = "test_comp"
        data_bridge.project.model.components = [component]

        # Setup optimize integration with line info
        optimize_integration.line_info = {
            "rest_wavelength": 1215.67,
            "lambda_range": (3500.0, 4000.0),  # z range: ~1.88 to ~2.29
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        # Drag to redshift below minimum
        _complete_drag(presenter, component, 1.5)

        # Should be clamped to minimum
        clamped_value = component.parameters["redshift"].value
        assert abs(clamped_value - 1.8791) < 0.001

    def test_drag_with_clamping_above_maximum(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Test drag-and-drop with clamping to maximum z value."""
        # Create test component
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=2.0)
        component.id = "test_comp"
        data_bridge.project.model.components = [component]

        # Setup optimize integration with line info
        optimize_integration.line_info = {
            "rest_wavelength": 1215.67,
            "lambda_range": (3500.0, 4000.0),  # z range: ~1.88 to ~2.29
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        # Drag to redshift above maximum
        _complete_drag(presenter, component, 3.0)

        # Should be clamped to maximum
        clamped_value = component.parameters["redshift"].value
        assert abs(clamped_value - 2.2904) < 0.001

    def test_drag_with_physical_constraints(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Test drag-and-drop respects physical constraints."""
        # Create test component
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=0.0)
        component.id = "test_comp"
        data_bridge.project.model.components = [component]

        # Setup optimize integration with very wide line range
        optimize_integration.line_info = {
            "rest_wavelength": 1215.67,
            "lambda_range": (100.0, 20000.0),  # Very wide range
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        # Drag to negative redshift below physical limit
        _complete_drag(presenter, component, -0.5)

        # Should be clamped to physical minimum
        clamped_value = component.parameters["redshift"].value
        assert clamped_value == -0.1

    def test_drag_without_line_info(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Test drag-and-drop when line info is not available."""
        # Create test component
        component = AbsorberComponent(name="Unknown", wavelength=1500.0, redshift=1.0)
        component.id = "test_comp"
        data_bridge.project.model.components = [component]

        # Setup optimize integration that returns None for line info
        optimize_integration.line_info = None
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        # Drag to new redshift
        _complete_drag(presenter, component, 2.5)

        # Should not be clamped (no line constraints)
        assert component.parameters["redshift"].value == 2.5

    def test_multiplet_constraints(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Test drag-and-drop with multiplet constraints (most restrictive limits)."""
        # Create test component (part of Mg II doublet)
        component = AbsorberComponent(name="Mg II", wavelength=2796.35, redshift=1.0)
        component.id = "mg2_comp"
        data_bridge.project.model.components = [component]

        # Setup optimize integration with narrow range (simulating multiplet constraints)
        optimize_integration.line_info = {
            "rest_wavelength": 2796.35,
            "lambda_range": (5590.0, 5600.0),  # Very narrow range for multiplet
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        # Try to drag outside narrow range
        _complete_drag(presenter, component, 1.05)

        # Should be clamped to narrow range
        clamped_value = component.parameters["redshift"].value
        # Expected max: (5600.0 / 2796.35) - 1 ≈ 1.0036
        assert abs(clamped_value - 1.0036) < 0.001


class TestModifyAbsorberParameterZLimits:
    """Test z-value restrictions when modifying absorber parameters (DoD operations)."""

    def test_modify_redshift_clamped_to_line_range(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Redshift updates clamp to the line wavelength range."""
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=2.0)
        component.id = "comp-alpha"
        data_bridge.project.model.components = [component]

        optimize_integration.line_info = {
            "rest_wavelength": 1215.67,
            "lambda_range": (3500.0, 4000.0),
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        presenter.update_absorber_param(component.id, "redshift", 1.5)

        clamped_value = component.parameters["redshift"].value
        assert abs(clamped_value - 1.8791) < 0.001

    def test_modify_redshift_within_range_no_clamp(
        self,
        presenter: SpectrumInteractionCoordinator,
        data_bridge: _DataBridge,
        optimize_integration: _OptimizeIntegration,
    ) -> None:
        """Redshift updates within range do not clamp."""
        component = AbsorberComponent(name="H I", wavelength=1215.67, redshift=2.0)
        component.id = "comp-beta"
        data_bridge.project.model.components = [component]

        optimize_integration.line_info = {
            "rest_wavelength": 1215.67,
            "lambda_range": (3500.0, 4000.0),
        }
        presenter.attach_optimize_integration(optimize_integration)  # type: ignore[arg-type]

        presenter.update_absorber_param(component.id, "redshift", 2.1)

        assert component.parameters["redshift"].value == pytest.approx(2.1)


class TestOptimizeIntegrationHelpers:
    """Test helper methods in OptimizeSpectrumIntegration."""

    def test_get_line_info_for_component_with_line(self) -> None:
        """Test getting line info when line exists."""
        # Create test line
        test_line = AbsorptionLine(
            line_id="test_line",
            species="H I",
            rest_wavelength=1215.67,
            center_z=2.0,
            window_kms=150.0,
            lambda_range=(3500.0, 4000.0),
            multiplet_label="",
            transition_name="H I 1215.7",
            oscillator_strength=0.1,
            gamma_value=1e8,
        )

        # Create integration
        integration = _build_optimize_spectrum_integration(
            _OptimizePresenter(), _OptimizePanel(test_line)
        )

        # Get line info for component
        component = AbsorberComponent(component_id="component-1")
        info = integration.get_line_info_for_component(component)

        assert info is not None
        assert info["rest_wavelength"] == 1215.67
        assert info["lambda_range"] == (3500.0, 4000.0)

    def test_get_line_info_for_component_without_line(self) -> None:
        """Test getting line info when line doesn't exist."""
        # Create integration
        integration = _build_optimize_spectrum_integration(
            _OptimizePresenter(), _OptimizePanel(None)
        )

        # Get line info for component
        component = AbsorberComponent(component_id="component-1")
        info = integration.get_line_info_for_component(component)

        assert info is None

    def test_optimize_integration_rejects_missing_panel(self) -> None:
        """Missing optimize panel should fail at composition."""
        with pytest.raises(TypeError, match="requires an optimize panel"):
            _build_optimize_spectrum_integration(_OptimizePresenter(), None)
