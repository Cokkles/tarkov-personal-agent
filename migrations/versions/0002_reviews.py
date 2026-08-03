"""Add raid review and audit tables.

Revision ID: 0002_reviews
Revises: 0001_initial
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_reviews"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raid_reviews",
        sa.Column("raid_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["raid_id"], ["raids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("raid_id"),
    )
    op.create_index("ix_raid_reviews_status", "raid_reviews", ["status"], unique=False)
    op.create_index(
        "ix_raid_reviews_updated_at",
        "raid_reviews",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "review_audit",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("raid_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["raid_id"], ["raids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_audit_raid_id", "review_audit", ["raid_id"], unique=False)
    op.create_index("ix_review_audit_version", "review_audit", ["version"], unique=False)
    op.create_index(
        "ix_review_audit_changed_at",
        "review_audit",
        ["changed_at"],
        unique=False,
    )
    op.create_index("ix_review_audit_action", "review_audit", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_review_audit_action", table_name="review_audit")
    op.drop_index("ix_review_audit_changed_at", table_name="review_audit")
    op.drop_index("ix_review_audit_version", table_name="review_audit")
    op.drop_index("ix_review_audit_raid_id", table_name="review_audit")
    op.drop_table("review_audit")
    op.drop_index("ix_raid_reviews_updated_at", table_name="raid_reviews")
    op.drop_index("ix_raid_reviews_status", table_name="raid_reviews")
    op.drop_table("raid_reviews")
