"""Use case for creating identify temporary lines from velocity slices."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from chappy.application.identify.group_labels import declarative_group_label
from chappy.application.identify.models import PreviewEntryModel, VelocitySliceTemporaryLineRequest
from chappy.core.constants import LIGHT_SPEED_KMS

if TYPE_CHECKING:
    from chappy.core.atomic_data import AtomicLineData


class BuildVelocitySliceTemporaryLinesUseCase:
    """Build temporary-line preview entries from selected velocity slices."""

    def build(
        self, request: VelocitySliceTemporaryLineRequest, atomic_data: AtomicLineData
    ) -> tuple[PreviewEntryModel, ...]:
        """Build preview entries for velocity slice temporary-line creation.

        Args:
            request: Velocity slice temporary-line request.
            atomic_data: Atomic line repository for reproducible line metadata.

        Returns:
            Preview entries suitable for temporary-line creation.
        """
        analysis_half_width_kms = request.new_candidate_analysis_half_width.kms

        entries: list[PreviewEntryModel] = []
        for selection in request.slices:
            atomic_line = (
                atomic_data.get_line_by_id(selection.line_id) if selection.line_id else None
            )
            if atomic_line is None:
                continue

            rest_wavelength = atomic_line.wavelength_angstrom
            if rest_wavelength <= 0:
                continue

            observed = rest_wavelength * (1.0 + request.center_z)
            if not math.isfinite(observed) or observed <= 0:
                continue

            delta = abs(observed) * (analysis_half_width_kms / LIGHT_SPEED_KMS)
            if not math.isfinite(delta) or delta <= 0:
                continue

            label = atomic_line.transition_name or selection.label
            entries.append(
                PreviewEntryModel(
                    line_id=atomic_line.line_id,
                    lambda_min=observed - delta,
                    lambda_max=observed + delta,
                    center=observed,
                    label=label,
                    original_label=label,
                    transition_name=atomic_line.transition_name,
                    color="#0066CC",
                    is_primary=selection.is_primary,
                    fill_alpha=0.12 if selection.is_primary else 0.06,
                    line_alpha=0.95 if selection.is_primary else 0.65,
                    line_width=1.4 if selection.is_primary else 1.0,
                    line_style="-." if selection.is_primary else "--",
                    multiplet_id=atomic_line.multiplet_id,
                    multiplet_label=declarative_group_label(
                        multiplet_label=atomic_line.multiplet_label,
                        species=atomic_line.species,
                        tie_group_key=selection.tie_group_key,
                    ),
                    species=atomic_line.species,
                    rest_wavelength=rest_wavelength,
                    oscillator_strength=atomic_line.oscillator_strength,
                    gamma_value=atomic_line.gamma_value,
                    delta_velocity=None,
                    tie_group_key=selection.tie_group_key,
                )
            )

        return tuple(entries)
