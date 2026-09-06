"""Bridge between CommandHistory (core) and GUI layer.

This module provides the HistoryBridge class that connects the Qt-independent
CommandHistory to PySide6 GUI components via signals.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from chappy.application.history import ChangeSet, HistoryApplyError, HistoryApplyErrorCode
from chappy.application.history.apply import HistoryApplyUseCase
from chappy.core.history import HistoryState
from chappy.gui.history.refresh_adapter import (
    HistoryBridgeRefreshPort,
    HistoryMainWindowPort,
    HistoryRefreshAdapter,
    SpectrumRangeUpdatePort,
)
from chappy.gui.history.translation import translate_operation
from chappy.i18n.language_switcher import get_language_switcher

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.application.history import RangeSnapshot
    from chappy.application.spectrum import ResolutionChangeNotifier
    from chappy.core.history import CommandHistory, RedoResult, UndoResult
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.history.refresh_adapter import (
        ContinuumHistoryRefreshPort,
        DockLayoutRefreshPort,
    )


logger = logging.getLogger(__name__)


class HistoryBridge(QObject):
    """Bridge connecting CommandHistory to Qt/PySide6 GUI.

    This class:
    - Owns the HistoryApplyUseCase registered as CommandHistory's applier
    - Emits Qt signals when history state changes
    - Implements RangeHistoryPort for spectrum range history

    Signals:
        state_changed: Emitted when undo/redo availability changes.
    """

    # Qt Signals
    state_changed = Signal(HistoryState)

    def __init__(
        self,
        command_history: CommandHistory,
        parent: QObject | None = None,
        refresh_main_window: HistoryMainWindowPort | None = None,
    ) -> None:
        """Initialize the history bridge.

        Args:
            command_history: The core command history instance.
            parent: Optional parent QObject.
            refresh_main_window: Main-window refresh surface. When omitted, the
                parent must implement the refresh surface.
        """
        super().__init__(parent)
        self._command_history = command_history

        # Subscribe to history state changes
        self._command_history.subscribe(self._on_state_changed)

        self._refresh_adapter = HistoryRefreshAdapter(
            self._require_refresh_main_window(parent, refresh_main_window)
        )

        # Handler references for dispatching
        self._spectrum_range_port: SpectrumRangeUpdatePort | None = None
        self._continuum_editor: ContinuumHistoryRefreshPort | None = None
        self._dock_layout_coordinator: DockLayoutRefreshPort | None = None
        self._resolution_change_notifier_provider: (
            Callable[[], ResolutionChangeNotifier | None] | None
        ) = None
        self._project: SpectroscopyProject | None = None

        refresh_port = HistoryBridgeRefreshPort(
            self._refresh_adapter,
            project_provider=lambda: self._project,
            continuum_editor_provider=lambda: self._continuum_editor,
            dock_layout_coordinator_provider=lambda: self._dock_layout_coordinator,
        )
        self._history_apply_usecase = HistoryApplyUseCase(
            project_provider=lambda: self._project,
            range_port=self,
            refresh_port=refresh_port,
            resolution_notifier_provider=self._notify_resolution_changed_provider,
        )

        # Set the use case as the applier
        self._command_history.set_applier(self._history_apply_usecase)

        logger.debug("HistoryBridge initialized")

    @staticmethod
    def _require_refresh_main_window(
        parent: QObject | None, refresh_main_window: HistoryMainWindowPort | None
    ) -> HistoryMainWindowPort:
        """Return the required history refresh main-window port.

        Args:
            parent: Optional QObject parent.
            refresh_main_window: Explicit refresh surface.

        Returns:
            Required refresh surface.

        Raises:
            RuntimeError: If no refresh surface is wired.
        """
        if refresh_main_window is not None:
            return refresh_main_window
        if isinstance(parent, HistoryMainWindowPort):
            return parent
        msg = "HistoryBridge requires a main-window refresh port."
        raise RuntimeError(msg)

    def set_spectrum_range_port(self, port: SpectrumRangeUpdatePort) -> None:
        """Set the spectrum range port for range change operations.

        Args:
            port: The spectrum range-apply surface.
        """
        self._spectrum_range_port = port
        logger.debug("Spectrum range port connected to HistoryBridge")

    def set_continuum_editor(self, editor: ContinuumHistoryRefreshPort) -> None:
        """Set the continuum editor for continuum operations.

        Args:
            editor: The continuum editor instance.
        """
        self._continuum_editor = editor
        logger.debug("ContinuumEditor connected to HistoryBridge")

    def set_dock_layout_coordinator(self, coordinator: DockLayoutRefreshPort) -> None:
        """Set the dock layout coordinator for structure operations.

        Args:
            coordinator: The dock layout coordinator instance.
        """
        self._dock_layout_coordinator = coordinator
        logger.debug("DockLayoutCoordinator connected to HistoryBridge")

    def set_resolution_change_notifier_provider(
        self, provider: Callable[[], ResolutionChangeNotifier | None]
    ) -> None:
        """Connect the optional active-mode resolution notifier provider."""
        self._resolution_change_notifier_provider = provider

    def set_project(self, project: SpectroscopyProject | None) -> None:
        """Set the current project for group operations.

        Args:
            project: The current project instance, or None.
        """
        self._project = project
        logger.debug("Project connected to HistoryBridge: %s", project.name if project else None)

    def _notify_resolution_changed_provider(self) -> ResolutionChangeNotifier | None:
        """Return the active resolution notifier, if any is connected."""
        provider = self._resolution_change_notifier_provider
        if provider is None:
            return None
        return provider()

    def apply_range(self, snapshot: RangeSnapshot, *, source: str) -> ChangeSet:
        """Apply a spectrum range snapshot from a typed command."""
        if source != "history":
            raise HistoryApplyError(
                HistoryApplyErrorCode.INVALID_STATE, f"Unsupported range history source: {source}"
            )
        if self._spectrum_range_port is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                "Cannot apply range change without a connected spectrum range port.",
            )

        min_wave, max_wave = snapshot.wavelength_range
        self._spectrum_range_port.coordinate_range_update(
            source="history",
            min_wave=min_wave,
            max_wave=max_wave,
            flux_range=snapshot.flux_range,
            record_history=False,
        )
        return ChangeSet.empty()

    def undo(self) -> tuple[bool, str]:
        """Execute undo operation.

        Returns:
            Tuple of (success, translated_operation_name or error_reason).
        """
        return self._run_undo_or_redo(self._command_history.undo)

    def redo(self) -> tuple[bool, str]:
        """Execute redo operation.

        Returns:
            Tuple of (success, translated_operation_name or error_reason).
        """
        return self._run_undo_or_redo(self._command_history.redo)

    @staticmethod
    def _run_undo_or_redo(operation: Callable[[], UndoResult | RedoResult]) -> tuple[bool, str]:
        """Run an undo or redo operation and translate its outcome.

        Args:
            operation: Bound ``CommandHistory.undo`` or ``CommandHistory.redo``.

        Returns:
            Tuple of (success, translated_operation_name or error_reason).
        """
        try:
            result = operation()
        except HistoryApplyError as error:
            if error.error_code is HistoryApplyErrorCode.TARGET_NOT_FOUND:
                return False, str(error)
            raise
        if result.success:
            translated = translate_operation(result.operation_name, get_language_switcher())
            return True, translated
        return False, result.error_reason or "Unknown error"

    def clear(self) -> None:
        """Clear history (for session boundary)."""
        self._command_history.clear()

    def get_state(self) -> HistoryState:
        """Get current history state."""
        return self._command_history.get_state()

    def _on_state_changed(self, state: HistoryState) -> None:
        """Handle state change from CommandHistory.

        Args:
            state: New history state.
        """
        self.state_changed.emit(state)
