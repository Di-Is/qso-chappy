"""Qt-free implementations of the `HistoryCommandContext` project-bound ports.

Each applier implements one port `Protocol` from `chappy.application.history.ports`
(and `chappy.application.history.resolution_commands` for the resolution port)
against a lazily resolved `SpectroscopyProject`. `RangeHistoryPort` is not
implemented here because it needs the GUI `SpectrumInteractionCoordinator`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from chappy.application.history.apply.parameter_targets import resolve_parameter_targets
from chappy.application.history.models import ChangeSet, HistoryApplyError, HistoryApplyErrorCode
from chappy.application.history.snapshot_mapping import (
    absorber_component_from_snapshot,
    absorption_line_from_snapshot,
    absorption_region_from_snapshot,
    mask_from_snapshot,
    model_link_sort_key,
    temporary_line_from_snapshot,
    tie_sets_from_snapshots,
)
from chappy.core.absorption.models import UNASSIGNED_REGION_ID
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.continuum import ContinuumComponent

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.application.history.ports import (
        AbsorberComponentGroupAssignment,
        AbsorberComponentSnapshot,
        AbsorptionLineSnapshot,
        AbsorptionRegionSnapshot,
        ComponentParameterState,
        ContinuumComponentSnapshot,
        ContinuumPointSnapshot,
        LineAnalysisHalfWidthStateSnapshot,
        LineOptimizationStateSnapshot,
        LineRegionAssignment,
        MaskDefinitionSnapshot,
        ModelComponentLinkSnapshot,
        MultipletLinkSnapshot,
        TieSetSnapshot,
    )
    from chappy.application.history.resolution_commands import ResolutionStateSnapshot
    from chappy.application.identify import TemporaryLineSnapshot
    from chappy.core.identify_state import IdentifySessionState
    from chappy.core.spectroscopy_project import SpectroscopyProject


class ProjectModelHistoryApplier:
    """`ModelHistoryPort` implementation bound to the current project."""

    def __init__(self, project_provider: Callable[[], SpectroscopyProject | None]) -> None:
        """Store the lazy project provider."""
        self._project_provider = project_provider

    @property
    def _project(self) -> SpectroscopyProject | None:
        """Return the currently connected project, if any."""
        return self._project_provider()

    def _require_project(self, action: str) -> SpectroscopyProject:
        """Return the current project or raise a typed history error."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"{HistoryApplyErrorCode.TARGET_NOT_FOUND}: "
                f"Cannot {action} without a connected project.",
            )
        return project

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
        project = self._project
        if not project or not project.model:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot restore model components without a connected project and model.",
            )

        changed_component_ids: list[str] = []
        changed_line_ids: set[str] = set()
        target_component_ids = {snapshot.component_id for snapshot in components}
        restored_components = {
            component.id: component
            for component in project.model.components
            if isinstance(component, AbsorberComponent)
        }

        for snapshot in components:
            component = project.find_absorber_component(snapshot.component_id)
            if component is not None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    f"Model component already exists during restore: {snapshot.component_id}",
                )
            component = absorber_component_from_snapshot(snapshot)
            project.model.add_component_storage(component)
            changed_component_ids.append(component.id)
            restored_components[component.id] = component

        ordered_components = [
            component
            for component in project.model.components
            if component.id not in target_component_ids
        ]
        for index, snapshot in sorted(
            zip(component_indices, components, strict=True), key=lambda item: item[0]
        ):
            ordered_components.insert(index, restored_components[snapshot.component_id])
        project.model.restore_component_order_for_transaction(tuple(ordered_components))

        for link in sorted(links, key=model_link_sort_key):
            line = project.absorption_lines.get(link.line_id)
            if line is None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Model component history line was removed: {link.line_id}",
                )
            if link.component_id in line.model_ids or link.index > len(line.model_ids):
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    f"Model component history link cannot be restored exactly: {link.line_id}",
                )
            line.model_ids.insert(link.index, link.component_id)
            changed_line_ids.add(link.line_id)

        if any(
            component_id not in restored_components
            for tie_set_snapshot in tie_sets
            for component_id in tie_set_snapshot.component_ids
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot restore model tie sets with missing components.",
            )
        tie_changes = self.restore_tie_sets(
            tie_sets, tie_set_indices=tie_set_indices, removed_uids=removed_tie_uids
        )
        changed_component_ids.extend(tie_changes.changed_component_ids)

        return ChangeSet(
            changed_component_ids=tuple(changed_component_ids),
            changed_line_ids=tuple(sorted(changed_line_ids)),
        )

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
        project = self._project
        if not project or not project.model:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot remove model components without a connected project and model.",
            )

        changed_component_ids: list[str] = []
        for component_id in component_ids:
            component = project.find_absorber_component(component_id)
            if component is None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Model component was removed before history apply: {component_id}",
                )
            project.model.remove_component_storage(component)
            changed_component_ids.append(component_id)

        changed_line_ids: set[str] = set()
        for link in links:
            line = project.absorption_lines.get(link.line_id)
            if line is None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Model component history line was removed: {link.line_id}",
                )
            if (
                link.component_id not in line.model_ids
                or line.model_ids.index(link.component_id) != link.index
            ):
                raise HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE,
                    f"Model component history link cannot be removed exactly: {link.line_id}",
                )
        for link in sorted(links, key=lambda item: (item.line_id, item.index), reverse=True):
            line = project.absorption_lines[link.line_id]
            line.model_ids.pop(link.index)
            changed_line_ids.add(link.line_id)

        tie_changes = self.restore_tie_sets(
            tie_sets, tie_set_indices=tie_set_indices, removed_uids=removed_tie_uids
        )
        changed_component_ids.extend(tie_changes.changed_component_ids)

        return ChangeSet(
            changed_component_ids=tuple(dict.fromkeys(changed_component_ids)),
            changed_line_ids=tuple(sorted(changed_line_ids)),
        )

    def restore_component_parameters(
        self, states: tuple[ComponentParameterState, ...]
    ) -> ChangeSet:
        """Restore exact component parameters after validating every shared target."""
        project = self._require_project("resolve model parameter history")
        component_ids = tuple(state.component_id for state in states)
        resolved = resolve_parameter_targets(project, component_ids, states)
        for item in resolved:
            target = item.target
            if target.min_value is None or target.max_value is None or target.error is None:
                msg = "Effective parameter history target is incomplete."
                raise RuntimeError(msg)
            item.parameter.min_val = target.min_value
            item.parameter.max_val = target.max_value
            item.parameter.set_value(target.value)
            item.parameter.fixed = not target.vary
            item.parameter.error = target.error
        return ChangeSet(changed_component_ids=component_ids)

    def restore_tie_sets(
        self,
        snapshots: tuple[TieSetSnapshot, ...],
        *,
        tie_set_indices: tuple[int, ...],
        removed_uids: tuple[str, ...],
    ) -> ChangeSet:
        """Restore parameter tie set membership and origin from typed snapshots.

        Any currently registered tie set whose uid appears in ``removed_uids``
        or matches a snapshot's ``uid`` is unbound and cleared first, then
        each snapshot is rebuilt. Components are never added or removed.
        """
        project = self._project
        if not project or not project.model:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot restore tie sets without a connected project and model.",
            )

        snapshot_uids = tuple(snapshot.uid for snapshot in snapshots)
        if len(set(snapshot_uids)) != len(snapshot_uids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Tie set history snapshots contain duplicate identities.",
            )
        component_ids = {
            component_id for snapshot in snapshots for component_id in snapshot.component_ids
        }
        restored_components = {
            component_id: found
            for component_id in component_ids
            if (found := project.find_absorber_component(component_id)) is not None
        }
        if len(restored_components) != len(component_ids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Tie set history component was removed before apply.",
            )

        stale_uids = set(snapshot_uids) | set(removed_uids)
        changed_component_ids: set[str] = set()
        current_tie_sets = tuple(project.model.iter_tie_sets())
        stale_tie_sets = [tie_set for tie_set in current_tie_sets if tie_set.uid in stale_uids]
        stale_current_uids = tuple(tie_set.uid for tie_set in stale_tie_sets)
        final_count = len(current_tie_sets) - len(stale_tie_sets) + len(snapshots)
        if (
            len(set(stale_current_uids)) != len(stale_current_uids)
            or len(tie_set_indices) != len(snapshots)
            or len(set(tie_set_indices)) != len(tie_set_indices)
            or any(index < 0 or index >= final_count for index in tie_set_indices)
        ):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Tie set history storage indices are inconsistent.",
            )
        for tie_set in stale_tie_sets:
            changed_component_ids.update(component.id for component in tie_set.components)
        for tie_set in stale_tie_sets:
            for nested_uid in tuple(tie_set.member_uids):
                nested = next(
                    (
                        candidate
                        for candidate in project.model.iter_tie_sets()
                        if candidate.uid == nested_uid and candidate.parent_tie is tie_set
                    ),
                    None,
                )
                if nested is not None:
                    tie_set.detach_tie_set(nested)
        for tie_set in stale_tie_sets:
            if tie_set.parent_tie is not None:
                tie_set.parent_tie.detach_tie_set(tie_set)
        for tie_set in stale_tie_sets:
            for component in [
                component for component in tie_set.components if component.tie_set is tie_set
            ]:
                tie_set.remove_component(component)
            project.model.remove_tie_set(tie_set)

        restored_tie_sets = tie_sets_from_snapshots(
            snapshots, restored_components, existing_tie_sets=tuple(project.model.iter_tie_sets())
        )
        ordered_tie_sets = list(project.model.iter_tie_sets())
        if len(restored_tie_sets) != len(snapshots):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Tie set history could not rebuild every declared snapshot.",
            )
        for index, restored_tie_set in sorted(
            zip(tie_set_indices, restored_tie_sets, strict=True), key=lambda item: item[0]
        ):
            ordered_tie_sets.insert(index, restored_tie_set)
            changed_component_ids.update(member.id for member in restored_tie_set.components)
        project.model.restore_tie_set_order_for_transaction(tuple(ordered_tie_sets))

        return ChangeSet(changed_component_ids=tuple(sorted(changed_component_ids)))

    def restore_line_optimization(
        self, states: tuple[LineOptimizationStateSnapshot, ...]
    ) -> ChangeSet:
        """Restore optimization-needed states for absorption lines."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot restore line optimization state without a connected project.",
            )

        changed_line_ids: list[str] = []
        for state in states:
            line = project.absorption_lines.get(state.line_id)
            if line is None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Line not found for optimization restore: {state.line_id}",
                )
            line.needs_optimization = state.needs_optimization
            changed_line_ids.append(state.line_id)

        return ChangeSet(changed_line_ids=tuple(changed_line_ids))

    def clear_region_needs_optimization(self, region_id: str) -> ChangeSet:
        """Clear optimization-needed states for a region."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot clear region optimization state without a connected project.",
            )
        project.clear_region_needs_optimization(region_id)
        region = project.absorption_regions.get(region_id)
        changed_line_ids = tuple(region.line_ids) if region is not None else ()
        return ChangeSet(changed_line_ids=changed_line_ids, changed_region_ids=(region_id,))

    def restore_line_analysis_half_width_states(
        self, states: tuple[LineAnalysisHalfWidthStateSnapshot, ...], *, region_id: str
    ) -> ChangeSet:
        """Restore Optimize analysis ranges while leaving the whole region stale."""
        project = self._require_project("restore line analysis half-width states")
        region = project.absorption_regions.get(region_id)
        if region is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Cannot restore analysis half-widths for missing region: {region_id}",
            )
        required_line_ids = tuple(
            dict.fromkeys((*(state.line_id for state in states), *region.line_ids))
        )
        missing_ids = [
            line_id for line_id in required_line_ids if line_id not in project.absorption_lines
        ]
        if missing_ids:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Cannot restore analysis half-widths for missing lines: {', '.join(missing_ids)}",
            )

        for state in states:
            line = project.absorption_lines[state.line_id]
            line.window_kms = state.half_width_kms
            line.lambda_range = state.lambda_range
        project.update_region_analysis_range(region_id)
        project.modified = datetime.now(UTC)
        return ChangeSet(
            changed_line_ids=tuple(state.line_id for state in states),
            changed_region_ids=(region_id,),
        )


class ProjectStructureHistoryApplier:
    """`StructureHistoryPort` implementation bound to the current project."""

    def __init__(self, project_provider: Callable[[], SpectroscopyProject | None]) -> None:
        """Store the lazy project provider."""
        self._project_provider = project_provider

    @property
    def _project(self) -> SpectroscopyProject | None:
        """Return the currently connected project, if any."""
        return self._project_provider()

    def _require_project(self, action: str) -> SpectroscopyProject:
        """Return the current project or raise a typed history error."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"{HistoryApplyErrorCode.TARGET_NOT_FOUND}: "
                f"Cannot {action} without a connected project.",
            )
        return project

    def restore_absorption_regions(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore absorption regions from typed snapshots."""
        project = self._require_project("restore absorption regions")
        changed_region_ids: list[str] = []
        for snapshot in snapshots:
            project.restore_absorption_region(absorption_region_from_snapshot(snapshot))
            changed_region_ids.append(snapshot.region_id)
        return ChangeSet(changed_region_ids=tuple(changed_region_ids))

    def apply_absorption_region_states_exact(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore exact current region fields and mapping order."""
        project = self._require_project("restore exact absorption region states")
        snapshot_ids = tuple(snapshot.region_id for snapshot in snapshots)
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Exact absorption region history contains duplicate identities.",
            )
        current_ids = set(project.absorption_regions)
        if set(snapshot_ids) != current_ids:
            missing = set(snapshot_ids) - current_ids
            code = (
                HistoryApplyErrorCode.TARGET_NOT_FOUND
                if missing
                else HistoryApplyErrorCode.INVALID_STATE
            )
            raise HistoryApplyError(
                code, "Exact absorption region history does not match current topology."
            )

        ordered_regions = []
        for snapshot in snapshots:
            region = project.absorption_regions[snapshot.region_id]
            region.line_ids[:] = snapshot.line_ids
            region.display_color = snapshot.display_color
            region.analysis_range = snapshot.analysis_range
            region.created_at = snapshot.created_at
            ordered_regions.append((snapshot.region_id, region))
        project.absorption_regions.clear()
        project.absorption_regions.update(ordered_regions)
        return ChangeSet(changed_region_ids=snapshot_ids)

    def apply_absorption_region_states_partial_exact(
        self, snapshots: tuple[AbsorptionRegionSnapshot, ...]
    ) -> ChangeSet:
        """Restore exact fields for one declared subset of current regions."""
        project = self._require_project("restore exact partial absorption region states")
        snapshot_ids = tuple(snapshot.region_id for snapshot in snapshots)
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Partial absorption region history contains duplicate identities.",
            )
        missing = set(snapshot_ids) - set(project.absorption_regions)
        if missing:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Partial absorption regions not found: {', '.join(sorted(missing))}",
            )
        for snapshot in snapshots:
            region = project.absorption_regions[snapshot.region_id]
            region.line_ids[:] = snapshot.line_ids
            region.display_color = snapshot.display_color
            region.analysis_range = snapshot.analysis_range
            region.created_at = snapshot.created_at
        return ChangeSet(changed_region_ids=snapshot_ids)

    def restore_absorption_lines(
        self, snapshots: tuple[AbsorptionLineSnapshot, ...], *, restore_multiplet_links: bool
    ) -> ChangeSet:
        """Restore absorption lines from typed snapshots."""
        project = self._require_project("restore absorption lines")
        changed_line_ids: list[str] = []
        changed_region_ids: set[str] = set()
        for snapshot in snapshots:
            project.restore_absorption_line(
                absorption_line_from_snapshot(snapshot),
                restore_multiplet_links=restore_multiplet_links,
            )
            changed_line_ids.append(snapshot.line_id)
            if snapshot.region_id is not None:
                changed_region_ids.add(snapshot.region_id)
        return ChangeSet(
            changed_line_ids=tuple(changed_line_ids),
            changed_region_ids=tuple(sorted(changed_region_ids)),
        )

    def apply_absorption_line_order_exact(self, line_ids: tuple[str, ...]) -> ChangeSet:
        """Restore exact current absorption-line mapping order."""
        project = self._require_project("restore exact absorption line order")
        if len(set(line_ids)) != len(line_ids) or set(line_ids) != set(project.absorption_lines):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Exact absorption line order does not match current topology.",
            )
        ordered = tuple((line_id, project.absorption_lines[line_id]) for line_id in line_ids)
        project.absorption_lines.clear()
        project.absorption_lines.update(ordered)
        return ChangeSet(changed_line_ids=line_ids)

    def restore_masks(self, snapshots: tuple[MaskDefinitionSnapshot, ...]) -> ChangeSet:
        """Restore wavelength masks from typed snapshots."""
        project = self._require_project("restore masks")
        changed_region_ids: set[str] = set()
        for snapshot in snapshots:
            mask = mask_from_snapshot(snapshot)
            project.model.update_mask_definition(mask)
            if snapshot.group_id is not None:
                changed_region_ids.add(snapshot.group_id)
        return ChangeSet(changed_region_ids=tuple(sorted(changed_region_ids)))

    def replace_masks_exact(self, snapshots: tuple[MaskDefinitionSnapshot, ...]) -> ChangeSet:
        """Replace the exact ordered mask collection without observer dispatch."""
        project = self._require_project("replace exact structure masks")
        masks = tuple(mask_from_snapshot(snapshot) for snapshot in snapshots)
        project.model.restore_mask_definitions_for_transaction(masks, model_was_valid=False)
        region_ids = tuple(
            dict.fromkeys(
                snapshot.group_id for snapshot in snapshots if snapshot.group_id is not None
            )
        )
        return ChangeSet(changed_region_ids=region_ids)

    def apply_absorber_component_groups(
        self, assignments: tuple[AbsorberComponentGroupAssignment, ...]
    ) -> ChangeSet:
        """Apply exact absorber component region associations."""
        project = self._require_project("apply absorber component groups")
        assignment_ids = tuple(assignment.component_id for assignment in assignments)
        if len(set(assignment_ids)) != len(assignment_ids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Absorber component group history contains duplicate identities.",
            )
        components = tuple(
            component
            for component in project.model.components
            if isinstance(component, AbsorberComponent)
        )
        components_by_id = {component.id: component for component in components}
        missing = set(assignment_ids) - set(components_by_id)
        if missing:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Absorber components not found for group history: {', '.join(sorted(missing))}",
            )
        if set(assignment_ids) != set(components_by_id):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Absorber component group history does not cover current components exactly.",
            )
        for assignment in assignments:
            components_by_id[assignment.component_id].set_group(assignment.group_id)
        return ChangeSet(changed_component_ids=assignment_ids)

    def restore_mask_state(
        self, mask_id: str, snapshot: MaskDefinitionSnapshot | None, *, index: int | None
    ) -> ChangeSet:
        """Restore or remove one mask state silently at its exact index.

        Region revision re-invalidation for successful Undo/Redo is owned by P1f.
        """
        project = self._require_project("restore mask state")
        mask = mask_from_snapshot(snapshot) if snapshot is not None else None
        project.model.restore_mask_definition_for_transaction(mask_id, mask, index=index)
        region_ids = (
            (snapshot.group_id,) if snapshot is not None and snapshot.group_id is not None else ()
        )
        return ChangeSet(changed_region_ids=region_ids)

    def ensure_absorption_region(self, region_id: str, *, color: str | None) -> ChangeSet:
        """Ensure an absorption region exists."""
        project = self._require_project("ensure absorption region")
        if region_id not in project.absorption_regions and region_id != UNASSIGNED_REGION_ID:
            project.create_absorption_region(region_id=region_id, color=color)
        return ChangeSet(changed_region_ids=(region_id,))

    def apply_line_region_assignments(
        self, assignments: tuple[LineRegionAssignment, ...]
    ) -> ChangeSet:
        """Assign lines to target regions."""
        project = self._require_project("apply line region assignments")
        changed_line_ids: list[str] = []
        changed_region_ids: set[str] = set()
        for assignment in assignments:
            line = project.absorption_lines.get(assignment.line_id)
            if line is None:
                raise HistoryApplyError(
                    HistoryApplyErrorCode.TARGET_NOT_FOUND,
                    f"Line not found for region assignment: {assignment.line_id}",
                )
            if line.region_id is not None:
                changed_region_ids.add(line.region_id)
            project.assign_line_to_region(assignment.line_id, assignment.region_id)
            changed_line_ids.append(assignment.line_id)
            if assignment.region_id is not None:
                changed_region_ids.add(assignment.region_id)
        return ChangeSet(
            changed_line_ids=tuple(changed_line_ids),
            changed_region_ids=tuple(sorted(changed_region_ids)),
        )

    def remove_empty_absorption_region(self, region_id: str) -> ChangeSet:
        """Remove a region if it has no lines."""
        project = self._require_project("remove empty absorption region")
        region = project.absorption_regions.get(region_id)
        if region is not None and not region.line_ids:
            project.remove_absorption_region(region_id, delete_models=False)
            return ChangeSet(changed_region_ids=(region_id,))
        return ChangeSet.empty()

    def remove_absorption_lines(
        self, line_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        """Remove absorption lines by ID."""
        project = self._require_project("remove absorption lines")
        changed_region_ids: set[str] = set()
        removed_line_ids: list[str] = []
        for line_id in line_ids:
            line = project.absorption_lines.get(line_id)
            if line is None:
                continue
            if line.region_id is not None:
                changed_region_ids.add(line.region_id)
            if project.remove_absorption_line(line_id, delete_models=delete_models):
                removed_line_ids.append(line_id)
        return ChangeSet(
            changed_line_ids=tuple(removed_line_ids),
            changed_region_ids=tuple(sorted(changed_region_ids)),
        )

    def remove_absorption_regions(
        self, region_ids: tuple[str, ...], *, delete_models: bool
    ) -> ChangeSet:
        """Remove absorption regions by ID."""
        project = self._require_project("remove absorption regions")
        changed_region_ids: list[str] = []
        changed_line_ids: list[str] = []
        for region_id in region_ids:
            region = project.absorption_regions.get(region_id)
            if region is None:
                continue
            changed_line_ids.extend(region.line_ids)
            removed = project.remove_absorption_region(region_id, delete_models=delete_models)
            if removed:
                changed_region_ids.append(region_id)
        return ChangeSet(
            changed_line_ids=tuple(changed_line_ids), changed_region_ids=tuple(changed_region_ids)
        )

    def restore_multiplet_links(self, snapshots: tuple[MultipletLinkSnapshot, ...]) -> ChangeSet:
        """Restore multiplet cross-links."""
        project = self._require_project("restore multiplet links")
        changed_line_ids: set[str] = set()
        for snapshot in snapshots:
            line = project.absorption_lines.get(snapshot.line_id)
            if line is None:
                continue
            for related_id in snapshot.related_line_ids:
                if related_id not in line.multiplet_ids:
                    line.multiplet_ids.append(related_id)
                related = project.absorption_lines.get(related_id)
                if related is not None and snapshot.line_id not in related.multiplet_ids:
                    related.multiplet_ids.append(snapshot.line_id)
                    changed_line_ids.add(related_id)
            changed_line_ids.add(snapshot.line_id)
        return ChangeSet(changed_line_ids=tuple(sorted(changed_line_ids)))

    def apply_multiplet_links_exact(
        self, line_ids: tuple[str, ...], snapshots: tuple[MultipletLinkSnapshot, ...]
    ) -> ChangeSet:
        """Replace exact ordered multiplet links for one closed line set."""
        project = self._require_project("apply exact multiplet links")
        snapshot_ids = tuple(snapshot.line_id for snapshot in snapshots)
        if snapshot_ids != line_ids or len(set(line_ids)) != len(line_ids):
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                "Exact multiplet link snapshots do not cover unique command lines.",
            )
        missing = tuple(line_id for line_id in line_ids if line_id not in project.absorption_lines)
        if missing:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Multiplet link lines not found: {', '.join(missing)}",
            )
        for snapshot in snapshots:
            project.absorption_lines[snapshot.line_id].multiplet_ids[:] = snapshot.related_line_ids
        region_ids = tuple(
            dict.fromkeys(
                project.absorption_lines[line_id].region_id or UNASSIGNED_REGION_ID
                for line_id in line_ids
            )
        )
        return ChangeSet(changed_line_ids=line_ids, changed_region_ids=region_ids)


class ProjectIdentifyHistoryApplier:
    """`IdentifyHistoryPort` implementation bound to the current project."""

    def __init__(self, project_provider: Callable[[], SpectroscopyProject | None]) -> None:
        """Store the lazy project provider."""
        self._project_provider = project_provider

    @property
    def _project(self) -> SpectroscopyProject | None:
        """Return the currently connected project, if any."""
        return self._project_provider()

    def _require_project(self, action: str) -> SpectroscopyProject:
        """Return the current project or raise a typed history error."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"{HistoryApplyErrorCode.TARGET_NOT_FOUND}: "
                f"Cannot {action} without a connected project.",
            )
        return project

    def _get_identify_session(self) -> IdentifySessionState | None:
        """Get current identify session from project.

        Returns:
            IdentifySessionState if available, None otherwise.
        """
        if not self._project:
            return None
        return self._project.identify_state

    def _require_identify_session(self, action: str) -> IdentifySessionState:
        """Return the current identify session or raise a typed history error."""
        session = self._get_identify_session()
        if session is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Cannot {action} without a connected identify session.",
            )
        return session

    def restore_identify_temporary_lines(
        self, snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> ChangeSet:
        """Restore identify temporary lines from typed snapshots."""
        session = self._require_identify_session("restore identify temporary lines")
        restored_ids: list[str] = []
        for snapshot in snapshots:
            temporary_line = session.restore_temporary_line(temporary_line_from_snapshot(snapshot))
            restored_ids.append(temporary_line.temporary_line_id)
        return ChangeSet(changed_temporary_line_ids=tuple(restored_ids))

    def remove_identify_temporary_lines(self, temporary_line_ids: tuple[str, ...]) -> ChangeSet:
        """Remove identify temporary lines by line ID."""
        session = self._require_identify_session("remove identify temporary lines")
        removed_ids = session.remove_temporary_lines(temporary_line_ids)
        return ChangeSet(changed_temporary_line_ids=tuple(removed_ids))

    def clear_identify_temporary_lines(self) -> ChangeSet:
        """Clear all identify temporary lines."""
        session = self._require_identify_session("clear identify temporary lines")
        cleared_ids = tuple(
            temporary_line.temporary_line_id for temporary_line in session.temporary_lines
        )
        session.clear_temporary_lines()
        return ChangeSet(changed_temporary_line_ids=cleared_ids)

    def update_identify_region_analysis_ranges(self, region_ids: tuple[str, ...]) -> ChangeSet:
        """Update analysis ranges for identify-affected regions."""
        project = self._require_project("update identify region analysis ranges")
        changed_region_ids: list[str] = []
        for region_id in region_ids:
            project.update_region_analysis_range(region_id)
            changed_region_ids.append(region_id)
        return ChangeSet(changed_region_ids=tuple(changed_region_ids))


class ProjectContinuumHistoryApplier:
    """`ContinuumHistoryPort` implementation bound to the current project."""

    def __init__(self, project_provider: Callable[[], SpectroscopyProject | None]) -> None:
        """Store the lazy project provider."""
        self._project_provider = project_provider

    @property
    def _project(self) -> SpectroscopyProject | None:
        """Return the currently connected project, if any."""
        return self._project_provider()

    def _require_project(self, action: str) -> SpectroscopyProject:
        """Return the current project or raise a typed history error."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"{HistoryApplyErrorCode.TARGET_NOT_FOUND}: "
                f"Cannot {action} without a connected project.",
            )
        return project

    def add_continuum_component(
        self, snapshot: ContinuumComponentSnapshot, *, index: int
    ) -> ChangeSet:
        """Recreate one continuum component from a history snapshot."""
        project = self._require_project("add a continuum component")
        if project.model.get_component_by_id(snapshot.component_id) is not None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE,
                f"Continuum component already exists: {snapshot.component_id}",
            )
        continuum = ContinuumComponent(name=snapshot.name)
        continuum.id = snapshot.component_id
        continuum.enabled = snapshot.enabled
        continuum.is_shared_with_absorption = snapshot.is_shared_with_absorption
        continuum.continuum_points = [point.as_position() for point in snapshot.points]
        project.model.add_component_storage(continuum)
        ordered_components = [
            component for component in project.model.components if component is not continuum
        ]
        ordered_components.insert(index, continuum)
        project.model.restore_component_order_for_transaction(tuple(ordered_components))
        return ChangeSet(changed_continuum_ids=(snapshot.component_id,))

    def remove_continuum_component(self, continuum_id: str) -> ChangeSet:
        """Remove one continuum component through the history application API."""
        project = self._require_project("remove a continuum component")
        component = project.model.get_component_by_id(continuum_id)
        if not isinstance(component, ContinuumComponent):
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND, f"Continuum not found: {continuum_id}"
            )
        project.model.remove_component_storage(component)
        return ChangeSet(changed_continuum_ids=(continuum_id,))

    def replace_continuum_points(
        self, continuum_id: str, points: tuple[ContinuumPointSnapshot, ...]
    ) -> ChangeSet:
        """Replace all continuum points through the current editor.

        Args:
            continuum_id: Target continuum identifier.
            points: Replacement point snapshots.

        Returns:
            Changed continuum identifier.
        """
        continuum = self.require_continuum(continuum_id)
        continuum.continuum_points = [point.as_position() for point in points]
        return ChangeSet(changed_continuum_ids=(continuum_id,))

    def require_continuum(self, continuum_id: str) -> ContinuumComponent:
        """Resolve a continuum canonically from the current project model."""
        project = self._require_project("resolve a continuum component")
        component = project.model.get_component_by_id(continuum_id)
        if not isinstance(component, ContinuumComponent):
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Continuum not found in current project: {continuum_id}",
            )
        return component


class ProjectResolutionHistoryApplier:
    """`ResolutionHistoryPort` implementation bound to the current project."""

    def __init__(self, project_provider: Callable[[], SpectroscopyProject | None]) -> None:
        """Store the lazy project provider."""
        self._project_provider = project_provider

    @property
    def _project(self) -> SpectroscopyProject | None:
        """Return the currently connected project, if any."""
        return self._project_provider()

    def _require_project(self, action: str) -> SpectroscopyProject:
        """Return the current project or raise a typed history error."""
        project = self._project
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"{HistoryApplyErrorCode.TARGET_NOT_FOUND}: "
                f"Cannot {action} without a connected project.",
            )
        return project

    def apply_resolution_state(self, snapshot: ResolutionStateSnapshot) -> ChangeSet:
        """Apply one exact spectral-resolution state through the current project."""
        project = self._require_project("apply spectral resolution state")
        project.set_resolution(snapshot.value, snapshot.enabled)
        return ChangeSet.empty()
