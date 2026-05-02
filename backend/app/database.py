import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_SessionLocal: type[Session] | None = None


def _session_factory() -> type[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        engine = create_engine(os.environ["DATABASE_URL"])
        _SessionLocal = sessionmaker(bind=engine)  # type: ignore[assignment]
    return _SessionLocal  # type: ignore[return-value]


def get_db() -> Generator[Session, None, None]:
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()
