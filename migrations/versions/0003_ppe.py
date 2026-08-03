"""Add Personal Playstyle Engine tables.

Revision ID: 0003_ppe
Revises: 0002_reviews
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ppe"
down_revision: str | None = "0002_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ppe_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("raid_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["raid_id"], ["raids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ppe_evidence_raid_id", "ppe_evidence", ["raid_id"], unique=False)
    op.create_index("ix_ppe_evidence_source", "ppe_evidence", ["source"], unique=False)
    op.create_index(
        "ix_ppe_evidence_observed_at",
        "ppe_evidence",
        ["observed_at"],
        unique=False,
    )

    op.create_table(
        "ppe_profile_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index(
        "ix_ppe_profile_snapshots_version",
        "ppe_profile_snapshots",
        ["version"],
        unique=True,
    )
    op.create_index(
        "ix_ppe_profile_snapshots_generated_at",
        "ppe_profile_snapshots",
        ["generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_ppe_profile_snapshots_evidence_fingerprint",
        "ppe_profile_snapshots",
        ["evidence_fingerprint"],
        unique=False,
    )

    op.create_table(
        "ppe_profile_audit",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger", sa.String(length=240), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["ppe_profile_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ppe_profile_audit_snapshot_id",
        "ppe_profile_audit",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_ppe_profile_audit_generated_at",
        "ppe_profile_audit",
        ["generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_ppe_profile_audit_trigger",
        "ppe_profile_audit",
        ["trigger"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ppe_profile_audit_trigger", table_name="ppe_profile_audit")
    op.drop_index("ix_ppe_profile_audit_generated_at", table_name="ppe_profile_audit")
    op.drop_index("ix_ppe_profile_audit_snapshot_id", table_name="ppe_profile_audit")
    op.drop_table("ppe_profile_audit")

    op.drop_index(
        "ix_ppe_profile_snapshots_evidence_fingerprint",
        table_name="ppe_profile_snapshots",
    )
    op.drop_index(
        "ix_ppe_profile_snapshots_generated_at",
        table_name="ppe_profile_snapshots",
    )
    op.drop_index("ix_ppe_profile_snapshots_version", table_name="ppe_profile_snapshots")
    op.drop_table("ppe_profile_snapshots")

    op.drop_index("ix_ppe_evidence_observed_at", table_name="ppe_evidence")
    op.drop_index("ix_ppe_evidence_source", table_name="ppe_evidence")
    op.drop_index("ix_ppe_evidence_raid_id", table_name="ppe_evidence")
    op.drop_table("ppe_evidence")
