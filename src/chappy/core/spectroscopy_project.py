"""Project management for the Chappy spectroscopy application."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from .absorption.multiplet_service import expand_multiplet_lines
from .absorption.registry import AbsorptionRegistry
from .analysis import AnalysisRevision, RegionAnalysisState
from .components.absorber import AbsorberComponent
from .components.continuum import ContinuumComponent
from .identify_state import IdentifySessionState
from .optimizer_settings import (
    DEFAULT_AUTO_CONTINUE,
    DEFAULT_MAX_FUNCTION_EVALUATIONS,
    DEFAULT_TOLERANCE,
    OptimizerSettingsState,
)
from .resolution import RESOLUTION_CONSTRAINTS, ResolutionState
from .spectrum_model import SpectrumModel

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


class SpectroscopyProject:
    """Main project class for the Chappy spectroscopy application.

    Manages the complete project state including:
    - Observed spectrum data
    - Model components and parameters
    - Project metadata and settings
    - File I/O operations

    Ported from the Java DProject class.
    """

    def __init__(
        self, name: str = "Untitled Project", spectrum_filename: str | None = None
    ) -> None:
        """Initialize a new project.

        Args:
            name: Project name
            spectrum_filename: Path to spectrum FITS file
        """
        self.name = name
        self.spectrum_filename = spectrum_filename

        # Timestamps
        self.created = datetime.now(UTC)
        self.modified = datetime.now(UTC)

        # Core model
        self.model = SpectrumModel()

        # Instrumental resolution configuration (defaults to disabled)
        default_resolution = float(RESOLUTION_CONSTRAINTS["default"])
        self._resolution_state = ResolutionState(value=default_resolution, enabled=False)
        self.model.set_resolution_state(self._resolution_state)

        # Optimizer convergence settings, overridden per region; absent → defaults
        self._region_optimizer_settings: dict[str, OptimizerSettingsState] = {}

        # Project metadata
        self.metadata: dict[str, Any] = {
            "version": "2.0",
            "created_by": "chappy",
            "description": "",
            "author": "",
            "notes": "",
        }

        # Settings
        self.settings: dict[str, Any] = {
            "display_units": "angstrom",
            "velocity_reference": None,
            "default_error_level": 0.01,
        }

        # Identify-mode absorption entities
        self._absorption = AbsorptionRegistry()

        # Region-scoped analysis evidence and input revisions.
        self._region_analysis_states: dict[str, RegionAnalysisState] = {}

        # Identify mode session state (temporary lines, velocity window, etc.)
        self.identify_state: IdentifySessionState = IdentifySessionState()

    def mark_scientific_modified(self) -> None:
        """Record a committed scientific storage mutation."""
        self.modified = datetime.now(UTC)

    @property
    def resolution_state(self) -> ResolutionState:
        """Return the current instrumental resolution state."""
        return self._resolution_state

    def region_optimizer_settings(self, region_id: str) -> OptimizerSettingsState:
        """Return the optimizer convergence settings for one region.

        Falls back to defaults when the region has no explicit override.
        """
        return self._region_optimizer_settings.get(
            region_id,
            OptimizerSettingsState(
                max_function_evaluations=DEFAULT_MAX_FUNCTION_EVALUATIONS,
                tolerance=DEFAULT_TOLERANCE,
            ),
        )

    def region_optimizer_settings_overrides(self) -> dict[str, OptimizerSettingsState]:
        """Return regions with explicit optimizer settings overrides only."""
        return dict(self._region_optimizer_settings)

    @property
    def absorption_lines(self) -> dict[str, AbsorptionLine]:
        """Return the live absorption lines mapping."""
        return self._absorption.lines

    @absorption_lines.setter
    def absorption_lines(self, value: dict[str, AbsorptionLine]) -> None:
        """Replace the absorption lines mapping wholesale."""
        self._absorption.lines = value

    @property
    def absorption_regions(self) -> dict[str, AbsorptionRegion]:
        """Return the live absorption regions mapping."""
        return self._absorption.regions

    @absorption_regions.setter
    def absorption_regions(self, value: dict[str, AbsorptionRegion]) -> None:
        """Replace the absorption regions mapping wholesale."""
        self._absorption.regions = value
        self._region_analysis_states = {}
        self._region_optimizer_settings = {}

    def load_absorption_state(
        self, *, regions: dict[str, AbsorptionRegion], lines: dict[str, AbsorptionLine]
    ) -> None:
        """Replace all absorption regions and lines from restored document state."""
        self._absorption.regions = regions
        self._absorption.lines = lines
        self._region_analysis_states = {}
        self._region_optimizer_settings = {}

    def region_analysis_state(self, region_id: str) -> RegionAnalysisState | None:
        """Return the project-owned analysis state for an existing region."""
        if region_id not in self.absorption_regions:
            return None
        return self._region_analysis_states.get(
            region_id,
            RegionAnalysisState(region_id=region_id, current_revision=AnalysisRevision()),
        )

    def region_analysis_states(self) -> tuple[RegionAnalysisState, ...]:
        """Return analysis state for every current region in stable order."""
        return tuple(
            state
            for region_id in sorted(self.absorption_regions)
            if (state := self.region_analysis_state(region_id)) is not None
        )

    def set_region_analysis_state(self, state: RegionAnalysisState) -> None:
        """Replace one existing region's analysis state."""
        self.set_region_analysis_states((state,))

    def set_region_analysis_states(self, states: Iterable[RegionAnalysisState]) -> None:
        """Atomically replace analysis state for multiple existing regions."""
        replacements: dict[str, RegionAnalysisState] = {}
        for state in states:
            if state.region_id not in self.absorption_regions:
                msg = f"Absorption region not found: {state.region_id}"
                raise ValueError(msg)
            if state.region_id in replacements:
                msg = f"Duplicate analysis state for region: {state.region_id}"
                raise ValueError(msg)
            replacements[state.region_id] = state
        if all(
            self.region_analysis_state(region_id) == state
            for region_id, state in replacements.items()
        ):
            return
        updated = dict(self._region_analysis_states)
        updated.update(replacements)
        self._region_analysis_states = updated
        self.modified = datetime.now(UTC)

    def stored_region_analysis_states_for_transaction(self) -> tuple[RegionAnalysisState, ...]:
        """Return explicitly stored analysis states in their exact insertion order."""
        return tuple(self._region_analysis_states.values())

    def replace_region_analysis_states_for_transaction(
        self, states: Iterable[RegionAnalysisState]
    ) -> None:
        """Replace exact stored analysis states without changing modified time."""
        replacements: dict[str, RegionAnalysisState] = {}
        for state in states:
            if state.region_id not in self.absorption_regions:
                msg = f"Analysis state references missing region: {state.region_id}"
                raise ValueError(msg)
            if state.region_id in replacements:
                msg = f"Duplicate analysis state for region: {state.region_id}"
                raise ValueError(msg)
            replacements[state.region_id] = state
        self._region_analysis_states = replacements

    def prune_region_analysis_states_for_transaction(self) -> None:
        """Remove stored analysis states for regions deleted inside a transaction."""
        self._region_analysis_states = {
            region_id: state
            for region_id, state in self._region_analysis_states.items()
            if region_id in self.absorption_regions
        }

    def reset_region_analysis_states_for_transaction(self, region_ids: Iterable[str]) -> None:
        """Reset current regions to implicit revision-zero state inside a transaction."""
        requested = tuple(dict.fromkeys(region_ids))
        missing = [
            region_id for region_id in requested if region_id not in self.absorption_regions
        ]
        if missing:
            msg = f"Analysis regions not found for reset: {', '.join(missing)}"
            raise ValueError(msg)
        for region_id in requested:
            self._region_analysis_states.pop(region_id, None)

    def remove_region_analysis_state(self, region_id: str) -> None:
        """Remove persisted analysis state for one region if present."""
        if self._region_analysis_states.pop(region_id, None) is not None:
            self.modified = datetime.now(UTC)

    def load_region_analysis_states(self, states: Iterable[RegionAnalysisState]) -> None:
        """Replace analysis state from a validated project document."""
        restored: dict[str, RegionAnalysisState] = {}
        for state in states:
            if state.region_id not in self.absorption_regions:
                msg = f"Analysis state references missing region: {state.region_id}"
                raise ValueError(msg)
            if state.region_id in restored:
                msg = f"Duplicate analysis state for region: {state.region_id}"
                raise ValueError(msg)
            restored[state.region_id] = state
        self._region_analysis_states = restored

    def is_region_analysis_capable(self, region_id: str) -> bool:
        """Return whether a region has a complete non-empty line assignment."""
        region = self.absorption_regions.get(region_id)
        if region is None or not region.line_ids:
            return False
        return all(
            (line := self.absorption_lines.get(line_id)) is not None
            and line.region_id == region_id
            for line_id in region.line_ids
        )

    def region_requires_reanalysis(self, region_id: str) -> bool:
        """Return whether any line in a region requires another analysis."""
        return self.is_region_needs_optimization(region_id)

    def set_resolution(self, value: float, enabled: bool) -> None:
        """Update instrumental resolution settings for the project."""
        new_state = ResolutionState(value=float(value), enabled=enabled)
        if self._resolution_state == new_state:
            return
        self._resolution_state = new_state
        self.model.set_resolution_state(new_state)
        # Trigger immediate recomputation so dependent views refresh
        self.model.update_model()

    def set_region_optimizer_settings(
        self,
        region_id: str,
        max_function_evaluations: int,
        tolerance: float,
        auto_continue: bool = DEFAULT_AUTO_CONTINUE,
    ) -> None:
        """Update the optimizer convergence settings for one region."""
        self._region_optimizer_settings[region_id] = OptimizerSettingsState(
            max_function_evaluations=max_function_evaluations,
            tolerance=tolerance,
            auto_continue=auto_continue,
        )

    def remove_absorber_component(self, component: AbsorberComponent) -> bool:
        """Remove an absorber component and tidy group membership."""
        if component not in self.model.components:
            msg = f"Absorber component not found: {component.id}"
            raise ValueError(msg)
        self.model.remove_component(component)

        return True

    def remove_absorber_component_by_id(self, component_id: str) -> bool:
        """Remove absorber component identified by ``component_id``."""
        component = self.require_absorber_component(component_id)
        return self.remove_absorber_component(component)

    def find_absorber_component(self, component_id: str) -> AbsorberComponent | None:
        """Return matching absorber component if present."""
        if not component_id:
            return None

        if self.model is not None:
            component = self.model.get_absorber_component_by_id(component_id)
            if component is not None:
                return component

        for component in self._iter_absorber_components():
            if component.id == component_id:
                return component
        return None

    def require_absorber_component(self, component_id: str) -> AbsorberComponent:
        """Return a required absorber component or raise.

        Args:
            component_id: Absorber component identifier.

        Returns:
            Matching absorber component.

        Raises:
            ValueError: If the component is missing.
        """
        component = self.find_absorber_component(component_id)
        if component is None:
            msg = f"Absorber component not found: {component_id}"
            raise ValueError(msg)
        return component

    def _iter_absorber_components(self) -> Iterable[AbsorberComponent]:
        return (
            component
            for component in self.model.components
            if isinstance(component, AbsorberComponent)
        )

    def list_absorption_lines(self) -> list[AbsorptionLine]:
        """Return current absorption lines."""
        return self._absorption.list_lines()

    def list_absorption_regions(self) -> list[AbsorptionRegion]:
        """Return absorption regions."""
        return self._absorption.list_regions()

    def ensure_absorption_unassigned_region(self) -> AbsorptionRegion:
        """Ensure the logical unassigned region exists and return it."""
        return self._absorption.ensure_unassigned_region()

    def create_absorption_region(
        self, region_id: str | None = None, *, color: str | None = None
    ) -> AbsorptionRegion:
        """Create a new absorption region with optional colour.

        Args:
            region_id: Optional region identifier. If None, a new UUID is generated.
            color: Optional display color. If None, a color is allocated automatically.

        Note:
            Prefer ``create_region_with_lines`` for application code to ensure
            the region invariant (non-UNASSIGNED regions always have lines).
            This method is retained for internal use and migration scenarios.
        """
        return self._absorption.create_region(region_id, color=color)

    def create_region_with_lines(
        self, line_ids: Sequence[str], color: str | None = None
    ) -> AbsorptionRegion:
        """Create a new region and assign lines atomically.

        Args:
            line_ids: Non-empty sequence of absorption line identifiers to assign.
            color: Optional display colour for the region.

        Returns:
            The newly created AbsorptionRegion with all lines assigned.

        Raises:
            ValueError: If line_ids is empty.
        """
        if not line_ids:
            msg = "Cannot create region without lines"
            raise ValueError(msg)

        region = self.create_absorption_region(color=color)
        for line_id in line_ids:
            self.assign_line_to_region(line_id, region.region_id)
        return region

    def find_absorption_region(self, region_id: str) -> AbsorptionRegion | None:
        """Return matching absorption region if present."""
        return self._absorption.find_region(region_id)

    def require_absorption_region(self, region_id: str) -> AbsorptionRegion:
        """Return a required absorption region or raise.

        Args:
            region_id: Absorption region identifier.

        Returns:
            Matching absorption region.

        Raises:
            ValueError: If the region is missing.
        """
        return self._absorption.require_region(region_id)

    def find_absorption_line(self, line_id: str) -> AbsorptionLine | None:
        """Return matching absorption line if present."""
        return self._absorption.find_line(line_id)

    def require_absorption_line(self, line_id: str) -> AbsorptionLine:
        """Return a required absorption line or raise.

        Args:
            line_id: Absorption line identifier.

        Returns:
            Matching absorption line.

        Raises:
            ValueError: If the line is missing.
        """
        return self._absorption.require_line(line_id)

    def find_lines_for_region(self, region_id: str) -> list[AbsorptionLine] | None:
        """Return region lines when the region exists, otherwise None."""
        return self._absorption.find_lines_for_region(region_id)

    def region_model_ids(self, region_id: str) -> tuple[str, ...]:
        """Return unique component IDs referenced by a region in stable order."""
        return self._absorption.region_model_ids(region_id)

    def is_region_needs_optimization(self, region_id: str) -> bool:
        """Return whether any absorption line in the region needs optimization.

        Args:
            region_id: Region identifier.

        Returns:
            True when at least one line in the region has ``needs_optimization`` set.
        """
        return self._absorption.is_region_needs_optimization(region_id)

    def mark_region_needs_optimization(self, region_id: str) -> int:
        """Mark every absorption line in a region as needing optimization.

        Args:
            region_id: Region identifier.

        Returns:
            Number of lines whose flag was changed.
        """
        updated = self._absorption.set_region_needs_optimization(
            region_id, needs_optimization=True
        )
        if updated:
            self.modified = datetime.now(UTC)
        return updated

    def clear_region_needs_optimization(self, region_id: str) -> int:
        """Clear the optimization-needed flag for every line in a region.

        Args:
            region_id: Region identifier.

        Returns:
            Number of lines whose flag was changed.
        """
        updated = self._absorption.set_region_needs_optimization(
            region_id, needs_optimization=False
        )
        if updated:
            self.modified = datetime.now(UTC)
        return updated

    def add_absorption_line(  # noqa: PLR0913 - data model requires explicit fields
        self,
        *,
        species: str,
        rest_wavelength: float,
        center_z: float,
        window_kms: float,
        multiplet_label: str,
        transition_name: str,
        oscillator_strength: float,
        gamma_value: float,
        lambda_range: tuple[float, float] | None,
        region_id: str | None = None,
        multiplet_ids: Sequence[str] | None = None,
        created_by: str = "identify",
    ) -> AbsorptionLine:
        """Register an absorption line derived from identify mode.

        Args:
            species: Element/ion species (e.g., "C IV").
            rest_wavelength: Rest-frame wavelength in Angstroms.
            center_z: Central redshift.
            window_kms: Velocity window in km/s.
            multiplet_label: Display label from atomic database (for reproducibility).
            transition_name: Transition name from atomic database.
            oscillator_strength: Oscillator strength (f-value) from atomic database.
            gamma_value: Damping constant from atomic database.
            lambda_range: Optional observed wavelength range.
            region_id: Optional region to assign the line to.
            multiplet_ids: Optional list of related line IDs.
            created_by: Creation source identifier.

        Returns:
            The newly created AbsorptionLine.
        """
        return self._absorption.add_line(
            species=species,
            rest_wavelength=rest_wavelength,
            center_z=center_z,
            window_kms=window_kms,
            multiplet_label=multiplet_label,
            transition_name=transition_name,
            oscillator_strength=oscillator_strength,
            gamma_value=gamma_value,
            lambda_range=lambda_range,
            region_id=region_id,
            multiplet_ids=multiplet_ids,
            created_by=created_by,
        )

    def update_region_analysis_range(self, region_id: str) -> None:
        """Update the analysis range for an absorption region.

        Calculates the union of wavelength ranges from all absorption lines
        in the region.

        Args:
            region_id: ID of the region to update
        """
        self._absorption.update_region_analysis_range(region_id)

    def assign_line_to_region(self, line_id: str, region_id: str | None) -> None:
        """Move a line into the specified absorption region."""
        result = self._absorption.assign_line_to_region(line_id, region_id)
        if result.vacated_region_needs_deletion and result.vacated_region_id:
            self._delete_region_with_model_cleanup(result.vacated_region_id)

    def assign_line_models_to_region(self, line: AbsorptionLine) -> None:
        """Assign absorber components linked to ``line`` into its region."""
        if not line.model_ids:
            return

        region_id = line.region_id or UNASSIGNED_REGION_ID
        target_region = self.absorption_regions.get(region_id)
        if target_region is None:
            if region_id == UNASSIGNED_REGION_ID:
                target_region = self.ensure_absorption_unassigned_region()
            else:
                # Create region with specific region_id (for legacy/migration scenarios)
                target_region = self.create_absorption_region(region_id)

        for model_id in line.model_ids:
            component = self.require_absorber_component(model_id)
            component.set_group(target_region.region_id)

    def move_absorption_lines(
        self, line_ids: Sequence[str], *, target_region_id: str | None
    ) -> str | None:
        """Move absorption lines into the specified region.

        Args:
            line_ids: Sequence of absorption line identifiers to move.
            target_region_id: Destination region identifier. ``None`` creates a new region.

        Returns:
            The identifier of the destination region, or ``None`` if nothing moved.
        """
        result = self._absorption.move_lines(line_ids, target_region_id=target_region_id)
        if result.destination_region_id is None:
            return None

        for line in result.moved_lines:
            self.assign_line_to_region(line.line_id, result.destination_region_id)
            self.assign_line_models_to_region(line)

        return result.destination_region_id

    def expand_multiplet_line_ids(self, seed_ids: Sequence[str]) -> list[str]:
        """Expand seed line IDs to include all multiplet companions.

        Args:
            seed_ids: Initial line IDs to expand.

        Returns:
            Sorted list of expanded line IDs including multiplet companions.
        """
        return self._absorption.expand_multiplet_line_ids(seed_ids)

    def unlink_linked_lines(self, line_id: str) -> tuple[str, ...]:
        """Remove one materialized linked-line group without changing its declaration.

        The selected line and every transitively connected multiplet companion become
        independent lines. Scientific invalidation and history are application-layer
        responsibilities; this method only applies the validated domain topology change.
        """
        line = self.require_absorption_line(line_id)
        if not line.multiplet_ids:
            return ()

        expanded_line_ids = tuple(self.expand_multiplet_line_ids([line_id]))
        expanded_set = set(expanded_line_ids)
        if len(expanded_line_ids) < 2:
            msg = f"Linked lines have no existing companion: {line_id}"
            raise ValueError(msg)
        for member_id in expanded_line_ids:
            member = self.require_absorption_line(member_id)
            if member_id in member.multiplet_ids:
                msg = f"Linked lines contain a self-reference: {member_id}"
                raise ValueError(msg)
            missing_ids = tuple(
                related_id
                for related_id in member.multiplet_ids
                if related_id not in self.absorption_lines
            )
            if missing_ids:
                msg = (
                    f"Linked lines reference missing lines from {member_id}: "
                    f"{', '.join(missing_ids)}"
                )
                raise ValueError(msg)
            asymmetric_ids = tuple(
                related_id
                for related_id in member.multiplet_ids
                if member_id not in self.absorption_lines[related_id].multiplet_ids
            )
            if asymmetric_ids:
                msg = (
                    f"Linked lines are not symmetric for {member_id}: {', '.join(asymmetric_ids)}"
                )
                raise ValueError(msg)
            if any(related_id not in expanded_set for related_id in member.multiplet_ids):
                msg = f"Linked-line expansion is incomplete for {member_id}"
                raise ValueError(msg)

        unexpected_incoming = tuple(
            other_id
            for other_id, other in self.absorption_lines.items()
            if other_id not in expanded_set and expanded_set.intersection(other.multiplet_ids)
        )
        if unexpected_incoming:
            msg = (
                "Linked lines have asymmetric incoming references: "
                f"{', '.join(unexpected_incoming)}"
            )
            raise ValueError(msg)

        for member_id in expanded_line_ids:
            self.absorption_lines[member_id].multiplet_ids.clear()
        return expanded_line_ids

    def restore_absorption_line(
        self, line: AbsorptionLine, *, restore_multiplet_links: bool = True
    ) -> AbsorptionLine | None:
        """Restore an absorption line from a typed core object.

        Args:
            line: Absorption line to restore.
            restore_multiplet_links: If True, restore bidirectional multiplet links.

        Returns:
            Restored AbsorptionLine.
        """
        return self._absorption.restore_line(line, restore_multiplet_links=restore_multiplet_links)

    def restore_absorption_region(self, region: AbsorptionRegion) -> AbsorptionRegion | None:
        """Restore an absorption region from a typed core object.

        Note: This only restores the region structure, not the lines.
        Lines should be restored separately with restore_absorption_line.

        Args:
            region: Absorption region to restore.

        Returns:
            Restored AbsorptionRegion.
        """
        return self._absorption.restore_region(region)

    def remove_absorption_line(self, line_id: str, *, delete_models: bool = True) -> bool:
        """Remove an absorption line and associated data."""
        line = self._absorption.pop_line(line_id)

        if delete_models:
            for model_id in list(line.model_ids):
                self.remove_absorber_component_by_id(model_id)

        self._absorption.clear_multiplet_references(line_id)

        region_id = line.region_id or UNASSIGNED_REGION_ID
        if self._absorption.find_region(region_id) is not None:
            result = self._absorption.finalize_region_after_line_removal(region_id)
            if result.needs_deletion:
                self._delete_region_with_model_cleanup(result.region_id)

        return True

    def remove_absorption_lines_with_multiplet(
        self, line_ids: Sequence[str], *, delete_models: bool = True
    ) -> int:
        """Remove absorption lines and all related multiplet lines.

        Expands the selection to find all lines in the same multiplet group
        and removes them all together (ADR: multiplet-display-consolidation).

        Args:
            line_ids: Line IDs to remove (will be expanded to include multiplet members).
            delete_models: Whether to delete associated absorber components.

        Returns:
            Number of lines actually removed.
        """
        if not line_ids:
            return 0

        missing_ids = [line_id for line_id in line_ids if line_id not in self.absorption_lines]
        if missing_ids:
            msg = f"Absorption lines not found: {', '.join(map(str, missing_ids))}"
            raise ValueError(msg)

        expanded_ids = expand_multiplet_lines(self.absorption_lines, line_ids)
        if not expanded_ids:
            msg = f"Absorption lines not found: {', '.join(map(str, line_ids))}"
            raise ValueError(msg)
        removed = 0
        for line_id in expanded_ids:
            if self.remove_absorption_line(line_id, delete_models=delete_models):
                removed += 1
        return removed

    def remove_absorption_region(self, region_id: str, *, delete_models: bool = True) -> int:
        """Remove an absorption region and optionally its lines' models.

        Returns the number of lines removed.
        """
        if region_id == UNASSIGNED_REGION_ID:
            return 0

        region = self.require_absorption_region(region_id)

        removed = 0
        for line_id in list(region.line_ids):
            if self.remove_absorption_line(line_id, delete_models=delete_models):
                removed += 1

        self._delete_region_with_model_cleanup(region_id)
        return removed

    def _delete_region_with_model_cleanup(self, region_id: str) -> None:
        region = self._absorption.pop_region(region_id)
        if region is None:
            return

        self.remove_region_analysis_state(region_id)
        self._region_optimizer_settings.pop(region_id, None)

        self.model.remove_masks_for_group(region_id)
        for component in self._iter_absorber_components():
            if component.group_id == region_id:
                component.set_group(None)

    def _prune_empty_absorption_regions(self) -> None:
        """Remove non-UNASSIGNED regions with no lines (defensive cleanup).

        Called after project load to enforce the region invariant for legacy data.
        """
        for region_id in self._absorption.empty_region_ids():
            self._delete_region_with_model_cleanup(region_id)

    def prune_empty_absorption_regions(self) -> None:
        """Remove empty absorption regions while preserving the unassigned region."""
        self._prune_empty_absorption_regions()

    def merge_absorption_regions(self, region_ids: Sequence[str]) -> AbsorptionRegion | None:
        """Merge absorption regions into the first region in ``region_ids``."""
        valid_ids = self._absorption.validate_merge_ids(region_ids)
        if not valid_ids:
            return None

        primary_id = valid_ids[0]
        primary_region = self.require_absorption_region(primary_id)

        for rid in valid_ids[1:]:
            self.model.reassign_masks_to_group(rid, primary_id)
            region = self.require_absorption_region(rid)
            for line_id in list(region.line_ids):
                self.assign_line_to_region(line_id, primary_id)
                line = self.require_absorption_line(line_id)
                self.assign_line_models_to_region(line)
            self._delete_region_with_model_cleanup(rid)

        self.update_region_analysis_range(primary_id)
        return primary_region

    def initialize_continuum(self, name: str | None = None) -> ContinuumComponent:
        """Add a history-free continuum during project initialization.

        User-triggered scientific edits must use the application mutation
        workflow so analysis freshness and command history stay atomic.

        Args:
            name: Component name

        Returns:
            Newly initialized continuum component.
        """
        if name is None:
            n_continua = sum(1 for c in self.model.components if isinstance(c, ContinuumComponent))
            name = f"Continuum {n_continua + 1}"

        # New Java-compliant ContinuumComponent only takes name parameter
        continuum = ContinuumComponent(name=name)
        # Note: model_type, order, wavelength_range are no longer used in spline-only version
        self.model.add_component(continuum)
        self.mark_scientific_modified()
        return continuum

    def __repr__(self) -> str:
        """String representation of project."""
        n_components = len(self.model.components)

        return f"SpectroscopyProject(name='{self.name}', components={n_components})"
