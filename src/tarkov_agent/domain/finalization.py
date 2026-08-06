from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FinalizationStage(StrEnum):
    ACCEPTED = "accepted"
    RAID_ENDED = "raid_ended"
    STOPPING_RECORDING = "stopping_recording"
    INDEXING_MEDIA = "indexing_media"
    QUEUING_REVIEW = "queuing_review"
    READY = "ready"
    FAILED = "failed"


TERMINAL_FINALIZATION_STAGES = {
    FinalizationStage.READY,
    FinalizationStage.FAILED,
}


class FinalizationJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    raid_id: UUID
    result: str | None = None
    stage: FinalizationStage = FinalizationStage.ACCEPTED
    progress: int = Field(default=5, ge=0, le=100)
    message: str = "Raid end accepted"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None
    retryable: bool = False
    attempt: int = Field(default=1, ge=1)

    @property
    def terminal(self) -> bool:
        return self.stage in TERMINAL_FINALIZATION_STAGES
