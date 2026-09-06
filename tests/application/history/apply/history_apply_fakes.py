"""Shared Qt-free fakes for HistoryApplyUseCase tests.

Every ``test_*_apply.py`` file in this directory builds a real
``CommandHistory`` wired to a real ``HistoryApplyUseCase`` registered through
``CommandHistory.set_applier``, then drives undo/redo directly. These fakes
stand in for the GUI-owned ``HistoryRefreshPort`` and ``RangeHistoryPort``
adapters so no PySide6 import is required anywhere under this directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from chappy.application.history import ChangeSet
from chappy.application.history.apply.usecase import HistoryApplyUseCase

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.application.history import HistoryApplyError, HistoryRefreshTarget, RangeSnapshot
    from chappy.application.spectrum import ResolutionChangeNotifier
    from chappy.core.spectroscopy_project import SpectroscopyProject


@dataclass(slots=True)
class FakeHistoryRefreshPort:
    """Records every dispatched GUI refresh target, optionally failing some."""

    fail_targets: frozenset[HistoryRefreshTarget] = frozenset()
    calls: list[tuple[HistoryRefreshTarget, ChangeSet]] = field(default_factory=list)

    def refresh(self, target: HistoryRefreshTarget, change_set: ChangeSet) -> None:
        """Record one refresh dispatch and optionally raise for the target."""
        self.calls.append((target, change_set))
        if target in self.fail_targets:
            msg = f"injected refresh failure: {target}"
            raise RuntimeError(msg)

    def targets(self) -> tuple[HistoryRefreshTarget, ...]:
        """Return every dispatched target in call order."""
        return tuple(target for target, _ in self.calls)

    def region_ids_for(self, target: HistoryRefreshTarget) -> list[str | None]:
        """Return the leading changed region id recorded for each call to ``target``.

        Mirrors ``HistoryBridgeRefreshPort.refresh``, which always derives its
        dock region-id argument as ``change_set.changed_region_ids[0]`` (or
        ``None``).
        """
        return [
            (change_set.changed_region_ids[0] if change_set.changed_region_ids else None)
            for recorded_target, change_set in self.calls
            if recorded_target is target
        ]


@dataclass(slots=True)
class FakeRangeHistoryPort:
    """Range history port test double that can be armed to fail."""

    calls: list[tuple[RangeSnapshot, Literal["history"]]] = field(default_factory=list)
    error: HistoryApplyError | None = None

    def apply_range(self, snapshot: RangeSnapshot, *, source: Literal["history"]) -> ChangeSet:
        """Record the applied snapshot, or raise the armed error."""
        self.calls.append((snapshot, source))
        if self.error is not None:
            raise self.error
        return ChangeSet.empty()


def build_usecase(
    *,
    project_provider: Callable[[], SpectroscopyProject | None],
    refresh_port: FakeHistoryRefreshPort | None = None,
    range_port: FakeRangeHistoryPort | None = None,
    resolution_notifier_provider: Callable[[], ResolutionChangeNotifier | None] = lambda: None,
) -> HistoryApplyUseCase:
    """Build one Qt-free ``HistoryApplyUseCase`` wired to fake GUI ports."""
    return HistoryApplyUseCase(
        project_provider=project_provider,
        range_port=range_port if range_port is not None else FakeRangeHistoryPort(),
        refresh_port=refresh_port if refresh_port is not None else FakeHistoryRefreshPort(),
        resolution_notifier_provider=resolution_notifier_provider,
    )
