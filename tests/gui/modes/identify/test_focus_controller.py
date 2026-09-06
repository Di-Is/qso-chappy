"""Tests for identify spectrum focus controller."""

from __future__ import annotations

from dataclasses import dataclass

from chappy.gui.modes.identify.focus_controller import (
    IdentifyFocusMessages,
    IdentifyFocusPorts,
    IdentifySpectrumFocusController,
)
from chappy.gui.modes.identify.panel.panel_models import CandidateRow


@dataclass(slots=True)
class _RangeUpdate:
    """Captured spectrum range update."""

    source: str
    x_min: float
    x_max: float
    record_history: bool


class _RangeCoordinator:
    """Capture range and flux requests from the focus controller."""

    def __init__(self) -> None:
        """Initialize captured calls."""
        self.updates: list[_RangeUpdate] = []
        self.auto_flux_count = 0

    def coordinate_range_update(
        self, source: str, x_min: float, x_max: float, *, record_history: bool = True
    ) -> None:
        """Store the requested wavelength range."""
        self.updates.append(
            _RangeUpdate(source=source, x_min=x_min, x_max=x_max, record_history=record_history)
        )

    def handle_auto_flux_range_request(self) -> None:
        """Store an automatic flux-range request."""
        self.auto_flux_count += 1


class _SpectrumView:
    """Minimal spectrum view used by focus controller tests."""

    def __init__(self) -> None:
        """Initialize the fake spectrum view."""
        self.coordinator = _RangeCoordinator()
        self.wavelength_range = (4900.0, 5100.0)

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the current visible wavelength range."""
        return self.wavelength_range


def _messages() -> IdentifyFocusMessages:
    """Return deterministic focus-controller messages."""
    return IdentifyFocusMessages(
        candidate_template="candidate {start:.2f} {end:.2f}",
        group_template="group {start:.1f} {end:.1f}",
        line_template="line {start:.1f} {end:.1f}",
    )


def test_focus_candidate_updates_range_and_status() -> None:
    """Candidate focus should move the spectrum view without touching session state."""
    view = _SpectrumView()
    status_messages: list[str] = []
    controller = IdentifySpectrumFocusController(
        IdentifyFocusPorts(
            candidate_rows_provider=lambda: (
                CandidateRow(
                    identifier="cand-1",
                    lambda_start=5000.0,
                    lambda_end=5010.0,
                    sigma=5.0,
                    status="candidate",
                ),
            ),
            spectrum_view_provider=lambda: view,
            data_bounds_provider=lambda: (4900.0, 5100.0),
            status_callback=status_messages.append,
            messages_provider=_messages,
        )
    )

    controller.focus_candidate("cand-1")

    assert view.coordinator.updates == [
        _RangeUpdate(
            source="identify-candidate-focus", x_min=4980.0, x_max=5030.0, record_history=False
        )
    ]
    assert view.coordinator.auto_flux_count == 1
    assert status_messages == ["candidate 5000.00 5010.00"]


def test_focus_group_and_line_apply_padded_ranges() -> None:
    """Group and line focus should apply their distinct padding rules."""
    view = _SpectrumView()
    status_messages: list[str] = []
    controller = IdentifySpectrumFocusController(
        IdentifyFocusPorts(
            candidate_rows_provider=tuple,
            spectrum_view_provider=lambda: view,
            data_bounds_provider=lambda: (4900.0, 5100.0),
            status_callback=status_messages.append,
            messages_provider=_messages,
        )
    )

    controller.focus_group(5000.0, 5010.0)
    controller.focus_line(5000.0, 5010.0)

    assert view.coordinator.updates == [
        _RangeUpdate(source="identify-focus", x_min=4999.0, x_max=5011.0, record_history=False),
        _RangeUpdate(source="identify-focus", x_min=4999.5, x_max=5010.5, record_history=False),
    ]
    assert view.coordinator.auto_flux_count == 2
    assert status_messages == ["group 4999.0 5011.0", "line 4999.5 5010.5"]
