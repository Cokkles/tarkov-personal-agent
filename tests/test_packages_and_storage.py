from datetime import UTC, datetime
from pathlib import Path

from tarkov_agent.domain.models import EvidenceKind, Game, RaidRecord, RaidState, TimelineEvent
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


def test_package_builder_and_repository_round_trip(tmp_path: Path) -> None:
    packages = RaidPackageBuilder(tmp_path / "raids")
    raid = RaidRecord(
        game=Game.TARKOV,
        state=RaidState.IN_RAID,
        started_at=datetime.now(UTC),
        map_name="Interchange",
        data_root=tmp_path,
    )
    raid = packages.create(raid)

    evidence_source = tmp_path / "sample.log"
    evidence_source.write_text("sample", encoding="utf-8")
    raid, evidence = packages.attach_file(
        raid,
        evidence_source,
        EvidenceKind.LOG,
        copy_into_package=True,
    )

    repository = RaidRepository(tmp_path / "agent.sqlite3")
    repository.initialize()
    repository.save_raid(raid)

    event = TimelineEvent(
        raid_id=raid.id,
        occurred_at=datetime.now(UTC),
        event_type="marker",
        label="Possible PMC",
        source="user",
    )
    repository.add_timeline_event(event)
    packages.append_timeline_event(raid, event)

    restored = repository.get_raid(raid.id)
    timeline = repository.list_timeline_events(raid.id)

    assert restored is not None
    assert restored.map_name == "Interchange"
    assert restored.evidence[0].sha256 == evidence.sha256
    assert evidence.path.parent.name == "logs"
    assert timeline == [event]
    assert (raid.data_root / "raid.json").exists()
    assert (raid.data_root / "timeline.jsonl").read_text(encoding="utf-8").strip()
