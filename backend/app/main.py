import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from pydantic import BaseModel

from app.routers.admin import router as admin_router
from app.routers.reps import router as reps_router

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_sync_job() -> None:
    from app.database import _session_factory
    from app.services.congress_client import ProPublicaCongressClient
    from app.services.congress_sync import sync_chamber

    api_key = os.environ.get("CONGRESS_API_KEY", "")
    client = ProPublicaCongressClient(api_key=api_key)
    db = _session_factory()()
    try:
        for chamber in ("house", "senate"):
            result = sync_chamber(db, client, chamber)
            logger.info("congress sync %s: %s", chamber, result)
    except Exception:
        logger.exception("congress sync job failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _scheduler
    if os.environ.get("CONGRESS_API_KEY"):
        interval = int(os.environ.get("CONGRESS_SYNC_INTERVAL_MINUTES", "60"))
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(_run_sync_job, "interval", minutes=interval)
        _scheduler.start()
        logger.info("congress sync scheduler started (interval=%dm)", interval)
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


app = FastAPI(lifespan=lifespan)
app.include_router(reps_router)
app.include_router(admin_router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
