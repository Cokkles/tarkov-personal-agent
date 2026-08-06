from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from tarkov_agent.domain.finalization import (
    TERMINAL_FINALIZATION_STAGES,
    FinalizationJob,
    FinalizationStage,
)
from tarkov_agent.services.control import ControlConflictError, ManualControlService
from tarkov_agent.services.coordinator import RaidCoordinator

LOGGER = logging.getLogger(__name__)


class FinalizationConflictError(RuntimeError):
    pass


class FinalizationNotFoundError(LookupError):
    pass


class RaidFinalizationService:
    """Runs slow OBS and media finalization outside the API request thread."""

    def __init__(
        self,
        controls: ManualControlService,
        coordinator: RaidCoordinator,
        storage_root: Path,
    ) -> None:
        self._controls = controls
        self._coordinator = coordinator
        self._storage_path = storage_root / "finalization-jobs.json"
        self._lock = threading.RLock()
        self._jobs: dict[UUID, FinalizationJob] = {}
        self._threads: dict[UUID, threading.Thread] = {}
        self._load()

    def submit(self, *, result: str | None = None) -> FinalizationJob:
        active = self._coordinator.active_raid
        if active is None:
            raise FinalizationConflictError("No active raid to end")
        with self._lock:
            existing = self._active_job_for_raid(active.id)
            if existing is not None:
                raise FinalizationConflictError(
                    f"Raid finalization is already running: {existing.id}"
                )
            job = FinalizationJob(raid_id=active.id, result=result)
            self._jobs[job.id] = job
            self._persist()
            self._start(job.id)
            return job.model_copy(deep=True)

    def retry(self, job_id: UUID | str) -> FinalizationJob:
        identifier = UUID(str(job_id))
        with self._lock:
            current = self._jobs.get(identifier)
            if current is None:
                raise FinalizationNotFoundError(f"Finalization job not found: {identifier}")
            active = self._coordinator.active_raid
            if (
                current.stage is not FinalizationStage.FAILED
                or not current.retryable
                or active is None
                or active.id != current.raid_id
            ):
                raise FinalizationConflictError(
                    "This finalization job cannot be retried in the current raid state"
                )
            now = datetime.now(UTC)
            updated = current.model_copy(
                update={
                    "stage": FinalizationStage.ACCEPTED,
                    "progress": 5,
                    "message": "Retry accepted",
                    "updated_at": now,
                    "completed_at": None,
                    "error": None,
                    "retryable": False,
                    "attempt": current.attempt + 1,
                }
            )
            self._jobs[identifier] = updated
            self._persist()
            self._start(identifier)
            return updated.model_copy(deep=True)

    def get(self, job_id: UUID | str) -> FinalizationJob:
        identifier = UUID(str(job_id))
        with self._lock:
            job = self._jobs.get(identifier)
            if job is None:
                raise FinalizationNotFoundError(f"Finalization job not found: {identifier}")
            return job.model_copy(deep=True)

    def list(self, *, limit: int = 50) -> list[FinalizationJob]:
        with self._lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda item: item.created_at,
                reverse=True,
            )[:limit]
            return [job.model_copy(deep=True) for job in jobs]

    def latest(self) -> FinalizationJob | None:
        jobs = self.list(limit=1)
        return jobs[0] if jobs else None

    def recover_interrupted(self) -> None:
        """Convert stale in-progress jobs into explicit recoverable failures."""
        with self._lock:
            active = self._coordinator.active_raid
            changed = False
            for identifier, job in tuple(self._jobs.items()):
                if job.stage in TERMINAL_FINALIZATION_STAGES:
                    continue
                retryable = active is not None and active.id == job.raid_id
                now = datetime.now(UTC)
                self._jobs[identifier] = job.model_copy(
                    update={
                        "stage": FinalizationStage.FAILED,
                        "message": "Finalization was interrupted by an application restart",
                        "updated_at": now,
                        "completed_at": now,
                        "error": "Interrupted before completion",
                        "retryable": retryable,
                    }
                )
                changed = True
            if changed:
                self._persist()

    def _start(self, job_id: UUID) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(job_id,),
            name=f"raid-finalization-{str(job_id)[:8]}",
            daemon=True,
        )
        self._threads[job_id] = thread
        thread.start()

    def _run(self, job_id: UUID) -> None:
        job = self.get(job_id)
        try:
            self._controls.end_raid(
                result=job.result,
                progress_callback=lambda stage, progress, message: self._update(
                    job_id,
                    stage=stage,
                    progress=progress,
                    message=message,
                ),
            )
        except (ControlConflictError, RuntimeError, OSError) as exc:
            active = self._coordinator.active_raid
            self._update(
                job_id,
                stage=FinalizationStage.FAILED,
                progress=max(job.progress, 5),
                message="Raid finalization failed",
                error=str(exc),
                retryable=active is not None and active.id == job.raid_id,
                completed=True,
            )
            LOGGER.exception("Raid finalization job %s failed", job_id)
        except Exception as exc:  # pragma: no cover - final safety boundary
            active = self._coordinator.active_raid
            self._update(
                job_id,
                stage=FinalizationStage.FAILED,
                progress=max(job.progress, 5),
                message="Raid finalization failed unexpectedly",
                error=str(exc),
                retryable=active is not None and active.id == job.raid_id,
                completed=True,
            )
            LOGGER.exception("Unexpected raid finalization failure for %s", job_id)
        else:
            self._update(
                job_id,
                stage=FinalizationStage.READY,
                progress=100,
                message="Raid review and evidence references are ready",
                completed=True,
            )
        finally:
            with self._lock:
                self._threads.pop(job_id, None)

    def _update(
        self,
        job_id: UUID,
        *,
        stage: FinalizationStage,
        progress: int,
        message: str,
        error: str | None = None,
        retryable: bool = False,
        completed: bool = False,
    ) -> FinalizationJob:
        with self._lock:
            current = self._jobs[job_id]
            now = datetime.now(UTC)
            updated = current.model_copy(
                update={
                    "stage": stage,
                    "progress": progress,
                    "message": message,
                    "updated_at": now,
                    "completed_at": now if completed else None,
                    "error": error,
                    "retryable": retryable,
                }
            )
            self._jobs[job_id] = updated
            self._persist()
            return updated.model_copy(deep=True)

    def _active_job_for_raid(self, raid_id: UUID) -> FinalizationJob | None:
        for job in self._jobs.values():
            if job.raid_id == raid_id and job.stage not in TERMINAL_FINALIZATION_STAGES:
                return job
        return None

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                return
            for item in payload:
                job = FinalizationJob.model_validate(item)
                self._jobs[job.id] = job
        except (OSError, ValueError, TypeError):
            LOGGER.exception("Unable to load raid finalization job history")

    def _persist(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._storage_path.with_suffix(".tmp")
            payload = [
                job.model_dump(mode="json")
                for job in sorted(self._jobs.values(), key=lambda item: item.created_at)
            ]
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(self._storage_path)
        except OSError:
            LOGGER.exception("Unable to persist raid finalization job history")
