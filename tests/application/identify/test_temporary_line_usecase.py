"""Tests for identify temporary-line use cases."""

from __future__ import annotations

import math

import pytest

from chappy.application.identify import (
    AtomicLineSnapshot,
    BuildVelocityPreviewUseCase,
    TemporaryLineCreationEntry,
    TemporaryLineSnapshot,
    CreateTemporaryLineFromVelocityUseCase,
    VelocityTemporaryLineRequest,
)
from chappy.core.identify_state import (
    TemporaryLine,
    TemporaryLineContext,
    IDENTIFY_TEMPORARY_LINE_LIMIT,
    IdentifySessionState,
)
from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.core.velocity_ranges import LineAnalysisHalfWidth, NewCandidateAnalysisHalfWidth


def _line(
    line_id: str,
    species: str,
    wavelength: float,
    *,
    multiplet_id: str = "",
    transition_name: str = "",
    tie_group_key: str | None = None,
) -> AtomicLineSnapshot:
    """Create an atomic line snapshot for tests.

    Args:
        line_id: Atomic line ID.
        species: Species label.
        wavelength: Rest wavelength.
        multiplet_id: Multiplet identifier.
        transition_name: Transition display name.

    Returns:
        Atomic line snapshot.
    """
    return AtomicLineSnapshot(
        line_id=line_id,
        species=species,
        wavelength_angstrom=wavelength,
        oscillator_strength=0.1,
        gamma_value=1e8,
        multiplet_id=multiplet_id,
        multiplet_label="",
        transition_name=transition_name,
        tie_group_key=multiplet_id if tie_group_key is None else tie_group_key,
    )


def _temporary_line_snapshot(temporary_line: TemporaryLine) -> TemporaryLineSnapshot:
    """Convert a core temporary line to an application snapshot.

    Args:
        temporary line: Temporary line stored in test session state.

    Returns:
        Immutable temporary line snapshot.
    """
    return TemporaryLineSnapshot(
        temporary_line_id=temporary_line.temporary_line_id,
        species=temporary_line.species,
        lambda_min=temporary_line.lambda_min,
        lambda_max=temporary_line.lambda_max,
        creation_method=temporary_line.creation_method,
        line_id=temporary_line.line_id,
        rest_wavelength=temporary_line.rest_wavelength,
        center_z=temporary_line.center_z,
        multiplet_id=temporary_line.multiplet_id,
        multiplet_label=temporary_line.multiplet_label,
        tie_group_key=temporary_line.tie_group_key,
        transition_name=temporary_line.transition_name,
        oscillator_strength=temporary_line.oscillator_strength,
        gamma_value=temporary_line.gamma_value,
        analysis_half_width=LineAnalysisHalfWidth(temporary_line.analysis_half_width_kms),
    )


class _SessionMutationAdapter:
    """Test adapter that applies application creation entries to core session state."""

    def __init__(self, session: IdentifySessionState) -> None:
        """Create an adapter for a test identify session."""
        self._session = session

    @property
    def temporary_line_snapshots(self) -> tuple[TemporaryLineSnapshot, ...]:
        """Return current temporary line snapshots."""
        return tuple(
            _temporary_line_snapshot(temporary_line)
            for temporary_line in self._session.temporary_lines
        )

    def add_temporary_line_creation_entry(self, creation_entry: TemporaryLineCreationEntry) -> str:
        """Add a temporary line from an application creation entry.

        Args:
            creation_entry: Temporary line creation entry from the use case.

        Returns:
            Created temporary line ID.
        """
        entry = creation_entry.preview_entry
        context = TemporaryLineContext(
            line_id=entry.line_id,
            rest_wavelength=entry.rest_wavelength,
            multiplet_id=entry.multiplet_id,
            multiplet_label=entry.multiplet_label,
            tie_group_key=entry.tie_group_key,
            transition_name=entry.transition_name,
            oscillator_strength=entry.oscillator_strength,
            gamma_value=entry.gamma_value,
            center_z=creation_entry.redshift,
        )
        temporary_line = self._session.add_temporary_line(
            entry.species,
            entry.lambda_min,
            entry.lambda_max,
            creation_method="manual",
            context=context,
            analysis_half_width=creation_entry.analysis_half_width,
        )
        return temporary_line.temporary_line_id


def test_preview_calculates_redshift_and_window() -> None:
    """Preview builder should derive redshift and velocity window."""
    baseline = _line("base", "Mg II", 2803.0, transition_name="2803")

    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=2803.0,
            baseline_line=baseline,
            preset_lines=(baseline,),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
            include_all_preview_lines=False,
        )
    )

    assert math.isclose(preview.redshift, 0.0, rel_tol=0.0, abs_tol=1e-12)
    assert len(preview.entries) == 1
    entry = preview.entries[0]
    expected_delta = baseline.wavelength_angstrom * (200.0 / LIGHT_SPEED_KMS)
    assert math.isclose(entry.lambda_min, baseline.wavelength_angstrom - expected_delta)
    assert math.isclose(entry.lambda_max, baseline.wavelength_angstrom + expected_delta)
    assert entry.line_id == "base"


def test_preview_rejects_invalid_baseline_rest_wavelength() -> None:
    """Invalid atomic baseline data should not produce a zero-redshift preview."""
    baseline = _line("base", "Mg II", 0.0)

    with pytest.raises(ValueError, match="Baseline rest wavelength must be positive"):
        BuildVelocityPreviewUseCase().build(
            VelocityTemporaryLineRequest(
                observed_wavelength=2803.0,
                baseline_line=baseline,
                preset_lines=(baseline,),
                new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
                include_all_preview_lines=False,
            )
        )


def test_preview_includes_same_multiplet_without_include_all() -> None:
    """Preview should include baseline multiplet members without include-all mode."""
    baseline = _line("base", "Mg II", 2803.0, multiplet_id="MGII")
    companion = _line("comp", "Mg II", 2796.0, multiplet_id="MGII")
    unrelated = _line("other", "Fe II", 2600.0)

    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=2803.0,
            baseline_line=baseline,
            preset_lines=(baseline, companion, unrelated),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
            include_all_preview_lines=False,
        )
    )

    assert {entry.line_id for entry in preview.entries} == {"base", "comp"}


def test_preview_uses_declared_tie_key_instead_of_atomic_multiplet_id() -> None:
    """DB multiplet metadata alone must not expand a preview."""
    baseline = _line("base", "Mg II", 2803.0, multiplet_id="MGII", tie_group_key="group-a")
    unrelated = _line("comp", "Mg II", 2796.0, multiplet_id="MGII", tie_group_key="group-b")

    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=2803.0,
            baseline_line=baseline,
            preset_lines=(baseline, unrelated),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
            include_all_preview_lines=False,
        )
    )

    assert tuple(entry.line_id for entry in preview.entries) == ("base",)


def test_preview_expands_same_declared_key_without_atomic_multiplet_id() -> None:
    """An explicit key expands a preview even when DB metadata is empty."""
    baseline = _line("base", "H I", 1215.67, tie_group_key="lyman-group")
    companion = _line("comp", "H I", 1025.72, tie_group_key="lyman-group")

    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=1215.67,
            baseline_line=baseline,
            preset_lines=(baseline, companion),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
            include_all_preview_lines=False,
        )
    )

    assert {entry.line_id for entry in preview.entries} == {"base", "comp"}
    assert {entry.tie_group_key for entry in preview.entries} == {"lyman-group"}
    assert {entry.multiplet_label for entry in preview.entries} == {"H I"}


def test_preview_filters_data_bounds() -> None:
    """Preview should drop lines outside observed data bounds."""
    baseline = _line("base", "Mg II", 2803.0)
    outside = _line("outside", "Fe II", 1000.0)

    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=2803.0,
            baseline_line=baseline,
            preset_lines=(baseline, outside),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(100.0),
            include_all_preview_lines=True,
            data_bounds=(2500.0, 2900.0),
        )
    )

    assert [entry.line_id for entry in preview.entries] == ["base"]


def test_create_temporary_line_skips_duplicate() -> None:
    """Temporary line creation should report duplicates without mutating twice."""
    baseline = _line("base", "Mg II", 2803.0)
    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=2803.0,
            baseline_line=baseline,
            preset_lines=(baseline,),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
            include_all_preview_lines=False,
        )
    )
    session = IdentifySessionState()
    usecase = CreateTemporaryLineFromVelocityUseCase()
    entries = tuple(
        TemporaryLineCreationEntry(
            preview_entry=entry,
            redshift=preview.redshift,
            analysis_half_width=LineAnalysisHalfWidth(200.0),
        )
        for entry in preview.entries
    )

    adapter = _SessionMutationAdapter(session)
    first = usecase.create(adapter, entries)
    second = usecase.create(adapter, entries)

    assert len(first.created) == 1
    assert len(second.created) == 0
    assert second.duplicate_count == 1
    assert session.temporary_count == 1


def test_creation_entry_keeps_range_and_saved_half_width_atomic() -> None:
    """Temporary-line creation must not re-read a changed future-candidate session draft."""
    baseline = _line("base", "Mg II", 2803.0)
    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=2803.0,
            baseline_line=baseline,
            preset_lines=(baseline,),
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(140.0),
            include_all_preview_lines=False,
        )
    )
    session = IdentifySessionState()
    session.set_new_candidate_analysis_half_width(NewCandidateAnalysisHalfWidth(500.0))
    entry = TemporaryLineCreationEntry(
        preview_entry=preview.entries[0],
        redshift=preview.redshift,
        analysis_half_width=LineAnalysisHalfWidth(140.0),
    )

    result = CreateTemporaryLineFromVelocityUseCase().create(
        _SessionMutationAdapter(session), (entry,)
    )

    assert len(result.created) == 1
    temporary_line = session.temporary_lines[0]
    assert temporary_line.analysis_half_width_kms == 140.0
    expected_delta = baseline.wavelength_angstrom * 140.0 / LIGHT_SPEED_KMS
    assert temporary_line.lambda_min == pytest.approx(
        baseline.wavelength_angstrom - expected_delta
    )
    assert temporary_line.lambda_max == pytest.approx(
        baseline.wavelength_angstrom + expected_delta
    )


class _ErrorProneMutationAdapter:
    """Adapter used to verify non-limit ValueError propagation."""

    @property
    def temporary_line_snapshots(self) -> tuple[TemporaryLineSnapshot, ...]:
        """Return no existing temporary line snapshots."""
        return ()

    def add_temporary_line_creation_entry(self, creation_entry: TemporaryLineCreationEntry) -> str:
        """Raise unexpected mutation error without recovery."""
        raise ValueError("unexpected mutation failure")


def _create_identify_temporary_line_request(count: int) -> tuple[TemporaryLineCreationEntry, ...]:
    """Build `count` creation entries for stable deterministic use-case tests."""
    lines = tuple(
        _line(
            f"line-{index}",
            "Mg II",
            2803.0 + index * 0.01,
            multiplet_id="MG",
            transition_name=f"{index}",
        )
        for index in range(count)
    )
    baseline = lines[0]
    preview = BuildVelocityPreviewUseCase().build(
        VelocityTemporaryLineRequest(
            observed_wavelength=baseline.wavelength_angstrom,
            baseline_line=baseline,
            preset_lines=lines,
            new_candidate_analysis_half_width=NewCandidateAnalysisHalfWidth(200.0),
            include_all_preview_lines=True,
        )
    )
    return tuple(
        TemporaryLineCreationEntry(
            preview_entry=entry,
            redshift=preview.redshift,
            analysis_half_width=LineAnalysisHalfWidth(200.0),
        )
        for entry in preview.entries
    )


def test_create_temporary_line_limit_reached_remains_recovered() -> None:
    """Temporary line limit reached from session remains user-recoverable with this use case."""
    usecase = CreateTemporaryLineFromVelocityUseCase()
    session = IdentifySessionState()
    adapter = _SessionMutationAdapter(session)

    entries = _create_identify_temporary_line_request(IDENTIFY_TEMPORARY_LINE_LIMIT + 1)
    result = usecase.create(adapter, entries)

    assert result.limit_reached is True
    assert len(result.created) == IDENTIFY_TEMPORARY_LINE_LIMIT
    assert result.duplicate_count == 0
    assert session.temporary_count == IDENTIFY_TEMPORARY_LINE_LIMIT


def test_create_temporary_line_unexpected_value_error_propagates() -> None:
    """Unexpected ValueError from mutation port must propagate without masking."""
    usecase = CreateTemporaryLineFromVelocityUseCase()
    entries = _create_identify_temporary_line_request(1)

    with pytest.raises(ValueError, match="unexpected mutation failure"):
        usecase.create(_ErrorProneMutationAdapter(), entries)
