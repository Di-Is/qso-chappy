"""Regression tests for Region Detail refresh after structure topology commits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QComboBox, QTreeWidget

from chappy.application.history import ChangeSet as HistoryChangeSet
from chappy.application.history import HistoryRecorder
from chappy.application.history.apply.usecase import HistoryApplyUseCase
from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    AtomicRegisterSelectedLinesRequest,
    TemporaryLineSnapshot,
)
from chappy.application.structure.structure_operation_usecase import StructureOperationUseCase
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.change_set import ChangeSet
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.editing_mode import EditingMode
from chappy.core.events import RegionTopologyChanged
from chappy.core.history import CommandHistory
from chappy.core.identify_state import TemporaryLineContext
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.contracts import BottomPage, PanelState, RightPage
from chappy.gui.modes.analysis.overview.adapters import StructureOperationAdapter
from chappy.gui.modes.analysis.overview.interaction_coordinator import (
    StructureInteractionCoordinator,
    StructureInteractionPorts,
)
from chappy.gui.modes.analysis.overview.operation_controller import StructureOperationController
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from chappy.gui.modes.analysis.region_detail.editor import OptimizeEditor
from chappy.gui.modes.analysis.region_detail.panel import RegionDetailPanel
from chappy.gui.modes.analysis.surface_coordinator import AnalysisSurfaceCoordinator
from chappy.gui.modes.analysis.surface_policy import AnalysisSurfaceUiPolicy
from chappy.gui.modes.common.analysis_navigation import AnalysisNavigationState, AnalysisSurface
from chappy.gui.adapters.model_event_adapter import SpectrumModelEventAdapter
from chappy.gui.shell.main_window import MainWindow
from chappy.core.velocity_ranges import (
    DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
    LineAnalysisHalfWidth,
)
from tests.gui.widgets.optimize_panel_helpers import (
    NoOpModelAdditionUseCase,
    build_region_detail_usecases,
)

if TYPE_CHECKING:
    from chappy.gui.modes.common.analysis_navigation import AnalysisOverviewNavigationPort
    from pytestqt.qtbot import QtBot


class _ModeState(QObject):
    """Mode-state test double that makes the selector available."""

    def set_focused_region(
        self, region: AbsorptionRegion | None, *, emit_signal: bool = True
    ) -> ChangeSet:
        """Accept the legacy focused-region projection."""
        _ = region, emit_signal
        return ChangeSet.empty()


class _AnalysisFocus:
    """Canonical focus shared by the shell and real Region Detail panel."""

    def __init__(self) -> None:
        self._state = AnalysisNavigationState(surface=AnalysisSurface.REGION_DETAIL)
        self.focus_calls: list[str] = []
        self.clear_focus_calls: list[str] = []

    @property
    def state(self) -> AnalysisNavigationState:
        """Expose the shell-facing navigation state."""
        return self._state

    def focus_region(self, region_id: str) -> bool:
        """Record and apply a canonical focus request."""
        self.focus_calls.append(region_id)
        self._state = self._state.with_focused_region(region_id)
        return True

    def set_surface(self, surface: AnalysisSurface) -> None:
        """Apply the surface persisted by the production coordinator."""
        self._state = self._state.with_surface(surface)

    def focused_region_id(self) -> str | None:
        """Return the canonical focused region ID."""
        return self._state.focused_region_id

    def clear_focus_if(self, region_id: str) -> None:
        """Apply the navigation mutation requested by the production coordinator."""
        self.clear_focus_calls.append(region_id)
        if self._state.focused_region_id == region_id:
            self._state = self._state.with_focused_region(None).with_surface(
                AnalysisSurface.OVERVIEW
            )

    def clear_focus_only_if(self, region_id: str) -> None:
        """Clear a removed focus without changing the surface."""
        if self._state.focused_region_id == region_id:
            self._state = self._state.with_focused_region(None)

    def select_overview_region(self, _region_id: str | None) -> bool:
        """Accept Overview selection changes needed by the real widget."""
        return True

    def update_overview_view(self, **_state: object) -> None:
        """Accept persisted Overview table state needed by the real widget."""

    def update_structure_selection(
        self, *, region_ids: tuple[str, ...], line_ids: tuple[str, ...]
    ) -> None:
        """Accept Structure selection state needed by the real widget."""
        _ = region_ids, line_ids


class _Workspace:
    """Record surface focus and announcement effects."""

    current_right_page = RightPage.DETAIL
    current_bottom_page = BottomPage.PARAMETERS

    def __init__(self) -> None:
        self.focuses: list[str] = []
        self.announcements: list[str] = []

    def show_right_page(self, page: RightPage) -> None:
        self.current_right_page = page

    def show_bottom_page(self, page: BottomPage) -> None:
        self.current_bottom_page = page

    def apply_policy(self, policy: AnalysisSurfaceUiPolicy) -> None:
        self.current_right_page = policy.right_page
        self.current_bottom_page = policy.bottom_page

    def focus_right_page(self, page: RightPage | None = None) -> None:
        _ = page
        self.focuses.append("right")

    def focus_bottom_page(self, page: BottomPage | None = None) -> None:
        _ = page
        self.focuses.append("bottom")

    def announce(self, message: str) -> None:
        self.announcements.append(message)


class _Policies:
    """Record semantic surface policy commits."""

    def __init__(self) -> None:
        self.applied: list[AnalysisSurfaceUiPolicy] = []

    def apply(self, policy: AnalysisSurfaceUiPolicy) -> None:
        self.applied.append(policy)


class _Guard:
    """Allow the surface transition exercised by this regression test."""

    def fit_running(self) -> bool:
        return False

    def commit_pending_editor(self) -> bool:
        return True

    def focus_invalid_editor(self) -> None:
        raise AssertionError("No invalid editor is expected during removed-focus recovery")


class _Presentation:
    """Record Overview and Detail refresh effects."""

    def __init__(self, overview: StructureSidePanel | None = None) -> None:
        self.overview_refreshes = 0
        self.region_detail_refreshes: list[str] = []
        self._overview = overview

    def refresh_overview(self) -> None:
        self.overview_refreshes += 1
        if self._overview is not None:
            self._overview.refresh()

    def refresh_region_detail(self, region_id: str) -> None:
        self.region_detail_refreshes.append(region_id)


class _ModeShell:
    """Keep structure refresh execution inside Analysis and record overlays."""

    def __init__(self) -> None:
        self.overlay_refreshes: list[EditingMode] = []

    def get_current_mode(self) -> EditingMode:
        """Return the active mode."""
        return EditingMode.ANALYSIS

    def refresh_line_overlays_for_mode(self, mode: EditingMode) -> None:
        """Record the existing overlay refresh side effect."""
        self.overlay_refreshes.append(mode)


class _ShellTopologyOwner(QObject):
    """Exercise MainWindow's project-scoped topology adapter without full composition."""

    def __init__(
        self,
        *,
        project: SpectroscopyProject,
        focus: _AnalysisFocus,
        surface: AnalysisSurfaceCoordinator,
        mode_shell: _ModeShell,
    ) -> None:
        super().__init__()
        self.current_project: SpectroscopyProject | None = project
        self._analysis_navigation = focus
        self._analysis_surface_coordinator = surface
        self.mode_shell_coordinator = mode_shell
        self._region_topology_event_adapter: SpectrumModelEventAdapter | None = None
        self.set_project(project)

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Switch the project used by the production shell subscription."""
        self.current_project = project
        MainWindow._set_region_topology_project(cast("MainWindow", self), project)

    def _on_region_topology_changed(self, event: RegionTopologyChanged) -> None:
        """Delegate to the production shell handler."""
        MainWindow._on_region_topology_changed(cast("MainWindow", self), event)


class _FailingModelEventAdapter(SpectrumModelEventAdapter):
    """Inject one failing domain listener ahead of the real UI subscribers."""

    def apply(self, change_set: ChangeSet) -> None:
        """Fail before adapting the committed topology change."""
        _ = change_set
        raise RuntimeError("injected topology subscriber failure")


class _NoOpRangeHistoryPort:
    """Unused range dependency for topology history replay."""

    def apply_range(self, _snapshot: object, *, source: str) -> HistoryChangeSet:
        """Accept an unused range replay request."""
        _ = source
        return HistoryChangeSet.empty()


class _NoOpHistoryRefreshPort:
    """Reject unexpected legacy refresh targets for topology history."""

    def refresh(self, _target: object, _change_set: HistoryChangeSet) -> None:
        """Fail because topology history must publish through domain events only."""
        raise AssertionError("unexpected legacy topology refresh target")


@dataclass(slots=True)
class _Harness:
    """Real Detail UI plus the minimal shell collaborators under test."""

    project: SpectroscopyProject
    panel: RegionDetailPanel
    focus: _AnalysisFocus
    surface: AnalysisSurfaceCoordinator
    workspace: _Workspace
    policies: _Policies
    presentation: _Presentation
    mode_shell: _ModeShell
    overview: StructureSidePanel
    overview_refreshes: list[None]
    shell_owner: _ShellTopologyOwner

    def selector_region_ids(self) -> list[str]:
        """Return stable IDs currently shown by the real Detail selector."""
        selector = self.panel.findChild(QComboBox, "analysisDetailRegionSelector")
        assert selector is not None
        return [selector.itemData(index) for index in range(selector.count())]

    def selected_region_id(self) -> str | None:
        """Return the region ID currently displayed by the real selector."""
        selector = self.panel.findChild(QComboBox, "analysisDetailRegionSelector")
        assert selector is not None
        value = selector.currentData()
        return value if isinstance(value, str) else None

    def overview_region_ids(self) -> list[str]:
        """Return the region IDs currently listed by the real Overview tree."""
        tree = self.overview.findChild(QTreeWidget, "analysisStructureTree")
        assert tree is not None
        identifiers: list[str] = []
        for index in range(tree.topLevelItemCount()):
            payload = tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict) and payload.get("type") == "group":
                identifiers.append(payload["id"])
        return identifiers


def _line(line_id: str, region_id: str, rest_wavelength: float) -> AbsorptionLine:
    """Create one selectable line."""
    return AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=rest_wavelength,
        center_z=1.0,
        window_kms=150.0,
        region_id=region_id,
        multiplet_label="Ly alpha",
        transition_name="Ly alpha",
        oscillator_strength=0.1,
        gamma_value=1e8,
    )


def _project() -> SpectroscopyProject:
    """Create three regions, including a two-line region that can be split."""
    project = SpectroscopyProject(name="structure-detail-refresh")
    definitions = {
        "region-1": (("line-1", 1215.67), ("line-2", 1216.0)),
        "region-2": (("line-3", 1548.2),),
        "region-3": (("line-4", 1550.8),),
    }
    for region_id, line_definitions in definitions.items():
        line_ids = [line_id for line_id, _wavelength in line_definitions]
        project.absorption_regions[region_id] = AbsorptionRegion(
            region_id=region_id, line_ids=line_ids
        )
        for line_id, wavelength in line_definitions:
            project.absorption_lines[line_id] = _line(line_id, region_id, wavelength)
    return project


@pytest.fixture
def harness(qtbot: QtBot) -> _Harness:
    """Build a real Region Detail selector around mutable project topology."""
    project = _project()
    focus = _AnalysisFocus()
    editor = OptimizeEditor()
    parameter_mutation_usecase, tie_set_edit_usecase = build_region_detail_usecases()
    panel = RegionDetailPanel(
        optimize_editor=editor,
        analysis_focus=focus,
        mode_state=_ModeState(),
        model_addition_usecase=NoOpModelAdditionUseCase(),
        parameter_mutation_usecase=parameter_mutation_usecase,
        tie_set_edit_usecase=tie_set_edit_usecase,
        velocity_plot_active_provider=lambda: False,
        project_file_path_provider=lambda: None,
    )
    qtbot.addWidget(editor)
    qtbot.addWidget(panel)
    panel.set_project(project)
    overview = StructureSidePanel(navigation=cast("AnalysisOverviewNavigationPort", focus))
    qtbot.addWidget(overview)
    overview.set_project(project)
    overview_refreshes: list[None] = []
    overview.review_refresh_requested.connect(lambda: overview_refreshes.append(None))
    workspace = _Workspace()
    policies = _Policies()
    presentation = _Presentation(overview)
    surface = AnalysisSurfaceCoordinator(
        navigation=focus,
        workspace=workspace,
        policies=policies,
        guard=_Guard(),
        presentation=presentation,
    )
    mode_shell = _ModeShell()
    shell_owner = _ShellTopologyOwner(
        project=project, focus=focus, surface=surface, mode_shell=mode_shell
    )
    return _Harness(
        project=project,
        panel=panel,
        focus=focus,
        surface=surface,
        workspace=workspace,
        policies=policies,
        presentation=presentation,
        mode_shell=mode_shell,
        overview=overview,
        overview_refreshes=overview_refreshes,
        shell_owner=shell_owner,
    )


@dataclass(slots=True)
class _TopologyDestinations:
    """Real Overview plus the shell topology surface used by route tests."""

    overview: StructureSidePanel
    overview_refreshes: list[None]
    mode_shell: _ModeShell
    shell_owner: _ShellTopologyOwner


def _attach_topology_destinations(
    qtbot: QtBot, project: SpectroscopyProject
) -> _TopologyDestinations:
    """Attach real Overview and production shell observers to one project."""
    overview = StructureSidePanel()
    qtbot.addWidget(overview)
    overview.set_project(project)
    overview_refreshes: list[None] = []
    overview.review_refresh_requested.connect(lambda: overview_refreshes.append(None))

    focus = _AnalysisFocus()
    workspace = _Workspace()
    surface = AnalysisSurfaceCoordinator(
        navigation=focus,
        workspace=workspace,
        policies=_Policies(),
        guard=_Guard(),
        presentation=_Presentation(),
    )
    mode_shell = _ModeShell()
    shell_owner = _ShellTopologyOwner(
        project=project, focus=focus, surface=surface, mode_shell=mode_shell
    )
    return _TopologyDestinations(
        overview=overview,
        overview_refreshes=overview_refreshes,
        mode_shell=mode_shell,
        shell_owner=shell_owner,
    )


def _identify_registration_request(
    project: SpectroscopyProject,
) -> AtomicRegisterSelectedLinesRequest:
    """Build one valid Identify registration that creates a region."""
    temporary_line = project.identify_state.add_temporary_line(
        "C IV",
        1000.0,
        1005.0,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="civ-1548",
            rest_wavelength=1000.0,
            center_z=0.0,
            multiplet_id="civ-doublet",
            multiplet_label="C IV",
            transition_name="C IV 1548",
            oscillator_strength=0.19,
            gamma_value=2.64e8,
            tie_group_key="",
        ),
    )
    return AtomicRegisterSelectedLinesRequest(
        project=project,
        session=project.identify_state,
        temporary_lines=(
            TemporaryLineSnapshot(
                temporary_line_id=temporary_line.temporary_line_id,
                species=temporary_line.species,
                lambda_min=temporary_line.lambda_min,
                lambda_max=temporary_line.lambda_max,
                creation_method=temporary_line.creation_method,
                line_id=temporary_line.line_id,
                rest_wavelength=temporary_line.rest_wavelength,
                center_z=temporary_line.center_z,
                multiplet_id=temporary_line.multiplet_id,
                multiplet_label=temporary_line.multiplet_label,
                transition_name=temporary_line.transition_name,
                oscillator_strength=temporary_line.oscillator_strength,
                gamma_value=temporary_line.gamma_value,
                analysis_half_width=LineAnalysisHalfWidth(temporary_line.analysis_half_width_kms),
                tie_group_key=temporary_line.tie_group_key,
            ),
        ),
        existing_regions=(),
        region_line_memberships=(),
        multiplet_grouping_tolerance=DEFAULT_IDENTIFY_MULTIPLET_GROUPING_TOLERANCE,
        unknown_label="Unknown",
    )


def test_merge_commit_rebuilds_detail_selector_from_live_regions(harness: _Harness) -> None:
    """A merge must remove merged-away IDs while preserving the primary focus."""
    harness.focus.focus_region("region-1")
    harness.panel.reconcile_focus_with_selector()

    result = StructureOperationUseCase().merge_regions(
        harness.project, group_ids=["region-1", "region-2"], history_recorder=None
    )
    assert result is not None

    assert set(harness.selector_region_ids()) == set(harness.project.absorption_regions)
    assert "region-2" not in harness.selector_region_ids()
    assert harness.focus.focused_region_id() == "region-1"

    assert harness.mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]
    assert harness.overview_refreshes == [None]


def test_structure_coordinator_commit_rebuilds_real_overview_exactly_once(qtbot: QtBot) -> None:
    """One coordinator commit must rebuild the event-subscribed Overview exactly once."""
    project = _project()
    overview = StructureSidePanel()
    qtbot.addWidget(overview)
    overview.set_project(project)
    rebuilds: list[None] = []
    overview.review_refresh_requested.connect(lambda: rebuilds.append(None))
    coordinator = StructureInteractionCoordinator(
        operations=StructureOperationController(
            operation_adapter=StructureOperationAdapter(StructureOperationUseCase())
        ),
        ports=StructureInteractionPorts(
            project_provider=lambda: project,
            history_recorder_provider=lambda: None,
            focus_range_callback=lambda _start, _end: None,
            status_callback=lambda _message, _timeout, _undo_hint: None,
            delete_confirmation=lambda _impact, _project: True,
            unlink_confirmation=lambda _impact, _project: True,
            context_menu_parent=overview,
        ),
    )
    coordinator.connect_panel(overview)
    coordinator.handle_selection(["region-1", "region-2"], [])

    assert coordinator.execute_merge() is True

    assert len(rebuilds) == 1, (
        "one structure coordinator commit must rebuild the real Overview exactly once; "
        f"observed {len(rebuilds)} rebuilds"
    )


def test_identify_registration_reaches_overview_and_shell(qtbot: QtBot) -> None:
    """Identify registration must reach both topology-driven GUI destinations."""
    project = SpectroscopyProject(name="identify-topology-destinations")
    destinations = _attach_topology_destinations(qtbot, project)

    result = AtomicIdentifyRegistrationUseCase().register(_identify_registration_request(project))

    assert result.changed
    assert destinations.overview_refreshes == [None]
    assert destinations.mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]


def test_structure_undo_redo_reach_overview_and_shell(qtbot: QtBot) -> None:
    """Both history directions must use the same topology-driven GUI destinations."""
    project = _project()
    history = CommandHistory()
    history.set_applier(
        HistoryApplyUseCase(
            project_provider=lambda: project,
            range_port=_NoOpRangeHistoryPort(),
            refresh_port=_NoOpHistoryRefreshPort(),
            resolution_notifier_provider=lambda: None,
        )
    )
    recorder = HistoryRecorder(history, lambda: project)
    assert StructureOperationUseCase().merge_regions(
        project, group_ids=["region-1", "region-2"], history_recorder=recorder
    )
    destinations = _attach_topology_destinations(qtbot, project)

    assert history.undo().success
    assert history.redo().success

    assert destinations.overview_refreshes == [None, None]
    assert destinations.mode_shell.overlay_refreshes == [
        EditingMode.ANALYSIS,
        EditingMode.ANALYSIS,
    ]


def test_failing_subscriber_does_not_block_overview_or_shell(qtbot: QtBot) -> None:
    """One failing model subscriber must not suppress either later GUI subscriber."""
    project = _project()
    failing = _FailingModelEventAdapter(project.model)
    destinations = _attach_topology_destinations(qtbot, project)

    result = StructureOperationUseCase().merge_regions(
        project, group_ids=["region-1", "region-2"], history_recorder=None
    )

    assert result is not None
    assert destinations.overview_refreshes == [None]
    assert destinations.mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]
    failing.close()


def test_overview_refreshes_once_when_component_and_topology_events_share_commit(
    qtbot: QtBot,
) -> None:
    """Component events in one topology change set must not double-refresh Overview."""
    project = _project()
    component = AbsorberComponent(component_id="absorber", group_id="region-2")
    project.model.add_component_storage(component)
    destinations = _attach_topology_destinations(qtbot, project)
    changes = project.model.remove_component_storage(component).extend(
        RegionTopologyChanged(removed_region_ids=("region-2",))
    )

    project.model.publish_storage_changes(changes)

    assert destinations.overview_refreshes == [None]


def test_merge_commit_reprojects_surviving_non_first_focus_into_selector(
    harness: _Harness,
) -> None:
    """A surviving non-first Detail focus must remain displayed after a merge."""
    harness.focus.focus_region("region-3")
    harness.panel.reconcile_focus_with_selector()
    assert harness.selected_region_id() == "region-3"

    result = StructureOperationUseCase().merge_regions(
        harness.project, group_ids=["region-1", "region-2"], history_recorder=None
    )
    assert result is not None

    assert harness.selector_region_ids() == ["region-1", "region-3"]
    assert harness.focus.focused_region_id() == "region-3"
    assert harness.selected_region_id() == "region-3"


def test_merge_commit_recovers_removed_focus_through_shell_surface_coordinator(
    harness: _Harness,
) -> None:
    """Shell recovery must leave the Overview rebuild to the panel's own subscription."""
    harness.focus.focus_region("region-2")
    harness.panel.reconcile_focus_with_selector()
    harness.surface.restore()
    harness.focus.focus_calls.clear()
    harness.policies.applied.clear()
    harness.presentation.region_detail_refreshes.clear()

    result = StructureOperationUseCase().merge_regions(
        harness.project, group_ids=["region-1", "region-2"], history_recorder=None
    )
    assert result is not None

    assert set(harness.selector_region_ids()) == set(harness.project.absorption_regions)
    assert harness.focus.clear_focus_calls == ["region-2"]
    assert harness.focus.focused_region_id() is None
    assert harness.focus.state.surface is AnalysisSurface.OVERVIEW
    assert harness.surface.panel_state is PanelState.OVERVIEW_SUMMARY
    assert [policy.panel_state for policy in harness.policies.applied] == [
        PanelState.OVERVIEW_SUMMARY
    ]
    assert harness.presentation.overview_refreshes == 0
    assert harness.presentation.region_detail_refreshes == []
    assert harness.workspace.focuses == ["bottom"]
    assert len(harness.workspace.announcements) == 1
    assert harness.workspace.announcements[0]
    assert harness.mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]
    assert harness.overview_refreshes == [None]


def test_merge_commit_rebuilds_the_overview_tree_when_it_absorbs_the_focused_region(
    harness: _Harness,
) -> None:
    """A merge that removes the Detail focus must still rebuild the Overview tree."""
    harness.focus.focus_region("region-2")
    harness.panel.reconcile_focus_with_selector()
    assert harness.surface.open_structure_editor() is True
    assert harness.overview_region_ids() == ["region-1", "region-2", "region-3"]

    result = StructureOperationUseCase().merge_regions(
        harness.project, group_ids=["region-1", "region-2"], history_recorder=None
    )
    assert result is not None

    assert harness.overview_region_ids() == list(harness.project.absorption_regions)


def test_merge_commit_keeps_the_structure_editor_open_for_a_stale_detail_focus(
    harness: _Harness,
) -> None:
    """A merge run from the Structure editor must not evict it to the summary."""
    harness.focus.focus_region("region-2")
    harness.panel.reconcile_focus_with_selector()
    assert harness.surface.open_structure_editor() is True
    harness.policies.applied.clear()
    harness.workspace.focuses.clear()
    harness.presentation.overview_refreshes = 0

    result = StructureOperationUseCase().merge_regions(
        harness.project, group_ids=["region-1", "region-2"], history_recorder=None
    )
    assert result is not None

    assert harness.surface.panel_state is PanelState.OVERVIEW_STRUCTURE
    assert harness.policies.applied == []
    assert harness.workspace.focuses == []
    assert harness.workspace.announcements == []
    assert harness.focus.clear_focus_calls == ["region-2"]
    assert harness.focus.focused_region_id() is None
    assert harness.mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]


@pytest.mark.parametrize("shell_first", [False, True], ids=["detail-first", "shell-first"])
def test_removed_focus_recovery_is_independent_of_subscriber_order(
    qtbot: QtBot, shell_first: bool
) -> None:
    """Detail and shell must converge regardless of their model subscription order."""
    project = _project()
    focus = _AnalysisFocus()
    focus.focus_region("region-2")
    workspace = _Workspace()
    policies = _Policies()
    presentation = _Presentation()
    surface = AnalysisSurfaceCoordinator(
        navigation=focus,
        workspace=workspace,
        policies=policies,
        guard=_Guard(),
        presentation=presentation,
    )
    mode_shell = _ModeShell()
    shell_owner: _ShellTopologyOwner | None = None
    if shell_first:
        shell_owner = _ShellTopologyOwner(
            project=project, focus=focus, surface=surface, mode_shell=mode_shell
        )

    editor = OptimizeEditor()
    parameter_mutation_usecase, tie_set_edit_usecase = build_region_detail_usecases()
    panel = RegionDetailPanel(
        optimize_editor=editor,
        analysis_focus=focus,
        mode_state=_ModeState(),
        model_addition_usecase=NoOpModelAdditionUseCase(),
        parameter_mutation_usecase=parameter_mutation_usecase,
        tie_set_edit_usecase=tie_set_edit_usecase,
        velocity_plot_active_provider=lambda: False,
        project_file_path_provider=lambda: None,
    )
    qtbot.addWidget(editor)
    qtbot.addWidget(panel)
    panel.set_project(project)
    panel.reconcile_focus_with_selector()
    if shell_owner is None:
        shell_owner = _ShellTopologyOwner(
            project=project, focus=focus, surface=surface, mode_shell=mode_shell
        )

    surface.restore()
    policies.applied.clear()
    presentation.overview_refreshes = 0
    workspace.focuses.clear()
    workspace.announcements.clear()
    focus.clear_focus_calls.clear()

    result = StructureOperationUseCase().merge_regions(
        project, group_ids=["region-1", "region-2"], history_recorder=None
    )

    selector = panel.findChild(QComboBox, "analysisDetailRegionSelector")
    assert selector is not None
    assert result is not None
    assert {selector.itemData(index) for index in range(selector.count())} == set(
        project.absorption_regions
    )
    assert focus.focused_region_id() is None
    assert focus.state.surface is AnalysisSurface.OVERVIEW
    assert surface.panel_state is PanelState.OVERVIEW_SUMMARY
    assert [policy.panel_state for policy in policies.applied] == [PanelState.OVERVIEW_SUMMARY]
    assert presentation.overview_refreshes == 0
    assert workspace.focuses == ["bottom"]
    assert len(workspace.announcements) == 1
    assert mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]


def test_split_commit_adds_new_region_to_detail_selector(harness: _Harness) -> None:
    """A split must expose its newly created region and retain the source focus."""
    harness.focus.focus_region("region-1")
    harness.panel.reconcile_focus_with_selector()
    original_region_ids = set(harness.project.absorption_regions)

    result = StructureOperationUseCase().split_lines(
        harness.project, linked_line_ids=["line-1"], history_recorder=None
    )
    assert result is not None
    new_region_ids = set(harness.project.absorption_regions) - original_region_ids
    assert len(new_region_ids) == 1

    assert set(harness.selector_region_ids()) == set(harness.project.absorption_regions)
    assert new_region_ids <= set(harness.selector_region_ids())
    assert harness.focus.focused_region_id() == "region-1"


def test_project_switch_detaches_old_topology_source_and_attaches_new_one(
    harness: _Harness,
) -> None:
    """Only the currently attached project may drive Detail topology refreshes."""
    old_project = harness.project
    replacement = _project()
    harness.panel.set_project(replacement)
    harness.overview.set_project(replacement)
    harness.shell_owner.set_project(replacement)
    harness.mode_shell.overlay_refreshes.clear()
    harness.focus.focus_region("region-3")
    harness.panel.reconcile_focus_with_selector()

    old_project.model.publish_storage_changes(
        ChangeSet.of(RegionTopologyChanged(removed_region_ids=("region-3",)))
    )

    assert harness.focus.focused_region_id() == "region-3"
    assert harness.mode_shell.overlay_refreshes == []

    replacement.absorption_regions["region-4"] = AbsorptionRegion(
        region_id="region-4", line_ids=["line-5"]
    )
    replacement.absorption_lines["line-5"] = _line("line-5", "region-4", 1600.0)
    replacement.model.publish_storage_changes(
        ChangeSet.of(RegionTopologyChanged(created_region_ids=("region-4",)))
    )

    assert set(harness.selector_region_ids()) == set(replacement.absorption_regions)
    assert harness.focus.focused_region_id() == "region-3"
    assert harness.selected_region_id() == "region-3"
    assert harness.mode_shell.overlay_refreshes == [EditingMode.ANALYSIS]
