"""Tests for history operation Qt translation helpers."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chappy.core.history import OperationId
from chappy.gui.history.translation import (
    _OPERATION_SOURCES,
    normalize_operation_id,
    translate_operation,
)
from chappy.i18n.language_switcher import LanguageSwitcher
from scripts.i18n_lupdate import run_lupdate


HISTORY_OPERATION_SOURCES = {
    "Add Temporary Line",
    "Remove Temporary Line",
    "Clear Temporary Lines",
    "Register Selected Lines",
    "Move Lines",
    "Split Region",
    "Merge Regions",
    "Delete Region",
    "Create Mask",
    "Delete Mask",
    "Edit Mask",
    "Add Continuum Point",
    "Delete Continuum Point",
    "Move Continuum Point",
    "Reset Continuum",
    "Add Component",
    "Delete Component",
    "Bulk Add Components",
    "Bulk Delete Components",
    "Edit Parameters",
    "Edit Spectral Resolution",
    "Bulk Add Multiplet",
    "Bulk Delete Multiplet",
    "Apply Optimization",
    "Change Display Range",
}


@pytest.mark.parametrize(
    ("operation_id", "expected"),
    [
        ("ident.add_temporary_line", "ident.add_temporary_line"),
        ("cont.add_point.nav", "cont.add_point"),
        ("draw.range_change.manual", "draw.range_change"),
    ],
)
def test_normalize_operation_id(operation_id: str, expected: str) -> None:
    """Operation qualifiers should not affect the display source lookup."""
    assert normalize_operation_id(operation_id) == expected


@pytest.mark.parametrize("operation_id", ["", "unknown", ".action", "namespace."])
def test_normalize_operation_id_fails_for_malformed_id(operation_id: str) -> None:
    """Malformed operation IDs should fail fast instead of using a placeholder."""
    with pytest.raises(ValueError, match="Malformed history operation ID"):
        normalize_operation_id(operation_id)


def test_translate_operation_returns_source_text_for_known_operation() -> None:
    """Known operation IDs should resolve to Qt source text."""
    result = translate_operation("cont.add_point", LanguageSwitcher())

    assert result == "Add Continuum Point"


def test_translate_operation_ignores_qualifier() -> None:
    """Known operation IDs should ignore optional qualifiers."""
    result = translate_operation("draw.range_change.nav", LanguageSwitcher())

    assert result == "Change Display Range"


def test_translate_operation_fails_for_unknown_operation() -> None:
    """Unknown operation IDs should fail fast instead of using a debug fallback."""
    with pytest.raises(KeyError, match="Missing history operation source text"):
        translate_operation("unknown.action", LanguageSwitcher())


def test_translation_catalog_covers_all_operation_ids() -> None:
    """Every operation ID must have a Qt source text entry."""
    assert {operation_id.value for operation_id in OperationId} <= _OPERATION_SOURCES.keys()


def test_lupdate_extracts_history_operation_sources(tmp_path: Path) -> None:
    """Verify lupdate extracts migrated history operation source text."""
    if shutil.which("pyside6-lupdate") is None:
        pytest.skip("pyside6-lupdate is not available")

    ts_path = tmp_path / "history_translation.ts"
    run_lupdate(source_dirs=[Path("src/chappy/gui/history/translation.py")], ts_output=ts_path)

    root = ET.parse(ts_path).getroot()
    sources = {
        source.text
        for source in root.findall("./context/message/source")
        if source.text is not None
    }
    assert HISTORY_OPERATION_SOURCES <= sources
    assert not any("MSG__" in source for source in sources)
