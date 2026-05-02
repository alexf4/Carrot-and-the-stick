"""SQLAlchemy ORM models for votes and vote outcomes.

This module defines two tightly coupled tables:

``votes``
    Records a congressional roll-call vote on a specific bill. A vote begins
    as unresolved (``resolved_at = None``) and becomes resolved once the
    ProPublica sync records a non-empty ``result`` string. The lifecycle of a
    vote directly drives the pledge resolution engine — pledges remain ``held``
    until the vote resolves, at which point they become Carrots or Sticks.

``vote_outcomes``
    Records each representative's individual position on a vote. One row per
    (vote, representative) pair. These rows are created by the congress sync
    engine when it fetches detailed vote data from ProPublica, and consumed
    by the resolution engine to determine whether each pledge is a Carrot or
    a Stick.

Unique constraints (added in migration 0002)
--------------------------------------------
Both models declare ``__table_args__`` that enforce uniqueness at the database
level, in addition to the application-level query-before-insert guards in the
sync engine. See ``alembic/versions/0002_congress_sync_constraints.py`` for
the rationale.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import vote_outcome_enum


class Vote(Base):
    """A congressional roll-call vote on a specific bill.

    Votes move through a two-state lifecycle:
    - **Unresolved**: ``resolved_at = None``. The vote is scheduled or in
      progress. Pledges against this vote are in ``held`` status.
    - **Resolved**: ``resolved_at`` is set to the timestamp when the vote
      concluded. The resolution engine can now determine Carrot vs. Stick
      outcomes for all associated pledges.

    The ``congress_vote_id`` field is the stable external identifier from
    ProPublica (formatted as ``"{congress}/{chamber}/{session}/{roll_call}"``).
    It is nullable because votes can be pre-scheduled in our system before
    they appear in the ProPublica API — those rows start with a NULL
    ``congress_vote_id`` and are matched to a ProPublica record when the sync
    runs.

    Attributes
    ----------
    id:
        Internal UUID primary key. Used in foreign keys from ``vote_outcomes``
        and ``pledges``.
    bill_id:
        Foreign key to the ``bills`` table. Every vote is associated with
        exactly one bill.
    scheduled_at:
        The datetime the vote was expected (or did) occur. For votes ingested
        via the ProPublica sync this is the same as ``resolved_at``. For
        pre-scheduled votes it represents the expected floor time.
    resolved_at:
        The datetime the vote concluded and positions were finalised. ``None``
        if the vote has not yet resolved. Setting this value is what triggers
        the resolution engine event.
    congress_vote_id:
        ProPublica composite key: ``"{congress}/{chamber}/{session}/{roll_call}"``.
        Nullable to support pre-scheduled votes created before the
        corresponding ProPublica record exists. A partial unique index
        (migration 0002) prevents duplicates among non-null values.
    """

    __tablename__ = "votes"
    __table_args__ = (
        # Partial unique index so that each ProPublica vote ID maps to exactly
        # one row, while allowing multiple NULL rows for pre-scheduled votes
        # that do not yet have a ProPublica ID. SQLite (used in tests) ignores
        # ``postgresql_where`` and creates a full unique index — that is
        # acceptable because tests never insert two NULL congress_vote_id rows
        # that need to coexist.
        sa.Index(
            "uq_votes_congress_vote_id",
            "congress_vote_id",
            unique=True,
            postgresql_where=sa.text("congress_vote_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("bills.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    congress_vote_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class VoteOutcomeRow(Base):
    """A representative's recorded position on a specific vote.

    One row exists per (vote, representative) pair once the vote has been
    synced from ProPublica. This table is the authoritative record of how each
    rep voted and is the direct input to the pledge resolution engine.

    Outcome semantics (from the ubiquitous language):
    - ``"yes"`` or ``"no"`` that matches the constituent's Direction →
      **Compliant Vote** → **Carrot** (pledge routes to Support Destination).
    - ``"yes"`` or ``"no"`` that does NOT match the Direction →
      **Non-compliant Vote** → **Stick**.
    - ``"absent"`` (mapped from ProPublica's ``"Not Voting"``) → always a
      **Stick**, regardless of Direction.
    - ``"present"`` → always a **Stick**, regardless of Direction.

    Attributes
    ----------
    id:
        Internal UUID primary key.
    vote_id:
        Foreign key to the ``votes`` table.
    representative_id:
        Foreign key to the ``representatives`` table.
    outcome:
        The representative's recorded position. One of the values in the
        ``vote_outcome`` enum: ``"yes"``, ``"no"``, ``"absent"``,
        ``"present"``.
    """

    __tablename__ = "vote_outcomes"
    __table_args__ = (
        # A representative votes exactly once per vote. This constraint
        # prevents the sync engine from inserting duplicate outcomes under
        # concurrent execution (e.g. two simultaneous POST /admin/sync calls).
        sa.UniqueConstraint("vote_id", "representative_id", name="uq_vote_outcomes_vote_rep"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("votes.id"), nullable=False)
    representative_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("representatives.id"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(vote_outcome_enum, nullable=False)
