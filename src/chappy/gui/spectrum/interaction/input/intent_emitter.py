"""Typed intent emitter for spectrum interaction signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from chappy.gui.protocols.intent_types import (
    AddIdentifyTemporaryLineIntent,
    CenterOnWavelengthIntent,
    EndAbsorberDragIntent,
    ModifyAbsorberIntent,
    PanIntent,
    SelectAbsorberIntent,
    SelectRangeIntent,
    ShowContextMenuIntent,
    SpectrumInteractionIntent,
    StartAbsorberDragIntent,
    ToggleVelocityPlotIntent,
    UpdateAbsorberDragIntent,
    ZoomFactorIntent,
    ZoomRectIntent,
)

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance


@dataclass(frozen=True, slots=True)
class SpectrumIntentEmitter:
    """Dispatch typed spectrum intents to the corresponding Qt signals."""

    zoom_requested: SignalInstance
    pan_requested: SignalInstance
    range_selected: SignalInstance
    absorber_action: SignalInstance
    context_menu_requested: SignalInstance
    identify_action: SignalInstance
    center_requested: SignalInstance

    def emit(self, intent: SpectrumInteractionIntent) -> None:
        """Emit the Qt signal matching an interaction intent."""
        if isinstance(intent, ZoomRectIntent | ZoomFactorIntent):
            self.zoom_requested.emit(intent)
            return
        if isinstance(intent, PanIntent):
            self.pan_requested.emit(intent)
            return
        if isinstance(intent, SelectRangeIntent):
            self.range_selected.emit(intent)
            return
        if isinstance(
            intent,
            SelectAbsorberIntent
            | ModifyAbsorberIntent
            | StartAbsorberDragIntent
            | UpdateAbsorberDragIntent
            | EndAbsorberDragIntent,
        ):
            self.absorber_action.emit(intent)
            return
        if isinstance(intent, ShowContextMenuIntent):
            self.context_menu_requested.emit(intent)
            return
        if isinstance(intent, ToggleVelocityPlotIntent | AddIdentifyTemporaryLineIntent):
            self.identify_action.emit(intent)
            return
        if isinstance(intent, CenterOnWavelengthIntent):
            self.center_requested.emit(intent)
