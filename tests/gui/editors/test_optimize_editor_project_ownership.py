"""Project ownership boundaries for the optimize editor fit service."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray
from pytestqt.qtbot import QtBot

from chappy.application.project_mapper import project_from_document, project_to_document
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.base import ModelComponent
from chappy.core.components.continuum import ContinuumComponent
from chappy.core.components.optimize import OptimizeComponent
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.region_detail.editor import OptimizeEditor


class _UnknownComponent(ModelComponent):
    """Non-persistable model component used to verify fail-fast mapping."""

    def calculate(self, wavelength: NDArray[np.float64]) -> NDArray[np.float64]:
        """Return a neutral multiplicative contribution."""
        return np.ones_like(wavelength)


def _scientific_project(name: str) -> SpectroscopyProject:
    """Build a project with both persistable component kinds."""
    project = SpectroscopyProject(name=name)
    project.model.add_component(
        AbsorberComponent(
            name="C IV 1548", wavelength=1548.195, oscillator_strength=0.19, gamma=2.65e8
        )
    )
    project.model.add_component(ContinuumComponent(name="Continuum"))
    return project


def test_project_attach_does_not_change_components_or_serialization(qtbot: QtBot) -> None:
    """Attaching the editor must not add its local fit service to project state."""
    project = _scientific_project("Attached")
    component_ids_before = tuple(component.id for component in project.model.components)
    document_before = project_to_document(project)
    editor = OptimizeEditor()
    qtbot.addWidget(editor)

    editor.set_project(project)

    assert tuple(component.id for component in project.model.components) == component_ids_before
    assert all(
        not isinstance(component, OptimizeComponent) for component in project.model.components
    )
    assert project_to_document(project) == document_before
    assert editor.optimize_component is not None
    assert editor.optimize_component not in project.model.components


def test_switching_projects_replaces_the_editor_local_fit_service(qtbot: QtBot) -> None:
    """One mutable optimizer instance must never be reused across projects."""
    first_project = SpectroscopyProject(name="First")
    second_project = SpectroscopyProject(name="Second")
    editor = OptimizeEditor()
    qtbot.addWidget(editor)

    editor.set_project(first_project)
    first_optimizer = editor.optimize_component
    assert first_optimizer is not None
    first_optimizer.last_result = {"project": "first"}

    editor.set_project(second_project)
    second_optimizer = editor.optimize_component

    assert second_optimizer is not None
    assert second_optimizer is not first_optimizer
    assert second_optimizer.last_result is None
    assert first_project.model.components == []
    assert second_project.model.components == []


def test_project_document_persists_only_absorber_and_continuum_components() -> None:
    """Editor-only optimizer state is outside the project document schema."""
    project = _scientific_project("Persistence boundary")
    project.model.add_component(OptimizeComponent(name="Transient optimizer"))

    document = project_to_document(project)
    restored = project_from_document(document).project

    assert tuple(component.kind for component in document.components) == ("absorber", "continuum")
    assert [type(component) for component in restored.model.components] == [
        AbsorberComponent,
        ContinuumComponent,
    ]


def test_project_document_rejects_unknown_model_component() -> None:
    """Unknown scientific component types must not be silently omitted."""
    project = _scientific_project("Unknown component")
    project.model.add_component(_UnknownComponent(name="Unsupported"))

    with pytest.raises(ValueError, match="Unsupported component type.*_UnknownComponent"):
        project_to_document(project)
