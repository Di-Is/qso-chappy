"""Redshift limit calculation helpers for absorption lines."""

from __future__ import annotations

PHYSICAL_Z_MIN = -0.1
PHYSICAL_Z_MAX = 10.0


def calculate_dynamic_z_limits(
    rest_wavelength: float, lambda_range: tuple[float, float] | None = None
) -> tuple[float, float]:
    """Calculate redshift limits from a wavelength range.

    Args:
        rest_wavelength: Rest wavelength of the absorption line in Angstrom.
        lambda_range: Line wavelength range in Angstrom, or None to use physical limits.

    Returns:
        Minimum and maximum allowed redshift.
    """
    if not lambda_range:
        return (PHYSICAL_Z_MIN, PHYSICAL_Z_MAX)

    if rest_wavelength <= 0:
        return (PHYSICAL_Z_MIN, PHYSICAL_Z_MAX)

    lambda_lower, lambda_upper = lambda_range
    dynamic_z_min = (lambda_lower / rest_wavelength) - 1.0
    dynamic_z_max = (lambda_upper / rest_wavelength) - 1.0

    z_min = max(dynamic_z_min, PHYSICAL_Z_MIN)
    z_max = min(dynamic_z_max, PHYSICAL_Z_MAX)

    return (z_min, z_max)


def clamp_z_value(
    z_value: float, rest_wavelength: float, lambda_range: tuple[float, float] | None = None
) -> float:
    """Clamp a redshift value to the valid range.

    Args:
        z_value: Redshift value to clamp.
        rest_wavelength: Rest wavelength of the absorption line in Angstrom.
        lambda_range: Line wavelength range in Angstrom, or None to use physical limits.

    Returns:
        Clamped redshift value.
    """
    z_min, z_max = calculate_dynamic_z_limits(rest_wavelength, lambda_range)
    return max(z_min, min(z_value, z_max))


__all__ = ["PHYSICAL_Z_MAX", "PHYSICAL_Z_MIN", "calculate_dynamic_z_limits", "clamp_z_value"]
