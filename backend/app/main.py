"""FastAPI application entry point and process lifecycle management.

This module creates the ``app`` instance, registers all routers, and manages
the application lifespan — specifically the APScheduler background thread that
runs the Congress sync job on a configurable interval.

Scheduler design
----------------
The scheduler is a ``BackgroundScheduler`` (thread-based, not async). This
choice preserves compatibility with the synchronous SQLAlchemy session pattern
used everywhere else in the codebase. An ``AsyncIOScheduler`` would require
async-aware database sessions and a more complex context management story.

The scheduler is started inside the ``lifespan`` async context manager, which
is the FastAPI-recommended way to run startup/shutdown logic (replacing the
deprecated ``@app.on_event`` hooks). It shuts down with ``wait=False`` on
application exit to avoid blocking the ASGI server during graceful shutdown.

Fail-soft startup
-----------------
The scheduler is only started when ``CONGRESS_API_KEY`` is present in the
environment. This means:
- Test runs (which do not set this variable) start the app without a
  scheduler, keeping the test suite fast and free of background threads.
- Staging/production environments without the key (e.g. a freshly deployed
  instance before secrets are configured) will start normally and serve
  requests — the sync simply won't run until the key is added.

Scheduler job isolation
-----------------------
The ``_run_sync_job`` function creates its own SQLAlchemy session using
``_session_factory()`` directly, rather than using the ``get_db`` dependency.
This is intentional: ``get_db`` is designed for request-scoped use (it yields
inside a FastAPI dependency), whereas the scheduler job runs outside any
request context. Using ``_session_factory()`` gives us a session we own and
can close explicitly in a ``finally`` block.

Environment variables
---------------------
``CONGRESS_API_KEY``
    When set, the scheduler starts at app boot and runs
    ``_run_sync_job`` at the configured interval.
``CONGRESS_SYNC_INTERVAL_MINUTES``
    Interval between sync runs. Defaults to ``60`` if not set.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from app.routers.admin import router as admin_router
from app.routers.reps import router as reps_router

# load_dotenv() is called after all imports to satisfy flake8 E402. This is
# safe because env reads (CONGRESS_API_KEY etc.) happen at lifespan startup
# time — after this module is fully loaded — not at import time.
load_dotenv()  # loads .env from project root (searches upward from backend/)

logger = logging.getLogger(__name__)

# Module-level reference to the running scheduler, held so the lifespan
# shutdown hook can call scheduler.shutdown() without needing a closure.
# ``None`` when the scheduler is not running (i.e. CONGRESS_API_KEY is unset).
_scheduler: BackgroundScheduler | None = None


def _run_sync_job() -> None:
    """APScheduler job — sync both chambers from ProPublica.

    This function is called by the background scheduler on the configured
    interval. It creates its own session, runs the sync engine for both
    chambers, and logs the results. All exceptions are caught and logged
    rather than propagated, so a transient API failure or database error
    does not kill the scheduler thread.

    The imports are done inline (inside the function) to avoid circular
    import issues at module load time — ``congress_client`` and
    ``congress_sync`` both import from ``app.models``, which is fine at
    call time but can cause problems if imported at the module level of
    ``main.py`` before the app is fully initialised.
    """
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
    """Manage application startup and shutdown.

    On startup: starts the APScheduler background thread if
    ``CONGRESS_API_KEY`` is configured in the environment. The scheduler
    immediately schedules the first sync run after ``interval`` minutes
    (it does NOT run immediately on startup — use POST /admin/sync for that).

    On shutdown: gracefully stops the scheduler with ``wait=False`` so the
    ASGI server is not blocked waiting for an in-progress sync to finish.
    Any in-progress sync will be interrupted; the idempotency guarantees
    in the sync engine ensure the next run will pick up cleanly.

    Parameters
    ----------
    app:
        The FastAPI application instance (provided by the framework, not
        used directly here but required by the context manager signature).

    Yields
    ------
    None:
        Control returns to the framework to serve requests.
    """
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
    """Response schema for the health check endpoint.

    Attributes
    ----------
    status:
        Always ``"ok"`` when the application is running and reachable.
    """

    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check endpoint for load balancers and uptime monitors.

    Returns a 200 with ``{"status": "ok"}`` if the application process is
    running. Does not check database connectivity or external service health
    — it is intentionally shallow so it never blocks under load.

    Returns
    -------
    HealthResponse:
        Static ``{"status": "ok"}`` response.
    """
    return HealthResponse(status="ok")
