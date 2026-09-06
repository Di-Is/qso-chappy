"""Qt-independent structure tree presentation model."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from chappy.core.absorption_display import (
    format_region_display,
    group_lines_by_multiplet,
    sort_lines_for_display,
)
from chappy.core.constants import LIGHT_SPEED_KMS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
    from chappy.core.components.absorber import AbsorberComponent

_RANGE_SINGLE_THRESHOLD = 0.05
_WINDOW_ROUND_THRESHOLD = 0.25


class AbsorberComponentResolver(Protocol):
    """Resolve absorber components by persistent component ID."""

    def find_absorber_component(self, component_id: str) -> AbsorberComponent | None:
        """Return an absorber component by ID.

        Args:
            component_id: Persistent absorber component ID.

        Returns:
            Absorber component when available.
        """
        ...


@dataclass(slots=True)
class StructureComponentNode:
    """Render metadata for an absorber component row."""

    component: AbsorberComponent
    observed_lambda: float | None
    redshift: float | None
    window_kms: float | None
    is_primary: bool


@dataclass(slots=True)
class StructureLinkedLineNode:
    """Render metadata for an absorption line header."""

    line_ids: tuple[str, ...]
    header_label: str
    lambda_range: tuple[float, float] | None
    needs_optimization: bool
    components: list[StructureComponentNode] = field(default_factory=list)
    tooltip: str | None = None
    multiplet_ids: tuple[str, ...] = field(default_factory=tuple)
    display_id: int | None = None


@dataclass(slots=True)
class StructureRegionEntry:
    """Grouped absorbers summary used for display and focus."""

    identifier: str
    label: str
    wavelength_min: float | None
    wavelength_max: float | None
    components: list[AbsorberComponent]
    color: str | None = None
    linked_line_nodes: list[StructureLinkedLineNode] = field(default_factory=list)
    linked_line_count: int = 0
    needs_optimization: bool = False
    shows_badges: bool = False


class StructureTreePresenter:
    """Build structure tree view models from core absorption models."""

    def __init__(
        self, *, range_tooltip_template: str, linked_line_header_template: str, unknown_label: str
    ) -> None:
        """Initialize the presenter with translated display templates.

        Args:
            range_tooltip_template: Template for observed range tooltips.
            linked_line_header_template: Template for linked-line headers.
            unknown_label: Display text for an unknown linked line.
        """
        self._range_tooltip_template = range_tooltip_template
        self._linked_line_header_template = linked_line_header_template
        self._unknown_label = unknown_label

    def build_absorption_region_entry(
        self,
        *,
        region_id: str,
        region: AbsorptionRegion,
        lines: Mapping[str, AbsorptionLine],
        component_resolver: AbsorberComponentResolver | None,
    ) -> StructureRegionEntry | None:
        """Build a region entry for absorption-line aware structure display.

        Args:
            region_id: Persistent region ID.
            region: Region model.
            lines: Absorption lines indexed by line ID.
            component_resolver: Optional absorber component resolver.

        Returns:
            Structure group entry, or None when the region has no displayable lines.
        """
        line_nodes: list[StructureLinkedLineNode] = []
        collected_components: list[AbsorberComponent] = []
        wavelength_min: float | None = None
        wavelength_max: float | None = None
        needs_optimization = False

        line_list = [lines[line_id] for line_id in region.line_ids if line_id in lines]
        sorted_lines = sort_lines_for_display(line_list)
        if not sorted_lines:
            return None

        multiplet_groups = group_lines_by_multiplet(sorted_lines)
        for display_index, group in enumerate(multiplet_groups, start=1):
            line_node = self.build_multiplet_node(
                group, display_id=display_index, component_resolver=component_resolver
            )
            line_nodes.append(line_node)
            needs_optimization = needs_optimization or line_node.needs_optimization
            wavelength_min, wavelength_max = self.combine_ranges(
                wavelength_min, wavelength_max, line_node.lambda_range
            )
            collected_components.extend(node.component for node in line_node.components)

        analysis_range = self.safe_analysis_range(region)
        wavelength_min, wavelength_max = self.combine_ranges(
            wavelength_min, wavelength_max, analysis_range
        )
        display_info = format_region_display(sorted_lines, analysis_range)

        return StructureRegionEntry(
            identifier=region_id,
            label=display_info.display_name,
            wavelength_min=wavelength_min,
            wavelength_max=wavelength_max,
            components=collected_components,
            color=region.display_color,
            linked_line_nodes=line_nodes,
            linked_line_count=len(line_nodes),
            needs_optimization=needs_optimization,
        )

    def build_line_node(
        self,
        line: AbsorptionLine,
        *,
        display_id: int | None = None,
        component_resolver: AbsorberComponentResolver | None = None,
    ) -> StructureLinkedLineNode:
        """Build a linked-line node for a single absorption line.

        Args:
            line: Absorption line to display.
            display_id: Optional display ID.
            component_resolver: Optional absorber component resolver.

        Returns:
            Linked-line node for the line.
        """
        component_nodes = self._component_nodes_for_line(
            line, component_resolver=component_resolver
        )
        lambda_range = self.calculate_lambda_range(line)
        header_label = self.format_line_header(line, component_nodes)
        tooltip = self.format_observed_range_tooltip(lambda_range)

        return StructureLinkedLineNode(
            line_ids=(line.line_id,),
            header_label=header_label,
            lambda_range=lambda_range,
            needs_optimization=line.needs_optimization,
            components=component_nodes,
            tooltip=tooltip,
            multiplet_ids=tuple(line.multiplet_ids),
            display_id=display_id,
        )

    def build_multiplet_node(
        self,
        lines: Sequence[AbsorptionLine],
        *,
        display_id: int | None = None,
        component_resolver: AbsorberComponentResolver | None = None,
    ) -> StructureLinkedLineNode:
        """Build a linked-line node from a single-line or multiplet group.

        Args:
            lines: Absorption lines in one multiplet group.
            display_id: Optional display ID.
            component_resolver: Optional absorber component resolver.

        Returns:
            Linked-line node for the group.
        """
        if len(lines) == 1:
            return self.build_line_node(
                lines[0], display_id=display_id, component_resolver=component_resolver
            )

        component_nodes = self._unique_component_nodes_for_lines(
            lines, component_resolver=component_resolver
        )
        lambda_range = self._combined_line_range(lines)
        line_ids = tuple(line.line_id for line in lines)
        multiplet_ids = tuple(
            sorted({related_id for line in lines for related_id in line.multiplet_ids})
        )

        return StructureLinkedLineNode(
            line_ids=line_ids,
            header_label=self.format_multiplet_header(lines),
            lambda_range=lambda_range,
            needs_optimization=any(line.needs_optimization for line in lines),
            components=component_nodes,
            tooltip=self.format_observed_range_tooltip(lambda_range),
            multiplet_ids=multiplet_ids,
            display_id=display_id,
        )

    def format_multiplet_header(self, lines: Sequence[AbsorptionLine]) -> str:
        """Format a header for a multiplet row.

        Args:
            lines: Lines in a multiplet group.

        Returns:
            Display header.
        """
        if not lines:
            return self._unknown_label
        species = lines[0].multiplet_label
        return self._format_linked_line_header(
            species=species, redshift=lines[0].center_z, window_kms=lines[0].window_kms
        )

    def format_line_header(
        self, line: AbsorptionLine, components: Sequence[StructureComponentNode]
    ) -> str:
        """Format a header for a single absorption line.

        Args:
            line: Absorption line to display.
            components: Resolved component nodes for the line.

        Returns:
            Display header.
        """
        display_name = ""
        for node in components:
            atomic_line = node.component.atomic_line
            if atomic_line is not None:
                display_name = atomic_line.multiplet_label or atomic_line.transition_name
                if display_name:
                    break
        if not display_name:
            display_name = line.transition_name
        return self._format_linked_line_header(
            species=display_name, redshift=line.center_z, window_kms=line.window_kms
        )

    def format_observed_range_tooltip(
        self, lambda_range: tuple[float, float] | None
    ) -> str | None:
        """Return observed range tooltip text.

        Args:
            lambda_range: Observed wavelength range.

        Returns:
            Tooltip text, or None without a valid range.
        """
        if lambda_range is None:
            return None
        return self._range_tooltip_template.format(
            minimum=lambda_range[0], maximum=lambda_range[1]
        )

    def format_range_text(self, lambda_range: tuple[float, float] | None) -> str | None:
        """Format a compact wavelength range.

        Args:
            lambda_range: Wavelength range.

        Returns:
            Compact range text, or None for invalid input.
        """
        if not lambda_range:
            return None
        low, high = lambda_range
        if not (math.isfinite(low) and math.isfinite(high)):
            return None
        if abs(high - low) < _RANGE_SINGLE_THRESHOLD:
            return self.format_value((low + high) / 2.0, decimals=2)
        low_text = self.format_value(low, decimals=1)
        high_text = self.format_value(high, decimals=1)
        return f"{low_text}-{high_text}"

    @staticmethod
    def safe_analysis_range(region: AbsorptionRegion) -> tuple[float, float] | None:
        """Return a normalized finite analysis range for a region."""
        analysis_range = region.analysis_range
        if not analysis_range:
            return None
        low, high = analysis_range
        if not (math.isfinite(low) and math.isfinite(high)):
            return None
        low, high = sorted((low, high))
        return (low, high)

    @staticmethod
    def combine_ranges(
        current_min: float | None, current_max: float | None, candidate: tuple[float, float] | None
    ) -> tuple[float | None, float | None]:
        """Combine a current range with a candidate range."""
        if candidate is None:
            return current_min, current_max
        low, high = candidate
        if current_min is None or low < current_min:
            current_min = low
        if current_max is None or high > current_max:
            current_max = high
        return current_min, current_max

    @staticmethod
    def calculate_lambda_range(line: AbsorptionLine) -> tuple[float, float] | None:
        """Return a finite wavelength range for an absorption line."""
        lambda_range = line.lambda_range
        if lambda_range:
            low, high = sorted(lambda_range)
            if math.isfinite(low) and math.isfinite(high):
                return (low, high)

        observed = line.observed_wavelength()
        window = line.window_kms
        if not (math.isfinite(observed) and math.isfinite(window) and window > 0):
            return None
        delta = abs(observed) * (abs(window) / LIGHT_SPEED_KMS)
        if not math.isfinite(delta) or delta <= 0:
            return None
        low = observed - delta
        high = observed + delta
        return (min(low, high), max(low, high))

    @staticmethod
    def component_redshift(component: AbsorberComponent, fallback: float | None) -> float | None:
        """Return component redshift for a model-backed component.

        Args:
            component: Absorber component whose redshift parameter is required.
            fallback: Deprecated fallback value. This must be None; line redshift
                fallback is not valid for model-backed component rows.

        Returns:
            Component redshift.

        Raises:
            RuntimeError: If a caller tries to provide a fallback redshift.
            KeyError: If the component has no redshift parameter.
            ValueError: If the redshift value is not finite numeric data.
        """
        if fallback is not None:
            msg = "Structure component rows must use component redshift, not line fallback."
            raise RuntimeError(msg)
        param = component.parameters.get("redshift")
        if param is None:
            msg = f"Absorber component '{component.id}' has no redshift parameter."
            raise KeyError(msg)
        try:
            redshift = float(param.value)
        except (TypeError, ValueError):
            msg = f"Absorber component '{component.id}' has invalid redshift."
            raise ValueError(msg) from None
        if not math.isfinite(redshift):
            msg = f"Absorber component '{component.id}' redshift must be finite."
            raise ValueError(msg)
        return redshift

    @staticmethod
    def format_value(value: float | None, *, decimals: int = 2, fallback: str = "—") -> str:
        """Format a numeric value with trimmed trailing zeros."""
        if value is None or not math.isfinite(value):
            return fallback
        formatted = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
        return formatted or "0"

    @staticmethod
    def format_redshift(redshift: float | None) -> str | None:
        """Format a redshift value."""
        if redshift is None or not math.isfinite(redshift):
            return None
        return StructureTreePresenter.format_value(redshift, decimals=5)

    @staticmethod
    def format_window(window_kms: float | None) -> str | None:
        """Format a velocity window value."""
        if window_kms is None or not math.isfinite(window_kms) or window_kms <= 0:
            return None
        rounded = round(window_kms)
        if abs(window_kms - rounded) < _WINDOW_ROUND_THRESHOLD:
            return f"{rounded}"
        return StructureTreePresenter.format_value(window_kms, decimals=1)

    @staticmethod
    def observed_wavelength(absorber: AbsorberComponent, redshift: float | None) -> float | None:
        """Return observed wavelength for an absorber component."""
        if redshift is None:
            return None
        return float(absorber.wavelength * (1.0 + redshift))

    def _format_linked_line_header(
        self, *, species: str, redshift: float | None, window_kms: float | None
    ) -> str:
        """Format a linked-line header from values."""
        result = self._linked_line_header_template.format(
            species=species,
            wavelengths="",
            redshift=self.format_redshift(redshift) or "—",
            window=self.format_window(window_kms) or "—",
        )
        return result.replace("  ", " ")

    def _component_nodes_for_line(
        self, line: AbsorptionLine, *, component_resolver: AbsorberComponentResolver | None
    ) -> list[StructureComponentNode]:
        """Resolve component nodes for one line."""
        if not line.model_ids:
            return []
        component_resolver = self._require_component_resolver(component_resolver)

        candidates: list[StructureComponentNode] = []
        for component_id in line.model_ids:
            component = component_resolver.find_absorber_component(component_id)
            if component is None:
                continue
            redshift = self.component_redshift(component, None)
            observed = self.observed_wavelength(component, redshift)
            candidates.append(
                StructureComponentNode(
                    component=component,
                    observed_lambda=observed,
                    redshift=redshift,
                    window_kms=line.window_kms,
                    is_primary=False,
                )
            )
        return self._mark_primary(candidates)

    def _unique_component_nodes_for_lines(
        self,
        lines: Sequence[AbsorptionLine],
        *,
        component_resolver: AbsorberComponentResolver | None,
    ) -> list[StructureComponentNode]:
        """Resolve unique component nodes for a multiplet group."""
        if not any(line.model_ids for line in lines):
            return []
        component_resolver = self._require_component_resolver(component_resolver)

        component_nodes: list[StructureComponentNode] = []
        seen_model_ids: set[str] = set()
        for line in lines:
            for component_id in line.model_ids:
                if component_id in seen_model_ids:
                    continue
                seen_model_ids.add(component_id)
                component = component_resolver.find_absorber_component(component_id)
                if component is None:
                    continue
                redshift = self.component_redshift(component, None)
                observed = self.observed_wavelength(component, redshift)
                component_nodes.append(
                    StructureComponentNode(
                        component=component,
                        observed_lambda=observed,
                        redshift=redshift,
                        window_kms=line.window_kms,
                        is_primary=False,
                    )
                )
        return self._mark_primary(component_nodes)

    @staticmethod
    def _require_component_resolver(
        component_resolver: AbsorberComponentResolver | None,
    ) -> AbsorberComponentResolver:
        """Return the component resolver required for model-backed lines."""
        if component_resolver is None:
            msg = "StructureTreePresenter requires a component resolver for model-backed lines."
            raise RuntimeError(msg)
        return component_resolver

    def _combined_line_range(self, lines: Sequence[AbsorptionLine]) -> tuple[float, float] | None:
        """Return the combined range for a sequence of lines."""
        combined_min: float | None = None
        combined_max: float | None = None
        for line in lines:
            combined_min, combined_max = self.combine_ranges(
                combined_min, combined_max, self.calculate_lambda_range(line)
            )
        if combined_min is None or combined_max is None:
            return None
        return (combined_min, combined_max)

    @staticmethod
    def _mark_primary(nodes: list[StructureComponentNode]) -> list[StructureComponentNode]:
        """Sort component nodes and mark the first component as primary."""
        nodes.sort(key=lambda node: node.component.wavelength)
        for index, node in enumerate(nodes):
            node.is_primary = index == 0
        return nodes
