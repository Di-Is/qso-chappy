"""Typed row models for the identify side panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(slots=True)
class LineListItem:
    """Representation of a preset line entry."""

    identifier: str
    reference: str
    name: str
    wavelength: float
    oscillator_strength: float
    is_reference: bool = False
    multiplet_id: str = ""


@dataclass(slots=True)
class CandidateRow:
    """Representation of a detection candidate row."""

    identifier: str
    lambda_start: float
    lambda_end: float
    sigma: float
    status: str  # identified | candidate | unused


@dataclass(frozen=True, slots=True)
class CandidateTableItemPayload:
    """Typed payload stored in the identify candidate table."""

    candidate_id: str
    lambda_start: float


@dataclass(slots=True)
class TemporaryLineRow:
    """Representation of a temporary line row in workflow tab.

    For multiplet groups, temporary_line_ids contains multiple IDs with the primary ID first.
    """

    temporary_line_ids: tuple[str, ...]  # Primary ID first, then others in rest_wavelength order
    species: str
    lambda_start: float
    lambda_end: float
    creation_method: str
    transition_name: str  # Required (from TemporaryLine)
    redshift: float | None = None  # center_z from TemporaryLine
    display_id: int = 0  # 1-based display index for consistency with other modes
    multiplet_label: str = ""  # Multiplet name for display


@dataclass(slots=True)
class RegionPreviewRow:
    """Representation of a grouping preview entry."""

    group_id: str
    label: str
    member_count: int
    warning: bool = False
    is_existing_group: bool = False
    old_member_count: int | None = None
    new_lines_count: int = 0
    member_temporary_line_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConfirmedLineRow:
    """Representation of a confirmed line within a group."""

    line_id: str
    species: str  # e.g., "Mg II 2796/2803" (multiplet combined)
    redshift: float  # z value
    lambda_start: float
    lambda_end: float
    transition_name: str | None = None
    display_id: int = 0  # 1-based display index for consistency with other modes


@dataclass(slots=True)
class ConfirmedRegionRow:
    """Representation of a confirmed absorption region."""

    group_id: str
    label: str  # e.g., "Group 1"
    lines: list[ConfirmedLineRow]
    is_expanded: bool = False  # For accordion state


class IdentifyWorkflowItemKind(Enum):
    """Typed item categories stored in workflow tree item payloads."""

    TEMPORARY_LINE = "temporary_line"
    CONFIRMED_GROUP = "confirmed_group"
    CONFIRMED_LINE = "confirmed_line"


@dataclass(frozen=True, slots=True)
class TemporaryLineItemPayload:
    """Tree payload for a temporary line row."""

    primary_temporary_line_id: str
    temporary_line_ids: tuple[str, ...]

    @property
    def kind(self) -> IdentifyWorkflowItemKind:
        """Return the payload category."""
        return IdentifyWorkflowItemKind.TEMPORARY_LINE


@dataclass(frozen=True, slots=True)
class ConfirmedGroupItemPayload:
    """Tree payload for a confirmed or preview group row."""

    group_id: str

    @property
    def kind(self) -> IdentifyWorkflowItemKind:
        """Return the payload category."""
        return IdentifyWorkflowItemKind.CONFIRMED_GROUP


@dataclass(frozen=True, slots=True)
class ConfirmedLineItemPayload:
    """Tree payload for a confirmed line row."""

    line_id: str

    @property
    def kind(self) -> IdentifyWorkflowItemKind:
        """Return the payload category."""
        return IdentifyWorkflowItemKind.CONFIRMED_LINE


type IdentifyWorkflowItemPayload = (
    TemporaryLineItemPayload | ConfirmedGroupItemPayload | ConfirmedLineItemPayload
)
