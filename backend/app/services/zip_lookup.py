import os
from dataclasses import dataclass
from typing import Protocol


class ZipNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ZipInfo:
    state: str  # 2-letter uppercase, e.g. "VA"
    house_district: int  # congressional district number


class ZipLookupClient(Protocol):
    def lookup(self, zip_code: str) -> ZipInfo: ...


class GoogleCivicZipLookup:
    _BASE = "https://www.googleapis.com/civicinfo/v2/representatives"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def lookup(self, zip_code: str) -> ZipInfo:
        import httpx

        resp = httpx.get(
            self._BASE,
            params={
                "address": zip_code,
                "key": self._api_key,
                "roles": "legislatorLowerBody",
                "includeOffices": "true",
            },
        )
        if resp.status_code == 404:
            raise ZipNotFoundError(zip_code)
        resp.raise_for_status()

        divisions = resp.json().get("divisions", {})
        # Parse "ocd-division/country:us/state:va/cd:8" → state="VA", district=8
        for ocd_id in divisions:
            parts = dict(seg.split(":", 1) for seg in ocd_id.split("/") if ":" in seg)
            if "cd" in parts and "state" in parts:
                return ZipInfo(
                    state=parts["state"].upper(),
                    house_district=int(parts["cd"]),
                )

        raise ZipNotFoundError(zip_code)


def get_zip_lookup() -> ZipLookupClient:
    return GoogleCivicZipLookup(api_key=os.environ.get("GOOGLE_CIVIC_API_KEY", ""))
