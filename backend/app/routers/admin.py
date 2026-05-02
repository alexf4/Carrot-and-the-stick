"""Admin endpoints — manual sync trigger and other operator tools."""
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.congress_client import CongressClient, get_congress_client
from app.services.congress_sync import SyncResult, sync_chamber

router = APIRouter(prefix="/admin")


def get_congress_client_dep() -> CongressClient:
    """Named dependency so tests can override it independently."""
    return get_congress_client()


class ChamberSyncResult(BaseModel):
    bills_upserted: int
    votes_upserted: int
    outcomes_upserted: int


class SyncResponse(BaseModel):
    house: ChamberSyncResult
    senate: ChamberSyncResult


def _verify_admin_key(key: str | None) -> None:
    expected = os.environ.get("ADMIN_API_KEY", "")
    if not expected or not key or key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")


@router.post("/sync", response_model=SyncResponse)
def trigger_sync(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
    client: CongressClient = Depends(get_congress_client_dep),
) -> SyncResponse:
    _verify_admin_key(x_admin_key)
    house = sync_chamber(db, client, "house")
    senate = sync_chamber(db, client, "senate")
    return SyncResponse(
        house=_to_schema(house),
        senate=_to_schema(senate),
    )


def _to_schema(r: SyncResult) -> ChamberSyncResult:
    return ChamberSyncResult(
        bills_upserted=r.bills_upserted,
        votes_upserted=r.votes_upserted,
        outcomes_upserted=r.outcomes_upserted,
    )
