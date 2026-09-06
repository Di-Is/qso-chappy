"""Integration module for optimize mode spectrum interactions.

This module provides the integration between the spectrum view and optimize mode panel
for handling model addition through context menu and Shift+click.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from PySide6.QtCore import QObject, Signal

from chappy.gui.protocols.context_menu import ContextMenuActionDescriptor, ContextMenuActionIntent
from chappy.gui.protocols.intent_types import (
    AddOptimizeComponentIntent,
    ToggleOptimizeVelocityPlotIntent,
)
from chappy.gui.protocols.optimize_spectrum import OptimizeCursorMode, OptimizeLineInfo
from chappy.presentation.interaction.interaction_contracts import (
    MaskSelectionRequest,
    OptimizeLineSelectionChange,
    OptimizeMaskFocusChange,
    OptimizeMaskGroupChange,
)

if TYPE_CHECKING:
    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.components.absorber import AbsorberComponent
    from chappy.presentation.interaction.interaction_contracts import (
        InteractionStateSnapshot,
        MaskSelectionContext,
    )

logger = logging.getLogger(__name__)

type OptimizeContextMenuActionProvider = Callable[
    [float, bool, bool, bool, bool], tuple[ContextMenuActionDescriptor, ...]
]
type VelocityVisibleProvider = Callable[[], bool]
type VelocityToggleCallback = Callable[[], None]
type OptimizeCursorFeedbackCallback = Callable[[OptimizeCursorMode], None]
_SignalPayloadT_co = TypeVar("_SignalPayloadT_co", covariant=True)


class PayloadSignalPort(Protocol[_SignalPayloadT_co]):
    """Typed subset of Qt signal objects that emit one payload.

    The signature mirrors PySide6's ``SignalInstance.connect`` (positional-only
    slot, non-None return) so concrete Qt signals satisfy this protocol
    structurally without an explicit ``cast``.
    """

    def connect(self, slot: Callable[[_SignalPayloadT_co], None], /) -> object:
        """Connect a one-argument slot."""
        ...


class NotificationSignalPort(Protocol):
    """Typed subset of Qt signal objects that emit no payload.

    The signature mirrors PySide6's ``SignalInstance.connect`` (positional-only
    slot, non-None return) so concrete Qt signals satisfy this protocol
    structurally without an explicit ``cast``.
    """

    def connect(self, slot: Callable[[], None], /) -> object:
        """Connect a no-argument slot."""
        ...


@runtime_checkable
class OptimizeSpectrumInteractionCoordinatorPort(Protocol):
    """Spectrum operations required by optimize mode integration."""

    def set_absorber_drag_candidates(self, absorber_ids: set[str] | None) -> None:
        """Set absorber identifiers available for drag operations."""
        ...

    def request_mask_selection_interaction(self, request: MaskSelectionRequest) -> bool:
        """Request mask selection interaction through shared spectrum state."""
        ...

    def highlight_mask(self, mask_id: str | None) -> None:
        """Highlight a mask on the shared spectrum surface."""
        ...

    def set_active_mask_group(self, group_id: str | None) -> None:
        """Set the active mask group on the shared spectrum surface."""
        ...

    def cancel_mask_selection(self) -> None:
        """Cancel active mask selection on the shared spectrum surface."""
        ...

    def set_selected_component_id(self, component_id: str | None) -> None:
        """Emphasise one absorber component on the shared spectrum surface."""
        ...


@runtime_checkable
class OptimizeSpectrumPanelPort(Protocol):
    """Optimize panel operations required by spectrum integration.

    Signal members are declared as read-only properties so mypy checks them
    covariantly. A writable (plain attribute) protocol member is invariant,
    which would reject concrete Qt ``SignalInstance`` attributes even though
    they structurally satisfy the signal ports.
    """

    @property
    def line_selected(self) -> PayloadSignalPort[OptimizeLineSelectionChange]:
        """Signal emitted when a line is selected."""
        ...

    @property
    def mask_selection_requested(self) -> PayloadSignalPort[MaskSelectionRequest]:
        """Signal emitted when mask selection is requested."""
        ...

    @property
    def mask_focus_changed(self) -> PayloadSignalPort[OptimizeMaskFocusChange]:
        """Signal emitted when mask focus changes."""
        ...

    @property
    def mask_cancel_requested(self) -> NotificationSignalPort:
        """Signal emitted when mask selection is cancelled."""
        ...

    @property
    def mask_group_changed(self) -> PayloadSignalPort[OptimizeMaskGroupChange]:
        """Signal emitted when the mask group changes."""
        ...

    def add_model_at_wavelength(self, wavelength: float) -> None:
        """Add a model at the specified wavelength."""
        ...

    def cancel_mask_selection(self) -> None:
        """Cancel active mask selection UI."""
        ...

    def handle_mask_selection_snapshot(
        self, snapshot: InteractionStateSnapshot[MaskSelectionContext]
    ) -> None:
        """Handle mask selection state snapshot."""
        ...

    def current_region_id(self) -> str | None:
        """Return the region currently focused in Analysis Detail."""
        ...

    def find_line_by_wavelength(self, wavelength: float) -> AbsorptionLine | None:
        """Find the owning optimize line for a wavelength."""
        ...

    def get_line_wavelength_range(self) -> tuple[float, float] | None:
        """Return the selected line wavelength range."""
        ...

    def get_line_for_component(self, component: AbsorberComponent | None) -> AbsorptionLine | None:
        """Return the absorption line for a component."""
        ...

    def tie_member_ids_for_redshift(self, component_id: str) -> frozenset[str]:
        """Return the ids of components sharing redshift with the given component."""
        ...

    def update_model_parameters(self) -> None:
        """Refresh displayed model parameters."""
        ...

    def focus_component(self, component_id: str) -> None:
        """Focus a component row."""
        ...


class OptimizeSpectrumIntegration(QObject):
    """Handles integration between spectrum view and optimize mode panel."""

    model_add_requested = Signal(float)  # wavelength

    def __init__(
        self,
        spectrum_interaction_coordinator: OptimizeSpectrumInteractionCoordinatorPort,
        optimize_panel: OptimizeSpectrumPanelPort,
        *,
        velocity_visible_provider: VelocityVisibleProvider,
        velocity_toggle_callback: VelocityToggleCallback,
        cursor_feedback_callback: OptimizeCursorFeedbackCallback,
        context_menu_action_provider: OptimizeContextMenuActionProvider | None = None,
    ) -> None:
        """Initialize the integration handler.

        Args:
            spectrum_interaction_coordinator: The spectrum presenter
            optimize_panel: The optimize mode panel
            velocity_visible_provider: Reports shared velocity overlay visibility.
            velocity_toggle_callback: Toggles the optimize velocity plot through its owner.
            cursor_feedback_callback: Applies optimize cursor feedback to the spectrum surface.
            context_menu_action_provider: Mode-local optimize context menu provider.
        """
        super().__init__()
        if optimize_panel is None:
            msg = "Optimize spectrum integration requires an optimize panel."
            raise TypeError(msg)
        self.spectrum_interaction_coordinator = spectrum_interaction_coordinator
        self.optimize_panel = optimize_panel
        self._velocity_visible_provider = velocity_visible_provider
        self._velocity_toggle_callback = velocity_toggle_callback
        self._cursor_feedback_callback = cursor_feedback_callback
        self._context_menu_action_provider = context_menu_action_provider
        self._selected_line: AbsorptionLine | None = None
        self._line_wavelength_range: tuple[float, float] | None = None

        self.optimize_panel.line_selected.connect(self._on_line_selected)
        self.model_add_requested.connect(self.optimize_panel.add_model_at_wavelength)
        self.optimize_panel.mask_selection_requested.connect(self._on_mask_selection_requested)
        self.optimize_panel.mask_focus_changed.connect(self._on_mask_focus_changed)
        self.optimize_panel.mask_cancel_requested.connect(self._on_mask_cancel_requested)
        self.optimize_panel.mask_group_changed.connect(self._on_mask_group_changed)
        self._on_mask_group_changed(
            OptimizeMaskGroupChange(group_id=self.optimize_panel.current_region_id())
        )

    def _on_line_selected(self, event: OptimizeLineSelectionChange) -> None:
        """Handle line selection from optimize panel.

        Args:
            event: The selected line change event.
        """
        line = event.line
        self._selected_line = line

        # Update spectrum interactor with selected line's absorber IDs
        if line:
            self.spectrum_interaction_coordinator.set_absorber_drag_candidates(
                self._drag_candidate_ids(line)
            )
        else:
            self.spectrum_interaction_coordinator.set_absorber_drag_candidates(None)

        if line:
            self._refresh_selected_range()
        else:
            self._line_wavelength_range = None

        self.spectrum_interaction_coordinator.set_selected_component_id(event.component_id)

    def _drag_candidate_ids(self, line: AbsorptionLine) -> set[str]:
        """Return the line's component ids plus their redshift-tie members.

        A materialized multiplet tie renders as one tree row that carries only
        the group's first line, so drag eligibility must cover every component
        sharing the tied redshift, not just the stored line's own components.
        """
        candidate_ids = set(line.model_ids)
        for model_id in line.model_ids:
            candidate_ids |= self.optimize_panel.tie_member_ids_for_redshift(model_id)
        return candidate_ids

    def _on_mask_selection_requested(self, payload: MaskSelectionRequest) -> None:
        if not self.spectrum_interaction_coordinator.request_mask_selection_interaction(payload):
            logger.warning("Failed to initiate mask selection interaction")
            self.optimize_panel.cancel_mask_selection()
            return

    def handle_mask_selection_snapshot(
        self, snapshot: InteractionStateSnapshot[MaskSelectionContext]
    ) -> None:
        """Forward mask selection snapshots to the optimize panel.

        Args:
            snapshot: Snapshot describing the mask selection lifecycle.
        """
        self.optimize_panel.handle_mask_selection_snapshot(snapshot)

    def _on_mask_focus_changed(self, event: OptimizeMaskFocusChange) -> None:
        highlight_id = event.mask_id
        self.spectrum_interaction_coordinator.highlight_mask(highlight_id)

    def _on_mask_cancel_requested(self) -> None:
        self.cancel_mask_selection()

    def _on_mask_group_changed(self, event: OptimizeMaskGroupChange) -> None:
        group_identifier = event.group_id
        self.spectrum_interaction_coordinator.set_active_mask_group(group_identifier)

    def context_menu_actions(self, wavelength: float) -> tuple[ContextMenuActionDescriptor, ...]:
        """Return optimize context menu actions for a wavelength."""
        if self._context_menu_action_provider is None:
            return ()

        has_selected_region = self.optimize_panel.current_region_id() is not None
        has_selected_line = self._selected_line is not None
        can_add_component = self._can_add_at_wavelength(wavelength) if has_selected_line else False
        velocity_plot_visible = self._velocity_visible_provider()
        return self._context_menu_action_provider(
            wavelength,
            can_add_component,
            has_selected_line,
            has_selected_region,
            velocity_plot_visible,
        )

    def handle_context_menu_intent(self, intent: ContextMenuActionIntent) -> None:
        """Execute an optimize context menu intent."""
        if isinstance(intent, AddOptimizeComponentIntent):
            self._add_model_at_wavelength(intent.wavelength)
            return

        if isinstance(intent, ToggleOptimizeVelocityPlotIntent):
            self._toggle_velocity_plot()
            return

    def handle_shift_click(self, wavelength: float, _flux: float) -> bool:
        """Handle Shift+click for quick model addition.

        Args:
            wavelength: Wavelength at click position
            _flux: Flux at click position (unused, kept for interface compatibility)

        Returns:
            True if handled, False otherwise
        """
        if not self._selected_line:
            return False

        allowed = self._can_add_at_wavelength(wavelength)
        if allowed:
            self._add_model_at_wavelength(wavelength)
        else:
            logger.info(
                "Shift-click rejected at %.4f Å for selected line %s",
                wavelength,
                self._selected_line.line_id,
            )

        # Always return True so default absorber creation does not run
        return True

    def cancel_mask_selection(self) -> None:
        """Propagate cancellation events to spectrum and panel components."""
        self.spectrum_interaction_coordinator.cancel_mask_selection()
        self.spectrum_interaction_coordinator.highlight_mask(None)

        self.optimize_panel.cancel_mask_selection()

    def _resolve_owner_line(self, wavelength: float) -> AbsorptionLine | None:
        if not math.isfinite(wavelength):
            return None

        return self.optimize_panel.find_line_by_wavelength(wavelength)

    def _refresh_selected_range(self) -> tuple[float, float] | None:
        if not self._selected_line:
            self._line_wavelength_range = None
            return None

        latest = self.optimize_panel.get_line_wavelength_range()
        self._line_wavelength_range = latest
        return latest

    def _can_add_at_wavelength(self, wavelength: float) -> bool:
        if not self._selected_line or not math.isfinite(wavelength):
            return False

        range_bounds = self._refresh_selected_range()
        if not range_bounds:
            logger.debug("Optimize add guard: no range for line %s", self._selected_line.line_id)
            return False

        low, high = range_bounds
        if not (low <= wavelength <= high):
            logger.debug(
                "Optimize add guard: %.4f Å outside range [%.4f, %.4f] for line %s",
                wavelength,
                low,
                high,
                self._selected_line.line_id,
            )
            return False

        owner = self._resolve_owner_line(wavelength)
        if owner is None:
            logger.debug(
                "Optimize add guard: no owner line for %.4f Å (selected=%s)",
                wavelength,
                self._selected_line.line_id,
            )
            return False

        allowed = owner.line_id == self._selected_line.line_id
        if not allowed:
            logger.debug(
                "Optimize add guard: owner %s != selected %s at %.4f Å",
                owner.line_id,
                self._selected_line.line_id,
                wavelength,
            )
        return allowed

    def _add_model_at_wavelength(self, wavelength: float) -> None:
        """Add model at specified wavelength.

        Args:
            wavelength: Wavelength where to add model
        """
        if self._selected_line:
            self.model_add_requested.emit(wavelength)

    def update_cursor_for_shift(
        self, wavelength: float, shift_pressed: bool
    ) -> OptimizeCursorMode:
        """Update cursor based on Shift key state and wavelength position.

        Args:
            wavelength: Current wavelength under cursor
            shift_pressed: Whether Shift key is pressed

        Returns:
            Cursor type string: 'crosshair', 'not-allowed', or 'default'
        """
        if not self._selected_line or not shift_pressed:
            return "default"

        return "crosshair" if self._can_add_at_wavelength(wavelength) else "not-allowed"

    def handle_cursor_position(self, wavelength: float, shift_pressed: bool) -> None:
        """Apply optimize cursor feedback for a raw spectrum cursor position."""
        self._cursor_feedback_callback(self.update_cursor_for_shift(wavelength, shift_pressed))

    def handle_velocity_shortcut(self) -> None:
        """Handle the optimize velocity shortcut."""
        self._toggle_velocity_plot()

    def get_line_info_for_component(
        self, component: AbsorberComponent | None
    ) -> OptimizeLineInfo | None:
        """Get line information for a component.

        Args:
            component: The absorber component

        Returns:
            Dict with line info (rest_wavelength, lambda_range) or None
        """
        # Get the line for this component from optimize panel
        if component is None:
            return None

        line = self.optimize_panel.get_line_for_component(component)
        if line:
            return OptimizeLineInfo(
                rest_wavelength=float(line.rest_wavelength), lambda_range=line.lambda_range
            )

        return None

    def update_tree_view(self) -> None:
        """Update the optimize panel tree view with current model state.

        This method is called when the model is updated from the spectrum view
        (e.g., after drag-and-drop operations) to keep the tree view in sync.
        """
        self.optimize_panel.update_model_parameters()

    def focus_component(self, component_id: str) -> None:
        """Highlight the optimize panel row for the specified component."""
        if not component_id:
            return

        self.optimize_panel.focus_component(component_id)

    def _toggle_velocity_plot(self) -> None:
        """Toggle velocity plot visibility via the mode-owned controller."""
        self._velocity_toggle_callback()
