"""Focused tests for ModeLifecycleRouter."""

from __future__ import annotations

from dataclasses import dataclass

from chappy.core.editing_mode import EditingMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.common import ModeRefreshRequest
from chappy.gui.shell.mode_lifecycle_router import ModeLifecycleRouter


@dataclass
class _LifecycleProbe:
    project: SpectroscopyProject | None = None
    activate_count: int = 0
    deactivate_count: int = 0
    refreshes: list[ModeRefreshRequest] | None = None

    def __post_init__(self) -> None:
        self.refreshes = []

    def set_project(self, project: SpectroscopyProject | None) -> None:
        self.project = project

    def activate(self) -> None:
        self.activate_count += 1

    def deactivate(self) -> None:
        self.deactivate_count += 1

    def refresh(self, request: ModeRefreshRequest) -> None:
        self.refreshes.append(request)


def test_mode_lifecycle_router_activates_and_deactivates_modes() -> None:
    """Lifecycle router should move activation ownership between modes."""
    structure = _LifecycleProbe()
    identify = _LifecycleProbe()
    router = ModeLifecycleRouter({EditingMode.ANALYSIS: structure, EditingMode.IDENTIFY: identify})

    router.sync_mode(EditingMode.ANALYSIS, reason="mode-changed")
    router.sync_mode(EditingMode.IDENTIFY, reason="mode-changed")

    assert structure.activate_count == 1
    assert structure.deactivate_count == 1
    assert structure.refreshes == [
        ModeRefreshRequest(mode=EditingMode.ANALYSIS, reason="mode-changed")
    ]
    assert identify.activate_count == 1
    assert identify.deactivate_count == 0
    assert identify.refreshes == [
        ModeRefreshRequest(mode=EditingMode.IDENTIFY, reason="mode-changed")
    ]


def test_mode_lifecycle_router_refreshes_line_overlays_through_lifecycle() -> None:
    """Line-overlay refresh should be delegated to the lifecycle owner."""
    optimize = _LifecycleProbe()
    router = ModeLifecycleRouter({EditingMode.ANALYSIS: optimize})

    router.refresh_line_overlays(EditingMode.ANALYSIS)

    assert optimize.refreshes == [
        ModeRefreshRequest(mode=EditingMode.ANALYSIS, reason="line-overlays-refreshed")
    ]


def test_mode_lifecycle_router_propagates_project() -> None:
    """Project propagation should touch every registered lifecycle."""
    identify = _LifecycleProbe()
    analysis = _LifecycleProbe()
    router = ModeLifecycleRouter({EditingMode.IDENTIFY: identify, EditingMode.ANALYSIS: analysis})
    project = SpectroscopyProject()

    router.set_project(project)

    assert identify.project is project
    assert analysis.project is project
