from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tarkov_agent.domain.models import RaidRecord, TimelineEvent


class Base(DeclarativeBase):
    pass


class RaidRow(Base):
    __tablename__ = "raids"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    game: Mapped[str] = mapped_column(String(20), index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document_json: Mapped[str] = mapped_column(Text)


class TimelineEventRow(Base):
    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    raid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raids.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(200))
    document_json: Mapped[str] = mapped_column(Text)


class RaidRepository:
    """SQLite-backed document repository with indexed raid and timeline fields."""

    def __init__(self, database_path: Path | str) -> None:
        path = Path(database_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite+pysqlite:///{path.as_posix()}", future=True)

    def initialize(self) -> None:
        Base.metadata.create_all(self._engine)

    def save_raid(self, raid: RaidRecord) -> None:
        now = datetime.now(UTC)
        with Session(self._engine) as session:
            row = session.get(RaidRow, str(raid.id))
            if row is None:
                row = RaidRow(
                    id=str(raid.id),
                    game=raid.game.value,
                    state=raid.state.value,
                    created_at=raid.created_at,
                    updated_at=now,
                    document_json=raid.model_dump_json(),
                )
                session.add(row)
            else:
                row.game = raid.game.value
                row.state = raid.state.value
                row.updated_at = now
                row.document_json = raid.model_dump_json()
            session.commit()

    def get_raid(self, raid_id: UUID | str) -> RaidRecord | None:
        with Session(self._engine) as session:
            row = session.get(RaidRow, str(raid_id))
            if row is None:
                return None
            return RaidRecord.model_validate_json(row.document_json)

    def list_raids(self, limit: int = 100) -> list[RaidRecord]:
        statement = select(RaidRow).order_by(RaidRow.created_at.desc()).limit(limit)
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [RaidRecord.model_validate_json(row.document_json) for row in rows]

    def add_timeline_event(self, event: TimelineEvent) -> None:
        with Session(self._engine) as session:
            session.merge(
                TimelineEventRow(
                    id=str(event.id),
                    raid_id=str(event.raid_id),
                    occurred_at=event.occurred_at,
                    event_type=event.event_type,
                    label=event.label,
                    document_json=event.model_dump_json(),
                )
            )
            session.commit()

    def list_timeline_events(self, raid_id: UUID | str) -> list[TimelineEvent]:
        statement = (
            select(TimelineEventRow)
            .where(TimelineEventRow.raid_id == str(raid_id))
            .order_by(TimelineEventRow.occurred_at.asc())
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [TimelineEvent.model_validate_json(row.document_json) for row in rows]
