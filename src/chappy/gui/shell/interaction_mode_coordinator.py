"""Own spectrum interaction policy and snapshot routing for shell modes."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    ContinuumContext,
    InteractionChannel,
    InteractionPhase,
    MaskSelectionContext,
    RectZoomContext,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.core.editing_mode import EditingMode
    from chappy.gui.spectrum.interaction_state_coordinator import SpectrumInteractionSnapshot
    from chappy.gui.spectrum.policy import SpectrumPolicy
    from chappy.gui.spectrum.spectrum_interaction_coordinator import SpectrumInteractionCoordinator
    from chappy.gui.spectrum.spectrum_view import SpectrumView

logger = logging.getLogger(__name__)


class InteractionModeCoordinator:
    """Connect shell mode changes to spectrum interaction policy."""

    def __init__(
        self,
        *,
        spectrum_view_provider: Callable[[], SpectrumView],
        current_mode_provider: Callable[[], EditingMode],
        zoom_button_callback: Callable[[bool], None],
        mode_display_callback: Callable[[EditingMode], None],
    ) -> None:
        """Store interaction policy dependencies."""
        self._spectrum_view_provider = spectrum_view_provider
        self._current_mode_provider = current_mode_provider
        self._zoom_button_callback = zoom_button_callback
        self._mode_display_callback = mode_display_callback
        self._presenter: SpectrumInteractionCoordinator | None = None
        self._latest_interaction_snapshot: SpectrumInteractionSnapshot | None = None
        self._requested_interaction_mode: str | None = None

    @property
    def latest_interaction_snapshot(self) -> SpectrumInteractionSnapshot | None:
        """Return the latest interaction snapshot tracked by the shell."""
        return self._latest_interaction_snapshot

    @property
    def requested_interaction_mode(self) -> str | None:
        """Return the pending interaction-mode request, if any."""
        return self._requested_interaction_mode

    def connect_presenter(self) -> None:
        """Connect the current spectrum presenter to interaction handlers."""
        presenter = self._spectrum_view_provider().coordinator
        if self._presenter is presenter:
            return

        if self._presenter is not None:
            with contextlib.suppress(TypeError):
                self._presenter.mode_command_requested.disconnect(self.handle_mode_command)
            with contextlib.suppress(TypeError):
                self._presenter.interaction_snapshot_applied.disconnect(
                    self.handle_interaction_snapshot
                )

        self._presenter = presenter
        presenter.mode_command_requested.connect(self.handle_mode_command)
        presenter.interaction_snapshot_applied.connect(self.handle_interaction_snapshot)

        mode_name: str | None = None
        if self._latest_interaction_snapshot is not None:
            mode_name = self._get_mode_name_from_snapshot(self._latest_interaction_snapshot)
        elif self._requested_interaction_mode is not None:
            mode_name = self._requested_interaction_mode
        else:
            mode_name = "rect_zoom" if presenter.is_rect_zoom_mode_enabled() else None
        presenter.set_interaction_mode(mode_name)

    def handle_zoom_rect_mode(self, enable: bool) -> None:
        """Enable or disable rectangle zoom interaction mode."""
        if enable:
            self._set_interaction_mode("rect_zoom")
        else:
            self._set_interaction_mode(None)
        self._zoom_button_callback(enable)

    def apply_policy(self, policy: SpectrumPolicy) -> None:
        """Apply a complete policy through the spectrum view entrypoint."""
        spectrum_view = self._spectrum_view_provider()
        spectrum_view.apply_policy(policy)

    def handle_policy_committed(self, policy: SpectrumPolicy) -> None:
        """Discard shell observation caches after view-owned cleanup commits."""
        if not policy.transition_cleanup.clear_interaction_mode:
            return
        self._requested_interaction_mode = None
        self._latest_interaction_snapshot = None
        self._zoom_button_callback(False)

    def handle_policy_invalidated(self) -> None:
        """Clear shell observation caches when the view policy becomes unknown."""
        self._requested_interaction_mode = None
        self._latest_interaction_snapshot = None
        self._zoom_button_callback(False)

    def handle_mode_command(self, command: str) -> None:
        """Process high-level mode commands emitted by the presenter."""
        current_mode = self._current_mode_provider()
        snapshot_info = (
            f"{self._latest_interaction_snapshot.channel.value}/"
            f"{self._latest_interaction_snapshot.phase.value}"
            if self._latest_interaction_snapshot
            else "none"
        )
        logger.debug(
            "Processing mode command %s (current mode: %s, snapshot: %s)",
            command,
            current_mode,
            snapshot_info,
        )
        if command == "disable_rect_zoom":
            self.handle_zoom_rect_mode(False)

    def handle_interaction_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Handle a presenter interaction snapshot."""
        if snapshot.channel is InteractionChannel.RECT_ZOOM:
            self._handle_rect_zoom_snapshot(snapshot)
            return
        if snapshot.channel is InteractionChannel.ABSORBER_DRAG:
            self._handle_absorber_drag_snapshot(snapshot)
            return
        if snapshot.channel is InteractionChannel.MASK_SELECTION:
            self._handle_mask_selection_snapshot(snapshot)
            return
        if snapshot.channel is InteractionChannel.CONTINUUM:
            self._handle_continuum_snapshot(snapshot)
            return
        self._raise_unhandled_interaction_snapshot_channel(snapshot.channel)

    def _handle_rect_zoom_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        self._require_snapshot_context_type(
            snapshot,
            expected_type=RectZoomContext,
            channel_name=InteractionChannel.RECT_ZOOM.value,
        )
        self._latest_interaction_snapshot = snapshot
        self._requested_interaction_mode = self._get_mode_name_from_snapshot(snapshot)
        is_active = snapshot.phase in {InteractionPhase.ARMED, InteractionPhase.ACTIVE}
        self._zoom_button_callback(is_active)
        if (
            not is_active
            and self._presenter is not None
            and self._presenter.is_rect_zoom_mode_enabled()
        ):
            self._presenter.set_interaction_mode(None)
        self._log_rect_zoom_snapshot(snapshot)

    def _handle_absorber_drag_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        self._require_snapshot_context_type(
            snapshot,
            expected_type=AbsorberDragContext,
            channel_name=InteractionChannel.ABSORBER_DRAG.value,
        )
        self._latest_interaction_snapshot = snapshot
        self._requested_interaction_mode = None
        self._log_absorber_drag_snapshot(snapshot)

    def _handle_mask_selection_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        self._require_snapshot_context_type(
            snapshot,
            expected_type=MaskSelectionContext,
            channel_name=InteractionChannel.MASK_SELECTION.value,
        )
        self._latest_interaction_snapshot = snapshot
        self._requested_interaction_mode = None

    def _handle_continuum_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        self._require_snapshot_context_type(
            snapshot,
            expected_type=ContinuumContext,
            channel_name=InteractionChannel.CONTINUUM.value,
        )
        self._latest_interaction_snapshot = snapshot
        self._requested_interaction_mode = None

    @staticmethod
    def _require_snapshot_context_type(
        snapshot: SpectrumInteractionSnapshot,
        *,
        expected_type: type[
            RectZoomContext | AbsorberDragContext | MaskSelectionContext | ContinuumContext
        ],
        channel_name: str,
    ) -> None:
        """Ensure that snapshot context matches its interaction channel."""
        context = snapshot.context
        if context is None or isinstance(context, expected_type):
            return
        msg = (
            f"Snapshot context for {channel_name} must be "
            f"{expected_type.__name__}, got {type(context).__name__}."
        )
        raise TypeError(msg)

    @staticmethod
    def _raise_unhandled_interaction_snapshot_channel(channel: InteractionChannel) -> None:
        """Raise for an interaction channel without a shell handler."""
        msg = f"Unhandled interaction snapshot channel: {channel.value}"
        raise ValueError(msg)

    @staticmethod
    def _is_terminal_phase(phase: InteractionPhase) -> bool:
        """Return whether the phase represents a finished interaction."""
        return phase in (InteractionPhase.IDLE, InteractionPhase.CANCELLED)

    def _get_mode_name_from_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> str | None:
        """Return the legacy interaction mode name for a snapshot."""
        if self._is_terminal_phase(snapshot.phase):
            return None
        if snapshot.channel is InteractionChannel.RECT_ZOOM:
            return "rect_zoom"
        return None

    def _set_interaction_mode(self, mode_name: str | None) -> None:
        """Synchronize presenter/UI with the active interaction sub-mode."""
        logger.debug("Interaction sub-mode set to: %s", mode_name)
        self._requested_interaction_mode = mode_name
        if mode_name is None:
            self._clear_interaction_snapshot()
        if self._presenter is not None:
            self._presenter.set_interaction_mode(mode_name)
        self._mode_display_callback(self._current_mode_provider())

    def _clear_interaction_snapshot(self) -> None:
        """Clear cached interaction snapshot to prevent stale reapplication."""
        if self._latest_interaction_snapshot is None:
            return
        snapshot = self._latest_interaction_snapshot
        logger.debug(
            "Clearing interaction snapshot",
            extra={
                "channel": snapshot.channel.value,
                "phase": snapshot.phase.value,
                "interaction_id": snapshot.interaction_id,
            },
        )
        self._latest_interaction_snapshot = None

    def _log_rect_zoom_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Emit diagnostic logs for rectangle zoom snapshots."""
        phase = snapshot.phase
        context = snapshot.context
        if context is not None and not isinstance(context, RectZoomContext):
            msg = f"Rect zoom log context must be RectZoomContext, got {type(context).__name__}."
            raise TypeError(msg)
        payload: dict[str, object] = {
            "interaction_id": snapshot.interaction_id,
            "phase": phase.value,
        }
        if context and context.start:
            payload["start"] = list(context.start)
        if context and context.current:
            payload["current"] = list(context.current)
        if context and context.end:
            payload["end"] = list(context.end)

        if phase is InteractionPhase.CANCELLED:
            logger.info("🛑 Mode coordinator received rect zoom cancellation", extra=payload)
            return
        if phase is InteractionPhase.IDLE:
            logger.info("✅ Mode coordinator applied rect zoom completion", extra=payload)
            return
        logger.debug("📐 Mode coordinator tracking rect zoom", extra=payload)

    def _log_absorber_drag_snapshot(self, snapshot: SpectrumInteractionSnapshot) -> None:
        """Emit diagnostic logs for absorber drag snapshots."""
        phase = snapshot.phase
        context = snapshot.context
        if context is not None and not isinstance(context, AbsorberDragContext):
            msg = (
                "Absorber drag log context must be "
                f"AbsorberDragContext, got {type(context).__name__}."
            )
            raise TypeError(msg)
        payload: dict[str, object] = {
            "interaction_id": snapshot.interaction_id,
            "phase": phase.value,
        }
        if context and context.absorber_id:
            payload["absorber_id"] = context.absorber_id
        if context and context.start:
            payload["start"] = list(context.start)
        if context and context.current:
            payload["current"] = list(context.current)
        if context and context.end:
            payload["end"] = list(context.end)
        if context and context.cancel_reason:
            payload["reason"] = context.cancel_reason

        if phase is InteractionPhase.CANCELLED:
            logger.info("🛑 Mode coordinator received absorber drag cancellation", extra=payload)
            return
        if phase is InteractionPhase.IDLE:
            logger.info("✅ Mode coordinator applied absorber drag completion", extra=payload)
            return
        logger.debug("🎯 Mode coordinator tracking absorber drag", extra=payload)


__all__ = ["InteractionModeCoordinator"]
