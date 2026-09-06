"""Immutable user intents emitted inside the Analysis workspace."""

from __future__ import annotations

from dataclasses import dataclass

from chappy.gui.modes.common.analysis_navigation import (
    OpenAnalysisRegionIntent,
    OpenAnalysisStructureIntent,
)


def _require_id(value: str, *, field_name: str) -> None:
    if not value.strip():
        msg = f"{field_name} must not be empty."
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ReturnToOverviewIntent:
    """Return from Region Detail while preserving Overview view context."""


@dataclass(frozen=True, slots=True)
class OpenStructureEditorIntent:
    """Open the nested Overview structure editor with ID-only selection."""

    region_ids: tuple[str, ...] = ()
    line_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate every optional selection identifier."""
        for region_id in self.region_ids:
            _require_id(region_id, field_name="region_ids item")
        for line_id in self.line_ids:
            _require_id(line_id, field_name="line_ids item")


@dataclass(frozen=True, slots=True)
class CloseStructureEditorIntent:
    """Close the nested editor and restore the Overview summary panel."""


AnalysisWorkspaceIntent = (
    OpenAnalysisRegionIntent
    | OpenAnalysisStructureIntent
    | ReturnToOverviewIntent
    | OpenStructureEditorIntent
    | CloseStructureEditorIntent
)


__all__ = [
    "AnalysisWorkspaceIntent",
    "CloseStructureEditorIntent",
    "OpenAnalysisRegionIntent",
    "OpenAnalysisStructureIntent",
    "OpenStructureEditorIntent",
    "ReturnToOverviewIntent",
]
