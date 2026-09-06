"""Shared models for typed history command application."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class HistoryApplyErrorCode(StrEnum):
    """Error code returned by history command application."""

    INVALID_STATE = "invalid_state"
    TARGET_NOT_FOUND = "target_not_found"


class HistoryApplyError(RuntimeError):
    """Exception raised by history ports when typed application fails."""

    def __init__(self, error_code: HistoryApplyErrorCode, message: str) -> None:
        """Initialize a typed history apply exception.

        Args:
            error_code: Machine-readable apply failure code.
            message: Human-readable diagnostic message.
        """
        super().__init__(message)
        self.error_code = error_code


class HistoryRefreshTarget(StrEnum):
    """UI target that should be refreshed after a history command applies."""

    SPECTRUM_RANGE = "spectrum_range"
    MODEL = "model"
    OPTIMIZE_PANEL = "optimize_panel"
    IDENTIFY_PANEL = "identify_panel"
    CONTINUUM_EDITOR = "continuum_editor"
    LINE_OVERLAYS = "line_overlays"
    VELOCITY_PLOT = "velocity_plot"
    OPTIMIZE_WAVELENGTH_MODEL_RESIDUAL = "optimize_wavelength_model_residual"


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """Summary of domain objects changed by history command application."""

    changed_component_ids: tuple[str, ...] = ()
    changed_line_ids: tuple[str, ...] = ()
    changed_region_ids: tuple[str, ...] = ()
    changed_temporary_line_ids: tuple[str, ...] = ()
    changed_continuum_ids: tuple[str, ...] = ()

    @staticmethod
    def empty() -> ChangeSet:
        """Return an empty change set."""
        return ChangeSet()


@dataclass(frozen=True, slots=True)
class HistoryApplyResult:
    """Result returned by typed history command application."""

    success: bool
    error_code: HistoryApplyErrorCode | None = None
    change_set: ChangeSet = field(default_factory=ChangeSet.empty)
    refresh_targets: tuple[HistoryRefreshTarget, ...] = ()

    @staticmethod
    def ok(
        *,
        change_set: ChangeSet | None = None,
        refresh_targets: tuple[HistoryRefreshTarget, ...] = (),
    ) -> HistoryApplyResult:
        """Create a successful apply result."""
        return HistoryApplyResult(
            success=True,
            change_set=change_set or ChangeSet.empty(),
            refresh_targets=refresh_targets,
        )

    @staticmethod
    def fail(error_code: HistoryApplyErrorCode) -> HistoryApplyResult:
        """Create a failed apply result."""
        return HistoryApplyResult(success=False, error_code=error_code)


def recoverable_history_apply_failure(error: HistoryApplyError) -> HistoryApplyResult:
    """Convert only stale-target history failures to recoverable apply results.

    Args:
        error: Typed history apply failure raised by a port.

    Returns:
        Recoverable failed apply result for stale command targets.

    Raises:
        HistoryApplyError: If the failure represents an internal state or wiring error.
    """
    if error.error_code is HistoryApplyErrorCode.TARGET_NOT_FOUND:
        return HistoryApplyResult.fail(error.error_code)
    raise error
