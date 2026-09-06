"""Caller-owned ports for analysis artifact queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from chappy.core.analysis import RegionAnalysisState


class AnalysisReadinessSourcePort(Protocol):
    """Read-only project facts required to derive region readiness."""

    def region_analysis_state(self, region_id: str) -> RegionAnalysisState | None:
        """Return current project-owned analysis state for one region."""
        ...

    def region_requires_reanalysis(self, region_id: str) -> bool:
        """Return whether any region input requires reanalysis."""
        ...


class AnalysisArtifactStorePort(AnalysisReadinessSourcePort, Protocol):
    """Writable project boundary for region analysis state."""

    def is_region_analysis_capable(self, region_id: str) -> bool:
        """Return whether the region satisfies analysis prerequisites."""
        ...

    def set_region_analysis_state(self, state: RegionAnalysisState) -> None:
        """Replace one existing region's analysis state."""
        ...

    def region_analysis_states(self) -> tuple[RegionAnalysisState, ...]:
        """Return current state for every project region."""
        ...

    def set_region_analysis_states(self, states: Iterable[RegionAnalysisState]) -> None:
        """Atomically replace state for multiple existing regions."""
        ...

    def remove_region_analysis_state(self, region_id: str) -> None:
        """Remove explicitly stored state for one region."""
        ...
