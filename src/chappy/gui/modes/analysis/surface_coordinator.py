"""Surface transitions inside the single top-level Analysis mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QCoreApplication

from chappy.gui.modes.analysis.contracts import (
    AnalysisSurfacePresentationPort,
    AnalysisWorkspacePort,
    PanelState,
)
from chappy.gui.modes.analysis.surface_policy import (
    AnalysisSurfaceUiPolicy,
    default_policy_for_surface,
    policy_for_panel_state,
)
from chappy.gui.modes.common.analysis_navigation import AnalysisSurface

if TYPE_CHECKING:
    from chappy.gui.modes.analysis.intents import OpenAnalysisRegionIntent
    from chappy.gui.modes.common.analysis_navigation import AnalysisNavigationState


class AnalysisNavigationPort(Protocol):
    """Navigation mutations required by Analysis surface transitions."""

    @property
    def state(self) -> AnalysisNavigationState:
        """Return current ID-only navigation state."""

    def focus_region(self, region_id: str) -> bool:
        """Validate and focus a region in the current project."""

    def set_surface(self, surface: AnalysisSurface) -> None:
        """Persist the selected Analysis surface."""

    def clear_focus_if(self, region_id: str) -> None:
        """Clear canonical focus only when it still names a removed region."""


class AnalysisSurfacePolicyPort(Protocol):
    """Shell-owned atomic semantic policy application."""

    def apply(self, policy: AnalysisSurfaceUiPolicy) -> None:
        """Apply one complete workspace/spectrum/shell policy."""


class AnalysisTransitionGuardPort(Protocol):
    """Fit and editor guards checked at command execution time."""

    def fit_running(self) -> bool:
        """Return whether a fit currently prevents navigation."""

    def commit_pending_editor(self) -> bool:
        """Commit pending Detail edits, returning false for invalid input."""

    def focus_invalid_editor(self) -> None:
        """Focus the editor that rejected a transition."""


class AnalysisSurfaceCoordinator:
    """Own open/back/structure/restore transitions without switching mode."""

    def __init__(
        self,
        *,
        navigation: AnalysisNavigationPort,
        workspace: AnalysisWorkspacePort,
        policies: AnalysisSurfacePolicyPort,
        guard: AnalysisTransitionGuardPort,
        presentation: AnalysisSurfacePresentationPort,
    ) -> None:
        self._navigation = navigation
        self._workspace = workspace
        self._policies = policies
        self._guard = guard
        self._presentation = presentation
        self._panel_state = PanelState.OVERVIEW_SUMMARY

    @property
    def panel_state(self) -> PanelState:
        """Return the current nested Analysis panel state."""
        return self._panel_state

    def restore(self) -> None:
        """Apply the persisted surface after entering Analysis or changing project."""
        surface = self._navigation.state.surface
        policy = default_policy_for_surface(surface)
        self._commit(policy, persist_surface=False)
        if surface is AnalysisSurface.REGION_DETAIL:
            region_id = self._navigation.state.focused_region_id
            if region_id is None:
                msg = "Restoring the Region Detail surface requires a focused region id."
                raise RuntimeError(msg)
            self._presentation.refresh_region_detail(region_id)
        else:
            self._presentation.refresh_overview()

    def open_region(self, intent: OpenAnalysisRegionIntent) -> bool:
        """Open one validated region only from an explicit user intent."""
        if self._guard.fit_running() or not self._navigation.focus_region(intent.region_id):
            return False
        policy = policy_for_panel_state(PanelState.REGION_DETAIL)
        self._commit(policy)
        self._presentation.refresh_region_detail(intent.region_id)
        self._workspace.focus_right_page()
        self._workspace.announce(
            QCoreApplication.translate("AnalysisSurfaceCoordinator", "Region Detail opened")
        )
        return True

    def back_to_overview(self) -> bool:
        """Return to Overview while keeping the current region focus."""
        if not self._can_leave_detail():
            return False
        policy = policy_for_panel_state(PanelState.OVERVIEW_SUMMARY)
        self._commit(policy)
        self._presentation.refresh_overview()
        self._workspace.focus_bottom_page()
        self._workspace.announce(
            QCoreApplication.translate(
                "AnalysisSurfaceCoordinator", "Returned to Analysis Overview"
            )
        )
        return True

    def open_structure_editor(self) -> bool:
        """Open the nested Structure editor without creating a third surface."""
        if self._guard.fit_running():
            return False
        self._commit(policy_for_panel_state(PanelState.OVERVIEW_STRUCTURE))
        self._workspace.focus_right_page()
        return True

    def close_structure_editor(self) -> None:
        """Return from Structure to the Overview summary."""
        self._commit(policy_for_panel_state(PanelState.OVERVIEW_SUMMARY))
        self._presentation.refresh_overview()
        self._workspace.focus_bottom_page()

    def handle_focused_region_removed(self, region_id: str) -> None:
        """Recover to Overview when the currently focused Detail region is deleted."""
        if self._navigation.state.focused_region_id != region_id:
            return
        self._navigation.clear_focus_if(region_id)
        # Structure edits that remove the focused region are performed from the
        # Overview itself, so evicting that page would close the editor in use.
        if self._panel_state is not PanelState.REGION_DETAIL:
            return
        self._commit(policy_for_panel_state(PanelState.OVERVIEW_SUMMARY))
        self._workspace.focus_bottom_page()
        self._workspace.announce(
            QCoreApplication.translate(
                "AnalysisSurfaceCoordinator", "The open region was deleted; returned to Overview"
            )
        )

    def can_leave_analysis(self) -> bool:
        """Return whether top-level mode navigation may leave Analysis."""
        return self._can_leave_detail()

    def structure_actions_enabled(self) -> bool:
        """Return whether destructive Structure commands are in scope."""
        return self._panel_state is PanelState.OVERVIEW_STRUCTURE

    def _can_leave_detail(self) -> bool:
        if self._guard.fit_running():
            return False
        if self._panel_state is not PanelState.REGION_DETAIL:
            return True
        if self._guard.commit_pending_editor():
            return True
        self._guard.focus_invalid_editor()
        return False

    def _commit(self, policy: AnalysisSurfaceUiPolicy, *, persist_surface: bool = True) -> None:
        previous_panel_state = self._panel_state
        self._panel_state = policy.panel_state
        try:
            self._policies.apply(policy)
        except Exception:
            self._panel_state = previous_panel_state
            raise
        if persist_surface:
            self._navigation.set_surface(policy.surface)


__all__ = [
    "AnalysisNavigationPort",
    "AnalysisSurfaceCoordinator",
    "AnalysisSurfacePolicyPort",
    "AnalysisTransitionGuardPort",
]
