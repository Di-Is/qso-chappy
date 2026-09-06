"""Tests for the single-column identify side panel layout and persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from chappy.gui.modes.identify.panel.panel import (
    CONFIRMED_COLLAPSED_KEY,
    NONEMPTY_SPLITTER_SIZES_KEY,
    IdentifySidePanel,
)
from chappy.gui.modes.identify.panel.panel_models import (
    TemporaryLineRow,
    CandidateRow,
    ConfirmedLineRow,
    ConfirmedRegionRow,
    RegionPreviewRow,
    TemporaryLineItemPayload,
)
from chappy.gui.theme import empty_state_label_style
from tests.gui.support.faithful_env import faithful_application_environment

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "identify_panel.ini"), QSettings.Format.IniFormat)


def _candidate_rows() -> list[CandidateRow]:
    return [
        CandidateRow("candidate-1", 3544.8, 3545.6, 11.2, "candidate"),
        CandidateRow("candidate-2", 3550.0, 3550.8, 7.5, "unused"),
        CandidateRow("candidate-3", 3556.2, 3557.0, 9.8, "identified"),
    ]


def _temporary_rows() -> tuple[list[TemporaryLineRow], list[RegionPreviewRow]]:
    rows = [
        TemporaryLineRow(
            temporary_line_ids=("temporary-1",),
            species="C IV",
            lambda_start=3544.8,
            lambda_end=3546.3,
            creation_method="manual",
            transition_name="C IV 1548",
            redshift=1.2913,
        )
    ]
    previews = [
        RegionPreviewRow(
            group_id="preview-1",
            label="C IV",
            member_count=1,
            member_temporary_line_ids=["temporary-1"],
        )
    ]
    return rows, previews


def _confirmed_rows() -> list[ConfirmedRegionRow]:
    return [
        ConfirmedRegionRow(
            group_id="region-1",
            label="Region 1",
            lines=[
                ConfirmedLineRow(
                    line_id="confirmed-1",
                    species="C IV",
                    redshift=1.292,
                    lambda_start=3544.8,
                    lambda_end=3546.3,
                )
            ],
            is_expanded=True,
        )
    ]


def _assert_inside(child: QWidget, parent: QWidget) -> None:
    child_rect = QRect(child.mapTo(parent, QPoint()), child.size())
    assert QRect(QPoint(), parent.size()).contains(child_rect)


def _select_first_temporary_line(panel: IdentifySidePanel) -> None:
    tree = panel._temporary_section._temporary_tree
    top_level = tree.topLevelItem(0)
    assert top_level is not None
    item = top_level
    if not item.flags() & Qt.ItemFlag.ItemIsSelectable:
        item = top_level.child(0)
        assert item is not None
    payload = item.data(0, Qt.ItemDataRole.UserRole)
    assert isinstance(payload, TemporaryLineItemPayload)
    item.setSelected(True)


def _show_state(
    qtbot: QtBot,
    *,
    width: int,
    has_temporary: bool,
    has_confirmed: bool,
    has_candidates: bool = True,
) -> IdentifySidePanel:
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)
    panel.resize(width, 760)
    panel.set_candidates(_candidate_rows() if has_candidates else [])
    temporary_rows, previews = _temporary_rows()
    panel.set_temporary_lines(
        temporary_rows if has_temporary else [], previews if has_temporary else []
    )
    panel.set_confirmed_regions(_confirmed_rows() if has_confirmed else [])
    panel.show()
    QApplication.processEvents()
    return panel


def test_preset_setup_header_is_always_visible_without_collapsible(qtbot: QtBot) -> None:
    """The setup header has no collapse wrapper and stays visible."""
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)
    panel.show()

    assert panel.findChild(QWidget, "identifyPresetCollapsible") is None
    assert panel._preset_section.isVisible()
    assert panel._preset_section.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum


def test_disclosure_header_is_one_full_width_mouse_and_keyboard_target(qtbot: QtBot) -> None:
    """The title, summary, and trailing chevron form one accessible control."""
    panel = _show_state(qtbot, width=420, has_temporary=True, has_confirmed=True)
    collapsible = panel._confirmed_collapsible
    header = collapsible._header_button
    summary_center = header.summary_label.mapTo(header, header.summary_label.rect().center())

    assert header.width() == collapsible.width()
    assert collapsible.is_collapsed()
    assert not header._keyboard_focus_visible

    qtbot.mouseClick(header, Qt.MouseButton.LeftButton, pos=summary_center)
    assert not collapsible.is_collapsed()
    assert not header._keyboard_focus_visible

    qtbot.keyClick(header, Qt.Key.Key_Return)
    assert collapsible.is_collapsed()
    assert header._keyboard_focus_visible

    qtbot.keyClick(header, Qt.Key.Key_Space)
    assert not collapsible.is_collapsed()


@pytest.mark.parametrize("language", ["en", "ja"])
def test_preset_setup_header_keeps_practical_width_at_480(
    qtbot: QtBot, qapp: QApplication, language: str
) -> None:
    """The new-candidate editor must not widen the representative side panel."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(qtbot, width=480, has_temporary=True, has_confirmed=True)
        QApplication.processEvents()

        spinbox = panel._preset_section._half_width_spinbox
        assert panel.width() == 480
        assert spinbox.width() < 160
        _assert_inside(spinbox, panel)


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("width", [320, 420])
def test_registration_feedback_is_passive_and_wraps(
    qtbot: QtBot, qapp: QApplication, width: int, language: str
) -> None:
    """Long registration feedback remains readable without an embedded action."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(
            qtbot, width=width, has_temporary=False, has_confirmed=False, has_candidates=False
        )
        message = (
            "4線を登録しました（新規領域2件、非常に長い名前の既存領域へ追加。"
            "整理モードで重なりを確認してください）。"
            if language == "ja"
            else (
                "Registered 4 lines (2 new regions, added to a long existing region name; "
                "check overlapping assignments in Analysis Structure)."
            )
        )
        panel.show_registration_feedback(message)
        QApplication.processEvents()
        temporary = panel._temporary_section
        feedback = temporary._registration_feedback
        label = temporary._registration_feedback_label

        assert feedback.isVisible()
        assert not temporary._temporary_placeholder.isVisible()
        assert label.text() == message
        assert label.wordWrap()
        _assert_inside(feedback, panel)


def test_workflow_refresh_clears_registration_feedback(qtbot: QtBot) -> None:
    """The next temporary-line refresh expires registration feedback."""
    panel = _show_state(
        qtbot, width=320, has_temporary=False, has_confirmed=False, has_candidates=True
    )
    panel.show_registration_feedback("Registered 2 lines")

    panel.set_temporary_lines([])

    assert not panel._temporary_section._registration_feedback.isVisible()
    assert panel._temporary_section._temporary_placeholder.isVisible()


def test_ui_state_changed_emitted_on_collapse_toggle(qtbot: QtBot) -> None:
    """Collapse toggles notify the shell persistence path."""
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.ui_state_changed, timeout=1000):
        panel._confirmed_collapsible.set_collapsed(False)


def test_nonempty_layout_and_disclosures_round_trip_before_data_restore(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """Stored non-empty geometry survives restore before workflow data arrives."""
    panel = _show_state(qtbot, width=420, has_temporary=True, has_confirmed=True)
    panel._confirmed_collapsible.set_collapsed(False)
    panel._splitter.setSizes([360, 240, 180])
    panel._on_splitter_moved()
    saved_nonempty = panel._last_nonempty_splitter_sizes
    assert saved_nonempty is not None

    settings = _settings(tmp_path)
    panel.save_ui_state(settings)
    settings.sync()

    restored = IdentifySidePanel()
    qtbot.addWidget(restored)
    restored.resize(420, 760)
    restored.show()
    restored.restore_ui_state(_settings(tmp_path))
    QApplication.processEvents()

    assert restored._last_nonempty_splitter_sizes == saved_nonempty
    assert not restored._confirmed_collapsible.is_collapsed()
    assert restored._confirmed_collapsible._content.isVisible()
    assert restored._confirmed_section._empty_placeholder.isVisible()

    rows, previews = _temporary_rows()
    restored.set_temporary_lines(rows, previews)
    restored.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()

    assert restored._last_nonempty_splitter_sizes == saved_nonempty
    assert restored._confirmed_collapsible._content.isVisible()
    assert restored._splitter.sizes()[1] >= restored._temporary_section.minimum_readable_height()


def test_empty_derived_layout_does_not_overwrite_saved_nonempty_sizes(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """Window-close persistence ignores temporary and confirmed empty compaction."""
    panel = _show_state(qtbot, width=420, has_temporary=True, has_confirmed=True)
    panel._confirmed_collapsible.set_collapsed(False)
    panel._splitter.setSizes([350, 230, 170])
    panel._on_splitter_moved()
    saved_nonempty = panel._last_nonempty_splitter_sizes
    assert saved_nonempty is not None

    panel.set_temporary_lines([])
    panel.set_confirmed_regions([])
    QApplication.processEvents()
    compact_sizes = panel._splitter.sizes()
    assert compact_sizes != list(saved_nonempty)

    settings = _settings(tmp_path)
    panel.save_ui_state(settings)
    settings.sync()

    assert settings.value(NONEMPTY_SPLITTER_SIZES_KEY) == panel._encode_splitter_sizes(
        saved_nonempty
    )


def test_collapsed_confirmed_reclaim_is_not_double_counted_in_saved_layout(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """A compact confirmed summary does not inflate the saved candidate height."""
    panel = _show_state(qtbot, width=420, has_temporary=True, has_confirmed=True)
    assert panel._confirmed_collapsible.is_collapsed()
    panel._splitter.setSizes([414, 250, panel._confirmed_collapsible.sizeHint().height()])
    panel._on_splitter_moved()
    displayed_sizes = panel._splitter.sizes()
    saved_nonempty = panel._last_nonempty_splitter_sizes
    assert saved_nonempty is not None
    assert sum(saved_nonempty) == sum(displayed_sizes)

    rows, previews = _temporary_rows()
    panel.set_temporary_lines([])
    panel.set_temporary_lines(rows, previews)
    QApplication.processEvents()
    assert panel._splitter.sizes() == displayed_sizes

    settings = _settings(tmp_path)
    panel.save_ui_state(settings)
    restored = IdentifySidePanel()
    qtbot.addWidget(restored)
    restored.resize(420, 760)
    restored.restore_ui_state(settings)
    restored.set_temporary_lines(rows, previews)
    restored.set_confirmed_regions(_confirmed_rows())
    restored.show()
    QApplication.processEvents()

    assert restored._confirmed_collapsible.is_collapsed()
    assert restored._splitter.sizes() == displayed_sizes


@pytest.mark.parametrize("prior_sizes", [None, (340, 230, 130)])
def test_confirmed_only_user_layout_round_trips_before_data_and_temporary_arrives_later(
    qtbot: QtBot, tmp_path: Path, prior_sizes: tuple[int, int, int] | None
) -> None:
    """Confirmed-only adjustment preserves the compact temporary pane's baseline."""
    settings = _settings(tmp_path)
    settings.setValue(CONFIRMED_COLLAPSED_KEY, False)
    if prior_sizes is not None:
        settings.setValue(
            NONEMPTY_SPLITTER_SIZES_KEY, IdentifySidePanel._encode_splitter_sizes(prior_sizes)
        )
    settings.sync()

    panel = IdentifySidePanel()
    qtbot.addWidget(panel)
    panel.resize(420, 760)
    panel.show()
    panel.restore_ui_state(settings)
    panel.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()
    assert not panel._confirmed_collapsible.is_collapsed()

    compact_temporary = panel._temporary_section.maximumHeight()
    panel._splitter.setSizes([360, compact_temporary, 280])
    confirmed_only_sizes = panel._splitter.sizes()
    panel.save_ui_state(settings)
    settings.sync()
    saved_nonempty = panel._last_nonempty_splitter_sizes
    assert saved_nonempty is not None
    assert saved_nonempty[1] > confirmed_only_sizes[1]
    assert saved_nonempty[2] == confirmed_only_sizes[2]
    assert sum(saved_nonempty) == sum(confirmed_only_sizes)

    restored = IdentifySidePanel()
    qtbot.addWidget(restored)
    restored.resize(420, 760)
    restored.show()
    restored.restore_ui_state(_settings(tmp_path))
    QApplication.processEvents()
    assert restored._last_nonempty_splitter_sizes == saved_nonempty
    assert restored._confirmed_collapsible._content.isVisible()
    assert restored._confirmed_section._empty_placeholder.isVisible()

    restored.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()
    assert restored._confirmed_collapsible._content.isVisible()
    assert restored._splitter.sizes() == confirmed_only_sizes

    rows, previews = _temporary_rows()
    restored.set_temporary_lines(rows, previews)
    QApplication.processEvents()
    assert restored._last_nonempty_splitter_sizes == saved_nonempty
    assert restored._splitter.sizes()[1] >= restored._temporary_section.minimum_readable_height()
    assert restored._confirmed_collapsible._content.isVisible()
    assert restored._splitter.sizes()[2] > 0


def test_temporary_and_confirmed_content_transitions_restore_user_layout(qtbot: QtBot) -> None:
    """Repeated empty transitions preserve user geometry and confirmed expansion."""
    panel = _show_state(qtbot, width=420, has_temporary=True, has_confirmed=True)
    panel._confirmed_collapsible.set_collapsed(False)
    panel._splitter.setSizes([350, 230, 170])
    panel._on_splitter_moved()
    saved_nonempty = panel._last_nonempty_splitter_sizes
    assert saved_nonempty is not None
    rows, previews = _temporary_rows()

    for _ in range(2):
        panel.set_temporary_lines([])
        QApplication.processEvents()
        assert panel._splitter.sizes()[1] == panel._temporary_section.maximumHeight()
        panel.set_temporary_lines(rows, previews)
        QApplication.processEvents()
        assert panel._last_nonempty_splitter_sizes == saved_nonempty
        assert panel._splitter.sizes()[1] >= panel._temporary_section.minimum_readable_height()

    panel.set_confirmed_regions([])
    QApplication.processEvents()
    assert panel._confirmed_collapsible._content.isVisible()
    assert panel._confirmed_section._empty_placeholder.isVisible()
    panel.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()
    assert panel._confirmed_collapsible._content.isVisible()
    assert panel._confirmed_section._groups_tree.isVisible()
    assert panel._last_nonempty_splitter_sizes == saved_nonempty


@pytest.mark.parametrize("language", ["ja", "en"])
@pytest.mark.parametrize("width", [320, 420])
def test_temporary_action_tray_keeps_group_heading_and_two_lines_visible(
    qtbot: QtBot, qapp: QApplication, language: str, width: int
) -> None:
    """The non-empty action tray reserves three visible tree rows."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(qtbot, width=width, has_temporary=False, has_confirmed=False)
        rows = [
            TemporaryLineRow(
                temporary_line_ids=(f"temporary-{index}",),
                species="C IV",
                lambda_start=3544.8 + index,
                lambda_end=3545.6 + index,
                creation_method="manual",
                transition_name=f"C IV line {index}",
                redshift=1.2913 + index / 10_000,
            )
            for index in (1, 2)
        ]
        preview = RegionPreviewRow(
            group_id="preview-1",
            label="C IV",
            member_count=2,
            member_temporary_line_ids=["temporary-1", "temporary-2"],
        )

        panel.set_temporary_lines(rows, [preview])
        QApplication.processEvents()

        temporary = panel._temporary_section
        row_height = temporary._temporary_tree.sizeHintForRow(0)
        assert temporary._temporary_tree.topLevelItemCount() == 1
        heading = temporary._temporary_tree.topLevelItem(0)
        assert heading is not None
        assert heading.childCount() == 2
        assert temporary.height() >= temporary.minimum_readable_height()
        assert temporary._temporary_tree.height() >= (
            3 * row_height + 2 * temporary._temporary_tree.frameWidth()
        )


def test_confirmed_user_collapse_survives_data_updates(qtbot: QtBot) -> None:
    """Data updates never override the user's confirmed-history disclosure."""
    panel = _show_state(qtbot, width=420, has_temporary=True, has_confirmed=True)
    assert panel._confirmed_collapsible.is_collapsed()
    assert "Region 1" in panel._confirmed_collapsible._summary_label.full_text

    panel._confirmed_collapsible.set_collapsed(False)
    panel.set_confirmed_regions(_confirmed_rows())
    panel.set_confirmed_regions([])
    panel.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()

    assert not panel._confirmed_collapsible.is_collapsed()
    assert panel._confirmed_collapsible._content.isVisible()


def test_confirmed_state_is_persisted_without_legacy_sigma_disclosure_key(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """Only controls that still disclose content persist a collapse state."""
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)
    panel._confirmed_collapsible.set_collapsed(False)
    settings = _settings(tmp_path)
    panel.save_ui_state(settings)

    assert not settings.contains("identify_panel/sigma_adjust_expanded")
    assert not settings.value(CONFIRMED_COLLAPSED_KEY, type=bool)


def test_empty_states_and_all_sections_collapsed_do_not_break(qtbot: QtBot) -> None:
    """Zero candidates, temporary lines, and regions render placeholders."""
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)
    panel.resize(300, 700)

    panel.set_candidates([])
    panel.set_temporary_lines([])
    panel.set_confirmed_regions([])
    panel.show()

    candidate_section = panel._candidate_section
    assert (
        candidate_section._candidate_stack.currentWidget()
        is candidate_section._candidate_placeholder_page
    )
    assert panel._temporary_section._temporary_placeholder.isVisible()
    assert not panel._temporary_section._temporary_tree.isVisible()
    assert not panel._confirmed_section._groups_tree.isVisible()
    assert panel._confirmed_collapsible._header_button.isEnabled()
    assert not panel._confirmed_collapsible._content.isVisible()
    assert "0 regions" in panel._confirmed_collapsible._summary_label.full_text


def test_content_surfaces_stay_stable_across_workflow_states(qtbot: QtBot) -> None:
    """Data changes replace content inside stable frames without replacing the frames."""
    panel = _show_state(
        qtbot, width=320, has_temporary=False, has_confirmed=False, has_candidates=True
    )
    temporary = panel._temporary_section
    confirmed = panel._confirmed_section
    temporary_surface = temporary._content_surface
    confirmed_surface = confirmed._content_surface

    assert temporary_surface.isVisible()
    assert temporary._temporary_placeholder.isVisible()
    assert "border: 1px solid" in temporary_surface.styleSheet()

    temporary_rows, previews = _temporary_rows()
    panel.set_temporary_lines(temporary_rows, previews)
    QApplication.processEvents()
    assert temporary._content_surface is temporary_surface
    assert temporary_surface.isVisible()
    assert temporary._temporary_tree.isVisible()

    panel.set_temporary_lines([])
    panel.show_registration_feedback("Registered 1 line")
    QApplication.processEvents()
    assert temporary._content_surface is temporary_surface
    assert temporary_surface.isVisible()
    assert temporary._registration_feedback.isVisible()

    assert panel._confirmed_collapsible.is_collapsed()
    assert not confirmed_surface.isVisible()
    panel._confirmed_collapsible.set_collapsed(False)
    QApplication.processEvents()
    assert confirmed._content_surface is confirmed_surface
    assert confirmed_surface.isVisible()
    assert confirmed._empty_placeholder.isVisible()
    assert "border: 1px solid" in confirmed_surface.styleSheet()

    panel.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()
    assert confirmed._content_surface is confirmed_surface
    assert confirmed_surface.isVisible()
    assert confirmed._groups_tree.isVisible()

    panel.set_confirmed_regions([])
    QApplication.processEvents()
    assert confirmed._content_surface is confirmed_surface
    assert confirmed_surface.isVisible()
    assert confirmed._empty_placeholder.isVisible()


def test_compact_registration_feedback_fits_wrapped_text(qtbot: QtBot) -> None:
    """Compact feedback height follows wrapping at the rendered panel width."""
    panel = _show_state(
        qtbot, width=320, has_temporary=False, has_confirmed=True, has_candidates=True
    )
    panel.show_registration_feedback(
        "3 lines registered (1 new region, added to Region 3; "
        "check overlapping assignments in Analysis Structure)."
    )
    QApplication.processEvents()

    temporary = panel._temporary_section
    label = temporary._registration_feedback_label
    layout = temporary.layout()
    assert layout is not None
    assert label.height() >= label.heightForWidth(label.width())
    assert temporary.maximumHeight() >= layout.totalHeightForWidth(temporary.width())
    assert panel._splitter.sizes()[1] == temporary.height()
    _assert_inside(temporary._content_surface, temporary)
    _assert_inside(label, temporary._registration_feedback)


def test_splitter_handles_expose_only_available_resize_operations(qtbot: QtBot) -> None:
    """Compact panes disable handles that cannot perform a resize."""
    panel = _show_state(
        qtbot, width=320, has_temporary=False, has_confirmed=False, has_candidates=True
    )
    candidate_temporary_handle = panel._splitter.handle(1)
    temporary_confirmed_handle = panel._splitter.handle(2)

    assert not candidate_temporary_handle.isEnabled()
    assert not temporary_confirmed_handle.isEnabled()
    assert candidate_temporary_handle.cursor().shape() is Qt.CursorShape.ArrowCursor
    assert temporary_confirmed_handle.cursor().shape() is Qt.CursorShape.ArrowCursor

    temporary_rows, previews = _temporary_rows()
    panel.set_temporary_lines(temporary_rows, previews)
    QApplication.processEvents()
    assert candidate_temporary_handle.isEnabled()
    assert not temporary_confirmed_handle.isEnabled()
    assert candidate_temporary_handle.cursor().shape() is Qt.CursorShape.SplitVCursor

    panel.set_confirmed_regions(_confirmed_rows())
    QApplication.processEvents()
    assert not temporary_confirmed_handle.isEnabled()

    panel._confirmed_collapsible.set_collapsed(False)
    QApplication.processEvents()
    assert candidate_temporary_handle.isEnabled()
    assert temporary_confirmed_handle.isEnabled()
    assert temporary_confirmed_handle.cursor().shape() is Qt.CursorShape.SplitVCursor

    panel.set_temporary_lines([])
    QApplication.processEvents()
    assert not candidate_temporary_handle.isEnabled()
    assert not temporary_confirmed_handle.isEnabled()
    assert candidate_temporary_handle.cursor().shape() is Qt.CursorShape.ArrowCursor


def test_enabled_candidate_temporary_handle_resizes_both_panes(qtbot: QtBot) -> None:
    """The visible upper grip performs the resize operation it advertises."""
    panel = _show_state(
        qtbot, width=320, has_temporary=True, has_confirmed=False, has_candidates=True
    )
    handle = panel._splitter.handle(1)
    before = panel._splitter.sizes()
    center = handle.rect().center()

    qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
    qtbot.mouseMove(handle, pos=center + QPoint(0, -40))
    qtbot.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=center + QPoint(0, -40))
    QApplication.processEvents()

    after = panel._splitter.sizes()
    assert after[0] < before[0]
    assert after[1] > before[1]


@pytest.mark.parametrize("language", ["ja", "en"])
@pytest.mark.parametrize("width", [320, 420])
@pytest.mark.parametrize(
    ("has_temporary", "has_confirmed"),
    [(True, True), (False, True), (True, False), (False, False)],
)
def test_state_geometry_excludes_empty_section_controls(
    qtbot: QtBot,
    qapp: QApplication,
    language: str,
    width: int,
    has_temporary: bool,
    has_confirmed: bool,
) -> None:
    """Empty sections contribute only their compact guidance to splitter geometry."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(
            qtbot, width=width, has_temporary=has_temporary, has_confirmed=has_confirmed
        )
        temporary = panel._temporary_section
        candidate = panel._candidate_section
        confirmed = panel._confirmed_section
        confirmed_collapsible = panel._confirmed_collapsible

        candidate_margins = candidate.layout().contentsMargins()
        temporary_margins = temporary.layout().contentsMargins()
        assert (
            candidate_margins.left(),
            candidate_margins.top(),
            candidate_margins.right(),
            candidate_margins.bottom(),
        ) == (0, 0, 0, 0)
        assert (
            temporary_margins.left(),
            temporary_margins.top(),
            temporary_margins.right(),
            temporary_margins.bottom(),
        ) == (0, 0, 0, 0)
        assert (
            candidate._candidate_section_label.mapToGlobal(QPoint()).x()
            == temporary._temporary_label.mapToGlobal(QPoint()).x()
        )
        peer_headings = (
            panel._preset_section._preset_label,
            panel._preset_section._reference_label,
            candidate._candidate_section_label,
            temporary._temporary_label,
            confirmed_collapsible._header_button._title_label,
        )
        assert len({heading.mapToGlobal(QPoint()).x() for heading in peer_headings}) == 1
        header = confirmed_collapsible._header_button
        chevron = header._arrow_label
        assert header.width() == confirmed_collapsible.width()
        assert (
            chevron.mapToGlobal(chevron.rect().topRight()).x()
            == header.mapToGlobal(header.rect().topRight()).x()
        )
        assert header._title_label.geometry().right() < chevron.geometry().left()
        assert (
            candidate._candidate_section_label.styleSheet()
            == temporary._temporary_label.styleSheet()
        )
        assert temporary._temporary_label.sizeHint().width() <= temporary._temporary_label.width()
        assert panel.findChild(QWidget, "identifyCandidateFrame") is None
        assert panel.findChild(QWidget, "identifySigmaAdjustButton") is None
        assert panel.findChild(QWidget, "identifySigmaSliderContainer") is None
        for sigma_control in (
            candidate._sigma_label,
            candidate._sigma_slider,
            candidate._sigma_spin,
        ):
            assert sigma_control.isVisible()
            _assert_inside(sigma_control, candidate)
        sigma_centers = {
            control.mapTo(candidate, control.rect().center()).y()
            for control in (candidate._sigma_label, candidate._sigma_slider, candidate._sigma_spin)
        }
        assert max(sigma_centers) - min(sigma_centers) <= 1
        assert candidate._candidate_table.horizontalScrollBar().maximum() == 0
        for row in range(candidate._candidate_table.rowCount()):
            for column in range(3):
                item = candidate._candidate_table.item(row, column)
                assert item is not None
                available_width = candidate._candidate_table.visualItemRect(item).width()
                text_width = candidate._candidate_table.fontMetrics().horizontalAdvance(
                    item.text()
                )
                assert text_width + 4 <= available_width

        assert temporary._temporary_tree.isVisible() is has_temporary
        assert temporary._temporary_placeholder.isVisible() is (not has_temporary)
        assert temporary._button_bar.isVisible() is has_temporary
        assert not confirmed._groups_tree.isVisible()
        assert confirmed_collapsible._header_button.isEnabled()
        assert confirmed_collapsible.is_collapsed()

        for section in (panel._candidate_section, temporary, confirmed_collapsible):
            _assert_inside(section, panel._splitter)

        if not has_temporary:
            assert temporary.height() == temporary.maximumHeight()
            assert temporary.height() < panel._candidate_section.height()
            required_height = temporary._temporary_placeholder.heightForWidth(
                temporary._temporary_placeholder.width()
            )
            assert required_height > 0
            assert temporary._temporary_placeholder.height() >= required_height
            _assert_inside(temporary._temporary_placeholder, temporary)
        if not has_confirmed:
            assert confirmed_collapsible.height() == confirmed_collapsible.sizeHint().height()
            assert confirmed_collapsible.height() < panel._candidate_section.height()
            _assert_inside(confirmed_collapsible._summary_label, confirmed_collapsible)


@pytest.mark.parametrize("language", ["ja", "en"])
@pytest.mark.parametrize("width", [320, 420])
def test_empty_nonempty_round_trip_reapplies_layout_constraints_and_keeps_selection(
    qtbot: QtBot, qapp: QApplication, language: str, width: int
) -> None:
    """Repeated content transitions release and restore compact layout constraints."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(qtbot, width=width, has_temporary=False, has_confirmed=False)
        temporary = panel._temporary_section
        confirmed = panel._confirmed_section
        confirmed_collapsible = panel._confirmed_collapsible
        temporary_rows, previews = _temporary_rows()
        confirmed_rows = _confirmed_rows()

        assert temporary.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
        assert confirmed_collapsible.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
        assert temporary.maximumHeight() < temporary._unconstrained_maximum_height

        for _ in range(2):
            panel.set_temporary_lines(temporary_rows, previews)
            panel.set_confirmed_regions(confirmed_rows)
            QApplication.processEvents()

            assert temporary.maximumHeight() == temporary._unconstrained_maximum_height
            assert temporary.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
            assert temporary._temporary_tree.isVisible()
            assert temporary._button_bar.isVisible()
            assert not temporary._temporary_placeholder.isVisible()
            assert not confirmed._groups_tree.isVisible()
            assert not confirmed_collapsible._content.isVisible()

            _select_first_temporary_line(panel)
            panel.set_temporary_lines(temporary_rows, previews)
            selected_ids = temporary._selection_controller.selected_temporary_primary_ids(
                temporary._temporary_tree
            )
            assert selected_ids == ["temporary-1"]

            panel.set_temporary_lines([])
            panel.set_confirmed_regions([])
            QApplication.processEvents()

            temporary_layout = temporary.layout()
            assert temporary_layout is not None
            assert temporary.maximumHeight() == temporary_layout.totalHeightForWidth(
                temporary.width()
            )
            assert temporary.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
            assert (
                confirmed_collapsible.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
            )
            assert not temporary._temporary_tree.isVisible()
            assert not temporary._button_bar.isVisible()
            assert temporary._temporary_placeholder.isVisible()
            assert not confirmed._groups_tree.isVisible()
            assert not confirmed_collapsible._content.isVisible()


def test_retranslation_recomputes_compact_height_after_font_change(qtbot: QtBot) -> None:
    """Retranslation must not retain an empty-state height from older font metrics."""
    panel = _show_state(qtbot, width=320, has_temporary=False, has_confirmed=False)
    temporary = panel._temporary_section
    old_temporary_height = temporary.maximumHeight()

    larger_empty_style = empty_state_label_style(font_size="24pt")
    temporary._temporary_placeholder.setStyleSheet(larger_empty_style)
    temporary.retranslate_ui()
    QApplication.processEvents()

    temporary_layout = temporary.layout()
    assert temporary_layout is not None
    assert temporary.maximumHeight() == temporary_layout.totalHeightForWidth(temporary.width())
    assert temporary.maximumHeight() > old_temporary_height


@pytest.mark.parametrize("language", ["ja", "en"])
@pytest.mark.parametrize("width", [320, 420])
def test_all_empty_candidate_guidance_is_fully_visible(
    qtbot: QtBot, qapp: QApplication, language: str, width: int
) -> None:
    """The all-empty layout keeps the candidate heading and complete guidance visible."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(
            qtbot, width=width, has_temporary=False, has_confirmed=False, has_candidates=False
        )
        candidate = panel._candidate_section
        placeholder = candidate._candidate_placeholder

        assert candidate._candidate_section_label.isVisible()
        assert candidate._candidate_section_label.text() != ""
        assert candidate._candidate_stack.currentWidget() is candidate._candidate_placeholder_page
        assert placeholder.isVisible()
        assert placeholder.text() != ""
        assert placeholder.width() > 0
        required_height = placeholder.heightForWidth(placeholder.width())
        assert required_height > 0
        assert placeholder.height() >= required_height
        _assert_inside(candidate._candidate_section_label, candidate)
        _assert_inside(placeholder, candidate._candidate_placeholder_page)

        image = panel.grab().toImage()
        assert not image.isNull()
        assert image.width() == panel.width()
        assert image.height() == panel.height()


@pytest.mark.parametrize("language", ["ja", "en"])
@pytest.mark.parametrize("has_selection", [False, True])
def test_temporary_actions_fit_320px_with_complete_labels(
    qtbot: QtBot, qapp: QApplication, language: str, has_selection: bool
) -> None:
    """The secondary, overflow, and primary actions fit without widening the panel."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(qtbot, width=320, has_temporary=True, has_confirmed=False)
        panel.setFixedWidth(320)
        QApplication.processEvents()
        temporary = panel._temporary_section
        if has_selection:
            _select_first_temporary_line(panel)
            QApplication.processEvents()

        assert panel.width() == 320
        for button in (
            temporary._delete_button,
            temporary._more_button,
            temporary._register_button,
        ):
            assert button.width() >= button.sizeHint().width()
            _assert_inside(button, temporary._button_bar)


def test_candidate_status_display_updates_on_refresh(qtbot: QtBot) -> None:
    """The registered-state vocabulary follows ApplicationRegionStatus updates."""
    panel = IdentifySidePanel()
    qtbot.addWidget(panel)

    def candidate(status: str) -> CandidateRow:
        return CandidateRow(
            identifier="candidate-a",
            lambda_start=5000.0,
            lambda_end=5004.0,
            sigma=8.0,
            status=status,
        )

    table = panel._candidate_section._candidate_table
    for status, text in (
        ("unused", "Unassigned"),
        ("candidate", "Tentative"),
        ("identified", "Registered"),
    ):
        panel.set_candidates([candidate(status)])
        status_item = table.item(0, 2)
        assert status_item is not None
        assert status_item.text() == text
        assert status_item.toolTip() != ""


@pytest.mark.parametrize("language", ["ja", "en"])
def test_candidate_rows_are_pointer_and_keyboard_move_targets_at_320px(
    qtbot: QtBot, qapp: QApplication, language: str
) -> None:
    """The candidate row moves the spectrum by double-click or Enter, never by a single click."""
    with faithful_application_environment(qapp, language):
        panel = _show_state(qtbot, width=320, has_temporary=False, has_confirmed=False)
        panel.setFixedWidth(320)
        QApplication.processEvents()

        table = panel._candidate_section._candidate_table
        assert table.columnCount() == 3
        assert table.horizontalScrollBar().maximum() == 0

        first_item = table.item(0, 0)
        assert first_item is not None
        with qtbot.waitSignal(panel.candidate_activated, timeout=1000) as blocker:
            qtbot.mouseDClick(
                table.viewport(),
                Qt.MouseButton.LeftButton,
                pos=table.visualItemRect(first_item).center(),
            )
        assert blocker.args == ["candidate-1"]

        table.setCurrentCell(1, 0)
        table.setFocus()
        with qtbot.waitSignal(panel.candidate_activated, timeout=1000) as blocker:
            qtbot.keyClick(table, Qt.Key.Key_Return)
        assert blocker.args == ["candidate-2"]
