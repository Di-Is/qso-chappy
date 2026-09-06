"""Mode-specific spectrum intent ports shared by spectrum and shell layers."""

from __future__ import annotations

from typing import Protocol

from chappy.gui.protocols.context_menu import ContextMenuActionIntent
from chappy.gui.protocols.intent_types import (
    AddContinuumPointIntent,
    AddIdentifyTemporaryLineIntent,
    DeleteContinuumPointIntent,
    ToggleIdentifyPreviewLockIntent,
)

type IdentifyModeIntent = (
    ContextMenuActionIntent | AddIdentifyTemporaryLineIntent | ToggleIdentifyPreviewLockIntent
)
type ContinuumModeIntent = AddContinuumPointIntent | DeleteContinuumPointIntent


class SpectrumModeIntentSink(Protocol):
    """Mode intent sink implemented by shell composition."""

    def handle_mode_click(self, wavelength: float, flux: float, modifiers: int) -> None:
        """Route a raw spectrum click to the active mode owner."""
        ...

    def handle_mode_velocity_shortcut(self) -> None:
        """Route a raw velocity shortcut to the active mode owner."""
        ...

    def handle_context_menu_intent(self, intent: ContextMenuActionIntent) -> None:
        """Route a typed context menu intent to the active mode owner."""
        ...

    def handle_continuum_intent(self, intent: ContextMenuActionIntent) -> None:
        """Route a continuum-mode context menu intent."""
        ...

    def handle_identify_intent(self, intent: IdentifyModeIntent) -> None:
        """Route an identify-mode specific intent."""
        ...
