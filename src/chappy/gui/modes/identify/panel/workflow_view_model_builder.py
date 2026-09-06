"""Build identify workflow view models from core state."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.application.identify import UnionFind
from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from chappy.core.absorption_display import (
    format_region_display,
    group_lines_by_multiplet,
    sort_lines_for_display,
)
from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.gui.modes.identify.panel import panel_models

if TYPE_CHECKING:
    from collections.abc import Sequence

    from chappy.core.identify_state import RegionPreview, TemporaryLine
    from chappy.core.velocity_ranges import MultipletGroupingVelocityTolerance


@dataclass(frozen=True, slots=True)
class IdentifyWorkflowMethodLabels:
    """Translated labels for temporary-line creation methods."""

    candidate_table: str
    manual: str
    velocity_plot: str

    def label_for(self, creation_method: str) -> str:
        """Return the display label for a creation method."""
        labels = {
            "candidate_table": self.candidate_table,
            "manual": self.manual,
            "velocity_plot": self.velocity_plot,
        }
        return labels.get(creation_method, creation_method.replace("_", " ").title())


@dataclass(frozen=True, slots=True)
class IdentifyWorkflowBuilderInput:
    """Input snapshots needed to build identify workflow rows."""

    temporary_lines: Sequence[TemporaryLine]
    region_previews: Sequence[RegionPreview]
    absorption_lines: Sequence[AbsorptionLine]
    absorption_regions: Sequence[AbsorptionRegion]
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance
    atomic_data_available: bool
    method_labels: IdentifyWorkflowMethodLabels


@dataclass(frozen=True, slots=True)
class IdentifyWorkflowViewModel:
    """Panel rows and lookup data for identify workflow display."""

    temporary_line_rows: list[panel_models.TemporaryLineRow]
    region_preview_rows: list[panel_models.RegionPreviewRow]
    confirmed_region_rows: list[panel_models.ConfirmedRegionRow]
    primary_to_members: dict[str, tuple[str, ...]]


class IdentifyWorkflowViewModelBuilder:
    """Build panel row models for the identify workflow tab."""

    def build(self, input_data: IdentifyWorkflowBuilderInput) -> IdentifyWorkflowViewModel:
        """Build workflow rows and primary-to-member lookup data."""
        temporary_line_rows, primary_to_members = self._build_temporary_line_rows(input_data)
        line_map = {line.line_id: line for line in input_data.absorption_lines}
        region_preview_rows = self._build_preview_rows(
            previews=input_data.region_previews,
            temporary_line_rows=temporary_line_rows,
            absorption_regions=input_data.absorption_regions,
            line_map=line_map,
        )
        confirmed_region_rows = self._build_confirmed_region_rows(
            absorption_regions=input_data.absorption_regions, line_map=line_map
        )
        return IdentifyWorkflowViewModel(
            temporary_line_rows=temporary_line_rows,
            region_preview_rows=region_preview_rows,
            confirmed_region_rows=confirmed_region_rows,
            primary_to_members=primary_to_members,
        )

    def _build_temporary_line_rows(
        self, input_data: IdentifyWorkflowBuilderInput
    ) -> tuple[list[panel_models.TemporaryLineRow], dict[str, tuple[str, ...]]]:
        groups = group_temporary_lines_by_multiplet(
            input_data.temporary_lines,
            atomic_data_available=input_data.atomic_data_available,
            multiplet_grouping_tolerance=input_data.multiplet_grouping_tolerance,
        )
        sorted_groups = sorted(groups, key=_temporary_line_group_sort_key)

        primary_to_members: dict[str, tuple[str, ...]] = {}
        rows: list[panel_models.TemporaryLineRow] = []
        for display_index, group in enumerate(sorted_groups, start=1):
            primary_line = group[0]
            member_ids = tuple(line.temporary_line_id for line in group)
            primary_to_members[primary_line.temporary_line_id] = member_ids

            transition_labels: list[str] = []
            species_label = ""
            multiplet_label_candidate = ""
            for line in group:
                if not multiplet_label_candidate:
                    multiplet_label_candidate = line.multiplet_label
                transition_labels.append(line.transition_name)
                if not species_label:
                    species_label = line.species

            if len(group) > 1:
                display_species = multiplet_label_candidate
                combined_transition = multiplet_label_candidate
            else:
                display_species = transition_labels[0]
                combined_transition = transition_labels[0]

            rows.append(
                panel_models.TemporaryLineRow(
                    temporary_line_ids=member_ids,
                    species=display_species,
                    lambda_start=min(line.lambda_min for line in group),
                    lambda_end=max(line.lambda_max for line in group),
                    creation_method=input_data.method_labels.label_for(
                        primary_line.creation_method
                    ),
                    transition_name=combined_transition,
                    redshift=group[0].center_z,
                    display_id=display_index,
                    multiplet_label=multiplet_label_candidate,
                )
            )

        return rows, primary_to_members

    def _build_preview_rows(
        self,
        *,
        previews: Sequence[RegionPreview],
        temporary_line_rows: Sequence[panel_models.TemporaryLineRow],
        absorption_regions: Sequence[AbsorptionRegion],
        line_map: dict[str, AbsorptionLine],
    ) -> list[panel_models.RegionPreviewRow]:
        temporary_line_id_to_row: dict[str, panel_models.TemporaryLineRow] = {}
        for row in temporary_line_rows:
            for temporary_line_id in row.temporary_line_ids:
                temporary_line_id_to_row[temporary_line_id] = row

        preview_rows: list[panel_models.RegionPreviewRow] = []
        for preview in previews:
            is_existing = bool(preview.existing_group_id)
            old_member_count = None
            if is_existing:
                old_member_count = self._existing_region_member_count(
                    preview.existing_group_id,
                    absorption_regions=absorption_regions,
                    line_map=line_map,
                )

            unique_rows: set[int] = set()
            for temporary_line_id in preview.member_temporary_line_ids:
                matched_row = temporary_line_id_to_row.get(temporary_line_id)
                if matched_row is not None:
                    unique_rows.add(id(matched_row))
            new_lines_count = len(unique_rows)

            preview_rows.append(
                panel_models.RegionPreviewRow(
                    group_id=preview.existing_group_id or preview.group_id,
                    label=preview.name,
                    member_count=new_lines_count + (old_member_count or 0),
                    warning=preview.overlap_warning,
                    is_existing_group=is_existing,
                    old_member_count=old_member_count,
                    new_lines_count=new_lines_count,
                    member_temporary_line_ids=list(preview.member_temporary_line_ids),
                )
            )
        return preview_rows

    def _build_confirmed_region_rows(
        self,
        *,
        absorption_regions: Sequence[AbsorptionRegion],
        line_map: dict[str, AbsorptionLine],
    ) -> list[panel_models.ConfirmedRegionRow]:
        confirmed_regions: list[panel_models.ConfirmedRegionRow] = []
        for region in absorption_regions:
            if region.region_id == UNASSIGNED_REGION_ID:
                continue

            region_line_objects = [
                line_map[line_id] for line_id in region.line_ids if line_id in line_map
            ]
            sorted_region_lines = sort_lines_for_display(region_line_objects)
            multiplet_groups: list[list[AbsorptionLine]] = group_lines_by_multiplet(
                sorted_region_lines
            )

            region_lines: list[panel_models.ConfirmedLineRow] = []
            for display_index, absorption_group in enumerate(multiplet_groups, start=1):
                region_lines.append(
                    self._confirmed_line_row(absorption_group, display_index=display_index)
                )

            if region_lines:
                display_info = format_region_display(sorted_region_lines, region.analysis_range)
                confirmed_regions.append(
                    panel_models.ConfirmedRegionRow(
                        group_id=region.region_id,
                        label=display_info.display_name,
                        lines=region_lines,
                        is_expanded=True,
                    )
                )
        return confirmed_regions

    def _existing_region_member_count(
        self,
        region_id: str | None,
        *,
        absorption_regions: Sequence[AbsorptionRegion],
        line_map: dict[str, AbsorptionLine],
    ) -> int | None:
        if region_id is None:
            return None
        for region in absorption_regions:
            if region.region_id == region_id:
                existing_region_lines = [
                    line_map[line_id] for line_id in region.line_ids if line_id in line_map
                ]
                return len(group_lines_by_multiplet(existing_region_lines))
        return None

    def _confirmed_line_row(
        self, absorption_group: Sequence[AbsorptionLine], *, display_index: int
    ) -> panel_models.ConfirmedLineRow:
        if len(absorption_group) == 1:
            absorption_line = absorption_group[0]
            lambda_start, lambda_end = _require_line_range(absorption_line)
            return panel_models.ConfirmedLineRow(
                line_id=absorption_line.line_id,
                species=absorption_line.species,
                transition_name=absorption_line.transition_name,
                redshift=_require_line_redshift(absorption_line),
                lambda_start=lambda_start,
                lambda_end=lambda_end,
                display_id=display_index,
            )

        primary_line = absorption_group[0]
        all_ranges = [
            line.lambda_range
            for line in absorption_group
            if isinstance(line.lambda_range, tuple) and len(line.lambda_range) == 2
        ]
        if not all_ranges:
            msg = f"Confirmed multiplet group has no wavelength ranges: {primary_line.line_id}"
            raise ValueError(msg)
        lambda_start = min(range_pair[0] for range_pair in all_ranges)
        lambda_end = max(range_pair[1] for range_pair in all_ranges)

        combined_label = primary_line.multiplet_label
        return panel_models.ConfirmedLineRow(
            line_id=primary_line.line_id,
            species=combined_label,
            transition_name=combined_label,
            redshift=_require_line_redshift(primary_line),
            lambda_start=lambda_start,
            lambda_end=lambda_end,
            display_id=display_index,
        )


def group_temporary_lines_by_multiplet(
    lines: Sequence[TemporaryLine],
    *,
    atomic_data_available: bool,
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance,
) -> list[list[TemporaryLine]]:
    """Group temporary lines by multiplet and redshift proximity."""
    lines_list = list(lines)
    if not lines_list:
        return []
    if not atomic_data_available:
        return [[line] for line in lines_list]

    union_find = UnionFind(len(lines_list))
    _union_by_tie_group(
        union_find, lines_list, multiplet_grouping_tolerance=multiplet_grouping_tolerance
    )

    result: list[list[TemporaryLine]] = []
    for indices in union_find.collect_groups().values():
        group = [lines_list[index] for index in indices]
        result.append(
            sorted(
                group,
                key=lambda line: (
                    line.rest_wavelength if line.rest_wavelength is not None else float("inf")
                ),
            )
        )
    return result


def _temporary_line_group_sort_key(group: list[TemporaryLine]) -> tuple[float, float, str]:
    primary = group[0]
    center_z = primary.center_z if primary.center_z is not None else float("inf")
    rest_wavelength = (
        primary.rest_wavelength if primary.rest_wavelength is not None else float("inf")
    )
    return (center_z, rest_wavelength, primary.temporary_line_id)


def _derive_redshift_from_line(line: TemporaryLine) -> float | None:
    if line.center_z is not None and math.isfinite(line.center_z):
        return line.center_z
    if line.rest_wavelength > 0:
        center = line.center_wavelength
        if math.isfinite(center) and center > 0:
            return (center / line.rest_wavelength) - 1.0
    return None


def _should_union_by_redshift(
    line_a: TemporaryLine,
    line_b: TemporaryLine,
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance,
) -> bool:
    z_a = _derive_redshift_from_line(line_a)
    z_b = _derive_redshift_from_line(line_b)
    if z_a is None or z_b is None:
        return False

    delta_velocity = abs(z_a - z_b) * LIGHT_SPEED_KMS
    return delta_velocity <= multiplet_grouping_tolerance.kms


def _union_by_tie_group(
    union_find: UnionFind,
    lines_list: Sequence[TemporaryLine],
    multiplet_grouping_tolerance: MultipletGroupingVelocityTolerance,
) -> None:
    tie_group_map: dict[str, list[int]] = defaultdict(list)
    for index, line in enumerate(lines_list):
        if line.tie_group_key:
            tie_group_map[line.tie_group_key].append(index)

    for indices in tie_group_map.values():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                idx_a, idx_b = indices[i], indices[j]
                if _should_union_by_redshift(
                    lines_list[idx_a], lines_list[idx_b], multiplet_grouping_tolerance
                ):
                    union_find.union(idx_a, idx_b)


def _require_line_range(line: AbsorptionLine) -> tuple[float, float]:
    line_lambda_range = line.lambda_range
    if isinstance(line_lambda_range, tuple | list) and len(line_lambda_range) == 2:
        return line_lambda_range
    msg = f"Confirmed absorption line has no wavelength range: {line.line_id}"
    raise ValueError(msg)


def _require_line_redshift(line: AbsorptionLine) -> float:
    redshift = line.center_z
    if redshift is None or not math.isfinite(redshift):
        msg = f"Confirmed absorption line has invalid redshift: {line.line_id}"
        raise ValueError(msg)
    return redshift
