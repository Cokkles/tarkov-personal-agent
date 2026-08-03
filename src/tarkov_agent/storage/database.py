from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tarkov_agent.domain.models import RaidRecord, RaidState, TimelineEvent
from tarkov_agent.domain.ppe import PPEEvidence, ProfileAuditEntry, ProfileSnapshot
from tarkov_agent.domain.reviews import RaidReview, ReviewAuditEntry


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


class RaidReviewRow(Base):
    __tablename__ = "raid_reviews"

    raid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raids.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class ReviewAuditRow(Base):
    __tablename__ = "review_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    raid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raids.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class PPEEvidenceRow(Base):
    __tablename__ = "ppe_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    raid_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("raids.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(60), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class ProfileSnapshotRow(Base):
    __tablename__ = "ppe_profile_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evidence_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class ProfileAuditRow(Base):
    __tablename__ = "ppe_profile_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ppe_profile_snapshots.id", ondelete="CASCADE"),
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    trigger: Mapped[str] = mapped_column(String(240), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class RaidRepository:
    """SQLite-backed document repository with indexed query fields."""

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

    def list_raids_by_states(
        self,
        states: set[RaidState],
        *,
        limit: int = 100,
    ) -> list[RaidRecord]:
        if not states:
            return []
        statement = (
            select(RaidRow)
            .where(RaidRow.state.in_([state.value for state in states]))
            .order_by(RaidRow.created_at.desc())
            .limit(limit)
        )
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

    def save_review(self, review: RaidReview) -> None:
        with Session(self._engine) as session:
            row = session.get(RaidReviewRow, str(review.raid_id))
            if row is None:
                row = RaidReviewRow(
                    raid_id=str(review.raid_id),
                    version=review.version,
                    status=review.status.value,
                    updated_at=review.updated_at,
                    document_json=review.model_dump_json(),
                )
                session.add(row)
            else:
                row.version = review.version
                row.status = review.status.value
                row.updated_at = review.updated_at
                row.document_json = review.model_dump_json()
            session.commit()

    def get_review(self, raid_id: UUID | str) -> RaidReview | None:
        with Session(self._engine) as session:
            row = session.get(RaidReviewRow, str(raid_id))
            if row is None:
                return None
            return RaidReview.model_validate_json(row.document_json)

    def add_review_audit(self, entry: ReviewAuditEntry) -> None:
        with Session(self._engine) as session:
            session.add(
                ReviewAuditRow(
                    id=str(entry.id),
                    raid_id=str(entry.raid_id),
                    version=entry.version,
                    changed_at=entry.changed_at,
                    action=entry.action,
                    document_json=entry.model_dump_json(),
                )
            )
            session.commit()

    def list_review_audits(self, raid_id: UUID | str) -> list[ReviewAuditEntry]:
        statement = (
            select(ReviewAuditRow)
            .where(ReviewAuditRow.raid_id == str(raid_id))
            .order_by(ReviewAuditRow.version.asc(), ReviewAuditRow.changed_at.asc())
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [ReviewAuditEntry.model_validate_json(row.document_json) for row in rows]

    def save_ppe_evidence(self, evidence: PPEEvidence) -> None:
        with Session(self._engine) as session:
            session.merge(self._ppe_evidence_row(evidence))
            session.commit()

    def replace_ppe_evidence_for_raid(
        self,
        raid_id: UUID | str,
        evidence: list[PPEEvidence],
    ) -> None:
        raid_key = str(raid_id)
        if any(str(item.raid_id) != raid_key for item in evidence):
            raise ValueError("All replacement PPE evidence must belong to the supplied raid")
        with Session(self._engine) as session:
            session.execute(delete(PPEEvidenceRow).where(PPEEvidenceRow.raid_id == raid_key))
            session.add_all(self._ppe_evidence_row(item) for item in evidence)
            session.commit()

    def list_ppe_evidence(self, limit: int | None = None) -> list[PPEEvidence]:
        statement = select(PPEEvidenceRow).order_by(PPEEvidenceRow.observed_at.asc())
        if limit is not None:
            statement = statement.limit(limit)
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [PPEEvidence.model_validate_json(row.document_json) for row in rows]

    def list_ppe_evidence_for_raid(self, raid_id: UUID | str) -> list[PPEEvidence]:
        statement = (
            select(PPEEvidenceRow)
            .where(PPEEvidenceRow.raid_id == str(raid_id))
            .order_by(PPEEvidenceRow.observed_at.asc())
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [PPEEvidence.model_validate_json(row.document_json) for row in rows]

    def save_profile_snapshot(self, snapshot: ProfileSnapshot) -> None:
        with Session(self._engine) as session:
            session.merge(
                ProfileSnapshotRow(
                    id=str(snapshot.id),
                    version=snapshot.version,
                    generated_at=snapshot.generated_at,
                    evidence_fingerprint=snapshot.evidence_fingerprint,
                    document_json=snapshot.model_dump_json(),
                )
            )
            session.commit()

    def get_latest_profile_snapshot(self) -> ProfileSnapshot | None:
        statement = select(ProfileSnapshotRow).order_by(ProfileSnapshotRow.version.desc()).limit(1)
        with Session(self._engine) as session:
            row = session.scalars(statement).first()
            if row is None:
                return None
            return ProfileSnapshot.model_validate_json(row.document_json)

    def list_profile_snapshots(self, limit: int = 100) -> list[ProfileSnapshot]:
        statement = (
            select(ProfileSnapshotRow)
            .order_by(ProfileSnapshotRow.version.desc())
            .limit(limit)
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [ProfileSnapshot.model_validate_json(row.document_json) for row in rows]

    def add_profile_audit(self, entry: ProfileAuditEntry) -> None:
        with Session(self._engine) as session:
            session.add(
                ProfileAuditRow(
                    id=str(entry.id),
                    snapshot_id=str(entry.snapshot_id),
                    generated_at=entry.generated_at,
                    trigger=entry.trigger,
                    document_json=entry.model_dump_json(),
                )
            )
            session.commit()

    def list_profile_audits(self, limit: int = 100) -> list[ProfileAuditEntry]:
        statement = (
            select(ProfileAuditRow)
            .order_by(ProfileAuditRow.generated_at.desc())
            .limit(limit)
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [ProfileAuditEntry.model_validate_json(row.document_json) for row in rows]

    @staticmethod
    def _ppe_evidence_row(evidence: PPEEvidence) -> PPEEvidenceRow:
        return PPEEvidenceRow(
            id=str(evidence.id),
            raid_id=str(evidence.raid_id) if evidence.raid_id is not None else None,
            source=evidence.source.value,
            observed_at=evidence.observed_at,
            document_json=evidence.model_dump_json(),
        )
