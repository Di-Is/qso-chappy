"""Ports used by typed history commands."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from chappy.application.identify import TemporaryLineSnapshot

    from .models import ChangeSet
    from .resolution_commands import ResolutionHistoryPort


@dataclass(frozen=True, slots=True)
class RangeSnapshot:
    """Snapshot of visible spectrum ranges."""

    wavelength_range: tuple[float, float]
    flux_range: tuple[float, float] | None = None


class RangeHistoryPort(Protocol):
    """Port for applying range history snapshots."""

    def apply_range(self, snapshot: RangeSnapshot, *, source: Literal["history"]) -> ChangeSet:
        """Apply a spectrum range snapshot."""
        ...


@dataclass(frozen=True, slots=True)
class ContinuumPointSnapshot:
    """Snapshot of one continuum control point."""

    wavelength: float
    flux: float

    @staticmethod
    def from_position(position: tuple[float, float]) -> ContinuumPointSnapshot:
        """Create a point snapshot from a wavelength-flux tuple.

        Args:
            position: Wavelength and flux pair.

        Returns:
            Typed continuum point snapshot.
        """
        wavelength, flux = position
        return ContinuumPointSnapshot(wavelength=float(wavelength), flux=float(flux))

    def as_position(self) -> tuple[float, float]:
        """Return the point as a wavelength-flux tuple."""
        return (self.wavelength, self.flux)


@dataclass(frozen=True, slots=True)
class ContinuumComponentSnapshot:
    """Complete state required to recreate one continuum component."""

    component_id: str
    name: str
    enabled: bool
    is_shared_with_absorption: bool
    points: tuple[ContinuumPointSnapshot, ...]


class ContinuumHistoryPort(Protocol):
    """Port for applying continuum control point history."""

    def add_continuum_component(
        self, snapshot: ContinuumComponentSnapshot, *, index: int
    ) -> ChangeSet:
        """Recreate one continuum component from a typed snapshot."""
        ...

    def remove_continuum_component(self, continuum_id: str) -> ChangeSet:
        """Remove one continuum component by stable identity."""
        ...

    def replace_continuum_points(
        self, continuum_id: str, points: tuple[ContinuumPointSnapshot, ...]
    ) -> ChangeSet:
        """Replace all continuum control points."""
        ...


@dataclass(frozen=True, slots=True)
class NamedParameterState:
    """State of one named model parameter."""

    name: str
    value: float
    vary: bool
    min_value: float | None
    max_value: float | None
    error: float | None


@dataclass(frozen=True, slots=True)
class ComponentParameterState:
    """Parameter state for one absorber component."""

    component_id: str
    parameters: tuple[NamedParameterState, ...]


@dataclass(frozen=True, slots=True)
class AbsorberComponentParameterSnapshot:
    """Typed history snapshot of one absorber component parameter."""

    name: str
    value: float
    min_value: float
    max_value: float
    fixed: bool
    error: float
    unit: str | None


@dataclass(frozen=True, slots=True)
class AbsorberComponentSnapshot:
    """Typed history snapshot of one absorber model component."""

    component_id: str
    name: str
    enabled: bool
    wavelength: float
    oscillator_strength: float
    gamma: float
    group_id: str | None
    external_continuum_name: str | None
    parameters: tuple[AbsorberComponentParameterSnapshot, ...]


@dataclass(frozen=True, slots=True)
class ModelComponentLinkSnapshot:
    """Typed history snapshot of a line-to-component link."""

    line_id: str
    component_id: str
    index: int


@dataclass(frozen=True, slots=True)
class TieSetSnapshot:
    """Typed history snapshot of one parameter tie set."""

    uid: str
    tie_id: str
    name: str
    origin: str
    mask: tuple[str, ...]
    component_ids: tuple[str, ...]
    shared_parameters: tuple[NamedParameterState, ...]
    member_uids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LineOptimizationStateSnapshot:
    """Optimization-needed state for one absorption line."""

    line_id: str
    needs_optimization: bool


@dataclass(frozen=True, slots=True)
class AbsorptionRegionSnapshot:
    """Typed history snapshot of an absorption region."""

    region_id: str
    line_ids: tuple[str, ...]
    display_color: str
    analysis_range: tuple[float, float] | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AbsorptionLineSnapshot:
    """Typed history snapshot of an absorption line."""

    line_id: str
    species: str
    rest_wavelength: float
    center_z: float
    window_kms: float
    multiplet_label: str
    transition_name: str
    oscillator_strength: float
    gamma_value: float
    lambda_range: tuple[float, float] | None
    region_id: str | None
    multiplet_ids: tuple[str, ...]
    model_ids: tuple[str, ...]
    needs_optimization: bool
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MaskDefinitionSnapshot:
    """Typed history snapshot of a wavelength mask definition."""

    identifier: str
    label: str
    mode: str
    start_wavelength: float | None
    end_wavelength: float | None
    center: float | None
    half_width: float | None
    note: str
    color: str | None
    enabled: bool
    group_id: str | None

    def with_group_id(self, group_id: str | None) -> MaskDefinitionSnapshot:
        """Return a copy assigned to another region group."""
        return replace(self, group_id=group_id)


@dataclass(frozen=True, slots=True)
class LineRegionAssignment:
    """Target region assignment for one absorption line."""

    line_id: str
    region_id: str | None


@dataclass(frozen=True, slots=True)
class AbsorberComponentGroupAssignment:
    """Region association for one absorber model component."""

    component_id: str
    group_id: str | None


@dataclass(frozen=True, slots=True)
class StructureMoveHistoryPayload:
    """Complete exact before/after payload for one structure move."""

    expanded_line_ids: tuple[str, ...]
    source_assignments: tuple[LineRegionAssignment, ...]
    destination_assignments: tuple[LineRegionAssignment, ...]
    source_regions: tuple[AbsorptionRegionSnapshot, ...]
    destination_regions: tuple[AbsorptionRegionSnapshot, ...]
    source_masks: tuple[MaskDefinitionSnapshot, ...]
    destination_masks: tuple[MaskDefinitionSnapshot, ...]
    source_component_groups: tuple[AbsorberComponentGroupAssignment, ...]
    destination_component_groups: tuple[AbsorberComponentGroupAssignment, ...]

    @property
    def destination_region_id(self) -> str:
        """Return the one destination identity encoded by all target assignments."""
        region_ids = {assignment.region_id for assignment in self.destination_assignments}
        if len(region_ids) != 1 or None in region_ids:
            msg = "Structure move payload does not encode one destination region."
            raise ValueError(msg)
        return next(region_id for region_id in region_ids if region_id is not None)

    @property
    def created_new_region(self) -> bool:
        """Return whether the destination is absent from the source topology."""
        return self.destination_region_id not in {
            snapshot.region_id for snapshot in self.source_regions
        }

    @property
    def new_region_color(self) -> str | None:
        """Return the created destination color when applicable."""
        if not self.created_new_region:
            return None
        return next(
            (
                snapshot.display_color
                for snapshot in self.destination_regions
                if snapshot.region_id == self.destination_region_id
            ),
            None,
        )

    @property
    def auto_deleted_regions(self) -> tuple[AbsorptionRegionSnapshot, ...]:
        """Return source regions absent from the destination topology."""
        destination_ids = {snapshot.region_id for snapshot in self.destination_regions}
        return tuple(
            snapshot
            for snapshot in self.source_regions
            if snapshot.region_id not in destination_ids
        )


@dataclass(frozen=True, slots=True)
class StructureLineTopologySnapshot:
    """Exact structure-owned topology for one absorption line."""

    line_id: str
    region_id: str | None
    multiplet_ids: tuple[str, ...]
    model_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructureStateSnapshot:
    """Exact ordered region, mask, and absorber-group topology at one instant."""

    regions: tuple[AbsorptionRegionSnapshot, ...]
    lines: tuple[StructureLineTopologySnapshot, ...]
    masks: tuple[MaskDefinitionSnapshot, ...]
    component_groups: tuple[AbsorberComponentGroupAssignment, ...]


@dataclass(frozen=True, slots=True)
class StructureDeleteModelHistorySnapshot:
    """Model topology removed as part of one structure delete command."""

    components: tuple[AbsorberComponentSnapshot, ...]
    component_indices: tuple[int, ...]
    links: tuple[ModelComponentLinkSnapshot, ...]
    tie_sets: tuple[TieSetSnapshot, ...]
    tie_set_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MultipletLinkSnapshot:
    """Lost multiplet links for one deleted absorption line."""

    line_id: str
    related_line_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructureUnlinkHistoryPayload:
    """Exact before/after line-link topology for one unlink command."""

    line_ids: tuple[str, ...]
    affected_region_ids: tuple[str, ...]
    before_links: tuple[MultipletLinkSnapshot, ...]
    after_links: tuple[MultipletLinkSnapshot, ...]


@dataclass(frozen=True, slots=True)
class LineAnalysisHalfWidthStateSnapshot:
    """Scientific analysis half-width state for one absorption line."""

    line_id: str
    half_width_kms: float
    lambda_range: tuple[float, float] | None


class ModelHistoryPort(Protocol):
    """Port for applying model parameter history snapshots."""

    def restore_model_components(
        self,
        components: tuple[AbsorberComponentSnapshot, ...],
        *,
        component_indices: tuple[int, ...],
        links: tuple[ModelComponentLinkSnapshot, ...],
        tie_sets: tuple[TieSetSnapshot, ...],
        tie_set_indices: tuple[int, ...],
        removed_tie_uids: tuple[str, ...],
    ) -> ChangeSet:
        """Restore absorber components and their line links."""
        ...

    def remove_model_components(
        self,
        component_ids: tuple[str, ...],
        *,
        links: tuple[ModelComponentLinkSnapshot, ...],
        tie_sets: tuple[TieSetSnapshot, ...],
        tie_set_indices: tuple[int, ...],
        removed_tie_uids: tuple[str, ...],
    ) -> ChangeSet:
        """Remove absorber components and their line links."""
        ...

    def restore_component_parameters(
        self, states: tuple[ComponentParameterState, ...]
    ) -> ChangeSet:
        """Restore component parameter states."""
        ...

    def restore_tie_sets(
        self,
        snapshots: tuple[TieSetSnapshot, ...],
        *,
        tie_set_indices: tuple[int, ...],
        removed_uids: tuple[str, ...],
    ) -> ChangeSet:
        """Restore parameter tie set membership and origin from snapshots.

        Any currently registered tie set whose uid appears in ``removed_uids``
        or matches a snapshot's ``uid`` is unbound and cleared first, then
        each snapshot is rebuilt. Components are never added or removed.
        """
        ...

    def restore_line_optimization(
        self, states: tuple[LineOptimizationStateSnapshot, ...]
    ) -> ChangeSet:
        """Restore line optimization-needed states."""
        ...

    def clear_region_needs_optimization(self, region_id: str) -> ChangeSet:
        """Clear optimization-needed state for all lines in a region."""
        ...

    def restore_line_analysis_half_width_states(
        self, states: tuple[LineAnalysisHalfWidthStateSnapshot, ...], *, region_id: str
    ) -> ChangeSet:
        """Restore scientific line ranges while keeping the entire region stale."""
        ...


class StructureHistoryPort(Protocol):
    """Port for applying structure operation history snapshots."""

    def restore_absorption_regions(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore absorption regions from typed snapshots."""
        ...

    def apply_absorption_region_states_exact(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore exact current region fields and mapping order."""
        ...

    def apply_absorption_region_states_partial_exact(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore exact fields for a declared subset of current regions."""
        ...

    def restore_absorption_lines(
        self, snapshots: tuple[AbsorptionLineSnapshot, ...], *, restore_multiplet_links: bool
    ) -> ChangeSet:
        """Restore absorption lines from typed snapshots."""
        ...

    def apply_absorption_line_order_exact(self, line_ids: tuple[str, ...]) -> ChangeSet:
        """Restore exact current absorption-line mapping order."""
        ...

    def restore_masks(self, snapshots: tuple[MaskDefinitionSnapshot, ...]) -> ChangeSet:
        """Restore wavelength masks from typed snapshots."""
        ...

    def replace_masks_exact(self, snapshots: tuple[MaskDefinitionSnapshot, ...]) -> ChangeSet:
        """Replace the exact ordered mask collection."""
        ...

    def apply_absorber_component_groups(
        self, assignments: tuple[AbsorberComponentGroupAssignment, ...]
    ) -> ChangeSet:
        """Apply exact absorber component region associations."""
        ...

    def restore_mask_state(
        self, mask_id: str, snapshot: MaskDefinitionSnapshot | None, *, index: int | None
    ) -> ChangeSet:
        """Restore or remove one wavelength mask by identity."""
        ...

    def ensure_absorption_region(self, region_id: str, *, color: str | None) -> ChangeSet:
        """Ensure an absorption region exists."""
        ...

    def apply_line_region_assignments(
        self, assignments: tuple[LineRegionAssignment, ...]
    ) -> ChangeSet:
        """Assign lines to target regions."""
        ...

    def remove_empty_absorption_region(self, region_id: str) -> ChangeSet:
        """Remove a region if it has no lines."""
        ...

    def remove_absorption_lines(
        self, line_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        """Remove absorption lines by ID."""
        ...

    def remove_absorption_regions(
        self, region_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        """Remove absorption regions by ID."""
        ...

    def restore_multiplet_links(self, snapshots: tuple[MultipletLinkSnapshot, ...]) -> ChangeSet:
        """Restore multiplet cross-links."""
        ...

    def apply_multiplet_links_exact(
        self, line_ids: tuple[str, ...], snapshots: tuple[MultipletLinkSnapshot, ...]
    ) -> ChangeSet:
        """Apply exact multiplet links for a closed set of lines."""
        ...


class IdentifyHistoryPort(Protocol):
    """Port for applying identify operation history snapshots."""

    def restore_identify_temporary_lines(
        self, snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> ChangeSet:
        """Restore identify temporary lines from typed snapshots."""
        ...

    def remove_identify_temporary_lines(self, temporary_line_ids: tuple[str, ...]) -> ChangeSet:
        """Remove identify temporary lines by line ID."""
        ...

    def clear_identify_temporary_lines(self) -> ChangeSet:
        """Clear all identify temporary lines."""
        ...

    def update_identify_region_analysis_ranges(self, region_ids: tuple[str, ...]) -> ChangeSet:
        """Update analysis ranges for identify-affected regions."""
        ...


@dataclass(frozen=True, slots=True)
class HistoryCommandContext:
    """Read-only context passed to typed history commands."""

    range_port: RangeHistoryPort | None = None
    model_port: ModelHistoryPort | None = None
    structure_port: StructureHistoryPort | None = None
    identify_port: IdentifyHistoryPort | None = None
    continuum_port: ContinuumHistoryPort | None = None
    resolution_port: ResolutionHistoryPort | None = None

    def require_range_port(self) -> RangeHistoryPort:
        """Return the required range history port."""
        if self.range_port is None:
            msg = "Range history port is required."
            raise RuntimeError(msg)
        return self.range_port

    def require_model_port(self) -> ModelHistoryPort:
        """Return the required model history port."""
        if self.model_port is None:
            msg = "Model history port is required."
            raise RuntimeError(msg)
        return self.model_port

    def require_structure_port(self) -> StructureHistoryPort:
        """Return the required structure history port."""
        if self.structure_port is None:
            msg = "Structure history port is required."
            raise RuntimeError(msg)
        return self.structure_port

    def require_identify_port(self) -> IdentifyHistoryPort:
        """Return the required identify history port."""
        if self.identify_port is None:
            msg = "Identify history port is required."
            raise RuntimeError(msg)
        return self.identify_port

    def require_continuum_port(self) -> ContinuumHistoryPort:
        """Return the required continuum history port."""
        if self.continuum_port is None:
            msg = "Continuum history port is required."
            raise RuntimeError(msg)
        return self.continuum_port

    def require_resolution_port(self) -> ResolutionHistoryPort:
        """Return the required spectral-resolution history port."""
        if self.resolution_port is None:
            msg = "Resolution history port is required."
            raise RuntimeError(msg)
        return self.resolution_port
