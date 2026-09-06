"""Attach identify side panels and wire panel signals."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
    from chappy.gui.modes.identify.panel.panel import IdentifySidePanel


@dataclass(frozen=True, slots=True)
class IdentifyPanelConnectorPorts:
    """Callbacks required to attach and initialize an identify side panel."""

    panel_provider: Callable[[], IdentifySidePanel | None]
    panel_setter: Callable[[IdentifySidePanel | None], None]
    preset_panel_setter: Callable[[IdentifySidePanel | None], None]
    preset_refresh_callback: Callable[[], None]
    preset_changed_callback: Callable[[str], None]
    reference_line_changed_callback: Callable[[str], None]
    manage_presets_callback: Callable[[], None]
    sigma_threshold_provider: Callable[[], float]
    sigma_threshold_changed_callback: Callable[[float], None]
    new_candidate_analysis_half_width_provider: Callable[[], NewCandidateAnalysisHalfWidth]
    new_candidate_analysis_half_width_changed_callback: Callable[
        [NewCandidateAnalysisHalfWidth], None
    ]
    candidate_activated_callback: Callable[[str], None]
    temporary_delete_callback: Callable[[list[str]], None]
    temporary_clear_callback: Callable[[], None]
    registration_requested_callback: Callable[[list[str] | None], None]
    group_focus_callback: Callable[[str, float, float], None]
    line_focus_callback: Callable[[str, float, float], None]
    region_open_callback: Callable[[str], None]
    region_structure_edit_callback: Callable[[str], None]
    refresh_candidates_callback: Callable[[], None]
    refresh_workflow_callback: Callable[[], None]


class IdentifyPanelConnector:
    """Own identify panel attach, detach, and initial refresh sequencing."""

    def __init__(self, ports: IdentifyPanelConnectorPorts) -> None:
        """Initialize the connector."""
        self._ports = ports

    def set_panel(self, panel: IdentifySidePanel | None) -> None:
        """Attach the identify side panel and wire its signals."""
        current_panel = self._ports.panel_provider()
        if panel is current_panel:
            return

        if current_panel is not None:
            self._disconnect_panel_signals(current_panel)

        self._ports.panel_setter(panel)
        self._ports.preset_panel_setter(panel)
        if panel is None:
            return

        self._connect_panel_signals(panel)
        panel.set_sigma_threshold(self._ports.sigma_threshold_provider())
        panel.set_new_candidate_analysis_half_width(
            self._ports.new_candidate_analysis_half_width_provider()
        )
        self._ports.preset_refresh_callback()
        self._ports.refresh_candidates_callback()
        self._ports.refresh_workflow_callback()

    def _connect_panel_signals(self, panel: IdentifySidePanel) -> None:
        panel.preset_changed.connect(self._ports.preset_changed_callback)
        panel.reference_line_changed.connect(self._ports.reference_line_changed_callback)
        panel.manage_presets_requested.connect(self._ports.manage_presets_callback)
        panel.sigma_threshold_changed.connect(self._ports.sigma_threshold_changed_callback)
        panel.new_candidate_analysis_half_width_changed.connect(
            self._ports.new_candidate_analysis_half_width_changed_callback
        )
        panel.candidate_activated.connect(self._ports.candidate_activated_callback)
        panel.temporary_delete_requested.connect(self._ports.temporary_delete_callback)
        panel.temporary_clear_requested.connect(self._ports.temporary_clear_callback)
        panel.registration_requested.connect(self._ports.registration_requested_callback)
        panel.group_focus_requested.connect(self._ports.group_focus_callback)
        panel.line_focus_requested.connect(self._ports.line_focus_callback)
        panel.region_open_requested.connect(self._ports.region_open_callback)
        panel.region_structure_edit_requested.connect(self._ports.region_structure_edit_callback)

    def _disconnect_panel_signals(self, panel: IdentifySidePanel) -> None:
        with suppress(TypeError):
            panel.preset_changed.disconnect(self._ports.preset_changed_callback)
        with suppress(TypeError):
            panel.reference_line_changed.disconnect(self._ports.reference_line_changed_callback)
        with suppress(TypeError):
            panel.manage_presets_requested.disconnect(self._ports.manage_presets_callback)
        with suppress(TypeError):
            panel.sigma_threshold_changed.disconnect(self._ports.sigma_threshold_changed_callback)
        with suppress(TypeError):
            panel.new_candidate_analysis_half_width_changed.disconnect(
                self._ports.new_candidate_analysis_half_width_changed_callback
            )
        with suppress(TypeError):
            panel.candidate_activated.disconnect(self._ports.candidate_activated_callback)
        with suppress(TypeError):
            panel.temporary_delete_requested.disconnect(self._ports.temporary_delete_callback)
        with suppress(TypeError):
            panel.temporary_clear_requested.disconnect(self._ports.temporary_clear_callback)
        with suppress(TypeError):
            panel.registration_requested.disconnect(self._ports.registration_requested_callback)
        with suppress(TypeError):
            panel.group_focus_requested.disconnect(self._ports.group_focus_callback)
        with suppress(TypeError):
            panel.line_focus_requested.disconnect(self._ports.line_focus_callback)
        with suppress(TypeError):
            panel.region_open_requested.disconnect(self._ports.region_open_callback)
        with suppress(TypeError):
            panel.region_structure_edit_requested.disconnect(
                self._ports.region_structure_edit_callback
            )
