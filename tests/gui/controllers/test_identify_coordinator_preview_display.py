"""Tests for preview display name generation in identify coordinator."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, Signal
import pytest

from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    BuildRegionPreviewsUseCase,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.identify_state import TemporaryLine, TemporaryLineContext, IdentifySessionState
from chappy.core.presets import Preset
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.identify.coordinator import IdentifyModeCoordinator
from chappy.gui.modes.identify.panel.panel import IdentifySidePanel
from chappy.gui.modes.identify.panel.panel_models import (
    TemporaryLineRow,
    ConfirmedRegionRow,
    RegionPreviewRow,
)
from chappy.gui.modes.identify.shell_ports import IdentifyShellPorts
from chappy.gui.modes.identify.workflows.registration_workflow import (
    IdentifyRegistrationWorkflow,
    IdentifyRegistrationWorkflowMessages,
    IdentifyRegistrationWorkflowPorts,
)
from chappy.infrastructure.atomic_lines import get_atomic_data
from scripts.i18n_lupdate import run_lupdate

pytestmark = pytest.mark.usefixtures("qapp")


IDENTIFY_COORDINATOR_QT_SOURCES = {
    "Added {count} temporary line(s).",
    "Added {count} temporary line(s) from the velocity plot.",
    "Added {created} temporary line(s); skipped {skipped} duplicate(s).",
    "Baseline line updated for the active preset.",
    "Candidate table",
    "Temporary line added for {species} (λ = {start:.2f}–{end:.2f} Å).",
    "A temporary line already exists at this location.",
    "Temporary line limit reached (1000 entries).",
    "Temporary lines cleared.",
    "Temporary lines could not be registered.",
    "Cannot register lines without an active project.",
    "Registered {count} line(s)",
    "Undo ({undo_shortcut}) reverts this registration.",
    " ({details})",
    "{count} new region(s)",
    "added to {region}",
    ", ",
    "Overlaps multiple existing regions. Check the assignment in Analysis Structure after registering.",
    "Continuum model is not available.",
    "Detection failed: {reason}",
    "Error spectrum is required for detection.",
    "Focused spectrum view on candidate window (λ = {start:.2f}–{end:.2f} Å).",
    "Focused spectrum view on region range (λ = {start:.1f}–{end:.1f} Å).",
    "Focused spectrum view on line range (λ = {start:.1f}–{end:.1f} Å).",
    "Insufficient data for detection (minimum 100 samples).",
    "Manual placement",
    "No temporary lines selected.",
    "No temporary lines to clear.",
    "No lines were selected.",
    "Please specify a valid wavelength position",
    "Preset could not be selected because it no longer exists.",
    "Removed {count} temporary line(s).",
    "Select a baseline line before opening the velocity plot.",
    "Select at least one line in the velocity plot.",
    "Selected temporary lines were not removed.",
    "Unable to create temporary lines from the selected lines.",
    "Unknown",
    "Velocity plot",
    "Velocity plot centered at z = {z:.4f} for {label}.",
    "Velocity plot closed.",
    "New candidates ±{value:g} km/s  ·  V: Verify in Velocity Plot",
    "{count} temporary line(s) could not be registered due to missing atomic data.",
}


def _make_line(
    line_id: str,
    *,
    species: str = "Mg II",
    rest_wavelength: float = 2796.352,
    center_z: float = 1.0,
) -> AbsorptionLine:
    """Create a minimal AbsorptionLine for testing."""
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=150.0,
        multiplet_label="",
        transition_name=f"{species} {rest_wavelength:.1f}",
        oscillator_strength=0.1,
        gamma_value=1e8,
        multiplet_ids=[],
        model_ids=[],
    )


class _IdentifyMainWindow(QObject):
    """Minimal QObject parent accepted by IdentifyModeCoordinator."""

    project_changed = Signal(SpectroscopyProject)

    def __init__(self, project: SpectroscopyProject | None) -> None:
        """Initialize the main-window surface used by the coordinator."""
        super().__init__()
        self.current_project = project
        self.view_stack = None
        self.mode_state_store = None
        self.preset_store = _DummyIdentifyPresetStore()
        self.data_control_panel = None
        self.identify_velocity_runtime = _IdentifyVelocityRuntime()

    @property
    def identify_history_recorder(self) -> None:
        """Return no history recorder for isolated workflow tests."""
        return None

    @property
    def preset_dialog_port(self) -> _IdentifyMainWindow:
        """Return the preset dialog port used by the coordinator."""
        return self

    def show_preset_list_dialog(self) -> None:
        """No-op preset dialog hook for isolated workflow tests."""
        return None


class _IdentifyVelocityRuntime:
    """No-op identify velocity runtime double."""

    def hide_velocity_plot(self) -> None:
        """No-op velocity plot hook for isolated workflow tests."""
        return None

    def refresh_velocity_overlay(self) -> None:
        """No-op velocity plot hook for isolated workflow tests."""
        return None


class _DummySignal:
    """Small signal double for preset store callbacks."""

    def __init__(self) -> None:
        """Initialize callbacks."""
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Record a callback."""
        self._callbacks.append(callback)


class _DummyIdentifyPresetStore:
    """Minimal preset store that avoids QObject construction in coordinator tests."""

    def __init__(self) -> None:
        """Initialize empty preset state."""
        self.current_preset_id: str | None = None
        self.presets_changed = _DummySignal()
        self.selection_changed = _DummySignal()
        self.preset_updated = _DummySignal()

    def list_presets(self) -> list[Preset]:
        """Return no presets for display-name tests."""
        return []

    def get_preset(self, preset_id: str) -> Preset | None:
        """Return no preset for display-name tests."""
        del preset_id
        return None

    def set_current_preset(self, preset_id: str | None) -> None:
        """Store current preset id."""
        self.current_preset_id = preset_id


class _WorkflowPanel:
    """Capture workflow rows emitted by IdentifyModeCoordinator."""

    def __init__(self) -> None:
        """Initialize captured row containers."""
        self.temporary_lines: list[TemporaryLineRow] = []
        self.region_previews: list[RegionPreviewRow] = []
        self.confirmed_regions: list[ConfirmedRegionRow] = []

    def set_temporary_lines(
        self, lines: Sequence[TemporaryLineRow], previews: Sequence[RegionPreviewRow] = ()
    ) -> None:
        """Store temporary line and preview rows for assertions."""
        self.temporary_lines = list(lines)
        self.region_previews = list(previews)

    def set_confirmed_regions(self, regions: Sequence[ConfirmedRegionRow]) -> None:
        """Store confirmed region rows for assertions."""
        self.confirmed_regions = list(regions)


def _build_coordinator(project: SpectroscopyProject | None = None) -> IdentifyModeCoordinator:
    """Build a minimal IdentifyModeCoordinator for testing."""
    main_window = _IdentifyMainWindow(project)
    coordinator = IdentifyModeCoordinator(
        main_window,
        shell_ports=IdentifyShellPorts(
            current_project_provider=lambda: main_window.current_project,
            spectrum_view_provider=lambda: None,
            mode_state_provider=lambda: main_window.mode_state_store,
            preset_store_setter=lambda store: setattr(main_window, "preset_store", store),
            history_recorder_provider=lambda: main_window.identify_history_recorder,
            velocity_runtime_provider=lambda: main_window.identify_velocity_runtime,
            preset_dialog_provider=lambda: main_window.preset_dialog_port,
            undo_shortcut_provider=lambda: "Ctrl+Z",
        ),
        atomic_data=get_atomic_data(),
        preset_store=main_window.preset_store,
    )

    session = IdentifySessionState()
    coordinator._session = session
    coordinator._detached_session = session
    coordinator._atomic_data = get_atomic_data()
    coordinator._project = project

    return coordinator


def _registration_messages() -> IdentifyRegistrationWorkflowMessages:
    """Return deterministic registration workflow messages."""
    return IdentifyRegistrationWorkflowMessages(
        cannot_register_without_project="No project",
        no_temporary_lines_to_register="No candidates",
        temporary_lines_could_not_register="Failed",
        registered_template="Registered {count}",
        registered_details_template=" ({details})",
        new_regions_template="{count} new region(s)",
        appended_template="added to {region}",
        detail_separator=", ",
        multi_overlap_warning="Overlaps multiple existing regions.",
        missing_atomic_template="Missing {count}",
        undo_hint="Undo (Ctrl+Z) reverts this registration.",
        unknown="Unknown",
    )


def _build_registration_workflow(
    project: SpectroscopyProject | None = None,
) -> IdentifyRegistrationWorkflow:
    """Build a registration workflow for display-name focused tests."""
    session = IdentifySessionState()
    return IdentifyRegistrationWorkflow(
        IdentifyRegistrationWorkflowPorts(
            project_provider=lambda: project,
            session_provider=lambda: session,
            history_recorder_provider=lambda: None,
            primary_members_provider=lambda: {},
            messages_provider=_registration_messages,
        ),
        BuildRegionPreviewsUseCase(),
        AtomicIdentifyRegistrationUseCase(),
    )


def _temporary_line(
    temporary_line_id: str,
    creation_method: str,
    *,
    species: str = "Mg II",
    lambda_min: float = 5000.0,
    lambda_max: float = 5010.0,
) -> TemporaryLine:
    """Create a temporary line for workflow tests."""
    return TemporaryLine(
        temporary_line_id=temporary_line_id,
        species=species,
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        creation_method=creation_method,
        line_id=f"{temporary_line_id}-line",
        rest_wavelength=2796.352,
        center_z=0.788,
        multiplet_id="",
        multiplet_label="",
        transition_name="Mg II 2796",
        oscillator_strength=0.612,
        gamma_value=2.6e8,
        tie_group_key="",
    )


def _add_temporary_line(
    session: IdentifySessionState,
    temporary_line_id: str,
    creation_method: str,
    *,
    lambda_min: float,
    lambda_max: float,
) -> TemporaryLine:
    """Add a temporary line through the session API."""
    context = TemporaryLineContext(
        line_id=f"{temporary_line_id}-line",
        rest_wavelength=2796.352,
        center_z=0.788,
        multiplet_id="",
        multiplet_label="",
        transition_name="Mg II 2796",
        oscillator_strength=0.612,
        gamma_value=2.6e8,
        tie_group_key="",
    )
    return session.add_temporary_line(
        species="Mg II",
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        creation_method=creation_method,
        context=context,
    )


def _ts_sources(ts_path: Path) -> set[str]:
    """Return source texts extracted into a Qt TS file."""
    root = ET.parse(ts_path).getroot()
    return {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }


def test_workflow_labels_use_qt_source_text() -> None:
    """Verify migrated workflow labels use Qt source text."""
    coordinator = _build_coordinator(project=None)
    panel = _WorkflowPanel()
    coordinator._panel = cast(IdentifySidePanel, panel)
    _add_temporary_line(
        coordinator._session, "candidate", "candidate_table", lambda_min=5000.0, lambda_max=5005.0
    )
    _add_temporary_line(
        coordinator._session, "manual", "manual", lambda_min=5010.0, lambda_max=5015.0
    )
    _add_temporary_line(
        coordinator._session, "velocity", "velocity_plot", lambda_min=5020.0, lambda_max=5025.0
    )

    coordinator._refresh_workflow()

    assert {row.creation_method for row in panel.temporary_lines} == {
        "Candidate table",
        "Manual placement",
        "Velocity plot",
    }


def test_cursor_preview_hint_reports_current_state_and_next_action() -> None:
    """The transient hint describes the active preview instead of the consumed key."""
    coordinator = _build_coordinator(project=None)

    assert (
        coordinator._cursor_preview_hint()
        == "New candidates ±200 km/s  ·  V: Verify in Velocity Plot"
    )


def test_region_preview_and_default_group_name_use_qt_source_text() -> None:
    """Verify migrated fallback labels use Qt source text."""
    workflow = _build_registration_workflow(project=None)
    temporary_line = _temporary_line(
        "unknown", "manual", species="", lambda_min=5100.0, lambda_max=5110.0
    )

    previews = workflow.build_region_previews([temporary_line])

    assert previews[0].name == "Unknown @ 5100.0-5110.0Å"


def test_lupdate_extracts_identify_coordinator_qt_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated IdentifyModeCoordinator GUI sources."""
    if shutil.which("pyside6-lupdate") is None:
        return

    ts_path = tmp_path / "identify_coordinator.ts"
    run_lupdate(
        source_dirs=[
            Path("src/chappy/gui/modes/identify/coordinator.py"),
            Path("src/chappy/gui/modes/identify/panel_refresh_controller.py"),
        ],
        ts_output=ts_path,
    )

    sources = _ts_sources(ts_path)
    assert IDENTIFY_COORDINATOR_QT_SOURCES <= sources
    assert not any("GUI__" in source for source in sources)
    assert not any("MSG__" in source for source in sources)


class TestGetRegionDisplayName:
    """Tests for registration workflow region display names."""

    def test_returns_dynamic_name_with_valid_region(self) -> None:
        """Dynamic name is returned for a region with lines."""
        # Given: A project with a region containing Mg II lines
        project = SpectroscopyProject()
        line = project.add_absorption_line(
            species="Mg II",
            transition_name="Mg II 2796.4",
            rest_wavelength=2796.352,
            center_z=1.0,
            window_kms=150.0,
            multiplet_label="Mg II 2796/2803",
            oscillator_strength=0.612,
            gamma_value=2.6e8,
            lambda_range=(5000.0, 6000.0),
        )
        region = project.create_region_with_lines([line.line_id])
        region.analysis_range = (5000.0, 6000.0)

        workflow = _build_registration_workflow(project)

        # When: get_region_display_name is called
        result = workflow.get_region_display_name(region)

        # Then: Dynamic name with species, range, and count is returned
        assert "Mg II" in result
        assert "5000.0-6000.0" in result
        assert "(1)" in result

    def test_returns_truncated_id_when_region_has_no_lines(self) -> None:
        """Fallback to truncated region_id when region has no lines."""
        # Given: A region with no lines (edge case / defensive)
        region = AbsorptionRegion(
            region_id="abcdef1234567890", line_ids=[], analysis_range=(5000.0, 6000.0)
        )

        project = SpectroscopyProject()
        workflow = _build_registration_workflow(project)

        # When: get_region_display_name is called
        result = workflow.get_region_display_name(region)

        # Then: Truncated region_id is returned
        assert result == "abcdef12"

    def test_returns_truncated_id_when_project_is_none(self) -> None:
        """Fallback to truncated region_id when project is unavailable."""
        # Given: A workflow with no project
        region = AbsorptionRegion(
            region_id="abcdef1234567890", line_ids=["line1"], analysis_range=(5000.0, 6000.0)
        )

        workflow = _build_registration_workflow(project=None)

        # When: get_region_display_name is called
        result = workflow.get_region_display_name(region)

        # Then: Truncated region_id is returned
        assert result == "abcdef12"

    def test_returns_dynamic_name_for_mixed_species(self) -> None:
        """Dynamic name includes all species when region has mixed lines."""
        # Given: A project with a region containing Mg II and Al I lines
        project = SpectroscopyProject()
        line1 = project.add_absorption_line(
            species="Mg II",
            transition_name="Mg II 2796.4",
            rest_wavelength=2796.352,
            center_z=1.0,
            window_kms=150.0,
            multiplet_label="Mg II 2796/2803",
            oscillator_strength=0.612,
            gamma_value=2.6e8,
            lambda_range=(5000.0, 5500.0),
        )
        line2 = project.add_absorption_line(
            species="Al I",
            transition_name="Al I 2119.0",
            rest_wavelength=2118.9862,
            center_z=1.0,
            window_kms=150.0,
            multiplet_label="",
            oscillator_strength=0.0167,
            gamma_value=4.1e7,
            lambda_range=(5500.0, 6000.0),
        )
        region = project.create_region_with_lines([line1.line_id])
        project.assign_line_to_region(line2.line_id, region.region_id)
        region.analysis_range = (5000.0, 6000.0)

        workflow = _build_registration_workflow(project)

        # When: get_region_display_name is called
        result = workflow.get_region_display_name(region)

        # Then: Both species are included (sorted alphabetically)
        assert "Al I" in result
        assert "Mg II" in result
        assert "|" in result  # Species separator
