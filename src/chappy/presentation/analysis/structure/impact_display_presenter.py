"""Human-readable structure-impact identities for confirmation dialogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.core.absorption_display import (
    format_region_display,
    group_lines_by_multiplet,
    iter_component_display_rows,
    sort_lines_for_display,
)
from chappy.presentation.analysis.structure.tree_presenter import StructureTreePresenter

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.components.base import ModelComponent
    from chappy.core.masking import MaskDefinition


class ImpactModelFacts(Protocol):
    """Read-only model facts needed to display a structure-impact preview."""

    @property
    def components(self) -> Sequence[ModelComponent]:
        """Return current model components in storage order."""
        ...

    @property
    def mask_definitions(self) -> Sequence[MaskDefinition]:
        """Return current wavelength masks in storage order."""
        ...


class ImpactProjectFacts(Protocol):
    """Read-only project facts needed to display a structure-impact preview."""

    @property
    def absorption_regions(self) -> Mapping[str, AbsorptionRegion]:
        """Return current absorption regions keyed by identity."""
        ...

    @property
    def absorption_lines(self) -> Mapping[str, AbsorptionLine]:
        """Return current absorption lines keyed by identity."""
        ...

    @property
    def model(self) -> ImpactModelFacts:
        """Return the project's model storage."""
        ...


@dataclass(frozen=True, slots=True)
class StructureImpactCategoryDisplay:
    """Human-readable identities changed or removed within one impact category."""

    changed: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureImpactDisplay:
    """Human-readable structure-impact identities for one confirmation dialog."""

    regions: StructureImpactCategoryDisplay
    lines: StructureImpactCategoryDisplay
    components: StructureImpactCategoryDisplay
    masks: StructureImpactCategoryDisplay


def build_structure_impact_display(  # noqa: PLR0913 - one keyword per preview identity category
    *,
    changed_region_ids: tuple[str, ...],
    removed_region_ids: tuple[str, ...],
    changed_line_ids: tuple[str, ...],
    removed_line_ids: tuple[str, ...],
    changed_model_ids: tuple[str, ...],
    removed_model_ids: tuple[str, ...],
    changed_mask_ids: tuple[str, ...],
    removed_mask_ids: tuple[str, ...],
    project: ImpactProjectFacts,
) -> StructureImpactDisplay:
    """Convert a structure-impact preview's raw identities into display labels.

    Args:
        changed_region_ids: Region identities from the preview's changed set.
        removed_region_ids: Region identities from the preview's removed set.
        changed_line_ids: Line identities from the preview's changed set.
        removed_line_ids: Line identities from the preview's removed set.
        changed_model_ids: Component identities from the preview's changed set.
        removed_model_ids: Component identities from the preview's removed set.
        changed_mask_ids: Mask identities from the preview's changed set.
        removed_mask_ids: Mask identities from the preview's removed set.
        project: Read-only project facts used to resolve identities to labels.

    Returns:
        Display labels grouped the same way as the source preview's categories.
    """
    return StructureImpactDisplay(
        regions=StructureImpactCategoryDisplay(
            changed=_region_labels(changed_region_ids, project),
            removed=_region_labels(removed_region_ids, project),
        ),
        lines=StructureImpactCategoryDisplay(
            changed=_line_labels(changed_line_ids, project),
            removed=_line_labels(removed_line_ids, project),
        ),
        components=StructureImpactCategoryDisplay(
            changed=_component_labels(changed_model_ids, project),
            removed=_component_labels(removed_model_ids, project),
        ),
        masks=StructureImpactCategoryDisplay(
            changed=_mask_labels(changed_mask_ids, project),
            removed=_mask_labels(removed_mask_ids, project),
        ),
    )


def _region_labels(region_ids: tuple[str, ...], project: ImpactProjectFacts) -> tuple[str, ...]:
    """Return region display names for the given region identities."""
    labels: list[str] = []
    for region_id in region_ids:
        region = project.absorption_regions.get(region_id)
        if region is None:
            continue
        lines = [
            project.absorption_lines[line_id]
            for line_id in region.line_ids
            if line_id in project.absorption_lines
        ]
        if not lines:
            continue
        display_info = format_region_display(lines, region.analysis_range)
        labels.append(display_info.display_name)
    return tuple(labels)


def _line_labels(line_ids: tuple[str, ...], project: ImpactProjectFacts) -> tuple[str, ...]:
    """Return species/wavelength/redshift display labels for the given lines."""
    labels: list[str] = []
    for line_id in line_ids:
        line = project.absorption_lines.get(line_id)
        if line is None:
            continue
        labels.append(_format_line(line))
    return tuple(labels)


def _format_line(line: AbsorptionLine) -> str:
    """Format one absorption line as species, rest wavelength, and redshift."""
    redshift = StructureTreePresenter.format_redshift(line.center_z) or "—"
    return f"{line.species} {line.rest_wavelength:.2f} (z={redshift})"


def _component_labels(model_ids: tuple[str, ...], project: ImpactProjectFacts) -> tuple[str, ...]:
    """Return component labels grouped under their owning line's display name."""
    if not model_ids:
        return ()
    model_id_set = set(model_ids)
    resolve = {component.id: component for component in project.model.components}.get
    relevant_lines = [
        line
        for line in project.absorption_lines.values()
        if any(model_id in model_id_set for model_id in line.model_ids)
    ]
    sorted_lines = sort_lines_for_display(relevant_lines)
    labels: list[str] = []
    for group in group_lines_by_multiplet(sorted_lines):
        for line, component, ordinal in iter_component_display_rows(group, resolve):
            if component.id not in model_id_set:
                continue
            labels.append(f"{_format_line(line)} · {component.name} c{ordinal}")
    return tuple(labels)


def _mask_labels(mask_ids: tuple[str, ...], project: ImpactProjectFacts) -> tuple[str, ...]:
    """Return mask labels, preferring the user label over the wavelength range."""
    masks_by_id = {mask.identifier: mask for mask in project.model.mask_definitions}
    labels: list[str] = []
    for mask_id in mask_ids:
        mask = masks_by_id.get(mask_id)
        if mask is None:
            continue
        labels.append(mask.label or f"{mask.wavelength_min:.1f}–{mask.wavelength_max:.1f}")
    return tuple(labels)


__all__ = [
    "ImpactModelFacts",
    "ImpactProjectFacts",
    "StructureImpactCategoryDisplay",
    "StructureImpactDisplay",
    "build_structure_impact_display",
]
