"""Coverage checks tying TutorialCompletion/FitOutcome enums to their consumers.

Separate from test_tutorial_chapter_semantics.py, which asserts per-step
target/text facts: these tests instead guard the enum-vs-resolver drift the
step-gating design explicitly warns about (docs/task/onboarding-tutorial/
step-gating-requirements.md) -- a step referencing a TutorialCompletion
nobody resolves, an unused TutorialCompletion member, or a FitOutcome missing
from FIT_OUTCOME_NOTE_SOURCES that would KeyError inside
MainWindow._tutorial_region_fit_note.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from chappy.core.components.optimize import FitOutcome
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.presets import METAL_LINES_PRESET_ID, Preset, PresetTieGroup
from chappy.gui.common.tutorial import (
    COMPLETION_NOTE_SOURCES,
    FIT_OUTCOME_NOTE_SOURCES,
    TutorialCompletion,
)
from chappy.gui.modes.analysis.contracts import PanelState
from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
from chappy.gui.shell.composition import create_main_window
from chappy.gui.shell.dependencies import ShellDependencies
from chappy.gui.shell.main_window import (
    _SAMPLE_RESOLVING_POWER,
    _TUTORIAL_PRESET_LINE_IDS,
    _find_sample_spectrum_pair,
)
from chappy.infrastructure import preset_store as infrastructure_preset_store
from chappy.infrastructure.composition import create_default_infrastructure_dependencies
from tests.helpers.tutorial_chapters import all_walkthrough_chapters

if TYPE_CHECKING:
    from pathlib import Path

    from chappy.gui.shell.main_window import MainWindow


@pytest.fixture(autouse=True)
def _isolate_preset_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep GUI tests isolated from the user's persistent preset file."""
    monkeypatch.setattr(
        infrastructure_preset_store, "DEFAULT_PRESET_PATH", tmp_path / "presets.json"
    )


def _required_completions() -> set[TutorialCompletion]:
    return {
        step.requires
        for chapter in all_walkthrough_chapters()
        for step in chapter.steps
        if step.requires is not None
    }


def test_every_tutorial_completion_member_is_used_by_a_walkthrough_step() -> None:
    """No TutorialCompletion member is dead: each gates at least one real step."""
    assert _required_completions() == set(TutorialCompletion)


def _main_window(qtbot) -> MainWindow:
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
    return window


def test_every_step_requires_condition_has_a_main_window_resolver(qtbot) -> None:
    """No walkthrough step references a condition MainWindow leaves unresolved."""
    window = _main_window(qtbot)

    resolvers = window._tutorial_completion_checks()

    assert _required_completions() <= resolvers.keys()


def test_identify_gates_follow_the_preset_and_reference_line_selection(qtbot) -> None:
    """The identify gates must open only once C IV 1548 is the active reference line."""
    window = _main_window(qtbot)
    resolvers = window._tutorial_completion_checks()
    preset_selected = resolvers[TutorialCompletion.METAL_LINES_PRESET_SELECTED]
    reference_is_civ1548 = resolvers[TutorialCompletion.REFERENCE_LINE_IS_CIV1548]

    window.preset_store.set_current_preset(METAL_LINES_PRESET_ID)

    assert preset_selected()
    assert not reference_is_civ1548()

    window.preset_store.set_baseline(METAL_LINES_PRESET_ID, _civ1548_line_id(window))

    assert reference_is_civ1548()


def _civ1548_line_id(window: MainWindow) -> str:
    preset = window.preset_store.get_preset(METAL_LINES_PRESET_ID)
    assert preset is not None
    for line_id in preset.line_ids:
        line = window._atomic_data.get_line_by_id(line_id)
        if line is not None and line.species == "C IV" and round(line.wavelength_angstrom) == 1548:
            return line_id
    msg = "The Metal Lines preset must contain C IV 1548."
    raise AssertionError(msg)


def test_fit_outcome_note_sources_cover_every_fit_outcome() -> None:
    """Every FitOutcome member has a note so _tutorial_region_fit_note cannot KeyError."""
    assert set(FIT_OUTCOME_NOTE_SOURCES) == set(FitOutcome)


def test_every_noted_condition_has_a_main_window_note_resolver(qtbot) -> None:
    """Each note source is reachable: MainWindow resolves every noted condition."""
    window = _main_window(qtbot)

    assert set(COMPLETION_NOTE_SOURCES) <= window._tutorial_completion_notes().keys()


def _species_line_ids(window: MainWindow, species: str, count: int) -> list[str]:
    line_ids = [
        line.line_id for line in window._atomic_data.search_lines() if line.species == species
    ][:count]
    assert len(line_ids) == count
    return line_ids


def _tutorial_preset(window: MainWindow, *, fe2: int, mg2: int) -> Preset:
    tutorial_ids_by_species = {
        species: [
            line_id
            for line_id in _TUTORIAL_PRESET_LINE_IDS
            if (line := window._atomic_data.get_line_by_id(line_id)) is not None
            and line.species == species
        ]
        for species in ("Fe II", "Mg II")
    }

    def _line_ids(species: str, count: int) -> list[str]:
        requested = tutorial_ids_by_species[species][:count]
        if len(requested) == count:
            return requested
        extras = [
            line.line_id
            for line in window._atomic_data.search_lines()
            if line.species == species and line.line_id not in tutorial_ids_by_species[species]
        ]
        return [*requested, *extras[: count - len(requested)]]

    return Preset(
        id="tutorial-note-test",
        name="Tutorial note test",
        source="custom",
        line_ids=[*_line_ids("Fe II", fe2), *_line_ids("Mg II", mg2)],
    )


def _tutorial_species_line_ids(window: MainWindow, species: str) -> list[str]:
    preset = _tutorial_preset(window, fe2=4, mg2=2)
    return [
        line_id
        for line_id in preset.line_ids
        if (line := window._atomic_data.get_line_by_id(line_id)) is not None
        and line.species == species
    ]


def _preset_lines_note(qtbot, monkeypatch, *, fe2: int, mg2: int) -> str | None:
    window = _main_window(qtbot)
    preset = _tutorial_preset(window, fe2=fe2, mg2=mg2)
    monkeypatch.setattr(window, "_current_tutorial_preset", lambda: preset)
    return window._tutorial_completion_notes()[TutorialCompletion.PRESET_HAS_TUTORIAL_LINES]()


def test_preset_lines_note_reports_the_missing_species_counts(qtbot, monkeypatch) -> None:
    """A preset short of Mg II explains the gate with its live counts."""
    note = _preset_lines_note(qtbot, monkeypatch, fe2=4, mg2=0)

    assert note == COMPLETION_NOTE_SOURCES[TutorialCompletion.PRESET_HAS_TUTORIAL_LINES].format(
        fe2_count=4, mg2_count=0
    )


def test_preset_lines_note_reports_surplus_lines_that_also_hold_the_gate(
    qtbot, monkeypatch
) -> None:
    """The exact-count gate also closes on surplus lines, and the note says so."""
    note = _preset_lines_note(qtbot, monkeypatch, fe2=4, mg2=3)

    assert note is not None
    assert "Mg II 3" in note


def test_preset_lines_note_disappears_once_the_gate_opens(qtbot, monkeypatch) -> None:
    """No note is shown while the tutorial lines are exactly in place."""
    assert _preset_lines_note(qtbot, monkeypatch, fe2=4, mg2=2) is None


def test_existing_custom_preset_does_not_satisfy_new_preset_gate(qtbot) -> None:
    """A custom preset present at tour start cannot stand in for clicking New."""
    window = _main_window(qtbot)
    existing = window.preset_store.create_custom_preset("Existing")
    window._tutorial_initial_preset_ids = frozenset(
        preset.id for preset in window.preset_store.list_presets()
    )
    window.preset_store.set_current_preset(existing.id)

    gate = window._tutorial_completion_checks()[TutorialCompletion.NEW_TUTORIAL_PRESET_SELECTED]
    assert not gate()

    created = window.preset_store.create_custom_preset("New")
    assert gate()
    window.preset_store.set_current_preset(existing.id)
    assert not gate()
    window.preset_store.set_current_preset(created.id)
    assert gate()


def test_tutorial_preset_gate_checks_ids_and_rejects_extra_lines(qtbot, monkeypatch) -> None:
    """Species counts alone cannot satisfy the six specifically requested transitions."""
    window = _main_window(qtbot)
    gate = window._tutorial_completion_checks()[TutorialCompletion.PRESET_HAS_TUTORIAL_LINES]
    exact = Preset(
        id="exact", name="Exact", source="custom", line_ids=list(_TUTORIAL_PRESET_LINE_IDS)
    )
    monkeypatch.setattr(window, "_current_tutorial_preset", lambda: exact)
    assert gate()

    wrong = _tutorial_preset(window, fe2=4, mg2=2)
    wrong.line_ids[0] = next(
        line.line_id
        for line in window._atomic_data.search_lines()
        if line.species == "Fe II" and line.line_id not in _TUTORIAL_PRESET_LINE_IDS
    )
    monkeypatch.setattr(window, "_current_tutorial_preset", lambda: wrong)
    assert not gate()

    exact.line_ids.append(_species_line_ids(window, "C IV", 1)[0])
    monkeypatch.setattr(window, "_current_tutorial_preset", lambda: exact)
    assert not gate()

    duplicate = Preset(
        id="duplicate",
        name="Duplicate",
        source="custom",
        line_ids=[*_TUTORIAL_PRESET_LINE_IDS, next(iter(_TUTORIAL_PRESET_LINE_IDS))],
    )
    monkeypatch.setattr(window, "_current_tutorial_preset", lambda: duplicate)
    assert not gate()


def _fe2_single_group_met(
    window: MainWindow, monkeypatch, tie_groups: list[PresetTieGroup]
) -> bool:
    preset = _tutorial_preset(window, fe2=4, mg2=2)
    preset.tie_groups = tie_groups
    preset.line_ids.extend(
        line_id
        for group in tie_groups
        for line_id in group.line_ids
        if line_id not in preset.line_ids
    )
    monkeypatch.setattr(window, "_current_tutorial_preset", lambda: preset)
    return window._tutorial_completion_checks()[TutorialCompletion.PRESET_FE2_SINGLE_GROUP]()


def test_fe2_single_group_gate_opens_while_the_mg2_link_is_kept(qtbot, monkeypatch) -> None:
    """The step tells the user to keep the automatic Mg II link, so it cannot hold the gate."""
    window = _main_window(qtbot)
    fe2_line_ids = _tutorial_species_line_ids(window, "Fe II")
    mg2_line_ids = _tutorial_species_line_ids(window, "Mg II")

    assert _fe2_single_group_met(
        window,
        monkeypatch,
        [
            PresetTieGroup(uid="fe2", line_ids=tuple(fe2_line_ids)),
            PresetTieGroup(uid="mg2", line_ids=tuple(mg2_line_ids)),
        ],
    )


def test_fe2_single_group_gate_stays_shut_while_fe2_spans_two_links(qtbot, monkeypatch) -> None:
    """Two Fe II multiplets are the state the step exists to merge."""
    window = _main_window(qtbot)
    fe2_line_ids = _tutorial_species_line_ids(window, "Fe II")

    assert not _fe2_single_group_met(
        window,
        monkeypatch,
        [
            PresetTieGroup(uid="fe2-lower", line_ids=tuple(fe2_line_ids[:2])),
            PresetTieGroup(uid="fe2-upper", line_ids=tuple(fe2_line_ids[2:])),
        ],
    )


def test_fe2_single_group_gate_stays_shut_while_one_fe2_line_is_left_out(
    qtbot, monkeypatch
) -> None:
    """A link covering only three Fe II lines is not the shared link the step asks for."""
    window = _main_window(qtbot)
    fe2_line_ids = _tutorial_species_line_ids(window, "Fe II")
    mg2_line_ids = _tutorial_species_line_ids(window, "Mg II")

    assert not _fe2_single_group_met(
        window,
        monkeypatch,
        [
            PresetTieGroup(uid="fe2", line_ids=tuple(fe2_line_ids[:3])),
            PresetTieGroup(uid="mg2", line_ids=tuple(mg2_line_ids)),
        ],
    )


def test_fe2_single_group_gate_stays_shut_once_the_mg2_link_is_destroyed(
    qtbot, monkeypatch
) -> None:
    """Step 8 also asserts the Mg II link, which nothing later in the tour re-checks."""
    window = _main_window(qtbot)
    fe2_line_ids = _tutorial_species_line_ids(window, "Fe II")

    assert not _fe2_single_group_met(
        window, monkeypatch, [PresetTieGroup(uid="fe2", line_ids=tuple(fe2_line_ids))]
    )


def test_fe2_single_group_gate_stays_shut_while_mg2_spans_two_links(qtbot, monkeypatch) -> None:
    """Split Mg II lines would each register as their own region, which the step forbids."""
    window = _main_window(qtbot)
    fe2_line_ids = _tutorial_species_line_ids(window, "Fe II")
    mg2_line_ids = _tutorial_species_line_ids(window, "Mg II")
    other_line_ids = _species_line_ids(window, "C IV", 2)

    assert not _fe2_single_group_met(
        window,
        monkeypatch,
        [
            PresetTieGroup(uid="fe2", line_ids=tuple(fe2_line_ids)),
            PresetTieGroup(uid="mg2-a", line_ids=(mg2_line_ids[0], other_line_ids[0])),
            PresetTieGroup(uid="mg2-b", line_ids=(mg2_line_ids[1], other_line_ids[1])),
        ],
    )


def test_fe2_single_group_gate_stays_shut_while_a_link_mixes_in_a_foreign_line(
    qtbot, monkeypatch
) -> None:
    """An Fe II line linked to anything else is not the four-line link the step asks for."""
    window = _main_window(qtbot)
    fe2_line_ids = _tutorial_species_line_ids(window, "Fe II")
    mg2_line_ids = _tutorial_species_line_ids(window, "Mg II")
    other_line_id = _species_line_ids(window, "C IV", 1)[0]

    assert not _fe2_single_group_met(
        window,
        monkeypatch,
        [
            PresetTieGroup(uid="fe2", line_ids=tuple(fe2_line_ids)),
            PresetTieGroup(uid="stray", line_ids=(fe2_line_ids[0], other_line_id)),
            PresetTieGroup(uid="mg2", line_ids=tuple(mg2_line_ids)),
        ],
    )


def _window_with_sample(qtbot, monkeypatch) -> MainWindow:
    monkeypatch.setenv("CHAPPY_DOC_AUTO_DISCARD", "1")
    window = _main_window(qtbot)
    sample_pair = _find_sample_spectrum_pair()
    assert sample_pair is not None, "bundled sample spectrum is missing"
    flux_path, error_path = sample_pair
    window._require_project_session().open_sample_data(
        str(flux_path), str(error_path), resolving_power=_SAMPLE_RESOLVING_POWER
    )
    return window


def _register_region(
    window: MainWindow, species: str, rest_wavelengths: tuple[float, ...], *, redshift: float
) -> str:
    project = window.current_project
    assert project is not None
    line_ids = []
    for rest_wavelength in rest_wavelengths:
        observed = rest_wavelength * (1.0 + redshift)
        line = project.add_absorption_line(
            species=species,
            rest_wavelength=rest_wavelength,
            center_z=redshift,
            window_kms=200.0,
            multiplet_label=species,
            transition_name=f"{species} {rest_wavelength:.0f}",
            oscillator_strength=0.1,
            gamma_value=1.0e8,
            lambda_range=(observed - 3.0, observed + 3.0),
        )
        line_ids.append(line.line_id)
    return project.create_region_with_lines(line_ids).region_id


_ABSORBER_REDSHIFT = 0.7627
_FE2_REST_WAVELENGTHS = (2382.8, 2600.2, 2586.6, 2374.5)
_MG2_REST_WAVELENGTHS = (2796.4, 2803.5)


def _fe2_and_mg2_regions_exist(window: MainWindow) -> bool:
    return window._tutorial_completion_checks()[TutorialCompletion.FE2_AND_MG2_REGIONS_EXIST]()


def test_registration_gate_opens_on_the_two_regions_the_step_promises(qtbot, monkeypatch) -> None:
    """The step's expected text names a 4-line Fe II region and a 2-line Mg II region."""
    window = _window_with_sample(qtbot, monkeypatch)
    _register_region(window, "Fe II", _FE2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT)
    _register_region(window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT)

    assert _fe2_and_mg2_regions_exist(window)


def test_registration_gate_stays_shut_when_only_mg2_was_registered(qtbot, monkeypatch) -> None:
    """A pre-existing region plus Mg II alone reached two regions and hid the missing Fe II."""
    window = _window_with_sample(qtbot, monkeypatch)
    _register_region(window, "C IV", (1548.2, 1550.8), redshift=2.0764)
    _register_region(window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT)

    assert window._confirmed_tutorial_region_count() >= 2
    assert not _fe2_and_mg2_regions_exist(window)


def test_registration_gate_stays_shut_while_fe2_split_into_single_line_regions(
    qtbot, monkeypatch
) -> None:
    """Unlinked Fe II lines register one region each, which the step's text forbids."""
    window = _window_with_sample(qtbot, monkeypatch)
    for rest_wavelength in _FE2_REST_WAVELENGTHS:
        _register_region(window, "Fe II", (rest_wavelength,), redshift=_ABSORBER_REDSHIFT)
    _register_region(window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT)

    assert not _fe2_and_mg2_regions_exist(window)


def _focus_region_detail(window: MainWindow, region_id: str) -> None:
    assert window._analysis_navigation.focus_region(region_id)
    window._require_analysis_surface_coordinator()._panel_state = PanelState.REGION_DETAIL


def _add_species_components(window: MainWindow, species: str, count: int) -> None:
    project = window.current_project
    assert project is not None
    region_id = window._analysis_navigation.state.focused_region_id
    assert region_id is not None
    lines = project.find_lines_for_region(region_id)
    assert lines is not None
    for line in lines:
        if line.species != species:
            continue
        for index in range(count):
            component = AbsorberComponent(
                name=f"{species}-{index}", wavelength=line.rest_wavelength, group_id=region_id
            )
            project.model.add_component(component)
            line.model_ids.append(component.id)


def test_opened_region_gate_rejects_an_unrelated_detail_region(qtbot, monkeypatch) -> None:
    """Opening C IV cannot hand the joint-fit chapter the wrong focused region."""
    window = _window_with_sample(qtbot, monkeypatch)
    civ_region = _register_region(window, "C IV", (1548.2, 1550.8), redshift=2.0764)
    fe_region = _register_region(
        window, "Fe II", _FE2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT
    )
    mg_region = _register_region(
        window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT
    )
    project = window.current_project
    assert project is not None
    project.move_absorption_lines(
        project.absorption_regions[mg_region].line_ids, target_region_id=fe_region
    )
    gate = window._tutorial_completion_checks()[
        TutorialCompletion.TUTORIAL_MULTI_ION_REGION_OPENED
    ]

    _focus_region_detail(window, civ_region)
    assert not gate()
    _focus_region_detail(window, fe_region)
    assert gate()

    project.move_absorption_lines(
        [project.absorption_regions[civ_region].line_ids[0]], target_region_id=fe_region
    )
    assert not gate()


def test_joint_component_gates_distinguish_species_and_count(qtbot, monkeypatch) -> None:
    """Fe addition cannot open Mg addition, and both ions need three components."""
    window = _window_with_sample(qtbot, monkeypatch)
    region_id = _register_region(
        window, "Fe II", _FE2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT
    )
    mg_region = _register_region(
        window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT
    )
    project = window.current_project
    assert project is not None
    project.move_absorption_lines(
        project.absorption_regions[mg_region].line_ids, target_region_id=region_id
    )
    _focus_region_detail(window, region_id)
    gates = window._tutorial_completion_checks()

    _add_species_components(window, "Fe II", 1)
    assert gates[TutorialCompletion.FE2_COMPONENT_EXISTS]()
    assert not gates[TutorialCompletion.MG2_COMPONENT_EXISTS]()
    assert not gates[TutorialCompletion.FE2_AND_MG2_HAVE_THREE_COMPONENTS]()

    _add_species_components(window, "Mg II", 1)
    assert gates[TutorialCompletion.MG2_COMPONENT_EXISTS]()
    assert not gates[TutorialCompletion.FE2_AND_MG2_HAVE_THREE_COMPONENTS]()

    _add_species_components(window, "Fe II", 2)
    _add_species_components(window, "Mg II", 2)
    assert gates[TutorialCompletion.FE2_AND_MG2_HAVE_THREE_COMPONENTS]()


def test_fixed_mg2_gate_tracks_only_the_logn_fix(qtbot, monkeypatch) -> None:
    """The fix step opens on the parameter edit alone; the refit is a separate step."""
    window = _window_with_sample(qtbot, monkeypatch)
    region_id = _register_region(
        window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT
    )
    _focus_region_detail(window, region_id)
    _add_species_components(window, "Mg II", 1)
    gate = window._tutorial_completion_checks()[TutorialCompletion.MG2_LOGN_FIXED]
    assert not gate()

    project = window.current_project
    assert project is not None
    mg_line = window._tutorial_focused_region_lines("Mg II")[0]
    component = project.find_absorber_component(mg_line.model_ids[0])
    assert component is not None
    component.parameters["column_density"].fixed = True
    assert gate()


def test_fixed_mg2_note_explains_the_closed_gate_until_logn_is_fixed(qtbot, monkeypatch) -> None:
    """The gated step shows how to fix logN instead of only a disabled [Next]."""
    window = _window_with_sample(qtbot, monkeypatch)
    region_id = _register_region(
        window, "Mg II", _MG2_REST_WAVELENGTHS, redshift=_ABSORBER_REDSHIFT
    )
    _focus_region_detail(window, region_id)
    _add_species_components(window, "Mg II", 1)
    note = window._tutorial_completion_notes()[TutorialCompletion.MG2_LOGN_FIXED]

    assert note() == COMPLETION_NOTE_SOURCES[TutorialCompletion.MG2_LOGN_FIXED]

    project = window.current_project
    assert project is not None
    mg_line = window._tutorial_focused_region_lines("Mg II")[0]
    component = project.find_absorber_component(mg_line.model_ids[0])
    assert component is not None
    component.parameters["column_density"].fixed = True

    assert note() is None
