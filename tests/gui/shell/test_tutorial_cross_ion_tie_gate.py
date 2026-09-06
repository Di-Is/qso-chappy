"""The cross-ion redshift gate must see a tie nested over per-ion multiplet ties.

Sharing z between two ions whose lines are already multiplet-linked does not
retie the components: the use case nests each ion's existing tie set under a
new redshift-only parent. ``component.tie_set`` therefore still points at the
per-ion multiplet tie, and the shared redshift lives on its parent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chappy.application.optimize.tie_set_edit_usecase import TieSetCreated, TieSetEditUseCase
from chappy.core.atomic_data import AtomicLine
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.tie_set import FULL_TIE_MASK, ParameterTieSet
from chappy.gui.modes.analysis.region_detail.composition import (
    create_optimize_parameter_mutation_usecase,
)
from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
from chappy.gui.shell.composition import create_main_window
from chappy.gui.shell.dependencies import ShellDependencies
from chappy.gui.shell.main_window import _SAMPLE_RESOLVING_POWER, _find_sample_spectrum_pair
from chappy.infrastructure.composition import create_default_infrastructure_dependencies

if TYPE_CHECKING:
    from chappy.core.spectroscopy_project import SpectroscopyProject
    from chappy.gui.shell.main_window import ChappyMain

_REDSHIFT = 0.76274
_WINDOW_KMS = 200.0
_LIGHT_SPEED_KMS = 299792.458

_FE2_LINES = ((2382.765, 0.320), (2600.173, 0.239))
_MG2_LINES = ((2796.352, 0.608), (2803.531, 0.303))


def _window(qtbot, monkeypatch) -> ChappyMain:
    monkeypatch.setenv("CHAPPY_DOC_AUTO_DISCARD", "1")
    dependencies = create_default_infrastructure_dependencies(translate_presets=str)
    window = create_main_window(
        ShellDependencies(
            project_io_usecase=dependencies.project_io_usecase,
            atomic_data=dependencies.atomic_repository,
            preset_store=IdentifyPresetStore(dependencies.preset_store),
            optimize_model_addition_usecase=dependencies.optimize_model_addition_usecase,
        )
    )
    qtbot.addWidget(window)
    sample_pair = _find_sample_spectrum_pair()
    assert sample_pair is not None, "bundled sample spectrum is missing"
    flux_path, error_path = sample_pair
    window._require_project_session().open_sample_data(
        str(flux_path), str(error_path), resolving_power=_SAMPLE_RESOLVING_POWER
    )
    return window


def _add_ion(
    project: SpectroscopyProject, species: str, lines: tuple[tuple[float, float], ...]
) -> tuple[str, ParameterTieSet, AbsorberComponent]:
    """Add one ion's lines with a component each, tied as a multiplet."""
    line_ids: list[str] = []
    tie_set = ParameterTieSet(species, mask=FULL_TIE_MASK, origin="multiplet")
    first: AbsorberComponent | None = None
    for rest_wavelength, oscillator_strength in lines:
        observed = rest_wavelength * (1.0 + _REDSHIFT)
        half_width = observed * _WINDOW_KMS / _LIGHT_SPEED_KMS
        line = project.add_absorption_line(
            species=species,
            rest_wavelength=rest_wavelength,
            center_z=_REDSHIFT,
            window_kms=_WINDOW_KMS,
            multiplet_label=species,
            transition_name=f"{species} {rest_wavelength:.0f}",
            oscillator_strength=oscillator_strength,
            gamma_value=3.0e8,
            lambda_range=(observed - half_width, observed + half_width),
        )
        component = AbsorberComponent.from_atomic_line(
            AtomicLine(
                line_identifier=f"{species}-{rest_wavelength:.0f}",
                species=species,
                wavelength_angstrom=rest_wavelength,
                oscillator_strength=oscillator_strength,
                gamma_value=3.0e8,
            ),
            redshift=_REDSHIFT,
        )
        project.model.add_component(component)
        line.model_ids.append(component.id)
        tie_set.add_component(component)
        line_ids.append(line.line_id)
        first = first or component
    project.model.add_tie_set(tie_set)
    assert first is not None
    return line_ids, tie_set, first


def _multi_ion_region(
    project: SpectroscopyProject,
) -> tuple[str, AbsorberComponent, AbsorberComponent]:
    fe2_line_ids, _, fe2_component = _add_ion(project, "Fe II", _FE2_LINES)
    mg2_line_ids, _, mg2_component = _add_ion(project, "Mg II", _MG2_LINES)
    region = project.create_region_with_lines([*fe2_line_ids, *mg2_line_ids])
    return region.region_id, fe2_component, mg2_component


def test_the_gate_opens_for_a_tie_nested_over_per_ion_multiplet_ties(qtbot, monkeypatch) -> None:
    window = _window(qtbot, monkeypatch)
    project = window.current_project
    assert project is not None
    region_id, fe2_component, mg2_component = _multi_ion_region(project)
    assert window.open_analysis_region(region_id)

    assert not window._tutorial_cross_ion_redshift_tie_exists()

    result = TieSetEditUseCase(
        redshift_tolerance=5e-5, parameter_mutation=create_optimize_parameter_mutation_usecase()
    ).create_tie_set(project.model, (fe2_component, mg2_component), frozenset({"redshift"}))

    assert isinstance(result, TieSetCreated)
    assert fe2_component.tie_set is not None
    assert fe2_component.tie_set.mask == FULL_TIE_MASK
    assert fe2_component.tie_set.parent_tie is result.tie_set
    assert window._tutorial_cross_ion_redshift_tie_exists()
