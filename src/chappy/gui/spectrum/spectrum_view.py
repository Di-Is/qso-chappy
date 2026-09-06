"""SpectrumView implementation following Phase 4 refactoring.

This is a clean, maintainable implementation of SpectrumView with
reduced complexity and clear separation of concerns.
"""

# ruff: noqa: D102

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QStackedLayout, QWidget

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.application.spectrum.range_usecase import RangeNavigationUseCase

# Components for simplified architecture
from chappy.gui.common.start_mode_overlay import StartModeOverlay
from chappy.gui.spectrum.interaction.input.ports import SpectrumPlotWidgetPort
from chappy.gui.spectrum.interaction.input.spectrum_input_adapter import SpectrumInputAdapter
from chappy.gui.spectrum.interaction_controller_factory import SpectrumInteractionControllerFactory
from chappy.gui.spectrum.navigation_controller import SpectrumNavigationControllerFactory
from chappy.gui.spectrum.overlay_payload_normalizer import SpectrumOverlayPayloadNormalizer
from chappy.gui.spectrum.policy import (
    SpectrumPolicy,
    SpectrumPolicyCleanupError,
    neutral_spectrum_policy,
)
from chappy.gui.spectrum.range_input_controls import SpectrumRangeInputControls
from chappy.gui.spectrum.spectrum_data_bridge import SpectrumDataBridge
from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
from chappy.gui.spectrum.spectrum_view_builder import SpectrumViewBuilder
from chappy.gui.spectrum.spectrum_view_components import SpectrumViewComponents
from chappy.gui.spectrum.velocity import SpectrumVelocityOverlayWidget, VelocityGridWidget
from chappy.i18n import LanguageSwitcher, get_language_switcher
from chappy.presentation.spectrum import SpectrumDisplayOptions
from chappy.presentation.velocity import (
    VelocityOverlayInfo,
    VelocitySelectionCreateRequest,
    build_velocity_view_data,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from PySide6.QtGui import QCloseEvent, QFocusEvent, QMouseEvent, QWheelEvent

    from chappy.core.components.absorber import AbsorberComponent
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.spectrum.spectrum_plot import SpectrumPlotHostFactory
    from chappy.plotting.overlays import AbsorptionLineRegion, IdentifyPreviewPayload
    from chappy.presentation.identify import DetectionOverlayPayload

logger = logging.getLogger(__name__)


class SpectrumView(QWidget):
    """SpectrumView focused on display responsibilities only.

    This implementation follows the Single Responsibility Principle:
    - Display: Managed by this class
    - Data: Managed by SpectrumModel via project
    - User Input: Handled by SpectrumEventDispatcher
    - Range Control: Delegated to SpectrumInteractionCoordinator

    Key features:
    - Direct dependency injection
    - Single coordinator for component orchestration
    - Clear separation of concerns
    - Minimal state management
    """

    range_changed = Signal(float, float, float, float)  # x_min, x_max, y_min, y_max

    absorber_selected = Signal(str)  # absorber_name
    velocity_plot_exit_requested = Signal()
    velocity_plot_add_requested = Signal(VelocityOverlayInfo, list)
    # Context menu request from velocity plot: velocity, line_id, rest_wavelength, center_z, x, y
    velocity_context_menu_requested = Signal(object)
    velocity_shift_click_requested = Signal(object)
    cursor_position_changed = Signal(float, float, int)  # wavelength, flux, modifiers
    cursor_left = Signal()
    identify_preview_shift_released = Signal()
    policy_applied = Signal(object)
    policy_invalidated = Signal()
    model_display_supported_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        plot_host_factory: SpectrumPlotHostFactory,
        project: SpectroscopyProject | None = None,
    ) -> None:
        """Initialize spectrum view.

        Args:
            parent: Parent widget
            plot_host_factory: Factory for plot host creation.
            project: Initial project (optional)
        """
        super().__init__(parent)

        self._language_switcher: LanguageSwitcher = get_language_switcher(self)
        self._plot_host_factory = plot_host_factory

        # Core state
        self.current_project = project
        self._plot_container: QWidget | None = None
        self._plot_stack: QStackedLayout | None = None
        self._plot_widget: QWidget | None = None
        self.start_overlay: StartModeOverlay | None = None
        self._current_policy: SpectrumPolicy | None = None
        self._velocity_widget: SpectrumVelocityOverlayWidget | None = None
        self._velocity_visible = False
        self._velocity_flux_sync_connected = False
        self._velocity_view: VelocityGridWidget | None = None
        self._velocity_overlay_info: VelocityOverlayInfo | None = None
        self._velocity_context: Literal["identify", "optimize"] = "identify"
        self._reset_wavelength_range: tuple[float, float] | None = None
        self._reset_flux_range: tuple[float, float] | None = None
        self._wavelength_fields_enabled_callback: Callable[[bool], None] | None = None
        self._tie_label_resolver: Callable[[AbsorberComponent], str | None] | None = None
        self._velocity_tie_member_resolver: Callable[[str], frozenset[str]] | None = None
        self._selected_component_id: str | None = None
        self._display_options = SpectrumDisplayOptions()

        # Setup data bridge first
        self._setup_data_bridge()

        # Setup UI components
        self._setup_components()

        # Setup coordinator
        self._setup_coordinator()

        # Build UI
        self._build_ui()

        # Connect signals
        self._connect_signals()

        # Set initial project if provided
        if project:
            self.set_project(project)

        # Set focus policy
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Initialize overlay content after UI is built
        self._initialize_overlay()

        self._language_switcher.language_changed.connect(self._apply_translations)
        self._apply_translations()

    def _setup_data_bridge(self) -> None:
        """Setup data bridge component."""
        self.data_bridge = SpectrumDataBridge()

    def _setup_coordinator(self) -> None:
        """Setup coordinator component."""
        self.coordinator = SpectrumInteractionCoordinator(
            self,
            SpectrumNavigationControllerFactory(RangeNavigationUseCase()),
            SpectrumInteractionControllerFactory(),
            SpectrumViewComponents(
                data_bridge=self.data_bridge,
                plot_host=self.plot_host,
                range_input_controls=self.range_input_controls,
                interactor=self.spectrum_input_adapter,
            ),
        )

    def _setup_components(self) -> None:
        """Setup UI components."""
        # Plot host
        self.plot_host = self._plot_host_factory.create(self)

        # Optional range input synchronization
        self.range_input_controls = SpectrumRangeInputControls(self)

        # Create SpectrumInputAdapter for MVP-Lite pattern (type-safe)
        self.spectrum_input_adapter = SpectrumInputAdapter(view=self, parent_view=self)

    def _build_ui(self) -> None:
        """Build the UI using view builder."""
        self.ui_builder = SpectrumViewBuilder(self)
        self.ui_builder.build()

    def set_wavelength_fields_enabled_callback(self, callback: Callable[[bool], None]) -> None:
        """Set the required shell callback for wavelength field availability."""
        self._wavelength_fields_enabled_callback = callback

    def set_tie_label_resolver(
        self, resolver: Callable[[AbsorberComponent], str | None] | None
    ) -> None:
        """Set the resolver used to append tie labels to velocity and wavelength marker text."""
        self._tie_label_resolver = resolver
        self.plot_host.set_tie_label_resolver(resolver)

    def set_velocity_tie_member_resolver(
        self, resolver: Callable[[str], frozenset[str]] | None
    ) -> None:
        """Set the resolver used to mirror drag overlays across redshift-tied subplots."""
        self._velocity_tie_member_resolver = resolver
        if self._velocity_view is not None:
            self._velocity_view.set_tie_member_resolver(resolver)

    def _connect_signals(self) -> None:
        """Connect component signals to view signals."""
        # Data bridge signals
        self.data_bridge.project_changed.connect(self._on_project_loaded)
        self.data_bridge.range_changed.connect(self._on_range_changed)

        # Connect interactor intent signals to coordinator (MVP-Lite pattern)
        self._connect_interactor_signals()

        # Configure spectrum actions after UI is built
        self._configure_spectrum_actions()

    def _connect_interactor_signals(self) -> None:
        """Connect interactor intent signals to coordinator/presenter."""
        # Connect intent signals to coordinator methods
        # The coordinator acts as the presenter in MVP-Lite pattern

        # Zoom intents
        self.spectrum_input_adapter.sig_zoom_requested.connect(
            self.coordinator.handle_navigation_intent
        )

        # Pan intents
        self.spectrum_input_adapter.sig_pan_requested.connect(
            self.coordinator.handle_navigation_intent
        )

        # Center on wavelength (double-click)
        self.spectrum_input_adapter.sig_center_requested.connect(
            self.coordinator.handle_navigation_intent
        )

        # Range selection
        self.spectrum_input_adapter.sig_range_selected.connect(
            self.coordinator.handle_navigation_intent
        )

        # Absorber actions
        self.spectrum_input_adapter.sig_absorber_action.connect(
            self.coordinator.coordinate_absorber_intent
        )

        # Context menu
        self.spectrum_input_adapter.sig_context_menu_requested.connect(
            self.coordinator.coordinate_context_menu
        )

        # Identify mode specific intents
        self.spectrum_input_adapter.sig_identify_action.connect(
            self.coordinator.coordinate_identify_intent
        )

        # Raw mode clicks
        self.spectrum_input_adapter.sig_mode_click_requested.connect(
            self.coordinator.coordinate_mode_click
        )
        self.spectrum_input_adapter.sig_mode_velocity_shortcut_requested.connect(
            self.coordinator.coordinate_mode_velocity_shortcut
        )

        # Cursor tracking
        self.spectrum_input_adapter.sig_cursor_position_changed.connect(
            self._on_cursor_position_changed
        )
        self.spectrum_input_adapter.sig_cursor_left.connect(self._on_cursor_left)
        self.spectrum_input_adapter.sig_identify_preview_shift_released.connect(
            self.identify_preview_shift_released
        )

        logger.debug("Interactor intent signals connected to coordinator")

    def _configure_spectrum_actions(self) -> None:
        """Configure spectrum interactor with plot widget after UI is built."""
        # Get the plot widget from plot host
        if self.plot_host.plot_widget:
            if not isinstance(self.plot_host.plot_widget, SpectrumPlotWidgetPort):
                msg = "Plot widget must satisfy SpectrumInputAdapter's plot widget port."
                raise TypeError(msg)
            # Set it on the interactor for coordinate transforms
            self.spectrum_input_adapter.attach_plot_widget(self.plot_host.plot_widget)
            canvas = self.plot_host.plot_widget.canvas
            if isinstance(canvas, QObject):
                canvas.installEventFilter(self)

            logger.debug("Plot widget set on spectrum interactor")

    def _on_project_loaded(self, project: SpectroscopyProject | None) -> None:
        """Handle project loaded signal."""
        if project is not self.current_project and self._velocity_widget is not None:
            self._velocity_widget.clear_display_range_session()
        self.current_project = project

    def _on_range_changed(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        """Handle range changed signal."""
        self.range_changed.emit(x_min, x_max, y_min, y_max)

    def update_plot(self) -> None:
        """Update the plot display."""
        if self.plot_host:
            self.plot_host.refresh_plot()

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Set the current project.

        Args:
            project: The project or None
        """
        if project is not self.current_project and self._velocity_widget is not None:
            self._velocity_widget.clear_display_range_session()
        self.current_project = project
        if self.data_bridge:
            self.data_bridge.set_project(project)
        if not project and self.start_overlay:
            self.start_overlay.set_status_message(None)
        if self._velocity_view:
            self._refresh_velocity_view_data()

    def apply_policy(self, policy: SpectrumPolicy) -> None:
        """Preflight, clean up, and atomically commit one complete policy."""
        self.coordinator.preflight_policy(policy)
        self.plot_host.preflight_policy(policy.plot_policy)
        previous = self._current_policy or neutral_spectrum_policy()
        SpectrumView._run_policy_cleanup(self, policy)
        try:
            self.plot_host.apply_policy(policy.plot_policy)
            self.coordinator.commit_policy(policy)
            self.set_start_mode_active(policy.start_overlay_active)
        except Exception as original_error:
            try:
                self.plot_host.apply_policy(previous.plot_policy)
                self.coordinator.commit_policy(previous)
                self.set_start_mode_active(previous.start_overlay_active)
            except Exception as rollback_error:
                original_error.add_note(
                    "Spectrum policy rollback failed: "
                    f"{type(rollback_error).__name__}: {rollback_error}"
                )
                self.coordinator.invalidate_policy()
                self.plot_host.invalidate_policy()
                self._current_policy = None
                run_postcommit_actions_isolated(self.policy_invalidated.emit)
                raise original_error from rollback_error
            self._current_policy = previous
            raise
        self._current_policy = policy
        run_postcommit_actions_isolated(lambda: self.policy_applied.emit(policy))
        run_postcommit_actions_isolated(
            lambda: self.model_display_supported_changed.emit(
                policy.plot_policy.show_model_and_residual
            )
        )

    def _run_policy_cleanup(self, policy: SpectrumPolicy) -> None:
        """Run the irreversible cleanup boundary before reversible policy commit.

        Every declared cleanup stage is attempted. Any failures are aggregated,
        and no reversible policy state is committed afterward.
        """
        errors: list[Exception] = []
        try:
            self.coordinator.cleanup_for_policy(policy)
        except SpectrumPolicyCleanupError as error:
            errors.extend(error.errors)
        except Exception as error:  # noqa: BLE001 - aggregate cleanup boundary failures
            errors.append(error)
        if policy.transition_cleanup.clear_reset_ranges:
            try:
                self.clear_reset_ranges()
            except Exception as error:  # noqa: BLE001 - aggregate cleanup boundary failures
                errors.append(error)
        if errors:
            raise SpectrumPolicyCleanupError(tuple(errors))

    @property
    def current_policy(self) -> SpectrumPolicy | None:
        """Return the last fully applied spectrum policy."""
        return self._current_policy

    def set_start_mode_active(self, active: bool) -> None:
        """Show or hide the start overlay and spectrum plot."""
        stack = self._plot_stack
        plot_widget = self._plot_widget
        overlay = self.start_overlay
        if stack is None or plot_widget is None or overlay is None:
            return

        target_widget = overlay if active else plot_widget
        if stack.currentWidget() is not target_widget:
            stack.setCurrentWidget(target_widget)

        if active and self.plot_host:
            self.plot_host.clear_plot_data()
            self._disconnect_velocity_flux_sync()
            self._velocity_visible = False
        if not active:
            overlay.set_status_message(None)

    def set_start_mode_drop_target(self, drop_target: QWidget | None) -> None:
        """Set the explicit drag-and-drop target for the start-mode overlay."""
        if self.start_overlay is None:
            return
        self.start_overlay.set_drop_target(drop_target)

    def _initialize_overlay(self) -> None:
        if not self._plot_stack or not self._plot_container:
            return
        if self.start_overlay is not None:
            return

        self.start_overlay = StartModeOverlay(self._plot_container)
        self._plot_stack.addWidget(self.start_overlay)
        self._configure_overlay_text()
        self._plot_stack.setCurrentWidget(self.start_overlay)

    def _ensure_velocity_widget(self) -> SpectrumVelocityOverlayWidget:
        if self._velocity_widget and self._plot_stack:
            return self._velocity_widget

        if not self._plot_container or not self._plot_stack:
            msg = "Velocity widget requested before plot container initialised"
            raise RuntimeError(msg)

        container = SpectrumVelocityOverlayWidget(self._plot_container)
        container.add_requested.connect(self._handle_velocity_add_clicked)
        container.exit_requested.connect(self.velocity_plot_exit_requested.emit)

        self._velocity_view = container.grid_widget
        self._velocity_view.set_tie_member_resolver(self._velocity_tie_member_resolver)
        self._refresh_velocity_view_data()

        # Connect velocity view D&D signals to interactor
        if self.spectrum_input_adapter:
            self.spectrum_input_adapter.connect_velocity_view(self._velocity_view)

        # Forward velocity view context menu signal to SpectrumView level
        self._velocity_view.sig_context_menu_requested.connect(
            self.velocity_context_menu_requested.emit
        )
        # Forward velocity view Shift+click signal to SpectrumView level
        self._velocity_view.sig_shift_click_requested.connect(
            self.velocity_shift_click_requested.emit
        )

        self._plot_stack.addWidget(container)
        self._velocity_widget = container

        return container

    def register_plot_container(
        self, container: QWidget, stack: QStackedLayout, plot_widget: QWidget
    ) -> None:
        """Register the plot container widget built by the view builder."""
        self._plot_container = container
        self._plot_stack = stack
        self._plot_widget = plot_widget

    def set_velocity_plot_active(
        self,
        active: bool,
        info: VelocityOverlayInfo | None = None,
        context: Literal["identify", "optimize"] = "identify",
    ) -> None:
        if not self._plot_stack:
            return

        if active:
            self._activate_velocity_plot(info, context)
            return

        self._deactivate_velocity_plot()

    def _activate_velocity_plot(
        self,
        info: VelocityOverlayInfo | None,
        context: Literal["identify", "optimize"] = "identify",
    ) -> None:
        widget = self._ensure_velocity_widget()

        details = self._build_velocity_overlay_parts(info)
        self._velocity_overlay_info = info
        self._velocity_context = context
        widget.set_mode(context)

        if self._velocity_view:
            self._velocity_view.set_mode(context)

            # P4-D: モード別UI制御 - チェックボックスの表示/非表示
            is_identify = context == "identify"
            self._velocity_view.set_selection_controls_visible(is_identify)
            self._velocity_view.set_tie_member_resolver(
                self._velocity_tie_member_resolver if context == "optimize" else None
            )

            widget.set_context_parts(details)
            if info and info.rest_wavelength is not None:
                self._velocity_view.set_rest_wavelength(info.rest_wavelength)
            if info and info.center_z is not None:
                self._velocity_view.set_center_redshift(info.center_z)
            if (
                info is None
                or info.display_range_scope_key is None
                or not info.analysis_half_widths_kms
            ):
                msg = "Velocity overlay requires a display scope and analysis ranges."
                raise ValueError(msg)
            widget.activate_display_range(
                scope_key=info.display_range_scope_key,
                analysis_half_widths_kms=info.analysis_half_widths_kms,
            )
            self._refresh_velocity_view_data()
            self._velocity_view.refresh_plot()

        # P4-D: モード別UI制御 - 同定ボタンの表示/非表示と有効化
        is_identify = context == "identify"
        widget.set_create_visible(is_identify)
        if is_identify:
            widget.set_create_enabled(bool(info and info.slices))

        self._refresh_velocity_overlay_context()

        stack = self._plot_stack
        if stack is not None:
            stack.setCurrentWidget(widget)
        self._connect_velocity_flux_sync()
        self._velocity_visible = True

        self._set_wavelength_fields_enabled(False)

    def _build_velocity_overlay_parts(self, info: VelocityOverlayInfo | None) -> list[str]:
        """Build context text fragments for the velocity overlay header."""
        if info is None:
            return []

        parts: list[str] = []
        if info.center_z is not None:
            template = self.tr("z = {value:.4f}")
            parts.append(template.format(value=info.center_z))
        return parts

    def _refresh_velocity_overlay_context(self) -> None:
        if self._velocity_widget is None:
            return

        if self._velocity_overlay_info is None:
            self._velocity_widget.clear_context()
            return

        # 最適化モードでは情報ラベルを表示しない
        is_optimize = self._velocity_context == "optimize"
        if is_optimize:
            details: list[str] = []
        else:
            details = self._build_velocity_overlay_parts(self._velocity_overlay_info)

        self._velocity_widget.set_context_parts(details)

    def _apply_translations(self) -> None:
        self._refresh_velocity_overlay_context()

    def _deactivate_velocity_plot(self) -> None:
        self._cancel_velocity_interactions()
        self._disconnect_velocity_flux_sync()

        plot_widget = self._plot_widget
        stack = self._plot_stack
        if plot_widget is not None and stack is not None:
            stack.setCurrentWidget(plot_widget)
        self._velocity_visible = False
        if self._velocity_widget is not None:
            self._velocity_widget.clear_context()
            self._velocity_widget.set_create_enabled(False)
            self._velocity_widget.clear_display_range_session()
        if self._velocity_view is not None:
            self._velocity_view.reset_selection_state()
            self._velocity_view.reset_manual_y_range()

        self._velocity_overlay_info = None
        self._velocity_context = "identify"

        self._refresh_velocity_overlay_context()

        self._set_wavelength_fields_enabled(True)

    def _set_wavelength_fields_enabled(self, enabled: bool) -> None:
        """Apply wavelength field availability through the required shell port."""
        callback = self._wavelength_fields_enabled_callback
        if callback is None:
            msg = "Velocity plot requires a wavelength fields enabled callback."
            raise RuntimeError(msg)
        callback(enabled)

    def _cancel_velocity_interactions(self) -> None:
        """Cancel transient interactions owned by the velocity overlay."""
        self.coordinator.cancel_active_drags()

        self.spectrum_input_adapter.cancel_active_absorber_drag(reason="velocity-plot-closed")

        if self._velocity_view is not None:
            self._velocity_view.cancel_active_drag()

    def is_velocity_plot_visible(self) -> bool:
        return self._velocity_visible

    def get_velocity_plot_y_range(self) -> tuple[float, float] | None:
        """Get Y range from velocity plot if visible.

        Returns:
            Tuple of (y_min, y_max) with margins, or None if not visible or no data.
        """
        if self._velocity_view and self._velocity_visible:
            return self._velocity_view.get_global_observed_y_range()
        return None

    def get_velocity_overlay_info(self) -> VelocityOverlayInfo | None:
        """Return the current velocity overlay info if velocity plot is visible."""
        if self._velocity_visible:
            return self._velocity_overlay_info
        return None

    @property
    def velocity_view(self) -> VelocityGridWidget | None:
        """Return the velocity view widget if available."""
        return self._velocity_view

    def apply_display_options(self, options: SpectrumDisplayOptions) -> None:
        """Apply the user's spectrum display toggles to every spectrum surface."""
        self._display_options = options
        self.plot_host.apply_display_options(options)
        if self._velocity_visible:
            self._refresh_velocity_view_data()

    @property
    def display_options(self) -> SpectrumDisplayOptions:
        """Return the display toggles last applied to this view."""
        return self._display_options

    def _refresh_velocity_view_data(self) -> None:
        """Refresh the active velocity view's non-Qt data package."""
        if self._velocity_view is None:
            return

        overlay_info = self._velocity_overlay_info
        slices = overlay_info.slices if overlay_info is not None else []
        selection_scope_key = (
            overlay_info.selection_scope_key if overlay_info is not None else None
        )
        display_half_width_kms = self._velocity_view.display_half_width.value
        effective = self.plot_host.display_command
        self._velocity_view.apply_view_data(
            build_velocity_view_data(
                self.current_project,
                slices,
                selection_scope_key=selection_scope_key,
                display_half_width_kms=display_half_width_kms,
                include_optimize_overlays=self._velocity_context == "optimize",
                tie_label_resolver=(
                    self._tie_label_resolver if self._velocity_context == "optimize" else None
                ),
                display_options=SpectrumDisplayOptions(
                    show_error_spectrum=effective.show_error_spectrum,
                    show_component_profiles=effective.show_component_profiles,
                ),
                emphasized_component_id=self._selected_component_id,
            )
        )

    def _handle_velocity_add_clicked(self, request: VelocitySelectionCreateRequest) -> None:
        if not self._velocity_view:
            return
        overlay = self._velocity_overlay_info
        self.velocity_plot_add_requested.emit(overlay, list(request.selections))

    def _configure_overlay_text(self) -> None:
        if not self.start_overlay:
            return

        self.start_overlay.use_default_messages()
        self.start_overlay.set_status_message(None)

    def get_wavelength_range(self) -> tuple[float, float]:
        """Get current wavelength display range.

        Returns:
            Tuple of (min_wavelength, max_wavelength)
        """
        if self.data_bridge:
            return self.data_bridge.get_wavelength_range()
        msg = "Data bridge is required before reading wavelength range."
        raise RuntimeError(msg)

    def get_flux_range(self) -> tuple[float, float]:
        """Get current flux display range.

        Returns:
            Tuple of (min_flux, max_flux)
        """
        if self.data_bridge:
            return self.data_bridge.get_flux_range()
        msg = "Data bridge is required before reading flux range."
        raise RuntimeError(msg)

    def _has_spectrum_data(self) -> bool:
        """Return whether user navigation can read required spectrum ranges."""
        return bool(self.data_bridge and self.data_bridge.get_spectrum_data() is not None)

    def set_wavelength_range(self, min_wave: float, max_wave: float) -> None:
        """Set the wavelength range for display.

        Args:
            min_wave: Minimum wavelength
            max_wave: Maximum wavelength
        """
        if self.data_bridge:
            self.data_bridge.set_wavelength_range(min_wave, max_wave)

    def set_flux_range(self, min_flux: float, max_flux: float) -> None:
        """Set the flux range for display.

        Args:
            min_flux: Minimum flux value.
            max_flux: Maximum flux value.
        """
        if self.data_bridge:
            self.data_bridge.set_flux_range(min_flux, max_flux)

    def _connect_velocity_flux_sync(self) -> None:
        """Mirror flux-range changes into the velocity grid while it is shown."""
        if self._velocity_flux_sync_connected:
            return
        self.data_bridge.range_changed.connect(self._sync_velocity_flux_range)
        self._velocity_flux_sync_connected = True

    def _disconnect_velocity_flux_sync(self) -> None:
        """Stop mirroring flux-range changes once the velocity grid is hidden."""
        if not self._velocity_flux_sync_connected:
            return
        self.data_bridge.range_changed.disconnect(self._sync_velocity_flux_range)
        self._velocity_flux_sync_connected = False

    def _sync_velocity_flux_range(
        self, _min_wave: float, _max_wave: float, min_flux: float, max_flux: float
    ) -> None:
        """Apply the shared flux range to the visible velocity grid."""
        if self._velocity_view is not None:
            self._velocity_view.set_flux_range(min_flux, max_flux)

    def set_reset_ranges(
        self, wavelength_range: tuple[float, float] | None, flux_range: tuple[float, float] | None
    ) -> None:
        """Store reset ranges applied when auto-range is requested."""
        if wavelength_range is None or wavelength_range[0] >= wavelength_range[1]:
            self._reset_wavelength_range = None
            self._reset_flux_range = None
            return

        self._reset_wavelength_range = (float(wavelength_range[0]), float(wavelength_range[1]))

        if flux_range and flux_range[0] < flux_range[1]:
            self._reset_flux_range = (float(flux_range[0]), float(flux_range[1]))
        elif self.plot_host:
            _xmin, _xmax, ymin, ymax = self.plot_host.get_plot_range()
            if ymin < ymax:
                self._reset_flux_range = (float(ymin), float(ymax))
            else:
                self._reset_flux_range = None
        else:
            self._reset_flux_range = None

    def clear_reset_ranges(self) -> None:
        """Clear any stored reset ranges."""
        self._reset_wavelength_range = None
        self._reset_flux_range = None

    def get_reset_ranges(self) -> tuple[tuple[float, float], tuple[float, float] | None] | None:
        """Return the stored reset wavelength/flux ranges if available."""
        if not self._reset_wavelength_range:
            return None
        return (self._reset_wavelength_range, self._reset_flux_range)

    def set_identify_preview(
        self, preview: Mapping[str, object] | IdentifyPreviewPayload | None
    ) -> None:
        """Send identify-mode cursor preview payload to the plot host.

        Args:
            preview: Identify preview payload collected from the coordinator.
        """
        normalized = SpectrumOverlayPayloadNormalizer.normalize_identify_preview(preview)
        if self.plot_host:
            self.plot_host.set_identify_preview(normalized)

    def wavelength_under_cursor(self) -> float | None:
        """Return the spectrum wavelength under the pointer."""
        return self.spectrum_input_adapter.wavelength_under_cursor()

    def set_detection_regions(self, regions: list[DetectionOverlayPayload]) -> None:
        """Forward detection region overlays to the plot host."""
        if self.plot_host:
            self.plot_host.set_detection_regions(regions)

    def set_selected_component_id(self, component_id: str | None) -> None:
        """Record and forward the absorber component emphasised across spectrum surfaces.

        Args:
            component_id: Identifier of the component to emphasise, or ``None`` to clear.
        """
        self._selected_component_id = component_id
        if self.plot_host:
            self.plot_host.set_selected_component_id(component_id)
        if self._velocity_visible:
            self._refresh_velocity_view_data()

    def set_absorption_line_regions(
        self, regions: Sequence[Mapping[str, object]] | Sequence[AbsorptionLineRegion] | None
    ) -> None:
        """Forward absorption line overlays to the plot host.

        Args:
            regions: Overlay payloads describing line spans.
        """
        normalized = SpectrumOverlayPayloadNormalizer.normalize_absorption_regions(regions)
        if self.plot_host:
            self.plot_host.set_absorption_line_regions(normalized)

    def auto_range(self) -> None:
        """Auto-range the plot to fit stored reset ranges or all data."""
        if self.data_bridge and self._reset_wavelength_range:
            min_wave, max_wave = self._reset_wavelength_range
            self.data_bridge.set_wavelength_range(min_wave, max_wave)

            if self._reset_flux_range:
                min_flux, max_flux = self._reset_flux_range
                self.data_bridge.set_flux_range(min_flux, max_flux)
            # Preserve current flux span when no flux reset was stored
            elif self.plot_host:
                _xmin, _xmax, min_flux, max_flux = self.plot_host.get_plot_range()
                if min_flux < max_flux:
                    self.data_bridge.set_flux_range(min_flux, max_flux)

            if self.plot_host:
                if self._reset_flux_range:
                    min_flux, max_flux = self._reset_flux_range
                else:
                    _xmin, _xmax, min_flux, max_flux = self.plot_host.get_plot_range()
                self.plot_host.set_plot_range(min_wave, max_wave, min_flux, max_flux)
            return

        if self.plot_host:
            self.plot_host.auto_range_all()

    def refresh(self) -> None:
        """Refresh the entire view."""
        # Refresh data
        if self.data_bridge and self.data_bridge.project:
            self.data_bridge.project.model.update_model()

        # Refresh display
        if self.plot_host:
            self.plot_host.refresh_plot()

    def refresh_selected_region_model_residual(self, region_id: str) -> bool:
        """Re-slice selected-region model/residual curves without model recalculation."""
        return self.plot_host.refresh_selected_region_model_residual(region_id)

    @property
    def spectrum_plot(self) -> QWidget | None:
        """Get spectrum plot widget."""
        if not self.plot_host:
            return None
        widget = self.plot_host.plot_widget
        return widget if isinstance(widget, QWidget) else None

    # Event handling
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events.

        Args:
            event: Key event
        """
        # Keep the mode-owned V toggle, but do not let other keys navigate the hidden spectrum.
        if self._velocity_visible and not (
            event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            event.accept()
            return

        # Route to SpectrumInputAdapter
        if self.spectrum_input_adapter and self._has_spectrum_data():
            logger.debug("Routing key event to SpectrumInputAdapter: key=%s", event.key())
            self.spectrum_input_adapter.process_key_event(event)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Clear transient Identify Shift state without requiring pointer movement."""
        if self._handle_key_release_event(event):
            event.accept()
            return

        super().keyReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route key releases from the focused Matplotlib canvas to mode input."""
        if (
            event.type() == QEvent.Type.KeyRelease
            and isinstance(event, QKeyEvent)
            and self._handle_key_release_event(event)
        ):
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _handle_key_release_event(self, event: QKeyEvent) -> bool:
        """Delegate supported release events to the typed spectrum input adapter."""
        return bool(
            self.spectrum_input_adapter
            and self._has_spectrum_data()
            and self.spectrum_input_adapter.handle_key_release_event(event)
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events.

        Args:
            event: Mouse move event
        """
        # Route to SpectrumInputAdapter
        interactor = self.spectrum_input_adapter
        if interactor and interactor.handle_mouse_move_event(event):
            event.accept()
            return

        super().mouseMoveEvent(event)

    def _on_cursor_position_changed(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Relay cursor coordinates to listeners."""
        self.cursor_position_changed.emit(wavelength, flux, modifiers)

    def _on_cursor_left(self) -> None:
        """Notify listeners that the cursor exited the spectrum plot."""
        self.coordinator.reset_optimize_cursor()
        self.cursor_left.emit()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Handle focus in events.

        Args:
            event: Focus event
        """
        super().focusInEvent(event)

        # Update UI for focus
        if self.plot_host:
            plot_widget = self.plot_host.plot_widget
            if isinstance(plot_widget, QWidget):
                plot_widget.setFocus()

    def set_continuum_visibility(self, visible: bool) -> None:
        """Set continuum visibility.

        Args:
            visible: Whether continuum should be visible
        """
        if self.plot_host:
            self.plot_host.set_continuum_visibility(visible)

    def update_continuum_display(self) -> None:
        """Update continuum display."""
        if self.plot_host:
            self.plot_host.update_continuum_display()

    def ensure_continuum_reference_line(self) -> None:
        """Ensure the continuum reference line is visible."""
        if self.plot_host:
            self.plot_host.ensure_continuum_reference_line()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle wheel events.

        Args:
            event: Wheel event
        """
        # Wheel gestures over the velocity surface must not navigate the hidden spectrum.
        if self._velocity_visible:
            event.accept()
            return

        # New route: SpectrumInputAdapter (priority)
        if self.spectrum_input_adapter and self._has_spectrum_data():
            self.spectrum_input_adapter.process_mouse_event(event)
            event.accept()
            return

        # Fallback to default handling
        super().wheelEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle close events.

        Args:
            event: Close event
        """
        super().closeEvent(event)
