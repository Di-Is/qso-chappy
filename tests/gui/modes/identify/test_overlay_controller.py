"""Tests for identify line overlay controller."""

from __future__ import annotations

from collections.abc import Sequence

from chappy.core.identify_state import TemporaryLine
from chappy.gui.modes.identify.overlay_controller import (
    IdentifyLineOverlayController,
    IdentifyLineOverlayPorts,
)
from chappy.gui.utils.absorption_overlays import RegionPayload


class _Session:
    """Minimal identify session for overlay tests."""

    def __init__(self, temporary_lines: Sequence[TemporaryLine]) -> None:
        """Initialize temporary line storage."""
        self._temporary_lines = tuple(temporary_lines)

    @property
    def temporary_lines(self) -> tuple[TemporaryLine, ...]:
        """Return temporary identify candidates."""
        return self._temporary_lines


class _SpectrumView:
    """Capture line overlay payloads applied by the controller."""

    def __init__(self) -> None:
        """Initialize captured payloads."""
        self.applied: list[list[RegionPayload]] = []

    def set_absorption_line_regions(self, regions: list[RegionPayload]) -> None:
        """Store line overlay regions."""
        self.applied.append(regions)


def _candidate(temporary_line_id: str) -> TemporaryLine:
    """Build a temporary line for overlay tests."""
    return TemporaryLine(
        temporary_line_id=temporary_line_id,
        species="Mg II",
        lambda_min=5000.0,
        lambda_max=5010.0,
        creation_method="manual",
        line_id=f"{temporary_line_id}-line",
        rest_wavelength=2796.352,
        center_z=0.788,
        multiplet_id="",
        multiplet_label="",
        transition_name="Mg II 2796",
        oscillator_strength=0.612,
        gamma_value=2.6e8,
        tie_group_key="",
    )


def test_build_payload_includes_temporary_candidates_when_requested() -> None:
    """Temporary candidate overlays should be included only when requested."""
    session = _Session([_candidate("tmp-1")])
    controller = IdentifyLineOverlayController(
        IdentifyLineOverlayPorts(
            project_provider=lambda: None,
            session_provider=lambda: session,
            spectrum_view_provider=lambda: None,
            identify_mode_active_provider=lambda: True,
        )
    )

    assert controller.build_payload(include_temporary=False) == []

    payload = controller.build_payload(include_temporary=True)

    assert len(payload) == 1
    assert payload[0]["id"] == "tmp-1"
    assert payload[0]["category"] == "temporary"


def test_apply_uses_identify_mode_active_when_flag_is_omitted() -> None:
    """Omitted include flag should follow the active identify mode state."""
    session = _Session([_candidate("tmp-1")])
    view = _SpectrumView()
    controller = IdentifyLineOverlayController(
        IdentifyLineOverlayPorts(
            project_provider=lambda: None,
            session_provider=lambda: session,
            spectrum_view_provider=lambda: view,
            identify_mode_active_provider=lambda: True,
        )
    )

    controller.apply()

    assert len(view.applied) == 1
    assert view.applied[0][0]["id"] == "tmp-1"
