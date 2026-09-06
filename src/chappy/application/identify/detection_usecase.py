"""Use case for identify candidate detection."""

from __future__ import annotations

from chappy.application.identify.models import (
    DetectCandidateLinesRequest,
    DetectCandidateLinesResult,
    DetectedRegionSnapshot,
    DetectionErrorCode,
)
from chappy.core.absorption.search9_detection import MIN_DATA_POINTS, Search9Error, detect_regions


class DetectCandidateLinesUseCase:
    """Run Search9 detection and classify detected regions."""

    def detect(self, request: DetectCandidateLinesRequest) -> DetectCandidateLinesResult:
        """Detect candidate line regions.

        Args:
            request: Detection request with observed arrays, continuum, parameters, and ranges.

        Returns:
            Detection result with classified regions or a typed error.
        """
        if request.error is None:
            return DetectCandidateLinesResult(
                regions=(), error_code=DetectionErrorCode.NO_ERROR_ARRAY
            )
        if request.wavelength.size < MIN_DATA_POINTS:
            return DetectCandidateLinesResult(
                regions=(), error_code=DetectionErrorCode.INSUFFICIENT_DATA
            )
        if request.continuum_flux is None:
            return DetectCandidateLinesResult(
                regions=(), error_code=DetectionErrorCode.NO_CONTINUUM
            )

        try:
            raw_regions = detect_regions(
                request.wavelength,
                request.flux,
                request.error,
                request.continuum_flux,
                request.parameters,
            )
        except Search9Error as exc:
            return DetectCandidateLinesResult(
                regions=(), error_code=_error_code_from_search9(exc), error_detail=str(exc)
            )

        detected_regions = tuple(
            _assign_region_status(
                DetectedRegionSnapshot(
                    region_id=f"Region_{idx:03d}",
                    lambda_start=region.lambda_start,
                    lambda_end=region.lambda_end,
                    lambda_bar=region.lambda_center,
                    sigma=region.significance,
                    status="unused",
                ),
                existing_line_ranges=request.existing_line_ranges,
                temporary_line_ranges=request.temporary_line_ranges,
            )
            for idx, region in enumerate(raw_regions, start=1)
        )
        return DetectCandidateLinesResult(regions=detected_regions)


def _assign_region_status(
    region: DetectedRegionSnapshot,
    *,
    existing_line_ranges: tuple[tuple[float, float], ...],
    temporary_line_ranges: tuple[tuple[float, float], ...],
) -> DetectedRegionSnapshot:
    """Assign status based on overlap with existing and temporary-line ranges.

    Args:
        region: Detected region to classify.
        existing_line_ranges: Existing confirmed absorption line ranges.
        temporary_line_ranges: Wavelength ranges of existing temporary lines.

    Returns:
        Region with status assigned.
    """
    center = region.lambda_bar
    for start, end in existing_line_ranges:
        if start <= center <= end:
            return DetectedRegionSnapshot(
                region_id=region.region_id,
                lambda_start=region.lambda_start,
                lambda_end=region.lambda_end,
                lambda_bar=region.lambda_bar,
                sigma=region.sigma,
                status="identified",
            )
    for start, end in temporary_line_ranges:
        if start <= center <= end:
            return DetectedRegionSnapshot(
                region_id=region.region_id,
                lambda_start=region.lambda_start,
                lambda_end=region.lambda_end,
                lambda_bar=region.lambda_bar,
                sigma=region.sigma,
                status="candidate",
            )
    return region


def _error_code_from_search9(error: Search9Error) -> DetectionErrorCode:
    """Map Search9 error codes to application error codes.

    Args:
        error: Search9 exception.

    Returns:
        Detection error code.
    """
    if error.code == "insufficient-data":
        return DetectionErrorCode.INSUFFICIENT_DATA
    if error.code == "no-continuum":
        return DetectionErrorCode.NO_CONTINUUM
    if error.code == "no-error-array":
        return DetectionErrorCode.NO_ERROR_ARRAY
    return DetectionErrorCode.FAILED
