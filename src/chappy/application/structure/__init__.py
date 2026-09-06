"""Shared contracts for scientific line and region structure mutations."""

from .atomic_mutation_executor import AtomicStructureMutationExecutor, AtomicStructureProjectPort
from .impact_preview import (
    DeleteStructureRequest,
    MergeStructureRequest,
    MoveStructureRequest,
    SplitStructureRequest,
    StructureImpactOperation,
    StructureImpactPreview,
    StructureImpactPreviewUseCase,
    StructureImpactProjectPort,
    UnlinkStructureRequest,
)
from .models import (
    AtomicStructureMutationExecution,
    StructureDeleteResult,
    StructureInvalidationScope,
    StructureMergeResult,
    StructureMoveResult,
    StructureMutationOutcome,
    StructureMutationResult,
    StructureRegionDelta,
    StructureSplitResult,
    StructureUnlinkResult,
)
from .ports import StructureHistoryRecorder, StructureMoveHistoryRecorder, StructureProjectPort
from .topology import (
    StructureTopologyProjectPort,
    StructureTopologySnapshot,
    StructureTopologySnapshotService,
)
from .topology_validation import (
    StructureTopologyValidation,
    StructureTopologyValidationError,
    StructureTopologyValidator,
    StructureTopologyViolation,
    StructureTopologyViolationKind,
)

__all__ = [
    "AtomicStructureMutationExecution",
    "AtomicStructureMutationExecutor",
    "AtomicStructureProjectPort",
    "DeleteStructureRequest",
    "MergeStructureRequest",
    "MoveStructureRequest",
    "SplitStructureRequest",
    "StructureDeleteResult",
    "StructureHistoryRecorder",
    "StructureImpactOperation",
    "StructureImpactPreview",
    "StructureImpactPreviewUseCase",
    "StructureImpactProjectPort",
    "StructureInvalidationScope",
    "StructureMergeResult",
    "StructureMoveHistoryRecorder",
    "StructureMoveResult",
    "StructureMutationOutcome",
    "StructureMutationResult",
    "StructureProjectPort",
    "StructureRegionDelta",
    "StructureSplitResult",
    "StructureTopologyProjectPort",
    "StructureTopologySnapshot",
    "StructureTopologySnapshotService",
    "StructureTopologyValidation",
    "StructureTopologyValidationError",
    "StructureTopologyValidator",
    "StructureTopologyViolation",
    "StructureTopologyViolationKind",
    "StructureUnlinkResult",
    "UnlinkStructureRequest",
]
