"""Control identify cursor preview overlays."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from chappy.gui.modes.identify.application_adapters import (
    VelocityPreviewBuilderPort,
    build_cursor_preview_entries,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from chappy.core.atomic_data import AtomicLine
    from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth
    from chappy.presentation.identify import CursorPreviewPayload, PreviewEntry

logger = logging.getLogger(__name__)


def modifier_value(modifier: Qt.KeyboardModifier) -> int:
    """Return the integer Qt modifier mask."""
    value = modifier.value
    if isinstance(value, int):
        return value
    msg = f"Qt modifier value must be int, got {type(value).__name__}."
    raise TypeError(msg)


def shift_modifier_value() -> int:
    """Return the integer Qt shift modifier mask."""
    return modifier_value(Qt.KeyboardModifier.ShiftModifier)


def modifier_active(modifiers: int, modifier: Qt.KeyboardModifier) -> bool:
    """Return True if ``modifier`` is active in the supplied bitmask."""
    return bool(modifiers & modifier_value(modifier))


@dataclass(frozen=True, slots=True)
class IdentifyCursorPreviewPorts:
    """Collaborators required to build and apply cursor preview overlays."""

    identify_mode_active_provider: Callable[[], bool]
    new_candidate_analysis_half_width_provider: Callable[[], NewCandidateAnalysisHalfWidth]
    baseline_line_provider: Callable[[], AtomicLine | None]
    current_lines_provider: Callable[[], Sequence[AtomicLine]]
    observed_wavelength_bounds_provider: Callable[[], tuple[float, float] | None]
    preview_builder: VelocityPreviewBuilderPort
    preview_sink: Callable[[CursorPreviewPayload | None], None]
    preview_hint_provider: Callable[[], str]
    tie_group_keys_provider: Callable[[], Mapping[str, str]]


class IdentifyCursorPreviewController:
    """Manage identify cursor preview state and overlay payloads."""

    def __init__(self, ports: IdentifyCursorPreviewPorts) -> None:
        """Initialize the controller."""
        self._ports = ports
        self._cached_preview_payload: CursorPreviewPayload | None = None
        self._cursor_state: tuple[float, int] | None = None
        self._preview_always_on = False

    def set_preview_always_on(self, enabled: bool) -> None:
        """Enable or disable identify preview lock."""
        flag = bool(enabled)
        if flag == self._preview_always_on:
            return

        self._preview_always_on = flag
        if not self._preview_always_on:
            self._clear_cursor_preview_overlay()
            return

        if self._ports.identify_mode_active_provider():
            self.reapply_cursor_preview()

    def preview_always_on(self) -> bool:
        """Return whether identify preview lock is active."""
        return self._preview_always_on

    def handle_cursor_position(self, wavelength: float, _flux: float, modifiers: int) -> None:
        """Update ghost overlays based on the current cursor position."""
        logger.debug(
            "handle_cursor_position called: wavelength=%.2f, modifiers=%d", wavelength, modifiers
        )

        if not self._ports.identify_mode_active_provider():
            self.clear_cursor_preview()
            return

        shift_pressed = modifier_active(modifiers, Qt.KeyboardModifier.ShiftModifier)
        preview_forced = self._preview_always_on
        if not shift_pressed and not preview_forced:
            self.clear_cursor_preview()
            return

        self._cursor_state = (float(wavelength), int(modifiers))

        baseline_line = self._ports.baseline_line_provider()
        if baseline_line is None or baseline_line.wavelength_angstrom <= 0:
            self._clear_cursor_preview_overlay()
            return

        rest_wavelength = baseline_line.wavelength_angstrom
        redshift = (wavelength / rest_wavelength) - 1.0

        analysis_half_width = self._ports.new_candidate_analysis_half_width_provider()
        lines = list(self._ports.current_lines_provider())
        if not lines:
            self._clear_cursor_preview_overlay()
            return

        effective_shift = shift_pressed or preview_forced
        entries = self.build_cursor_preview_entries(
            lines=lines,
            baseline_line=baseline_line,
            redshift=redshift,
            new_candidate_analysis_half_width=analysis_half_width,
            shift_pressed=effective_shift,
            tie_group_keys=self._ports.tie_group_keys_provider(),
            data_bounds=self._ports.observed_wavelength_bounds_provider(),
        )

        if not entries:
            self._clear_cursor_preview_overlay()
            return

        preview_payload: CursorPreviewPayload = {
            "entries": entries,
            "observed_cursor": wavelength,
            "modifiers": modifiers if not preview_forced else self._apply_shift_mask(modifiers),
        }
        if shift_pressed:
            preview_payload["hint_text"] = self._ports.preview_hint_provider()
        self._apply_cursor_preview(preview_payload)

    def clear_cursor_preview(self) -> None:
        """Forget cursor input state and remove its identify preview overlay."""
        self._cursor_state = None
        self._clear_cursor_preview_overlay()

    def _clear_cursor_preview_overlay(self) -> None:
        """Remove the overlay while retaining cursor state for local reapplication."""
        if self._cached_preview_payload is None:
            return

        self._ports.preview_sink(None)
        self._cached_preview_payload = None

    def handle_cursor_left(self) -> None:
        """Forget cursor state and clear overlays when leaving the spectrum view."""
        self.clear_cursor_preview()

    def handle_shift_released(self) -> None:
        """Remove transient Shift guidance while preserving a forced preview lock."""
        if self._cursor_state is None:
            self.clear_cursor_preview()
            return

        wavelength, modifiers = self._cursor_state
        modifiers_without_shift = modifiers & ~shift_modifier_value()
        self._cursor_state = (wavelength, modifiers_without_shift)
        if not self._preview_always_on:
            self._clear_cursor_preview_overlay()
            return

        self.handle_cursor_position(wavelength, 0.0, modifiers_without_shift)

    def reapply_cursor_preview(self) -> None:
        """Recompute ghost overlays using the last known cursor state."""
        if self._cursor_state is None:
            return
        if not self._ports.identify_mode_active_provider():
            self.clear_cursor_preview()
            return

        wavelength, modifiers = self._cursor_state
        self.handle_cursor_position(wavelength, 0.0, modifiers)

    def note_manual_temporary_line_position(
        self, observed_wavelength: float, modifiers: int
    ) -> None:
        """Remember the cursor position after a shift-click manual temporary-line action."""
        if self._ports.identify_mode_active_provider() and modifier_active(
            modifiers, Qt.KeyboardModifier.ShiftModifier
        ):
            self._cursor_state = (float(observed_wavelength), int(modifiers))

    def clear_preview_lock(self) -> None:
        """Disable preview lock without reapplying preview."""
        self._preview_always_on = False

    def build_cursor_preview_entries(
        self,
        *,
        lines: Sequence[AtomicLine],
        baseline_line: AtomicLine,
        redshift: float,
        new_candidate_analysis_half_width: NewCandidateAnalysisHalfWidth,
        shift_pressed: bool,
        tie_group_keys: Mapping[str, str],
        data_bounds: tuple[float, float] | None = None,
        for_preview: bool = True,
    ) -> list[PreviewEntry]:
        """Build cursor preview entries from the current preview dependencies."""
        return build_cursor_preview_entries(
            preview_builder=self._ports.preview_builder,
            lines=tuple(lines),
            baseline_line=baseline_line,
            redshift=redshift,
            new_candidate_analysis_half_width=new_candidate_analysis_half_width,
            shift_pressed=shift_pressed,
            tie_group_keys=tie_group_keys,
            data_bounds=data_bounds,
            for_preview=for_preview,
        )

    def _apply_cursor_preview(self, payload: CursorPreviewPayload) -> None:
        if payload == self._cached_preview_payload:
            return

        self._ports.preview_sink(payload)
        self._cached_preview_payload = payload

    def _apply_shift_mask(self, modifiers: int) -> int:
        """Return modifiers mask with shift enforced for preview payloads."""
        return modifiers | shift_modifier_value()
