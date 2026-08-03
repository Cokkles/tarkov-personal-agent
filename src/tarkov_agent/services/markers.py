from __future__ import annotations

from datetime import UTC, datetime

from tarkov_agent.domain.models import MarkerCommand, RaidRecord, TimelineEvent
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


class NoActiveRaidError(RuntimeError):
    pass


class MarkerService:
    def __init__(self, repository: RaidRepository, packages: RaidPackageBuilder) -> None:
        self._repository = repository
        self._packages = packages
        self._active_raid: RaidRecord | None = None

    @property
    def active_raid(self) -> RaidRecord | None:
        return self._active_raid

    def activate(self, raid: RaidRecord) -> None:
        self._active_raid = raid

    def deactivate(self) -> None:
        self._active_raid = None

    def create(
        self,
        command: MarkerCommand,
        *,
        occurred_at: datetime | None = None,
    ) -> TimelineEvent:
        raid = self._active_raid
        if raid is None:
            raise NoActiveRaidError("A marker cannot be created without an active raid")

        timestamp = occurred_at or datetime.now(UTC)
        offset_ms: int | None = None
        if raid.started_at is not None:
            offset_ms = max(0, int((timestamp - raid.started_at).total_seconds() * 1000))

        event = TimelineEvent(
            raid_id=raid.id,
            occurred_at=timestamp,
            raid_offset_ms=offset_ms,
            event_type="marker",
            label=command.label,
            source="user",
            confidence=1.0,
            payload={
                "category": command.category,
                "details": command.details,
            },
        )
        self._repository.add_timeline_event(event)
        self._packages.append_timeline_event(raid, event)
        return event
