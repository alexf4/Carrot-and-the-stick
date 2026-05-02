import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    zip_code: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    verification_tier: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    total_pledged_lifetime_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    stripe_customer_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class UserRepresentative(Base):
    __tablename__ = "user_representatives"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id"), primary_key=True
    )
    representative_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("representatives.id"), primary_key=True
    )
    is_confirmed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
