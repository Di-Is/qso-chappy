"""Coordinator linking identify mode UI with preset data structures."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSettings, Signal

from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    BuildRegionPreviewsUseCase,
    BuildVelocityPreviewUseCase,
    BuildVelocitySliceTemporaryLinesUseCase,
    CreateTemporaryLineFromVelocityUseCase,
    DetectCandidateLinesUseCase,
)
from chappy.core.conversion import coerce_float
from chappy.core.editing_mode import EditingMode
from chappy.core.identify_state import (
    DetectedRegion,
    IdentifySessionState,
    RegionPreview,
    TemporaryLine,
)
from chappy.gui.modes.common.analysis_navigation import (
    OpenAnalysisRegionIntent,
    OpenAnalysisStructureIntent,
)
from chappy.gui.modes.identify.adapters import IdentifyPresetAdapter
from chappy.gui.modes.identify.application_adapters import VelocityPreviewAdapter
from chappy.gui.modes.identify.cursor_preview_controller import (
    IdentifyCursorPreviewController,
    IdentifyCursorPreviewPorts,
    shift_modifier_value,
)
from chappy.gui.modes.identify.detection_controller import (
    IdentifyDetectionController,
    IdentifyDetectionPorts,
)
from chappy.gui.modes.identify.focus_controller import (
    IdentifyFocusMessages,
    IdentifyFocusPorts,
    IdentifySpectrumFocusController,
)
from chappy.gui.modes.identify.overlay_controller import (
    IdentifyLineOverlayController,
    IdentifyLineOverlayPorts,
)
from chappy.gui.modes.identify.panel_connector import (
    IdentifyPanelConnector,
    IdentifyPanelConnectorPorts,
)
from chappy.gui.modes.identify.panel_refresh_controller import (
    IdentifyPanelRefreshController,
    IdentifyPanelRefreshPorts,
)
from chappy.gui.modes.identify.presets.preset_controller import (
    IdentifyPresetCallbacks,
    IdentifyPresetController,
    IdentifyPresetMessages,
)
from chappy.gui.modes.identify.registration_controller import (
    IdentifyRegistrationController,
    IdentifyRegistrationMessages,
    IdentifyRegistrationPorts,
)
from chappy.gui.modes.identify.shell_ports import (
    IdentifyHistoryRecorder,
    IdentifyModeStateProvider,
    IdentifyShellPorts,
    IdentifySpectrumView,
)
from chappy.gui.modes.identify.temporary_line_controller import (
    IdentifyTemporaryLineController,
    IdentifyTemporaryLineHistoryRecorder,
    IdentifyTemporaryLineMessages,
    IdentifyTemporaryLinePorts,
)
from chappy.gui.modes.identify.workflow_lifecycle_controller import (
    IdentifyWorkflowLifecycleController,
    IdentifyWorkflowLifecyclePorts,
)
from chappy.gui.modes.identify.workflows.detection_workflow import (
    IdentifyDetectionMessages,
    IdentifyDetectionWorkflow,
    IdentifyDetectionWorkflowPorts,
)
from chappy.gui.modes.identify.workflows.registration_workflow import (
    IdentifyRegistrationHistoryRecorder,
    IdentifyRegistrationWorkflow,
    IdentifyRegistrationWorkflowMessages,
    IdentifyRegistrationWorkflowPorts,
)
from chappy.gui.modes.identify.workflows.velocity_workflow import (
    IdentifyVelocityMessages,
    IdentifyVelocityWorkflow,
    IdentifyVelocityWorkflowPorts,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from chappy.core.atomic_data import AtomicLine, AtomicLineData
    from chappy.core.presets import Preset
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
    from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
    from chappy.gui.modes.identify.panel.panel_models import CandidateRow
    from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
    from chappy.gui.utils.absorption_overlays import RegionPayload
    from chappy.presentation.identify import (
        CursorPreviewPayload,
        IdentifyVelocityPlotContext,
        IdentifyVelocitySelectionPort,
        PreviewEntry,
    )
logger = logging.getLogger(__name__)


class IdentifyModeCoordinator(QObject):
    """Synchronise identify side panel with preset store and project state."""

    status_message = Signal(str)
    open_analysis_region_requested = Signal(object)  # OpenAnalysisRegionIntent
    open_analysis_structure_requested = Signal(object)  # OpenAnalysisStructureIntent

    def __init__(
        self,
        qt_parent: QObject,
        *,
        shell_ports: IdentifyShellPorts,
        atomic_data: AtomicLineData,
        preset_store: IdentifyPresetStore,
    ) -> None:
        """Create coordinator with references to the main window."""
        if not isinstance(qt_parent, QObject):
            msg = "Identify coordinator parent must be a QObject."
            raise TypeError(msg)
        super().__init__(qt_parent)
        self._shell_ports = shell_ports
        self._panel: IdentifySidePanel | None = None
        self._atomic_data = atomic_data
        self._preset_store = preset_store
        self._shell_ports.preset_store_setter(preset_store)
        self._settings = QSettings("Chappy", "Chappy")
        self._sigma_settings_key = "identify_panel/sigma_threshold"
        self._tutorial_sigma_threshold: float | None = None
        self._project: SpectroscopyProject | None = shell_ports.current_project_provider()
        self._detached_session = IdentifySessionState()
        self._session: IdentifySessionState = self._resolve_session(self._project)
        self._detection_workflow = IdentifyDetectionWorkflow(
            IdentifyDetectionWorkflowPorts(
                project_provider=lambda: self._project,
                session_provider=lambda: self._session,
                sigma_threshold_provider=self._load_sigma_threshold,
                status_callback=self.status_message.emit,
                messages_provider=self._detection_messages,
            ),
            DetectCandidateLinesUseCase(),
        )
        self._detection_controller = IdentifyDetectionController(
            IdentifyDetectionPorts(
                current_mode_provider=self._current_editing_mode,
                workflow_provider=lambda: self._detection_workflow,
                session_provider=lambda: self._session,
                overlay_provider=self._get_spectrum_view,
            )
        )
        self._preset_controller: IdentifyPresetController | None = None
        self._velocity_preview_adapter = VelocityPreviewAdapter(BuildVelocityPreviewUseCase())
        self._cursor_preview_controller = IdentifyCursorPreviewController(
            IdentifyCursorPreviewPorts(
                identify_mode_active_provider=self._is_identify_mode_active,
                new_candidate_analysis_half_width_provider=(
                    lambda: self._session.new_candidate_analysis_half_width
                ),
                baseline_line_provider=self._current_baseline_line,
                current_lines_provider=self._collect_current_lines,
                observed_wavelength_bounds_provider=self._observed_wavelength_bounds,
                preview_builder=self._velocity_preview_adapter,
                tie_group_keys_provider=self._current_tie_group_keys,
                preview_sink=self._set_identify_preview,
                preview_hint_provider=self._cursor_preview_hint,
            )
        )
        self._temporary_line_controller = IdentifyTemporaryLineController(
            IdentifyTemporaryLinePorts(
                session_provider=lambda: self._session,
                identify_mode_active_provider=self._is_identify_mode_active,
                baseline_line_provider=self._current_baseline_line,
                current_lines_provider=self._collect_current_lines,
                tie_group_keys_provider=self._current_tie_group_keys,
                observed_bounds_provider=self._observed_wavelength_bounds,
                history_recorder_provider=self._identify_temporary_line_history_recorder,
                primary_members_provider=self._primary_members,
                status_callback=self.status_message.emit,
                refresh_workflow_callback=self._refresh_workflow,
                refresh_candidates_callback=self._refresh_candidates,
                clear_cursor_preview_callback=self.clear_cursor_preview,
                messages_provider=self._temporary_line_messages,
                shift_modifier_value_provider=shift_modifier_value,
            ),
            CreateTemporaryLineFromVelocityUseCase(),
            preview_adapter=self._velocity_preview_adapter,
        )
        self._focus_controller = IdentifySpectrumFocusController(
            IdentifyFocusPorts(
                candidate_rows_provider=self._current_focus_candidate_rows,
                spectrum_view_provider=self._get_spectrum_view,
                data_bounds_provider=self._observed_wavelength_bounds,
                status_callback=self.status_message.emit,
                messages_provider=self._focus_messages,
            )
        )
        self._line_overlay_controller = IdentifyLineOverlayController(
            IdentifyLineOverlayPorts(
                project_provider=lambda: self._project,
                session_provider=lambda: self._session,
                spectrum_view_provider=self._get_spectrum_view,
                identify_mode_active_provider=self._is_identify_mode_active,
            )
        )
        self._panel_refresh_controller = IdentifyPanelRefreshController(
            IdentifyPanelRefreshPorts(
                panel_provider=lambda: self._panel,
                project_provider=lambda: self._project,
                session_provider=lambda: self._session,
                atomic_data_available_provider=lambda: self._atomic_data is not None,
                detection_provider=self._perform_detection,
                detection_overlay_callback=self._update_detection_overlays,
                line_overlay_callback=self._apply_line_overlays,
                region_previews_provider=self._build_live_region_previews,
            )
        )
        self._registration_workflow = IdentifyRegistrationWorkflow(
            IdentifyRegistrationWorkflowPorts(
                project_provider=lambda: self._project,
                session_provider=lambda: self._session,
                history_recorder_provider=self._identify_registration_history_recorder,
                primary_members_provider=self._primary_members,
                messages_provider=self._registration_workflow_messages,
            ),
            BuildRegionPreviewsUseCase(),
            AtomicIdentifyRegistrationUseCase(),
        )
        self._registration_controller = IdentifyRegistrationController(
            IdentifyRegistrationPorts(
                session_provider=lambda: self._session,
                workflow_provider=lambda: self._registration_workflow,
                status_callback=self.status_message.emit,
                refresh_workflow_callback=self._refresh_workflow,
                refresh_candidates_callback=self._refresh_candidates,
                messages_provider=self._registration_messages,
            )
        )
        self._velocity_workflow = IdentifyVelocityWorkflow(
            IdentifyVelocityWorkflowPorts(
                session_provider=lambda: self._session,
                baseline_line_provider=self._current_baseline_line,
                current_lines_provider=self._collect_current_lines,
                atomic_data_provider=lambda: self._atomic_data,
                tie_group_keys_provider=self._current_tie_group_keys,
                temporary_line_creation_callback=lambda entries, redshift, half_width: (
                    self._create_temporary_lines_from_entries(
                        entries, redshift=redshift, new_candidate_analysis_half_width=half_width
                    )
                ),
                status_callback=self.status_message.emit,
                refresh_workflow_callback=self._refresh_workflow,
                refresh_candidates_callback=self._refresh_candidates,
                messages_provider=self._velocity_messages,
            ),
            BuildVelocitySliceTemporaryLinesUseCase(),
        )

        self._initialise_preset_store()
        self._panel_connector = IdentifyPanelConnector(
            IdentifyPanelConnectorPorts(
                panel_provider=lambda: self._panel,
                panel_setter=self._set_panel_reference,
                preset_panel_setter=self._set_preset_panel,
                preset_refresh_callback=self._refresh_presets,
                preset_changed_callback=self._handle_panel_preset_changed,
                reference_line_changed_callback=self._handle_reference_line_changed,
                manage_presets_callback=self._show_preset_management_dialog,
                sigma_threshold_provider=self._load_sigma_threshold,
                sigma_threshold_changed_callback=self._handle_sigma_threshold_changed,
                new_candidate_analysis_half_width_provider=(
                    lambda: self._session.new_candidate_analysis_half_width
                ),
                new_candidate_analysis_half_width_changed_callback=(
                    self._handle_new_candidate_analysis_half_width_changed
                ),
                candidate_activated_callback=self._handle_candidate_activated,
                temporary_delete_callback=self._handle_temporary_delete_requested,
                temporary_clear_callback=self._handle_temporary_clear_requested,
                registration_requested_callback=self._handle_registration_requested,
                group_focus_callback=self._handle_group_focus_requested,
                line_focus_callback=self._handle_line_focus_requested,
                region_open_callback=self._handle_region_open_requested,
                region_structure_edit_callback=self._handle_region_structure_edit_requested,
                refresh_candidates_callback=self._refresh_candidates,
                refresh_workflow_callback=self._refresh_workflow,
            )
        )
        self._lifecycle_controller = IdentifyWorkflowLifecycleController(
            IdentifyWorkflowLifecyclePorts(
                session_provider=lambda: self._session,
                session_resolver=self._resolve_session,
                project_setter=self._set_project,
                session_setter=self._set_session,
                velocity_workflow_reset_callback=self._velocity_workflow.reset,
                detection_overlay_clear_callback=self._detection_controller.clear_overlays,
                cursor_preview_clear_callback=self.clear_cursor_preview,
                preview_lock_enabled_provider=self._cursor_preview_controller.preview_always_on,
                preview_lock_clear_callback=self._cursor_preview_controller.clear_preview_lock,
                preview_reapply_callback=self._cursor_preview_controller.reapply_cursor_preview,
                refresh_candidates_callback=self._refresh_candidates,
                refresh_workflow_callback=self._refresh_workflow,
            )
        )

    def _identify_temporary_line_history_recorder(
        self,
    ) -> IdentifyTemporaryLineHistoryRecorder | None:
        """Return a validated temporary-line history recorder when configured."""
        recorder = self._shell_ports.history_recorder_provider()
        if recorder is None:
            return None
        if isinstance(recorder, IdentifyHistoryRecorder):
            return recorder
        msg = "Identify history recorder does not implement the required recorder port."
        raise TypeError(msg)

    def _identify_registration_history_recorder(
        self,
    ) -> IdentifyRegistrationHistoryRecorder | None:
        """Return a validated registration history recorder when configured."""
        recorder = self._shell_ports.history_recorder_provider()
        if recorder is None:
            return None
        if isinstance(recorder, IdentifyHistoryRecorder):
            return recorder
        msg = "Identify history recorder does not implement the required recorder port."
        raise TypeError(msg)

    def set_panel(self, panel: IdentifySidePanel | None) -> None:
        """Attach the identify side panel and wire its signals."""
        self._panel_connector.set_panel(panel)

    def connect_status_message(self, callback: Callable[[str], None]) -> None:
        """Connect a shell status message callback."""
        self.status_message.connect(callback)

    def refresh(self) -> None:
        """Refresh identify UI to reflect current application state."""
        if self._preset_controller is not None:
            self._preset_controller.refresh_presets()
        self._refresh_candidates()
        self._refresh_workflow()
        if self._cursor_preview_controller.preview_always_on():
            self._cursor_preview_controller.reapply_cursor_preview()

    def _handle_new_candidate_analysis_half_width_changed(
        self, value: NewCandidateAnalysisHalfWidth
    ) -> None:
        """Update only the future-candidate draft and its dependent previews."""
        self._session.set_new_candidate_analysis_half_width(value)
        self._cursor_preview_controller.reapply_cursor_preview()
        self._refresh_velocity_overlay()

    def set_preview_always_on(self, enabled: bool) -> None:
        """Enable or disable identify preview lock.

        Args:
            enabled: True to allow overlay preview without Shift; False to require Shift.
        """
        self._cursor_preview_controller.set_preview_always_on(enabled)

    def preview_always_on(self) -> bool:
        """Return whether identify preview lock is active.

        Returns:
            True when preview overlay remains visible without Shift.
        """
        return self._cursor_preview_controller.preview_always_on()

    def _cursor_preview_hint(self) -> str:
        """Return guidance shown only while a Shift preview is active."""
        #: {value} is the future-candidate analysis half-width in km/s.
        template = self.tr("New candidates ±{value:g} km/s  ·  V: Verify in Velocity Plot")
        return template.format(value=self._session.new_candidate_analysis_half_width.kms)

    def _temporary_line_messages(self) -> IdentifyTemporaryLineMessages:
        """Return translated messages for temporary-line workflows."""
        return IdentifyTemporaryLineMessages(
            invalid_wavelength=self.tr("Please specify a valid wavelength position"),
            baseline_required=self.tr("Select a baseline line before opening the velocity plot."),
            no_lines_selected=self.tr("No lines were selected."),
            invalid_baseline=self.tr("Baseline wavelength is invalid for velocity conversion."),
            limit_reached=self.tr("Temporary line limit reached (1000 entries)."),
            add_one_template=self.tr(
                "Temporary line added for {species} (λ = {start:.2f}–{end:.2f} Å)."
            ),
            add_many_template=self.tr("Added {count} temporary line(s)."),
            duplicate_partial_template=self.tr(
                "Added {created} temporary line(s); skipped {skipped} duplicate(s)."
            ),
            duplicate_existing=self.tr("A temporary line already exists at this location."),
            none_selected=self.tr("No temporary lines selected."),
            remove_failed=self.tr("Selected temporary lines were not removed."),
            remove_template=self.tr("Removed {count} temporary line(s)."),
            none_to_clear=self.tr("No temporary lines to clear."),
            cleared=self.tr("Temporary lines cleared."),
        )

    def _focus_messages(self) -> IdentifyFocusMessages:
        """Return translated messages for spectrum focus workflows."""
        return IdentifyFocusMessages(
            candidate_template=self.tr(
                "Focused spectrum view on candidate window (λ = {start:.2f}–{end:.2f} Å)."
            ),
            group_template=self.tr(
                "Focused spectrum view on region range (λ = {start:.1f}–{end:.1f} Å)."
            ),
            line_template=self.tr(
                "Focused spectrum view on line range (λ = {start:.1f}–{end:.1f} Å)."
            ),
        )

    def _detection_messages(self) -> IdentifyDetectionMessages:
        """Return translated messages for detection workflow."""
        return IdentifyDetectionMessages(
            error_spectrum_required=self.tr("Error spectrum is required for detection."),
            insufficient_data=self.tr("Insufficient data for detection (minimum 100 samples)."),
            no_continuum=self.tr("Continuum model is not available."),
            failed_template=self.tr("Detection failed: {reason}"),
            unknown=self.tr("Unknown"),
        )

    def notify_resolution_changed(self) -> None:
        """React to resolution updates by scheduling or running detection."""
        if self._is_identify_mode_active():
            self._refresh_candidates()

    def _perform_detection(self) -> list[DetectedRegion]:
        return self._detection_controller.perform_detection()

    def _update_detection_overlays(self, regions: Sequence[DetectedRegion]) -> None:
        self._detection_controller.sync_overlays(regions)

    def _get_spectrum_view(self) -> IdentifySpectrumView | None:
        return self._shell_ports.spectrum_view_provider()

    def build_line_overlay_payload(self, *, include_temporary: bool) -> list[RegionPayload]:
        """Construct overlay payloads for confirmed and temporary lines."""
        return self._line_overlay_controller.build_payload(include_temporary=include_temporary)

    def _apply_line_overlays(self, include_temporary: bool | None = None) -> None:
        """Push current line overlays to the spectrum view."""
        self._line_overlay_controller.apply(include_temporary)

    def handle_cursor_position(self, wavelength: float, _flux: float, modifiers: int) -> None:
        """Update ghost overlays based on the current cursor position."""
        self._cursor_preview_controller.handle_cursor_position(wavelength, _flux, modifiers)

    def clear_cursor_preview(self) -> None:
        """Remove identify-mode cursor overlays from the spectrum view."""
        self._cursor_preview_controller.clear_cursor_preview()

    def handle_cursor_left(self) -> None:
        """Forget cursor state and clear overlays when leaving the spectrum view."""
        self._cursor_preview_controller.handle_cursor_left()

    def handle_preview_shift_released(self) -> None:
        """Drop Shift-only preview state without conflating it with cursor leave."""
        self._cursor_preview_controller.handle_shift_released()

    def _reapply_cursor_preview(self) -> None:
        """Recompute ghost overlays using the last known cursor state."""
        self._cursor_preview_controller.reapply_cursor_preview()

    def _is_identify_mode_active(self) -> bool:
        return self._current_editing_mode() is EditingMode.IDENTIFY

    def _current_editing_mode(self) -> EditingMode | None:
        """Return the current editing mode from the shell."""
        mode_state_store = self._shell_ports.mode_state_provider()
        if mode_state_store is None:
            return None
        if isinstance(mode_state_store, IdentifyModeStateProvider):
            return mode_state_store.current_mode
        msg = "Identify mode state store does not implement the required mode-state port."
        raise TypeError(msg)

    def _collect_current_lines(self) -> list[AtomicLine]:
        if self._preset_controller is None:
            return []
        self._preset_controller.set_atomic_data(self._atomic_data)
        return self._preset_controller.collect_current_lines()

    def _current_tie_group_keys(self) -> Mapping[str, str]:
        """Return the active preset's transient line-to-group key mapping."""
        if self._preset_controller is None:
            return {}
        return self._preset_controller.current_tie_group_keys()

    def _observed_wavelength_bounds(self) -> tuple[float, float] | None:
        """Return observed spectrum wavelength bounds if available and valid."""
        project = self._project
        if project is None:
            return None

        observed = project.model.observed_spectrum
        if observed is None:
            return None

        bounds = observed.wavelength_range

        data_min = coerce_float(bounds[0], default=None, require_finite=True)
        data_max = coerce_float(bounds[1], default=None, require_finite=True)
        if data_min is None or data_max is None:
            return None
        if data_max <= data_min:
            return None

        return data_min, data_max

    def _current_focus_candidate_rows(self) -> tuple[CandidateRow, ...]:
        """Return displayed candidate rows available for focus actions."""
        return self._panel_refresh_controller.current_candidate_rows()

    def _primary_members(self) -> dict[str, tuple[str, ...]]:
        """Return latest primary-to-member temporary line mapping."""
        return self._panel_refresh_controller.primary_to_members

    def _set_identify_preview(self, payload: CursorPreviewPayload | None) -> None:
        """Apply identify cursor preview payload to the spectrum view."""
        spectrum_view = self._get_spectrum_view()
        if spectrum_view is None:
            return
        spectrum_view.set_identify_preview(payload)

    def handle_manual_temporary_line(
        self, *, observed_wavelength: float, modifiers: int = 0, source: str = "click"
    ) -> None:
        """Create temporary lines at the given wavelength."""
        self._cursor_preview_controller.note_manual_temporary_line_position(
            observed_wavelength, modifiers
        )
        self._temporary_line_controller.handle_manual_temporary_line(
            observed_wavelength=observed_wavelength, modifiers=modifiers, source=source
        )

    def _create_temporary_lines_from_entries(
        self,
        entries: list[PreviewEntry],
        *,
        redshift: float,
        new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth,
    ) -> tuple[list[tuple[TemporaryLine, PreviewEntry]], int, bool]:
        """Create temporary lines from prepared entry data."""
        return self._temporary_line_controller.create_temporary_lines_from_entries(
            entries,
            redshift=redshift,
            new_candidate_analysis_half_width=new_candidate_analysis_half_width,
        )

    def _initialise_preset_store(self) -> None:
        """Ensure preset store exists and connect change signals."""
        store = self._preset_store
        self._preset_controller = IdentifyPresetController(
            store=store,
            atomic_data=self._atomic_data,
            callbacks=IdentifyPresetCallbacks(
                status_callback=self.status_message.emit,
                hide_velocity_plot_callback=self._hide_velocity_plot,
                reapply_cursor_preview_callback=self._reapply_cursor_preview,
                refresh_velocity_overlay_callback=self._refresh_velocity_overlay,
                messages_provider=self._preset_messages,
                velocity_active_provider=self._velocity_workflow.is_active,
            ),
            adapter=IdentifyPresetAdapter(),
        )

        store.presets_changed.connect(self._preset_controller.refresh_presets)
        store.selection_changed.connect(self._preset_controller.handle_store_selection_changed)
        store.preset_updated.connect(self._preset_controller.handle_preset_updated)

    def _resolve_session(self, project: SpectroscopyProject | None) -> IdentifySessionState:
        """Return the identify session associated with ``project``."""
        if project is None:
            return self._detached_session

        return project.identify_state

    def _set_project(self, project: SpectroscopyProject | None) -> None:
        """Store the active project."""
        self._project = project

    def _set_session(self, session: IdentifySessionState) -> None:
        """Store the active identify session."""
        self._session = session

    def _set_panel_reference(self, panel: IdentifySidePanel | None) -> None:
        """Store the attached identify panel reference."""
        self._panel = panel

    def _set_preset_panel(self, panel: IdentifySidePanel | None) -> None:
        if self._preset_controller is not None:
            self._preset_controller.set_panel(panel)

    def _refresh_presets(self) -> None:
        if self._preset_controller is not None:
            self._preset_controller.refresh_presets()

    def _handle_panel_preset_changed(self, preset_id: str) -> None:
        if self._preset_controller is not None:
            self._preset_controller.handle_panel_preset_changed(preset_id)

    def _handle_reference_line_changed(self, line_id: str) -> None:
        if self._preset_controller is not None:
            self._preset_controller.handle_reference_line_changed(line_id)

    def _preset_messages(self) -> IdentifyPresetMessages:
        """Return translated messages for preset workflow."""
        return IdentifyPresetMessages(
            baseline_updated=self.tr("Baseline line updated for the active preset."),
            selection_missing=self.tr("Preset could not be selected because it no longer exists."),
        )

    def _refresh_candidates(self) -> None:
        self._panel_refresh_controller.refresh_candidates()

    def set_tutorial_sigma_threshold(self, value: float | None) -> None:
        """Apply a temporary tutorial threshold without changing user settings."""
        if value is not None and not 2.0 <= value <= 100.0:
            msg = "Tutorial sigma threshold must be between 2.0 and 100.0."
            raise ValueError(msg)
        if self._tutorial_sigma_threshold == value:
            return
        self._tutorial_sigma_threshold = value
        if self._panel is not None:
            self._panel.set_sigma_threshold(self._load_sigma_threshold())
        self._refresh_candidates()

    def _refresh_workflow(self) -> None:
        self._panel_refresh_controller.refresh_workflow()

    def _build_live_region_previews(self) -> list[RegionPreview]:
        """Re-evaluate the bundling result for the always-visible grouping display."""
        return self._registration_workflow.build_region_previews(self._session.temporary_lines)

    def _refresh_velocity_overlay(self) -> None:
        if not self._velocity_workflow.is_active():
            return
        self._shell_ports.velocity_runtime_provider().refresh_velocity_overlay()

    def _hide_velocity_plot(self) -> None:
        """Hide the shell velocity plot."""
        self._shell_ports.velocity_runtime_provider().hide_velocity_plot()

    def _registration_messages(self) -> IdentifyRegistrationMessages:
        """Return translated messages for registration routing."""
        return IdentifyRegistrationMessages(
            no_temporary_lines=self.tr("No temporary lines to group."),
            no_selected_temporary_lines=self.tr("No selected temporary lines to group."),
        )

    def _registration_workflow_messages(self) -> IdentifyRegistrationWorkflowMessages:
        """Return translated messages for the immediate registration workflow."""
        return IdentifyRegistrationWorkflowMessages(
            cannot_register_without_project=self.tr(
                "Cannot register lines without an active project."
            ),
            no_temporary_lines_to_register=self.tr("No temporary lines to register."),
            temporary_lines_could_not_register=self.tr("Temporary lines could not be registered."),
            #: {count} is the number of registered lines.
            registered_template=self.tr("Registered {count} line(s)"),
            #: {details} is a pre-built list such as "2 new region(s), added to Region 3".
            registered_details_template=self.tr(" ({details})"),
            #: {count} is the number of newly created regions.
            new_regions_template=self.tr("{count} new region(s)"),
            #: {region} is the display name of an existing region.
            appended_template=self.tr("added to {region}"),
            detail_separator=self.tr(", "),
            multi_overlap_warning=self.tr(
                "Overlaps multiple existing regions. Check the assignment in Analysis "
                "Structure after registering."
            ),
            missing_atomic_template=self.tr(
                "{count} temporary line(s) could not be registered due to missing atomic data."
            ),
            #: Keep {undo_shortcut} unchanged; it is replaced for the running OS.
            undo_hint=self.tr("Undo ({undo_shortcut}) reverts this registration.").format(
                undo_shortcut=self._shell_ports.undo_shortcut_provider()
            ),
            unknown=self.tr("Unknown"),
        )

    def _velocity_messages(self) -> IdentifyVelocityMessages:
        """Return translated messages for velocity plot workflow."""
        return IdentifyVelocityMessages(
            baseline_required=self.tr("Select a baseline line before opening the velocity plot."),
            invalid_wavelength=self.tr("Please specify a valid wavelength position"),
            no_lines_selected=self.tr("No lines were selected."),
            invalid_baseline=self.tr("Baseline wavelength is invalid for velocity conversion."),
            centered_template=self.tr("Velocity plot centered at z = {z:.4f} for {label}."),
            closed=self.tr("Velocity plot closed."),
            select_one=self.tr("Select at least one line in the velocity plot."),
            unable_to_create=self.tr("Unable to create temporary lines from the selected lines."),
            add_one_template=self.tr(
                "Temporary line added for {species} (λ = {start:.2f}–{end:.2f} Å)."
            ),
            add_many_template=self.tr("Added {count} temporary line(s) from the velocity plot."),
            duplicate_partial_template=self.tr(
                "Added {created} temporary line(s); skipped {skipped} duplicate(s)."
            ),
            duplicate_existing=self.tr("A temporary line already exists at this location."),
        )

    def _show_preset_management_dialog(self) -> None:
        self._shell_ports.preset_dialog_provider().show_preset_list_dialog()

    def _handle_sigma_threshold_changed(self, value: float) -> None:
        self._settings.setValue(self._sigma_settings_key, float(value))
        self._refresh_candidates()

    def _handle_candidate_activated(self, candidate_id: str) -> None:
        self._focus_controller.focus_candidate(candidate_id)

    def _handle_group_focus_requested(
        self, _group_id: str, min_wave: float, max_wave: float
    ) -> None:
        self._focus_controller.focus_group(min_wave, max_wave)

    def _handle_region_open_requested(self, region_id: str) -> None:
        self.open_analysis_region_requested.emit(OpenAnalysisRegionIntent(region_id))

    def _handle_region_structure_edit_requested(self, region_id: str) -> None:
        self.open_analysis_structure_requested.emit(OpenAnalysisStructureIntent(region_id))

    def _handle_line_focus_requested(
        self, _temporary_line_id: str, min_wave: float, max_wave: float
    ) -> None:
        self._focus_controller.focus_line(min_wave, max_wave)

    def _handle_temporary_delete_requested(self, temporary_line_ids: list[str]) -> None:
        self._temporary_line_controller.delete_temporary_lines(temporary_line_ids)

    def _handle_temporary_clear_requested(self) -> None:
        self._temporary_line_controller.clear_temporary_lines()

    def _handle_registration_requested(self, selected_ids: list[str] | None = None) -> None:
        result = self._registration_controller.register(selected_ids)
        if result is not None and self._panel is not None:
            self._panel.show_registration_feedback(result.message)
            if result.outcome is not None:
                self._panel.reveal_confirmed_regions(result.outcome.affected_region_ids)
        if (
            result is not None
            and result.outcome is not None
            and len(result.outcome.created_region_ids) == 1
        ):
            self.open_analysis_region_requested.emit(
                OpenAnalysisRegionIntent(result.outcome.created_region_ids[0])
            )

    def on_mode_changed(self, mode: EditingMode) -> None:
        """Synchronise detection overlays with the active editing mode."""
        self._lifecycle_controller.on_mode_changed(mode)

    def set_identify_active(self, active: bool) -> None:
        """Activate or deactivate Identify without a non-active mode sentinel."""
        self._lifecycle_controller.on_mode_changed(
            EditingMode.IDENTIFY if active else EditingMode.ANALYSIS
        )

    def request_velocity_plot(
        self, observed_wavelength: float
    ) -> IdentifyVelocityPlotContext | None:
        """Calculate velocity plot context for the given observed wavelength."""
        return self._velocity_workflow.request_velocity_plot(observed_wavelength)

    def handle_velocity_plot_closed(self) -> None:
        """Reset internal state when the velocity plot is dismissed."""
        self._velocity_workflow.handle_velocity_plot_closed()

    def report_invalid_wavelength(self) -> None:
        """Tell the user that a valid wavelength position must be specified."""
        self._velocity_workflow.report_invalid_wavelength()

    def baseline_line_selected(self) -> bool:
        """Return whether the active preset defines a baseline line."""
        return self._current_baseline_line() is not None

    def confirm_velocity_plot_selection(
        self, *, center_z: float | None, slices: Sequence[IdentifyVelocitySelectionPort]
    ) -> None:
        """Create temporary lines from checked velocity slices."""
        self._velocity_workflow.confirm_velocity_plot_selection(center_z=center_z, slices=slices)

    def _current_preset(self) -> Preset | None:
        if self._preset_controller is None:
            return None
        return self._preset_controller.current_preset()

    def _current_baseline_line(self) -> AtomicLine | None:
        preset = self._current_preset()
        if not preset or not preset.baseline_id:
            return None
        return self._atomic_data.get_line_by_id(preset.baseline_id)

    def handle_project_changed(self, project: SpectroscopyProject | None) -> None:
        """Synchronise identify workflow state with the active project."""
        self._lifecycle_controller.handle_project_changed(project)

    def _load_sigma_threshold(self) -> float:
        if self._tutorial_sigma_threshold is not None:
            return self._tutorial_sigma_threshold
        value = self._settings.value(self._sigma_settings_key, 50.0)
        parsed = coerce_float(value, default=None, require_finite=True)
        return parsed if parsed is not None else 50.0
