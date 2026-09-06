"""Tests for identify detection use case."""

from __future__ import annotations

import numpy as np
import pytest

from chappy.application.identify import (
    DetectCandidateLinesRequest,
    DetectCandidateLinesUseCase,
    DetectionErrorCode,
)
from chappy.core.absorption.search9_detection import Search9Parameters
import chappy.application.identify.detection_usecase as detection_usecase_module


def _request(
    *,
    error: np.ndarray | None,
    continuum: np.ndarray | None,
    n_points: int = 120,
    existing_ranges: tuple[tuple[float, float], ...] = (),
    temporary_line_ranges: tuple[tuple[float, float], ...] = (),
) -> DetectCandidateLinesRequest:
    """Build a detection request for tests.

    Args:
        error: Error array.
        continuum: Continuum flux array.
        n_points: Number of samples.
        existing_ranges: Existing confirmed line ranges.
        temporary_line_ranges: Wavelength ranges of existing temporary lines.

    Returns:
        Detection request.
    """
    wavelength = np.linspace(1000.0, 1100.0, n_points, dtype=float)
    flux = np.ones(n_points, dtype=float)
    if n_points > 60:
        flux[50:55] = 0.8
    return DetectCandidateLinesRequest(
        wavelength=wavelength,
        flux=flux,
        error=error,
        continuum_flux=continuum,
        parameters=Search9Parameters(n_sigma=2.0),
        existing_line_ranges=existing_ranges,
        temporary_line_ranges=temporary_line_ranges,
    )


def test_missing_error_array_returns_typed_error() -> None:
    """Missing error array should not call Search9."""
    result = DetectCandidateLinesUseCase().detect(
        _request(error=None, continuum=np.ones(120, dtype=float))
    )

    assert result.error_code is DetectionErrorCode.NO_ERROR_ARRAY
    assert result.regions == ()


def test_insufficient_data_returns_typed_error() -> None:
    """Short spectra should return insufficient-data error."""
    result = DetectCandidateLinesUseCase().detect(
        _request(
            error=np.full(50, 0.05, dtype=float), continuum=np.ones(50, dtype=float), n_points=50
        )
    )

    assert result.error_code is DetectionErrorCode.INSUFFICIENT_DATA


def test_missing_continuum_returns_typed_error() -> None:
    """Missing continuum model should return typed no-continuum error."""
    result = DetectCandidateLinesUseCase().detect(
        _request(error=np.full(120, 0.05, dtype=float), continuum=None)
    )

    assert result.error_code is DetectionErrorCode.NO_CONTINUUM


def test_detected_regions_are_classified_by_existing_ranges() -> None:
    """Detected regions should be marked identified when center falls in existing ranges."""
    result = DetectCandidateLinesUseCase().detect(
        _request(
            error=np.full(120, 0.02, dtype=float),
            continuum=np.ones(120, dtype=float),
            existing_ranges=((1040.0, 1055.0),),
        )
    )

    assert result.error_code is None
    assert result.regions
    assert any(region.status == "identified" for region in result.regions)


def test_detection_internal_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected detection failures are not converted to a generic user error."""

    def fail_detection(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("search implementation failed")

    monkeypatch.setattr(detection_usecase_module, "detect_regions", fail_detection)

    with pytest.raises(RuntimeError, match="search implementation failed"):
        DetectCandidateLinesUseCase().detect(
            _request(error=np.full(120, 0.02, dtype=float), continuum=np.ones(120, dtype=float))
        )
