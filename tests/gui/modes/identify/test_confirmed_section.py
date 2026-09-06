"""Tests for confirmed-region navigation in the identify side panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QMenu, QWidget

from chappy.gui.modes.identify.panel import confirmed_section as confirmed_section_module
from chappy.gui.modes.identify.panel.confirmed_section import IdentifyConfirmedRegionsSection
from chappy.gui.modes.identify.panel.panel_models import ConfirmedLineRow, ConfirmedRegionRow

if TYPE_CHECKING:
    import pytest
    from PySide6.QtCore import QPoint
    from pytestqt.qtbot import QtBot


def _confirmed_region() -> ConfirmedRegionRow:
    return ConfirmedRegionRow(
        group_id="region-1",
        label="Region 1",
        lines=[
            ConfirmedLineRow(
                line_id="line-1",
                species="C IV",
                redshift=1.292,
                lambda_start=3544.8,
                lambda_end=3546.3,
            )
        ],
        is_expanded=True,
    )


def test_summary_uses_neutral_region_context(qtbot: QtBot) -> None:
    """Collapsed context must not imply that row order represents recency."""
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.set_confirmed_regions([_confirmed_region()])

    summary = section.summary_text()
    assert summary == "1 region · Region 1 · C IV z=1.2920"
    assert "Latest" not in summary


def test_single_click_selects_without_focusing(qtbot: QtBot) -> None:
    """A single click changes selection without issuing navigation."""
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.resize(320, 300)
    section.set_confirmed_regions([_confirmed_region()])
    section.show()
    tree = section._groups_tree
    line_item = tree.topLevelItem(0).child(0)
    assert line_item is not None
    group_spy = QSignalSpy(section.group_focus_requested)
    line_spy = QSignalSpy(section.line_focus_requested)

    qtbot.mouseClick(
        tree.viewport(), Qt.MouseButton.LeftButton, pos=tree.visualItemRect(line_item).center()
    )

    assert line_item.isSelected()
    assert group_spy.count() == 0
    assert line_spy.count() == 0


def test_enter_focuses_current_group_once(qtbot: QtBot) -> None:
    """Enter moves the spectrum to the group range without requesting Analysis."""
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.resize(320, 300)
    section.set_confirmed_regions([_confirmed_region()])
    section.show()
    tree = section._groups_tree
    group_item = tree.topLevelItem(0)
    assert group_item is not None
    tree.setCurrentItem(group_item)
    tree.setFocus()
    spy = QSignalSpy(section.group_focus_requested)
    open_spy = QSignalSpy(section.region_open_requested)
    edit_spy = QSignalSpy(section.region_structure_edit_requested)

    qtbot.keyClick(tree, Qt.Key.Key_Return)

    assert spy.count() == 1
    assert spy.at(0) == ["region-1", 3544.8, 3546.3]
    assert open_spy.count() == 0
    assert edit_spy.count() == 0


def test_double_click_focuses_line_once(qtbot: QtBot) -> None:
    """Double-click moves the spectrum to the line range without requesting Analysis."""
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.resize(320, 300)
    section.set_confirmed_regions([_confirmed_region()])
    section.show()
    tree = section._groups_tree
    line_item = tree.topLevelItem(0).child(0)
    assert line_item is not None
    spy = QSignalSpy(section.line_focus_requested)
    open_spy = QSignalSpy(section.region_open_requested)
    edit_spy = QSignalSpy(section.region_structure_edit_requested)

    qtbot.mouseDClick(
        tree.viewport(), Qt.MouseButton.LeftButton, pos=tree.visualItemRect(line_item).center()
    )

    assert spy.count() == 1
    assert spy.at(0) == ["line-1", 3544.8, 3546.3]
    assert open_spy.count() == 0
    assert edit_spy.count() == 0


def _request_context_menu(
    monkeypatch: pytest.MonkeyPatch, section: IdentifyConfirmedRegionsSection, position: QPoint
) -> QMenu | None:
    """Trigger the tree context menu at one point and return the menu it built."""
    created: list[QMenu] = []

    def factory(parent: QWidget | None = None, title: str = "") -> QMenu:
        menu = QMenu(title, parent) if title else QMenu(parent)
        menu.exec = lambda *_args, **_kwargs: None
        created.append(menu)
        return menu

    monkeypatch.setattr(confirmed_section_module, "create_styled_menu", factory)
    section._groups_tree.customContextMenuRequested.emit(position)
    return created[0] if created else None


def _prepared_section(qtbot: QtBot) -> IdentifyConfirmedRegionsSection:
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.resize(320, 300)
    section.set_confirmed_regions([_confirmed_region()])
    section.show()
    return section


def test_region_row_context_menu_offers_open_and_edit(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Right-clicking a region row exposes both Analysis entry points."""
    section = _prepared_section(qtbot)
    group_item = section._groups_tree.topLevelItem(0)
    assert group_item is not None
    open_spy = QSignalSpy(section.region_open_requested)
    edit_spy = QSignalSpy(section.region_structure_edit_requested)

    menu = _request_context_menu(
        monkeypatch, section, section._groups_tree.visualItemRect(group_item).center()
    )

    assert menu is not None
    assert [action.text() for action in menu.actions()] == ["Open region", "Edit region"]
    menu.actions()[0].trigger()
    menu.actions()[1].trigger()
    assert open_spy.at(0) == ["region-1"]
    assert edit_spy.at(0) == ["region-1"]


def test_line_row_context_menu_targets_the_parent_region(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A line row offers the same items resolved against its parent region."""
    section = _prepared_section(qtbot)
    line_item = section._groups_tree.topLevelItem(0).child(0)
    assert line_item is not None
    open_spy = QSignalSpy(section.region_open_requested)
    edit_spy = QSignalSpy(section.region_structure_edit_requested)

    menu = _request_context_menu(
        monkeypatch, section, section._groups_tree.visualItemRect(line_item).center()
    )

    assert menu is not None
    assert [action.text() for action in menu.actions()] == ["Open region", "Edit region"]
    menu.actions()[0].trigger()
    menu.actions()[1].trigger()
    assert open_spy.at(0) == ["region-1"]
    assert edit_spy.at(0) == ["region-1"]


def test_context_menu_selects_the_clicked_row(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The right-clicked row becomes the selected row before the menu opens."""
    section = _prepared_section(qtbot)
    tree = section._groups_tree
    group_item = tree.topLevelItem(0)
    line_item = group_item.child(0) if group_item is not None else None
    assert group_item is not None
    assert line_item is not None
    tree.setCurrentItem(group_item)

    _request_context_menu(monkeypatch, section, tree.visualItemRect(line_item).center())

    assert line_item.isSelected()
    assert not group_item.isSelected()


def test_context_menu_ignores_empty_space(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """A right-click that resolves to no row must not build a menu."""
    section = _prepared_section(qtbot)
    tree = section._groups_tree

    menu = _request_context_menu(monkeypatch, section, tree.viewport().rect().bottomRight())

    assert menu is None


def _many_regions(count: int) -> list[ConfirmedRegionRow]:
    return [
        ConfirmedRegionRow(
            group_id=f"region-{index}",
            label=f"Region {index}",
            lines=[
                ConfirmedLineRow(
                    line_id=f"line-{index}",
                    species="Fe II",
                    redshift=0.7627,
                    lambda_start=4183.5 + index,
                    lambda_end=4204.7 + index,
                )
            ],
            is_expanded=True,
        )
        for index in range(count)
    ]


def test_reveal_regions_scrolls_a_region_below_the_fold_into_view(qtbot: QtBot) -> None:
    """A region registered while off-screen must become visible without user scrolling."""
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.resize(320, 120)
    section.set_confirmed_regions(_many_regions(12))
    section.show()
    tree = section._groups_tree
    last_group = tree.topLevelItem(11)
    assert last_group is not None
    assert not tree.viewport().rect().intersects(tree.visualItemRect(last_group))

    section.reveal_regions(["region-11"])

    assert tree.viewport().rect().intersects(tree.visualItemRect(last_group))
    assert last_group.isSelected()


def test_reveal_regions_ignores_unknown_ids(qtbot: QtBot) -> None:
    """Region ids absent from the tree must leave the current scroll position alone."""
    section = IdentifyConfirmedRegionsSection()
    qtbot.addWidget(section)
    section.resize(320, 120)
    section.set_confirmed_regions(_many_regions(12))
    section.show()
    tree = section._groups_tree
    before = tree.verticalScrollBar().value()

    section.reveal_regions(["unassigned-region"])

    assert tree.verticalScrollBar().value() == before
    assert tree.currentItem() is None
