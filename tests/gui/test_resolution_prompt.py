"""Integration tests for resolution prompting behaviour."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from chappy.application.project_io_usecase import ProjectIOUseCase
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.shell.main_window import MainWindow
from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
from chappy.gui.shell.composition import create_main_window
from chappy.gui.shell.dependencies import ShellDependencies
from chappy.infrastructure.composition import (
    DefaultInfrastructureDependencies,
    create_default_infrastructure_dependencies,
)
from chappy.i18n import language_switcher as lm
from chappy.i18n.language_switcher import LanguageSwitcher


@pytest.fixture()
def language_switcher(tmp_path, monkeypatch) -> LanguageSwitcher:
    config_dir = tmp_path / "cfg"
    monkeypatch.setenv("CHAPPY_CONFIG_DIR", str(config_dir))
    lm._INSTANCE = None
    switcher = LanguageSwitcher(config_dir=config_dir)
    switcher.set_language("ja")
    lm._INSTANCE = switcher
    yield switcher
    lm._INSTANCE = None


@pytest.fixture()
def isolated_settings(tmp_path) -> None:
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(settings_dir))
    settings = QSettings()
    settings.clear()
    yield
    settings.clear()


@pytest.fixture
def project_io() -> ProjectIOUseCase:
    """Create the default project I/O use case."""
    return create_default_infrastructure_dependencies(translate_presets=str).project_io_usecase


def _build_dependencies() -> DefaultInfrastructureDependencies:
    """Build infrastructure dependencies for main-window tests."""
    return create_default_infrastructure_dependencies(translate_presets=str)


def _build_main_window(dependencies: DefaultInfrastructureDependencies) -> MainWindow:
    """Build the main window through the GUI composition boundary."""
    return create_main_window(
        ShellDependencies(
            project_io_usecase=dependencies.project_io_usecase,
            atomic_data=dependencies.atomic_repository,
            preset_store=IdentifyPresetStore(dependencies.preset_store),
            optimize_model_addition_usecase=dependencies.optimize_model_addition_usecase,
        )
    )


def test_new_project_triggers_resolution_prompt(
    qtbot, language_switcher: LanguageSwitcher, isolated_settings, monkeypatch
) -> None:
    window = _build_main_window(_build_dependencies())
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)

    prompt_calls: list[None] = []
    monkeypatch.setattr(
        window.dialog_commands, "_present_resolution_dialog", lambda: prompt_calls.append(None)
    )

    new_project = SpectroscopyProject()
    window.dialog_commands.handle_project_changed(new_project)

    qtbot.waitUntil(lambda: bool(prompt_calls))
    assert prompt_calls == [None]

    # Second invocation with the same project should not schedule another dialog.
    window.dialog_commands.handle_project_changed(new_project)
    qtbot.wait(20)
    assert prompt_calls == [None]

    window.close()


def test_loaded_hdf5_project_skips_resolution_prompt(
    qtbot,
    tmp_path,
    language_switcher: LanguageSwitcher,
    isolated_settings,
    monkeypatch,
    project_io: ProjectIOUseCase,
) -> None:
    dependencies = _build_dependencies()
    window = create_main_window(
        ShellDependencies(
            project_io_usecase=project_io,
            atomic_data=dependencies.atomic_repository,
            preset_store=IdentifyPresetStore(dependencies.preset_store),
            optimize_model_addition_usecase=dependencies.optimize_model_addition_usecase,
        )
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)

    project = SpectroscopyProject(name="Persisted")
    project.set_resolution(52000.0, True)
    project_path = tmp_path / "persisted.h5"
    project_io.save_project(project, str(project_path))

    loaded_project = project_io.load_project(str(project_path)).project
    window._require_project_session().set_project_file_path(str(project_path))

    prompt_calls: list[None] = []
    monkeypatch.setattr(
        window.dialog_commands, "_present_resolution_dialog", lambda: prompt_calls.append(None)
    )

    window.dialog_commands.handle_project_changed(loaded_project)
    qtbot.wait(20)

    assert prompt_calls == []

    window.close()
