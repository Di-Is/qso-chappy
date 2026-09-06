"""Application ports for spectrum-wide scientific settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from chappy.application.analysis_artifacts import GlobalAnalysisMutationProjectPort

if TYPE_CHECKING:
    from chappy.core.resolution import ResolutionState


class ResolutionProjectPort(GlobalAnalysisMutationProjectPort, Protocol):
    """Minimal project operation required by resolution use cases."""

    @property
    def resolution_state(self) -> ResolutionState:
        """Return the current instrumental resolution state."""
        ...

    def set_resolution(self, value: float, enabled: bool) -> None:
        """Apply resolution state to the project."""
        ...


@runtime_checkable
class ResolutionChangeNotifier(Protocol):
    """Notifier interface for consumers that react to resolution changes."""

    def notify_resolution_changed(self) -> None:
        """Notify that the current project resolution changed."""
        ...


__all__ = ["ResolutionChangeNotifier", "ResolutionProjectPort"]
