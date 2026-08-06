from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tarkov_agent.config import AppSettings
from tarkov_agent.domain.finalization import FinalizationStage
from tarkov_agent.domain.models import (
    EvidenceKind,
    MarkerCommand,
    RaidRecord,
    RaidState,
    TimelineEvent,
)
from tarkov_agent.domain.state_machine import InvalidTransition, RaidSignal
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


class ControlConflictError(RuntimeError):
    pass


class EvidencePathError(ValueError):
    pass


FinalizationProgressCallback = Callable[[FinalizationStage, int, str], None]


@dataclass(frozen=True, slots=True)
class EvidenceAttachment:
    raid: RaidRecord
    evidence_id: str


class ManualControlService:
    def __init__(
        self,
        settings: AppSettings,
        coordinator: RaidCoordinator,
        markers: MarkerService,
        repository: RaidRepository,
        packages: RaidPackageBuilder,
    ) -> None:
        self._settings = settings
        self._coordinator = coordinator
        self._markers = markers
        self._repository = repository
        self._packages = packages

    def start_raid(self, payload: dict[str, Any]) -> RaidRecord:
        if self._coordinator.active_raid is not None:
            raise ControlConflictError("A raid is already active")
        state = self._coordinator.lifecycle.state
        if state is RaidState.IDLE:
            self._coordinator.handle_signal(
                RaidSignal.GAME_FOUND,
                reason="Manual control initialized game-running state",
            )
        elif state in {RaidState.COMPLETE, RaidState.ABORTED, RaidState.REVIEW_PENDING}:
            self._coordinator.handle_signal(
                RaidSignal.RESET,
                reason="Manual control reset lifecycle before raid start",
            )
        if not self._coordinator.lifecycle.can_apply(RaidSignal.RAID_STARTED):
            raise ControlConflictError(
                f"Cannot manually start a raid from {self._coordinator.lifecycle.state.value}"
            )
        try:
            self._coordinator.handle_signal(
                RaidSignal.RAID_STARTED,
                reason="Manual raid start",
                payload=payload,
            )
        except InvalidTransition as exc:
            raise ControlConflictError(str(exc)) from exc
        raid = self._coordinator.active_raid
        if raid is None:
            raise ControlConflictError("Raid start did not create an active record")
        return raid

    def end_raid(
        self,
        *,
        result: str | None = None,
        progress_callback: FinalizationProgressCallback | None = None,
    ) -> RaidRecord:
        active = self._coordinator.active_raid
        if active is None:
            raise ControlConflictError("No active raid to end")
        if not self._coordinator.lifecycle.can_apply(RaidSignal.RAID_ENDED):
            raise ControlConflictError(
                f"Cannot end a raid from {self._coordinator.lifecycle.state.value}"
            )
        raid_id = active.id
        self._coordinator.handle_signal(
            RaidSignal.RAID_ENDED,
            reason="Manual raid end",
            payload={"result": result},
            progress_callback=progress_callback,
        )
        raid = self._repository.get_raid(raid_id)
        if raid is None:
            raise ControlConflictError("Ended raid could not be reloaded")
        return raid

    def abort_raid(self, *, reason: str | None = None) -> RaidRecord:
        active = self._coordinator.active_raid
        if active is None:
            raise ControlConflictError("No active raid to abort")
        raid_id = active.id
        if not self._coordinator.lifecycle.can_apply(RaidSignal.ABORT):
            raise ControlConflictError(
                f"Cannot abort a raid from {self._coordinator.lifecycle.state.value}"
            )
        self._coordinator.handle_signal(
            RaidSignal.ABORT,
            reason=reason or "Manual raid abort",
        )
        raid = self._repository.get_raid(raid_id)
        if raid is None:
            raise ControlConflictError("Aborted raid could not be reloaded")
        return raid

    def marker(self, command: MarkerCommand) -> TimelineEvent:
        return self._markers.create(command)

    def attach_evidence(
        self,
        raid_id: str,
        source: Path | str,
        kind: EvidenceKind,
        *,
        copy_into_package: bool,
    ) -> EvidenceAttachment:
        raid = self._repository.get_raid(raid_id)
        if raid is None:
            raise LookupError(f"Raid not found: {raid_id}")
        source_path = Path(source).expanduser().resolve()
        self._validate_evidence_path(source_path)
        updated, evidence = self._packages.attach_file(
            raid,
            source_path,
            kind,
            copy_into_package=copy_into_package,
            metadata={
                "source": "manual-reference",
                "attached_at": datetime.now(UTC).isoformat(),
            },
        )
        self._repository.save_raid(updated)
        return EvidenceAttachment(updated, str(evidence.id))

    def _validate_evidence_path(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise EvidencePathError(f"Evidence file does not exist: {path}")
        roots = [self._settings.paths.data_root, *self._settings.api.allowed_evidence_roots]
        for root in roots:
            try:
                path.relative_to(root)
                return
            except ValueError:
                continue
        raise EvidencePathError(
            "Evidence path is outside data_root and api.allowed_evidence_roots"
        )
