"""Undo/redo application use case: dispatch typed history commands and publish commits."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from chappy.application.analysis_artifacts import run_postcommit_actions_isolated
from chappy.application.history import (
    ContinuumAddComponentCommand,
    ContinuumAddPointCommand,
    ContinuumDeletePointCommand,
    ContinuumMovePointCommand,
    ContinuumResetCommand,
    HistoryApplyError,
    HistoryApplyErrorCode,
    HistoryCommand,
    HistoryCommandContext,
    IdentifyRegisterSelectedCommand,
    LineAnalysisHalfWidthHistoryCommand,
    MaskHistoryCommand,
    ModelComponentHistoryCommand,
    ModelOptimizeApplyCommand,
    ModelParameterEditCommand,
    ResolutionHistoryCommand,
    ScientificHistoryApplyExecutor,
    StructureDeleteCommand,
    StructureMergeCommand,
    StructureMoveLinkedLinesCommand,
    StructureSplitCommand,
    StructureUnlinkLinkedLinesCommand,
    TieSetEditCommand,
)
from chappy.application.history.apply.continuum_apply import ContinuumApply
from chappy.application.history.apply.identify_apply import IdentifyApply
from chappy.application.history.apply.mask_apply import MaskApply
from chappy.application.history.apply.model_apply import ModelApply
from chappy.application.history.apply.project_appliers import (
    ProjectContinuumHistoryApplier,
    ProjectIdentifyHistoryApplier,
    ProjectModelHistoryApplier,
    ProjectResolutionHistoryApplier,
    ProjectStructureHistoryApplier,
)
from chappy.application.history.apply.resolution_apply import ResolutionApply
from chappy.application.history.apply.structure_apply import StructureApply
from chappy.application.history.apply.tie_set_apply import TieSetApply
from chappy.application.optimize.model_topology_usecase import AbsorberModelTopologyUseCase
from chappy.application.structure import (
    AtomicStructureMutationExecutor,
    StructureTopologySnapshotService,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.application.history import (
        ChangeSet,
        HistoryApplyResult,
        HistoryRefreshTarget,
        RangeHistoryPort,
        ScientificHistoryApplyExecution,
    )
    from chappy.application.spectrum import ResolutionChangeNotifier
    from chappy.core.change_set import ChangeSet as DomainChangeSet
    from chappy.core.history import HistoryEvent
    from chappy.core.identify_state import IdentifySessionState
    from chappy.core.spectroscopy_project import SpectroscopyProject


class HistoryRefreshPort(Protocol):
    """Port for dispatching one GUI refresh after a committed history transition."""

    def refresh(self, target: HistoryRefreshTarget, change_set: ChangeSet) -> None:
        """Refresh the GUI surface associated with one refresh target."""
        ...


class HistoryApplyUseCase:
    """Apply typed undo/redo history events against the active project.

    Implements the ``HistoryApplier`` protocol expected by ``CommandHistory.set_applier``.
    """

    def __init__(
        self,
        project_provider: Callable[[], SpectroscopyProject | None],
        range_port: RangeHistoryPort,
        refresh_port: HistoryRefreshPort,
        resolution_notifier_provider: Callable[[], ResolutionChangeNotifier | None],
    ) -> None:
        """Initialize with GUI-injected ports and build the application pipeline."""
        self._project_provider = project_provider
        self._range_port = range_port
        self._refresh_port = refresh_port
        self._resolution_notifier_provider = resolution_notifier_provider

        self._scientific_executor = ScientificHistoryApplyExecutor()
        self._structure_executor = AtomicStructureMutationExecutor()
        structure_topology = StructureTopologySnapshotService()
        absorber_topology = AbsorberModelTopologyUseCase()

        self._model_applier = ProjectModelHistoryApplier(project_provider)
        self._structure_applier = ProjectStructureHistoryApplier(project_provider)
        self._identify_applier = ProjectIdentifyHistoryApplier(project_provider)
        self._continuum_applier = ProjectContinuumHistoryApplier(project_provider)
        self._resolution_applier = ProjectResolutionHistoryApplier(project_provider)

        self._model_apply = ModelApply(self._scientific_executor, absorber_topology)
        self._tie_set_apply = TieSetApply(self._scientific_executor, absorber_topology)
        self._continuum_apply = ContinuumApply(self._scientific_executor, self._continuum_applier)
        self._mask_apply = MaskApply(self._scientific_executor)
        self._resolution_apply = ResolutionApply(self._scientific_executor)
        self._structure_apply = StructureApply(self._structure_executor, structure_topology)
        self._identify_apply = IdentifyApply(self._structure_executor, structure_topology)

    def apply_history_event(  # noqa: PLR0911 - one typed branch per command family
        self, event: HistoryEvent, *, is_undo: bool
    ) -> bool:
        """Apply a history event.

        This method is called by CommandHistory during undo/redo operations.
        It dispatches to appropriate handlers based on operation_id.

        Args:
            event: The history event to apply.
            is_undo: True for undo, False for redo.

        Returns:
            True if applied successfully, False on failure.
        """
        context = self._create_command_context()
        command = event.command
        if not isinstance(command, HistoryCommand):
            msg = "HistoryApplyUseCase requires an application history command."
            raise TypeError(msg)

        if isinstance(command, ModelComponentHistoryCommand):
            project = self._require_project("apply model component history")
            execution = self._model_apply.apply_component(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(command, TieSetEditCommand):
            project = self._require_project("apply tie set history")
            execution = self._tie_set_apply.apply(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(
            command,
            (
                ContinuumAddComponentCommand,
                ContinuumAddPointCommand,
                ContinuumDeletePointCommand,
                ContinuumMovePointCommand,
                ContinuumResetCommand,
            ),
        ):
            project = self._require_project("apply continuum history")
            execution = self._continuum_apply.apply(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(command, ModelParameterEditCommand):
            project = self._require_project("apply model parameter history")
            execution = self._model_apply.apply_parameter(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(command, ResolutionHistoryCommand):
            project = self._require_project("apply spectral resolution history")
            execution = self._resolution_apply.apply(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            if execution.impact.changed:
                run_postcommit_actions_isolated(self._notify_resolution_changed)
            return execution.result.success
        if isinstance(command, ModelOptimizeApplyCommand):
            project = self._require_project("apply model optimize history")
            execution = self._model_apply.apply_optimize(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(command, LineAnalysisHalfWidthHistoryCommand):
            project = self._require_project("apply line analysis half-width history")
            execution = self._model_apply.apply_line_analysis_half_width(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(command, MaskHistoryCommand):
            project = self._require_project("apply mask history")
            execution = self._mask_apply.apply(project, command, context=context, is_undo=is_undo)
            self._publish_scientific_commit(project, execution)
            return execution.result.success
        if isinstance(command, IdentifyRegisterSelectedCommand):
            project = self._require_project("apply identify registration history")
            session = self._require_identify_session("apply identify registration history")
            result, domain_changes = self._identify_apply.apply(
                project, session, command, context=context, is_undo=is_undo
            )
            self._publish_commit(project, result, domain_changes)
            return result.success
        if isinstance(command, StructureMoveLinkedLinesCommand):
            project = self._require_project("apply structure move history")
            result, domain_changes = self._structure_apply.apply_move(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_commit(project, result, domain_changes)
            return result.success
        if isinstance(
            command, (StructureSplitCommand, StructureMergeCommand, StructureDeleteCommand)
        ):
            project = self._require_project("apply structure structure history")
            result, domain_changes = self._structure_apply.apply_structure(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_commit(project, result, domain_changes)
            return result.success
        if isinstance(command, StructureUnlinkLinkedLinesCommand):
            project = self._require_project("apply structure unlink history")
            result, domain_changes = self._structure_apply.apply_unlink(
                project, command, context=context, is_undo=is_undo
            )
            self._publish_commit(project, result, domain_changes)
            return result.success

        result = command.undo(context) if is_undo else command.redo(context)
        self._ensure_success(result)
        self._publish_refresh(result)
        return result.success

    def _create_command_context(self) -> HistoryCommandContext:
        """Create command context for typed history application."""
        return HistoryCommandContext(
            range_port=self._range_port,
            model_port=self._model_applier,
            structure_port=self._structure_applier,
            identify_port=self._identify_applier,
            continuum_port=self._continuum_applier,
            resolution_port=self._resolution_applier,
        )

    def _require_project(self, action: str) -> SpectroscopyProject:
        """Return the current project or raise a typed history error."""
        project = self._project_provider()
        if project is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"{HistoryApplyErrorCode.TARGET_NOT_FOUND}: "
                f"Cannot {action} without a connected project.",
            )
        return project

    def _require_identify_session(self, action: str) -> IdentifySessionState:
        """Return the current identify session or raise a typed history error."""
        session = self._require_project(action).identify_state
        if session is None:
            raise HistoryApplyError(
                HistoryApplyErrorCode.TARGET_NOT_FOUND,
                f"Cannot {action} without a connected identify session.",
            )
        return session

    def _notify_resolution_changed(self) -> None:
        """Notify the active resolution consumer after a successful history commit."""
        notifier = self._resolution_notifier_provider()
        if notifier is not None:
            notifier.notify_resolution_changed()

    def _publish_scientific_commit(
        self, project: SpectroscopyProject, execution: ScientificHistoryApplyExecution
    ) -> None:
        """Publish domain and GUI observers after science has irreversibly committed."""
        if not execution.impact.changed:
            return
        self._publish_commit(project, execution.result, execution.domain_changes)

    def _publish_commit(
        self,
        project: SpectroscopyProject,
        result: HistoryApplyResult,
        domain_changes: DomainChangeSet,
    ) -> None:
        """Publish one committed structure or science transition, isolating each observer."""
        actions: list[Callable[[], object]] = []
        if domain_changes:
            actions.append(lambda: project.model.publish_storage_changes(domain_changes))
        for target in dict.fromkeys(result.refresh_targets):

            def refresh_action(target: HistoryRefreshTarget = target) -> None:
                self._refresh_port.refresh(target, result.change_set)

            actions.append(refresh_action)
        run_postcommit_actions_isolated(*actions)

    def _publish_refresh(self, result: HistoryApplyResult) -> None:
        """Publish GUI refresh observers for one already-committed generic command."""
        actions: list[Callable[[], object]] = []
        for target in dict.fromkeys(result.refresh_targets):

            def refresh_action(target: HistoryRefreshTarget = target) -> None:
                self._refresh_port.refresh(target, result.change_set)

            actions.append(refresh_action)
        run_postcommit_actions_isolated(*actions)

    @staticmethod
    def _ensure_success(result: HistoryApplyResult) -> None:
        """Raise before any commit is published if the typed command failed."""
        if not result.success:
            error_code = result.error_code or HistoryApplyErrorCode.INVALID_STATE
            raise HistoryApplyError(error_code, f"Typed history command failed: {error_code}")


__all__ = ["HistoryApplyUseCase", "HistoryRefreshPort"]
