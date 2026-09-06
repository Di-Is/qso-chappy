"""Shell-facing ports consumed by identify mode composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from chappy.gui.modes.identify.detection_controller import IdentifyDetectionOverlayPort

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from chappy.application.history import AbsorptionRegionSnapshot
    from chappy.application.identify import TemporaryLineSnapshot
    from chappy.core.editing_mode import EditingMode
    from chappy.core.identify_state import IdentifySessionState
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
    from chappy.gui.modes.identify.runtime import IdentifyVelocityOverlayRuntimePort
    from chappy.gui.utils.absorption_overlays import RegionPayload
    from chappy.presentation.identify import CursorPreviewPayload


@runtime_checkable
class IdentifyModeStateProvider(Protocol):
    """Mode state operations required by identify workflows."""

    @property
    def current_mode(self) -> EditingMode:
        """Return the active editing mode."""
        ...


@runtime_checkable
class IdentifyHistoryRecorder(Protocol):
    """History operations required by identify workflows."""

    def atomic_recording(self) -> AbstractContextManager[None]:
        """Return a rollback scope for one atomic scientific command."""
        ...

    def record_ident_add_temporary_line(
        self, session: IdentifySessionState, _added_temporary_line_ids: list[str]
    ) -> None:
        """Record identify temporary-line creation."""
        ...

    def record_ident_remove_temporary_line(
        self, _removed_temporary_line_ids: list[str], snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> None:
        """Record identify temporary-line removal."""
        ...

    def record_ident_clear_temporary_lines(
        self, snapshots: tuple[TemporaryLineSnapshot, ...]
    ) -> None:
        """Record clearing identify temporary lines."""
        ...

    def record_ident_register_selected(
        self,
        project: SpectroscopyProject,
        created_line_ids: list[str],
        created_region_ids: list[str],
        _removed_temporary_line_ids: list[str],
        temporary_line_snapshots: tuple[TemporaryLineSnapshot, ...],
        affected_region_ids: list[str],
        before_affected_region_snapshots: tuple[AbsorptionRegionSnapshot, ...],
    ) -> None:
        """Record identify registration confirmation."""
        ...


class IdentifyRangeCoordinator(Protocol):
    """Spectrum range operations required by identify focus routing."""

    def coordinate_range_update(
        self, source: str, x_min: float, x_max: float, *, record_history: bool = True
    ) -> None:
        """Apply a wavelength range update."""
        ...

    def handle_auto_flux_range_request(self) -> None:
        """Apply automatic flux range adjustment."""
        ...


class IdentifySpectrumView(IdentifyDetectionOverlayPort, Protocol):
    """Spectrum operations required by identify workflows."""

    @property
    def coordinator(self) -> IdentifyRangeCoordinator:
        """Return the spectrum range coordinator."""
        ...

    def set_absorption_line_regions(self, regions: list[RegionPayload]) -> None:
        """Set absorption line overlay regions."""
        ...

    def set_identify_preview(self, payload: CursorPreviewPayload | None) -> None:
        """Set or clear identify cursor preview payload."""
        ...

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the displayed wavelength range."""
        ...


class IdentifyPresetDialogPort(Protocol):
    """Preset dialog operations required by identify workflows."""

    def show_preset_list_dialog(self) -> None:
        """Open the preset management dialog."""
        ...


@dataclass(frozen=True, slots=True)
class IdentifyShellPorts:
    """Operation-specific shell capabilities required by identify mode."""

    current_project_provider: Callable[[], SpectroscopyProject | None]
    spectrum_view_provider: Callable[[], IdentifySpectrumView | None]
    mode_state_provider: Callable[[], IdentifyModeStateProvider | None]
    preset_store_setter: Callable[[IdentifyPresetStore | None], None]
    history_recorder_provider: Callable[[], IdentifyHistoryRecorder | None]
    velocity_runtime_provider: Callable[[], IdentifyVelocityOverlayRuntimePort]
    preset_dialog_provider: Callable[[], IdentifyPresetDialogPort]
    undo_shortcut_provider: Callable[[], str]
