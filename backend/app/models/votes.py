import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import vote_outcome_enum


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("bills.id"), nullable=False)
    scheduled_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    congress_vote_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class VoteOutcomeRow(Base):
    __tablename__ = "vote_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("votes.id"), nullable=False)
    representative_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("representatives.id"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(vote_outcome_enum, nullable=False)
