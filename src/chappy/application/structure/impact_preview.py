"""Side-effect-free impact previews for scientific structure operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from chappy.application.structure.models import StructureMutationOutcome
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.components.absorber import AbsorberComponent

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.components.base import ModelComponent
    from chappy.core.masking import MaskDefinition


class StructureImpactOperation(StrEnum):
    """Structure operation represented by an impact preview."""

    MOVE = "move"
    SPLIT = "split"
    MERGE = "merge"
    UNLINK = "unlink"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class MoveStructureRequest:
    """Request to move expanded linked lines to an existing or new region."""

    line_ids: tuple[str, ...]
    target_region_id: str | None


@dataclass(frozen=True, slots=True)
class SplitStructureRequest:
    """Request to move expanded linked lines into one new region."""

    line_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MergeStructureRequest:
    """Request to merge regions into the first listed region."""

    region_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnlinkStructureRequest:
    """Request to clear one materialized linked-line group's links."""

    line_id: str


@dataclass(frozen=True, slots=True)
class DeleteStructureRequest:
    """Request to delete regions and multiplet-expanded linked lines."""

    region_ids: tuple[str, ...] = ()
    line_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureImpactPreview:
    """Exact known identities affected by a structure operation.

    A newly created region has no stable identity until the current domain API
    commits it, so previews expose its count separately. Every other count is
    derived from the normalized identity tuple and cannot disagree with it.
    """

    operation: StructureImpactOperation
    outcome: StructureMutationOutcome
    changed_region_ids: tuple[str, ...] = ()
    removed_region_ids: tuple[str, ...] = ()
    created_region_count: int = 0
    expanded_request_line_ids: tuple[str, ...] = ()
    changed_line_ids: tuple[str, ...] = ()
    removed_line_ids: tuple[str, ...] = ()
    changed_model_ids: tuple[str, ...] = ()
    removed_model_ids: tuple[str, ...] = ()
    changed_mask_ids: tuple[str, ...] = ()
    removed_mask_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize identities and require outcome/impact consistency."""
        identity_fields = (
            "changed_region_ids",
            "removed_region_ids",
            "expanded_request_line_ids",
            "changed_line_ids",
            "removed_line_ids",
            "changed_model_ids",
            "removed_model_ids",
            "changed_mask_ids",
            "removed_mask_ids",
        )
        for field_name in identity_fields:
            identities = tuple(dict.fromkeys(getattr(self, field_name)))
            if any(not identity for identity in identities):
                msg = f"Structure impact {field_name} cannot contain an empty identity."
                raise ValueError(msg)
            object.__setattr__(self, field_name, identities)

        if self.created_region_count < 0:
            msg = "Structure impact created region count cannot be negative."
            raise ValueError(msg)

        disjoint_pairs = (
            (self.changed_region_ids, self.removed_region_ids, "region"),
            (self.changed_line_ids, self.removed_line_ids, "line"),
            (self.changed_model_ids, self.removed_model_ids, "model"),
            (self.changed_mask_ids, self.removed_mask_ids, "mask"),
        )
        for changed_ids, removed_ids, label in disjoint_pairs:
            if set(changed_ids) & set(removed_ids):
                msg = f"Changed and removed structure {label} identities must be disjoint."
                raise ValueError(msg)

        has_impact = self.created_region_count > 0 or any(
            getattr(self, field_name) for field_name in identity_fields
        )
        if self.outcome is StructureMutationOutcome.CHANGED and not has_impact:
            msg = "A changed structure impact preview must contain an impact."
            raise ValueError(msg)
        if self.outcome is StructureMutationOutcome.NO_CHANGE and has_impact:
            msg = "A no-change structure impact preview cannot contain an impact."
            raise ValueError(msg)

    @property
    def changed(self) -> bool:
        """Return whether executing the request would change structure."""
        return self.outcome is StructureMutationOutcome.CHANGED

    @property
    def changed_region_count(self) -> int:
        """Return the number of known existing regions that would change."""
        return len(self.changed_region_ids)

    @property
    def removed_region_count(self) -> int:
        """Return the number of regions that would be removed."""
        return len(self.removed_region_ids)

    @property
    def changed_line_count(self) -> int:
        """Return the number of surviving lines that would change."""
        return len(self.changed_line_ids)

    @property
    def removed_line_count(self) -> int:
        """Return the number of lines that would be removed."""
        return len(self.removed_line_ids)

    @property
    def changed_model_count(self) -> int:
        """Return the number of surviving model components that would change."""
        return len(self.changed_model_ids)

    @property
    def removed_model_count(self) -> int:
        """Return the number of model components that would be removed."""
        return len(self.removed_model_ids)

    @property
    def changed_mask_count(self) -> int:
        """Return the number of surviving masks that would change."""
        return len(self.changed_mask_ids)

    @property
    def removed_mask_count(self) -> int:
        """Return the number of masks that would be removed."""
        return len(self.removed_mask_ids)

    @classmethod
    def no_change(cls, operation: StructureImpactOperation) -> StructureImpactPreview:
        """Build an inert preview for one operation."""
        return cls(operation=operation, outcome=StructureMutationOutcome.NO_CHANGE)


class StructureImpactModelPort(Protocol):
    """Read-only model facts needed to preview structure impacts."""

    @property
    def components(self) -> list[ModelComponent]:
        """Return current model components in storage order."""
        ...

    @property
    def mask_definitions(self) -> tuple[MaskDefinition, ...]:
        """Return current wavelength masks in storage order."""
        ...


class StructureImpactProjectPort(Protocol):
    """Read-only project facts and canonical multiplet expansion."""

    absorption_regions: dict[str, AbsorptionRegion]
    absorption_lines: dict[str, AbsorptionLine]

    @property
    def model(self) -> StructureImpactModelPort:
        """Return the project's model storage."""
        ...

    def expand_multiplet_line_ids(self, seed_ids: Sequence[str]) -> list[str]:
        """Expand seed identities by the project's canonical multiplet rule."""
        ...


class StructureImpactPreviewUseCase:
    """Resolve structure targets without mutating project or UI state."""

    def preview_move(
        self, project: StructureImpactProjectPort, request: MoveStructureRequest
    ) -> StructureImpactPreview:
        """Preview a line move using canonical multiplet expansion."""
        operation = StructureImpactOperation.MOVE
        if not request.line_ids:
            return StructureImpactPreview.no_change(operation)
        _require_unique_existing_lines(project, request.line_ids, label="Move")
        if (
            request.target_region_id is not None
            and request.target_region_id not in project.absorption_regions
        ):
            msg = f"Move destination region not found: {request.target_region_id}"
            raise ValueError(msg)
        expanded_line_ids = _expanded_line_ids(project, request.line_ids, label="Move")
        if request.target_region_id is not None and all(
            _line_region_id(project.absorption_lines[line_id]) == request.target_region_id
            for line_id in expanded_line_ids
        ):
            return StructureImpactPreview.no_change(operation)
        return _preview_move_expanded(
            project,
            operation=operation,
            expanded_line_ids=expanded_line_ids,
            target_region_id=request.target_region_id,
        )

    def preview_split(
        self, project: StructureImpactProjectPort, request: SplitStructureRequest
    ) -> StructureImpactPreview:
        """Preview a split into one new region."""
        operation = StructureImpactOperation.SPLIT
        if not request.line_ids:
            return StructureImpactPreview.no_change(operation)
        _require_unique_existing_lines(project, request.line_ids, label="Split")
        expanded_line_ids = _expanded_line_ids(project, request.line_ids, label="Split")
        source_region_ids = {
            _line_region_id(project.absorption_lines[line_id]) for line_id in expanded_line_ids
        }
        if len(source_region_ids) != 1:
            msg = "Split lines must belong to exactly one source region."
            raise ValueError(msg)
        source_region_id = next(iter(source_region_ids))
        if source_region_id not in project.absorption_regions:
            msg = f"Split source region not found: {source_region_id}"
            raise ValueError(msg)
        return _preview_move_expanded(
            project,
            operation=operation,
            expanded_line_ids=expanded_line_ids,
            target_region_id=None,
        )

    def preview_merge(
        self, project: StructureImpactProjectPort, request: MergeStructureRequest
    ) -> StructureImpactPreview:
        """Preview merging secondary regions into the first region."""
        operation = StructureImpactOperation.MERGE
        if len(request.region_ids) < 2:
            return StructureImpactPreview.no_change(operation)
        _require_unique_existing_regions(project, request.region_ids, label="Merge")
        if UNASSIGNED_REGION_ID in request.region_ids:
            msg = "The unassigned region cannot participate in a merge."
            raise ValueError(msg)

        primary_region_id = request.region_ids[0]
        secondary_region_ids = request.region_ids[1:]
        changed_line_ids = tuple(
            line_id
            for region_id in secondary_region_ids
            for line_id in project.absorption_regions[region_id].line_ids
        )
        changed_model_ids = _ordered_unique(
            (
                component.id
                for component in project.model.components
                if isinstance(component, AbsorberComponent)
                and component.group_id in secondary_region_ids
            ),
            (
                model_id
                for line_id in changed_line_ids
                for model_id in project.absorption_lines[line_id].model_ids
            ),
        )
        changed_mask_ids = tuple(
            mask.identifier
            for mask in project.model.mask_definitions
            if mask.group_id in secondary_region_ids
        )
        return StructureImpactPreview(
            operation=operation,
            outcome=StructureMutationOutcome.CHANGED,
            changed_region_ids=(primary_region_id,),
            removed_region_ids=secondary_region_ids,
            changed_line_ids=changed_line_ids,
            changed_model_ids=changed_model_ids,
            changed_mask_ids=changed_mask_ids,
        )

    def preview_unlink(
        self, project: StructureImpactProjectPort, request: UnlinkStructureRequest
    ) -> StructureImpactPreview:
        """Preview clearing all links in one canonical linked-line group."""
        operation = StructureImpactOperation.UNLINK
        if not request.line_id:
            msg = "Unlink line identity cannot be empty."
            raise ValueError(msg)
        _require_unique_existing_lines(project, (request.line_id,), label="Unlink")
        selected = project.absorption_lines[request.line_id]
        if not selected.multiplet_ids:
            return StructureImpactPreview.no_change(operation)
        expanded_line_ids = _expanded_line_ids(project, (request.line_id,), label="Unlink")
        if len(expanded_line_ids) < 2:
            msg = "Unlink expansion must contain linked line identities."
            raise ValueError(msg)
        affected_region_ids = _ordered_unique(
            _line_region_id(project.absorption_lines[line_id]) for line_id in expanded_line_ids
        )
        _require_unique_existing_regions(project, affected_region_ids, label="Unlink")
        return StructureImpactPreview(
            operation=operation,
            outcome=StructureMutationOutcome.CHANGED,
            changed_region_ids=affected_region_ids,
            expanded_request_line_ids=expanded_line_ids,
            changed_line_ids=expanded_line_ids,
        )

    def preview_delete(
        self, project: StructureImpactProjectPort, request: DeleteStructureRequest
    ) -> StructureImpactPreview:
        """Preview region/line deletion including multiplet and empty-region cascades."""
        operation = StructureImpactOperation.DELETE
        if not request.region_ids and not request.line_ids:
            return StructureImpactPreview.no_change(operation)
        _require_unique_existing_regions(project, request.region_ids, label="Delete")
        _require_unique_existing_lines(project, request.line_ids, label="Delete")
        if UNASSIGNED_REGION_ID in request.region_ids:
            msg = "The unassigned region cannot be deleted."
            raise ValueError(msg)

        expanded_line_ids = _expanded_line_ids(project, request.line_ids, label="Delete")
        all_removed_line_ids = set(expanded_line_ids)
        for region_id in request.region_ids:
            all_removed_line_ids.update(project.absorption_regions[region_id].line_ids)

        removed_line_ids = tuple(
            line_id for line_id in project.absorption_lines if line_id in all_removed_line_ids
        )
        removed_region_ids_set = set(request.region_ids)
        for line_id in expanded_line_ids:
            source_region_id = _line_region_id(project.absorption_lines[line_id])
            if source_region_id == UNASSIGNED_REGION_ID:
                continue
            source_region = project.absorption_regions.get(source_region_id)
            if source_region is not None and not (
                set(source_region.line_ids) - all_removed_line_ids
            ):
                removed_region_ids_set.add(source_region_id)
        removed_region_ids = tuple(
            region_id
            for region_id in project.absorption_regions
            if region_id in removed_region_ids_set
        )
        changed_region_ids = _changed_surviving_regions_for_removed_lines(
            project, all_removed_line_ids, removed_region_ids_set
        )
        changed_line_ids = _surviving_multiplet_companions(project, all_removed_line_ids)
        removed_model_ids = _ordered_unique(
            model_id
            for line_id in removed_line_ids
            for model_id in project.absorption_lines[line_id].model_ids
        )
        if removed_model_ids:
            changed_region_ids = _globally_affected_surviving_regions_after_delete(
                project, all_removed_line_ids, removed_region_ids_set
            )
        changed_model_ids = _ordered_unique(
            component.id
            for component in project.model.components
            if isinstance(component, AbsorberComponent)
            and component.group_id in removed_region_ids_set
            and component.id not in removed_model_ids
        )
        removed_mask_ids = tuple(
            mask.identifier
            for mask in project.model.mask_definitions
            if mask.group_id in removed_region_ids_set
        )
        return StructureImpactPreview(
            operation=operation,
            outcome=StructureMutationOutcome.CHANGED,
            changed_region_ids=changed_region_ids,
            removed_region_ids=removed_region_ids,
            expanded_request_line_ids=expanded_line_ids,
            changed_line_ids=changed_line_ids,
            removed_line_ids=removed_line_ids,
            changed_model_ids=changed_model_ids,
            removed_model_ids=removed_model_ids,
            removed_mask_ids=removed_mask_ids,
        )


def _preview_move_expanded(
    project: StructureImpactProjectPort,
    *,
    operation: StructureImpactOperation,
    expanded_line_ids: tuple[str, ...],
    target_region_id: str | None,
) -> StructureImpactPreview:
    """Build a move/split preview after shared target expansion."""
    moved_line_id_set = set(expanded_line_ids)
    source_region_ids = _ordered_unique(
        _line_region_id(project.absorption_lines[line_id]) for line_id in expanded_line_ids
    )
    removed_region_ids = tuple(
        region_id
        for region_id in source_region_ids
        if region_id not in {UNASSIGNED_REGION_ID, target_region_id}
        and not (set(project.absorption_regions[region_id].line_ids) - moved_line_id_set)
    )
    removed_region_id_set = set(removed_region_ids)
    changed_region_ids = _ordered_unique(
        (
            region_id
            for region_id in source_region_ids
            if region_id not in removed_region_id_set and region_id != target_region_id
        ),
        (() if target_region_id is None else (target_region_id,)),
    )
    changed_model_ids = _ordered_unique(
        (
            model_id
            for line_id in expanded_line_ids
            for model_id in project.absorption_lines[line_id].model_ids
        ),
        (
            component.id
            for component in project.model.components
            if isinstance(component, AbsorberComponent)
            and component.group_id in removed_region_id_set
        ),
    )
    removed_mask_ids = tuple(
        mask.identifier
        for mask in project.model.mask_definitions
        if mask.group_id in removed_region_id_set
    )
    return StructureImpactPreview(
        operation=operation,
        outcome=StructureMutationOutcome.CHANGED,
        changed_region_ids=changed_region_ids,
        removed_region_ids=removed_region_ids,
        created_region_count=1 if target_region_id is None else 0,
        expanded_request_line_ids=expanded_line_ids,
        changed_line_ids=expanded_line_ids,
        changed_model_ids=changed_model_ids,
        removed_mask_ids=removed_mask_ids,
    )


def _require_unique_existing_lines(
    project: StructureImpactProjectPort, line_ids: tuple[str, ...], *, label: str
) -> None:
    """Require unique, non-empty, existing line identities."""
    _require_unique_identities(line_ids, label=f"{label} line")
    missing = tuple(line_id for line_id in line_ids if line_id not in project.absorption_lines)
    if missing:
        msg = f"{label} request references missing lines: {', '.join(missing)}"
        raise ValueError(msg)


def _require_unique_existing_regions(
    project: StructureImpactProjectPort, region_ids: tuple[str, ...], *, label: str
) -> None:
    """Require unique, non-empty, existing region identities."""
    _require_unique_identities(region_ids, label=f"{label} region")
    missing = tuple(
        region_id for region_id in region_ids if region_id not in project.absorption_regions
    )
    if missing:
        msg = f"{label} request references missing regions: {', '.join(missing)}"
        raise ValueError(msg)


def _require_unique_identities(identities: tuple[str, ...], *, label: str) -> None:
    """Reject empty or duplicate requested identities."""
    if any(not identity for identity in identities):
        msg = f"{label} identities cannot be empty."
        raise ValueError(msg)
    if len(set(identities)) != len(identities):
        msg = f"{label} request contains duplicate identities."
        raise ValueError(msg)


def _expanded_line_ids(
    project: StructureImpactProjectPort, line_ids: tuple[str, ...], *, label: str
) -> tuple[str, ...]:
    """Return exact canonical multiplet expansion with invariant validation."""
    if not line_ids:
        return ()
    expanded = tuple(project.expand_multiplet_line_ids(line_ids))
    if len(set(expanded)) != len(expanded):
        msg = f"Expanded {label.lower()} lines contain duplicate identities."
        raise ValueError(msg)
    missing = tuple(line_id for line_id in expanded if line_id not in project.absorption_lines)
    if missing:
        msg = f"Expanded {label.lower()} lines are missing: {', '.join(missing)}"
        raise ValueError(msg)
    return expanded


def _line_region_id(line: AbsorptionLine) -> str:
    """Return the line's explicit region or the unassigned region identity."""
    return line.region_id or UNASSIGNED_REGION_ID


def _changed_surviving_regions_for_removed_lines(
    project: StructureImpactProjectPort, removed_line_ids: set[str], removed_region_ids: set[str]
) -> tuple[str, ...]:
    """Return surviving regions whose line membership would shrink."""
    return tuple(
        region_id
        for region_id, region in project.absorption_regions.items()
        if region_id not in removed_region_ids and bool(set(region.line_ids) & removed_line_ids)
    )


def _surviving_multiplet_companions(
    project: StructureImpactProjectPort, removed_line_ids: set[str]
) -> tuple[str, ...]:
    """Return surviving lines whose multiplet references would be cleared."""
    changed: set[str] = set()
    for line_id in removed_line_ids:
        line = project.absorption_lines[line_id]
        changed.update(
            related_id
            for related_id in line.multiplet_ids
            if related_id in project.absorption_lines and related_id not in removed_line_ids
        )
    return tuple(line_id for line_id in project.absorption_lines if line_id in changed)


def _globally_affected_surviving_regions_after_delete(
    project: StructureImpactProjectPort, removed_line_ids: set[str], removed_region_ids: set[str]
) -> tuple[str, ...]:
    """Resolve the global invalidation scope caused by model component deletion."""
    affected: list[str] = []
    for region_id, region in project.absorption_regions.items():
        if region_id in removed_region_ids:
            continue
        surviving_line_ids = tuple(
            line_id for line_id in region.line_ids if line_id not in removed_line_ids
        )
        if surviving_line_ids and all(
            (line := project.absorption_lines.get(line_id)) is not None
            and _line_region_id(line) == region_id
            for line_id in surviving_line_ids
        ):
            affected.append(region_id)
    return tuple(affected)


def _ordered_unique(*identity_groups: Iterable[str]) -> tuple[str, ...]:
    """Combine identity iterables without duplicates, preserving encounter order."""
    return tuple(dict.fromkeys(identity for group in identity_groups for identity in group))


__all__ = [
    "DeleteStructureRequest",
    "MergeStructureRequest",
    "MoveStructureRequest",
    "SplitStructureRequest",
    "StructureImpactOperation",
    "StructureImpactPreview",
    "StructureImpactPreviewUseCase",
    "StructureImpactProjectPort",
    "UnlinkStructureRequest",
]
