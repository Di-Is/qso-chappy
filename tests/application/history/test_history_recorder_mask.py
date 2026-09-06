"""Tests for user-visible mask history recording."""

from __future__ import annotations

import pytest

from chappy.application.history import HistoryRecorder, MaskDefinitionSnapshot
from chappy.application.optimize import MaskMutationKind
from chappy.core.history import CommandHistory, OperationId


def _snapshot(group_id: str) -> MaskDefinitionSnapshot:
    return MaskDefinitionSnapshot(
        identifier="mask-1",
        label="Mask 1",
        mode="range",
        start_wavelength=100.0,
        end_wavelength=110.0,
        center=105.0,
        half_width=5.0,
        note="",
        color="#abcdef",
        enabled=True,
        group_id=group_id,
    )


@pytest.mark.parametrize(
    ("kind", "before", "after", "affected_region_ids", "operation_id"),
    [
        (
            MaskMutationKind.CREATE,
            None,
            _snapshot("region-1"),
            ("region-1", "region-1"),
            OperationId.MASK_CREATE,
        ),
        (
            MaskMutationKind.UPDATE,
            _snapshot("region-1"),
            _snapshot("region-2"),
            ("region-1", "region-2", "region-1"),
            OperationId.MASK_EDIT,
        ),
        (
            MaskMutationKind.REMOVE,
            _snapshot("region-1"),
            None,
            ("region-1", "region-1"),
            OperationId.MASK_DELETE,
        ),
    ],
)
def test_recorder_uses_distinct_mask_operation_ids(
    kind: MaskMutationKind,
    before: MaskDefinitionSnapshot | None,
    after: MaskDefinitionSnapshot | None,
    affected_region_ids: tuple[str, ...],
    operation_id: OperationId,
) -> None:
    """Create, edit, and delete remain distinguishable in Undo labels."""
    history = CommandHistory()
    recorder = HistoryRecorder(history, lambda: None)

    recorder.record_mask_mutation(
        kind=kind,
        mask_id="mask-1",
        before=before,
        after=after,
        before_index=None if before is None else 0,
        after_index=None if after is None else 0,
        affected_region_ids=affected_region_ids,
    )

    state = history.get_state()
    assert state.undo_count == 1
    assert state.next_undo_operation_id == operation_id.value
