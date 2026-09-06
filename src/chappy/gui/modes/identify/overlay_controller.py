"""Line overlay controller for identify mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chappy.gui.utils.absorption_overlays import (
    RegionPayload,
    compute_confirmed_line_regions,
    compute_temporary_line_regions,
    merge_region_payloads,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from chappy.core.identify_state import TemporaryLine
    from chappy.core.spectroscopy_project import SpectroscopyProject


class IdentifyLineOverlaySessionPort(Protocol):
    """Session state required to build identify line overlays."""

    @property
    def temporary_lines(self) -> Sequence[TemporaryLine]:
        """Return temporary lines for identify overlays."""
        ...


class IdentifyLineOverlaySpectrumViewPort(Protocol):
    """Spectrum view operation required by line overlay updates."""

    def set_absorption_line_regions(self, regions: list[RegionPayload]) -> None:
        """Set absorption line overlay regions."""
        ...


@dataclass(frozen=True, slots=True)
class IdentifyLineOverlayPorts:
    """External state and callbacks required by line overlay workflows."""

    project_provider: Callable[[], SpectroscopyProject | None]
    session_provider: Callable[[], IdentifyLineOverlaySessionPort]
    spectrum_view_provider: Callable[[], IdentifyLineOverlaySpectrumViewPort | None]
    identify_mode_active_provider: Callable[[], bool]


class IdentifyLineOverlayController:
    """Build and apply confirmed and identify temporary line overlays."""

    def __init__(self, ports: IdentifyLineOverlayPorts) -> None:
        """Initialize the controller."""
        self._ports = ports

    def build_payload(self, *, include_temporary: bool) -> list[RegionPayload]:
        """Construct overlay payloads for confirmed and temporary lines."""
        confirmed = compute_confirmed_line_regions(self._ports.project_provider())
        if not include_temporary:
            return confirmed

        temporary = compute_temporary_line_regions(self._ports.session_provider().temporary_lines)
        return merge_region_payloads(confirmed, temporary)

    def apply(self, include_temporary: bool | None = None) -> None:
        """Push current line overlays to the spectrum view."""
        spectrum_view = self._ports.spectrum_view_provider()
        if spectrum_view is None:
            return

        if include_temporary is None:
            include_temporary = self._ports.identify_mode_active_provider()

        spectrum_view.set_absorption_line_regions(
            self.build_payload(include_temporary=include_temporary)
        )
