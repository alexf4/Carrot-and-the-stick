"""Add unique constraints required for congress sync idempotency.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-02

Why these constraints are needed
---------------------------------
The congress sync engine (``app.services.congress_sync``) is designed to be
run repeatedly without producing duplicate data. Application-level code
guards against duplicates with query-before-insert logic, but this alone is
not sufficient under concurrent conditions (e.g. two simultaneous requests to
``POST /admin/sync``, or a scheduler fire overlapping with a manual trigger).
These database-level constraints act as the final safety net.

Constraint 1 — partial unique index on ``votes.congress_vote_id``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A ``congress_vote_id`` (formatted as ``"{congress}/{chamber}/{session}/{roll_call}"``)
uniquely identifies a roll-call vote from the ProPublica API. Only one row in
the ``votes`` table should ever hold a given ``congress_vote_id``.

The index is **partial** (``WHERE congress_vote_id IS NOT NULL``) because the
column is nullable. Future functionality may allow pre-scheduling votes before
they appear in ProPublica — those rows would have ``congress_vote_id = NULL``
and must not conflict with each other.

SQLite note: the SQLAlchemy model's ``__table_args__`` declares this index
with ``postgresql_where``. SQLite ignores that clause and creates a full
unique index instead. This is acceptable for tests — test data never includes
two NULL-congress_vote_id rows that should be allowed to coexist.

Constraint 2 — unique constraint on ``vote_outcomes(vote_id, representative_id)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A representative casts exactly one vote per roll-call vote. The
``vote_outcomes`` table records each representative's position, so the
combination of ``(vote_id, representative_id)`` must be unique. Without this
constraint a bug or concurrent sync could insert two rows for the same rep on
the same vote, corrupting the pledge resolution logic (which counts outcomes
to determine Carrot vs. Stick).
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply both unique constraints."""
    # Partial unique index: rows where congress_vote_id IS NULL are excluded,
    # allowing multiple pre-scheduled votes without conflicts.
    op.create_index(
        "uq_votes_congress_vote_id",
        "votes",
        ["congress_vote_id"],
        unique=True,
        postgresql_where=sa.text("congress_vote_id IS NOT NULL"),
    )

    # A representative votes exactly once per vote — enforce at the DB level.
    op.create_unique_constraint(
        "uq_vote_outcomes_vote_rep",
        "vote_outcomes",
        ["vote_id", "representative_id"],
    )


def downgrade() -> None:
    """Remove both unique constraints in reverse order."""
    op.drop_constraint("uq_vote_outcomes_vote_rep", "vote_outcomes")
    op.drop_index("uq_votes_congress_vote_id", "votes")
