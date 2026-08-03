from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import DateTime, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tarkov_agent.domain.source_truth import (
    ClaimRecord,
    ClaimStatus,
    ConflictRecord,
    ConflictStatus,
    SourceRecord,
    SourceStatus,
)


class SourceTruthBase(DeclarativeBase):
    pass


class SourceRow(SourceTruthBase):
    __tablename__ = "truth_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    authority: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class ClaimRow(SourceTruthBase):
    __tablename__ = "truth_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_key: Mapped[str] = mapped_column(String(180), index=True)
    game_scope: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class ConflictRow(SourceTruthBase):
    __tablename__ = "truth_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_key: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    document_json: Mapped[str] = mapped_column(Text)


class SourceTruthRepository:
    def __init__(self, database_path: Path | str) -> None:
        path = Path(database_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite+pysqlite:///{path.as_posix()}", future=True)

    def initialize(self) -> None:
        SourceTruthBase.metadata.create_all(self._engine)

    def save_source(self, source: SourceRecord) -> None:
        with Session(self._engine) as session:
            session.merge(
                SourceRow(
                    id=str(source.id),
                    key=source.key,
                    authority=source.authority.value,
                    status=source.status.value,
                    next_review_at=source.next_review_at,
                    document_json=source.model_dump_json(),
                )
            )
            session.commit()

    def get_source(self, source_id: UUID | str) -> SourceRecord | None:
        with Session(self._engine) as session:
            row = session.get(SourceRow, str(source_id))
            if row is None:
                return None
            return SourceRecord.model_validate_json(row.document_json)

    def get_source_by_key(self, key: str) -> SourceRecord | None:
        statement = select(SourceRow).where(SourceRow.key == key).limit(1)
        with Session(self._engine) as session:
            row = session.scalars(statement).first()
            if row is None:
                return None
            return SourceRecord.model_validate_json(row.document_json)

    def list_sources(
        self,
        *,
        status: SourceStatus | None = None,
        limit: int = 1000,
    ) -> list[SourceRecord]:
        statement = select(SourceRow)
        if status is not None:
            statement = statement.where(SourceRow.status == status.value)
        statement = statement.order_by(SourceRow.key.asc()).limit(limit)
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [SourceRecord.model_validate_json(row.document_json) for row in rows]

    def save_claim(self, claim: ClaimRecord) -> None:
        with Session(self._engine) as session:
            session.merge(
                ClaimRow(
                    id=str(claim.id),
                    claim_key=claim.key,
                    game_scope=claim.game_scope.value,
                    status=claim.status.value,
                    next_review_at=claim.next_review_at,
                    document_json=claim.model_dump_json(),
                )
            )
            session.commit()

    def get_claim(self, claim_id: UUID | str) -> ClaimRecord | None:
        with Session(self._engine) as session:
            row = session.get(ClaimRow, str(claim_id))
            if row is None:
                return None
            return ClaimRecord.model_validate_json(row.document_json)

    def list_claims(
        self,
        *,
        key: str | None = None,
        status: ClaimStatus | None = None,
        limit: int = 5000,
    ) -> list[ClaimRecord]:
        statement = select(ClaimRow)
        if key is not None:
            statement = statement.where(ClaimRow.claim_key == key)
        if status is not None:
            statement = statement.where(ClaimRow.status == status.value)
        statement = statement.order_by(ClaimRow.claim_key.asc()).limit(limit)
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [ClaimRecord.model_validate_json(row.document_json) for row in rows]

    def replace_conflicts(self, conflicts: list[ConflictRecord]) -> None:
        with Session(self._engine) as session:
            session.execute(delete(ConflictRow))
            session.add_all(
                ConflictRow(
                    id=str(conflict.id),
                    claim_key=conflict.claim_key,
                    status=conflict.status.value,
                    detected_at=conflict.detected_at,
                    document_json=conflict.model_dump_json(),
                )
                for conflict in conflicts
            )
            session.commit()

    def list_conflicts(
        self,
        *,
        status: ConflictStatus | None = None,
        limit: int = 5000,
    ) -> list[ConflictRecord]:
        statement = select(ConflictRow)
        if status is not None:
            statement = statement.where(ConflictRow.status == status.value)
        statement = statement.order_by(ConflictRow.detected_at.desc()).limit(limit)
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [ConflictRecord.model_validate_json(row.document_json) for row in rows]
