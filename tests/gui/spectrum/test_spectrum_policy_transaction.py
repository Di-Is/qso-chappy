"""Atomic policy transition tests for the shared spectrum view."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.gui.spectrum.policy import (
    SpectrumPolicy,
    SpectrumPolicyCleanupError,
    SpectrumTransitionCleanup,
)
from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
from chappy.gui.spectrum.spectrum_view import SpectrumView
from chappy.presentation.interaction.interaction_contracts import InteractionPhase


class _Signal:
    def __init__(self, *, fail: bool = False) -> None:
        self.values: list[SpectrumPolicy | None] = []
        self.fail = fail

    def emit(self, policy: SpectrumPolicy | None = None) -> None:
        self.values.append(policy)
        if self.fail:
            raise RuntimeError("observer failed")


class _Coordinator:
    def __init__(self, initial: SpectrumPolicy, calls: list[str]) -> None:
        self.state = initial
        self.calls = calls
        self.fail_once_for: SpectrumPolicy | None = None
        self.fail_for: SpectrumPolicy | None = None
        self.fail_preflight = False
        self.fail_cleanup = False

    def preflight_policy(self, _policy: SpectrumPolicy) -> None:
        self.calls.append("coordinator-preflight")
        if self.fail_preflight:
            raise RuntimeError("preflight failed")

    def cleanup_for_policy(self, _policy: SpectrumPolicy) -> None:
        self.calls.append("cleanup")
        if self.fail_cleanup:
            raise RuntimeError("cleanup failed")

    def commit_policy(self, policy: SpectrumPolicy) -> None:
        self.calls.append(f"coordinator-commit:{policy.cursor_enabled}")
        self.state = policy
        if self.fail_once_for is policy:
            self.fail_once_for = None
            raise RuntimeError("coordinator commit failed")
        if self.fail_for is policy:
            raise RuntimeError("coordinator rollback failed")

    def invalidate_policy(self) -> None:
        self.calls.append("coordinator-invalidated")
        self.state = None


class _PlotHost:
    def __init__(self, initial: SpectrumPolicy, calls: list[str]) -> None:
        self.state = initial.plot_policy
        self.calls = calls
        self.fail_once_for: SpectrumPolicy | None = None

    def preflight_policy(self, _policy: object) -> None:
        self.calls.append("plot-preflight")

    def apply_policy(self, policy: object) -> None:
        self.calls.append("plot-commit")
        self.state = policy
        if self.fail_once_for is not None and policy is self.fail_once_for.plot_policy:
            self.fail_once_for = None
            raise RuntimeError("plot commit failed")

    def invalidate_policy(self) -> None:
        self.calls.append("plot-invalidated")
        self.state = None


class _View:
    def __init__(self, initial: SpectrumPolicy, *, observer_fails: bool = False) -> None:
        self.calls: list[str] = []
        self.coordinator = _Coordinator(initial, self.calls)
        self.plot_host = _PlotHost(initial, self.calls)
        self._current_policy: SpectrumPolicy | None = initial
        self.start_active = initial.start_overlay_active
        self.policy_applied = _Signal(fail=observer_fails)
        self.policy_invalidated = _Signal()

    def clear_reset_ranges(self) -> None:
        self.calls.append("clear-reset")

    def set_start_mode_active(self, active: bool) -> None:
        self.calls.append(f"overlay:{active}")
        self.start_active = active


@pytest.mark.parametrize("failure_owner", ("plot", "coordinator"))
def test_policy_commit_failure_rolls_back_every_reversible_owner(failure_owner: str) -> None:
    """Failure after cleanup must not leave mixed capabilities or current policy."""
    old = spectrum_interaction_mode_policy(EditingMode.IDENTIFY)
    new = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)
    view = _View(old)
    if failure_owner == "plot":
        view.plot_host.fail_once_for = new
    else:
        view.coordinator.fail_once_for = new

    with pytest.raises(RuntimeError, match="commit failed"):
        SpectrumView.apply_policy(cast("SpectrumView", view), new)

    assert view._current_policy is old
    assert view.coordinator.state is old
    assert view.plot_host.state is old.plot_policy
    assert view.start_active is old.start_overlay_active
    assert view.policy_applied.values == []


def test_policy_commit_order_and_observer_failure_isolation() -> None:
    """Observers run only after the full commit and cannot undo it."""
    old = spectrum_interaction_mode_policy(EditingMode.IDENTIFY)
    new = analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL)
    view = _View(old, observer_fails=True)

    SpectrumView.apply_policy(cast("SpectrumView", view), new)

    assert view.calls == [
        "coordinator-preflight",
        "plot-preflight",
        "cleanup",
        "clear-reset",
        "plot-commit",
        "coordinator-commit:True",
        "overlay:False",
    ]
    assert view._current_policy is new
    assert view.coordinator.state is new
    assert view.plot_host.state is new.plot_policy
    assert view.policy_applied.values == [new]


def test_rollback_failure_enters_unknown_disabled_policy_state() -> None:
    """Rollback failure must never advertise the previous policy as current."""
    old = spectrum_interaction_mode_policy(EditingMode.IDENTIFY)
    new = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)
    view = _View(old)
    view.coordinator.fail_once_for = new
    view.coordinator.fail_for = old

    with pytest.raises(RuntimeError, match="coordinator commit failed"):
        SpectrumView.apply_policy(cast("SpectrumView", view), new)

    assert view._current_policy is None
    assert view.coordinator.state is None
    assert view.plot_host.state is None
    assert view.policy_applied.values == []
    assert len(view.policy_invalidated.values) == 1


def test_preflight_failure_prevents_cleanup_and_commit() -> None:
    """Validation failure leaves pending interaction and all policy owners untouched."""
    old = spectrum_interaction_mode_policy(EditingMode.IDENTIFY)
    new = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)
    view = _View(old)
    view.coordinator.fail_preflight = True

    with pytest.raises(RuntimeError, match="preflight failed"):
        SpectrumView.apply_policy(cast("SpectrumView", view), new)

    assert view.calls == ["coordinator-preflight"]
    assert view._current_policy is old
    assert view.coordinator.state is old
    assert view.plot_host.state is old.plot_policy


def test_cleanup_failure_prevents_reversible_commit() -> None:
    """Cleanup errors stop before any capability, plot, or current-policy commit."""
    old = spectrum_interaction_mode_policy(EditingMode.IDENTIFY)
    new = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)
    view = _View(old)
    view.coordinator.fail_cleanup = True

    with pytest.raises(RuntimeError, match="cleanup failed"):
        SpectrumView.apply_policy(cast("SpectrumView", view), new)

    assert view.calls == ["coordinator-preflight", "plot-preflight", "cleanup", "clear-reset"]
    assert view._current_policy is old
    assert view.coordinator.state is old
    assert view.plot_host.state is old.plot_policy


class _CleanupHarness:
    def __init__(self, fail_stage: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_stage = fail_stage
        self._latest_interaction_snapshot = type(
            "Snapshot", (), {"phase": InteractionPhase.ACTIVE}
        )()

    def cancel_mask_selection(self) -> None:
        self.calls.append("mask")
        if self.fail_stage == "mask":
            raise RuntimeError("mask cleanup failed")

    def cancel_active_drags(self) -> bool:
        self.calls.append("drag")
        if self.fail_stage == "drag":
            raise RuntimeError("drag cleanup failed")
        return True

    def set_interaction_mode(self, mode: str | None) -> None:
        assert mode is None
        self.calls.append("interaction")
        if self.fail_stage == "interaction":
            raise RuntimeError("interaction cleanup failed")

    @staticmethod
    def _is_terminal_phase(phase: InteractionPhase) -> bool:
        return phase in (InteractionPhase.IDLE, InteractionPhase.CANCELLED)


def test_cleanup_flags_control_each_step_and_preserve_declared_order() -> None:
    """Cleanup is single-owner, ordered, and every step can be disabled."""
    policy = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)
    enabled = _CleanupHarness()
    SpectrumInteractionCoordinator.cleanup_for_policy(
        cast("SpectrumInteractionCoordinator", enabled), policy
    )
    assert enabled.calls == ["mask", "drag", "interaction"]

    disabled = _CleanupHarness()
    no_cleanup = replace(
        policy,
        transition_cleanup=SpectrumTransitionCleanup(
            cancel_mask_selection=False,
            cancel_absorber_drag=False,
            clear_interaction_mode=False,
            clear_reset_ranges=False,
        ),
    )
    SpectrumInteractionCoordinator.cleanup_for_policy(
        cast("SpectrumInteractionCoordinator", disabled), no_cleanup
    )
    assert disabled.calls == []


@pytest.mark.parametrize("failure_stage", ("mask", "drag", "interaction"))
def test_cleanup_stage_failure_attempts_every_remaining_stage(failure_stage: str) -> None:
    """One irreversible cleanup failure cannot skip later cleanup stages."""
    harness = _CleanupHarness(failure_stage)
    policy = spectrum_interaction_mode_policy(EditingMode.ANALYSIS)

    with pytest.raises(SpectrumPolicyCleanupError) as exc_info:
        SpectrumInteractionCoordinator.cleanup_for_policy(
            cast("SpectrumInteractionCoordinator", harness), policy
        )

    assert harness.calls == ["mask", "drag", "interaction"]
    assert len(exc_info.value.errors) == 1
