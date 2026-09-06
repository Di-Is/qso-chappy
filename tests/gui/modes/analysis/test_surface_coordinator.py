"""Tests for Analysis surface transitions inside one top-level mode."""

from __future__ import annotations

from dataclasses import replace

from chappy.gui.modes.analysis.contracts import BottomPage, PanelState, RightPage
from chappy.gui.modes.analysis.intents import OpenAnalysisRegionIntent
from chappy.gui.modes.analysis.surface_coordinator import AnalysisSurfaceCoordinator
from chappy.gui.modes.common.analysis_navigation import AnalysisNavigationState, AnalysisSurface


class _Navigation:
    def __init__(self) -> None:
        self.state = AnalysisNavigationState()
        self.valid_ids = {"region-1"}

    def focus_region(self, region_id: str) -> bool:
        if region_id not in self.valid_ids:
            return False
        self.state = self.state.with_focused_region(region_id)
        return True

    def set_surface(self, surface: AnalysisSurface) -> None:
        self.state = self.state.with_surface(surface)

    def clear_focus_if(self, region_id: str) -> None:
        if self.state.focused_region_id == region_id:
            self.state = self.state.with_focused_region(None).with_surface(
                AnalysisSurface.OVERVIEW
            )


class _Workspace:
    current_right_page = RightPage.SUMMARY
    current_bottom_page = BottomPage.REVIEW

    def __init__(self) -> None:
        self.focuses: list[str] = []
        self.announcements: list[str] = []

    def show_right_page(self, page: RightPage) -> None:
        self.current_right_page = page

    def show_bottom_page(self, page: BottomPage) -> None:
        self.current_bottom_page = page

    def apply_policy(self, policy: object) -> None:
        _ = policy

    def focus_right_page(self, page: RightPage | None = None) -> None:
        _ = page
        self.focuses.append("right")

    def focus_bottom_page(self, page: BottomPage | None = None) -> None:
        _ = page
        self.focuses.append("bottom")

    def announce(self, message: str) -> None:
        self.announcements.append(message)


class _Policies:
    def __init__(self) -> None:
        self.states: list[PanelState] = []

    def apply(self, policy: object) -> None:
        self.states.append(policy.panel_state)


class _Guard:
    def __init__(self) -> None:
        self.running = False
        self.commit_result = True
        self.invalid_focus_count = 0

    def fit_running(self) -> bool:
        return self.running

    def commit_pending_editor(self) -> bool:
        return self.commit_result

    def focus_invalid_editor(self) -> None:
        self.invalid_focus_count += 1


class _Presentation:
    def __init__(self) -> None:
        self.overview_refreshes = 0
        self.region_detail_refreshes: list[str] = []

    def refresh_overview(self) -> None:
        self.overview_refreshes += 1

    def refresh_region_detail(self, region_id: str) -> None:
        self.region_detail_refreshes.append(region_id)


def _coordinator() -> tuple[
    AnalysisSurfaceCoordinator, _Navigation, _Workspace, _Policies, _Guard, _Presentation
]:
    navigation = _Navigation()
    workspace = _Workspace()
    policies = _Policies()
    guard = _Guard()
    presentation = _Presentation()
    coordinator = AnalysisSurfaceCoordinator(
        navigation=navigation,
        workspace=workspace,
        policies=policies,
        guard=guard,
        presentation=presentation,
    )
    return coordinator, navigation, workspace, policies, guard, presentation


def test_open_and_back_change_surface_without_top_level_mode_signal() -> None:
    coordinator, navigation, workspace, policies, _guard, presentation = _coordinator()

    assert coordinator.open_region(OpenAnalysisRegionIntent("region-1")) is True
    assert navigation.state.surface is AnalysisSurface.REGION_DETAIL
    assert navigation.state.focused_region_id == "region-1"
    assert policies.states == [PanelState.REGION_DETAIL]
    assert presentation.region_detail_refreshes == ["region-1"]

    assert coordinator.back_to_overview() is True
    assert navigation.state.surface is AnalysisSurface.OVERVIEW
    assert policies.states[-1] is PanelState.OVERVIEW_SUMMARY
    assert workspace.focuses == ["right", "bottom"]
    assert presentation.overview_refreshes == 1


def test_fit_and_invalid_editor_guards_block_transition_and_restore_focus() -> None:
    coordinator, navigation, _workspace, policies, guard, presentation = _coordinator()
    navigation.state = replace(
        navigation.state, surface=AnalysisSurface.REGION_DETAIL, focused_region_id="region-1"
    )
    coordinator.restore()
    assert presentation.region_detail_refreshes == ["region-1"]

    guard.running = True
    assert coordinator.back_to_overview() is False
    guard.running = False
    guard.commit_result = False
    assert coordinator.back_to_overview() is False

    assert policies.states == [PanelState.REGION_DETAIL]
    assert guard.invalid_focus_count == 1
    assert presentation.overview_refreshes == 0


def test_structure_is_nested_overview_state() -> None:
    coordinator, navigation, _workspace, policies, _guard, presentation = _coordinator()

    assert coordinator.open_structure_editor() is True
    assert coordinator.panel_state is PanelState.OVERVIEW_STRUCTURE
    assert navigation.state.surface is AnalysisSurface.OVERVIEW
    coordinator.close_structure_editor()

    assert policies.states == [PanelState.OVERVIEW_STRUCTURE, PanelState.OVERVIEW_SUMMARY]
    assert presentation.overview_refreshes == 1


def test_restore_overview_surface_refreshes_overview() -> None:
    coordinator, navigation, _workspace, _policies, _guard, presentation = _coordinator()
    navigation.state = replace(navigation.state, surface=AnalysisSurface.OVERVIEW)

    coordinator.restore()

    assert presentation.overview_refreshes == 1
    assert presentation.region_detail_refreshes == []


def test_handle_focused_region_removed_leaves_the_overview_rebuild_to_the_panel() -> None:
    coordinator, navigation, _workspace, _policies, _guard, presentation = _coordinator()
    navigation.state = replace(
        navigation.state, surface=AnalysisSurface.REGION_DETAIL, focused_region_id="region-1"
    )
    coordinator.restore()
    presentation.region_detail_refreshes.clear()
    presentation.overview_refreshes = 0

    coordinator.handle_focused_region_removed("region-1")

    assert presentation.overview_refreshes == 0
    assert presentation.region_detail_refreshes == []
