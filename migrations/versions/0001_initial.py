"""Create raid and timeline tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raids",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("game", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raids_game", "raids", ["game"], unique=False)
    op.create_index("ix_raids_state", "raids", ["state"], unique=False)
    op.create_index("ix_raids_created_at", "raids", ["created_at"], unique=False)

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("raid_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["raid_id"], ["raids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_timeline_events_raid_id", "timeline_events", ["raid_id"], unique=False
    )
    op.create_index(
        "ix_timeline_events_occurred_at",
        "timeline_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_timeline_events_event_type",
        "timeline_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_events_event_type", table_name="timeline_events")
    op.drop_index("ix_timeline_events_occurred_at", table_name="timeline_events")
    op.drop_index("ix_timeline_events_raid_id", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_raids_created_at", table_name="raids")
    op.drop_index("ix_raids_state", table_name="raids")
    op.drop_index("ix_raids_game", table_name="raids")
    op.drop_table("raids")
