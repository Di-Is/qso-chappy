"""Mapping between domain project objects and typed project documents."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from chappy.application.project_document import (
    AbsorptionLineDocument,
    AbsorptionRegionDocument,
    AnalysisArtifactDocument,
    ComponentDocument,
    FitSummaryDocument,
    IdentifyStateDocument,
    JsonObject,
    JsonValue,
    MaskDocument,
    ParameterDocument,
    ProjectDocument,
    RegionAnalysisStateDocument,
    SpectrumDocument,
    TieSetDocument,
    TieSharedParameterDocument,
)
from chappy.application.structure.region_line_repair import (
    RegionLineRepairReport,
    RepairRegionLineTopologyUseCase,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.base import ModelComponent, Parameter
from chappy.core.components.continuum import ContinuumComponent
from chappy.core.components.optimize import FitOutcome, OptimizeComponent
from chappy.core.components.tie_set import ParameterTieSet
from chappy.core.identify_state import IdentifySessionState
from chappy.core.masking import MaskDefinition, MaskMode
from chappy.core.optimizer_settings import (
    DEFAULT_AUTO_CONTINUE,
    DEFAULT_MAX_FUNCTION_EVALUATIONS,
    DEFAULT_TOLERANCE,
    SETTINGS_REGION_OPTIMIZER_KEY,
    OptimizerSettingsState,
)
from chappy.core.resolution import (
    SETTINGS_RESOLUTION_ENABLED_KEY,
    SETTINGS_RESOLUTION_VALUE_KEY,
    ResolutionState,
)
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.core.spectrum_model import SpectrumModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProjectLoadResult:
    """Project reconstructed from storage and repairs applied during loading."""

    project: SpectroscopyProject
    repair_report: RegionLineRepairReport


def project_to_document(project: SpectroscopyProject) -> ProjectDocument:
    """Convert a project instance into a typed document.

    Args:
        project: Project to snapshot.

    Returns:
        Typed document containing project state.
    """
    spectrum = project.model.observed_spectrum
    settings = to_json_object(project.settings)
    settings[SETTINGS_RESOLUTION_VALUE_KEY] = float(project.resolution_state.value)
    settings[SETTINGS_RESOLUTION_ENABLED_KEY] = bool(project.resolution_state.enabled)
    region_optimizer_settings = project.region_optimizer_settings_overrides()
    if region_optimizer_settings:
        settings[SETTINGS_REGION_OPTIMIZER_KEY] = {
            region_id: {
                "max_function_evaluations": int(state.max_function_evaluations),
                "tolerance": float(state.tolerance),
                "auto_continue": bool(state.auto_continue),
            }
            for region_id, state in region_optimizer_settings.items()
        }
    return ProjectDocument(
        name=project.name,
        spectrum_filename=project.spectrum_filename,
        created=project.created,
        modified=project.modified,
        metadata=to_json_object(project.metadata),
        settings=settings,
        spectrum=_spectrum_to_document(spectrum),
        components=tuple(
            _component_to_document(component)
            for component in project.model.components
            if not isinstance(component, OptimizeComponent)
        ),
        masks=tuple(_mask_to_document(mask) for mask in project.model.mask_definitions),
        fit_wavelength_range=project.model.fit_wavelength_range,
        tie_sets=tuple(_tie_set_to_document(tie_set) for tie_set in project.model.iter_tie_sets()),
        absorption_regions=tuple(
            _absorption_region_to_document(region)
            for region in project.absorption_regions.values()
        ),
        absorption_lines=tuple(
            _absorption_line_to_document(line) for line in project.absorption_lines.values()
        ),
        analysis_states=tuple(
            _region_analysis_state_to_document(state) for state in project.region_analysis_states()
        ),
        identify_state=_identify_state_to_document(project.identify_state),
    )


def project_from_document(document: ProjectDocument) -> ProjectLoadResult:
    """Build a project instance from a typed document.

    Args:
        document: Source document.

    Returns:
        Reconstructed project and any automatic topology repairs.
    """
    project = SpectroscopyProject(name=document.name, spectrum_filename=document.spectrum_filename)
    project.created = document.created
    project.modified = document.modified
    project.metadata = dict(document.metadata)
    project.settings = dict(document.settings)

    model = SpectrumModel()
    if document.spectrum is not None:
        model.set_observed_spectrum(_spectrum_from_document(document.spectrum))

    for component_document in document.components:
        model.add_component(_component_from_document(component_document))

    model.mask_definitions = tuple(_mask_from_document(mask) for mask in document.masks)
    model.fit_wavelength_range = document.fit_wavelength_range
    project.model = model
    project.model.rebuild_tie_sets(_tie_sets_to_payload(document.tie_sets))
    resolution_state = _resolve_resolution_state(document.settings)
    if resolution_state is not None:
        project.set_resolution(resolution_state.value, resolution_state.enabled)

    project.load_absorption_state(
        regions={
            region.region_id: _absorption_region_from_document(region)
            for region in document.absorption_regions
        },
        lines={
            line.line_id: _absorption_line_from_document(line)
            for line in document.absorption_lines
        },
    )
    for region_id, state in _resolve_region_optimizer_settings(document.settings).items():
        if region_id in project.absorption_regions:
            project.set_region_optimizer_settings(
                region_id, state.max_function_evaluations, state.tolerance, state.auto_continue
            )
    project.identify_state = _identify_state_from_document(document.identify_state)
    project.load_region_analysis_states(
        _region_analysis_state_from_document(state) for state in document.analysis_states
    )
    repair_report = RepairRegionLineTopologyUseCase().execute(
        project.absorption_regions, project.absorption_lines
    )
    project.prune_empty_absorption_regions()
    project.modified = document.modified
    return ProjectLoadResult(project=project, repair_report=repair_report)


def _region_analysis_state_to_document(state: RegionAnalysisState) -> RegionAnalysisStateDocument:
    artifact = state.artifact
    return RegionAnalysisStateDocument(
        region_id=state.region_id,
        current_revision=state.current_revision.value,
        artifact=(
            AnalysisArtifactDocument(
                region_id=artifact.region_id,
                source_revision=artifact.source_revision.value,
                fit_summary=FitSummaryDocument(
                    chi_squared=artifact.fit_summary.chi_squared,
                    reduced_chi_squared=artifact.fit_summary.reduced_chi_squared,
                    degrees_of_freedom=artifact.fit_summary.degrees_of_freedom,
                    n_parameters=artifact.fit_summary.n_parameters,
                    n_function_evaluations=artifact.fit_summary.n_function_evaluations,
                    outcome=artifact.fit_summary.outcome.value
                    if artifact.fit_summary.outcome is not None
                    else None,
                ),
            )
            if artifact is not None
            else None
        ),
    )


def _region_analysis_state_from_document(
    document: RegionAnalysisStateDocument,
) -> RegionAnalysisState:
    artifact_document = document.artifact
    artifact = (
        AnalysisArtifact(
            region_id=artifact_document.region_id,
            source_revision=AnalysisRevision(artifact_document.source_revision),
            fit_summary=FitSummary(
                chi_squared=artifact_document.fit_summary.chi_squared,
                reduced_chi_squared=artifact_document.fit_summary.reduced_chi_squared,
                degrees_of_freedom=artifact_document.fit_summary.degrees_of_freedom,
                n_parameters=artifact_document.fit_summary.n_parameters,
                n_function_evaluations=artifact_document.fit_summary.n_function_evaluations,
                outcome=FitOutcome(artifact_document.fit_summary.outcome)
                if artifact_document.fit_summary.outcome is not None
                else None,
            ),
        )
        if artifact_document is not None
        else None
    )
    return RegionAnalysisState(
        region_id=document.region_id,
        current_revision=AnalysisRevision(document.current_revision),
        artifact=artifact,
    )


def _resolve_resolution_state(settings: Mapping[str, JsonValue]) -> ResolutionState | None:
    value_raw = settings.get(SETTINGS_RESOLUTION_VALUE_KEY, settings.get("resolution"))
    value = _parse_resolution_value(value_raw)
    if value is None:
        return None

    enabled_raw = settings.get(SETTINGS_RESOLUTION_ENABLED_KEY, settings.get("resolution_enabled"))
    enabled = _parse_resolution_enabled(enabled_raw)
    if enabled is None:
        return None
    return ResolutionState(value=value, enabled=enabled)


def _resolve_region_optimizer_settings(
    settings: Mapping[str, JsonValue],
) -> dict[str, OptimizerSettingsState]:
    raw = settings.get(SETTINGS_REGION_OPTIMIZER_KEY)
    if not isinstance(raw, dict):
        return {}
    resolved: dict[str, OptimizerSettingsState] = {}
    for region_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        resolved[region_id] = OptimizerSettingsState(
            max_function_evaluations=_parse_optimizer_max_function_evaluations(
                entry.get("max_function_evaluations")
            ),
            tolerance=_parse_optimizer_tolerance(entry.get("tolerance")),
            auto_continue=_parse_optimizer_auto_continue(entry.get("auto_continue")),
        )
    return resolved


def _parse_optimizer_max_function_evaluations(value: JsonValue | None) -> int:
    if isinstance(value, bool) or value is None:
        return DEFAULT_MAX_FUNCTION_EVALUATIONS
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return DEFAULT_MAX_FUNCTION_EVALUATIONS
    return DEFAULT_MAX_FUNCTION_EVALUATIONS


def _parse_optimizer_auto_continue(value: JsonValue | None) -> bool:
    if isinstance(value, bool):
        return value
    return DEFAULT_AUTO_CONTINUE


def _parse_optimizer_tolerance(value: JsonValue | None) -> float:
    if isinstance(value, bool) or value is None:
        return DEFAULT_TOLERANCE
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return DEFAULT_TOLERANCE
    return DEFAULT_TOLERANCE


def _parse_resolution_value(value: JsonValue | None) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_resolution_enabled(value: JsonValue | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "on"}
    if isinstance(value, int | float):
        return bool(value)
    return None


def to_json_object(mapping: Mapping[str, object]) -> JsonObject:
    """Convert a mapping into a JSON-compatible object.

    Args:
        mapping: Source mapping.

    Returns:
        JSON-compatible object.
    """
    return {str(key): to_json_value(value) for key, value in mapping.items()}


def to_json_value(value: object) -> JsonValue:
    """Convert a Python value into a JSON-compatible value.

    Args:
        value: Source value.

    Returns:
        JSON-compatible value.
    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [to_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def create_project_from_spectrum(
    spectrum: Spectrum, *, name: str, spectrum_filename: str
) -> SpectroscopyProject:
    """Create a project from an observed spectrum.

    Args:
        spectrum: Observed spectrum.
        name: Project name.
        spectrum_filename: Source spectrum file path.

    Returns:
        Project initialized with the observed spectrum and default continuum.
    """
    project = SpectroscopyProject(name=name, spectrum_filename=spectrum_filename)
    project.model.set_observed_spectrum(spectrum)
    _extract_spectrum_metadata(project, spectrum.header)
    _add_default_continuum(project, spectrum)
    project.prune_empty_absorption_regions()
    return project


def _spectrum_to_document(spectrum: Spectrum | None) -> SpectrumDocument | None:
    if spectrum is None:
        return None
    return SpectrumDocument(
        wavelength=np.asarray(spectrum.wavelength, dtype=np.float64),
        flux=np.asarray(spectrum.flux, dtype=np.float64),
        error=np.asarray(spectrum.error, dtype=np.float64) if spectrum.error is not None else None,
        header=to_json_object(spectrum.header),
    )


def _spectrum_from_document(document: SpectrumDocument) -> Spectrum:
    return Spectrum(
        wavelength=np.asarray(document.wavelength, dtype=np.float64),
        flux=np.asarray(document.flux, dtype=np.float64),
        error=np.asarray(document.error, dtype=np.float64) if document.error is not None else None,
        header=dict(document.header),
    )


def _parameter_to_document(parameter: Parameter) -> ParameterDocument:
    return ParameterDocument(
        name=parameter.name,
        value=float(parameter.value),
        min_val=float(parameter.min_val),
        max_val=float(parameter.max_val),
        fixed=bool(parameter.fixed),
        error=float(parameter.error),
        unit=parameter.unit,
    )


def _component_to_document(component: ModelComponent) -> ComponentDocument:
    parameters = tuple(
        _parameter_to_document(parameter) for parameter in component.parameters.values()
    )
    if isinstance(component, AbsorberComponent):
        return ComponentDocument(
            component_id=component.id,
            kind="absorber",
            name=component.name,
            enabled=component.enabled,
            parameters=parameters,
            wavelength=float(component.wavelength),
            oscillator_strength=float(component.oscillator_strength),
            gamma=float(component.gamma),
            group_id=component.group_id,
        )
    if isinstance(component, ContinuumComponent):
        return ComponentDocument(
            component_id=component.id,
            kind="continuum",
            name=component.name,
            enabled=component.enabled,
            parameters=parameters,
            continuum_points=tuple(
                (float(wavelength), float(flux))
                for wavelength, flux in component.get_continuum_points()
            ),
            is_shared_with_absorption=component.is_shared_with_absorption,
        )
    msg = f"Unsupported component type for project persistence: {type(component).__name__}"
    raise ValueError(msg)


def _component_from_document(document: ComponentDocument) -> ModelComponent:
    component: ModelComponent
    if document.kind == "absorber":
        absorber = AbsorberComponent(
            name=document.name,
            wavelength=_required_float_field(document, "wavelength"),
            oscillator_strength=_required_float_field(document, "oscillator_strength"),
            gamma=_required_float_field(document, "gamma"),
            component_id=document.component_id,
            group_id=document.group_id,
        )
        component = absorber
    elif document.kind == "continuum":
        continuum = ContinuumComponent(name=document.name)
        continuum.id = document.component_id
        continuum.continuum_points = list(document.continuum_points)
        continuum.is_shared_with_absorption = document.is_shared_with_absorption
        component = continuum
    else:
        msg = f"Unsupported component kind: {document.kind}"
        raise ValueError(msg)

    _restore_parameters(component, document.parameters)
    component.enabled = document.enabled
    return component


def _required_float_field(document: ComponentDocument, field_name: str) -> float:
    """Return a required persisted component field.

    Args:
        document: Component document being restored.
        field_name: Name of the required float field.

    Returns:
        Persisted field value.

    Raises:
        ValueError: If the field is missing.
    """
    if field_name == "wavelength":
        value = document.wavelength
    elif field_name == "oscillator_strength":
        value = document.oscillator_strength
    elif field_name == "gamma":
        value = document.gamma
    else:
        msg = f"Unsupported required component field: {field_name!r}"
        raise ValueError(msg)
    if value is None:
        msg = (
            f"Component document {document.component_id!r} of kind "
            f"{document.kind!r} is missing required field {field_name!r}."
        )
        raise ValueError(msg)
    return float(value)


def _restore_parameters(
    component: ModelComponent, parameters: tuple[ParameterDocument, ...]
) -> None:
    for parameter_document in parameters:
        parameter = component.parameters.get(parameter_document.name)
        if parameter is None:
            parameter = Parameter(
                parameter_document.name,
                parameter_document.value,
                min_val=parameter_document.min_val,
                max_val=parameter_document.max_val,
                fixed=parameter_document.fixed,
                error=parameter_document.error,
                unit=parameter_document.unit,
            )
            component.parameters[parameter_document.name] = parameter
            continue

        parameter.min_val = parameter_document.min_val
        parameter.max_val = parameter_document.max_val
        parameter.fixed = parameter_document.fixed
        parameter.error = parameter_document.error
        parameter.unit = parameter_document.unit
        parameter.value = parameter_document.value


def _mask_to_document(mask: MaskDefinition) -> MaskDocument:
    return MaskDocument(
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


def _mask_from_document(document: MaskDocument) -> MaskDefinition:
    return MaskDefinition(
        identifier=document.identifier,
        label=document.label,
        mode=MaskMode(document.mode),
        start_wavelength=document.start_wavelength,
        end_wavelength=document.end_wavelength,
        center=document.center,
        half_width=document.half_width,
        note=document.note,
        color=document.color,
        enabled=document.enabled,
        group_id=document.group_id,
    )


def _tie_set_to_document(tie_set: object) -> TieSetDocument:
    if not isinstance(tie_set, ParameterTieSet):
        msg = f"Unsupported parameter tie set type: {type(tie_set).__name__}"
        raise TypeError(msg)
    return TieSetDocument(
        uid=tie_set.uid,
        tie_id=tie_set.tie_id,
        name=tie_set.name,
        origin=tie_set.origin,
        mask=tuple(sorted(tie_set.mask)),
        component_ids=tuple(
            component.id for component in tie_set.components if component.tie_set is tie_set
        ),
        member_uids=tuple(sorted(tie_set.member_uids)),
        shared_parameters=tuple(
            TieSharedParameterDocument(
                name=name, value=float(parameter.value), fixed=bool(parameter.fixed)
            )
            for name, parameter in tie_set.shared_parameters.items()
        ),
    )


def _tie_sets_to_payload(tie_sets: tuple[TieSetDocument, ...]) -> list[dict[str, object]]:
    return [
        {
            "uid": tie_set.uid,
            "tie_id": tie_set.tie_id,
            "name": tie_set.name,
            "origin": tie_set.origin,
            "mask": list(tie_set.mask),
            "component_ids": list(tie_set.component_ids),
            "member_uids": list(tie_set.member_uids),
            "shared_parameters": {
                parameter.name: {"value": parameter.value, "fixed": parameter.fixed}
                for parameter in tie_set.shared_parameters
            },
        }
        for tie_set in tie_sets
    ]


def _absorption_region_to_document(region: AbsorptionRegion) -> AbsorptionRegionDocument:
    return AbsorptionRegionDocument(
        region_id=region.region_id,
        line_ids=tuple(region.line_ids),
        display_color=region.display_color,
        analysis_range=region.analysis_range,
        created_at=region.created_at,
    )


def _absorption_region_from_document(document: AbsorptionRegionDocument) -> AbsorptionRegion:
    return AbsorptionRegion(
        region_id=document.region_id,
        line_ids=list(document.line_ids),
        display_color=document.display_color,
        analysis_range=document.analysis_range,
        created_at=document.created_at,
    )


def _absorption_line_to_document(line: AbsorptionLine) -> AbsorptionLineDocument:
    return AbsorptionLineDocument(
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


def _absorption_line_from_document(document: AbsorptionLineDocument) -> AbsorptionLine:
    return AbsorptionLine(
        line_id=document.line_id,
        species=document.species,
        rest_wavelength=document.rest_wavelength,
        center_z=document.center_z,
        window_kms=document.window_kms,
        multiplet_label=document.multiplet_label,
        transition_name=document.transition_name,
        oscillator_strength=document.oscillator_strength,
        gamma_value=document.gamma_value,
        lambda_range=document.lambda_range,
        region_id=document.region_id,
        multiplet_ids=list(document.multiplet_ids),
        model_ids=list(document.model_ids),
        needs_optimization=document.needs_optimization,
        created_by=document.created_by,
        created_at=document.created_at,
    )


def _identify_state_to_document(state: IdentifySessionState) -> IdentifyStateDocument:
    return IdentifyStateDocument(
        work_phase=state.work_phase,
        reference_z=state.reference_z,
        last_added_wavelength=state.last_added_wavelength,
        last_click_wavelength=state.last_click_wavelength,
    )


def _identify_state_from_document(document: IdentifyStateDocument) -> IdentifySessionState:
    # Legacy "grouping" work_phase values normalize to the default "temporary_line_add".
    state = IdentifySessionState()
    state.reference_z = document.reference_z
    state.last_added_wavelength = document.last_added_wavelength
    state.last_click_wavelength = document.last_click_wavelength
    return state


def _extract_spectrum_metadata(project: SpectroscopyProject, header: Mapping[str, object]) -> None:
    fits_mapping = {
        "OBJECT": "object_name",
        "OBSERVER": "observer",
        "DATE-OBS": "observation_date",
        "EXPTIME": "exposure_time",
        "INSTRUME": "instrument",
        "TELESCOP": "telescope",
        "AIRMASS": "airmass",
        "RA": "right_ascension",
        "DEC": "declination",
    }
    for source_key, target_key in fits_mapping.items():
        value = header.get(source_key)
        if value is not None:
            project.metadata[target_key] = to_json_value(value)


def _add_default_continuum(project: SpectroscopyProject, spectrum: Spectrum) -> None:
    default_continuum = ContinuumComponent("Continuum")
    if len(spectrum.wavelength) > 0:
        min_wave = float(np.min(spectrum.wavelength))
        max_wave = float(np.max(spectrum.wavelength))
        mid_wave = (min_wave + max_wave) / 2.0
        default_continuum.continuum_points = [(min_wave, 1.0), (mid_wave, 1.0), (max_wave, 1.0)]
    project.model.add_component(default_continuum)
