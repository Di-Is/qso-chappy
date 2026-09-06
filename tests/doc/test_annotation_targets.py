from pathlib import Path

import pytest
import yaml
from pytestqt.qtbot import QtBot
from PySide6.QtWidgets import QApplication, QWidget

from chappy.core.editing_mode import EditingMode
from chappy_user_manual_generator import pipeline as doc_pipeline
from chappy_user_manual_generator.dialog_providers import known_dialog_providers
from chappy_user_manual_generator.fixtures import apply_fixture


ANNOTATIONS_PATH = Path("docs/user_manual/src/chappy_user_manual_generator/annotations_map.yaml")
OBJECT_NAME_PREFIX = "objectName:"


def test_annotation_object_name_targets_exist_at_runtime(
    monkeypatch: pytest.MonkeyPatch, qtbot: QtBot
) -> None:
    """Require every objectName annotation target to resolve at runtime."""
    monkeypatch.setenv("CHAPPY_DOC_AUTO_DISCARD", "1")
    entries = yaml.safe_load(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    targets = {
        entry["target"].split(":", 1)[1]
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("target"), str)
        and entry["target"].startswith(OBJECT_NAME_PREFIX)
    }

    app = QApplication.instance()
    assert app is not None
    with doc_pipeline._doc_environment(headless=True):
        window = doc_pipeline._create_window("main", headless=True)
        qtbot.addWidget(window)
        dialogs: list[QWidget] = []
        try:
            apply_fixture("identify-demo", app, window)
            doc_pipeline._switch_mode(window, EditingMode.IDENTIFY)
            velocity_capture = next(
                capture
                for capture in doc_pipeline._identify_custom_captures(window, app)
                if capture.suffix == "_velocity"
            )
            assert velocity_capture.pre_capture is not None
            velocity_capture.pre_capture(window)

            widgets = [window, *window.findChildren(QWidget)]
            dialogs = [provider.factory(window) for provider in known_dialog_providers().values()]
            for dialog in dialogs:
                widgets.extend((dialog, *dialog.findChildren(QWidget)))
            runtime_object_names = {widget.objectName() for widget in widgets}
            assert targets - runtime_object_names == set()
        finally:
            for dialog in dialogs:
                dialog.close()
            window.identify_velocity_runtime.hide_velocity_plot()
            window.close()
            app.processEvents()
