from datetime import UTC, datetime, timedelta
from pathlib import Path

from tarkov_agent.domain.models import (
    MarkerCommand,
    MarkerType,
    RaidRecord,
    RaidState,
    TimelineEvent,
)
from tarkov_agent.services.markers import MarkerService


class _Repository:
    def __init__(self) -> None:
        self.events: list[TimelineEvent] = []

    def add_timeline_event(self, event: TimelineEvent) -> None:
        self.events.append(event)


class _Packages:
    def __init__(self) -> None:
        self.events: list[TimelineEvent] = []

    def append_timeline_event(
        self,
        _raid: RaidRecord,
        event: TimelineEvent,
    ) -> None:
        self.events.append(event)


def _active_raid(root: Path, started_at: datetime) -> RaidRecord:
    return RaidRecord(
        state=RaidState.IN_RAID,
        started_at=started_at,
        data_root=root,
    )


def test_structured_marker_uses_canonical_defaults(tmp_path: Path) -> None:
    started_at = datetime(2026, 8, 6, 1, 0, tzinfo=UTC)
    repository = _Repository()
    packages = _Packages()
    service = MarkerService(repository, packages)
    service.activate(_active_raid(tmp_path, started_at))

    event = service.create(
        MarkerCommand(
            marker_type=MarkerType.PMC_HEARD,
            source="stream_deck",
            request_id="press-1",
        ),
        occurred_at=started_at + timedelta(seconds=12),
    )

    assert event.label == "PMC Heard"
    assert event.source == "stream_deck"
    assert event.raid_offset_ms == 12_000
    assert event.payload["marker_type"] == MarkerType.PMC_HEARD.value
    assert event.payload["category"] == "audio"
    assert event.payload["request_id"] == "press-1"
    assert repository.events == [event]
    assert packages.events == [event]


def test_duplicate_marker_press_is_suppressed(tmp_path: Path) -> None:
    started_at = datetime(2026, 8, 6, 1, 0, tzinfo=UTC)
    repository = _Repository()
    packages = _Packages()
    service = MarkerService(repository, packages, debounce_ms=750)
    service.activate(_active_raid(tmp_path, started_at))
    command = MarkerCommand(
        marker_type=MarkerType.IMPORTANT_LOOT,
        source="stream_deck",
    )

    first = service.create(command, occurred_at=started_at + timedelta(seconds=5))
    duplicate = service.create(
        command,
        occurred_at=started_at + timedelta(seconds=5, milliseconds=200),
    )
    later = service.create(command, occurred_at=started_at + timedelta(seconds=6))

    assert duplicate.id == first.id
    assert later.id != first.id
    assert len(repository.events) == 2
    assert len(packages.events) == 2


def test_legacy_custom_marker_remains_supported(tmp_path: Path) -> None:
    started_at = datetime(2026, 8, 6, 1, 0, tzinfo=UTC)
    repository = _Repository()
    packages = _Packages()
    service = MarkerService(repository, packages)
    service.activate(_active_raid(tmp_path, started_at))

    event = service.create(
        MarkerCommand(label="Custom Note", category="note"),
        occurred_at=started_at,
    )

    assert event.label == "Custom Note"
    assert event.source == "user"
    assert event.payload["marker_type"] is None


def test_client_supplied_time_and_confidence_are_used(tmp_path: Path) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=120)
    repository = _Repository()
    service = MarkerService(repository, _Packages())
    service.activate(_active_raid(tmp_path, started_at))
    spoken_at = started_at + timedelta(seconds=42.5)

    event = service.create(
        MarkerCommand(
            marker_type=MarkerType.PLAYER_SEEN,
            source="voice",
            occurred_at=spoken_at,
            confidence=0.8,
        )
    )

    assert event.raid_offset_ms == 42500
    assert event.occurred_at == spoken_at
    assert event.confidence == 0.8


def test_client_supplied_time_cannot_be_in_the_future(tmp_path: Path) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=30)
    service = MarkerService(_Repository(), _Packages())
    service.activate(_active_raid(tmp_path, started_at))

    event = service.create(
        MarkerCommand(
            marker_type=MarkerType.MISTAKE,
            occurred_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )

    assert event.raid_offset_ms is not None
    assert event.raid_offset_ms < 60_000


def test_naive_client_time_is_treated_as_utc() -> None:
    command = MarkerCommand(
        marker_type=MarkerType.MISTAKE,
        occurred_at=datetime(2026, 8, 6, 1, 0, 0),
    )
    assert command.occurred_at == datetime(2026, 8, 6, 1, 0, 0, tzinfo=UTC)


def test_different_callouts_of_same_type_are_not_debounced_together(
    tmp_path: Path,
) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=30)
    repository = _Repository()
    service = MarkerService(repository, _Packages(), debounce_ms=750)
    service.activate(_active_raid(tmp_path, started_at))
    when = started_at + timedelta(seconds=10)

    first = service.create(
        MarkerCommand(
            marker_type=MarkerType.IMPORTANT_LOOT,
            source="voice",
            details="Found: keycard",
            occurred_at=when,
        )
    )
    second = service.create(
        MarkerCommand(
            marker_type=MarkerType.IMPORTANT_LOOT,
            source="voice",
            details="Found: graphics card",
            occurred_at=when + timedelta(milliseconds=200),
        )
    )

    assert first.id != second.id
    assert len(repository.events) == 2
