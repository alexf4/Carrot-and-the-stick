import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import vote_outcome_enum


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        # Partial unique index: NULL congress_vote_id rows (pre-scheduled votes) are excluded.
        # SQLite ignores postgresql_where and applies a full unique index, which is fine for tests.
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
    __tablename__ = "vote_outcomes"
    __table_args__ = (
        sa.UniqueConstraint("vote_id", "representative_id", name="uq_vote_outcomes_vote_rep"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("votes.id"), nullable=False)
    representative_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("representatives.id"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(vote_outcome_enum, nullable=False)
