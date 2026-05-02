"""Add unique constraints for congress sync idempotency.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index on votes.congress_vote_id — NULLs excluded so pre-scheduled
    # votes (created before we have a ProPublica ID) are unaffected.
    op.create_index(
        "uq_votes_congress_vote_id",
        "votes",
        ["congress_vote_id"],
        unique=True,
        postgresql_where=sa.text("congress_vote_id IS NOT NULL"),
    )
    # A representative votes exactly once per vote.
    op.create_unique_constraint(
        "uq_vote_outcomes_vote_rep",
        "vote_outcomes",
        ["vote_id", "representative_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_vote_outcomes_vote_rep", "vote_outcomes")
    op.drop_index("uq_votes_congress_vote_id", "votes")
