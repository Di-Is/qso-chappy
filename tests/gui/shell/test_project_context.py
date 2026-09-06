"""Tests for local project UI identity."""

from __future__ import annotations

from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from uuid import UUID

import pytest

from chappy.gui.modes.common.project_key import (
    _canonicalize_resolved_path,
    _case_lookup_key,
    _select_canonical_entry_name,
    _split_absolute_path,
)
from chappy.gui.shell.project_context import (
    ProjectKey,
    ProjectPathCanonicalizationError,
    canonical_project_path,
)


def _project_file(path: Path) -> Path:
    """Create one saved-project file for identity tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def test_saved_project_key_uses_canonical_absolute_path(tmp_path) -> None:
    """Equivalent path spellings must resolve to one saved-project key."""
    project_path = _project_file(tmp_path / "observations" / "target.h5")
    equivalent_path = project_path.parent / ".." / "observations" / "target.h5"

    assert canonical_project_path(project_path) == canonical_project_path(equivalent_path)
    assert ProjectKey.for_saved_path(project_path) == ProjectKey.for_saved_path(equivalent_path)


def test_same_filename_in_different_directories_has_distinct_keys(tmp_path) -> None:
    """A basename must not identify a saved project."""
    first = _project_file(tmp_path / "first" / "target.h5")
    second = _project_file(tmp_path / "second" / "target.h5")

    assert ProjectKey.for_saved_path(first) != ProjectKey.for_saved_path(second)


def test_saved_project_key_resolves_symlink_to_target(tmp_path: Path) -> None:
    """A symlink spelling and parent traversal should identify the target project."""
    project_path = _project_file(tmp_path / "projects" / "target.h5")
    link_path = tmp_path / "links" / "project.h5"
    link_path.parent.mkdir()
    try:
        link_path.symlink_to(project_path)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
    traversed_link = link_path.parent / ".." / "links" / link_path.name

    assert ProjectKey.for_saved_path(traversed_link) == ProjectKey.for_saved_path(project_path)


def test_saved_project_key_obeys_current_volume_case_semantics(tmp_path: Path) -> None:
    """Case variants should follow the identity behavior of the actual test volume."""
    stored_path = _project_file(tmp_path / "ScienceProject.H5")
    case_variant = tmp_path / "scienceproject.h5"

    if case_variant.exists() and case_variant.samefile(stored_path):
        assert ProjectKey.for_saved_path(case_variant) == ProjectKey.for_saved_path(stored_path)
        assert canonical_project_path(case_variant) == str(stored_path.resolve())
        return

    _project_file(case_variant)
    assert ProjectKey.for_saved_path(case_variant) != ProjectKey.for_saved_path(stored_path)


def test_canonical_entry_selection_is_volume_aware_without_global_casefold() -> None:
    """Pure selection should use stored case only when filesystem identity agrees."""
    insensitive_candidates = (("ScienceProject.H5", True),)
    sensitive_candidates = (("ScienceProject.H5", False), ("scienceproject.h5", True))

    assert (
        _select_canonical_entry_name("scienceproject.h5", insensitive_candidates)
        == "ScienceProject.H5"
    )
    assert (
        _select_canonical_entry_name("scienceproject.h5", sensitive_candidates)
        == "scienceproject.h5"
    )


def test_unicode_case_lookup_still_requires_filesystem_identity() -> None:
    """Unicode-normalized candidates must not merge distinct case-sensitive entries."""
    composed = "Café.H5"
    decomposed = "Cafe\N{COMBINING ACUTE ACCENT}.h5"

    assert _case_lookup_key(composed) == _case_lookup_key(decomposed)
    assert _select_canonical_entry_name(decomposed, ((composed, True),)) == composed
    assert (
        _select_canonical_entry_name(decomposed, ((composed, False), (decomposed, True)))
        == decomposed
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (PurePosixPath("/home/research/project.h5"), ("/", ("home", "research", "project.h5"))),
        (
            PureWindowsPath(r"C:\Users\research\project.h5"),
            ("C:\\", ("Users", "research", "project.h5")),
        ),
        (
            PureWindowsPath(r"\\server\share\research\project.h5"),
            ("\\\\server\\share\\", ("research", "project.h5")),
        ),
    ],
)
def test_absolute_path_split_supports_posix_windows_drive_and_unc(
    path: PurePath, expected: tuple[str, tuple[str, ...]]
) -> None:
    """Root traversal must start from the native POSIX, drive, or UNC anchor."""
    assert _split_absolute_path(path) == expected


def test_canonicalization_wraps_parent_listing_errors(tmp_path: Path) -> None:
    """A parent without list permission should fail with the typed path error."""

    def _denied_entries(_directory: Path) -> tuple[Path, ...]:
        raise PermissionError("injected parent listing denial")

    with pytest.raises(
        ProjectPathCanonicalizationError, match="Cannot list project path parent"
    ) as captured:
        _canonicalize_resolved_path(tmp_path / "project.h5", directory_entries=_denied_entries)

    assert isinstance(captured.value.__cause__, PermissionError)


def test_canonicalization_wraps_entry_identity_errors(tmp_path: Path) -> None:
    """An identity lookup race should fail with the typed path error."""
    resolved = tmp_path / "project.h5"
    _anchor, parts = _split_absolute_path(resolved)

    def _matching_entry(directory: Path) -> tuple[Path, ...]:
        return (directory / parts[0],)

    def _failed_identity(_first: Path, _second: Path) -> bool:
        raise OSError("injected identity failure")

    with pytest.raises(
        ProjectPathCanonicalizationError, match="Cannot compare project path entry identity"
    ) as captured:
        _canonicalize_resolved_path(
            resolved, directory_entries=_matching_entry, same_file=_failed_identity
        )

    assert isinstance(captured.value.__cause__, OSError)


def test_saved_project_key_rejects_missing_or_non_file_paths(tmp_path: Path) -> None:
    """Only an existing saved-project file may receive a persistent key."""
    with pytest.raises(FileNotFoundError):
        ProjectKey.for_saved_path(tmp_path / "missing.h5")

    with pytest.raises(ValueError, match="existing file"):
        ProjectKey.for_saved_path(tmp_path)


def test_unsaved_project_key_is_session_only_and_repeatable_for_explicit_uuid() -> None:
    """Unsaved keys must carry no persistent-path semantics."""
    session_id = UUID("12345678-1234-5678-1234-567812345678")

    key = ProjectKey.for_unsaved_session(session_id)

    assert key == ProjectKey.for_unsaved_session(session_id)
    assert key.persistent is False
    assert key.value == f"session:{session_id}"
