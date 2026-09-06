"""Focused shell contracts for the atomic Analysis cutover."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from chappy.core.editing_mode import EditingMode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.contracts import PanelState
from chappy.gui.modes.common.analysis_navigation import (
    AnalysisSurface,
    OpenAnalysisRegionIntent,
    OpenAnalysisStructureIntent,
)
from chappy.gui.common.shared_operations import AnalysisOperationSurface
from chappy.gui.shell.main_window import MainWindow


def _project() -> SpectroscopyProject:
    project = SpectroscopyProject(name="analysis-cutover")
    project.absorption_lines["line-1"] = AbsorptionLine(
        line_id="line-1",
        species="H I",
        rest_wavelength=1215.67,
        center_z=1.0,
        window_kms=120.0,
        multiplet_label="Ly alpha",
        transition_name="Ly alpha",
        oscillator_strength=0.1,
        gamma_value=1.0e8,
        region_id="region-1",
    )
    project.absorption_regions["region-1"] = AbsorptionRegion(
        region_id="region-1", line_ids=["line-1"]
    )
    return project


class _Navigation:
    """Navigation double recording the shell-driven Analysis entry order."""

    def __init__(self, calls: list[tuple[str, object]], *, capable_region_id: str) -> None:
        self._calls = calls
        self._capable_region_id = capable_region_id

    def focus_region(self, region_id: str) -> bool:
        self._calls.append(("focus", region_id))
        return region_id == self._capable_region_id

    def set_surface(self, surface: AnalysisSurface) -> None:
        self._calls.append(("surface", surface))


class _ModeShell:
    """Mode shell double recording top-level mode switches."""

    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self._calls = calls

    def switch_mode(self, mode: EditingMode) -> None:
        self._calls.append(("mode", mode))


def test_identify_open_intent_uses_focus_destination_mode_order() -> None:
    calls: list[tuple[str, object]] = []
    window = SimpleNamespace(
        _analysis_navigation=_Navigation(calls, capable_region_id="region-1"),
        mode_shell_coordinator=_ModeShell(calls),
    )

    MainWindow.handle_identify_open_analysis_region(
        cast("MainWindow", window), OpenAnalysisRegionIntent("region-1")
    )

    assert calls == [
        ("focus", "region-1"),
        ("surface", AnalysisSurface.REGION_DETAIL),
        ("mode", EditingMode.ANALYSIS),
    ]


def test_identify_open_intent_stops_when_focus_rejects_the_region() -> None:
    calls: list[tuple[str, object]] = []
    window = SimpleNamespace(
        _analysis_navigation=_Navigation(calls, capable_region_id="region-1"),
        mode_shell_coordinator=_ModeShell(calls),
    )

    MainWindow.handle_identify_open_analysis_region(
        cast("MainWindow", window), OpenAnalysisRegionIntent("missing")
    )

    assert calls == [("focus", "missing")]


def test_identify_structure_intent_opens_the_editor_after_entering_analysis() -> None:
    calls: list[tuple[str, object]] = []
    panel = SimpleNamespace(
        restore_selection=lambda region_ids, line_ids: calls.append(
            ("select", (tuple(region_ids), tuple(line_ids)))
        )
    )
    window = SimpleNamespace(
        _analysis_navigation=_Navigation(calls, capable_region_id="region-1"),
        mode_shell_coordinator=_ModeShell(calls),
        open_analysis_structure=lambda: bool(calls.append(("structure", True))) or True,
        _require_dock_coordinator=lambda: SimpleNamespace(structure_panel=panel),
    )

    MainWindow.handle_identify_open_analysis_structure(
        cast("MainWindow", window), OpenAnalysisStructureIntent("region-1")
    )

    assert calls == [
        ("focus", "region-1"),
        ("surface", AnalysisSurface.OVERVIEW),
        ("mode", EditingMode.ANALYSIS),
        ("structure", True),
        ("select", (("region-1",), ())),
    ]


def test_identify_structure_intent_stops_when_focus_rejects_the_region() -> None:
    calls: list[tuple[str, object]] = []
    window = SimpleNamespace(
        _analysis_navigation=_Navigation(calls, capable_region_id="region-1"),
        mode_shell_coordinator=_ModeShell(calls),
        open_analysis_structure=lambda: (_ for _ in ()).throw(AssertionError),
    )

    MainWindow.handle_identify_open_analysis_structure(
        cast("MainWindow", window), OpenAnalysisStructureIntent("missing")
    )

    assert calls == [("focus", "missing")]


def test_back_to_overview_focuses_current_region_row() -> None:
    calls: list[tuple[str, object]] = []
    panel = SimpleNamespace(
        set_structure_editor_visible=lambda visible: calls.append(("structure", visible)),
        focus_review_region=lambda region_id: calls.append(("focus", region_id)) or True,
    )
    window = SimpleNamespace(
        _analysis_navigation=SimpleNamespace(state=SimpleNamespace(focused_region_id="region-1")),
        _require_analysis_surface_coordinator=lambda: SimpleNamespace(
            back_to_overview=lambda: True
        ),
        _require_dock_coordinator=lambda: SimpleNamespace(structure_panel=panel),
    )

    assert MainWindow.back_to_analysis_overview(cast("MainWindow", window)) is True
    assert calls == [("structure", False), ("focus", "region-1")]


def _tutorial_surface_window(
    focused_region_id: str | None, project: SpectroscopyProject | None
) -> SimpleNamespace:
    window = SimpleNamespace(
        opened=[],
        current_project=project,
        _analysis_navigation=SimpleNamespace(
            state=SimpleNamespace(focused_region_id=focused_region_id)
        ),
    )
    coordinator = SimpleNamespace(
        panel_state=None, open_region=lambda intent: window.opened.append(intent.region_id) or True
    )
    window._require_analysis_surface_coordinator = lambda: coordinator
    window._tutorial_region_exists = MainWindow._tutorial_region_exists.__get__(window)
    window._first_tutorial_region_id = MainWindow._first_tutorial_region_id.__get__(window)
    return window


def test_tutorial_region_detail_falls_back_when_focused_region_is_stale() -> None:
    project = _project()
    window = _tutorial_surface_window("merged-away", project)

    applied = MainWindow._switch_tutorial_analysis_surface(
        cast("MainWindow", window), AnalysisOperationSurface.REGION_DETAIL
    )

    assert applied is True
    assert window.opened == ["region-1"]


def test_tutorial_region_detail_fallback_skips_unassigned_region() -> None:
    project = SpectroscopyProject(name="unassigned-only")
    project.absorption_regions[UNASSIGNED_REGION_ID] = AbsorptionRegion(
        region_id=UNASSIGNED_REGION_ID, line_ids=[]
    )
    window = _tutorial_surface_window(None, project)

    applied = MainWindow._switch_tutorial_analysis_surface(
        cast("MainWindow", window), AnalysisOperationSurface.REGION_DETAIL
    )

    assert applied is False
    assert window.opened == []


def test_tutorial_region_detail_uses_valid_focused_region() -> None:
    project = _project()
    window = _tutorial_surface_window("region-1", project)

    applied = MainWindow._switch_tutorial_analysis_surface(
        cast("MainWindow", window), AnalysisOperationSurface.REGION_DETAIL
    )

    assert applied is True
    assert window.opened == ["region-1"]


def test_tutorial_region_detail_does_not_reopen_an_already_open_region() -> None:
    project = _project()
    window = _tutorial_surface_window("region-1", project)
    window._require_analysis_surface_coordinator().panel_state = PanelState.REGION_DETAIL

    applied = MainWindow._switch_tutorial_analysis_surface(
        cast("MainWindow", window), AnalysisOperationSurface.REGION_DETAIL
    )

    assert applied is True
    assert window.opened == []
