"""Tests for side-effect-free scientific structure impact previews."""

from __future__ import annotations

from chappy.application.structure import (
    DeleteStructureRequest,
    MergeStructureRequest,
    MoveStructureRequest,
    SplitStructureRequest,
    StructureImpactOperation,
    StructureImpactPreviewUseCase,
    StructureMutationOutcome,
    UnlinkStructureRequest,
)
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import (
    AnalysisArtifact,
    AnalysisRevision,
    FitSummary,
    RegionAnalysisState,
)
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.masking import MaskDefinition
from chappy.core.spectroscopy_project import SpectroscopyProject


def _line(
    line_id: str,
    region_id: str,
    *,
    related_ids: tuple[str, ...] = (),
    model_ids: tuple[str, ...] = (),
) -> AbsorptionLine:
    """Create one test absorption line."""
    return AbsorptionLine(
        line_id=line_id,
        species="Mg II",
        rest_wavelength=2796.35,
        center_z=1.0,
        window_kms=150.0,
        multiplet_label="Mg II",
        transition_name="Mg II 2796",
        oscillator_strength=0.6,
        gamma_value=1.0e8,
        region_id=region_id,
        multiplet_ids=list(related_ids),
        model_ids=list(model_ids),
    )


def _add_region(
    project: SpectroscopyProject, region_id: str, lines: tuple[AbsorptionLine, ...]
) -> None:
    """Register a region and its complete line membership."""
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=[line.line_id for line in lines]
    )
    project.absorption_lines.update((line.line_id, line) for line in lines)


def _add_model(project: SpectroscopyProject, model_id: str, region_id: str) -> None:
    """Register an absorber component with a stable ID and region."""
    project.model.add_component(AbsorberComponent(component_id=model_id, group_id=region_id))


def _add_mask(project: SpectroscopyProject, mask_id: str, region_id: str) -> None:
    """Register one region-owned mask."""
    project.model.add_mask_definition(
        MaskDefinition.from_range(1000.0, 1001.0, identifier=mask_id).with_group_id(region_id)
    )


def _project_snapshot(project: SpectroscopyProject) -> tuple[object, ...]:
    """Capture scientific facts whose equality proves preview purity."""
    return (
        project.modified,
        tuple(
            (region_id, tuple(region.line_ids), region.analysis_range)
            for region_id, region in project.absorption_regions.items()
        ),
        tuple(
            (
                line_id,
                line.region_id,
                tuple(line.multiplet_ids),
                tuple(line.model_ids),
                line.needs_optimization,
            )
            for line_id, line in project.absorption_lines.items()
        ),
        tuple(
            (component.id, getattr(component, "group_id", None))
            for component in project.model.components
        ),
        tuple((mask.identifier, mask.group_id) for mask in project.model.mask_definitions),
        project.stored_region_analysis_states_for_transaction(),
    )


def _seed_artifact(project: SpectroscopyProject, region_id: str) -> None:
    """Store revision/artifact evidence to catch accidental preview invalidation."""
    revision = AnalysisRevision(3)
    project.set_region_analysis_states(
        (
            RegionAnalysisState(
                region_id=region_id,
                current_revision=revision,
                artifact=AnalysisArtifact(
                    region_id=region_id,
                    source_revision=revision,
                    fit_summary=FitSummary(chi_squared=1.5),
                ),
            ),
        )
    )


def test_move_preview_expands_multiplet_and_reports_cascades_without_mutation() -> None:
    """Move preview reports expanded targets, model changes, and source deletion."""
    project = SpectroscopyProject()
    blue = _line("blue", "source", related_ids=("red",), model_ids=("model-blue",))
    red = _line("red", "source", related_ids=("blue",), model_ids=("model-red",))
    _add_region(project, "source", (blue, red))
    _add_region(project, "target", ())
    _add_model(project, "model-blue", "source")
    _add_model(project, "model-red", "source")
    _add_mask(project, "source-mask", "source")
    _seed_artifact(project, "source")
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_move(
        project, MoveStructureRequest(line_ids=("blue",), target_region_id="target")
    )

    assert preview.operation is StructureImpactOperation.MOVE
    assert preview.outcome is StructureMutationOutcome.CHANGED
    assert preview.changed_region_ids == ("target",)
    assert preview.removed_region_ids == ("source",)
    assert preview.expanded_request_line_ids == ("blue", "red")
    assert preview.changed_line_ids == ("blue", "red")
    assert preview.changed_model_ids == ("model-blue", "model-red")
    assert preview.removed_mask_ids == ("source-mask",)
    assert preview.changed_line_count == 2
    assert _project_snapshot(project) == before


def test_move_preview_reports_no_change_for_lines_already_in_destination() -> None:
    """A semantically inert move has a typed NoChange preview."""
    project = SpectroscopyProject()
    _add_region(project, "target", (_line("line", "target"),))
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_move(
        project, MoveStructureRequest(line_ids=("line",), target_region_id="target")
    )

    assert preview.outcome is StructureMutationOutcome.NO_CHANGE
    assert not preview.changed
    assert preview.changed_region_count == 0
    assert _project_snapshot(project) == before


def test_split_preview_reports_existing_source_and_anonymous_created_region() -> None:
    """Split preview distinguishes a known changed source from one future region."""
    project = SpectroscopyProject()
    selected = _line("selected", "source", model_ids=("model",))
    remaining = _line("remaining", "source")
    _add_region(project, "source", (selected, remaining))
    _add_model(project, "model", "source")
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_split(
        project, SplitStructureRequest(line_ids=("selected",))
    )

    assert preview.operation is StructureImpactOperation.SPLIT
    assert preview.changed_region_ids == ("source",)
    assert preview.removed_region_ids == ()
    assert preview.created_region_count == 1
    assert preview.changed_line_ids == ("selected",)
    assert preview.changed_model_ids == ("model",)
    assert _project_snapshot(project) == before


def test_merge_preview_reports_secondary_lines_models_and_masks() -> None:
    """Merge preview exposes every reassigned identity and removed secondary region."""
    project = SpectroscopyProject()
    _add_region(project, "primary", (_line("primary-line", "primary"),))
    _add_region(
        project,
        "secondary",
        (_line("secondary-line", "secondary", model_ids=("secondary-model",)),),
    )
    _add_model(project, "secondary-model", "secondary")
    _add_mask(project, "secondary-mask", "secondary")
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_merge(
        project, MergeStructureRequest(region_ids=("primary", "secondary"))
    )

    assert preview.operation is StructureImpactOperation.MERGE
    assert preview.changed_region_ids == ("primary",)
    assert preview.removed_region_ids == ("secondary",)
    assert preview.changed_line_ids == ("secondary-line",)
    assert preview.changed_model_ids == ("secondary-model",)
    assert preview.changed_mask_ids == ("secondary-mask",)
    assert _project_snapshot(project) == before


def test_delete_preview_reports_expanded_deletions_and_global_invalidation() -> None:
    """Model-deleting line removal reports all surviving analysis-capable regions."""
    project = SpectroscopyProject()
    blue = _line("blue", "deleted", related_ids=("red",), model_ids=("model-blue",))
    red = _line("red", "deleted", related_ids=("blue",), model_ids=("model-red",))
    _add_region(project, "deleted", (blue, red))
    _add_region(project, "survivor", (_line("surviving-line", "survivor"),))
    _add_model(project, "model-blue", "deleted")
    _add_model(project, "model-red", "deleted")
    _add_mask(project, "deleted-mask", "deleted")
    _seed_artifact(project, "survivor")
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_delete(
        project, DeleteStructureRequest(line_ids=("blue",))
    )

    assert preview.operation is StructureImpactOperation.DELETE
    assert preview.changed_region_ids == ("survivor",)
    assert preview.removed_region_ids == ("deleted",)
    assert preview.expanded_request_line_ids == ("blue", "red")
    assert preview.removed_line_ids == ("blue", "red")
    assert preview.removed_model_ids == ("model-blue", "model-red")
    assert preview.removed_mask_ids == ("deleted-mask",)
    assert preview.removed_region_count == 1
    assert preview.removed_line_count == 2
    assert preview.removed_model_count == 2
    assert preview.removed_mask_count == 1
    assert _project_snapshot(project) == before


def test_region_delete_reports_surviving_multiplet_reference_change() -> None:
    """Direct region deletion reports an external multiplet companion as changed."""
    project = SpectroscopyProject()
    selected = _line("selected", "deleted", related_ids=("companion",))
    companion = _line("companion", "survivor", related_ids=("selected",))
    _add_region(project, "deleted", (selected,))
    _add_region(project, "survivor", (companion,))
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_delete(
        project, DeleteStructureRequest(region_ids=("deleted",))
    )

    assert preview.removed_region_ids == ("deleted",)
    assert preview.removed_line_ids == ("selected",)
    assert preview.changed_line_ids == ("companion",)
    assert preview.removed_model_ids == ()
    assert _project_snapshot(project) == before


def test_unlink_preview_reports_every_linked_line_and_owning_region() -> None:
    """Unlink preview expands the linked lines without clearing their links."""
    project = SpectroscopyProject()
    blue = _line("blue", "first", related_ids=("red",))
    red = _line("red", "second", related_ids=("blue",))
    _add_region(project, "first", (blue,))
    _add_region(project, "second", (red,))
    before = _project_snapshot(project)

    preview = StructureImpactPreviewUseCase().preview_unlink(
        project, UnlinkStructureRequest(line_id="blue")
    )

    assert preview.operation is StructureImpactOperation.UNLINK
    assert preview.changed_region_ids == ("first", "second")
    assert preview.expanded_request_line_ids == ("blue", "red")
    assert preview.changed_line_ids == ("blue", "red")
    assert preview.removed_region_ids == ()
    assert _project_snapshot(project) == before


def test_empty_structure_requests_are_typed_no_change() -> None:
    """Every current structure operation returns NoChange for an empty request."""
    project = SpectroscopyProject()
    _add_region(project, "independent-region", (_line("independent", "independent-region"),))
    use_case = StructureImpactPreviewUseCase()

    previews = (
        use_case.preview_move(project, MoveStructureRequest((), None)),
        use_case.preview_split(project, SplitStructureRequest(())),
        use_case.preview_merge(project, MergeStructureRequest(())),
        use_case.preview_unlink(project, UnlinkStructureRequest("independent")),
        use_case.preview_delete(project, DeleteStructureRequest()),
    )

    assert [preview.operation for preview in previews] == list(StructureImpactOperation)
    assert all(preview.outcome is StructureMutationOutcome.NO_CHANGE for preview in previews)
