"""Tests for ModeShellCoordinator snapshot integration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.editing_mode import EditingMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.gui.shell.mode_identify_workflow_adapter import (
    IdentifyWorkflowWindow,
    ModeIdentifyWorkflowAdapter,
)
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.mode_continuum_adapter import ModeContinuumAdapter
from chappy.gui.shell.mode_line_overlay_adapter import ModeLineOverlayAdapter
from chappy.gui.shell.mode_lifecycle_router import ModeLifecycleRouter
from chappy.gui.shell.mode_shell_coordinator import ModeShellCoordinator, ModeShellUiParts
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.gui.modes.mode_state_store import ModeStateStore
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    InteractionChannel,
    InteractionId,
    InteractionPhase,
    InteractionStateSnapshot,
    RectZoomContext,
)
from chappy.gui.modes.common import ModeRefreshRequest
from scripts.i18n_lupdate import run_lupdate


class _PolicyEmitter(QObject):
    """Real Qt signal owner used to verify post-commit shell synchronization."""

    policy_applied = Signal(object)


if TYPE_CHECKING:
    from chappy.gui.shell.main_window import MainWindow
    from chappy.gui.shell.mode_context_bar import ModeContextBar
    from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
    from chappy.gui.spectrum.spectrum_view import SpectrumView

type _SignalArgument = str | bool | EditingMode | ShellActionId | None


class _StubSignal:
    """Minimal signal stub compatible with the coordinator expectations."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Register a callback for later emission."""
        self._callbacks.append(callback)

    def emit(self, *args: _SignalArgument, **kwargs: _SignalArgument) -> None:
        """Invoke all registered callbacks."""
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _DataBridge:
    """Small data bridge fake."""

    def __init__(self) -> None:
        """Initialize the bridge."""
        self.project = None
        self.project_changed = _StubSignal()
        self.data_updated = _StubSignal()
        self.range_changed = _StubSignal()


class _RangeInput:
    """Small range input fake."""

    def __init__(self) -> None:
        """Initialize the input."""
        self.wavelength_range_changed = _StubSignal()


class _Interactor:
    """Small interactor fake."""

    def __init__(self) -> None:
        """Initialize the interactor."""
        self.sig_interaction_snapshot = _StubSignal()
        self.sig_cursor_position_changed = _StubSignal()
        self.rect_zoom_enabled = False

    def set_rect_zoom_mode(self, enabled: bool) -> None:
        """Record rectangle zoom mode."""
        self.rect_zoom_enabled = enabled

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return rectangle zoom mode."""
        return self.rect_zoom_enabled

    def set_selected_line_absorbers(self, _absorber_ids: set[str] | None) -> None:
        """Accept selected absorber updates."""


class _Toolbar:
    """Small toolbar fake."""

    def set_active_mode(self, _mode_name: str | None) -> None:
        """Accept active mode updates."""


class _StubContextBar(SimpleNamespace):
    """Context bar stub exposing the minimal API used by ModeShellCoordinator."""

    def __init__(self) -> None:
        super().__init__()
        self.toolbar_action_triggered = _StubSignal()
        self.zoom_rect_toggled = _StubSignal()
        self.mode_switch_requested = _StubSignal()
        self.last_zoom_active: bool | None = None

    def set_zoom_mode_active(self, active: bool) -> None:
        self.last_zoom_active = active


class _FailingContextBar(_StubContextBar):
    """Context bar test double that fails on zoom state sync."""

    def set_zoom_mode_active(self, active: bool) -> None:
        """Raise to expose required UI collaborator failures."""
        _ = active
        msg = "zoom sync failed"
        raise RuntimeError(msg)


class _BrokenContextBar(SimpleNamespace):
    """Context bar test double missing required signal ports."""


class _FailingPlotHost:
    """Plot host test double that fails on shell-driven updates."""

    def set_selected_absorption_region(self, absorption_region: AbsorptionRegion) -> None:
        """Raise to expose selected-region update failures."""
        _ = absorption_region
        msg = "selected region update failed"
        raise RuntimeError(msg)

    def apply_policy(self, _policy: object) -> None:
        """Raise to expose mode update failures."""
        msg = "mode update failed"
        raise RuntimeError(msg)


class _NoopPlotHost:
    """Plot host test double that accepts shell-driven updates."""

    def set_selected_absorption_region(self, absorption_region: AbsorptionRegion) -> None:
        """Accept selected-region updates."""
        _ = absorption_region

    def apply_policy(self, _policy: object) -> None:
        """Accept mode updates."""


class _NoopContinuumCoordinator:
    """Continuum coordinator test double that accepts mode updates."""

    def set_continuum_visible(self, visible: bool) -> None:
        """Accept semantic continuum visibility updates."""
        _ = visible


class _ModeChangeSpectrumView(SimpleNamespace):
    """Spectrum view test double exposing plot-host mode-change hooks."""

    def __init__(self, plot_host: _FailingPlotHost) -> None:
        """Initialize a view with a failing plot host."""
        super().__init__(plot_host=plot_host)

    def clear_reset_ranges(self) -> None:
        """Mirror the production API without side effects."""
        return None

    def apply_policy(self, policy: object) -> None:
        """Apply the plot portion through the view-owned policy entrypoint."""
        self.plot_host.apply_policy(policy.plot_policy)

    def set_absorption_line_regions(self, regions: list[object]) -> None:
        """Mirror the production overlay API without side effects."""
        _ = regions
        return None

    def set_start_mode_active(self, active: bool) -> None:
        """Mirror the production API without side effects."""
        _ = active
        return None


class _StubMainWindow(SimpleNamespace):
    """Simple main window stub providing the attributes used by ModeShellCoordinator."""

    def __init__(
        self, presenter: SpectrumInteractionCoordinator, context_bar: _StubContextBar | None = None
    ) -> None:
        super().__init__()
        spectrum_view = SimpleNamespace(coordinator=presenter)
        self.view_stack: SimpleNamespace | None = SimpleNamespace(spectrum_view=spectrum_view)
        self.mode_context_bar = context_bar
        self.action_factory = None
        self.action_map: dict[ShellActionId, _TriggeredAction] | None = None
        self.continuum_coordinator = None
        self.dock_coordinator = None
        self.data_control_panel = None
        self.range_dock = None
        self.status_controller = None
        self.current_project = None
        self.identify_coordinator = None
        self.identify_velocity_runtime = _IdentifyVelocityRuntime()
        self.open_observation_data = lambda: None
        self.open_project = lambda: None
        self.save_project = lambda: None

    @property
    def confirmed_line_overlay_region_id(self) -> str | None:
        """Keep confirmed overlays unscoped in generic mode-shell tests."""
        return None


class _IdentifyVelocityRuntime:
    """Minimal identify runtime accepted by shell tests."""

    def hide_velocity_plot(self) -> None:
        """Accept velocity overlay hide requests."""
        return None


class _TriggeredAction:
    """Small action double that records trigger calls."""

    def __init__(self) -> None:
        """Initialize trigger state."""
        self.trigger_count = 0

    def trigger(self) -> None:
        """Record that the action was triggered."""
        self.trigger_count += 1


class _LifecycleProbe:
    """Record mode lifecycle calls from ModeShellCoordinator."""

    def __init__(self) -> None:
        """Initialize call counters."""
        self.project: SpectroscopyProject | None = None
        self.activate_count = 0
        self.deactivate_count = 0
        self.refreshes: list[ModeRefreshRequest] = []

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Record active project propagation."""
        self.project = project

    def activate(self) -> None:
        """Record activation."""
        self.activate_count += 1

    def deactivate(self) -> None:
        """Record deactivation."""
        self.deactivate_count += 1

    def refresh(self, request: ModeRefreshRequest) -> None:
        """Record refresh requests."""
        self.refreshes.append(request)


class _PresenterStub:
    """Minimal presenter surface consumed by ModeShellCoordinator tests."""

    def __init__(self) -> None:
        self.mode_command_requested = _StubSignal()
        self.interaction_snapshot_applied = _StubSignal()
        self._interaction_mode: str | None = None

    def apply_interaction_state_snapshot(self, snapshot: InteractionStateSnapshot[object]) -> None:
        """Emit the provided snapshot."""
        self.interaction_snapshot_applied.emit(snapshot)

    def is_rect_zoom_mode_enabled(self) -> bool:
        """Return whether rect-zoom mode is active."""
        return self._interaction_mode == "rect_zoom"

    def set_interaction_mode(self, mode_name: str | None) -> None:
        """Record the interaction mode requested by the shell."""
        self._interaction_mode = mode_name


@pytest.fixture
def presenter() -> _PresenterStub:
    """Create a minimal presenter for shell coordination tests."""
    return _PresenterStub()


def test_mode_shell_coordinator_receives_rect_zoom_snapshots(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """ModeShellCoordinator should track the latest snapshot emitted by the presenter."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    coordinator._connect_presenter_signals()

    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom-42"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ACTIVE,
        context=RectZoomContext(
            start=(5100.0, 0.3), current=(5200.0, 0.35), end=None, bounds=None
        ),
    )

    presenter.apply_interaction_state_snapshot(snapshot)

    assert coordinator._latest_interaction_snapshot == snapshot

    absorber_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("abs-drag-7"),
        channel=InteractionChannel.ABSORBER_DRAG,
        phase=InteractionPhase.CANCELLED,
        context=AbsorberDragContext(
            absorber_id="abs-7",
            start=(5300.0, 0.28),
            current=(5310.0, 0.3),
            end=None,
            modifiers=0,
            cancel_reason="transform-failed",
        ),
    )

    presenter.apply_interaction_state_snapshot(absorber_snapshot)

    assert coordinator._latest_interaction_snapshot == absorber_snapshot


def test_rect_zoom_snapshot_updates_context_bar(presenter: SpectrumInteractionCoordinator) -> None:
    """Rect zoom snapshots should toggle the context bar zoom button state."""
    context_bar = _StubContextBar()
    main_window = _StubMainWindow(presenter, context_bar)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    coordinator._connect_context_bar_signals(cast("ModeContextBar", context_bar))
    coordinator._connect_presenter_signals()

    armed_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom-armed"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ARMED,
        context=RectZoomContext(
            start=(5000.0, 0.2), current=(5010.0, 0.21), end=None, bounds=None
        ),
    )

    presenter.apply_interaction_state_snapshot(armed_snapshot)

    assert context_bar.last_zoom_active is True

    cancelled_snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("rect-zoom-cancelled"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.CANCELLED,
        context=RectZoomContext(start=None, current=None, end=None, bounds=None),
    )

    presenter.apply_interaction_state_snapshot(cancelled_snapshot)

    assert context_bar.last_zoom_active is False


def test_rect_zoom_context_bar_failure_propagates(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Context bar wiring failures should not be hidden as defensive logging."""
    main_window = _StubMainWindow(presenter, context_bar=_FailingContextBar())
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("zoom-failure"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ARMED,
        context=RectZoomContext(start=(1.0, 2.0), current=None, end=None, bounds=None),
    )

    with pytest.raises(RuntimeError, match="zoom sync failed"):
        coordinator._interaction_mode_coordinator.handle_interaction_snapshot(snapshot)


def test_mode_shell_coordinator_rejects_mismatched_snapshot_context(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Interaction snapshot context must match the declared channel."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    snapshot = InteractionStateSnapshot(
        interaction_id=InteractionId("bad-snapshot-context"),
        channel=InteractionChannel.RECT_ZOOM,
        phase=InteractionPhase.ARMED,
        context=AbsorberDragContext(
            absorber_id="abs-7",
            start=(5300.0, 0.28),
            current=(5310.0, 0.3),
            end=None,
            modifiers=0,
            cancel_reason=None,
        ),
    )

    with pytest.raises(TypeError, match="Snapshot context for rect_zoom"):
        coordinator._interaction_mode_coordinator.handle_interaction_snapshot(snapshot)


def test_mode_shell_coordinator_notifies_mode_lifecycles(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """ModeShellCoordinator should drive mode lifecycle objects on mode changes."""
    main_window = _StubMainWindow(presenter)
    main_window.view_stack = SimpleNamespace(
        spectrum_view=_ModeChangeSpectrumView(_NoopPlotHost())
    )
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))
    coordinator.mode_state_store = ModeStateStore()
    structure_lifecycle = _LifecycleProbe()
    identify_lifecycle = _LifecycleProbe()
    coordinator._mode_lifecycles = {
        EditingMode.ANALYSIS: structure_lifecycle,
        EditingMode.IDENTIFY: identify_lifecycle,
    }
    coordinator._lifecycle_router = ModeLifecycleRouter(coordinator._mode_lifecycles)

    project = SpectroscopyProject()
    coordinator._set_lifecycle_project(project)
    coordinator._on_mode_changed(EditingMode.ANALYSIS)
    coordinator._on_mode_changed(EditingMode.IDENTIFY)

    assert structure_lifecycle.project is project
    assert identify_lifecycle.project is project
    assert structure_lifecycle.activate_count == 1
    assert structure_lifecycle.deactivate_count == 1
    assert structure_lifecycle.refreshes == [
        ModeRefreshRequest(mode=EditingMode.ANALYSIS, reason="mode-changed")
    ]
    assert identify_lifecycle.activate_count == 1
    assert identify_lifecycle.deactivate_count == 0
    assert identify_lifecycle.refreshes == [
        ModeRefreshRequest(mode=EditingMode.IDENTIFY, reason="mode-changed")
    ]


def test_mode_shell_coordinator_set_project_refreshes_active_lifecycle(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Project data should refresh only after the entry resolver selects a mode."""
    main_window = _StubMainWindow(presenter)
    main_window.view_stack = SimpleNamespace(
        spectrum_view=_ModeChangeSpectrumView(_NoopPlotHost())
    )
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))
    coordinator.mode_state_store = ModeStateStore()
    coordinator.mode_state_store.switch_mode(EditingMode.ANALYSIS)
    structure_lifecycle = _LifecycleProbe()
    coordinator._mode_lifecycles = {EditingMode.ANALYSIS: structure_lifecycle}
    coordinator._lifecycle_router = ModeLifecycleRouter(
        coordinator._mode_lifecycles, active_mode=EditingMode.ANALYSIS
    )

    coordinator.set_project(SpectroscopyProject())

    assert structure_lifecycle.project is not None
    assert structure_lifecycle.refreshes == []

    coordinator.enter_project_mode(EditingMode.ANALYSIS)

    assert structure_lifecycle.refreshes[-1] == ModeRefreshRequest(
        mode=EditingMode.ANALYSIS, reason="project-entry"
    )


def test_mode_shell_coordinator_requires_mode_state_store_for_switch(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Mode switching should fail fast before mode state store setup."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    with pytest.raises(RuntimeError, match="Mode state store is required"):
        coordinator.switch_mode(EditingMode.ANALYSIS)


def test_mode_shell_coordinator_requires_spectrum_view_for_presenter_connection(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Presenter signal connection should require the shell spectrum view."""
    main_window = _StubMainWindow(presenter)
    main_window.view_stack = None
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    with pytest.raises(RuntimeError, match="View stack is required"):
        coordinator._connect_presenter_signals()


def test_mode_shell_coordinator_rejects_broken_context_bar_signal_port(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """A non-None context bar must expose the required signal ports."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    with pytest.raises(AttributeError, match="toolbar_action_triggered"):
        coordinator._connect_context_bar_signals(cast("ModeContextBar", _BrokenContextBar()))


def test_mode_shell_coordinator_rejects_invalid_toolbar_action_payload(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Toolbar payloads must use the shared shell action identifier type."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    with pytest.raises(TypeError, match="Unknown toolbar action"):
        coordinator._toolbar_controller.handle_toolbar_action("unknown-action")


def test_mode_shell_coordinator_toolbar_action_uses_registered_shell_action(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Toolbar commands should route through registered shell actions."""
    main_window = _StubMainWindow(presenter)
    action = _TriggeredAction()
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))
    coordinator.set_ui_parts(
        ModeShellUiParts(action_map_provider=lambda: {ShellActionId.OPEN_PROJECT: action})
    )

    coordinator._toolbar_controller.handle_toolbar_action(ShellActionId.OPEN_PROJECT)

    assert action.trigger_count == 1


def test_mode_shell_coordinator_rejects_unknown_mode_request(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Unknown mode IDs are composition contract errors."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    with pytest.raises(ValueError, match="Unknown mode requested"):
        coordinator._toolbar_controller.handle_mode_switch_request("UNKNOWN")


def test_mode_shell_coordinator_mode_switch_uses_registered_shell_action(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Mode switch requests should route through the shared shell action system."""
    main_window = _StubMainWindow(presenter)
    action = _TriggeredAction()
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))
    coordinator.set_ui_parts(
        ModeShellUiParts(action_map_provider=lambda: {ShellActionId.IDENTIFY_MODE: action})
    )

    coordinator._toolbar_controller.handle_mode_switch_request(ShellActionId.IDENTIFY_MODE)

    assert action.trigger_count == 1


def test_mode_shell_coordinator_line_bounds_fail_fast_for_invalid_window() -> None:
    """Invalid line physics should not be hidden as an absent range."""
    line = AbsorptionLine(
        line_id="line-1",
        species="C IV",
        rest_wavelength=1548.2,
        center_z=2.0,
        window_kms=0.0,
        multiplet_label="C IV",
        transition_name="1548",
        oscillator_strength=0.19,
        gamma_value=1.0,
    )

    with pytest.raises(ValueError, match="Invalid absorption line wavelength bounds"):
        ModeShellCoordinator._line_wavelength_bounds(line)


def test_mode_shell_coordinator_flux_range_returns_none_without_observed_spectrum() -> None:
    """Missing observed spectrum is valid empty state for focus range calculation."""
    project = SpectroscopyProject()

    assert ModeShellCoordinator._compute_flux_range(project, 5000.0, 5100.0) is None


def test_mode_shell_coordinator_flux_range_fails_fast_for_invalid_bounds() -> None:
    """Invalid focus bounds should fail fast instead of producing a fallback."""
    project = SpectroscopyProject()

    with pytest.raises(ValueError, match="Invalid wavelength bounds"):
        ModeShellCoordinator._compute_flux_range(project, 5100.0, 5000.0)


def test_mode_shell_coordinator_flux_range_uses_visible_finite_flux() -> None:
    """Flux range should be computed only from finite values inside the visible window."""
    project = SpectroscopyProject()
    project.model.set_observed_spectrum(
        Spectrum(
            wavelength=np.asarray([4990.0, 5000.0, 5050.0, 5100.0], dtype=np.float64),
            flux=np.asarray([0.4, np.nan, 0.8, 0.9], dtype=np.float64),
        )
    )

    assert ModeShellCoordinator._compute_flux_range(project, 5000.0, 5060.0) == (-0.1, 1.1)


def test_mode_change_plot_host_failure_propagates(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Mode plot update failures should not be swallowed."""
    main_window = _StubMainWindow(presenter)
    main_window.continuum_coordinator = _NoopContinuumCoordinator()
    plot_host = _FailingPlotHost()
    main_window.view_stack = SimpleNamespace(spectrum_view=_ModeChangeSpectrumView(plot_host))
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))
    coordinator.mode_state_store = ModeStateStore()

    with pytest.raises(RuntimeError, match="mode update failed"):
        coordinator._on_mode_changed(EditingMode.ANALYSIS)


class _IdentifyWorkflowController:
    """Record identify workflow mode-change notifications."""

    def __init__(self) -> None:
        """Initialize captured mode changes."""
        self.states: list[bool] = []

    def set_identify_active(self, active: bool) -> None:
        """Record semantic Identify activation state."""
        self.states.append(active)


class _IdentifyWorkflowWindow:
    """Window stub exposing an identify coordinator."""

    def __init__(self, coordinator: _IdentifyWorkflowController | None) -> None:
        """Initialize the window stub.

        Args:
            coordinator: Identify coordinator-like endpoint.
        """
        self._identify_coordinator = coordinator

    @property
    def identify_coordinator(self) -> _IdentifyWorkflowController | None:
        """Return the identify coordinator-like endpoint."""
        return self._identify_coordinator


def test_identify_workflow_adapter_forwards_lifecycle_modes() -> None:
    """Identify workflow adapter should forward activation and deactivation modes."""
    workflow = _IdentifyWorkflowController()
    window = _IdentifyWorkflowWindow(workflow)
    adapter = ModeIdentifyWorkflowAdapter(cast("IdentifyWorkflowWindow", window))

    adapter.activate_identify_workflow()
    adapter.deactivate_identify_workflow()

    assert workflow.states == [True, False]


def test_identify_workflow_adapter_requires_identify_coordinator() -> None:
    """Identify workflow adapter should fail fast when the coordinator is missing."""
    window = _IdentifyWorkflowWindow(None)
    adapter = ModeIdentifyWorkflowAdapter(cast("IdentifyWorkflowWindow", window))

    with pytest.raises(RuntimeError, match="require an identify coordinator"):
        adapter.activate_identify_workflow()


def test_identify_workflow_adapter_propagates_controller_failure() -> None:
    """Identify workflow adapter should not swallow required controller failures."""

    class _FailingIdentifyWorkflowController:
        def set_identify_active(self, active: bool) -> None:
            raise RuntimeError(f"failed {'identify' if active else 'inactive'}")

    window = _IdentifyWorkflowWindow(_FailingIdentifyWorkflowController())
    adapter = ModeIdentifyWorkflowAdapter(cast("IdentifyWorkflowWindow", window))

    with pytest.raises(RuntimeError, match="failed identify"):
        adapter.activate_identify_workflow()


def test_continuum_adapter_requires_coordinator_and_propagates_failure() -> None:
    """Continuum adapter should fail fast for missing or failing coordinators."""
    missing_window = SimpleNamespace(continuum_coordinator=None)
    missing_adapter = ModeContinuumAdapter(cast("object", missing_window))

    with pytest.raises(RuntimeError, match="requires a continuum coordinator"):
        missing_adapter.show_continuum()

    class _FailingContinuumCoordinator:
        def set_continuum_visible(self, visible: bool) -> None:
            raise RuntimeError(f"failed {'continuum' if visible else 'hidden'}")

    failing_window = SimpleNamespace(continuum_coordinator=_FailingContinuumCoordinator())
    failing_adapter = ModeContinuumAdapter(cast("object", failing_window))

    with pytest.raises(RuntimeError, match="failed continuum"):
        failing_adapter.show_continuum()


def test_line_overlay_adapter_requires_identify_coordinator_and_spectrum_view() -> None:
    """Line overlay adapter should fail fast for missing required shell collaborators."""
    missing_identify = SimpleNamespace(
        current_project=None,
        identify_coordinator=None,
        view_stack=SimpleNamespace(spectrum_view=SimpleNamespace()),
    )
    adapter = ModeLineOverlayAdapter(cast("object", missing_identify))

    with pytest.raises(RuntimeError, match="require an identify coordinator"):
        adapter.show_identify_line_overlays()

    missing_view = SimpleNamespace(
        current_project=None,
        identify_coordinator=SimpleNamespace(
            build_line_overlay_payload=lambda include_temporary: []
        ),
        view_stack=None,
    )
    adapter = ModeLineOverlayAdapter(cast("object", missing_view))

    with pytest.raises(RuntimeError, match="require a view stack"):
        adapter.clear_line_overlays()

    invalid_spectrum = SimpleNamespace(
        current_project=None,
        identify_coordinator=SimpleNamespace(
            build_line_overlay_payload=lambda include_temporary: []
        ),
        view_stack=SimpleNamespace(spectrum_view=SimpleNamespace()),
    )
    adapter = ModeLineOverlayAdapter(cast("object", invalid_spectrum))

    with pytest.raises(TypeError, match="require a spectrum view"):
        adapter.clear_line_overlays()


def test_mode_shell_coordinator_uses_qt_sources_for_labels(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """Mode labels should resolve from Qt source text."""
    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))

    assert coordinator._status_mode_label(EditingMode.START) == "Start"
    assert coordinator._status_mode_label(EditingMode.ANALYSIS) == "Analysis"
    assert coordinator._status_mode_label(EditingMode.IDENTIFY) == "Identify"
    assert coordinator._status_mode_label(EditingMode.CONTINUUM) == "Continuum"
    assert coordinator._context_text("start.title") == "Start"
    assert (
        coordinator._context_text("start.subtitle")
        == "Load observation data or a project to continue"
    )
    assert coordinator._context_text("analysis.title") == "Analysis"


def test_lupdate_extracts_mode_shell_coordinator_sources(tmp_path: Path) -> None:
    """ModeShellCoordinator should expose migrated UI strings to lupdate without legacy keys."""
    ts_path = tmp_path / "mode_shell_coordinator_ja.ts"
    result = run_lupdate(
        source_dirs=[Path("src/chappy/gui/shell/mode_shell_coordinator.py")],
        ts_output=ts_path,
        extensions="py",
    )

    assert result.returncode == 0
    assert "GUI__" not in ts_path.read_text(encoding="utf-8")

    root = ET.parse(ts_path).getroot()
    sources = {source.text for source in root.findall(".//source") if source.text is not None}
    comments = {comment.text for comment in root.findall(".//comment") if comment.text}

    assert {
        "Start",
        "Load observation data or a project to continue",
        "Analysis",
        "Review and analyze regions",
        "Identify",
        "Associate detected regions with absorption lines",
        "Continuum Editing",
        "Edit continuum control points",
        "Continuum",
        "Start mode ready",
        "Switched to {mode} mode",
    } <= sources
    assert {"context bar title", "mode name"} <= comments


def test_real_policy_signal_isolates_cache_failure_from_action_sync(
    presenter: SpectrumInteractionCoordinator,
) -> None:
    """One failing shell observer cannot block later policy-derived action state."""

    class _FailingCache:
        def handle_policy_committed(self, _policy: object) -> None:
            raise RuntimeError("cache observer failed")

    class _ActionFactory:
        def __init__(self) -> None:
            self.policies: list[object] = []

        def update_spectrum_policy(self, policy: object) -> None:
            self.policies.append(policy)

    main_window = _StubMainWindow(presenter)
    coordinator = ModeShellCoordinator(cast("MainWindow", main_window))
    action_factory = _ActionFactory()
    coordinator._interaction_mode_coordinator = cast("InteractionModeCoordinator", _FailingCache())
    coordinator._ui_parts = ModeShellUiParts(
        action_factory=cast("MenuActionFactory", action_factory)
    )
    emitter = _PolicyEmitter()
    emitter.policy_applied.connect(coordinator._on_spectrum_policy_applied)
    policy = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)

    emitter.policy_applied.emit(policy)

    assert action_factory.policies == [policy]
