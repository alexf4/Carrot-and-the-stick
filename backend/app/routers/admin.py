"""Admin API endpoints for operator-level actions.

This router exposes privileged endpoints that should never be accessible to
end users. At present the only endpoint is ``POST /admin/sync``, which
manually triggers the Congress sync pipeline for both chambers.

Authentication
--------------
All endpoints under this router are protected by a simple pre-shared API key
passed in the ``X-Admin-Key`` request header. The expected key is read from
the ``ADMIN_API_KEY`` environment variable at request time.

This is intentionally minimal for MVP. The checks are:
- If ``ADMIN_API_KEY`` is not set in the environment, all requests are
  rejected (fail-closed rather than fail-open).
- If the header is missing or the value does not match exactly, a 403 is
  returned. Missing headers produce 403, not 422, because we make the header
  optional at the FastAPI layer and enforce the rule ourselves.

Operational notes
-----------------
The sync endpoint makes two sequential API calls to ProPublica (one per
chamber) and several database writes per vote. On a normal day with ~20–40
votes this takes a few seconds. It is synchronous — the HTTP response is
returned only after both chambers have been fully synced. For the MVP load
profile this is acceptable; if sync times grow it can be moved to a
background task.

The scheduler (configured in ``app.main``) calls the sync engine directly,
not this endpoint. The endpoint exists so operators can trigger an
out-of-schedule sync without SSH access to the server.
"""

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.congress_client import CongressClient, get_congress_client
from app.services.congress_sync import SyncResult, sync_chamber

router = APIRouter(prefix="/admin")


def get_congress_client_dep() -> CongressClient:
    """Thin wrapper around ``get_congress_client`` registered as a named dependency.

    The extra indirection exists so that tests can override this specific
    dependency via ``app.dependency_overrides[get_congress_client_dep]``
    without also overriding the module-level ``get_congress_client`` factory,
    which may be used elsewhere. This keeps test overrides scoped to this
    router only.

    Returns
    -------
    CongressClient:
        A configured ``ProPublicaCongressClient`` in production, or whatever
        the test has injected via ``app.dependency_overrides``.
    """
    return get_congress_client()


class ChamberSyncResult(BaseModel):
    """Per-chamber counts from a sync run, as returned by the API.

    This is the Pydantic serialisation of ``SyncResult`` from the sync engine.
    It is kept as a separate schema (rather than making ``SyncResult`` a
    Pydantic model) to keep the sync engine free of FastAPI/Pydantic concerns.

    Attributes
    ----------
    bills_upserted:
        Number of ``bills`` rows inserted or updated.
    votes_upserted:
        Number of ``votes`` rows inserted or updated.
    outcomes_upserted:
        Number of ``vote_outcomes`` rows inserted during this run.
    """

    bills_upserted: int
    votes_upserted: int
    outcomes_upserted: int


class SyncResponse(BaseModel):
    """Full sync response containing results for both chambers.

    Attributes
    ----------
    house:
        Sync counts for the House of Representatives.
    senate:
        Sync counts for the Senate.
    """

    house: ChamberSyncResult
    senate: ChamberSyncResult


def _verify_admin_key(key: str | None) -> None:
    """Validate the X-Admin-Key header value against the environment.

    Always raises ``HTTPException(403)`` rather than 401 or 422, for two
    reasons:
    - We do not want to reveal whether the endpoint exists at all to
      unauthenticated callers.
    - FastAPI's ``Header(...)`` (required) would return 422 for a missing
      header; making the header optional and checking here gives us 403 in
      all failure cases (missing, empty, or wrong).

    Parameters
    ----------
    key:
        The value of the ``X-Admin-Key`` header, or ``None`` if it was absent.

    Raises
    ------
    HTTPException(403):
        If ``ADMIN_API_KEY`` is not configured in the environment, if ``key``
        is ``None`` or empty, or if ``key`` does not match the configured
        value.
    """
    expected = os.environ.get("ADMIN_API_KEY", "")
    if not expected or not key or key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")


@router.post("/sync", response_model=SyncResponse)
def trigger_sync(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
    client: CongressClient = Depends(get_congress_client_dep),
) -> SyncResponse:
    """Manually trigger a full Congress sync for both chambers.

    Runs ``sync_chamber`` sequentially for House then Senate. Returns row
    counts for each chamber so the caller can confirm the sync did useful work.

    This endpoint is intended for operator use (e.g. after deploying a schema
    change, after a ProPublica outage, or to bootstrap a fresh database). The
    APScheduler job in ``app.main`` handles normal scheduled operation.

    Parameters
    ----------
    x_admin_key:
        Value of the ``X-Admin-Key`` header. ``None`` if the header was
        omitted. Validated by ``_verify_admin_key`` before any sync work
        begins.
    db:
        Injected SQLAlchemy session (overridable in tests).
    client:
        Injected Congress API client (overridable in tests).

    Returns
    -------
    SyncResponse:
        Row counts for house and senate chambers.

    Raises
    ------
    HTTPException(403):
        If the admin key is missing or invalid.
    CongressAPIError:
        Propagated if the ProPublica API is unreachable after retries. The
        caller will receive a 500 — no partial state is rolled back since the
        sync is idempotent and can be retried safely.
    """
    _verify_admin_key(x_admin_key)
    house = sync_chamber(db, client, "house")
    senate = sync_chamber(db, client, "senate")
    return SyncResponse(
        house=_to_schema(house),
        senate=_to_schema(senate),
    )


def _to_schema(r: SyncResult) -> ChamberSyncResult:
    """Convert a ``SyncResult`` dataclass into the Pydantic ``ChamberSyncResult`` schema.

    This mapping layer keeps the sync engine (a plain dataclass) decoupled
    from the HTTP layer (Pydantic models). If the two structures ever diverge
    — e.g. if the API response needs different field names — only this
    function needs to change.

    Parameters
    ----------
    r:
        The ``SyncResult`` returned by ``sync_chamber``.

    Returns
    -------
    ChamberSyncResult:
        Pydantic model ready for JSON serialisation.
    """
    return ChamberSyncResult(
        bills_upserted=r.bills_upserted,
        votes_upserted=r.votes_upserted,
        outcomes_upserted=r.outcomes_upserted,
    )
