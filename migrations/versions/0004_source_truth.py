"""Add Source-of-Truth registry, claims, and conflicts.

Revision ID: 0004_source_truth
Revises: 0003_ppe
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_source_truth"
down_revision: str | None = "0003_ppe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "truth_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("authority", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_truth_sources_key", "truth_sources", ["key"], unique=True)
    op.create_index(
        "ix_truth_sources_authority",
        "truth_sources",
        ["authority"],
        unique=False,
    )
    op.create_index("ix_truth_sources_status", "truth_sources", ["status"], unique=False)
    op.create_index(
        "ix_truth_sources_next_review_at",
        "truth_sources",
        ["next_review_at"],
        unique=False,
    )

    op.create_table(
        "truth_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("claim_key", sa.String(length=180), nullable=False),
        sa.Column("game_scope", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_truth_claims_claim_key",
        "truth_claims",
        ["claim_key"],
        unique=False,
    )
    op.create_index(
        "ix_truth_claims_game_scope",
        "truth_claims",
        ["game_scope"],
        unique=False,
    )
    op.create_index("ix_truth_claims_status", "truth_claims", ["status"], unique=False)
    op.create_index(
        "ix_truth_claims_next_review_at",
        "truth_claims",
        ["next_review_at"],
        unique=False,
    )

    op.create_table(
        "truth_conflicts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("claim_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_truth_conflicts_claim_key",
        "truth_conflicts",
        ["claim_key"],
        unique=False,
    )
    op.create_index(
        "ix_truth_conflicts_status",
        "truth_conflicts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_truth_conflicts_detected_at",
        "truth_conflicts",
        ["detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_truth_conflicts_detected_at", table_name="truth_conflicts")
    op.drop_index("ix_truth_conflicts_status", table_name="truth_conflicts")
    op.drop_index("ix_truth_conflicts_claim_key", table_name="truth_conflicts")
    op.drop_table("truth_conflicts")

    op.drop_index("ix_truth_claims_next_review_at", table_name="truth_claims")
    op.drop_index("ix_truth_claims_status", table_name="truth_claims")
    op.drop_index("ix_truth_claims_game_scope", table_name="truth_claims")
    op.drop_index("ix_truth_claims_claim_key", table_name="truth_claims")
    op.drop_table("truth_claims")

    op.drop_index("ix_truth_sources_next_review_at", table_name="truth_sources")
    op.drop_index("ix_truth_sources_status", table_name="truth_sources")
    op.drop_index("ix_truth_sources_authority", table_name="truth_sources")
    op.drop_index("ix_truth_sources_key", table_name="truth_sources")
    op.drop_table("truth_sources")
