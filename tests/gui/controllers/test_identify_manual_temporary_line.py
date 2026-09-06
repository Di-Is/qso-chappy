"""Tests for manual temporary-line placement in identify coordinator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import math
from typing import Protocol

from PySide6.QtCore import QObject, Qt, Signal
import pytest

from chappy.core.atomic_data import AtomicLine, AtomicLineData
from chappy.core.editing_mode import EditingMode
from chappy.core.identify_state import IdentifySessionState, TemporaryLineContext
from chappy.core.presets import PresetTieGroup
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.gui.modes.identify.coordinator import IdentifyModeCoordinator
from chappy.gui.modes.identify.shell_ports import IdentifyShellPorts
from chappy.presentation.velocity import VelocitySliceInfo

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


class _StatusRecorder:
    """Collect status messages emitted by the coordinator."""

    def __init__(self) -> None:
        self.emitted: list[str] = []

    def emit(self, message: str) -> None:
        self.emitted.append(message)


class _TranslationKey(Protocol):
    """Translation key boundary used by dummy language switcher."""

    @property
    def value(self) -> str:
        """Return the string token."""
        ...


class _DummyLanguageSwitcher:
    """Lightweight translator returning deterministic English strings."""

    _MESSAGES: dict[str, str] = {
        "MSG__IDENT__TEMP_ADDED": (
            "Temporary line added for {species} (λ = {start:.2f}–{end:.2f} Å)."
        ),
        "MSG__IDENT__TEMP_ADDED_BULK": "Added {count} temporary line(s).",
        "MSG__IDENT__TEMP_DUPLICATE": "A temporary line already exists at this location.",
        "MSG__IDENT__TEMP_PARTIAL_DUPLICATE": (
            "Added {created} temporary line(s); skipped {skipped} duplicate(s)."
        ),
        "MSG__IDENT__VPLOT_CREATED": ("Added {count} temporary line(s) from the velocity plot."),
        "MSG__IDENT__VPLOT_NO_SELECTION": "Select at least one line in the velocity plot.",
        "MSG__IDENT__NO_LINES_SELECTED": "No lines were selected.",
        "MSG__IDENT__BASELINE_REQUIRED": "Select a baseline line before opening the velocity plot.",
        "MSG__IDENT__INVALID_POSITION": "Please specify a valid wavelength position",
    }

    def translate(
        self, key: _TranslationKey, default: str = "", **kwargs: str | int | float
    ) -> str:
        """Return a formatted message for the supplied key."""
        token = key.value
        template = self._MESSAGES.get(token, default or token)
        return template.format(**kwargs) if kwargs else template


class _DummyAtomicData:
    def __init__(self, lines: list[AtomicLine]) -> None:
        self._lines = {line.line_id: line for line in lines}

    def get_line_by_id(self, line_id: str) -> AtomicLine | None:
        return self._lines.get(line_id)

    @property
    def lines(self) -> list[AtomicLine]:  # noqa: D401
        return list(self._lines.values())


class _DummyPreset:
    def __init__(
        self, baseline_id: str, line_ids: list[str], tie_groups: list[PresetTieGroup] | None = None
    ) -> None:
        self.id = "preset-1"
        self.baseline_id = baseline_id
        self.line_ids = line_ids
        self.tie_groups = list(tie_groups or [])
        self.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        self.name = "Preset"

    def ensure_baseline(self, _atomic_data: _DummyAtomicData) -> None:
        if not self.baseline_id and self.line_ids:
            self.baseline_id = self.line_ids[0]


class _DummyIdentifyPresetStore:
    def __init__(self, preset: _DummyPreset) -> None:
        self.current_preset_id = preset.id
        self._preset = preset
        self.selection_changed = _DummySignal()
        self.presets_changed = _DummySignal()
        self.preset_updated = _DummySignal()

    def get_preset(self, preset_id: str) -> _DummyPreset | None:
        return self._preset if preset_id == self._preset.id else None

    def preset_revision(self, preset_id: str) -> float | None:
        preset = self.get_preset(preset_id)
        return preset.updated_at.timestamp() if preset else None

    def list_presets(self) -> list[_DummyPreset]:
        return [self._preset]

    def set_current_preset(self, preset_id: str) -> None:
        self.current_preset_id = preset_id

    def select_replacement_preset(self, preset_id: str) -> None:
        """Replace the only preset and emit the selection signal."""
        self._preset.id = preset_id
        self.current_preset_id = preset_id
        self.selection_changed.emit(preset_id)


class _DummyModeStateStore:
    def __init__(self) -> None:
        self.current_mode = EditingMode.IDENTIFY


class _DummyMainWindow(QObject):
    """Small QObject-backed main window double for coordinator construction."""

    project_changed = Signal(SpectroscopyProject)

    def __init__(self, mode_state_store: _DummyModeStateStore) -> None:
        super().__init__()
        self.mode_state_store = mode_state_store
        self.mode_shell_coordinator = None
        self.view_stack = None
        self.preset_store: _DummyIdentifyPresetStore | None = None
        self.current_project: SpectroscopyProject | None = None
        self._history_bridge = None
        self.hide_velocity_plot_called = 0
        self._coordinator: IdentifyModeCoordinator | None = None
        self.identify_velocity_runtime = _DummyIdentifyVelocityRuntime(self)

    def attach_coordinator(self, coordinator: IdentifyModeCoordinator) -> None:
        self._coordinator = coordinator

    @property
    def identify_history_recorder(self) -> None:
        """Return no history recorder for isolated workflow tests."""
        return None

    @property
    def preset_dialog_port(self) -> _DummyMainWindow:
        """Return the preset dialog port used by the coordinator."""
        return self

    def show_preset_list_dialog(self) -> None:
        """No-op preset dialog hook for isolated workflow tests."""
        return None


class _DummyIdentifyVelocityRuntime:
    """Small identify velocity runtime double for coordinator tests."""

    def __init__(self, main_window: _DummyMainWindow) -> None:
        """Store the owning main-window double."""
        self._main_window = main_window
        self.refresh_velocity_overlay_called = 0

    def hide_velocity_plot(self) -> None:
        """Record hide requests and notify the coordinator."""
        self._main_window.hide_velocity_plot_called += 1
        if self._main_window._coordinator is not None:
            self._main_window._coordinator.handle_velocity_plot_closed()

    def refresh_velocity_overlay(self) -> None:
        """Record refresh requests."""
        self.refresh_velocity_overlay_called += 1


@dataclass
class _CoordinatorHarness:
    """Test harness exposing public workflow state around IdentifyModeCoordinator."""

    coordinator: IdentifyModeCoordinator
    project: SpectroscopyProject
    status: _StatusRecorder
    main_window: _DummyMainWindow
    preset_store: _DummyIdentifyPresetStore

    @property
    def session(self) -> IdentifySessionState:
        return self.project.identify_state


def _shift_mask() -> int:
    try:
        return int(Qt.KeyboardModifier.ShiftModifier.value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise AssertionError("Unable to derive shift modifier mask") from exc


def _build_coordinator(
    lines: list[AtomicLine], baseline_id: str, project: SpectroscopyProject | None = None
) -> _CoordinatorHarness:
    active_project = project or SpectroscopyProject()
    mode_state_store = _DummyModeStateStore()
    main_window = _DummyMainWindow(mode_state_store)
    main_window.current_project = active_project
    line_ids_by_multiplet: dict[str, list[str]] = {}
    for line in lines:
        if line.multiplet_id:
            line_ids_by_multiplet.setdefault(line.multiplet_id, []).append(line.line_id)
    tie_groups = [
        PresetTieGroup(uid=f"fixture:{multiplet_id}", line_ids=tuple(line_ids))
        for multiplet_id, line_ids in line_ids_by_multiplet.items()
        if len(line_ids) >= 2
    ]
    preset_store = _DummyIdentifyPresetStore(
        _DummyPreset(baseline_id, [line.line_id for line in lines], tie_groups)
    )
    main_window.preset_store = preset_store

    coordinator = IdentifyModeCoordinator(
        main_window,
        shell_ports=IdentifyShellPorts(
            current_project_provider=lambda: main_window.current_project,
            spectrum_view_provider=lambda: None,
            mode_state_provider=lambda: mode_state_store,
            preset_store_setter=lambda store: setattr(main_window, "preset_store", store),
            history_recorder_provider=lambda: None,
            velocity_runtime_provider=lambda: main_window.identify_velocity_runtime,
            preset_dialog_provider=lambda: main_window,
            undo_shortcut_provider=lambda: "Ctrl+Z",
        ),
        atomic_data=AtomicLineData(lines),
        preset_store=preset_store,
    )
    main_window.attach_coordinator(coordinator)

    status = _StatusRecorder()
    coordinator.status_message.connect(status.emit)
    coordinator._language_switcher = _DummyLanguageSwitcher()
    coordinator._atomic_data = _DummyAtomicData(lines)
    coordinator._current_preset_id = preset_store.current_preset_id

    return _CoordinatorHarness(
        coordinator=coordinator,
        project=active_project,
        status=status,
        main_window=main_window,
        preset_store=preset_store,
    )


def test_manual_temporary_line_adds_single_line() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Mg II",
        wavelength_angstrom=2803.0,
        oscillator_strength=0.6,
        gamma_value=1.0,
        multiplet_id="MGII",
    )
    harness = _build_coordinator([baseline], baseline.line_id)

    harness.coordinator.handle_manual_temporary_line(
        observed_wavelength=2803.0, modifiers=_shift_mask()
    )

    assert harness.session.temporary_count == 1
    line = harness.session.temporary_lines[0]
    assert line.line_id == "base"

    velocity_window = harness.session.new_candidate_analysis_half_width.kms
    expected_delta = baseline.wavelength_angstrom * (velocity_window / LIGHT_SPEED_KMS)
    assert abs(line.lambda_min - (baseline.wavelength_angstrom - expected_delta)) < 1e-6
    assert abs(line.lambda_max - (baseline.wavelength_angstrom + expected_delta)) < 1e-6
    assert abs(line.center_wavelength - baseline.wavelength_angstrom) < 1e-6
    assert abs(harness.session.reference_z) < 1e-12
    assert harness.session.last_click_wavelength == 2803.0
    assert harness.status.emitted
    assert "Temporary line added" in harness.status.emitted[0]


def test_manual_temporary_line_with_shift_adds_multiplet_members() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Mg II",
        wavelength_angstrom=2803.0,
        oscillator_strength=0.6,
        gamma_value=1.0,
        multiplet_id="MGII",
    )
    companion = AtomicLine(
        line_identifier="comp",
        species="Mg II",
        wavelength_angstrom=2796.0,
        oscillator_strength=0.3,
        gamma_value=1.0,
        multiplet_id="MGII",
    )
    harness = _build_coordinator([baseline, companion], baseline.line_id)

    harness.coordinator.handle_manual_temporary_line(
        observed_wavelength=2803.0, modifiers=_shift_mask()
    )

    assert harness.session.temporary_count == 2
    line_ids = {line.line_id for line in harness.session.temporary_lines}
    assert line_ids == {"base", "comp"}


def test_manual_temporary_line_skips_duplicates() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Mg II",
        wavelength_angstrom=2803.0,
        oscillator_strength=0.6,
        gamma_value=1.0,
        multiplet_id="MGII",
    )
    harness = _build_coordinator([baseline], baseline.line_id)

    harness.coordinator.handle_manual_temporary_line(
        observed_wavelength=2803.0, modifiers=_shift_mask()
    )
    harness.status.emitted.clear()

    harness.coordinator.handle_manual_temporary_line(
        observed_wavelength=2803.0, modifiers=_shift_mask()
    )

    assert harness.session.temporary_count == 1
    assert harness.status.emitted
    assert "already exists" in harness.status.emitted[-1]


def test_velocity_plot_context_uses_preset_lines() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Si II",
        wavelength_angstrom=1526.7,
        oscillator_strength=0.13,
        gamma_value=0.5,
        multiplet_id="SIII",
    )
    companion = AtomicLine(
        line_identifier="comp",
        species="Si II",
        wavelength_angstrom=1260.4,
        oscillator_strength=1.0,
        gamma_value=0.5,
        multiplet_id="SIII",
    )

    harness = _build_coordinator([baseline, companion], baseline.line_id)
    observed = baseline.wavelength_angstrom * 1.015

    context = harness.coordinator.request_velocity_plot(observed)
    assert context is not None

    expected_z = (observed / baseline.wavelength_angstrom) - 1.0
    assert math.isclose(context.center_z, expected_z, rel_tol=1e-9)
    assert context.rest_wavelength == baseline.wavelength_angstrom

    slice_ids = [slice_info.line_id for slice_info in context.slices]
    assert slice_ids[0] == baseline.line_id
    assert set(slice_ids) == {baseline.line_id, companion.line_id}

    # Baseline slice should be flagged as primary
    assert context.slices[0].is_primary is True
    assert any(slice_info.line_id == companion.line_id for slice_info in context.slices)
    assert context.slices[0].default_selected is True
    assert any(
        slice_info.line_id == companion.line_id and slice_info.default_selected
        for slice_info in context.slices
    )


def test_confirm_velocity_plot_selection_creates_lines() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Si II",
        wavelength_angstrom=1526.7,
        oscillator_strength=0.13,
        gamma_value=0.5,
        multiplet_id="SIII",
    )
    companion = AtomicLine(
        line_identifier="comp",
        species="Si II",
        wavelength_angstrom=1260.4,
        oscillator_strength=1.0,
        gamma_value=0.5,
        multiplet_id="SIII",
    )
    unrelated = AtomicLine(
        line_identifier="oth",
        species="Fe II",
        wavelength_angstrom=1608.5,
        oscillator_strength=0.2,
        gamma_value=0.4,
        multiplet_id="",
    )

    harness = _build_coordinator([baseline, companion, unrelated], baseline.line_id)
    observed = baseline.wavelength_angstrom * 1.01

    context = harness.coordinator.request_velocity_plot(observed)
    assert context is not None

    slice_infos = [
        VelocitySliceInfo(
            rest_wavelength=descriptor.rest_wavelength,
            label=descriptor.label,
            tie_group_key=descriptor.tie_group_key,
            line_id=descriptor.line_id,
            is_primary=descriptor.is_primary,
            default_selected=descriptor.default_selected,
            selected=descriptor.default_selected,
        )
        for descriptor in context.slices
    ]

    # Only select the baseline and its multiplet companion
    selected = [info for info in slice_infos if info.default_selected]

    harness.coordinator.confirm_velocity_plot_selection(center_z=context.center_z, slices=selected)

    assert harness.session.temporary_count == 2
    line_ids = {line.line_id for line in harness.session.temporary_lines}
    assert line_ids == {"base", "comp"}
    assert any("Added 2" in message for message in harness.status.emitted)


def test_confirm_velocity_plot_selection_requires_choice() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Si II",
        wavelength_angstrom=1526.7,
        oscillator_strength=0.13,
        gamma_value=0.5,
        multiplet_id="SIII",
    )

    harness = _build_coordinator([baseline], baseline.line_id)
    harness.status.emitted.clear()

    harness.coordinator.confirm_velocity_plot_selection(center_z=0.0, slices=[])

    assert harness.status.emitted
    assert "Select at least one line" in harness.status.emitted[-1]


def test_velocity_plot_refreshes_on_preset_update() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Si II",
        wavelength_angstrom=1526.7,
        oscillator_strength=0.13,
        gamma_value=0.5,
        multiplet_id="SIII",
    )
    harness = _build_coordinator([baseline], baseline.line_id)
    context = harness.coordinator.request_velocity_plot(baseline.wavelength_angstrom)
    assert context is not None

    harness.preset_store.preset_updated.emit(harness.preset_store.current_preset_id)

    assert harness.main_window.identify_velocity_runtime.refresh_velocity_overlay_called == 1
    assert harness.main_window.hide_velocity_plot_called == 0


def test_velocity_plot_hides_when_preset_selection_changes() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Si II",
        wavelength_angstrom=1526.7,
        oscillator_strength=0.13,
        gamma_value=0.5,
        multiplet_id="SIII",
    )
    harness = _build_coordinator([baseline], baseline.line_id)
    context = harness.coordinator.request_velocity_plot(baseline.wavelength_angstrom)
    assert context is not None

    harness.preset_store.select_replacement_preset("preset-2")

    assert harness.main_window.hide_velocity_plot_called == 1
    assert harness.main_window.identify_velocity_runtime.refresh_velocity_overlay_called == 0
    assert harness.preset_store.current_preset_id == "preset-2"
    assert harness.session.reference_z == 0.0


def test_registration_creates_absorption_lines() -> None:
    baseline = AtomicLine(
        line_identifier="base",
        species="Si II",
        wavelength_angstrom=1526.7,
        oscillator_strength=0.13,
        gamma_value=0.5,
        multiplet_id="SIII",
    )
    project = SpectroscopyProject()
    harness = _build_coordinator([baseline], baseline.line_id, project=project)

    session = harness.session
    velocity_window = session.new_candidate_analysis_half_width.kms
    rest = baseline.wavelength_angstrom
    delta = rest * (velocity_window / LIGHT_SPEED_KMS)
    lambda_min = rest - delta
    lambda_max = rest + delta

    session.add_temporary_line(
        baseline.species,
        lambda_min,
        lambda_max,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id=baseline.line_identifier,
            rest_wavelength=rest,
            center_z=0.0,
            multiplet_id="SIII",
            multiplet_label="",
            transition_name=f"{baseline.species} {rest:.1f}",
            oscillator_strength=0.13,
            gamma_value=0.5,
            tie_group_key="",
        ),
    )

    harness.coordinator._handle_registration_requested()

    assert project.absorption_lines
    line = next(iter(project.absorption_lines.values()))
    assert line.species == baseline.species
    assert line.lambda_range == (lambda_min, lambda_max)
    assert line.region_id is not None

    region = project.find_absorption_region(line.region_id)
    assert region is not None
    assert line.line_id in region.line_ids

    # NOTE: モデルの自動生成は無効化されたため、model_idsは空であることを確認
    # 仕様書に基づき、同定モードではラインと領域の作成のみ行い、
    # 実際のAbsorberComponent（吸収線コンポーネント）の作成は最適化モードで行う
    assert line.model_ids == []  # コンポーネントは作成されていないはず


def test_multiplet_union_respects_redshift_tolerance() -> None:
    mg2796 = AtomicLine(
        line_identifier="mg2796",
        species="Mg II",
        wavelength_angstrom=2795.528,
        oscillator_strength=0.5,
        gamma_value=1.0,
        multiplet_id="MGII-2796-2803",
    )
    mg2803 = AtomicLine(
        line_identifier="mg2803",
        species="Mg II",
        wavelength_angstrom=2802.705,
        oscillator_strength=0.5,
        gamma_value=1.0,
        multiplet_id="MGII-2796-2803",
    )

    harness = _build_coordinator([mg2796, mg2803], mg2796.line_id)
    session = harness.session
    tie_group_key = "preset:preset-1:fixture:MGII-2796-2803"

    def add_line(line: AtomicLine, center_z: float) -> None:
        observed_center = line.wavelength_angstrom * (1.0 + center_z)
        half_span = 1.8
        session.add_temporary_line(
            line.species,
            observed_center - half_span,
            observed_center + half_span,
            creation_method="test",
            context=TemporaryLineContext(
                line_id=line.line_id,
                rest_wavelength=line.wavelength_angstrom,
                center_z=center_z,
                tie_group_key=tie_group_key,
                multiplet_id="MGII-2796-2803",
                multiplet_label="",
                transition_name=f"{line.species} {line.wavelength_angstrom:.1f}",
                oscillator_strength=0.5,
                gamma_value=1.0,
            ),
        )

    group_a_z = 1.2098
    group_b_z = 1.2201

    add_line(mg2796, group_a_z)
    add_line(mg2803, group_a_z)
    add_line(mg2796, group_b_z)
    add_line(mg2803, group_b_z)

    previews = harness.coordinator._registration_workflow.build_region_previews(
        harness.session.temporary_lines
    )

    assert len(previews) == 2
    member_sizes = sorted(len(preview.member_temporary_line_ids) for preview in previews)
    assert member_sizes == [2, 2]

    # Ensure each preview keeps one member from each transition and stays disjoint
    groups = [set(preview.member_temporary_line_ids) for preview in previews]
    assert groups[0].isdisjoint(groups[1])

    line_by_id = {line.temporary_line_id: line for line in session.temporary_lines}
    for members in groups:
        identifiers = {line_by_id[member].line_id for member in members}
        assert identifiers == {"mg2796", "mg2803"}
