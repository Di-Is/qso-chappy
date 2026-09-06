"""Project file handler regressions."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from PySide6.QtWidgets import QMainWindow

from chappy.application.project_mapper import ProjectLoadResult
from chappy.application.structure.region_line_repair import (
    RegionLineRepairAction,
    RegionLineRepairReport,
)
from chappy.application.structure.region_line_topology import RegionLineTopologyIssueKind
from chappy.core.absorption.models import UNASSIGNED_REGION_ID, AbsorptionLine, AbsorptionRegion
from chappy.core.spectroscopy_project import SpectroscopyProject
import chappy.gui.shell.project_file_dialog_adapters as project_file_dialog_adapters
from chappy.gui.shell.project_file_coordinator import (
    ProjectFileCoordinator,
    RequiredProjectFileDependencyError,
)
from chappy.gui.shell.project_file_dialog_adapters import (
    ProjectFileDialogAdapter,
    ProjectMessageDialogAdapter,
    RecentProjectDirectoryAdapter,
)
from scripts.i18n_lupdate import run_lupdate

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent
    from pytestqt.qtbot import QtBot


def _coordinator_with_fake_io(
    main_window: QMainWindow,
) -> tuple[ProjectFileCoordinator, _FakeProjectIO]:
    """Create a coordinator with an attached fake ProjectIOUseCase."""
    fake_project_io = _FakeProjectIO()
    coordinator = ProjectFileCoordinator(main_window, project_io=fake_project_io)
    return coordinator, fake_project_io


def _line(
    line_id: str, region_id: str, *, species: str, transition: str, rest_wavelength: float
) -> AbsorptionLine:
    return AbsorptionLine(
        line_id=line_id,
        species=species,
        rest_wavelength=rest_wavelength,
        center_z=0.0,
        window_kms=100.0,
        multiplet_label="",
        transition_name=transition,
        oscillator_strength=0.1,
        gamma_value=1.0,
        region_id=region_id,
    )


class _FakeSettings:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def value(
        self, key: str, defaultValue: object | None = None, type: type | None = None
    ) -> object | None:
        result = self._store.get(key, defaultValue)
        _ = type
        return result

    def setValue(self, key: str, value: object) -> None:
        self._store[key] = value


class _DummyProject:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeProjectIO:
    def __init__(self) -> None:
        self.saved_path: str | None = None
        self.validated_paths: list[str] = []
        self.info_paths: list[str] = []
        self.load_result = ProjectLoadResult(
            project=SpectroscopyProject(name="loaded"),
            repair_report=RegionLineRepairReport(actions=()),
        )

    def save_project(self, project: SpectroscopyProject, path: str) -> None:
        """Record the save request."""
        _ = project
        self.saved_path = path

    def validate_fits_spectrum(self, path: str) -> tuple[bool, list[str]]:
        """Record a FITS validation request."""
        self.validated_paths.append(path)
        return True, []

    def get_fits_info(self, path: str) -> dict[str, object]:
        """Record a FITS info request."""
        self.info_paths.append(path)
        return {"primary_shape": [42]}

    def load_project(self, path: str) -> ProjectLoadResult:
        """Return the configured project load result."""
        _ = path
        return self.load_result


class _FakeOpenProjectDialog:
    def open_project_path(self, parent: object, start_dir: str) -> str:
        """Return a fixed project path."""
        _ = parent, start_dir
        return "/tmp/repaired.h5"


class _FakeRecentDirectories:
    def project_start_directory(self) -> str:
        """Return an empty start directory."""
        return ""

    def store_project_directory(self, file_path: str) -> None:
        """Accept a successfully opened project path."""
        _ = file_path


class _FakeMessageDialogs:
    def __init__(self) -> None:
        self.repair_notices: list[tuple[str, str]] = []

    def show_repair_notice(self, parent: object, *, summary: str, details: str) -> None:
        """Record an automatic repair notice."""
        _ = parent
        self.repair_notices.append((summary, details))

    def show_error(self, parent: object, title: str, message: str) -> None:
        """Fail if an unexpected project error is shown."""
        _ = parent, title, message
        raise AssertionError("Unexpected project error")


class _FakeUrl:
    """Minimal local-file URL test double."""

    def __init__(self, path: str) -> None:
        self._path = path

    def isLocalFile(self) -> bool:  # noqa: N802
        """Return whether this URL represents a local file."""
        return True

    def toLocalFile(self) -> str:  # noqa: N802
        """Return the local file path."""
        return self._path


class _FakeMimeData:
    """Minimal MIME data test double for drag events."""

    def __init__(self, paths: list[str]) -> None:
        self._urls = [_FakeUrl(path) for path in paths]

    def hasUrls(self) -> bool:  # noqa: N802
        """Return whether URL payloads are present."""
        return bool(self._urls)

    def urls(self) -> list[_FakeUrl]:
        """Return local-file URLs."""
        return self._urls


class _FakeDragEnterEvent:
    """Minimal drag-enter event test double."""

    def __init__(self, paths: list[str]) -> None:
        self._mime_data = _FakeMimeData(paths)
        self.accepted = False
        self.ignored = False

    def mimeData(self) -> _FakeMimeData:  # noqa: N802
        """Return drag MIME data."""
        return self._mime_data

    def acceptProposedAction(self) -> None:  # noqa: N802
        """Record that the drop action was accepted."""
        self.accepted = True

    def ignore(self) -> None:
        """Record that the drag event was ignored."""
        self.ignored = True


def test_save_project_as_relies_on_os_overwrite_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qtbot: "QtBot"
) -> None:
    fake_settings = _FakeSettings()
    monkeypatch.setattr(project_file_dialog_adapters, "QSettings", lambda: fake_settings)

    existing_file = tmp_path / "demo.h5"
    existing_file.write_text("previous content", encoding="utf-8")

    dialog_args: list[tuple[object, ...]] = []
    dialog_kwargs: list[dict[str, object]] = []

    def fake_get_save_file_name(*args: object, **kwargs: object) -> tuple[str, str]:
        dialog_args.append(args)
        dialog_kwargs.append(kwargs)
        filters = "HDF5 project files (*.h5 *.hdf5);;All files (*.*)"
        return str(existing_file), filters

    monkeypatch.setattr(
        "chappy.gui.shell.project_file_dialog_adapters.QFileDialog.getSaveFileName",
        fake_get_save_file_name,
    )

    class _QMessageBoxProbe:
        @staticmethod
        def critical(*args: object, **kwargs: object) -> None:
            raise AssertionError("QMessageBox should not be invoked for overwrite confirmation")

    monkeypatch.setattr(project_file_dialog_adapters, "QMessageBox", _QMessageBoxProbe)

    main_window = QMainWindow()
    handler, fake_project_io = _coordinator_with_fake_io(main_window)
    project = _DummyProject(name="demo-project")

    assert handler.save_project_as(cast(SpectroscopyProject, project)) is True
    assert fake_project_io.saved_path == str(existing_file)
    assert fake_settings._store.get("recent_directories/project") == str(existing_file.parent)
    assert dialog_kwargs
    assert "options" not in dialog_kwargs[0]
    assert dialog_args[0][1] == "Save Project &As..."


def test_drag_enter_inspects_fits_through_project_io(qtbot: "QtBot") -> None:
    """Verify drag preflight uses ProjectIOUseCase instead of FITS infrastructure."""
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, fake_project_io = _coordinator_with_fake_io(main_window)

    event = _FakeDragEnterEvent(["/tmp/example.fits"])

    handler.handle_drag_enter_event(cast("QDragEnterEvent", event))

    assert event.accepted is True
    assert event.ignored is False
    assert fake_project_io.validated_paths == ["/tmp/example.fits"]
    assert fake_project_io.info_paths == ["/tmp/example.fits"]


def test_drag_enter_fails_fast_when_project_io_is_missing(qtbot: "QtBot") -> None:
    """Verify missing ProjectIO wiring is not converted to a drag rejection."""
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, fake_project_io = _coordinator_with_fake_io(main_window)
    handler._project_io = None

    event = _FakeDragEnterEvent(["/tmp/example.fits"])

    with pytest.raises(RequiredProjectFileDependencyError, match="_project_io"):
        handler.handle_drag_enter_event(cast("QDragEnterEvent", event))

    assert event.accepted is False
    assert event.ignored is False


def test_check_save_current_project_fails_fast_when_host_lacks_project_contract(
    qtbot: "QtBot",
) -> None:
    """Verify the shell host must expose the current-project contract."""
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)

    with pytest.raises(RequiredProjectFileDependencyError, match="current_project"):
        handler.check_save_current_project()


def test_dialog_selection_contract_error_is_not_reported_as_file_error(qtbot: "QtBot") -> None:
    """Verify malformed dialog payloads fail fast as wiring errors."""
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)

    with pytest.raises(TypeError, match="error_files"):
        handler._on_files_selected_from_dialog(
            {"flux_file": "flux.fits", "error_files": object(), "ignored_files": []}
        )


def test_save_project_as_fails_fast_when_project_io_is_missing(qtbot: "QtBot") -> None:
    """Verify save-as infrastructure wiring errors are not reported as save failures."""
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)
    handler._project_io = None
    project = _DummyProject(name="demo-project")

    with pytest.raises(RequiredProjectFileDependencyError, match="_project_io"):
        handler.save_project_as(cast(SpectroscopyProject, project))


def test_open_project_dialog_title_uses_qt_source_text(
    monkeypatch: pytest.MonkeyPatch, qtbot: "QtBot"
) -> None:
    """Verify the open project dialog title uses Qt source text."""
    fake_settings = _FakeSettings()
    monkeypatch.setattr(project_file_dialog_adapters, "QSettings", lambda: fake_settings)

    dialog_args: list[tuple[object, ...]] = []

    def fake_get_open_file_name(*args: object, **kwargs: object) -> tuple[str, str]:
        _ = kwargs
        dialog_args.append(args)
        filters = "HDF5 project files (*.h5 *.hdf5);;All files (*.*)"
        return "", filters

    monkeypatch.setattr(
        "chappy.gui.shell.project_file_dialog_adapters.QFileDialog.getOpenFileName",
        fake_get_open_file_name,
    )

    main_window = QMainWindow()
    main_window.current_project = None
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)

    handler.open_project()

    assert dialog_args[0][1] == "&Open Project..."


@pytest.mark.parametrize("has_repairs", [False, True])
def test_open_project_shows_notice_only_when_repairs_were_applied(
    has_repairs: bool, qtbot: "QtBot"
) -> None:
    """A successful load warns exactly when its repair report is non-empty."""
    main_window = QMainWindow()
    main_window.current_project = None
    qtbot.addWidget(main_window)
    handler, fake_project_io = _coordinator_with_fake_io(main_window)
    if has_repairs:
        fake_project_io.load_result = ProjectLoadResult(
            project=fake_project_io.load_result.project,
            repair_report=RegionLineRepairReport(
                actions=(
                    RegionLineRepairAction(
                        kind=RegionLineTopologyIssueKind.REGION_LINE_MISMATCH,
                        region_id="region-a",
                        line_id="line-1",
                        line_species="C IV",
                        line_transition="1548",
                    ),
                )
            ),
        )
    message_dialogs = _FakeMessageDialogs()
    handler._file_dialogs = cast(ProjectFileDialogAdapter, _FakeOpenProjectDialog())
    handler._message_dialogs = cast(ProjectMessageDialogAdapter, message_dialogs)
    handler._recent_directories = cast(RecentProjectDirectoryAdapter, _FakeRecentDirectories())

    handler.open_project()

    assert len(message_dialogs.repair_notices) == int(has_repairs)
    if has_repairs:
        summary, details = message_dialogs.repair_notices[0]
        assert summary.startswith("1 inconsistent line reference")
        assert "C IV 1548" in details


def test_repair_notice_describes_each_issue_kind_without_region_uuids(qtbot: "QtBot") -> None:
    """Each repair kind reports its actual effect with display-region labels."""
    missing_region_id = "11111111-1111-4111-8111-111111111111"
    duplicate_region_id = "22222222-2222-4222-8222-222222222222"
    mismatch_region_id = "33333333-3333-4333-8333-333333333333"
    claimed_region_id = "44444444-4444-4444-8444-444444444444"
    project = SpectroscopyProject(name="repaired")
    project.absorption_lines = {
        "missing-display": _line(
            "missing-display",
            missing_region_id,
            species="Si II",
            transition="1260",
            rest_wavelength=1260.0,
        ),
        "duplicate-display": _line(
            "duplicate-display",
            duplicate_region_id,
            species="Si IV",
            transition="1393",
            rest_wavelength=1393.0,
        ),
        "mismatch-line": _line(
            "mismatch-line",
            mismatch_region_id,
            species="O VI",
            transition="1031",
            rest_wavelength=1031.0,
        ),
        "unlisted-line": _line(
            "unlisted-line",
            UNASSIGNED_REGION_ID,
            species="N V",
            transition="1238",
            rest_wavelength=1238.0,
        ),
    }
    project.absorption_regions = {
        missing_region_id: AbsorptionRegion(
            region_id=missing_region_id, line_ids=["missing-display"]
        ),
        duplicate_region_id: AbsorptionRegion(
            region_id=duplicate_region_id, line_ids=["duplicate-display"]
        ),
        mismatch_region_id: AbsorptionRegion(
            region_id=mismatch_region_id, line_ids=["mismatch-line"]
        ),
        UNASSIGNED_REGION_ID: AbsorptionRegion(
            region_id=UNASSIGNED_REGION_ID, line_ids=["unlisted-line"]
        ),
    }
    report = RegionLineRepairReport(
        actions=(
            RegionLineRepairAction(
                kind=RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE,
                region_id=missing_region_id,
                line_id="missing-line",
                line_species="",
                line_transition="",
            ),
            RegionLineRepairAction(
                kind=RegionLineTopologyIssueKind.DUPLICATE_MEMBERSHIP,
                region_id=duplicate_region_id,
                line_id="duplicate-line",
                line_species="C IV",
                line_transition="1548",
            ),
            RegionLineRepairAction(
                kind=RegionLineTopologyIssueKind.REGION_LINE_MISMATCH,
                region_id=mismatch_region_id,
                line_id="mismatch-line",
                line_species="O VI",
                line_transition="1031",
            ),
            RegionLineRepairAction(
                kind=RegionLineTopologyIssueKind.UNLISTED_LINE,
                region_id=claimed_region_id,
                line_id="unlisted-line",
                line_species="N V",
                line_transition="1238",
            ),
        )
    )
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)
    message_dialogs = _FakeMessageDialogs()
    handler._message_dialogs = cast(ProjectMessageDialogAdapter, message_dialogs)

    handler._show_repair_notice(report, project)

    _, details = message_dialogs.repair_notices[0]
    assert details.splitlines() == [
        'Region "Si II (1)": a reference to a missing line was removed.',
        'Region "Si IV (1)": line "C IV 1548" was removed from this region because '
        "another region owns it.",
        'Region "O VI (1)": line "O VI 1031" was updated to reference this region.',
        'Line "N V 1238" did not belong to any region and was moved to Unassigned.',
    ]
    for region_id in (
        missing_region_id,
        duplicate_region_id,
        mismatch_region_id,
        claimed_region_id,
    ):
        assert region_id not in details


def test_repair_notice_uses_short_id_for_pruned_region(qtbot: "QtBot") -> None:
    """A pruned region falls back to its shortened UUID in every detail."""
    region_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    report = RegionLineRepairReport(
        actions=(
            RegionLineRepairAction(
                kind=RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE,
                region_id=region_id,
                line_id="missing-line",
                line_species="",
                line_transition="",
            ),
        )
    )
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)
    message_dialogs = _FakeMessageDialogs()
    handler._message_dialogs = cast(ProjectMessageDialogAdapter, message_dialogs)

    handler._show_repair_notice(report, SpectroscopyProject(name="repaired"))

    _, details = message_dialogs.repair_notices[0]
    assert details.splitlines() == [
        'Region "aaaaaaaa": a reference to a missing line was removed.',
        'Region "aaaaaaaa" no longer has any lines and was removed.',
    ]
    assert region_id not in details


def test_repair_notice_translates_unassigned_region_label(qtbot: "QtBot") -> None:
    """The internal unassigned-region ID is replaced by translatable source text."""
    report = RegionLineRepairReport(
        actions=(
            RegionLineRepairAction(
                kind=RegionLineTopologyIssueKind.MISSING_LINE_REFERENCE,
                region_id=UNASSIGNED_REGION_ID,
                line_id="missing-line",
                line_species="",
                line_transition="",
            ),
        )
    )
    main_window = QMainWindow()
    qtbot.addWidget(main_window)
    handler, _ = _coordinator_with_fake_io(main_window)
    message_dialogs = _FakeMessageDialogs()
    handler._message_dialogs = cast(ProjectMessageDialogAdapter, message_dialogs)

    handler._show_repair_notice(report, SpectroscopyProject(name="repaired"))

    _, details = message_dialogs.repair_notices[0]
    assert details == 'Region "Unassigned": a reference to a missing line was removed.'
    assert UNASSIGNED_REGION_ID not in details


def test_lupdate_extracts_project_file_coordinator_gui_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated project file handler source text."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "chappy_ja.ts"
    run_lupdate(
        source_dirs=[
            Path("src/chappy/gui/shell/project_file_coordinator.py"),
            Path("src/chappy/gui/shell/project_file_dialog_adapters.py"),
        ],
        ts_output=ts_path,
    )

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    expected_sources = {
        "Error",
        "&Open Project...",
        "Save Project &As...",
        "Save Project?",
        "The current project has unsaved changes.\nDo you want to save them?",
        "Save",
        "Don't Save",
        "Cancel",
        "❌ Please drop either FITS files or a project file, not both.",
        "✅ Ready to load project: {name}",
        " ({pixel_count} pixels)",
        "✅ Ready to load: {file_name}{pixel_suffix}",
        "Unknown validation error",
        "❌ Invalid FITS file: {reason}",
        "❌ Cannot read FITS file: {error}",
        "❌ Only FITS (.fits, .fit) or project files are supported.",
        "❌ Please drop either the flux/error pair or a single project file, not both.",
        "❌ Only one project file can be opened at a time.",
        "❌ No valid FITS or project files found in the drop.",
        "❌ Failed to load dropped file.",
        "Loading flux {flux_name} with {count} error file(s)...",
        "Loading flux file: {flux_name}...",
        "✅ Loaded: {flux_name} with error: {error_name}",
        "✅ Loaded project from: {source}",
        "Auto-detected: flux={flux_name}, error={error_name}...",
        "❌ No flux file selected.",
        "✅ Loaded: {flux_name} with {count} error files",
        " • {count} file(s) ignored",
        "❌ Failed to load selected files.",
        "Loading project...",
        "Opened project: {name}",
        "Failed to open project:\n{error}",
        "Saving project...",
        "Project saved",
        "Failed to save project",
        "Failed to save project:\n{error}",
        "Project saved as: {name}",
        "Failed to open project",
        "Loading flux: {flux} with error: {error}...",
        "✅ Loaded: {flux} with error: {error}",
        "Failed to load observation data:\n{error}",
        "Failed to load observation data",
        "Could not load dropped files:\n{error}",
        "Could not load selected files:\n{error}",
        "Unassigned",
        'Region "{region}": a reference to a missing line was removed.',
        'Region "{region}": line "{species} {transition}" was removed from this region because '
        "another region owns it.",
        'Region "{region}": line "{species} {transition}" was updated to reference this region.',
        'Line "{species} {transition}" did not belong to any region and was moved to '
        "{unassigned}.",
    }
    assert expected_sources <= sources
    assert not any("DLG__" in source for source in sources)
    assert not any("GUI__" in source for source in sources)
