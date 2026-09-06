"""Tests for HDF5 project file handling."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest

from chappy.application.project_io_usecase import ProjectIOUseCase
from chappy.application.analysis_artifacts import (
    AnalysisArtifactStoreUseCase,
    RecordSuccessfulAnalysisUseCase,
)
from chappy.core.absorption.models import AbsorptionRegion, AbsorptionLine
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.continuum import ContinuumComponent
from chappy.core.components.tie_set import FULL_TIE_MASK, ParameterTieSet
from chappy.core.masking import MaskDefinition
from chappy.core.analysis import FitSummary
from chappy.core.components.optimize import FitOutcome
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.core.velocity_ranges import (
    DEFAULT_ANALYSIS_HALF_WIDTH_KMS,
    NewCandidateAnalysisHalfWidth,
)
from chappy.infrastructure.fits_spectrum_reader import FitsSpectrumReader
from chappy.infrastructure.hdf5_project_repository import HDF5ProjectRepository


@pytest.fixture
def project_io() -> ProjectIOUseCase:
    """Create a project I/O use case for persistence tests."""
    return ProjectIOUseCase(
        spectrum_reader=FitsSpectrumReader(), project_repository=HDF5ProjectRepository()
    )


@pytest.fixture
def sample_project() -> SpectroscopyProject:
    """Create a representative project populated with spectrum and components."""
    project = SpectroscopyProject(name="Unit Test Project")

    # Provide observed spectrum so arrays are written to disk
    wavelength = np.linspace(1000.0, 1100.0, 8, dtype=float)
    flux = np.linspace(1.0, 1.4, 8, dtype=float)
    error = np.full(8, 0.05, dtype=float)
    project.model.set_observed_spectrum(Spectrum(wavelength=wavelength, flux=flux, error=error))

    # Add absorber component with distinctive parameters
    absorber = AbsorberComponent(
        name="Test Absorber",
        wavelength=1215.67,
        column_density=15.2,
        b_parameter=18.0,
        redshift=0.135,
    )
    absorber.parameters["column_density"].fixed = True
    absorber.parameters["covering_factor"].set_value(0.73)
    absorber.parameters["covering_factor"].fixed = False
    project.model.add_component(absorber)

    # Add a continuum component with anchor points
    continuum = ContinuumComponent(name="Continuum")
    continuum.set_continuum_points([(1000.0, 1.0), (1050.0, 1.1), (1100.0, 1.05)])
    project.model.add_component(continuum)

    # Configure model metadata
    project.model.mask_definitions = [
        MaskDefinition.from_range(
            1010.0, 1015.0, label="Core Mask", identifier="mask-1"
        ).with_group_id("grp-ident")
    ]
    project.model.fit_wavelength_range = (1005.0, 1095.0)

    region = AbsorptionRegion(
        region_id="grp-ident",
        line_ids=["line-1"],
        display_color="#abcdef",
        analysis_range=(1000.0, 1020.0),
    )
    project.absorption_regions[region.region_id] = region

    line = AbsorptionLine(
        line_id="line-1",
        species="CIV",
        transition_name="C IV 1548",
        rest_wavelength=1548.19,
        center_z=2.345,
        window_kms=120.0,
        lambda_range=(1540.0, 1560.0),
        region_id=region.region_id,
        multiplet_ids=["CIV-1548", "CIV-1550"],
        multiplet_label="",
        oscillator_strength=0.1,
        gamma_value=1e8,
        model_ids=[absorber.id],
        needs_optimization=True,
        created_by="unit-test",
    )
    project.absorption_lines[line.line_id] = line

    # Identify mode persisted state
    project.identify_state.reference_z = 0.987
    project.identify_state.set_new_candidate_analysis_half_width(
        NewCandidateAnalysisHalfWidth(180.0)
    )
    project.identify_state.last_added_wavelength = 1055.0

    return project


def test_hdf5_roundtrip_preserves_project(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """Saving and loading through ProjectIOUseCase should retain key structures."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        assert len(reloaded.model.components) == len(sample_project.model.components)
        assert reloaded.model.mask_definitions == sample_project.model.mask_definitions
        assert reloaded.model.fit_wavelength_range == sample_project.model.fit_wavelength_range

        reloaded_absorber = next(
            component
            for component in reloaded.model.components
            if isinstance(component, AbsorberComponent)
        )
        assert reloaded_absorber.parameters["covering_factor"].value == pytest.approx(0.73)
        assert reloaded_absorber.parameters["covering_factor"].fixed is False

        # Spectrum arrays persisted
        assert reloaded.model.observed_spectrum is not None
        assert np.allclose(
            reloaded.model.observed_spectrum.wavelength,
            sample_project.model.observed_spectrum.wavelength,
        )
        assert np.allclose(
            reloaded.model.observed_spectrum.error, sample_project.model.observed_spectrum.error
        )

        # Absorption structures restored
        assert set(reloaded.absorption_regions.keys()) == {"grp-ident"}
        assert set(reloaded.absorption_lines.keys()) == {"line-1"}
        reloaded_line = reloaded.absorption_lines["line-1"]
        assert reloaded_line.needs_optimization is True
        assert reloaded_line.transition_name == "C IV 1548"

        # Identify state persisted (work_phase always normalizes to temporary_line_add)
        assert reloaded.identify_state.work_phase == "temporary_line_add"
        assert pytest.approx(reloaded.identify_state.reference_z, rel=1e-9) == 0.987
        assert (
            pytest.approx(reloaded.identify_state.new_candidate_analysis_half_width.kms, rel=1e-9)
            == DEFAULT_ANALYSIS_HALF_WIDTH_KMS
        )
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_roundtrip_preserves_analysis_revision_and_artifact(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """Project persistence retains region revision and successful fit evidence."""
    artifacts = AnalysisArtifactStoreUseCase()
    artifacts.invalidate(sample_project, "grp-ident")
    summary = FitSummary(
        chi_squared=12.5,
        reduced_chi_squared=1.25,
        degrees_of_freedom=10.0,
        n_parameters=4,
        n_function_evaluations=7,
        outcome=FitOutcome.CONVERGED,
    )
    RecordSuccessfulAnalysisUseCase(artifacts=artifacts).execute(
        sample_project, "grp-ident", summary
    )

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        state = reloaded.region_analysis_state("grp-ident")
        assert state is not None
        assert state.current_revision.value == 1
        assert state.artifact is not None
        assert state.artifact.source_revision.value == 1
        assert state.artifact.fit_summary == summary
        assert reloaded.is_region_needs_optimization("grp-ident") is False
    finally:
        temp_path.unlink(missing_ok=True)


def test_save_as_preserves_analysis_state(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject, tmp_path: Path
) -> None:
    """Saving the same project under a new path retains all scientific analysis state."""
    artifacts = AnalysisArtifactStoreUseCase()
    artifacts.invalidate(sample_project, "grp-ident")
    summary = FitSummary(
        chi_squared=8.5,
        reduced_chi_squared=1.7,
        degrees_of_freedom=5.0,
        n_parameters=3,
        n_function_evaluations=11,
    )
    RecordSuccessfulAnalysisUseCase(artifacts=artifacts).execute(
        sample_project, "grp-ident", summary
    )
    original_state = sample_project.region_analysis_state("grp-ident")
    assert original_state is not None
    original_path = tmp_path / "original.h5"
    save_as_path = tmp_path / "renamed.h5"
    project_io.save_project(sample_project, str(original_path))

    project_io.save_project(sample_project, str(save_as_path))

    reloaded = project_io.load_project(str(save_as_path)).project
    state = reloaded.region_analysis_state("grp-ident")
    assert state is not None
    assert state.current_revision == original_state.current_revision
    assert state.artifact is not None
    assert state.artifact.source_revision == state.current_revision
    assert state.artifact.fit_summary == summary
    assert reloaded.is_region_needs_optimization("grp-ident") is False


def test_hdf5_load_rejects_analysis_state_for_missing_region(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """An analysis-state reference cannot outlive its owning region."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))
        with h5py.File(temp_path, "r+") as handle:
            states = json.loads(handle["analysis/states_json"][()])
            states[0]["region_id"] = "missing-region"
            del handle["analysis/states_json"]
            handle["analysis"].create_dataset(
                "states_json", data=json.dumps(states), dtype=h5py.string_dtype()
            )

        with pytest.raises(ValueError, match="missing region"):
            project_io.load_project(str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_load_normalizes_legacy_grouping_work_phase(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """Files persisted with the removed "grouping" phase still load and normalize."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))

        with h5py.File(temp_path, "r+") as handle:
            payload = json.loads(handle["session/identify_json"][()])
            payload["work_phase"] = "grouping"
            del handle["session/identify_json"]
            handle["session"].create_dataset(
                "identify_json", data=json.dumps(payload), dtype=h5py.string_dtype()
            )

        reloaded = project_io.load_project(str(temp_path)).project

        assert reloaded.identify_state.work_phase == "temporary_line_add"
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_roundtrip_preserves_line_and_region_details(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """Multiplet references and region display attributes survive a roundtrip."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        original_line = sample_project.absorption_lines["line-1"]
        reloaded_line = reloaded.absorption_lines["line-1"]
        assert reloaded_line.multiplet_ids == original_line.multiplet_ids

        original_region = sample_project.absorption_regions["grp-ident"]
        reloaded_region = reloaded.absorption_regions["grp-ident"]
        assert reloaded_region.display_color == original_region.display_color
        assert reloaded_region.analysis_range == original_region.analysis_range
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_roundtrip_preserves_legacy_mlt_absorption_line(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """Schema 2.4 projects keep materialized legacy ``-mlt`` lines without DB lookup."""
    line = sample_project.absorption_lines.pop("line-1")
    line.line_id = "41a9625cec8cf0f0"
    line.transition_name = "Lyα-mlt"
    line.species = "H I"
    line.rest_wavelength = 1215.670040
    line.oscillator_strength = 0.4164
    line.gamma_value = 6.26473e8
    line.multiplet_ids = ["b30fa388ea9bd571", "f0c8118c47920f8e"]
    sample_project.absorption_lines[line.line_id] = line
    sample_project.absorption_regions["grp-ident"].line_ids = [line.line_id]

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        restored = reloaded.absorption_lines[line.line_id]
        assert restored.transition_name == "Lyα-mlt"
        assert restored.species == "H I"
        assert restored.rest_wavelength == pytest.approx(1215.670040)
        assert restored.multiplet_ids == ["b30fa388ea9bd571", "f0c8118c47920f8e"]
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_schema_contains_required_groups(
    project_io: ProjectIOUseCase, sample_project: SpectroscopyProject
) -> None:
    """Saved HDF5 v2 file exposes required groups."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(sample_project, str(temp_path))

        with h5py.File(temp_path, "r") as handle:
            assert "metadata" in handle
            schema = handle["metadata/schema_version"][()]
            assert schema.decode("utf-8") == "2.6"
            assert "data/spectrum/wavelength" in handle
            assert "project/info_json" in handle
            assert "model/components_json" in handle
            assert "analysis/regions_json" in handle
            assert "analysis/states_json" in handle
            assert "analysis/absorber_groups_json" not in handle
            assert "state/json_snapshot" not in handle

            components = json.loads(handle["model/components_json"][()])
            assert {component["kind"] for component in components} == {"absorber", "continuum"}
            assert all(
                {"algorithm", "max_function_evaluations", "tolerance", "last_result"}.isdisjoint(
                    component
                )
                for component in components
            )

            checksum = handle["metadata/checksum"][()]
            assert isinstance(checksum, (np.integer, np.uint32))
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_roundtrip_preserves_tie_sets_with_mask_and_origin(
    project_io: ProjectIOUseCase,
) -> None:
    """Full-mask multiplet and partial-mask user tie sets round-trip with mask/origin."""
    project = SpectroscopyProject(name="Tie Set Roundtrip")

    multiplet_a = AbsorberComponent(name="Ly-alpha", wavelength=1215.67, redshift=2.0)
    multiplet_b = AbsorberComponent(name="Ly-beta", wavelength=1025.72, redshift=2.0)
    project.model.add_component(multiplet_a)
    project.model.add_component(multiplet_b)
    multiplet_tie_set = ParameterTieSet("multiplet-1", name="Lyman series", origin="multiplet")
    multiplet_tie_set.add_component(multiplet_a)
    multiplet_tie_set.add_component(multiplet_b)
    project.model.add_tie_set(multiplet_tie_set)

    user_a = AbsorberComponent(name="Mg II", wavelength=2796.35, redshift=1.5)
    user_b = AbsorberComponent(name="Fe II", wavelength=2600.17, redshift=1.5)
    project.model.add_component(user_a)
    project.model.add_component(user_b)
    user_tie_set = ParameterTieSet(
        "user-1", name="z share", mask=frozenset({"redshift"}), origin="user"
    )
    user_tie_set.add_component(user_a)
    user_tie_set.add_component(user_b)
    project.model.add_tie_set(user_tie_set)

    region_a = AbsorptionRegion(region_id="region-a", line_ids=["line-a"], display_color="#111111")
    region_b = AbsorptionRegion(region_id="region-b", line_ids=["line-b"], display_color="#222222")
    project.absorption_regions[region_a.region_id] = region_a
    project.absorption_regions[region_b.region_id] = region_b

    line_a = AbsorptionLine(
        line_id="line-a",
        species="MgII",
        rest_wavelength=2796.35,
        center_z=1.5,
        window_kms=100.0,
        multiplet_label="",
        transition_name="Mg II 2796",
        oscillator_strength=0.6123,
        gamma_value=2.6e8,
        region_id=region_a.region_id,
        model_ids=[user_a.id],
        created_by="unit-test",
    )
    line_b = AbsorptionLine(
        line_id="line-b",
        species="FeII",
        rest_wavelength=2600.17,
        center_z=1.5,
        window_kms=100.0,
        multiplet_label="",
        transition_name="Fe II 2600",
        oscillator_strength=0.2239,
        gamma_value=2.9e8,
        region_id=region_b.region_id,
        model_ids=[user_b.id],
        created_by="unit-test",
    )
    project.absorption_lines[line_a.line_id] = line_a
    project.absorption_lines[line_b.line_id] = line_b

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        tie_sets_by_id = {tie_set.tie_id: tie_set for tie_set in reloaded.model.iter_tie_sets()}
        assert set(tie_sets_by_id) == {"multiplet-1", "user-1"}

        reloaded_multiplet = tie_sets_by_id["multiplet-1"]
        assert reloaded_multiplet.origin == "multiplet"
        assert reloaded_multiplet.mask == FULL_TIE_MASK
        assert {component.name for component in reloaded_multiplet.components} == {
            "Ly-alpha",
            "Ly-beta",
        }

        reloaded_user = tie_sets_by_id["user-1"]
        assert reloaded_user.origin == "user"
        assert reloaded_user.mask == frozenset({"redshift"})
        assert {component.name for component in reloaded_user.components} == {"Mg II", "Fe II"}

        reloaded_line_a = reloaded.absorption_lines["line-a"]
        reloaded_line_b = reloaded.absorption_lines["line-b"]
        assert reloaded_line_a.region_id == "region-a"
        assert reloaded_line_b.region_id == "region-b"

        reloaded_component_a = reloaded.find_absorber_component(reloaded_line_a.model_ids[0])
        reloaded_component_b = reloaded.find_absorber_component(reloaded_line_b.model_ids[0])
        assert reloaded_component_a is not None
        assert reloaded_component_b is not None

        # Members share the same z master parameter, so editing one propagates to the other.
        reloaded_component_a.set_parameter("redshift", 1.75)
        assert reloaded_component_a.get_parameter_value("redshift") == pytest.approx(1.75)
        assert reloaded_component_b.get_parameter_value("redshift") == pytest.approx(1.75)

        # logN is not in the shared mask, so it stays independent per component.
        reloaded_component_a.set_parameter("column_density", 16.0)
        assert reloaded_component_b.get_parameter_value("column_density") != pytest.approx(16.0)
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_roundtrip_preserves_nested_tie_set_relationship(
    project_io: ProjectIOUseCase,
) -> None:
    """Nested external tie sets round-trip through member_uids and direct members."""
    project = SpectroscopyProject(name="Nested Tie Set Roundtrip")
    multiplet_a = AbsorberComponent(
        name="Mg II 2796", wavelength=2796.35, redshift=1.0, b_parameter=10.0
    )
    multiplet_b = AbsorberComponent(
        name="Mg II 2803", wavelength=2803.53, redshift=1.0, b_parameter=10.0
    )
    direct = AbsorberComponent(
        name="Fe II 2600", wavelength=2600.17, redshift=1.0, b_parameter=20.0
    )
    for component in (multiplet_a, multiplet_b, direct):
        project.model.add_component(component)

    inner = ParameterTieSet("multiplet-1", name="Mg II doublet", origin="multiplet")
    inner.add_component(multiplet_a)
    inner.add_component(multiplet_b)
    outer = ParameterTieSet(
        "external-1",
        name="External z+b",
        mask=frozenset({"redshift", "b_parameter"}),
        origin="user",
    )
    outer.add_component(direct)
    outer.attach_tie_set(inner)
    project.model.add_tie_set(inner)
    project.model.add_tie_set(outer)

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        tie_sets_by_id = {tie_set.tie_id: tie_set for tie_set in reloaded.model.iter_tie_sets()}
        reloaded_inner = tie_sets_by_id["multiplet-1"]
        reloaded_outer = tie_sets_by_id["external-1"]
        reloaded_multiplet_a = next(
            component for component in reloaded.model.components if component.name == "Mg II 2796"
        )
        reloaded_multiplet_b = next(
            component for component in reloaded.model.components if component.name == "Mg II 2803"
        )
        reloaded_direct = next(
            component for component in reloaded.model.components if component.name == "Fe II 2600"
        )

        assert reloaded_inner.parent_tie is reloaded_outer
        assert reloaded_outer.member_uids == {reloaded_inner.uid}
        assert reloaded_multiplet_a.tie_set is reloaded_inner
        assert reloaded_multiplet_b.tie_set is reloaded_inner
        assert reloaded_direct.tie_set is reloaded_outer
        assert {component.name for component in reloaded_outer.components} == {
            "Mg II 2796",
            "Mg II 2803",
            "Fe II 2600",
        }
        assert (
            reloaded_multiplet_a.parameters["redshift"]
            is reloaded_outer.shared_parameters["redshift"]
        )
        assert (
            reloaded_multiplet_b.parameters["b_parameter"]
            is reloaded_outer.shared_parameters["b_parameter"]
        )
        assert (
            reloaded_multiplet_a.parameters["column_density"]
            is reloaded_inner.shared_parameters["column_density"]
        )
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_roundtrip_attaches_the_correct_inner_when_tie_ids_collide(
    project_io: ProjectIOUseCase,
) -> None:
    """A nested inner sharing its tie_id with a decoy must re-attach to the right unit."""
    project = SpectroscopyProject(name="Colliding Tie Id Roundtrip")
    inner_a = AbsorberComponent(
        name="Mg II 2796", wavelength=2796.35, redshift=1.0, b_parameter=10.0
    )
    inner_b = AbsorberComponent(
        name="Mg II 2803", wavelength=2803.53, redshift=1.0, b_parameter=10.0
    )
    direct = AbsorberComponent(
        name="Fe II 2600", wavelength=2600.17, redshift=1.0, b_parameter=20.0
    )
    decoy_a = AbsorberComponent(name="Mg II 2796 (decoy)", wavelength=2796.35, redshift=2.0)
    decoy_b = AbsorberComponent(name="Mg II 2803 (decoy)", wavelength=2803.53, redshift=2.0)
    for component in (inner_a, inner_b, direct, decoy_a, decoy_b):
        project.model.add_component(component)

    inner = ParameterTieSet("multiplet-1", name="Mg II doublet", origin="multiplet")
    inner.add_component(inner_a)
    inner.add_component(inner_b)
    decoy = ParameterTieSet("multiplet-1", name="Mg II doublet (decoy)", origin="multiplet")
    decoy.add_component(decoy_a)
    decoy.add_component(decoy_b)
    outer = ParameterTieSet(
        "external-1",
        name="External z+b",
        mask=frozenset({"redshift", "b_parameter"}),
        origin="user",
    )
    outer.add_component(direct)
    outer.attach_tie_set(inner)
    project.model.add_tie_set(inner)
    project.model.add_tie_set(decoy)
    project.model.add_tie_set(outer)

    inner_uid, decoy_uid, outer_uid = inner.uid, decoy.uid, outer.uid

    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        project_io.save_project(project, str(temp_path))
        reloaded = project_io.load_project(str(temp_path)).project

        tie_sets_by_uid = {tie_set.uid: tie_set for tie_set in reloaded.model.iter_tie_sets()}
        assert set(tie_sets_by_uid) == {inner_uid, decoy_uid, outer_uid}
        reloaded_inner = tie_sets_by_uid[inner_uid]
        reloaded_decoy = tie_sets_by_uid[decoy_uid]
        reloaded_outer = tie_sets_by_uid[outer_uid]

        assert reloaded_inner.parent_tie is reloaded_outer
        assert reloaded_outer.member_uids == {inner_uid}
        assert reloaded_decoy.parent_tie is None
        reloaded_inner_a = next(c for c in reloaded.model.components if c.name == "Mg II 2796")
        reloaded_decoy_a = next(
            c for c in reloaded.model.components if c.name == "Mg II 2796 (decoy)"
        )
        assert reloaded_inner_a.tie_set is reloaded_inner
        assert reloaded_decoy_a.tie_set is reloaded_decoy
        assert (
            reloaded_inner_a.parameters["redshift"] is reloaded_outer.shared_parameters["redshift"]
        )
        assert (
            reloaded_decoy_a.parameters["redshift"]
            is not reloaded_outer.shared_parameters["redshift"]
        )
    finally:
        temp_path.unlink(missing_ok=True)


def test_hdf5_repository_rejects_unsupported_schema() -> None:
    """Old project schema versions should fail explicitly."""
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        with h5py.File(temp_path, "w") as handle:
            metadata_group = handle.create_group("metadata")
            metadata_group.create_dataset(
                "schema_version", data="1.3", dtype=h5py.string_dtype("utf-8")
            )

        with pytest.raises(ValueError, match="Unsupported project schema version"):
            HDF5ProjectRepository().load(str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)
