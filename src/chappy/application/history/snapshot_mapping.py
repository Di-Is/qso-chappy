"""Snapshot conversion helpers for history command integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict, cast

from chappy.application.history.ports import (
    AbsorberComponentParameterSnapshot,
    AbsorberComponentSnapshot,
    AbsorptionLineSnapshot,
    AbsorptionRegionSnapshot,
    MaskDefinitionSnapshot,
    ModelComponentLinkSnapshot,
    NamedParameterState,
    TieSetSnapshot,
)
from chappy.application.identify import TemporaryLineSnapshot
from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.base import Parameter
from chappy.core.components.tie_set import ParameterTieSet, TieParameterName
from chappy.core.identify_state import TemporaryLine
from chappy.core.masking import MaskDefinition
from chappy.core.velocity_ranges import LineAnalysisHalfWidth

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from chappy.core.identify_state import IdentifySessionState


class ModelLink(TypedDict):
    """Line-component link with position for order preservation."""

    line_id: str
    component_id: str
    index: int


def absorption_region_from_snapshot(snapshot: AbsorptionRegionSnapshot) -> AbsorptionRegion:
    """Create a core absorption region from a typed history snapshot.

    Args:
        snapshot: Typed absorption region snapshot.

    Returns:
        Restored core absorption region.
    """
    line_ids: list[str] = []
    if snapshot.region_id == UNASSIGNED_REGION_ID:
        line_ids = list(snapshot.line_ids)
    return AbsorptionRegion(
        region_id=snapshot.region_id,
        line_ids=line_ids,
        display_color=snapshot.display_color,
        analysis_range=snapshot.analysis_range,
        created_at=snapshot.created_at,
    )


def absorber_component_snapshot(component: AbsorberComponent) -> AbsorberComponentSnapshot:
    """Convert an absorber component to a typed history snapshot.

    Args:
        component: Core absorber component.

    Returns:
        Typed absorber component snapshot.
    """
    return AbsorberComponentSnapshot(
        component_id=component.id,
        name=component.name,
        enabled=component.enabled,
        wavelength=component.wavelength,
        oscillator_strength=component.oscillator_strength,
        gamma=component.gamma,
        group_id=component.group_id,
        external_continuum_name=component.external_continuum_name,
        parameters=tuple(
            AbsorberComponentParameterSnapshot(
                name=name,
                value=parameter.value,
                min_value=parameter.min_val,
                max_value=parameter.max_val,
                fixed=parameter.fixed,
                error=parameter.error,
                unit=parameter.unit,
            )
            for name, parameter in component.parameters.items()
        ),
    )


def absorber_component_from_snapshot(snapshot: AbsorberComponentSnapshot) -> AbsorberComponent:
    """Create an absorber component from a typed history snapshot.

    Args:
        snapshot: Typed absorber component snapshot.

    Returns:
        Restored absorber component.
    """
    component = AbsorberComponent(
        name=snapshot.name,
        wavelength=snapshot.wavelength,
        oscillator_strength=snapshot.oscillator_strength,
        gamma=snapshot.gamma,
        component_id=snapshot.component_id,
        group_id=snapshot.group_id,
    )
    component.enabled = snapshot.enabled
    component.external_continuum_name = snapshot.external_continuum_name

    for parameter_snapshot in snapshot.parameters:
        parameter = component.parameters.get(parameter_snapshot.name)
        if parameter is None:
            component.parameters[parameter_snapshot.name] = Parameter(
                parameter_snapshot.name,
                parameter_snapshot.value,
                min_val=parameter_snapshot.min_value,
                max_val=parameter_snapshot.max_value,
                fixed=parameter_snapshot.fixed,
                error=parameter_snapshot.error,
                unit=parameter_snapshot.unit,
            )
            continue
        parameter.min_val = parameter_snapshot.min_value
        parameter.max_val = parameter_snapshot.max_value
        parameter.fixed = parameter_snapshot.fixed
        parameter.error = parameter_snapshot.error
        parameter.unit = parameter_snapshot.unit
        try:
            parameter.set_value(parameter_snapshot.value)
        except ValueError:
            clamped = max(
                parameter_snapshot.min_value,
                min(parameter_snapshot.max_value, parameter_snapshot.value),
            )
            parameter.set_value(clamped)
    return component


def model_link_snapshots(links: list[ModelLink]) -> tuple[ModelComponentLinkSnapshot, ...]:
    """Convert model link dictionaries to typed history snapshots.

    Args:
        links: Line-component link dictionaries.

    Returns:
        Typed model component link snapshots.
    """
    return tuple(
        ModelComponentLinkSnapshot(
            line_id=link["line_id"], component_id=link["component_id"], index=link["index"]
        )
        for link in links
    )


def model_link_sort_key(link: ModelComponentLinkSnapshot) -> int:
    """Return a stable sort key that appends negative-index links last.

    Args:
        link: Typed model component link snapshot.

    Returns:
        Sort key for restore ordering.
    """
    if link.index >= 0:
        return link.index
    return 999999


def tie_set_snapshot(tie_set: ParameterTieSet) -> TieSetSnapshot:
    """Convert a core parameter tie set to a typed history snapshot.

    Args:
        tie_set: Core parameter tie set.

    Returns:
        Typed tie set snapshot.
    """
    return TieSetSnapshot(
        uid=tie_set.uid,
        tie_id=tie_set.tie_id,
        name=tie_set.name,
        origin=tie_set.origin,
        mask=tuple(sorted(tie_set.mask)),
        component_ids=tuple(
            sorted(
                component.id for component in tie_set.components if component.tie_set is tie_set
            )
        ),
        shared_parameters=tuple(
            NamedParameterState(
                name=name,
                value=parameter.value,
                vary=not parameter.fixed,
                min_value=parameter.min_val,
                max_value=parameter.max_val,
                error=parameter.error,
            )
            for name, parameter in sorted(tie_set.shared_parameters.items())
        ),
        member_uids=tuple(sorted(tie_set.member_uids)),
    )


def tie_set_snapshots(tie_sets: tuple[ParameterTieSet, ...]) -> tuple[TieSetSnapshot, ...]:
    """Convert core parameter tie sets to typed history snapshots.

    Args:
        tie_sets: Core parameter tie sets.

    Returns:
        Typed tie set snapshots.
    """
    return tuple(tie_set_snapshot(tie_set) for tie_set in tie_sets)


def tie_set_from_snapshot(
    snapshot: TieSetSnapshot, components: Mapping[str, AbsorberComponent]
) -> ParameterTieSet | None:
    """Create a core parameter tie set from a typed history snapshot.

    Args:
        snapshot: Typed tie set snapshot.
        components: Available absorber components keyed by component ID.

    Returns:
        Restored parameter tie set, or None when fewer than two components exist.
    """
    component_ids = tuple(
        component_id for component_id in snapshot.component_ids if component_id in components
    )
    if len(component_ids) + len(snapshot.member_uids) < 2:
        return None
    if not snapshot.member_uids and len(component_ids) < 2:
        return None

    mask = frozenset(cast("TieParameterName", name) for name in snapshot.mask)
    tie_set = ParameterTieSet(
        snapshot.tie_id,
        uid=snapshot.uid,
        name=snapshot.name,
        mask=mask,
        origin=cast("Literal['multiplet', 'user']", snapshot.origin),
    )
    for component_id in component_ids:
        tie_set.add_component(components[component_id])

    if not snapshot.member_uids and len(tie_set.components) < 2:
        return None

    for parameter_state in snapshot.shared_parameters:
        parameter = tie_set.shared_parameters.get(cast("TieParameterName", parameter_state.name))
        if parameter is None:
            continue
        parameter.set_value(parameter_state.value)
        parameter.fixed = not parameter_state.vary
        parameter.error = parameter_state.error if parameter_state.error is not None else 0.0
    for component in tie_set.components:
        component.notify_changed()
    return tie_set


def tie_sets_from_snapshots(
    snapshots: tuple[TieSetSnapshot, ...],
    components: Mapping[str, AbsorberComponent],
    *,
    existing_tie_sets: Iterable[ParameterTieSet] = (),
) -> tuple[ParameterTieSet, ...]:
    """Create core tie sets from snapshots and apply nested attachments.

    Args:
        snapshots: Typed tie set snapshots.
        components: Available absorber components keyed by component ID.
        existing_tie_sets: Tie sets already registered on the model, used to
            resolve nested members whose snapshot is not part of ``snapshots``
            (e.g. a pre-existing multiplet tie set referenced by a restored
            external share).

    Returns:
        Restored parameter tie sets, nested members attached.
    """
    restored: list[ParameterTieSet] = []
    by_uid: dict[str, ParameterTieSet] = {}
    existing_by_uid = {tie_set.uid: tie_set for tie_set in existing_tie_sets}

    for snapshot in snapshots:
        tie_set = tie_set_from_snapshot(snapshot, components)
        if tie_set is None:
            continue
        restored.append(tie_set)
        by_uid[tie_set.uid] = tie_set

    for snapshot in snapshots:
        outer = by_uid.get(snapshot.uid)
        if outer is None:
            continue
        for member_uid in snapshot.member_uids:
            inner = by_uid.get(member_uid) or existing_by_uid.get(member_uid)
            if inner is None or inner.parent_tie is not None:
                continue
            outer.attach_tie_set(inner)

    return tuple(restored)


def absorption_line_from_snapshot(snapshot: AbsorptionLineSnapshot) -> AbsorptionLine:
    """Create a core absorption line from a typed history snapshot.

    Args:
        snapshot: Typed absorption line snapshot.

    Returns:
        Restored core absorption line.
    """
    return AbsorptionLine(
        line_id=snapshot.line_id,
        species=snapshot.species,
        rest_wavelength=snapshot.rest_wavelength,
        center_z=snapshot.center_z,
        window_kms=snapshot.window_kms,
        multiplet_label=snapshot.multiplet_label,
        transition_name=snapshot.transition_name,
        oscillator_strength=snapshot.oscillator_strength,
        gamma_value=snapshot.gamma_value,
        lambda_range=snapshot.lambda_range,
        region_id=snapshot.region_id,
        multiplet_ids=list(snapshot.multiplet_ids),
        model_ids=list(snapshot.model_ids),
        needs_optimization=snapshot.needs_optimization,
        created_by=snapshot.created_by,
        created_at=snapshot.created_at,
    )


def temporary_line_from_snapshot(snapshot: TemporaryLineSnapshot) -> TemporaryLine:
    """Create a core temporary line from a typed history snapshot.

    Args:
        snapshot: Typed temporary line snapshot.

    Returns:
        Restored core temporary line.
    """
    return TemporaryLine(
        temporary_line_id=snapshot.temporary_line_id,
        species=snapshot.species,
        lambda_min=snapshot.lambda_min,
        lambda_max=snapshot.lambda_max,
        creation_method=snapshot.creation_method,
        line_id=snapshot.line_id,
        rest_wavelength=snapshot.rest_wavelength,
        center_z=snapshot.center_z,
        multiplet_id=snapshot.multiplet_id,
        multiplet_label=snapshot.multiplet_label,
        tie_group_key=snapshot.tie_group_key,
        transition_name=snapshot.transition_name,
        oscillator_strength=snapshot.oscillator_strength,
        gamma_value=snapshot.gamma_value,
        analysis_half_width_kms=snapshot.analysis_half_width.kms,
    )


def temporary_line_snapshots_for_ids(
    session: IdentifySessionState, temporary_line_ids: tuple[str, ...]
) -> tuple[TemporaryLineSnapshot, ...]:
    """Return typed temporary-line snapshots for known line IDs.

    Args:
        session: Identify session containing temporary lines.
        temporary_line_ids: Temporary line IDs to snapshot.

    Returns:
        Typed temporary-line snapshots for matching IDs.
    """
    temporary_lines_by_id = {
        temporary_line.temporary_line_id: temporary_line
        for temporary_line in session.temporary_lines
    }
    return tuple(
        temporary_line_snapshot(temporary_line)
        for temporary_line_id in temporary_line_ids
        if (temporary_line := temporary_lines_by_id.get(temporary_line_id)) is not None
    )


def temporary_line_snapshot(temporary_line: TemporaryLine) -> TemporaryLineSnapshot:
    """Convert a core temporary line to an application snapshot.

    Args:
        temporary_line: Core temporary line.

    Returns:
        Typed temporary line snapshot.
    """
    return TemporaryLineSnapshot(
        temporary_line_id=temporary_line.temporary_line_id,
        species=temporary_line.species,
        lambda_min=temporary_line.lambda_min,
        lambda_max=temporary_line.lambda_max,
        creation_method=temporary_line.creation_method,
        line_id=temporary_line.line_id,
        rest_wavelength=temporary_line.rest_wavelength,
        center_z=temporary_line.center_z,
        multiplet_id=temporary_line.multiplet_id,
        multiplet_label=temporary_line.multiplet_label,
        tie_group_key=temporary_line.tie_group_key,
        transition_name=temporary_line.transition_name,
        oscillator_strength=temporary_line.oscillator_strength,
        gamma_value=temporary_line.gamma_value,
        analysis_half_width=LineAnalysisHalfWidth(temporary_line.analysis_half_width_kms),
    )


def absorption_region_snapshot(region: AbsorptionRegion) -> AbsorptionRegionSnapshot:
    """Convert a core absorption region to a typed history snapshot.

    Args:
        region: Core absorption region.

    Returns:
        Typed absorption region snapshot.
    """
    return AbsorptionRegionSnapshot(
        region_id=region.region_id,
        line_ids=tuple(region.line_ids),
        display_color=region.display_color,
        analysis_range=region.analysis_range,
        created_at=region.created_at,
    )


def absorption_line_snapshot(line: AbsorptionLine) -> AbsorptionLineSnapshot:
    """Convert a core absorption line to a typed history snapshot.

    Args:
        line: Core absorption line.

    Returns:
        Typed absorption line snapshot.
    """
    return AbsorptionLineSnapshot(
        line_id=line.line_id,
        species=line.species,
        rest_wavelength=line.rest_wavelength,
        center_z=line.center_z,
        window_kms=line.window_kms,
        multiplet_label=line.multiplet_label,
        transition_name=line.transition_name,
        oscillator_strength=line.oscillator_strength,
        gamma_value=line.gamma_value,
        lambda_range=line.lambda_range,
        region_id=line.region_id,
        multiplet_ids=tuple(line.multiplet_ids),
        model_ids=tuple(line.model_ids),
        needs_optimization=line.needs_optimization,
        created_by=line.created_by,
        created_at=line.created_at,
    )


def mask_from_snapshot(snapshot: MaskDefinitionSnapshot) -> MaskDefinition:
    """Convert a typed mask snapshot to a core mask definition.

    Args:
        snapshot: Typed mask definition snapshot.

    Returns:
        Core mask definition.
    """
    return MaskDefinition.from_payload(
        {
            "id": snapshot.identifier,
            "label": snapshot.label,
            "mode": snapshot.mode,
            "start_wavelength": snapshot.start_wavelength,
            "end_wavelength": snapshot.end_wavelength,
            "center": snapshot.center,
            "half_width": snapshot.half_width,
            "note": snapshot.note,
            "color": snapshot.color,
            "enabled": snapshot.enabled,
            "group_id": snapshot.group_id,
        }
    )


def mask_definition_snapshot(mask: MaskDefinition) -> MaskDefinitionSnapshot:
    """Convert a core mask definition to an immutable history snapshot."""
    return MaskDefinitionSnapshot(
        identifier=mask.identifier,
        label=mask.label,
        mode=mask.mode.value,
        start_wavelength=mask.start_wavelength,
        end_wavelength=mask.end_wavelength,
        center=mask.center,
        half_width=mask.half_width,
        note=mask.note,
        color=mask.color,
        enabled=mask.enabled,
        group_id=mask.group_id,
    )
