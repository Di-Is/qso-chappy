"""Tests for spectrum range navigation use case."""

from __future__ import annotations

import math

import pytest

from chappy.application.spectrum import (
    CenterOnWavelengthNavigationIntent,
    PanNavigationIntent,
    RangeNavigationRequest,
    RangeNavigationUseCase,
    SelectRangeNavigationIntent,
    SpectrumRangeSource,
    ZoomFactorNavigationIntent,
    ZoomRectNavigationIntent,
)
from chappy.application.spectrum.range_usecase import MIN_WAVELENGTH_DISPLAY_SPAN


def test_pan_clamps_to_data_bounds() -> None:
    """Pan navigation should preserve span while respecting data bounds."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=PanNavigationIntent(fraction=0.75),
            data_bounds=(900.0, 2500.0),
        )
    )

    assert result.wavelength_range == pytest.approx((1500.0, 2500.0))
    assert result.flux_range is None
    assert result.source is SpectrumRangeSource.INTENT


def test_zoom_factor_keeps_cursor_relative_position() -> None:
    """Fixed-point zoom should keep the cursor at the same relative position."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=ZoomFactorNavigationIntent(
                factor=2.0, center_wavelength=1900.0, cursor_relative_position=0.9
            ),
            data_bounds=(0.0, 3000.0),
        )
    )

    assert result.wavelength_range == pytest.approx((1450.0, 1950.0))
    assert result.source is SpectrumRangeSource.INTENT


def test_zoom_rect_returns_flux_range_and_rect_source() -> None:
    """Rectangle zoom should return both wavelength and flux ranges."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=ZoomRectNavigationIntent(
                min_wavelength=1200.0, max_wavelength=1500.0, min_flux=-0.2, max_flux=0.8
            ),
            data_bounds=(900.0, 2500.0),
        )
    )

    assert result.wavelength_range == pytest.approx((1200.0, 1500.0))
    assert result.flux_range == pytest.approx((-0.2, 0.8))
    assert result.source is SpectrumRangeSource.RECT_ZOOM


def test_center_on_wavelength_clamps_inside_bounds() -> None:
    """Center navigation should keep the current span inside data bounds."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=CenterOnWavelengthNavigationIntent(wavelength=2400.0),
            data_bounds=(900.0, 2500.0),
        )
    )

    assert result.wavelength_range == pytest.approx((1500.0, 2500.0))


def test_select_range_enforces_minimum_span_with_anchorless_expansion() -> None:
    """Small selected ranges should expand to the minimum display span."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=SelectRangeNavigationIntent(start_wavelength=20.0, end_wavelength=22.0),
            data_bounds=(0.0, 100.0),
        )
    )

    min_wave, max_wave = result.wavelength_range
    assert math.isclose(
        max_wave - min_wave, MIN_WAVELENGTH_DISPLAY_SPAN, rel_tol=0.0, abs_tol=1e-6
    )


def test_reversed_select_range_remains_valid_user_gesture() -> None:
    """Reversed drag/select gestures should normalize instead of failing."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=SelectRangeNavigationIntent(start_wavelength=1500.0, end_wavelength=1200.0),
            data_bounds=(900.0, 2500.0),
        )
    )

    assert result.wavelength_range == pytest.approx((1200.0, 1500.0))


@pytest.mark.parametrize(
    ("current_range", "match"),
    [
        ((2000.0, 1000.0), "current_range"),
        ((1000.0, 1000.0), "current_range"),
        ((1000.0, math.inf), "finite"),
    ],
)
def test_malformed_current_range_fails_fast(
    current_range: tuple[float, float], match: str
) -> None:
    """Current range is required application state and must be valid."""
    with pytest.raises(ValueError, match=match):
        RangeNavigationUseCase().calculate(
            RangeNavigationRequest(
                current_range=current_range, intent=PanNavigationIntent(fraction=0.1)
            )
        )


@pytest.mark.parametrize(
    ("data_bounds", "match"),
    [
        ((2500.0, 900.0), "data_bounds"),
        ((900.0, 900.0), "data_bounds"),
        ((900.0, math.nan), "finite"),
    ],
)
def test_malformed_data_bounds_fails_fast(data_bounds: tuple[float, float], match: str) -> None:
    """Present data bounds are required to be finite and ordered."""
    with pytest.raises(ValueError, match=match):
        RangeNavigationUseCase().calculate(
            RangeNavigationRequest(
                current_range=(1000.0, 2000.0),
                intent=PanNavigationIntent(fraction=0.1),
                data_bounds=data_bounds,
            )
        )


@pytest.mark.parametrize(
    ("intent", "match"),
    [
        (PanNavigationIntent(fraction=math.nan), "pan fraction"),
        (ZoomFactorNavigationIntent(factor=0.0), "zoom factor"),
        (ZoomFactorNavigationIntent(factor=-1.0), "zoom factor"),
        (ZoomFactorNavigationIntent(factor=math.inf), "zoom factor"),
        (
            ZoomFactorNavigationIntent(factor=2.0, cursor_relative_position=math.nan),
            "cursor_relative_position",
        ),
        (ZoomRectNavigationIntent(min_wavelength=1200.0, max_wavelength=1200.0), "zero-width"),
        (ZoomRectNavigationIntent(min_wavelength=1200.0, max_wavelength=math.nan), "finite"),
        (
            SelectRangeNavigationIntent(start_wavelength=1200.0, end_wavelength=1200.0),
            "zero-width",
        ),
        (CenterOnWavelengthNavigationIntent(wavelength=math.nan), "center wavelength"),
    ],
)
def test_malformed_navigation_intent_fails_fast(
    intent: (
        PanNavigationIntent
        | ZoomFactorNavigationIntent
        | ZoomRectNavigationIntent
        | SelectRangeNavigationIntent
        | CenterOnWavelengthNavigationIntent
    ),
    match: str,
) -> None:
    """Malformed navigation intents are programmer/state errors at usecase boundary."""
    with pytest.raises(ValueError, match=match):
        RangeNavigationUseCase().calculate(
            RangeNavigationRequest(current_range=(1000.0, 2000.0), intent=intent)
        )


def test_missing_data_bounds_remains_valid_unbounded_navigation() -> None:
    """None data bounds means unbounded navigation, not missing required data."""
    result = RangeNavigationUseCase().calculate(
        RangeNavigationRequest(
            current_range=(1000.0, 2000.0),
            intent=PanNavigationIntent(fraction=0.5),
            data_bounds=None,
        )
    )

    assert result.wavelength_range == pytest.approx((1500.0, 2500.0))
