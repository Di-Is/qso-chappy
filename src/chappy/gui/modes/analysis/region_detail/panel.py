"""Optimize mode side panel aligned with SCR-OPT specification."""

# ruff: noqa: D102

from __future__ import annotations

import logging
import math
import typing
from functools import partial
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QEvent, QPoint, Qt, Signal, SignalInstance
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QScrollArea, QTreeWidgetItem, QVBoxLayout, QWidget

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisReadiness
from chappy.gui.adapters.model_event_adapter import SpectrumModelEventAdapter
from chappy.gui.common.side_panel_section import SidePanelSection
from chappy.gui.modes.analysis.region_detail.composition import (
    MULTIPLET_REDSHIFT_TOLERANCE,
    create_line_analysis_half_width_controller,
    create_optimize_confirm_dialog_adapter,
    create_optimize_export_dialog_adapter,
    create_optimize_export_workflow_controller,
    create_optimize_fit_workflow_controller,
    create_optimize_group_selection_controller,
    create_optimize_history_adapter,
    create_optimize_mask_panel_adapter,
    create_optimize_mask_workflow_controller,
    create_optimize_mode_coordinator,
    create_optimize_model_addition_controller,
    create_optimize_model_mutation_adapter,
    create_optimize_parameter_context_controller,
    create_optimize_parameter_delete_controller,
    create_optimize_parameter_edit_controller,
    create_optimize_parameter_fix_controller,
    create_optimize_parameter_value_controller,
    create_optimize_settings_adapter,
    create_optimize_tie_set_edit_controller,
    create_optimize_tree_context_menu_controller,
)
from chappy.gui.modes.analysis.region_detail.line_analysis_half_width_controller import (
    LineAnalysisHalfWidthControllerInvariantError,
    LineAnalysisHalfWidthControllerResultKind,
)
from chappy.gui.modes.analysis.region_detail.mask.mask_panel import OptimizeMaskPanel
from chappy.gui.modes.analysis.region_detail.mask.port_adapters import (
    OptimizeMaskWorkflowPortAdapter,
    OptimizeRegionMaskRefreshPortAdapter,
)
from chappy.gui.modes.analysis.region_detail.model_addition_controller import (
    OptimizeModelAdditionUseCasePort,
    model_addition_wavelength_range_for_line,
)
from chappy.gui.modes.analysis.region_detail.model_addition_port_adapter import (
    OptimizeModelAdditionPortAdapter,
)
from chappy.gui.modes.analysis.region_detail.parameters.port_adapters import (
    OptimizeParameterDeletePortAdapter,
    OptimizeParameterEditPortAdapter,
    OptimizeParameterFixPortAdapter,
    OptimizeParameterValuePortAdapter,
    OptimizeTieSetEditPortAdapter,
)
from chappy.gui.modes.analysis.region_detail.state import RegionDetailViewState
from chappy.gui.modes.analysis.region_detail.tree.context_menu_port_adapter import (
    OptimizeTreeContextMenuPortAdapter,
)
from chappy.gui.modes.analysis.region_detail.tree.tree_view import RegionDetailTreeView
from chappy.gui.modes.analysis.region_detail.views.actions_view import RegionDetailActionsView
from chappy.gui.modes.analysis.region_detail.views.advanced_settings_view import (
    RegionDetailAdvancedSettingsView,
)
from chappy.gui.modes.analysis.region_detail.views.header_view import RegionDetailHeaderView
from chappy.gui.modes.analysis.region_detail.workflows.fit_workflow_controller import (
    OptimizeFitEditorPort,
)
from chappy.gui.modes.analysis.region_detail.workflows.port_adapters import (
    OptimizeExportWorkflowPortAdapter,
    OptimizeFitWorkflowPortAdapter,
)
from chappy.gui.theme import create_styled_menu
from chappy.gui.utils.fit_requirements import region_has_models
from chappy.gui.visual_tokens import SidePanelMetrics
from chappy.i18n import get_language_switcher
from chappy.presentation.interaction.interaction_contracts import (
    InteractionStateSnapshot,
    MaskSelectionContext,
    MaskSelectionRequest,
    OptimizeLineSelectionChange,
    OptimizeMaskFocusChange,
    OptimizeMaskGroupChange,
)
from chappy.presentation.optimize import (
    FeedbackLevel,
    FitBlockedReason,
    HalfWidthAdjustedView,
    HalfWidthAppliedView,
    HalfWidthFeedbackAdjusted,
    HalfWidthFeedbackApplied,
    HalfWidthFeedbackInvariantError,
    HalfWidthFeedbackRejectedComponentRange,
    HalfWidthFeedbackRejectedOutOfBounds,
    HalfWidthFeedbackRetainedAlreadyEqual,
    HalfWidthFeedbackRetainedMinimum,
    HalfWidthInvariantErrorView,
    HalfWidthRejectedView,
    HalfWidthRejectionReason,
    HalfWidthRetainedView,
    RegionDetailActionInputs,
    RegionDetailActionState,
)
from chappy.presentation.optimize import action_state as _compute_action_state
from chappy.presentation.optimize import fit_blocked_reason as _compute_fit_blocked_reason
from chappy.presentation.optimize import half_width_feedback as _half_width_feedback
from chappy.presentation.optimize import summary_fit_display as _summary_fit_display
from chappy.presentation.optimize import summary_note_display as _summary_note_display
from chappy.presentation.optimize import summary_state_display as _summary_state_display

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.core.components.absorber import AbsorberComponent
    from chappy.core.events import RegionTopologyChanged
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.analysis.region_detail.adapters.history_adapter import (
        OptimizeHistoryRecorder,
    )
    from chappy.gui.modes.analysis.region_detail.composition import (
        OptimizeParameterMutationUseCase,
        TieSetEditUseCase,
    )
    from chappy.gui.modes.analysis.region_detail.line_analysis_half_width_controller import (
        LineAnalysisHalfWidthControllerResult,
    )
    from chappy.gui.modes.analysis.region_detail.workflows.fit_workflow_controller import (
        FitResultRawPayload,
    )
    from chappy.gui.modes.common.analysis_navigation import AnalysisRegionFocusPort
    from chappy.presentation.optimize import HalfWidthEditOutcomeView, HalfWidthFeedbackDisplay
    from chappy.presentation.velocity import (
        VelocityComponentCreateRequest,
        VelocityContextMenuRequest,
    )

logger = logging.getLogger(__name__)


class _OptimizeEditorPort(OptimizeFitEditorPort, Protocol):
    """Optimize editor operations required by the mode panel."""

    fit_started: SignalInstance
    fit_completed: SignalInstance
    parameter_changed: SignalInstance

    def apply_optimizer_settings(
        self,
        region_id: str | None,
        max_function_evaluations: int,
        tolerance: float,
        auto_continue: bool,
    ) -> None:
        """Persist optimizer convergence settings for one region and sync the live component."""
        ...

    def current_optimizer_settings(self, region_id: str | None) -> tuple[int, float, bool]:
        """Return the optimizer convergence settings in effect for one region."""
        ...


class RegionDetailPanel(QWidget):
    """Composite side panel for optimize mode (SCR-OPT compliant)."""

    back_to_overview_requested = Signal()
    line_selected = Signal(OptimizeLineSelectionChange)
    mask_selection_requested = Signal(MaskSelectionRequest)
    mask_cancel_requested = Signal()
    mask_focus_changed = Signal(OptimizeMaskFocusChange)
    mask_group_changed = Signal(OptimizeMaskGroupChange)
    export_feedback = Signal(str, int, str)  # message, timeout_ms, semantic level
    operation_feedback = Signal(str, int, str)
    line_analysis_half_width_changed = Signal(str)

    _WAVELENGTH_EPSILON = 1e-6
    _MIN_REDSHIFT = -0.1

    def __init__(  # noqa: PLR0913 - collaborators are injected explicitly, one per responsibility
        self,
        *,
        optimize_editor: _OptimizeEditorPort,
        analysis_focus: AnalysisRegionFocusPort,
        mode_state: object | None = None,
        model_addition_usecase: OptimizeModelAdditionUseCasePort,
        parameter_mutation_usecase: OptimizeParameterMutationUseCase,
        tie_set_edit_usecase: TieSetEditUseCase,
        velocity_plot_active_provider: Callable[[], bool],
        project_file_path_provider: Callable[[], str | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.optimize_editor = optimize_editor
        self.analysis_focus = analysis_focus
        self.mode_state = mode_state
        self._language_switcher = get_language_switcher(self)
        self._project: SpectroscopyProject | None = None
        self._topology_event_adapter: SpectrumModelEventAdapter | None = None
        self._install_shortcuts()

        self._history_adapter = create_optimize_history_adapter()
        self._settings_adapter = create_optimize_settings_adapter()
        self._view_state = RegionDetailViewState()
        self._confirm_dialog_adapter = create_optimize_confirm_dialog_adapter(self)
        self._model_mutation_adapter = create_optimize_model_mutation_adapter()

        self._header_view = RegionDetailHeaderView(
            mode_state_available=lambda: self.mode_state is not None, parent=self
        )
        self._tree_view = RegionDetailTreeView(
            parent=self,
            project_provider=lambda: self._project,
            view_state=self._view_state,
            # Deferred lookup: parameter_value_controller does not exist yet at this point.
            ensure_covering_factor_parameter=lambda component: (  # noqa: PLW0108
                self._parameter_value_controller.ensure_covering_factor_parameter(component)
            ),
            request_action_state_refresh=self._update_optimize_button_state,
            request_export_controls_refresh=self._update_export_controls,
            emit_line_selected=self.line_selected.emit,
            apply_parameter_value=self._apply_parameter_value,
            reset_component_parameter=self._reset_model_value,
            apply_line_analysis_half_width=self._on_line_analysis_half_width_changed,
            load_tree_header_state=self._settings_adapter.load_tree_header_state,
            save_tree_header_state=self._settings_adapter.save_tree_header_state,
            load_cosmology_parameters=self._settings_adapter.load_cosmology_parameters,
        )

        self._parameter_context_controller = create_optimize_parameter_context_controller(
            multiplet_redshift_tolerance=MULTIPLET_REDSHIFT_TOLERANCE,
            min_redshift=self._MIN_REDSHIFT,
        )
        self._parameter_mutation_usecase = parameter_mutation_usecase

        parameter_edit_port = OptimizeParameterEditPortAdapter(
            project_provider=lambda: self._project,
            parameter_context_controller=self._parameter_context_controller,
            parameter_fix_controller_provider=lambda: self._parameter_fix_controller,
            tree_view=self._tree_view,
            apply_parameter_value=self._apply_parameter_value,
        )
        self._parameter_edit_controller = create_optimize_parameter_edit_controller(
            parent=self, port=parameter_edit_port
        )

        parameter_value_port = OptimizeParameterValuePortAdapter(
            project_provider=lambda: self._project,
            history_adapter=self._history_adapter,
            group_selection_controller_provider=lambda: self._group_selection_controller,
            tree_view=self._tree_view,
            validate_value=self._validate_value,
            emit_parameter_changed=self.optimize_editor.parameter_changed.emit,
        )
        self._parameter_value_controller = create_optimize_parameter_value_controller(
            port=parameter_value_port, usecase=self._parameter_mutation_usecase
        )

        parameter_delete_port = OptimizeParameterDeletePortAdapter(
            history_adapter=self._history_adapter
        )
        self._parameter_delete_controller = create_optimize_parameter_delete_controller(
            port=parameter_delete_port
        )

        parameter_fix_port = OptimizeParameterFixPortAdapter(
            project_provider=lambda: self._project,
            history_adapter=self._history_adapter,
            group_selection_controller_provider=lambda: self._group_selection_controller,
            parameter_value_controller=self._parameter_value_controller,
            parameter_edit_controller=self._parameter_edit_controller,
            tree_view=self._tree_view,
        )
        self._parameter_fix_controller = create_optimize_parameter_fix_controller(
            port=parameter_fix_port
        )

        tie_set_edit_port = OptimizeTieSetEditPortAdapter(
            project_provider=lambda: self._project,
            history_adapter=self._history_adapter,
            confirm_dialog_adapter=self._confirm_dialog_adapter,
            header_view=self._header_view,
            on_group_combo_changed=self._on_group_combo_changed,
        )
        self._tie_set_edit_usecase = tie_set_edit_usecase
        self._tie_set_edit_controller = create_optimize_tie_set_edit_controller(
            usecase=self._tie_set_edit_usecase, port=tie_set_edit_port
        )

        tree_context_menu_port = OptimizeTreeContextMenuPortAdapter(
            project_provider=lambda: self._project,
            parameter_value_controller=self._parameter_value_controller,
            parameter_fix_controller=self._parameter_fix_controller,
            parameter_edit_controller=self._parameter_edit_controller,
            parameter_delete_controller=self._parameter_delete_controller,
            parameter_context_controller=self._parameter_context_controller,
            model_mutation_adapter=self._model_mutation_adapter,
            confirm_dialog_adapter=self._confirm_dialog_adapter,
            header_view=self._header_view,
            on_group_combo_changed=self._on_group_combo_changed,
        )
        self._tree_context_menu_controller = create_optimize_tree_context_menu_controller(
            tree=self._tree_view.tree,
            parent=self,
            port=tree_context_menu_port,
            tie_set_edit=self._tie_set_edit_controller,
            tie_label_for_uid=self._tree_view.tie_label_for_uid,
        )

        self._actions_view = RegionDetailActionsView(
            request_action_state_refresh=self._update_optimize_button_state,
            set_needs_badge_visible=self._header_view.set_needs_badge_visible,
            clear_group_summary=self._header_view.clear_group_summary,
            parent=self,
        )

        self._mask_panel = OptimizeMaskPanel(self)
        self._mask_panel.set_add_button_active(False)
        self._mask_panel_adapter = create_optimize_mask_panel_adapter(self._mask_panel)

        mask_workflow_port = OptimizeMaskWorkflowPortAdapter(
            group_selection_controller_provider=lambda: self._group_selection_controller,
            mask_panel_adapter=self._mask_panel_adapter,
            mask_panel=self._mask_panel,
            tree_view=self._tree_view,
            confirm_dialog_adapter=self._confirm_dialog_adapter,
            project_provider=lambda: self._project,
            velocity_plot_active_provider=velocity_plot_active_provider,
            mask_cancel_shortcut=self._mask_cancel_shortcut,
            emit_mask_selection_request=self.mask_selection_requested.emit,
            emit_mask_focus_changed=self.mask_focus_changed.emit,
            emit_mask_cancel_requested=self.mask_cancel_requested.emit,
            focused_region_id_provider=self.analysis_focus.focused_region_id,
        )
        self._mask_workflow_adapter = mask_workflow_port
        self._mask_workflow_controller = create_optimize_mask_workflow_controller(
            port=self._mask_workflow_adapter,
            mask_adapter=self._mask_panel_adapter,
            history=self._history_adapter,
            event_parent=self,
        )

        region_mask_refresh_port = OptimizeRegionMaskRefreshPortAdapter(
            project_provider=lambda: self._project,
            group_selection_controller_provider=lambda: self._group_selection_controller,
            mask_workflow_controller=self._mask_workflow_controller,
            emit_mask_group_changed=self.mask_group_changed.emit,
        )
        self._group_selection_controller = create_optimize_group_selection_controller(
            selector=self._header_view,
            actions=self._actions_view,
            tree_render=self._tree_view,
            mask_refresh=region_mask_refresh_port,
            analysis_focus=self.analysis_focus,
        )
        self._line_analysis_half_width_controller = create_line_analysis_half_width_controller(
            project_provider=lambda: self._project,
            group_controller=self._group_selection_controller,
            history=self._history_adapter,
        )

        self._advanced_settings_view = RegionDetailAdvancedSettingsView(parent=self)

        self._build_layout()
        self._connect_signals()

        self._language_switcher.language_changed.connect(self._on_language_changed)
        self._on_language_changed(self._language_switcher.current_language)

        self._export_dialog_adapter = create_optimize_export_dialog_adapter(self)
        export_workflow_port = OptimizeExportWorkflowPortAdapter(
            project_provider=lambda: self._project,
            group_selection_controller=self._group_selection_controller,
            settings_adapter=self._settings_adapter,
            project_file_path_provider=project_file_path_provider,
            emit_export_feedback=self.export_feedback.emit,
            focused_region_id_provider=self.analysis_focus.focused_region_id,
        )
        self._export_workflow_controller = create_optimize_export_workflow_controller(
            port=export_workflow_port, dialog_adapter=self._export_dialog_adapter
        )

        fit_workflow_port = OptimizeFitWorkflowPortAdapter(
            project_provider=lambda: self._project,
            group_selection_controller=self._group_selection_controller,
            view_state=self._view_state,
            tree_view=self._tree_view,
            should_enable_fit=self._should_enable_fit,
            update_button_state=self._update_optimize_button_state,
            refresh_fit_model_rows_display=self.update_model_parameters,
            focused_region_id_provider=self.analysis_focus.focused_region_id,
        )
        self._fit_workflow_controller = create_optimize_fit_workflow_controller(
            self.optimize_editor, fit_workflow_port
        )

        model_addition_port = OptimizeModelAdditionPortAdapter(
            project_provider=lambda: self._project,
            view_state=self._view_state,
            history_adapter=self._history_adapter,
            finalise_model_addition_display=self._finalise_model_addition,
        )
        self._model_addition_controller = create_optimize_model_addition_controller(
            port=model_addition_port, usecase=model_addition_usecase
        )
        self._coordinator = create_optimize_mode_coordinator(
            panel=self, editor=self.optimize_editor
        )
        self._coordinator.connect()
        self._restore_advanced_settings_expanded()
        self._initialize_advanced_settings(self.current_region_id())

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setObjectName("analysisDetailSidePanelScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget(scroll)
        content.setObjectName("analysisDetailSidePanelContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*SidePanelMetrics.OUTER_MARGIN)
        layout.setSpacing(SidePanelMetrics.SECTION_SPACING)

        layout.addWidget(self._header_view)

        # Flow order: region selection -> single primary action -> results
        # summary -> masked ranges.
        layout.addWidget(self._actions_view)

        # Advanced masked-range editing lives below the primary actions.
        self._mask_frame = SidePanelSection(self, object_name="analysisDetailMaskCard")
        self._mask_frame.body.addWidget(self._mask_panel)
        layout.addWidget(self._mask_frame)

        layout.addWidget(self._advanced_settings_view)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._mask_panel.add_mask_requested.connect(self._on_add_mask_requested)
        self._mask_panel.edit_mask_requested.connect(self._on_edit_mask_requested)
        self._mask_panel.mask_selected.connect(self._on_mask_selected)
        self._mask_panel.remove_mask_requested.connect(self._on_remove_mask_requested)
        self._mask_panel.mask_range_changed.connect(self._on_mask_range_changed)

        self._header_view.group_selection_changed.connect(self._on_group_combo_changed)
        self._header_view.back_clicked.connect(self.back_to_overview_requested.emit)
        self._tree_view.tree.customContextMenuRequested.connect(
            self._on_tree_context_menu_requested
        )
        self._actions_view.optimize_clicked.connect(self._on_optimize_clicked)
        self._actions_view.add_model_clicked.connect(self._on_add_model_clicked)
        self._actions_view.export_clicked.connect(self._on_export_clicked)

        self._advanced_settings_view.expanded_toggled.connect(self._on_advanced_toggled)
        self._advanced_settings_view.settings_changed.connect(self._apply_advanced_settings)
        self.mask_group_changed.connect(self._on_advanced_settings_region_changed)
        self.mask_group_changed.connect(self._on_view_state_region_changed)

    def _install_shortcuts(self) -> None:
        self._mask_cancel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._mask_cancel_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._mask_cancel_shortcut.setEnabled(False)
        self._mask_cancel_shortcut.activated.connect(self.mask_cancel_requested.emit)

    def _on_language_changed(self, _code: str) -> None:
        self.retranslate_ui()
        self._refresh_group_choices()
        focused_region_id = self.analysis_focus.focused_region_id()
        region = (
            self._project.absorption_regions.get(focused_region_id)
            if self._project is not None and focused_region_id is not None
            else None
        )
        if region is not None:
            # Rebuilding the combo above reset its display to index 0; re-project
            # canonical focus into the selector and force a tree rebuild so the
            # displayed region and its tree stay in sync with canonical focus
            # across a language switch (P2 addendum).
            self.select_focused_region(region)
            self.render_focused_region(region.region_id)
        else:
            self._rebuild_tree()
            self._group_selection_controller.reconcile_focus_with_selector(self._project)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt method override
        """Refresh translated UI text when Qt sends a language change event.

        Args:
            event: Qt change event.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        self._header_view.retranslate_ui()
        self._actions_view.retranslate_ui()
        self._advanced_settings_view.retranslate_ui()
        self._tree_view.retranslate()
        self._update_optimize_button_state()
        self._update_export_controls()

    def set_project(self, project: SpectroscopyProject | None) -> None:
        had_selection = self._view_state.selected_line_id is not None
        self._detach_topology_events()
        self._view_state.reset_for_project_change()
        self._project = project
        self._tree_view.tie_label_allocator.reset()
        self._mask_workflow_controller.clear_active_mask()
        self._mask_workflow_adapter.set_mask_interaction_active(False)
        self._mask_workflow_controller.attach_project(project)
        self._update_mask_panel_state()
        self._refresh_group_choices()
        self._rebuild_tree()
        # `mask_group_changed` is a display-projection signal (mask panel render
        # target, advanced-settings hydration, line-selection-clearing), not a
        # canonical-focus signal: it must carry the selector's just-populated
        # default so those listeners initialize correctly before any later
        # reconciliation runs (`reconcile_focus_with_selector` never re-emits
        # this signal). See tests/gui/widgets/test_optimize_mode_panel_advanced_settings.py
        # ::test_set_project_initializes_widgets_from_region_settings.
        displayed_group_id = self._group_selection_controller.current_group_id()
        self.mask_group_changed.emit(OptimizeMaskGroupChange(group_id=displayed_group_id))
        if project is not None:
            self._topology_event_adapter = SpectrumModelEventAdapter(project.model, self)
            self._topology_event_adapter.region_topology_changed.connect(
                self._on_region_topology_changed
            )
        if had_selection:
            self._propagate_selection_cleared()

    def tie_label_for_redshift(self, component: AbsorberComponent) -> str | None:
        """Return the tie-set display label for a component's redshift, if tied."""
        return self._tree_view.tie_label_for(component, "redshift")

    def tie_member_ids_for_redshift(self, component_id: str) -> frozenset[str]:
        """Return the ids of components sharing redshift with the given component."""
        return self._group_selection_controller.tie_member_ids_for_redshift(
            self._project, component_id
        )

    def refresh(self) -> None:
        """Refresh the panel display without mutating scientific project state."""
        if self._view_state.drop_vanished_selection(self._project):
            self._propagate_selection_cleared()
        self._refresh_group_choices()
        # If there's a selected group, rebuild the tree with it
        if self._header_view.current_group_selector_index() >= 0:
            self._on_group_combo_changed(self._header_view.current_group_selector_index())

    def set_history_recorder(self, recorder: OptimizeHistoryRecorder | None) -> None:
        """Set history recorder for undo/redo recording."""
        self._history_adapter.set_bridge(recorder)

    def refresh_for_history(self, region_id: str | None = None) -> None:
        """Refresh UI after undo/redo without mutating scientific project state."""
        _ = region_id  # Reserved for future selective badge updates
        self.refresh()

    def notify_cosmology_changed(self) -> None:
        """Rebuild the current region tree with freshly persisted cosmology parameters."""
        if self._project is None:
            return
        group_id = self.analysis_focus.focused_region_id()
        if not group_id:
            return
        region = self._project.absorption_regions.get(group_id)
        if region is None:
            return
        self._tree_view.rebuild_region(self._project, region)

    def _has_absorption_regions(self) -> bool:
        return self._group_selection_controller.has_regions_with_lines(self._project)

    def _update_mask_panel_state(self) -> None:
        has_regions = self._has_absorption_regions()
        self._mask_workflow_controller.update_panel_state(has_regions=has_regions)

    def _on_add_mask_requested(self) -> None:
        self._mask_workflow_controller.request_add_mask()

    def _on_edit_mask_requested(self, mask_id: str) -> None:
        self._mask_workflow_controller.request_edit_mask(mask_id)

    def _on_mask_selected(self, mask_id: str | None) -> None:
        self._mask_workflow_controller.select_mask(mask_id)

    def handle_mask_selection_snapshot(
        self, snapshot: InteractionStateSnapshot[MaskSelectionContext]
    ) -> None:
        """Apply a mask selection snapshot emitted by the state controller.

        Args:
            snapshot: Snapshot describing the current mask selection lifecycle.
        """
        self._mask_workflow_controller.handle_selection_snapshot(snapshot)

    def cancel_mask_selection(self) -> None:
        self._mask_workflow_controller.cancel_selection()

    def current_region_id(self) -> str | None:
        """Return the region currently focused in Analysis Detail."""
        return self.analysis_focus.focused_region_id()

    def select_focused_region(self, region: AbsorptionRegion | None) -> None:
        """Project the Analysis focus into the existing region selector."""
        region_id = region.region_id if region is not None else None
        self._group_selection_controller.select_group_id(self._project, region_id)

    def render_focused_region(self, region_id: str) -> None:
        """Rebuild this region's tree from current project state on surface entry."""
        self._group_selection_controller.render_region(self._project, region_id)

    def reconcile_focus_with_selector(self) -> None:
        """Make canonical Analysis focus and the selector's display agree.

        Called by the shell once a project context change has fully settled
        (`_context_switching` cleared), after canonical focus has already
        been restored/validated for the new project.
        """
        self._group_selection_controller.reconcile_focus_with_selector(self._project)

    def parameter_tree_widget(self) -> QWidget:
        """Widget hosting the parameter table, placed by the shell into a dock."""
        return self._tree_view.tree

    def _on_remove_mask_requested(self, mask_id: str) -> None:
        self._mask_workflow_controller.remove_mask(mask_id)

    def _on_mask_range_changed(self, mask_id: str, start: float, end: float) -> None:
        self._mask_workflow_controller.change_mask_range(mask_id, start, end)

    def _refresh_group_choices(self) -> None:
        self._group_selection_controller.refresh_group_choices(self._project)

    def _detach_topology_events(self) -> None:
        """Detach the project topology subscription owned by this panel."""
        if self._topology_event_adapter is None:
            return
        self._topology_event_adapter.region_topology_changed.disconnect(
            self._on_region_topology_changed
        )
        self._topology_event_adapter.close()
        self._topology_event_adapter = None

    def _on_region_topology_changed(self, _event: RegionTopologyChanged) -> None:
        """Rebuild Detail projections without treating selector defaults as user focus."""
        project = self._project
        if project is None:
            return

        focused_region_id = self.analysis_focus.focused_region_id()

        if self._view_state.drop_vanished_selection(project):
            self._propagate_selection_cleared()
        self._refresh_group_choices()

        if focused_region_id is not None and focused_region_id in project.absorption_regions:
            self._group_selection_controller.render_region(project, focused_region_id)
            return

        self._rebuild_tree()
        self._mask_workflow_controller.on_masks_changed()
        self._update_export_controls()
        self.mask_group_changed.emit(OptimizeMaskGroupChange(group_id=None))

    def _update_export_controls(self) -> None:
        self._group_selection_controller.update_export_controls(self._project)

    def _region_id_for_component(self, component: AbsorberComponent | None) -> str | None:
        """Return the absorption region identifier tied to the component.

        Args:
            component: Component to inspect.

        Returns:
            Region identifier if the component can be associated with one.
        """
        return self._group_selection_controller.region_id_for_component(self._project, component)

    def _on_group_combo_changed(self, index: int) -> None:
        self._group_selection_controller.group_combo_changed(self._project, index)

    def _rebuild_tree(self) -> None:
        self._tree_view.clear()

    def update_model_parameters(self) -> None:
        """Update tree view with current model parameters.

        This method synchronizes the tree view display with the current
        model state without rebuilding the entire tree.
        """
        self._tree_view.refresh_model_parameters(self._project)

    def focus_component(self, component_id: str) -> None:
        """Highlight the tree row corresponding to the component identifier."""
        self._tree_view.focus_component(component_id)

    def _on_line_analysis_half_width_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Apply one top-level scientific half-width cell edit."""
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(line, AbsorptionLine) or self._project is None:
            return
        text = item.text(column).strip().removeprefix("±").strip()
        try:
            requested = float(text)
        except ValueError:
            self._restore_line_analysis_half_width_cell(line)
            self._emit_analysis_half_width_feedback(
                self.tr("Enter a finite analysis range in km/s."), level="error"
            )
            return

        try:
            outcome = self._line_analysis_half_width_controller.edit(
                line_id=line.line_id, requested_half_width=requested
            )
        except LineAnalysisHalfWidthControllerInvariantError as error:
            logger.exception("Line analysis half-width edit failed project invariants")
            self._restore_line_analysis_half_width_cell(line)
            view: HalfWidthEditOutcomeView = HalfWidthInvariantErrorView(
                component_id=error.component_id
            )
            self._apply_half_width_feedback(item, column, _half_width_feedback(view))
            return

        self._restore_line_analysis_half_width_cell(line)
        view = self._half_width_outcome_view(outcome)
        if isinstance(view, (HalfWidthAppliedView, HalfWidthAdjustedView)):
            if outcome.region_id is None:
                msg = "Applied analysis half-width result is missing a region id."
                raise RuntimeError(msg)
            self._finish_line_analysis_half_width_mutation(
                outcome.region_id, outcome.affected_line_ids
            )
        self._apply_half_width_feedback(item, column, _half_width_feedback(view))

    def _half_width_outcome_view(
        self, outcome: LineAnalysisHalfWidthControllerResult
    ) -> HalfWidthEditOutcomeView:
        """Convert a controller half-width result into a presentation outcome view."""
        match outcome.kind:
            case LineAnalysisHalfWidthControllerResultKind.APPLIED:
                if outcome.applied is None or outcome.region_id is None:
                    msg = "Applied analysis half-width result is incomplete."
                    raise RuntimeError(msg)
                return HalfWidthAppliedView(
                    applied=outcome.applied, affected_count=len(outcome.affected_line_ids)
                )
            case LineAnalysisHalfWidthControllerResultKind.ADJUSTED:
                if outcome.applied is None or outcome.region_id is None:
                    msg = "Adjusted analysis half-width result is incomplete."
                    raise RuntimeError(msg)
                return HalfWidthAdjustedView(
                    requested=outcome.requested,
                    applied=outcome.applied,
                    affected_count=len(outcome.affected_line_ids),
                )
            case LineAnalysisHalfWidthControllerResultKind.NO_CHANGE:
                if outcome.applied is None:
                    msg = "No-change analysis half-width result is incomplete."
                    raise RuntimeError(msg)
                return HalfWidthRetainedView(
                    requested=outcome.requested,
                    retained=outcome.applied,
                    already_equal=outcome.reason == "already_equal",
                )
            case LineAnalysisHalfWidthControllerResultKind.REJECTED:
                reason = (
                    HalfWidthRejectionReason.COMPONENT_OUTSIDE_SUPPORTED_RANGE
                    if outcome.reason == "component_outside_supported_range"
                    else HalfWidthRejectionReason.OUT_OF_BOUNDS
                )
                return HalfWidthRejectedView(
                    reason=reason,
                    requested=outcome.requested,
                    supported_minimum=outcome.supported_minimum,
                    supported_maximum=outcome.supported_maximum,
                )
            case _:
                typing.assert_never(outcome.kind)

    def _apply_half_width_feedback(
        self, item: QTreeWidgetItem, column: int, display: HalfWidthFeedbackDisplay
    ) -> None:
        """Render a half-width feedback display as a status message and cell annotation."""
        message = self._half_width_feedback_message(display)
        level = "error" if display.level is FeedbackLevel.ERROR else "info"
        self._emit_analysis_half_width_feedback(message, level=level)
        if display.show_cell_annotation:
            item.setToolTip(column, message)
            item.setData(column, Qt.ItemDataRole.AccessibleDescriptionRole, message)

    def _half_width_feedback_message(self, display: HalfWidthFeedbackDisplay) -> str:
        """Return the tr() message for one half-width feedback display."""
        if isinstance(display, HalfWidthFeedbackApplied):
            return self.tr("Applied ±{applied:g} km/s to {count} linked lines.").format(
                applied=display.applied, count=display.affected_count
            )
        if isinstance(display, HalfWidthFeedbackAdjusted):
            return self.tr(
                "Requested ±{requested:g} km/s; applied ±{applied:g} km/s to {count} "
                "linked lines to include all model centers."
            ).format(
                requested=display.requested, applied=display.applied, count=display.affected_count
            )
        if isinstance(display, HalfWidthFeedbackRetainedAlreadyEqual):
            return self.tr("Analysis range is already ±{retained:g} km/s.").format(
                retained=display.retained
            )
        if isinstance(display, HalfWidthFeedbackRetainedMinimum):
            return self.tr(
                "Requested ±{requested:g} km/s; retained ±{retained:g} km/s because "
                "model centers require this minimum."
            ).format(requested=display.requested, retained=display.retained)
        if isinstance(display, HalfWidthFeedbackRejectedComponentRange):
            return self.tr(
                "Model centers require more than ±{maximum:g} km/s; the analysis range "
                "was not changed."
            ).format(maximum=display.supported_maximum)
        if isinstance(display, HalfWidthFeedbackRejectedOutOfBounds):
            return self.tr(
                "Analysis range must be between ±{minimum:g} and ±{maximum:g} km/s."
            ).format(minimum=display.supported_minimum, maximum=display.supported_maximum)
        if isinstance(display, HalfWidthFeedbackInvariantError):
            return self.tr(
                "Cannot edit the analysis range because model component {component_id} "
                "has inconsistent redshift data."
            ).format(component_id=display.component_id)
        typing.assert_never(display)

    def _restore_line_analysis_half_width_cell(self, line: AbsorptionLine) -> None:
        """Restore a line/multiplet cell from current project state."""
        if self._project is None:
            return
        affected_ids = tuple(self._project.expand_multiplet_line_ids([line.line_id]))
        self._tree_view.refresh_analysis_half_width_rows(self._project, affected_ids)

    def _finish_line_analysis_half_width_mutation(
        self, region_id: str, affected_line_ids: tuple[str, ...]
    ) -> None:
        """Refresh only views affected by a committed scientific range edit."""
        if self._project is None:
            return
        self._tree_view.refresh_analysis_half_width_rows(self._project, affected_line_ids)
        self.line_analysis_half_width_changed.emit(region_id)

    def _emit_analysis_half_width_feedback(self, message: str, *, level: str = "info") -> None:
        """Surface scientific edit feedback through the shell status boundary."""
        self.operation_feedback.emit(message, 7000, level)

    def _reset_model_value(
        self, item: QTreeWidgetItem, column: int, component: AbsorberComponent, param_name: str
    ) -> None:
        # Re-render the whole row (not just this cell) so the tie label prefix
        # and rounded "value ± error" text are restored consistently.
        self._tree_view.refresh_component_row(item, component)

        # Generate error message with dynamic constraint information
        if param_name == "redshift":
            z_bounds = self._parameter_context_controller.z_bounds(
                component,
                self._parameter_context_controller.line_for_component(self._project, component),
            )
            if z_bounds is not None:
                z_min, z_max = z_bounds
                tooltip_msg = self.tr(
                    "Redshift must be between {z_min:.3f} and {z_max:.3f} for this line"
                ).format(z_min=z_min, z_max=z_max)
            else:
                tooltip_msg = self.tr("Enter a valid value for this parameter")
        else:
            tooltip_msg = self.tr("Enter a valid value for this parameter")

        item.setToolTip(column, tooltip_msg)

    def _apply_parameter_value(
        self, component: AbsorberComponent, param_name: str, value: float
    ) -> bool:
        """Apply a parameter edit originating from the model tree or dialog.

        Args:
            component: Target absorber component.
            param_name: Name of the parameter being updated.
            value: The candidate value to assign.

        Returns:
            True when the value passes validation and updates the model.
        """
        return self._parameter_value_controller.apply_parameter_value(component, param_name, value)

    def _on_tree_context_menu_requested(self, point: QPoint) -> None:
        self._tree_context_menu_controller.show_context_menu(point)

    def _on_optimize_clicked(self) -> None:
        self._fit_workflow_controller.optimize_clicked()

    def _on_fit_started(self) -> None:
        self._fit_workflow_controller.fit_started()

    def _on_fit_completed(self, results: FitResultRawPayload) -> None:
        self._fit_workflow_controller.fit_completed(results)

    def handle_editor_fit_started(self) -> None:
        """Handle editor fit-start signal routed by the mode coordinator."""
        self._on_fit_started()

    def handle_editor_fit_completed(self, results: FitResultRawPayload) -> None:
        """Handle editor fit-completed signal routed by the mode coordinator."""
        self._on_fit_completed(results)

    def _on_export_clicked(self) -> None:
        self._export_workflow_controller.export_current_region()

    def _restore_advanced_settings_expanded(self) -> None:
        expanded = self._settings_adapter.load_advanced_settings_expanded()
        self._advanced_settings_view.set_expanded(expanded)

    def _on_advanced_toggled(self, expanded: bool) -> None:
        self._settings_adapter.save_advanced_settings_expanded(expanded)

    def _on_advanced_settings_region_changed(self, change: OptimizeMaskGroupChange) -> None:
        self._initialize_advanced_settings(change.group_id)

    def _on_view_state_region_changed(self, change: OptimizeMaskGroupChange) -> None:
        """Clear a selected line that does not belong to the newly active region."""
        if self._view_state.clear_selection_outside_region(self._project, change.group_id):
            self._propagate_selection_cleared()

    def _propagate_selection_cleared(self) -> None:
        """Notify collaborators (spectrum integration, action state) of a cleared selection."""
        self._update_optimize_button_state()
        self.line_selected.emit(OptimizeLineSelectionChange(line=None, component_id=None))

    def _initialize_advanced_settings(self, region_id: str | None) -> None:
        max_function_evaluations, tolerance, auto_continue = (
            self.optimize_editor.current_optimizer_settings(region_id)
        )
        self._advanced_settings_view.show_settings(
            max_function_evaluations, tolerance, auto_continue
        )

    def _apply_advanced_settings(self) -> None:
        max_function_evaluations, tolerance, auto_continue = (
            self._advanced_settings_view.current_settings()
        )
        self.optimize_editor.apply_optimizer_settings(
            self.current_region_id(), max_function_evaluations, tolerance, auto_continue
        )

    def _region_detail_action_inputs(self) -> RegionDetailActionInputs:
        """Collect the facts the presentation action-state classification needs."""
        project = self._project
        has_spectrum = (
            project is not None
            and project.model is not None
            and project.model.observed_spectrum is not None
        )
        group_id = self.analysis_focus.focused_region_id()
        return RegionDetailActionInputs(
            fit_running=self.optimize_editor.is_fitting(),
            has_spectrum=has_spectrum,
            has_region_selected=bool(group_id),
            has_model_components=bool(group_id) and region_has_models(project, group_id),
            readiness=self._current_region_readiness(),
        )

    def _action_state(self) -> RegionDetailActionState:
        """Derive the exclusive action state from existing fit prerequisites."""
        return _compute_action_state(self._region_detail_action_inputs())

    def _current_region_readiness(self) -> AnalysisReadiness:
        group_id = self.analysis_focus.focused_region_id()
        if self._project is None or not group_id:
            return AnalysisReadiness.NOT_ANALYZED
        return self._group_selection_controller.analysis_readiness(self._project, group_id)

    def _update_optimize_button_state(self) -> None:
        """Synchronize the action buttons and results summary with panel state."""
        state = self._action_state()
        reason = self._fit_blocked_reason()
        line = self._view_state.resolve_selected_line(self._project)
        target_line = self._add_target_line()
        readiness = self._current_region_readiness()
        status = self._view_state.fit_status
        project_chi2, project_reduced = self._project_fit_summary_values()

        self._actions_view.render_action_state(
            state=state,
            blocked_reason=reason,
            add_model_target_label=(
                self._add_target_label(target_line) if target_line is not None else None
            ),
            add_model_visible=state is RegionDetailActionState.EMPTY or line is not None,
            summary_state_display=_summary_state_display(state, readiness, status),
            summary_fit_display=_summary_fit_display(
                status, project_chi2=project_chi2, project_reduced=project_reduced
            ),
            component_count=(
                None
                if state is RegionDetailActionState.NO_CONTEXT
                else self._current_component_count()
            ),
            summary_note_display=_summary_note_display(state, readiness, status, reason),
        )

    def _project_fit_summary_values(self) -> tuple[float | None, float | None]:
        """Return the project-stored chi-squared values for the focused region, if any."""
        group_id = self.analysis_focus.focused_region_id()
        if self._project is None or not group_id:
            return None, None
        summary = self._group_selection_controller.fit_summary(self._project, group_id)
        if summary is None:
            return None, None
        return summary.chi_squared, summary.reduced_chi_squared

    def _current_component_count(self) -> int:
        return self._group_selection_controller.component_count(
            self._project, self.analysis_focus.focused_region_id()
        )

    def _should_enable_fit(self) -> bool:
        """Return True when the panel meets the fit prerequisites."""
        return self._fit_blocked_reason() is None

    def _fit_blocked_reason(self) -> FitBlockedReason | None:
        """Return the typed reason the fit action is unavailable, if any.

        The checks decompose the existing enablement sources: the fit-running
        provider and the ``region_has_models`` prerequisite chain (loaded
        spectrum, selected region, at least one absorber component).
        """
        return _compute_fit_blocked_reason(self._region_detail_action_inputs())

    def _validate_value(self, param_name: str, value: float, component: AbsorberComponent) -> bool:
        """Validate a parameter value with current component context."""
        return self._parameter_context_controller.validate_value(
            self._project, param_name, value, component
        )

    def _add_target_line(self) -> AbsorptionLine | None:
        """Return the line a direct add-component action targets, if unambiguous."""
        selected_line = self._view_state.resolve_selected_line(self._project)
        if selected_line is not None:
            return selected_line
        lines = self._current_region_lines()
        return lines[0] if len(lines) == 1 else None

    @staticmethod
    def _add_target_label(line: AbsorptionLine) -> str:
        """Return a line label disambiguated by redshift for add-component UI."""
        return f"{line.transition_name} (z={line.center_z:.3f})"

    def _on_add_model_clicked(self) -> None:
        """Route the add-component action to the resolved or chosen line."""
        target_line = self._add_target_line()
        if target_line is not None:
            self._model_addition_controller.add_to_line(target_line)
            return
        lines = self._current_region_lines()
        if not lines:
            return
        menu = create_styled_menu(self)
        for line in lines:
            action = menu.addAction(self._add_target_label(line))
            action.triggered.connect(partial(self._model_addition_controller.add_to_line, line))
        add_model_button = self._actions_view.add_model_button()
        menu.exec(add_model_button.mapToGlobal(QPoint(0, add_model_button.height())))

    def _current_region_lines(self) -> tuple[AbsorptionLine, ...]:
        """Return display-ordered absorption lines of the focused region."""
        return self._group_selection_controller.region_lines(
            self._project, self.analysis_focus.focused_region_id()
        )

    def add_model_at_wavelength(self, wavelength: float) -> None:
        """Add a model at the specified wavelength.

        Args:
            wavelength: Observed wavelength where to add the model
        """
        self._model_addition_controller.add_at_wavelength(wavelength)

    def handle_velocity_context_menu(self, request: VelocityContextMenuRequest) -> None:
        """Handle context menu request from velocity plot.

        Args:
            request: Typed velocity context-menu payload.
        """
        self._model_addition_controller.show_velocity_context_menu(
            self,
            add_label=self.tr("Add Component Here"),
            velocity=request.velocity,
            line_id=request.line_id,
            rest_wavelength=request.rest_wavelength,
            center_z=request.center_z,
            global_x=request.global_position[0],
            global_y=request.global_position[1],
        )

    def handle_velocity_shift_click(self, request: VelocityComponentCreateRequest) -> None:
        """Handle Shift+click from velocity plot - direct component addition.

        Args:
            request: Typed component-creation payload.
        """
        self._model_addition_controller.add_from_velocity_line_id(
            request.velocity, request.line_id, request.rest_wavelength, request.center_z
        )

    def _finalise_model_addition(
        self, components: dict[str, AbsorberComponent], *, focus_line: AbsorptionLine
    ) -> None:
        """Refresh UI state and emit signals after adding components."""
        if not components:
            return

        # Always use full rebuild instead of partial update
        if self._header_view.current_group_selector_index() >= 0:
            self._on_group_combo_changed(self._header_view.current_group_selector_index())
        else:
            self._rebuild_tree()

        self._tree_view.select_component_for_line(focus_line, components.get(focus_line.line_id))

    def _line_wavelength_range_for(
        self, line: AbsorptionLine | None
    ) -> tuple[float, float] | None:
        if line is None:
            return None
        return model_addition_wavelength_range_for_line(line)

    def get_line_wavelength_range(self) -> tuple[float, float] | None:
        """Get the wavelength range of the selected line.

        Returns:
            Tuple of (min_wavelength, max_wavelength) or None if no line selected
        """
        return self._line_wavelength_range_for(
            self._view_state.resolve_selected_line(self._project)
        )

    def get_line_for_component(self, component: AbsorberComponent | None) -> AbsorptionLine | None:
        """Get the first absorption line associated with a component.

        Args:
            component: The component to find the line for.

        Returns:
            The first matching absorption line, or None if not found.
        """
        if component is None:
            return None
        return self._group_selection_controller.line_for_component(self._project, component.id)

    def find_line_by_wavelength(self, wavelength: float) -> AbsorptionLine | None:
        if not math.isfinite(wavelength):
            return None
        return self._group_selection_controller.line_for_wavelength(
            self._project, self.analysis_focus.focused_region_id(), wavelength
        )
