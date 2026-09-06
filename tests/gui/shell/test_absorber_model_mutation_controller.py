"""Tests for shell-owned absorber scientific mutations."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import numpy as np
import pytest

from chappy.application.history import ComponentParameterState, component_parameter_state
from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.analysis import AnalysisRevision
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.gui.shell.absorber_model_mutation_controller import (
    AbsorberModelMutationController,
    AbsorberModelMutationPorts,
)


@dataclass(frozen=True, slots=True)
class _HistoryRecord:
    """One absorber parameter history record."""

    component_ids: tuple[str, ...]
    parameter_name: str
    before_states: tuple[ComponentParameterState, ...]
    after_states: tuple[ComponentParameterState, ...]


@dataclass(slots=True)
class _History:
    """History test double with injectable record failure."""

    fail_record: bool = False
    records: list[_HistoryRecord] = field(default_factory=list)

    @contextlib.contextmanager
    def atomic_recording(self):
        """Provide a focused history recording boundary."""
        yield

    def record_model_edit_params(
        self,
        component_ids: list[str],
        param_name: str,
        before_states: tuple[ComponentParameterState, ...],
        after_states: tuple[ComponentParameterState, ...],
        _region_id: str | None,
    ) -> None:
        """Record one edit or raise an injected failure."""
        if self.fail_record:
            raise RuntimeError("injected absorber history failure")
        self.records.append(
            _HistoryRecord(tuple(component_ids), param_name, before_states, after_states)
        )


@dataclass(slots=True)
class _Observers:
    """Post-commit observer counters with injectable failure."""

    fail_data_update: bool = False
    data_updates: int = 0
    optimize_refreshes: int = 0
    plot_refreshes: int = 0
    velocity_refreshes: int = 0
    focused_component_ids: list[str] = field(default_factory=list)

    def update_data(self) -> None:
        """Record the model-update publication or fail."""
        self.data_updates += 1
        if self.fail_data_update:
            raise RuntimeError("injected absorber observer failure")


def _add_region(project: SpectroscopyProject, region_id: str) -> None:
    """Add one analysis-capable region whose line starts fresh."""
    line_id = f"line-{region_id}"
    project.absorption_lines[line_id] = AbsorptionLine(
        line_id=line_id,
        species="H I",
        rest_wavelength=1215.67,
        center_z=2.0,
        window_kms=100.0,
        multiplet_label="Ly alpha",
        transition_name="Ly alpha",
        oscillator_strength=0.4,
        gamma_value=1e8,
        region_id=region_id,
        needs_optimization=False,
    )
    project.absorption_regions[region_id] = AbsorptionRegion(
        region_id=region_id, line_ids=[line_id]
    )


def _project_with_absorber() -> tuple[SpectroscopyProject, AbsorberComponent]:
    """Create a real project with one absorber and two capable regions."""
    project = SpectroscopyProject(name="Shell Absorber Mutation Test")
    wavelength = np.linspace(3600.0, 3700.0, 101)
    project.model.set_observed_spectrum(
        Spectrum(
            wavelength=wavelength,
            flux=np.ones_like(wavelength),
            error=np.full_like(wavelength, 0.05),
        )
    )
    component = AbsorberComponent(
        name="H I", wavelength=1215.67, redshift=2.0, component_id="component-1"
    )
    project.model.add_component(component)
    _add_region(project, "region-1")
    _add_region(project, "region-2")
    return project, component


def _controller(
    project: SpectroscopyProject, *, history: _History | None, observers: _Observers
) -> AbsorberModelMutationController:
    """Create a controller with deterministic shell collaborators."""
    return AbsorberModelMutationController(
        ports=AbsorberModelMutationPorts(
            project_provider=lambda: project,
            line_info_provider=lambda _component: None,
            history_provider=lambda: history,
            plot_widget_provider=lambda: None,
            plot_refresh_callback=lambda: setattr(
                observers, "plot_refreshes", observers.plot_refreshes + 1
            ),
            data_updated_callback=observers.update_data,
            refresh_optimize_callback=lambda: setattr(
                observers, "optimize_refreshes", observers.optimize_refreshes + 1
            ),
            focus_component_callback=observers.focused_component_ids.append,
            refresh_velocity_overlay_callback=lambda: setattr(
                observers, "velocity_refreshes", observers.velocity_refreshes + 1
            ),
        )
    )


def test_parameter_control_edit_commits_global_invalidation_and_history() -> None:
    """A normal shell parameter edit should stale every capable region atomically."""
    project, component = _project_with_absorber()
    history = _History()
    observers = _Observers()

    _controller(project, history=history, observers=observers).update_parameter(
        component.id, "column_density", 14.5
    )

    assert component.parameters["column_density"].value == pytest.approx(14.5)
    assert len(history.records) == 1
    assert history.records[0].component_ids == (component.id,)
    assert history.records[0].parameter_name == "column_density"
    assert all(
        state.current_revision == AnalysisRevision(1) for state in project.region_analysis_states()
    )
    assert all(line.needs_optimization for line in project.absorption_lines.values())
    assert observers.data_updates == 1
    assert observers.optimize_refreshes == 1
    assert observers.velocity_refreshes == 1
    assert observers.plot_refreshes == 1


def test_identical_parameter_control_edit_is_no_change() -> None:
    """An identical shell edit should not record, invalidate, or notify observers."""
    project, component = _project_with_absorber()
    history = _History()
    observers = _Observers()

    _controller(project, history=history, observers=observers).update_parameter(
        component.id, "column_density", component.parameters["column_density"].value
    )

    assert history.records == []
    assert all(
        state.current_revision == AnalysisRevision(0) for state in project.region_analysis_states()
    )
    assert all(not line.needs_optimization for line in project.absorption_lines.values())
    assert observers.data_updates == 0
    assert observers.optimize_refreshes == 0
    assert observers.velocity_refreshes == 0
    assert observers.plot_refreshes == 0


def test_parameter_control_edit_requires_history_before_mutation() -> None:
    """A shell parameter edit must fail before mutation when history is unavailable."""
    project, component = _project_with_absorber()
    observers = _Observers()

    with pytest.raises(RuntimeError, match="require a history owner"):
        _controller(project, history=None, observers=observers).update_parameter(
            component.id, "column_density", 14.5
        )

    assert component.parameters["column_density"].value == pytest.approx(14.0)
    assert all(
        state.current_revision == AnalysisRevision(0) for state in project.region_analysis_states()
    )
    assert all(not line.needs_optimization for line in project.absorption_lines.values())
    assert observers.data_updates == 0


def test_drag_history_failure_rolls_back_parameter_and_freshness() -> None:
    """A failed drag history record should restore all scientific transaction facts."""
    project, component = _project_with_absorber()
    history = _History(fail_record=True)
    observers = _Observers()
    before_states = (component_parameter_state(component),)
    modified_before = project.modified

    with pytest.raises(RuntimeError, match="injected absorber history failure"):
        _controller(project, history=history, observers=observers).apply_drag(
            component.id, 2.01, before_states
        )

    assert component.parameters["redshift"].value == pytest.approx(2.0)
    assert all(
        state.current_revision == AnalysisRevision(0) for state in project.region_analysis_states()
    )
    assert all(not line.needs_optimization for line in project.absorption_lines.values())
    assert project.modified == modified_before
    assert observers.data_updates == 0
    assert observers.optimize_refreshes == 0
    assert observers.plot_refreshes == 0
    assert observers.focused_component_ids == []


def test_completed_drag_records_one_history_entry() -> None:
    """A completed drag should commit and record its begin snapshot exactly once."""
    project, component = _project_with_absorber()
    history = _History()
    observers = _Observers()
    before_states = (component_parameter_state(component),)

    _controller(project, history=history, observers=observers).apply_drag(
        component.id, 2.01, before_states
    )

    assert component.parameters["redshift"].value == pytest.approx(2.01)
    assert len(history.records) == 1
    assert history.records[0].component_ids == (component.id,)
    assert history.records[0].parameter_name == "redshift"
    assert history.records[0].before_states == before_states
    redshift_state = next(
        state
        for state in history.records[0].after_states[0].parameters
        if state.name == "redshift"
    )
    assert redshift_state.value == pytest.approx(2.01)
    assert observers.data_updates == 1


def test_drag_observer_failure_keeps_committed_scientific_state() -> None:
    """A failed post-commit observer must not block later drag refresh actions."""
    project, component = _project_with_absorber()
    history = _History()
    observers = _Observers(fail_data_update=True)
    before_states = (component_parameter_state(component),)

    _controller(project, history=history, observers=observers).apply_drag(
        component.id, 2.01, before_states
    )

    assert component.parameters["redshift"].value == pytest.approx(2.01)
    assert all(
        state.current_revision == AnalysisRevision(1) for state in project.region_analysis_states()
    )
    assert all(line.needs_optimization for line in project.absorption_lines.values())
    assert observers.data_updates == 1
    assert observers.optimize_refreshes == 1
    assert observers.plot_refreshes == 1
    assert observers.focused_component_ids == [component.id]


def test_drag_requires_history_before_mutation() -> None:
    """A completed drag must fail before mutation when history is unavailable."""
    project, component = _project_with_absorber()
    observers = _Observers()
    before_states = (component_parameter_state(component),)

    with pytest.raises(RuntimeError, match="require a history owner"):
        _controller(project, history=None, observers=observers).apply_drag(
            component.id, 2.01, before_states
        )

    assert component.parameters["redshift"].value == pytest.approx(2.0)
    assert all(
        state.current_revision == AnalysisRevision(0) for state in project.region_analysis_states()
    )
    assert all(not line.needs_optimization for line in project.absorption_lines.values())
    assert observers.data_updates == 0


def test_drag_without_before_state_is_ignored() -> None:
    """A drag lacking its begin snapshot must not mutate or record history."""
    project, component = _project_with_absorber()
    history = _History()
    observers = _Observers()

    _controller(project, history=history, observers=observers).apply_drag(component.id, 2.01, ())

    assert component.parameters["redshift"].value == pytest.approx(2.0)
    assert history.records == []
    assert all(
        state.current_revision == AnalysisRevision(0) for state in project.region_analysis_states()
    )
    assert all(not line.needs_optimization for line in project.absorption_lines.values())
    assert observers.data_updates == 0
