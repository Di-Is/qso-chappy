"""Tests for region overlap detection in identify coordinator.

Validates that multiplet regions with discrete lines are handled correctly:
- Lines between discrete wavelength ranges should NOT be considered overlapping
- Lines that actually overlap with existing line wavelength ranges should be detected
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from PySide6.QtCore import QObject, Signal
import pytest

from chappy.application.identify import (
    AtomicIdentifyRegistrationUseCase,
    BuildRegionPreviewsUseCase,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.atomic_data import AtomicLine, AtomicLineData
from chappy.core.identify_state import TemporaryLine, IdentifySessionState
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.identify.coordinator import IdentifyModeCoordinator
from chappy.gui.modes.identify.workflows.registration_workflow import (
    IdentifyRegistrationWorkflow,
    IdentifyRegistrationWorkflowMessages,
    IdentifyRegistrationWorkflowPorts,
)

pytestmark = pytest.mark.usefixtures("qapp")


class _DummySignal:
    def __init__(self) -> None:
        self.emitted: list[str] = []
        self._callbacks: list[Callable[[str], None]] = []

    def connect(self, callback: Callable[[str], None]) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable[[str], None]) -> None:
        self._callbacks.remove(callback)

    def emit(self, message: str) -> None:
        self.emitted.append(message)
        for callback in list(self._callbacks):
            callback(message)


class _TranslationKey(Protocol):
    """Translation key boundary used by dummy language switcher."""

    @property
    def value(self) -> str:
        """Return the string token."""
        ...


class _DummyLanguageSwitcher:
    """Lightweight translator returning deterministic English strings."""

    def translate(self, key: _TranslationKey, default: str = "", **kwargs: str) -> str:
        del default, kwargs
        return key.value


class _DummyAtomicData:
    def __init__(self, lines: list[AtomicLine] | None = None) -> None:
        self._lines = {line.line_id: line for line in (lines or [])}

    def get_line_by_id(self, line_id: str) -> AtomicLine | None:
        return self._lines.get(line_id)

    @property
    def lines(self) -> list[AtomicLine]:  # noqa: D401
        return list(self._lines.values())


class _DummyPreset:
    def __init__(self) -> None:
        self.id = "preset-1"
        self.baseline_id = ""
        self.line_ids: list[str] = []
        self.tie_groups: list[object] = []
        self.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        self.name = "Preset"

    def ensure_baseline(self, _atomic_data: _DummyAtomicData) -> None:
        pass


class _DummyIdentifyPresetStore:
    def __init__(self) -> None:
        self.current_preset_id = "preset-1"
        self._preset = _DummyPreset()
        self.selection_changed = _DummySignal()
        self.presets_changed = _DummySignal()
        self.preset_updated = _DummySignal()

    def get_preset(self, preset_id: str) -> _DummyPreset | None:
        return self._preset if preset_id == self._preset.id else None

    def list_presets(self) -> list[_DummyPreset]:
        return [self._preset]


class _DummyMainWindow(QObject):
    """Small QObject-backed main window double for coordinator construction."""

    project_changed = Signal(SpectroscopyProject)

    def __init__(self, mode_state_store: object) -> None:
        super().__init__()
        self.mode_state_store = mode_state_store
        self.mode_shell_coordinator = None
        self.view_stack = None
        self.preset_store = None
        self.current_project: SpectroscopyProject | None = None
        self._history_bridge = None


def _create_project() -> SpectroscopyProject:
    """Create a project for testing."""
    return SpectroscopyProject()


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


def _build_coordinator(project: SpectroscopyProject) -> IdentifyRegistrationWorkflow:
    """Build a registration workflow with the given project for testing."""
    return IdentifyRegistrationWorkflow(
        IdentifyRegistrationWorkflowPorts(
            project_provider=lambda: project,
            session_provider=IdentifySessionState,
            history_recorder_provider=lambda: None,
            primary_members_provider=lambda: {},
            messages_provider=_registration_messages,
        ),
        BuildRegionPreviewsUseCase(),
        AtomicIdentifyRegistrationUseCase(),
    )


def _add_existing_region_with_lines(
    project: SpectroscopyProject, region_id: str, lines: list[tuple[str, tuple[float, float]]]
) -> None:
    """Add an existing region with absorption lines to the project.

    Args:
        project: The project to add to.
        region_id: ID for the region.
        lines: List of (line_id, lambda_range) tuples.
    """
    region = AbsorptionRegion(region_id=region_id, line_ids=[line_id for line_id, _ in lines])
    project.absorption_regions[region_id] = region

    for line_id, lambda_range in lines:
        absorption_line = AbsorptionLine(
            line_id=line_id,
            species="Test",
            rest_wavelength=1000.0,
            center_z=0.0,
            window_kms=100.0,
            multiplet_label="",
            transition_name="",
            oscillator_strength=0.5,
            gamma_value=1.0,
            lambda_range=lambda_range,
            region_id=region_id,
        )
        project.absorption_lines[line_id] = absorption_line


def _make_temporary_line(
    temporary_line_id: str, lambda_min: float, lambda_max: float
) -> TemporaryLine:
    """Create a temporary line for testing."""
    return TemporaryLine(
        temporary_line_id=temporary_line_id,
        species="Test",
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        creation_method="test",
        line_id="test-line",
        rest_wavelength=1000.0,
        center_z=0.0,
        multiplet_id="",
        multiplet_label="",
        transition_name="",
        oscillator_strength=0.5,
        gamma_value=1.0,
        tie_group_key="",
    )


def test_multiplet_region_discrete_lines_no_overlap() -> None:
    """Verify that wavelengths between discrete lines are NOT considered overlapping.

    Given a region with lines at 1000Å and 1200Å (discrete, not continuous),
    a new temporary line at 1100Å (between them) should be treated as a new region.
    """
    project = _create_project()
    coordinator = _build_coordinator(project)

    # Add existing region with two discrete lines: 995-1005Å and 1195-1205Å
    _add_existing_region_with_lines(
        project, "region-1", [("line-1", (995.0, 1005.0)), ("line-2", (1195.0, 1205.0))]
    )

    # Create a temporary line at 1100Å (between the two lines, no overlap)
    temporary_line = _make_temporary_line("candidate-1", 1095.0, 1105.0)

    # Call build_region_previews
    previews = coordinator.build_region_previews([temporary_line])

    # Should create a new region (not add to existing)
    assert len(previews) == 1
    preview = previews[0]
    assert preview.existing_group_id is None, (
        "Temporary line between discrete lines should NOT be merged into existing region"
    )
    assert preview.group_id.startswith("preview-")


def test_multiplet_region_actual_overlap_detected() -> None:
    """Verify that actual wavelength overlap IS detected.

    Given a region with a line at 1000Å,
    a new temporary line at 1002Å (overlapping) should be added to the existing region.
    """
    project = _create_project()
    coordinator = _build_coordinator(project)

    # Add existing region with one line: 995-1005Å
    _add_existing_region_with_lines(project, "region-1", [("line-1", (995.0, 1005.0))])

    # Create a temporary line at 1002Å (overlapping with existing line)
    temporary_line = _make_temporary_line("candidate-1", 1000.0, 1008.0)

    # Call build_region_previews
    previews = coordinator.build_region_previews([temporary_line])

    # Should add to existing region
    assert len(previews) == 1
    preview = previews[0]
    assert preview.existing_group_id == "region-1", (
        "Temporary line overlapping with existing line should be merged into existing region"
    )
    assert preview.group_id.startswith("add-to-")


def test_single_line_region_backward_compatible() -> None:
    """Verify single-line regions work correctly (backward compatibility).

    This ensures the fix for multiplet regions doesn't break single-line regions.
    """
    project = _create_project()
    coordinator = _build_coordinator(project)

    # Add existing region with single line: 995-1005Å
    _add_existing_region_with_lines(project, "region-1", [("line-1", (995.0, 1005.0))])

    # Create a non-overlapping temporary line
    temporary_line_no_overlap = _make_temporary_line("candidate-1", 1100.0, 1110.0)

    # Should NOT be merged
    previews = coordinator.build_region_previews([temporary_line_no_overlap])
    assert len(previews) == 1
    assert previews[0].existing_group_id is None

    # Create an overlapping temporary line
    temporary_line_overlap = _make_temporary_line("candidate-2", 998.0, 1002.0)

    # Should be merged
    previews = coordinator.build_region_previews([temporary_line_overlap])
    assert len(previews) == 1
    assert previews[0].existing_group_id == "region-1"


def test_multiple_discrete_lines_all_checked() -> None:
    """Verify overlap is checked against ALL lines in a region, not just first/last.

    Given a region with lines at 1000Å, 1100Å, and 1200Å,
    a temporary line overlapping with the middle line (1100Å) should be detected.
    """
    project = _create_project()
    coordinator = _build_coordinator(project)

    # Add existing region with three discrete lines
    _add_existing_region_with_lines(
        project,
        "region-1",
        [
            ("line-1", (995.0, 1005.0)),
            ("line-2", (1095.0, 1105.0)),  # Middle line
            ("line-3", (1195.0, 1205.0)),
        ],
    )

    # Create a temporary line overlapping with the middle line only
    temporary_line = _make_temporary_line("candidate-1", 1098.0, 1108.0)

    # Call build_region_previews
    previews = coordinator.build_region_previews([temporary_line])

    # Should detect overlap with middle line
    assert len(previews) == 1
    assert previews[0].existing_group_id == "region-1", (
        "Temporary line overlapping with middle line should be detected"
    )
