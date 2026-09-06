"""Cross-consumer regression tests for shared tutorial/manual operations.

These guard against the kind of drift found in the 2026-07-04 tutorial audit
(docs/adr/doc-translation-qt-unification.md): the tutorial and the manual's
keyboard/mouse operation tables independently hand-wrote facts about the same
interaction and drifted apart. P4b introduced
``chappy.gui.common.shared_operations`` as the single source for those facts;
these tests confirm both consumers keep referencing the same instances.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from chappy.gui.common.shared_operations import SHARED_OPERATIONS, get_shared_operation
from chappy.gui.common.tutorial import TutorialStep
from chappy.gui.dialogs.line_selection_dialog import LineSelectionDialog
from chappy.gui.modes.identify.presets.preset_list_dialog import PresetListDialog
from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
from chappy.gui.spectrum.velocity.overlay_widget import SpectrumVelocityOverlayWidget
from chappy.gui.shell.composition import create_main_window
from chappy.gui.shell.dependencies import ShellDependencies
from chappy.gui.shell.tutorial_chapters import build_advanced_walkthrough_chapters
from chappy.infrastructure.composition import create_default_infrastructure_dependencies
from chappy_user_manual_generator.data.keyboard_operations import SHARED_OPERATION_IDS_IN_USE
from tests.helpers.tutorial_chapters import all_walkthrough_steps


def _steps_with_operation() -> list[TutorialStep]:
    return [step for step in all_walkthrough_steps() if step.operation is not None]


def test_tutorial_steps_reference_registered_shared_operation_instances() -> None:
    """Every tutorial step's operation is the exact registered singleton."""
    steps = _steps_with_operation()

    assert steps, "expected at least one tutorial step to reference a shared operation"
    for step in steps:
        assert step.operation is get_shared_operation(step.operation.op_id)


def test_tutorial_and_manual_reference_the_same_shared_operation_instances() -> None:
    """Op ids consumed by the manual's keyboard table are also used by the tutorial.

    Continuum's control-point *move* fact currently has no matching tutorial
    step (the tutorial covers add+move in one combined step already assigned
    to ``continuum_add_point``); it is intentionally manual-only and excluded
    here (see docs/task/doc-translation-qt-unification/plan.md, P4b-2).
    ``analysis_toggle_component_profiles`` has no tutorial step either, as the
    tutorial does not currently walk through the component-profiles toggle.
    """
    manual_only = {"analysis_toggle_component_profiles", "continuum_move_point"}
    tutorial_op_ids = {step.operation.op_id for step in _steps_with_operation()}

    for op_id in SHARED_OPERATION_IDS_IN_USE:
        if op_id in manual_only:
            continue
        assert op_id in tutorial_op_ids, f"{op_id} used by the manual but not by any tutorial step"


def test_advanced_chapters_link_every_matching_existing_shared_operation() -> None:
    chapters = {chapter.chapter_id: chapter for chapter in build_advanced_walkthrough_chapters()}

    operation_ids = {
        chapter_id: {
            step.operation.op_id
            for step in chapters[chapter_id].steps
            if step.operation is not None
        }
        for chapter_id in ("preset_build", "velocity_identify", "analysis_structure", "joint_fit")
    }

    assert operation_ids == {
        "preset_build": set(),
        "velocity_identify": {"identify_toggle_velocity"},
        "analysis_structure": {"analysis_structure_merge", "analysis_structure_split"},
        "joint_fit": {"analysis_fit", "analysis_toggle_velocity", "optimize_velocity_shift_click"},
    }


def test_shared_operation_target_object_names_exist_on_real_widgets(qtbot) -> None:
    """Each shared operation's target exists in the real window or velocity overlay."""
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
    velocity_overlay = SpectrumVelocityOverlayWidget(window)
    roots: tuple[QWidget, ...] = (window, velocity_overlay)

    for operation in SHARED_OPERATIONS:
        if operation.target_object_name is None:
            continue
        resolved = any(
            root.objectName() == operation.target_object_name
            or root.findChild(QWidget, operation.target_object_name) is not None
            for root in roots
        )
        assert resolved, f"{operation.op_id}: no widget named {operation.target_object_name!r}"


def test_tutorial_target_object_names_exist_on_real_widgets(qtbot) -> None:
    """Every coach-mark target resolves on the main window or a real dialog/overlay.

    Modal-dialog targets and the lazily created velocity overlay are resolved
    at runtime via ``QApplication.activeModalWidget`` and on-demand creation;
    here their real widgets are instantiated so the same object names are
    verified against the widgets that ship.
    """
    dependencies = create_default_infrastructure_dependencies(translate_presets=str)
    preset_store = IdentifyPresetStore(dependencies.preset_store)
    window = create_main_window(
        ShellDependencies(
            project_io_usecase=dependencies.project_io_usecase,
            atomic_data=dependencies.atomic_repository,
            preset_store=preset_store,
            optimize_model_addition_usecase=dependencies.optimize_model_addition_usecase,
        )
    )
    qtbot.addWidget(window)
    preset_dialog = PresetListDialog(
        window, preset_store, atomic_data=dependencies.atomic_repository
    )
    line_dialog = LineSelectionDialog(preset_dialog, atomic_data=dependencies.atomic_repository)
    velocity_overlay = SpectrumVelocityOverlayWidget(window)
    roots: tuple[QWidget, ...] = (window, preset_dialog, line_dialog, velocity_overlay)

    for step in all_walkthrough_steps():
        for target in step.targets:
            resolved = any(
                root.objectName() == target.object_name
                or root.findChild(QWidget, target.object_name) is not None
                for root in roots
            )
            assert resolved, f"no tutorial widget named {target.object_name!r}"
