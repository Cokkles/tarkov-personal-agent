from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock

from tarkov_agent.domain.models import MarkerCommand, RaidRecord, TimelineEvent
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


class NoActiveRaidError(RuntimeError):
    pass


class MarkerService:
    def __init__(
        self,
        repository: RaidRepository,
        packages: RaidPackageBuilder,
        *,
        debounce_ms: int = 750,
    ) -> None:
        if debounce_ms < 0:
            raise ValueError("debounce_ms cannot be negative")
        self._repository = repository
        self._packages = packages
        self._active_raid: RaidRecord | None = None
        self._debounce_window = timedelta(milliseconds=debounce_ms)
        self._recent: dict[
            tuple[str, str, str],
            tuple[datetime, TimelineEvent],
        ] = {}
        self._lock = Lock()

    @property
    def active_raid(self) -> RaidRecord | None:
        return self._active_raid

    def activate(self, raid: RaidRecord) -> None:
        if self._active_raid is None or self._active_raid.id != raid.id:
            self._recent.clear()
        self._active_raid = raid

    def deactivate(self) -> None:
        self._active_raid = None
        self._recent.clear()

    def create(
        self,
        command: MarkerCommand,
        *,
        occurred_at: datetime | None = None,
    ) -> TimelineEvent:
        with self._lock:
            raid = self._active_raid
            if raid is None:
                raise NoActiveRaidError(
                    "A marker cannot be created without an active raid"
                )

            timestamp = occurred_at or datetime.now(UTC)
            marker_key = (
                str(raid.id),
                command.marker_type.value
                if command.marker_type is not None
                else command.label.casefold(),
                command.source.casefold(),
            )
            recent = self._recent.get(marker_key)
            if recent is not None:
                previous_at, previous_event = recent
                if timestamp - previous_at <= self._debounce_window:
                    return previous_event

            offset_ms: int | None = None
            if raid.started_at is not None:
                offset_ms = max(
                    0,
                    int((timestamp - raid.started_at).total_seconds() * 1000),
                )

            event = TimelineEvent(
                raid_id=raid.id,
                occurred_at=timestamp,
                raid_offset_ms=offset_ms,
                event_type="marker",
                label=command.label,
                source=command.source,
                confidence=1.0,
                payload={
                    "marker_type": (
                        command.marker_type.value
                        if command.marker_type is not None
                        else None
                    ),
                    "category": command.category,
                    "details": command.details,
                    "request_id": command.request_id,
                },
            )
            self._repository.add_timeline_event(event)
            self._packages.append_timeline_event(raid, event)
            self._recent[marker_key] = (timestamp, event)
            return event
