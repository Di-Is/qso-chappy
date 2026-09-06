"""Qt-independent Analysis navigation state and caller-owned ports."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from chappy.core.analysis import AnalysisReadiness
    from chappy.gui.modes.common.project_key import ProjectKey


class AnalysisSurface(StrEnum):
    """Mutually exclusive scopes within the future Analysis workspace."""

    OVERVIEW = "overview"
    REGION_DETAIL = "region_detail"


class AnalysisOverviewColumnId(StrEnum):
    """Stable semantic IDs shared by Overview persistence and its table model."""

    REGION = "region"
    STATUS = "status"
    FIT_RESULT = "fit_result"
    NEXT_ACTION = "next_action"


ANALYSIS_OVERVIEW_FULL_COLUMNS = (
    AnalysisOverviewColumnId.REGION,
    AnalysisOverviewColumnId.STATUS,
    AnalysisOverviewColumnId.FIT_RESULT,
    AnalysisOverviewColumnId.NEXT_ACTION,
)
ANALYSIS_OVERVIEW_DEFAULT_SORT_COLUMN = AnalysisOverviewColumnId.REGION


def normalize_analysis_overview_column_state(
    *,
    sort_column_id: str | None,
    visible_column_ids: tuple[str, ...],
    column_order: tuple[str, ...],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Return one valid, duplicate-free full-table column configuration."""
    canonical = tuple(column.value for column in ANALYSIS_OVERVIEW_FULL_COLUMNS)
    known = frozenset(canonical)

    if sort_column_id in known:
        normalized_sort = sort_column_id
    else:
        normalized_sort = ANALYSIS_OVERVIEW_DEFAULT_SORT_COLUMN.value

    normalized_visible = tuple(
        dict.fromkeys(column_id for column_id in visible_column_ids if column_id in known)
    )
    if not normalized_visible:
        normalized_visible = canonical

    ordered_known = tuple(
        dict.fromkeys(column_id for column_id in column_order if column_id in known)
    )
    normalized_order = (*ordered_known, *(item for item in canonical if item not in ordered_known))
    return normalized_sort, normalized_visible, normalized_order


@dataclass(frozen=True, slots=True)
class OpenAnalysisRegionIntent:
    """Request Region Detail for one stable current-project region ID."""

    region_id: str

    def __post_init__(self) -> None:
        """Reject empty IDs at the intent boundary."""
        if not self.region_id.strip():
            msg = "region_id must not be empty."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class OpenAnalysisStructureIntent:
    """Request the Overview structure editor for one stable current-project region ID."""

    region_id: str

    def __post_init__(self) -> None:
        """Reject empty IDs at the intent boundary."""
        if not self.region_id.strip():
            msg = "region_id must not be empty."
            raise ValueError(msg)


class AnalysisNavigationPersistenceOperation(StrEnum):
    """Navigation persistence operation that failed without blocking project use."""

    LOAD = "load"
    SAVE = "save"
    MIGRATE = "migrate"


class AnalysisNavigationSettingsError(RuntimeError):
    """Raised when local navigation settings cannot be updated durably."""


@dataclass(frozen=True, slots=True)
class AnalysisNavigationPersistenceIssue:
    """Typed non-fatal local-persistence failure published by the shell."""

    operation: AnalysisNavigationPersistenceOperation
    project_key: ProjectKey
    message: str


@dataclass(frozen=True, slots=True)
class StructureSelectionIds:
    """Session-only structure selection represented exclusively by IDs."""

    region_ids: tuple[str, ...] = ()
    line_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisNavigationSnapshot:
    """Project-key persisted subset of Analysis navigation state."""

    surface: AnalysisSurface = AnalysisSurface.OVERVIEW
    focused_region_id: str | None = None
    filter_text: str = ""
    filter_readiness: tuple[AnalysisReadiness, ...] = ()
    sort_column_id: str | None = None
    sort_ascending: bool = True
    visible_column_ids: tuple[str, ...] = ()
    column_order: tuple[str, ...] = ()
    top_visible_region_id: str | None = None
    spectrum_wavelength_range: tuple[float, float] | None = None
    show_error_spectrum: bool = True
    show_component_profiles: bool = False


@dataclass(frozen=True, slots=True)
class AnalysisNavigationState:
    """Complete runtime navigation state with no domain objects or row indexes."""

    surface: AnalysisSurface = AnalysisSurface.OVERVIEW
    focused_region_id: str | None = None
    overview_selection: str | None = None
    structure_selection: StructureSelectionIds = field(default_factory=StructureSelectionIds)
    filter_text: str = ""
    filter_readiness: tuple[AnalysisReadiness, ...] = ()
    sort_column_id: str | None = None
    sort_ascending: bool = True
    visible_column_ids: tuple[str, ...] = ()
    column_order: tuple[str, ...] = ()
    top_visible_region_id: str | None = None
    spectrum_wavelength_range: tuple[float, float] | None = None
    show_error_spectrum: bool = True
    show_component_profiles: bool = False

    @classmethod
    def from_snapshot(cls, snapshot: AnalysisNavigationSnapshot) -> AnalysisNavigationState:
        """Restore runtime state while reconstructing runtime-only selection."""
        return cls(
            surface=snapshot.surface,
            focused_region_id=snapshot.focused_region_id,
            overview_selection=snapshot.focused_region_id,
            filter_text=snapshot.filter_text,
            filter_readiness=snapshot.filter_readiness,
            sort_column_id=snapshot.sort_column_id,
            sort_ascending=snapshot.sort_ascending,
            visible_column_ids=snapshot.visible_column_ids,
            column_order=snapshot.column_order,
            top_visible_region_id=snapshot.top_visible_region_id,
            spectrum_wavelength_range=snapshot.spectrum_wavelength_range,
            show_error_spectrum=snapshot.show_error_spectrum,
            show_component_profiles=snapshot.show_component_profiles,
        )

    def persistent_snapshot(self) -> AnalysisNavigationSnapshot:
        """Return the project-key persisted subset of this runtime state."""
        return AnalysisNavigationSnapshot(
            surface=self.surface,
            focused_region_id=self.focused_region_id,
            filter_text=self.filter_text,
            filter_readiness=self.filter_readiness,
            sort_column_id=self.sort_column_id,
            sort_ascending=self.sort_ascending,
            visible_column_ids=self.visible_column_ids,
            column_order=self.column_order,
            top_visible_region_id=self.top_visible_region_id,
            spectrum_wavelength_range=self.spectrum_wavelength_range,
            show_error_spectrum=self.show_error_spectrum,
            show_component_profiles=self.show_component_profiles,
        )

    def with_surface(self, surface: AnalysisSurface) -> AnalysisNavigationState:
        """Return state using a different Analysis surface."""
        return replace(self, surface=surface)

    def with_focused_region(self, region_id: str | None) -> AnalysisNavigationState:
        """Change region focus."""
        return replace(self, focused_region_id=region_id, overview_selection=region_id)


class AnalysisNavigationSettingsPort(Protocol):
    """Persistent navigation operations required by the shell coordinator."""

    def load(self, key: ProjectKey) -> AnalysisNavigationSnapshot | None:
        """Load persistent state for a saved project key."""

    def save(self, key: ProjectKey, snapshot: AnalysisNavigationSnapshot) -> None:
        """Save persistent state for a saved project key."""

    def migrate(
        self, old_key: ProjectKey, new_key: ProjectKey, snapshot: AnalysisNavigationSnapshot
    ) -> None:
        """Copy state to a new saved key, sync it, and then remove the old key."""


class AnalysisRegionFocusPort(Protocol):
    """Region focus read/write boundary used by current and future mode panels."""

    def focus_region(self, region_id: str) -> bool:
        """Focus a valid current-project region by ID."""

    def focused_region_id(self) -> str | None:
        """Return the canonical Analysis Detail focused region ID, if any."""

    def clear_focus_if(self, region_id: str) -> None:
        """Clear canonical focus and return to Overview when it names the given region."""

    def clear_focus_only_if(self, region_id: str) -> None:
        """Clear canonical focus without changing the surface when it names the given region."""


class AnalysisOverviewNavigationPort(Protocol):
    """Overview-local navigation state operations represented only by IDs."""

    @property
    def state(self) -> AnalysisNavigationState:
        """Return the current immutable Analysis navigation state."""

    def select_overview_region(self, region_id: str | None) -> bool:
        """Update runtime Overview selection without opening Detail."""

    def update_overview_view(
        self,
        *,
        filter_text: str,
        filter_readiness: tuple[AnalysisReadiness, ...],
        sort_column_id: str | None,
        sort_ascending: bool,
        visible_column_ids: tuple[str, ...],
        column_order: tuple[str, ...],
        top_visible_region_id: str | None,
    ) -> None:
        """Persist the ID-based Overview view context."""

    def update_structure_selection(
        self, *, region_ids: tuple[str, ...], line_ids: tuple[str, ...]
    ) -> None:
        """Update session-only structure editor selection IDs."""


__all__ = [
    "ANALYSIS_OVERVIEW_DEFAULT_SORT_COLUMN",
    "ANALYSIS_OVERVIEW_FULL_COLUMNS",
    "AnalysisNavigationPersistenceIssue",
    "AnalysisNavigationPersistenceOperation",
    "AnalysisNavigationSettingsError",
    "AnalysisNavigationSettingsPort",
    "AnalysisNavigationSnapshot",
    "AnalysisNavigationState",
    "AnalysisOverviewColumnId",
    "AnalysisOverviewNavigationPort",
    "AnalysisRegionFocusPort",
    "AnalysisSurface",
    "OpenAnalysisRegionIntent",
    "OpenAnalysisStructureIntent",
    "StructureSelectionIds",
    "normalize_analysis_overview_column_state",
]
