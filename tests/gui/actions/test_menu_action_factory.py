"""Tests for MenuActionFactory menu and action wiring."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow
from pytestqt.qtbot import QtBot

from chappy.core.editing_mode import EditingMode
from chappy.application.history import HistoryApplyError, HistoryApplyErrorCode
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.shell.actions.dispatcher import ActionDispatcher
from chappy.gui.shell.actions.ids import ShellActionId
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.shell.actions import ACTION_SOURCES, MENU_SOURCES
from chappy.gui.shell.menu_action_factory import (
    ABOUT_BODY_SOURCE,
    NOT_IMPLEMENTED_BODY_SOURCES,
    NOT_IMPLEMENTED_TITLE_SOURCE,
    MenuActionFactory,
)
from chappy.gui.shell.shortcuts import format_runtime_shortcuts
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.i18n.qt_translator import QtTranslatorInstaller
from scripts.i18n_lrelease import run_lrelease
from scripts.i18n_lupdate import run_lupdate

if TYPE_CHECKING:
    from chappy.gui.history.bridge import HistoryBridge


MENU_ACTION_TRANSLATIONS_JA = {
    "&File": "ファイル(&F)",
    "&Edit": "編集(&E)",
    "&View": "表示(&V)",
    "&Mode": "モード(&M)",
    "&Settings": "設定(&S)",
    "&Help": "ヘルプ(&H)",
    "Open Observation Data...": "観測データを開く...",
    "Load observed flux and error FITS files": "観測フラックスと誤差のFITSファイルを読み込みます",
    "&Open Project...": "プロジェクトを開く(&O)...",
    "Open project ({open_project_shortcut})": ("プロジェクトを開きます ({open_project_shortcut})"),
    "&Save Project": "プロジェクトを保存(&S)",
    "Save project ({save_project_shortcut})": (
        "プロジェクトを保存します ({save_project_shortcut})"
    ),
    "Save Project &As...": "名前を付けてプロジェクトを保存(&A)...",
    "Save project with new name": "新しい名前でプロジェクトを保存します",
    "&Close Project": "プロジェクトを閉じる(&C)",
    "Close the current project": "現在のプロジェクトを閉じます",
    "&Quit": "終了(&Q)",
    "Exit the application": "アプリケーションを終了します",
    "&Undo": "元に戻す(&U)",
    "Undo last action ({undo_shortcut})": "直前の操作を元に戻します ({undo_shortcut})",
    "&Redo": "やり直す(&R)",
    "Redo last undone action ({redo_shortcut})": (
        "元に戻した操作をやり直します ({redo_shortcut})"
    ),
    "&Copy": "コピー(&C)",
    "Copy selection": "選択範囲をコピーします",
    "&Paste": "貼り付け(&P)",
    "Paste from clipboard": "クリップボードから貼り付けます",
    "&Delete": "削除(&D)",
    "Delete selection": "選択範囲を削除します",
    "Zoom &In": "拡大(&I)",
    "Zoom into spectrum": "スペクトルを拡大します",
    "Zoom &Out": "縮小(&O)",
    "Zoom out of spectrum": "スペクトルを縮小します",
    "&Reset View": "表示をリセット(&R)",
    "Reset spectrum ranges to defaults": "スペクトル範囲を既定値に戻します",
    "&Auto Adjust Flux": "フラックスを自動調整(&A)",
    "Auto-adjust flux axis to fit data": "データに合わせてフラックス軸を自動調整します",
    "&Fit Model": "モデルをフィット(&F)",
    "Fit model to observed data": "観測データにモデルをフィットします",
    "&Identify Mode": "同定モード(&I)",
    "Identify mode": "同定モード",
    "&Analysis Mode": "解析モード(&A)",
    "Analysis workspace": "解析ワークスペース",
    "Back to Analysis Overview": "Analysis Overview に戻る",
    "Return to Analysis Overview": "Analysis Overview に戻ります",
    "Show Spectrum in Velocity Space": "速度空間でスペクトルを表示",
    "&Continuum Mode": "連続光モード(&C)",
    "Continuum editing mode": "連続光編集モード",
    "Open Line &Database Folder": "スペクトル線データベースのフォルダを開く(&D)",
    "Open the folder holding the spectral line CSV": "スペクトル線 CSV を置くフォルダを開きます",
    "&Cosmology...": "宇宙論(&C)...",
    "Adjust cosmology parameters": "宇宙論パラメータを調整します",
    "&Resolution...": "分解能(&R)...",
    "Configure spectral resolution settings": "スペクトル分解能設定を構成します",
    "&Language...": "言語(&L)...",
    "Change display language": "表示言語を変更します",
    "&Preset Management...": "プリセット管理(&P)...",
    "Manage preset configurations": "プリセット構成を管理します",
    "&User Guide": "ユーザーガイド(&U)",
    "Open user guide (F1)": "ユーザーガイドを開きます (F1)",
    "&Tutorial": "チュートリアル(&T)",
    "Start guided tutorial": "ガイド付きチュートリアルを開始します",
    "&About chappy": "chappy について(&A)",
    "About this application": "このアプリケーションについて",
}


class _DummyMainWindow(QMainWindow):
    """Minimal main window stub to capture action triggers."""

    def __init__(self) -> None:
        """Initialize captured call state."""
        super().__init__()
        self.open_observation_data_called = False
        self.toggle_velocity_plot_called = False
        self.toggle_identify_velocity_called = False
        self.fit_model_called = False
        self.delete_selection_called = False
        self.current_project = None

    def open_observation_data(self) -> None:
        """Record that observation data opening was requested."""
        self.open_observation_data_called = True

    def open_project(self) -> None:
        """Stub an unused project open callback."""

    def save_project(self) -> None:
        """Stub an unused project save callback."""

    def save_project_as(self) -> None:
        """Stub an unused project save-as callback."""

    def close_project(self) -> None:
        """Stub an unused project close callback."""

    def close(self) -> bool:
        """Stub the window close callback.

        Returns:
            Always true.
        """
        return True

    def add_continuum(self) -> None:
        """Stub an unused continuum callback."""

    def fit_model(self) -> None:
        """Record model fitting callback."""
        self.fit_model_called = True

    def delete_selection(self) -> None:
        """Record dispatch through the shared Delete action."""
        self.delete_selection_called = True

    def switch_mode(self, mode: EditingMode) -> None:
        """Stub an unused public mode switch callback.

        Args:
            mode: Requested editing mode.
        """

    def _switch_mode(self, mode: EditingMode) -> None:
        """Stub an unused private mode switch callback.

        Args:
            mode: Requested editing mode.
        """

    def show_cosmology_dialog(self) -> None:
        """Stub an unused cosmology dialog callback."""

    def show_resolution_dialog(self) -> None:
        """Stub an unused resolution dialog callback."""

    def open_line_database_folder(self) -> None:
        """Stub an unused line database folder callback."""

    def show_language_dialog(self) -> None:
        """Stub an unused language dialog callback."""

    def show_preset_list_dialog(self) -> None:
        """Stub an unused preset list dialog callback."""

    def open_user_manual(self) -> None:
        """Stub an unused user manual callback."""

    def reset_view(self) -> None:
        """Stub an unused view reset callback."""

    def auto_adjust_flux(self) -> None:
        """Stub an unused flux adjustment callback."""

    def zoom_in(self) -> None:
        """Stub an unused zoom-in callback."""

    def zoom_out(self) -> None:
        """Stub an unused zoom-out callback."""

    def toggle_velocity_plot_optimize(self) -> None:
        """Stub an unused optimize-mode velocity toggle callback."""
        self.toggle_velocity_plot_called = True

    def toggle_velocity_plot_identify(self) -> None:
        """Record Identify velocity toggle callback."""
        self.toggle_identify_velocity_called = True


class _HistoryActionBridge:
    """Minimal history action boundary for dispatcher behavior tests."""

    def __init__(
        self,
        *,
        undo_result: tuple[bool, str] = (True, "Undo operation"),
        redo_result: tuple[bool, str] = (True, "Redo operation"),
        error: Exception | None = None,
    ) -> None:
        self._undo_result = undo_result
        self._redo_result = redo_result
        self._error = error

    def undo(self) -> tuple[bool, str]:
        if self._error is not None:
            raise self._error
        return self._undo_result

    def redo(self) -> tuple[bool, str]:
        if self._error is not None:
            raise self._error
        return self._redo_result


def _normalize_label(label: str) -> str:
    """Strip mnemonic markers and normalise ellipsis for stable comparisons.

    Args:
        label: Menu or action label.

    Returns:
        Normalized label.
    """
    return label.replace("&", "").replace("…", "...").strip()


def _write_menu_action_ja_ts(ts_path: Path) -> None:
    """Write a Japanese TS catalog for MenuActionFactory.

    Args:
        ts_path: Output TS file path.
    """
    ts = ET.Element("TS", {"version": "2.1", "language": "ja_JP"})
    context = ET.SubElement(ts, "context")
    name = ET.SubElement(context, "name")
    name.text = "MenuActionFactory"
    for source_text, translation_text in MENU_ACTION_TRANSLATIONS_JA.items():
        message = ET.SubElement(context, "message")
        source = ET.SubElement(message, "source")
        source.text = source_text
        translation = ET.SubElement(message, "translation")
        translation.text = translation_text
    tree = ET.ElementTree(ts)
    tree.write(ts_path, encoding="utf-8", xml_declaration=True)


def _compile_menu_action_ja_qm(tmp_path: Path) -> Path:
    """Compile a test Japanese QM catalog for MenuActionFactory.

    Args:
        tmp_path: Temporary directory for generated catalogs.

    Returns:
        Directory containing ``chappy_ja.qm``.
    """
    if shutil.which("pyside6-lrelease") is None:
        pytest.skip("pyside6-lrelease is not available")

    catalog_root = tmp_path / "qt_catalogs"
    catalog_root.mkdir()
    ts_path = catalog_root / "chappy_ja.ts"
    qm_path = catalog_root / "chappy_ja.qm"
    _write_menu_action_ja_ts(ts_path)
    run_lrelease(ts_input=ts_path, qm_output=qm_path)
    return catalog_root


@pytest.fixture()
def qt_translator_installer(tmp_path: Path) -> Iterator[QtTranslatorInstaller]:
    """Provide a translator installer with a compiled menu test catalog.

    Args:
        tmp_path: Temporary directory for generated catalogs.

    Yields:
        Translator installer configured with the test catalog root.
    """
    catalog_root = _compile_menu_action_ja_qm(tmp_path)
    installer = QtTranslatorInstaller(
        translation_root=catalog_root, qt_translation_root=tmp_path / "missing_qt_catalogs"
    )
    yield installer
    installer.remove_translators()


def _create_factory_with_menu(qtbot: QtBot) -> tuple[MenuActionFactory, QMainWindow]:
    """Create a MenuActionFactory with actions and menus.

    Args:
        qtbot: pytest-qt bot used to manage the main window.

    Returns:
        Factory and parent window.
    """
    window = _DummyMainWindow()
    qtbot.addWidget(window)
    dispatcher = ActionDispatcher(
        project_commands=window,
        mode_commands=window,
        dialog_commands=window,
        navigation_commands=window,
        window_commands=window,
        status_emitter=lambda _message, _timeout_ms: None,
        tutorial_callback=lambda: None,
        about_callback=lambda: None,
        spectrum_policy_provider=lambda: analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL),
        fit_running_provider=lambda: False,
    )
    factory = MenuActionFactory(window, dispatcher=dispatcher)
    factory.create_all_actions()
    factory.create_menu_bar()
    return factory, window


def test_settings_menu_contains_resolution_entry(qtbot: QtBot) -> None:
    """Verify the settings menu contains the resolution action."""
    factory, _window = _create_factory_with_menu(qtbot)

    settings_menu = factory.menus["settings"]
    action_texts = [_normalize_label(action.text()) for action in settings_menu.actions()]
    expected_label = _normalize_label(ACTION_SOURCES[ShellActionId.RESOLUTION_SETTINGS].text)
    assert expected_label in action_texts


def test_analysis_menu_excludes_velocity_plot(qtbot: QtBot) -> None:
    """Verify the mode menu excludes the legacy velocity plot action."""
    factory, _window = _create_factory_with_menu(qtbot)

    mode_menu = factory.menus["mode"]
    action_texts = [_normalize_label(action.text()) for action in mode_menu.actions()]
    assert _normalize_label("Velocity Plot") not in action_texts


def test_view_menu_excludes_identify_velocity_entry(qtbot: QtBot) -> None:
    """The View menu no longer offers the identify velocity toggle."""
    factory, _window = _create_factory_with_menu(qtbot)

    menu_actions = {action for menu in factory.menus.values() for action in menu.actions()}

    assert factory.actions[ShellActionId.TOGGLE_VELOCITY_PLOT_IDENTIFY] not in menu_actions
    assert factory.actions[ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS] in set(
        factory.menus["view"].actions()
    )


def test_identify_velocity_action_keeps_window_level_shortcut(qtbot: QtBot) -> None:
    """Losing its menu entry must not cost the identify velocity action its V key."""
    factory, window = _create_factory_with_menu(qtbot)

    action = factory.actions[ShellActionId.TOGGLE_VELOCITY_PLOT_IDENTIFY]

    assert action in window.actions()
    assert {
        sequence.toString(QKeySequence.SequenceFormat.PortableText)
        for sequence in action.shortcuts()
    } == {"V"}


def test_zoom_action_shortcuts_use_control_modifier(qtbot: QtBot) -> None:
    """Ensure zoom action shortcuts rely solely on the Control/Command modifier.

    Note: This test uses PortableText format, which always shows "Ctrl" regardless
    of platform. On actual macOS menus, Qt automatically displays "⌘" (Command)
    and responds to the Command key, not the physical Control key.
    """
    factory, _window = _create_factory_with_menu(qtbot)

    def _shortcut_strings(action_name: ShellActionId) -> set[str]:
        """Return portable shortcut strings for an action.

        Args:
            action_name: Action registry name.

        Returns:
            Portable shortcut strings.
        """
        action = factory.actions[action_name]
        return {
            sequence.toString(QKeySequence.SequenceFormat.PortableText)
            for sequence in action.shortcuts()
        }

    assert _shortcut_strings(ShellActionId.ZOOM_IN) == {"Ctrl++", "Ctrl+="}
    assert _shortcut_strings(ShellActionId.ZOOM_OUT) == {"Ctrl+-"}


def test_velocity_toggle_action_dispatches_to_main_window(qtbot: QtBot) -> None:
    """Verify velocity action dispatch uses main-window toggle handler."""
    factory, window = _create_factory_with_menu(qtbot)
    window.current_project = SpectroscopyProject()

    action = factory.actions[ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS]
    action.setEnabled(True)
    action.trigger()

    assert window.toggle_velocity_plot_called is True


def test_delete_menu_and_shortcut_action_dispatch_to_mode_contract(qtbot: QtBot) -> None:
    """Edit/Delete and its Delete-key shortcut share one typed dispatcher path."""
    factory, window = _create_factory_with_menu(qtbot)
    action = factory.actions[ShellActionId.DELETE]

    factory.update_action_states(SpectroscopyProject())
    factory.update_mode_actions(EditingMode.ANALYSIS)
    assert not action.isEnabled(), "Delete stays disabled until a surface policy grants it"

    action.setEnabled(True)
    action.trigger()

    assert action.shortcut().toString(QKeySequence.SequenceFormat.PortableText) == "Del"
    assert window.delete_selection_called is True


def test_undo_redo_trigger_requires_history_bridge(qtbot: QtBot) -> None:
    """Undo/redo actions fail fast until a history bridge is configured."""
    factory, _window = _create_factory_with_menu(qtbot)

    with pytest.raises(RuntimeError, match="History bridge is required"):
        factory._dispatcher.dispatch(ShellActionId.UNDO)
    with pytest.raises(RuntimeError, match="History bridge is required"):
        factory._dispatcher.dispatch(ShellActionId.REDO)


def test_undo_missing_target_failure_reaches_action_status(qtbot: QtBot) -> None:
    """A recoverable bridge failure is rendered by the shell action boundary."""
    window = _DummyMainWindow()
    qtbot.addWidget(window)
    statuses: list[tuple[str, int]] = []
    dispatcher = ActionDispatcher(
        project_commands=window,
        mode_commands=window,
        dialog_commands=window,
        navigation_commands=window,
        window_commands=window,
        status_emitter=lambda message, timeout: statuses.append((message, timeout)),
        tutorial_callback=lambda: None,
        about_callback=lambda: None,
        spectrum_policy_provider=lambda: analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL),
        fit_running_provider=lambda: False,
    )
    dispatcher.set_history_bridge(
        cast(
            "HistoryBridge",
            _HistoryActionBridge(undo_result=(False, "Scientific history target not found")),
        )
    )

    dispatcher.dispatch(ShellActionId.UNDO)

    assert statuses == [("Cannot undo/redo: Scientific history target not found", 3000)]


def test_invalid_history_failure_propagates_through_action_dispatcher(qtbot: QtBot) -> None:
    """Invariant failures remain fail-fast through the shell action boundary."""
    window = _DummyMainWindow()
    qtbot.addWidget(window)
    dispatcher = ActionDispatcher(
        project_commands=window,
        mode_commands=window,
        dialog_commands=window,
        navigation_commands=window,
        window_commands=window,
        status_emitter=lambda _message, _timeout: None,
        tutorial_callback=lambda: None,
        about_callback=lambda: None,
        spectrum_policy_provider=lambda: analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL),
        fit_running_provider=lambda: False,
    )
    dispatcher.set_history_bridge(
        cast(
            "HistoryBridge",
            _HistoryActionBridge(
                error=HistoryApplyError(
                    HistoryApplyErrorCode.INVALID_STATE, "history invariant failed"
                )
            ),
        )
    )

    with pytest.raises(HistoryApplyError, match="history invariant failed"):
        dispatcher.dispatch(ShellActionId.UNDO)


def test_about_dialog_requires_qapplication(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """About dialog should fail fast when Qt application composition is missing."""
    factory, _window = _create_factory_with_menu(qtbot)
    monkeypatch.setattr(QApplication, "instance", lambda: None)

    with pytest.raises(RuntimeError, match="QApplication instance is required"):
        factory._show_about_dialog()


def test_qt_translator_updates_existing_menu_and_actions(
    qtbot: QtBot, qt_translator_installer: QtTranslatorInstaller
) -> None:
    """Verify existing menus and actions update from a Qt translator."""
    factory, _window = _create_factory_with_menu(qtbot)

    assert factory.menus["file"].title() == "&File"
    assert factory.actions[ShellActionId.OPEN_PROJECT].text() == "&Open Project..."
    assert factory.actions[ShellActionId.OPEN_PROJECT].statusTip() == format_runtime_shortcuts(
        "Open project ({open_project_shortcut})"
    )

    state = qt_translator_installer.install_language("ja")
    assert state.app_translator_loaded
    factory.retranslate()

    assert factory.menus["file"].title() == "ファイル(&F)"
    assert factory.menus["settings"].title() == "設定(&S)"
    assert factory.actions[ShellActionId.OPEN_PROJECT].text() == "プロジェクトを開く(&O)..."
    assert factory.actions[ShellActionId.OPEN_PROJECT].statusTip() == format_runtime_shortcuts(
        "プロジェクトを開きます ({open_project_shortcut})"
    )
    assert factory.actions[ShellActionId.RESOLUTION_SETTINGS].text() == "分解能(&R)..."
    assert (
        factory.actions[ShellActionId.RESOLUTION_SETTINGS].statusTip()
        == "スペクトル分解能設定を構成します"
    )

    qt_translator_installer.install_language("en")
    factory.retranslate()

    assert factory.menus["file"].title() == "&File"
    assert factory.actions[ShellActionId.OPEN_PROJECT].text() == "&Open Project..."
    assert factory.actions[ShellActionId.OPEN_PROJECT].statusTip() == format_runtime_shortcuts(
        "Open project ({open_project_shortcut})"
    )


def test_lupdate_extracts_menu_action_factory_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts menu titles, action text, and status tips."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "chappy_ja.ts"
    run_lupdate(
        source_dirs=[
            Path("src/chappy/gui/shell/menu_action_factory.py"),
            Path("src/chappy/gui/shell/actions/registry.py"),
        ],
        ts_output=ts_path,
    )

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    expected_menu_sources = {source.title for source in MENU_SOURCES.values()}
    expected_action_sources = {source.text for source in ACTION_SOURCES.values()}
    expected_status_tip_sources = {
        source.status_tip for source in ACTION_SOURCES.values() if source.status_tip is not None
    }
    expected_dialog_sources = {
        NOT_IMPLEMENTED_TITLE_SOURCE,
        ABOUT_BODY_SOURCE,
        *NOT_IMPLEMENTED_BODY_SOURCES.values(),
    }

    assert expected_menu_sources <= sources
    assert expected_action_sources <= sources
    assert expected_status_tip_sources <= sources
    assert expected_dialog_sources <= sources
    assert not any("DLG__" in source for source in sources)
    assert not any("GUI__" in source for source in sources)


def test_scientific_shortcuts_are_guarded_by_current_policy(qtbot: QtBot) -> None:
    """Disabled QAction state must not be the command boundary's authority."""
    window = _DummyMainWindow()
    qtbot.addWidget(window)
    window.current_project = SpectroscopyProject()
    policies = [spectrum_interaction_mode_policy(EditingMode.IDENTIFY)]
    fit_running = [False]
    dispatcher = ActionDispatcher(
        project_commands=window,
        mode_commands=window,
        dialog_commands=window,
        navigation_commands=window,
        window_commands=window,
        status_emitter=lambda _message, _timeout: None,
        tutorial_callback=lambda: None,
        about_callback=lambda: None,
        spectrum_policy_provider=lambda: policies[-1],
        fit_running_provider=lambda: fit_running[-1],
    )

    dispatcher.dispatch(ShellActionId.FIT_MODEL)
    dispatcher.dispatch(ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS)
    dispatcher.dispatch(ShellActionId.TOGGLE_VELOCITY_PLOT_IDENTIFY)
    assert window.fit_model_called is False
    assert window.toggle_velocity_plot_called is False
    assert window.toggle_identify_velocity_called is True

    policies.append(analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL))
    fit_running.append(True)
    dispatcher.dispatch(ShellActionId.FIT_MODEL)
    assert window.fit_model_called is False
    fit_running.append(False)

    dispatcher.dispatch(ShellActionId.FIT_MODEL)
    dispatcher.dispatch(ShellActionId.TOGGLE_VELOCITY_PLOT_ANALYSIS)
    dispatcher.dispatch(ShellActionId.TOGGLE_VELOCITY_PLOT_IDENTIFY)
    assert window.fit_model_called is True
    assert window.toggle_velocity_plot_called is True
    assert window.toggle_identify_velocity_called is True
