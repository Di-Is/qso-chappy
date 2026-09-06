"""Unit tests for identify mode session state helpers."""

from __future__ import annotations

import math

from chappy.core.identify_state import TemporaryLineContext, IdentifySessionState
from chappy.core.velocity_ranges import NewCandidateAnalysisHalfWidth


def test_add_temporary_line_computes_center_z_from_rest_wavelength() -> None:
    state = IdentifySessionState()

    rest_wavelength = 1548.195
    line = state.add_temporary_line(
        "C IV",
        1549.5,
        1547.1,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="test_civ_1548",
            rest_wavelength=rest_wavelength,
            multiplet_id="",
            multiplet_label="",
            transition_name="C IV 1548.2",
            oscillator_strength=0.19,
            gamma_value=2.65e8,
            tie_group_key="",
        ),
    )

    assert math.isclose(line.lambda_min, 1547.1)
    assert math.isclose(line.lambda_max, 1549.5)
    expected_center = (line.center_wavelength / rest_wavelength) - 1.0
    assert line.center_z is not None
    assert math.isclose(line.center_z, expected_center, rel_tol=1e-9)


def test_add_temporary_line_respects_explicit_center_z() -> None:
    state = IdentifySessionState()

    line = state.add_temporary_line(
        "Si II",
        1526.3,
        1527.9,
        creation_method="velocity_plot",
        context=TemporaryLineContext(
            line_id="SiII|1526.7069",
            rest_wavelength=1526.70698,
            multiplet_id="",
            multiplet_label="",
            transition_name="Si II 1526.7",
            oscillator_strength=0.127,
            gamma_value=2.2e8,
            tie_group_key="",
            center_z=0.1234,
        ),
    )

    assert math.isclose(line.center_z or 0.0, 0.1234)
    assert line.line_id == "SiII|1526.7069"


def test_new_candidate_half_width_does_not_mutate_existing_lines() -> None:
    state = IdentifySessionState()
    state.add_temporary_line(
        "O VI",
        1031.0,
        1033.0,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="test_ovi_1031",
            rest_wavelength=1031.9261,
            multiplet_id="",
            multiplet_label="",
            transition_name="O VI 1031.9",
            oscillator_strength=0.133,
            gamma_value=4.1e8,
            tie_group_key="",
        ),
    )
    state.add_temporary_line(
        "O VI",
        1037.0,
        1039.0,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="test_ovi_1037",
            rest_wavelength=1037.6167,
            multiplet_id="",
            multiplet_label="",
            transition_name="O VI 1037.6",
            oscillator_strength=0.066,
            gamma_value=4.1e8,
            tie_group_key="",
        ),
    )

    existing_ranges = [
        (line.lambda_min, line.lambda_max, line.analysis_half_width_kms)
        for line in state.temporary_lines
    ]

    state.set_new_candidate_analysis_half_width(NewCandidateAnalysisHalfWidth(250.0))

    assert math.isclose(state.new_candidate_analysis_half_width.kms, 250.0)
    assert [
        (line.lambda_min, line.lambda_max, line.analysis_half_width_kms)
        for line in state.temporary_lines
    ] == existing_ranges

    new_line = state.add_temporary_line(
        "O VI",
        1040.0,
        1042.0,
        creation_method="manual",
        context=TemporaryLineContext(
            line_id="test_ovi_new",
            rest_wavelength=1041.0,
            multiplet_id="",
            multiplet_label="",
            transition_name="O VI new",
            oscillator_strength=0.05,
            gamma_value=4.1e8,
            tie_group_key="",
        ),
    )
    assert math.isclose(new_line.analysis_half_width_kms, 250.0)
