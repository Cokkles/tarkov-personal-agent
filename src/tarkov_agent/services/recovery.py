from __future__ import annotations

from datetime import UTC, datetime

from tarkov_agent.domain.models import RaidRecord, RaidState, TimelineEvent
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


class RecoveryService:
    """Repairs interrupted local state without inventing a raid outcome."""

    _UNFINISHED_STATES = {
        RaidState.MATCHMAKING,
        RaidState.RAID_CANDIDATE,
        RaidState.IN_RAID,
        RaidState.ENDING,
        RaidState.REVIEW_PENDING,
    }

    def __init__(self, repository: RaidRepository, packages: RaidPackageBuilder) -> None:
        self._repository = repository
        self._packages = packages

    def pending(self, limit: int = 100) -> list[RaidRecord]:
        candidates = self._repository.list_raids_by_states(
            {RaidState.ENDING, RaidState.REVIEW_PENDING, RaidState.ABORTED},
            limit=limit,
        )
        pending: list[RaidRecord] = []
        for raid in candidates:
            review = self._repository.get_review(raid.id)
            if review is not None and review.status.value == "finalized":
                continue
            pending.append(raid)
        return pending

    def recover(self, *, game_running: bool) -> RaidRecord | None:
        candidates = self._repository.list_raids_by_states(self._UNFINISHED_STATES, limit=10)
        if not candidates:
            return None
        latest = candidates[0]
        if latest.state is RaidState.IN_RAID and game_running:
            return latest

        now = datetime.now(UTC)
        if latest.state in {RaidState.MATCHMAKING, RaidState.RAID_CANDIDATE}:
            updated = latest.model_copy(
                update={"state": RaidState.ABORTED, "ended_at": latest.ended_at or now}
            )
            label = "Interrupted pre-raid session recovered as aborted"
        elif latest.state in {RaidState.IN_RAID, RaidState.ENDING}:
            updated = latest.model_copy(
                update={"state": RaidState.REVIEW_PENDING, "ended_at": latest.ended_at or now}
            )
            label = "Interrupted raid recovered for manual review"
        else:
            return latest

        self._repository.save_raid(updated)
        event = TimelineEvent(
            raid_id=updated.id,
            occurred_at=now,
            raid_offset_ms=self._offset_ms(updated, now),
            event_type="recovery",
            label=label,
            source="system",
            payload={
                "previous_state": latest.state.value,
                "recovered_state": updated.state.value,
                "game_running": game_running,
            },
        )
        self._repository.add_timeline_event(event)
        if self._has_package(updated):
            self._packages.append_timeline_event(updated, event)
            self._packages.write_manifest(updated)
        return updated

    @staticmethod
    def _offset_ms(raid: RaidRecord, timestamp: datetime) -> int | None:
        if raid.started_at is None:
            return None
        return max(0, int((timestamp - raid.started_at).total_seconds() * 1000))

    @staticmethod
    def _has_package(raid: RaidRecord) -> bool:
        return (raid.data_root / "raid.json").exists()
