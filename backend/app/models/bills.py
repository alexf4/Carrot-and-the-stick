import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    congress_bill_id: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    summary_ai: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    introduced_date: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    status: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
