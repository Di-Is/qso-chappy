"""Unit tests for identify cursor preview logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from chappy.application.identify import BuildVelocityPreviewUseCase
from chappy.core.atomic_data import AtomicLine
from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
from chappy.gui.modes.identify.application_adapters import VelocityPreviewAdapter
from chappy.gui.modes.identify.cursor_preview_controller import (
    IdentifyCursorPreviewController,
    IdentifyCursorPreviewPorts,
    shift_modifier_value,
)
from chappy.gui.modes.identify.shared_surface_intent_controller import (
    IdentifySharedSurfaceIntentController,
    IdentifySharedSurfaceWorkflowPort,
)
from chappy.presentation.identify import CursorPreviewPayload

pytestmark = pytest.mark.usefixtures("qapp")


def _make_line(
    identifier: str, species: str, wavelength: float, *, multiplet: str = "", transition: str = ""
) -> AtomicLine:
    return AtomicLine(
        line_identifier=identifier,
        species=species,
        wavelength_angstrom=wavelength,
        oscillator_strength=0.1,
        gamma_value=1e8,
        multiplet_id=multiplet,
        transition_name=transition,
        multiplet_label="",
    )


def _build_entries(
    lines: list[AtomicLine],
    baseline: AtomicLine,
    *,
    velocity_window: float = 100.0,
    shift: bool = False,
    redshift: float = 0.0,
) -> list[dict[str, object]]:
    controller = _build_controller(lines=lines, baseline=baseline)
    tie_group_keys = {
        line.line_id: f"test:{line.multiplet_id}" for line in lines if line.multiplet_id
    }
    return controller.build_cursor_preview_entries(
        lines=lines,
        baseline_line=baseline,
        redshift=redshift,
        new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(velocity_window),
        shift_pressed=shift,
        tie_group_keys=tie_group_keys,
    )


def _build_controller(
    *,
    lines: list[AtomicLine],
    baseline: AtomicLine | None,
    active: bool = True,
    active_provider: Callable[[], bool] | None = None,
    velocity_window: float = 100.0,
    preview_calls: list[CursorPreviewPayload | None] | None = None,
) -> IdentifyCursorPreviewController:
    preview_adapter = VelocityPreviewAdapter(BuildVelocityPreviewUseCase())
    return IdentifyCursorPreviewController(
        IdentifyCursorPreviewPorts(
            identify_mode_active_provider=active_provider or (lambda: active),
            new_candidate_analysis_half_width_provider=lambda: NewCandidateAnalysisHalfWidth(
                velocity_window
            ),
            baseline_line_provider=lambda: baseline,
            current_lines_provider=lambda: lines,
            observed_wavelength_bounds_provider=lambda: None,
            preview_builder=preview_adapter,
            preview_sink=(
                preview_calls.append if preview_calls is not None else lambda _payload: None
            ),
            preview_hint_provider=lambda: "Shift hint",
            tie_group_keys_provider=lambda: {},
        )
    )


def test_preview_includes_only_baseline_without_shift() -> None:
    baseline = _make_line("base", "C IV", 1550.0, transition="1550")
    extra = _make_line("extra", "C IV", 1548.2)

    entries = _build_entries([baseline, extra], baseline, shift=False)

    assert len(entries) == 1
    assert entries[0]["line_id"] == "base"


def test_preview_includes_multiplet_members_without_shift() -> None:
    baseline = _make_line("base", "Mg II", 2803.0, multiplet="MGII", transition="2803")
    companion = _make_line("comp", "Mg II", 2796.0, multiplet="MGII")

    entries = _build_entries([baseline, companion], baseline, shift=False)

    assert {entry["line_id"] for entry in entries} == {"base", "comp"}


def test_preview_shift_includes_all_lines() -> None:
    baseline = _make_line("base", "Si II", 1526.0)
    others = [_make_line(f"l{idx}", "Si II", 1526.0 + idx * 0.1) for idx in range(1, 4)]

    entries_no_shift = _build_entries([baseline, *others], baseline, shift=False)
    entries_shift = _build_entries([baseline, *others], baseline, shift=True)

    assert len(entries_no_shift) == 1
    assert len(entries_shift) == 4


def test_preview_limits_labels_and_avoids_overlap() -> None:
    baseline = _make_line("base", "Si II", 1526.0)
    dense_lines = [_make_line(f"l{idx}", "Si II", 1526.0 + idx * 0.01) for idx in range(1, 12)]

    entries = _build_entries([baseline, *dense_lines], baseline, velocity_window=80.0, shift=True)

    labelled = [entry for entry in entries if entry.get("label")]

    assert len(entries) == 12
    assert len(labelled) <= 8


def test_preview_keeps_multiplet_member_labels() -> None:
    baseline = _make_line("base", "C IV", 1548.2043, multiplet="CIV", transition="1548")
    partner = _make_line("partner", "C IV", 1550.781, multiplet="CIV", transition="1550")
    crowded = [
        _make_line(
            f"crowd{idx}", "Si II", 1548.2043 + idx * 0.005, transition=str(1548.2043 + idx)
        )
        for idx in range(1, 9)
    ]

    entries = _build_entries([baseline, partner, *crowded], baseline, shift=True)

    entry_map = {entry["line_id"]: entry for entry in entries}

    assert entry_map["base"].get("label")
    assert entry_map["partner"].get("label")


def test_preview_lock_enable_keeps_active_shift_preview() -> None:
    baseline = _make_line("base", "C IV", 1550.0, transition="1550")
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.handle_cursor_position(3100.0, 0.0, shift_modifier_value())
    preview_calls.clear()

    controller.set_preview_always_on(True)

    assert controller.preview_always_on() is True
    assert preview_calls == []


def test_preview_lock_disable_clears_overlay() -> None:
    baseline = _make_line("base", "C IV", 1550.0, transition="1550")
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.handle_cursor_position(3100.0, 0.0, shift_modifier_value())
    controller.set_preview_always_on(True)
    preview_calls.clear()

    controller.set_preview_always_on(False)

    assert controller.preview_always_on() is False
    assert preview_calls == [None]


def test_preview_lock_toggle_reuses_cursor_without_shift_guidance() -> None:
    """A local lock toggle retains position without manufacturing Shift state."""
    baseline = _make_line("base", "C IV", 1550.0, transition="1550")
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.set_preview_always_on(True)
    controller.handle_cursor_position(3100.5, 0.0, 0)

    controller.set_preview_always_on(False)
    controller.set_preview_always_on(True)

    payload = preview_calls[-1]
    assert payload is not None
    assert payload["observed_cursor"] == 3100.5
    assert "hint_text" not in payload


def test_shift_preview_exposes_same_observed_wavelength_and_hint() -> None:
    """Velocity verification reads the exact wavelength held by typed preview state."""
    baseline = _make_line("base", "C IV", 1550.0)
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )

    controller.handle_cursor_position(3101.25, 0.0, shift_modifier_value())

    payload = preview_calls[-1]
    assert payload is not None
    assert payload["observed_cursor"] == 3101.25
    assert payload["hint_text"] == "Shift hint"


def test_velocity_intent_forgets_shift_state_before_later_reapply() -> None:
    """Velocity entry cannot resurrect the consumed Shift preview."""
    baseline = _make_line("base", "C IV", 1550.0)
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.handle_cursor_position(3101.75, 0.0, shift_modifier_value())
    toggles: list[float | None] = []
    surface = IdentifySharedSurfaceIntentController(
        workflow_provider=lambda: cast(IdentifySharedSurfaceWorkflowPort, controller),
        velocity_toggle_callback=toggles.append,
        cursor_wavelength_provider=lambda: 3101.75,
    )

    surface.handle_mode_velocity_shortcut()
    calls_after_velocity_entry = list(preview_calls)
    controller.reapply_cursor_preview()
    controller.set_preview_always_on(True)

    assert toggles == [3101.75]
    assert calls_after_velocity_entry[-1] is None
    assert preview_calls == calls_after_velocity_entry


def test_mode_leave_forgets_shift_state_before_reentry_and_lock() -> None:
    """Mode re-entry and preview lock cannot restore pre-leave Shift guidance."""
    baseline = _make_line("base", "C IV", 1550.0)
    preview_calls: list[CursorPreviewPayload | None] = []
    active_state = {"identify": True}
    controller = _build_controller(
        lines=[baseline],
        baseline=baseline,
        active_provider=lambda: active_state["identify"],
        preview_calls=preview_calls,
    )
    controller.handle_cursor_position(3102.25, 0.0, shift_modifier_value())

    active_state["identify"] = False
    controller.clear_cursor_preview()
    calls_after_mode_leave = list(preview_calls)
    active_state["identify"] = True
    controller.set_preview_always_on(True)
    controller.reapply_cursor_preview()

    assert calls_after_mode_leave[-1] is None
    assert preview_calls == calls_after_mode_leave


def test_preview_lock_without_shift_has_no_velocity_verification_hint() -> None:
    """Forced preview lock remains distinct from a Shift verification preview."""
    baseline = _make_line("base", "C IV", 1550.0)
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.set_preview_always_on(True)

    controller.handle_cursor_position(3102.0, 0.0, 0)

    payload = preview_calls[-1]
    assert payload is not None
    assert "hint_text" not in payload


def test_shift_release_clears_preview_but_velocity_shortcut_still_toggles() -> None:
    """Releasing Shift clears stale verification state without disabling the shortcut."""
    baseline = _make_line("base", "C IV", 1550.0)
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.handle_cursor_position(3104.25, 0.0, shift_modifier_value())
    toggles: list[float | None] = []
    surface = IdentifySharedSurfaceIntentController(
        workflow_provider=lambda: cast(IdentifySharedSurfaceWorkflowPort, controller),
        velocity_toggle_callback=toggles.append,
        cursor_wavelength_provider=lambda: 3104.25,
    )

    controller.handle_shift_released()
    surface.handle_mode_velocity_shortcut()

    assert preview_calls[-1] is None
    assert toggles == [3104.25]


def test_shift_release_reapplies_locked_preview_without_hint_or_target() -> None:
    """Preview lock preserves the overlay but never retains Shift-only guidance."""
    baseline = _make_line("base", "C IV", 1550.0)
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(
        lines=[baseline], baseline=baseline, preview_calls=preview_calls
    )
    controller.set_preview_always_on(True)
    controller.handle_cursor_position(3105.5, 0.0, shift_modifier_value())

    controller.handle_shift_released()

    payload = preview_calls[-1]
    assert payload is not None
    assert payload["observed_cursor"] == 3105.5
    assert "hint_text" not in payload

    controller.reapply_cursor_preview()

    reapplied_payload = preview_calls[-1]
    assert reapplied_payload is not None
    assert reapplied_payload["observed_cursor"] == 3105.5
    assert "hint_text" not in reapplied_payload


def test_locked_shift_release_clears_stale_overlay_when_dependencies_become_invalid() -> None:
    """A failed forced rebuild still removes the prior Shift hint and overlay."""
    baseline = _make_line("base", "C IV", 1550.0)
    lines = [baseline]
    preview_calls: list[CursorPreviewPayload | None] = []
    controller = _build_controller(lines=lines, baseline=baseline, preview_calls=preview_calls)
    controller.set_preview_always_on(True)
    controller.handle_cursor_position(3106.5, 0.0, shift_modifier_value())
    assert preview_calls[-1] is not None
    lines.clear()

    controller.handle_shift_released()

    assert preview_calls[-1] is None
