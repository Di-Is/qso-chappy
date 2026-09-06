"""Resolution update adapter for GUI controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.application.spectrum import (
    ResolutionChangeNotifier,
    ResolutionProjectPort,
    ResolutionUpdateResult,
    ResolutionUpdateUseCase,
)

if TYPE_CHECKING:
    from chappy.application.history import ResolutionHistoryRecorder


class ResolutionUpdateAdapter:
    """Delegate spectral resolution changes to an application use case."""

    def __init__(self, use_case: ResolutionUpdateUseCase) -> None:
        """Initialize the adapter.

        Args:
            use_case: Resolution update use case.
        """
        self._use_case = use_case

    def apply_resolution(
        self,
        project: ResolutionProjectPort,
        *,
        value: float,
        enabled: bool,
        notifier: ResolutionChangeNotifier | None,
        history_recorder: ResolutionHistoryRecorder,
    ) -> ResolutionUpdateResult:
        """Apply a spectral resolution value and notify interested consumers."""
        return self._use_case.apply_resolution(
            project,
            value=value,
            enabled=enabled,
            notifier=notifier,
            history_recorder=history_recorder,
        )


__all__ = [
    "ResolutionChangeNotifier",
    "ResolutionProjectPort",
    "ResolutionUpdateAdapter",
    "ResolutionUpdateResult",
]
