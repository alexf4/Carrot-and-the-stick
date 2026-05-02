import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import disbursement_status_enum, pledge_direction_enum, pledge_status_enum


class Pledge(Base):
    __tablename__ = "pledges"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("users.id"), nullable=False)
    vote_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("votes.id"), nullable=False)
    representative_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("representatives.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(pledge_direction_enum, nullable=False)
    amount_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(pledge_status_enum, nullable=False, default="held")
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Disbursement(Base):
    __tablename__ = "disbursements"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    election_date: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    executed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    total_carrot_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    total_stick_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(disbursement_status_enum, nullable=False, default="pending")
