"""Tests for identify panel attach and signal wiring."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
from chappy.gui.modes.identify.panel_connector import (
    IdentifyPanelConnector,
    IdentifyPanelConnectorPorts,
)


class _Signal:
    """Small signal double for connector tests."""

    def __init__(self) -> None:
        """Initialize callback storage."""
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Connect a callback."""
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., None]) -> None:
        """Disconnect a callback."""
        self._callbacks.remove(callback)

    def emit(self, *args: Any) -> None:
        """Emit arguments to connected callbacks."""
        for callback in list(self._callbacks):
            callback(*args)


class _Panel:
    """Panel double with the signal surface used by the connector."""

    def __init__(self, events: list[str]) -> None:
        """Initialize panel signals."""
        self.preset_changed = _Signal()
        self.reference_line_changed = _Signal()
        self.manage_presets_requested = _Signal()
        self.sigma_threshold_changed = _Signal()
        self.new_candidate_analysis_half_width_changed = _Signal()
        self.candidate_activated = _Signal()
        self.temporary_delete_requested = _Signal()
        self.temporary_clear_requested = _Signal()
        self.registration_requested = _Signal()
        self.group_focus_requested = _Signal()
        self.line_focus_requested = _Signal()
        self.region_open_requested = _Signal()
        self.region_structure_edit_requested = _Signal()
        self._events = events

    def set_sigma_threshold(self, value: float) -> None:
        """Record the initial sigma threshold."""
        self._events.append(f"sigma:{value:.1f}")

    def set_new_candidate_analysis_half_width(self, value: NewCandidateAnalysisHalfWidth) -> None:
        """Record the initial future-candidate half-width."""
        self._events.append(f"new_candidate_half_width:{value.kms:.1f}")


def _build_connector(events: list[str]) -> tuple[IdentifyPanelConnector, dict[str, _Panel | None]]:
    state: dict[str, _Panel | None] = {"panel": None}
    connector = IdentifyPanelConnector(
        IdentifyPanelConnectorPorts(
            panel_provider=lambda: state["panel"],
            panel_setter=lambda panel: (
                events.append("panel_set"),
                state.__setitem__("panel", panel),
            ),
            preset_panel_setter=lambda _panel: events.append("preset_panel"),
            preset_refresh_callback=lambda: events.append("preset_refresh"),
            preset_changed_callback=lambda _preset_id: events.append("preset_changed"),
            reference_line_changed_callback=lambda _line_id: events.append("reference_changed"),
            manage_presets_callback=lambda: events.append("manage_presets"),
            sigma_threshold_provider=lambda: 42.0,
            sigma_threshold_changed_callback=lambda _value: events.append("sigma_changed"),
            new_candidate_analysis_half_width_provider=lambda: NewCandidateAnalysisHalfWidth(
                200.0
            ),
            new_candidate_analysis_half_width_changed_callback=lambda _value: events.append(
                "new_candidate_half_width_changed"
            ),
            candidate_activated_callback=lambda _candidate_id: events.append("candidate"),
            temporary_delete_callback=lambda _temporary_line_ids: events.append("delete"),
            temporary_clear_callback=lambda: events.append("clear"),
            registration_requested_callback=lambda _selected_ids: events.append("register"),
            group_focus_callback=lambda _group_id, _min_wave, _max_wave: events.append(
                "group_focus"
            ),
            line_focus_callback=lambda _temporary_line_id, _min_wave, _max_wave: events.append(
                "line_focus"
            ),
            region_open_callback=lambda _region_id: events.append("region_open"),
            region_structure_edit_callback=lambda _region_id: events.append(
                "region_structure_edit"
            ),
            refresh_candidates_callback=lambda: events.append("refresh_candidates"),
            refresh_workflow_callback=lambda: events.append("refresh_workflow"),
        )
    )
    return connector, state


def test_set_panel_initializes_in_expected_order() -> None:
    events: list[str] = []
    connector, _state = _build_connector(events)
    panel = _Panel(events)

    connector.set_panel(panel)

    assert events == [
        "panel_set",
        "preset_panel",
        "sigma:42.0",
        "new_candidate_half_width:200.0",
        "preset_refresh",
        "refresh_candidates",
        "refresh_workflow",
    ]


def test_repeated_attach_does_not_duplicate_signal_handlers() -> None:
    events: list[str] = []
    connector, _state = _build_connector(events)
    panel = _Panel(events)

    connector.set_panel(panel)
    connector.set_panel(panel)
    events.clear()

    panel.candidate_activated.emit("candidate-1")

    assert events == ["candidate"]


def test_detach_disconnects_previous_panel_signals() -> None:
    events: list[str] = []
    connector, _state = _build_connector(events)
    panel = _Panel(events)

    connector.set_panel(panel)
    connector.set_panel(None)
    events.clear()

    panel.candidate_activated.emit("candidate-1")

    assert events == []
