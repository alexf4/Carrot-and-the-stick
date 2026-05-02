import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import chamber_enum


class Representative(Base):
    __tablename__ = "representatives"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    bioguide_id: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    party: Mapped[str] = mapped_column(sa.Text, nullable=False)
    chamber: Mapped[str] = mapped_column(chamber_enum, nullable=False)
    state: Mapped[str] = mapped_column(sa.Text, nullable=False)
    district: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    next_election_date: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
