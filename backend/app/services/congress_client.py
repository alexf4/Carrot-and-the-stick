"""HTTP client for the ProPublica Congress API.

This module provides the data-access layer for all ProPublica Congress API
interactions. It is intentionally kept free of database logic — its only
responsibility is to make HTTP requests, parse the raw JSON responses into
typed Python dataclasses, and surface retry/rate-limit behavior so the calling
code never has to reason about HTTP status codes.

Architecture note
-----------------
``CongressClient`` is a ``Protocol`` (structural subtyping) rather than an
abstract base class. This means any object that implements ``get_recent_votes``
and ``get_vote_detail`` with matching signatures satisfies the type without
inheriting from anything. This pattern makes test doubles trivial to write —
the ``FakeCongressClient`` in the test suite is just a plain class with no
inheritance required.

ProPublica API overview
-----------------------
Two endpoints are used:

1. Recent votes (per chamber):
   ``GET /congress/v1/{chamber}/votes/recent.json``
   Returns a paginated list of the most recent roll-call votes. Each item
   contains the bill metadata and totals but NOT per-representative positions.

2. Vote detail (single vote):
   ``GET /congress/v1/{congress}/{chamber}/sessions/{session}/votes/{roll_call}.json``
   Returns the full vote record including every member's position. This is
   called once per vote that needs its outcomes recorded.

Rate limiting
-------------
ProPublica enforces a limit of 500 requests per day for free-tier keys. When
the limit is hit they return HTTP 429 with a ``Retry-After`` header (seconds).
``_request_with_backoff`` honours this header and retries up to ``_MAX_RETRIES``
times with exponential fallback. On final exhaustion it raises
``CongressAPIError`` so the scheduler can log and continue rather than
crashing.

Environment variables
---------------------
``CONGRESS_API_KEY``
    Required at runtime. Supplied as the ``X-API-Key`` request header on every
    call. Not required in tests — inject a fake ``http_client`` instead.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

_BASE = "https://api.propublica.org/congress/v1"

# Maximum number of 429 retries before giving up and raising CongressAPIError.
# Each retry sleeps for the value in the Retry-After header (or an exponential
# fallback). Three retries means up to four total attempts before we bail.
_MAX_RETRIES = 3


class CongressAPIError(Exception):
    """Raised when the ProPublica API returns an unrecoverable error.

    This includes exhausted retries on 429 responses and any non-2xx status
    code that is not a rate-limit. Callers (e.g. the scheduler job) should
    catch this, log it, and move on rather than propagating the exception.
    """


@dataclass(frozen=True)
class RecentVote:
    """A single roll-call vote record from the ProPublica recent-votes endpoint.

    This is a lightweight summary — it contains bill metadata and totals but
    NOT per-representative positions. Use ``VoteDetail`` (returned by
    ``get_vote_detail``) when you need positions.

    Attributes
    ----------
    congress_vote_id:
        Internal composite key built from the ProPublica fields, formatted as
        ``"{congress}/{chamber}/{session}/{roll_call}"`` e.g.
        ``"119/house/1/142"``. Used as the unique identifier for a vote in
        our database (``votes.congress_vote_id``).
    congress:
        The congressional session number (e.g. 119 for the 119th Congress).
    chamber:
        Lowercase string: ``"house"`` or ``"senate"``.
    session:
        Congressional session number within the congress (typically 1 or 2).
    roll_call:
        The roll-call number within the session. Together with congress,
        chamber, and session this uniquely identifies a vote.
    date:
        Vote date as an ISO string ``"YYYY-MM-DD"``.
    time:
        Vote time as ``"HH:MM:SS"`` in the chamber's local clock (Eastern).
        Treated as UTC when stored in the database — close enough for our
        purposes since we only need resolution granularity, not exact TZ.
    congress_bill_id:
        ProPublica's bill slug, e.g. ``"hr1234-119"``. ``None`` for procedural
        votes (motions to table, quorum calls, etc.) that have no associated
        bill. The sync engine skips votes where this is ``None``.
    bill_title:
        Human-readable title of the bill. ``None`` when ``congress_bill_id``
        is ``None``.
    result:
        Raw result string from ProPublica, e.g. ``"Passed"``, ``"Failed"``,
        ``"Agreed to"``. An empty string means the vote is not yet resolved.
        Used by the sync engine to decide whether to set ``resolved_at``.
    """

    congress_vote_id: str
    congress: int
    chamber: str
    session: int
    roll_call: int
    date: str
    time: str
    congress_bill_id: str | None
    bill_title: str | None
    result: str


@dataclass(frozen=True)
class VotePosition:
    """A single representative's position on a specific vote.

    Returned as part of ``VoteDetail.positions``. The ``vote_position`` strings
    come directly from ProPublica and must be mapped to our ``VoteOutcome``
    enum values by the sync engine (see ``_POSITION_MAP`` in
    ``congress_sync.py``).

    Attributes
    ----------
    member_id:
        The representative's Bioguide ID (e.g. ``"P000197"``). This is the
        stable cross-database identifier for members of Congress and maps
        directly to ``representatives.bioguide_id`` in our database.
    vote_position:
        Raw ProPublica string. One of: ``"Yes"``, ``"No"``,
        ``"Not Voting"``, ``"Present"``.
        ``"Not Voting"`` maps to our ``absent`` outcome.
        ``"Present"`` is non-compliant per the domain model (see ubiquitous
        language: a Stick outcome).
    """

    member_id: str
    vote_position: str


@dataclass(frozen=True)
class VoteDetail:
    """Full vote record including every member's position.

    Returned by ``get_vote_detail``. Only fetched after we know a vote has
    resolved (i.e. ``RecentVote.result`` is non-empty), to avoid burning API
    quota on unresolved votes.

    Attributes
    ----------
    congress_vote_id:
        Same composite key as ``RecentVote.congress_vote_id``. Used to
        correlate this detail with the already-upserted ``Vote`` row.
    positions:
        Every member's recorded position for this vote. Members who are no
        longer active or not found in our ``representatives`` table are
        silently skipped by the sync engine.
    """

    congress_vote_id: str
    positions: list[VotePosition]


class CongressClient(Protocol):
    """Structural protocol for the Congress API client.

    Any object that implements these two methods satisfies this type. This
    enables test doubles (``FakeCongressClient``) without inheritance and
    makes the sync engine fully decoupled from the HTTP transport.

    Production code uses ``ProPublicaCongressClient``. Tests inject their own
    implementation that returns fixture data without making network calls.
    """

    def get_recent_votes(self, chamber: str) -> list[RecentVote]:
        """Return the most recent roll-call votes for the given chamber.

        Parameters
        ----------
        chamber:
            ``"house"`` or ``"senate"`` (case-insensitive).

        Returns
        -------
        list[RecentVote]:
            Ordered most-recent first. May be empty if the API returns no
            results (unusual but possible during recess periods).
        """
        ...

    def get_vote_detail(
        self, congress: int, chamber: str, session: int, roll_call: int
    ) -> VoteDetail:
        """Return the full per-member positions for a single vote.

        Parameters
        ----------
        congress:
            Congressional number, e.g. 119.
        chamber:
            ``"house"`` or ``"senate"``.
        session:
            Session number within the congress, typically 1 or 2.
        roll_call:
            Roll-call number within the session.

        Returns
        -------
        VoteDetail:
            Contains every member's recorded position. The ``positions`` list
            may include members not yet in our database — the sync engine
            handles those gracefully by skipping them.
        """
        ...


class ProPublicaCongressClient:
    """Concrete HTTP client for the ProPublica Congress API.

    Authenticates with an API key supplied via the ``X-API-Key`` header.
    All requests go through ``_request_with_backoff``, which handles 429
    rate-limit responses transparently.

    The ``http_client`` parameter exists specifically for testing. Injecting a
    fake ``httpx.Client`` lets the test suite exercise parsing and retry logic
    without any network calls. In production the default ``httpx.Client()``
    is used.

    Parameters
    ----------
    api_key:
        ProPublica API key. Passed as the ``X-API-Key`` header on every
        request.
    http_client:
        Optional pre-constructed ``httpx.Client``. When ``None`` (the default),
        a new client is created. Inject a mock in tests to avoid network calls.
    """

    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client()

    def get_recent_votes(self, chamber: str) -> list[RecentVote]:
        """Fetch the most recent roll-call votes for a chamber.

        Calls ``GET /congress/v1/{chamber}/votes/recent.json`` and parses each
        item in ``results.votes`` into a ``RecentVote`` dataclass. Procedural
        votes without an associated bill will have ``congress_bill_id=None``;
        the sync engine is responsible for deciding what to do with those.

        Parameters
        ----------
        chamber:
            ``"house"`` or ``"senate"`` (lowercased before use in the URL).

        Returns
        -------
        list[RecentVote]:
            Parsed vote summaries. Ordering matches the API (most recent
            first).

        Raises
        ------
        CongressAPIError:
            If the API returns a persistent 429 after all retries, or any
            other non-2xx response code.
        """
        data = self._request_with_backoff(f"{_BASE}/{chamber.lower()}/votes/recent.json")
        votes_raw: list[dict[str, Any]] = data["results"]["votes"]
        return [self._parse_recent_vote(v) for v in votes_raw]

    def get_vote_detail(
        self, congress: int, chamber: str, session: int, roll_call: int
    ) -> VoteDetail:
        """Fetch the full per-member vote positions for a single roll-call.

        Calls ``GET /congress/v1/{congress}/{chamber}/sessions/{session}/votes/{roll_call}.json``
        and extracts the ``positions`` array. This endpoint is only called for
        votes that have already resolved (non-empty ``result``) to avoid
        burning API quota on future votes that have no positions yet.

        Parameters
        ----------
        congress:
            Congressional number.
        chamber:
            ``"house"`` or ``"senate"``.
        session:
            Session number within the congress.
        roll_call:
            Roll-call number within the session.

        Returns
        -------
        VoteDetail:
            Full vote record with all member positions.

        Raises
        ------
        CongressAPIError:
            On persistent rate-limit or non-2xx response.
        """
        url = f"{_BASE}/{congress}/{chamber.lower()}/sessions/{session}/votes/{roll_call}.json"
        data = self._request_with_backoff(url)
        vote_raw = data["results"]["votes"]
        congress_vote_id = (
            f"{vote_raw['congress']}/{vote_raw['chamber'].lower()}"
            f"/{vote_raw['session']}/{vote_raw['roll_call']}"
        )
        positions = [
            VotePosition(member_id=p["member_id"], vote_position=p["vote_position"])
            for p in vote_raw.get("positions", [])
        ]
        return VoteDetail(congress_vote_id=congress_vote_id, positions=positions)

    def _request_with_backoff(self, url: str) -> dict[str, Any]:
        """Execute a GET request, retrying on HTTP 429 with exponential backoff.

        On each 429 response the method reads the ``Retry-After`` header (in
        seconds) and sleeps for that duration before retrying. If the header is
        absent it falls back to the current ``delay`` value, which doubles on
        each attempt. After ``_MAX_RETRIES`` failed attempts the method raises
        ``CongressAPIError`` rather than sleeping forever.

        Non-429 errors (e.g. 404, 500) are raised immediately via
        ``httpx.Response.raise_for_status()`` without retry, since retrying
        those responses is unlikely to help.

        Parameters
        ----------
        url:
            Fully-qualified ProPublica API URL to GET.

        Returns
        -------
        dict:
            Parsed JSON response body.

        Raises
        ------
        CongressAPIError:
            When the 429 retry budget is exhausted.
        httpx.HTTPStatusError:
            On any non-429 HTTP error response.
        """
        delay = 1
        for attempt in range(_MAX_RETRIES + 1):
            resp = self._http.get(url, headers={"X-API-Key": self._api_key})
            if resp.status_code == 429:
                if attempt == _MAX_RETRIES:
                    raise CongressAPIError(
                        f"Rate limit exceeded after {_MAX_RETRIES} retries: {url}"
                    )
                # Honour the Retry-After header if present; otherwise use the
                # exponential backoff delay.
                retry_after = int(resp.headers.get("Retry-After", delay))
                time.sleep(retry_after)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        raise CongressAPIError(f"Request failed after {_MAX_RETRIES} retries: {url}")

    @staticmethod
    def _parse_recent_vote(raw: dict[str, Any]) -> RecentVote:
        """Parse a single vote object from the recent-votes API response.

        Constructs the internal ``congress_vote_id`` composite key from the
        four fields that uniquely identify a roll-call vote in the ProPublica
        API: congress, chamber, session, and roll_call.

        The ``bill`` field is ``None`` for procedural votes (motions to table,
        rule adoptions, etc.) — in that case both ``congress_bill_id`` and
        ``bill_title`` are set to ``None`` in the returned dataclass. The sync
        engine skips such votes since they cannot be linked to a pledge.

        Parameters
        ----------
        raw:
            A single vote dict from ``results.votes[]`` in the API response.

        Returns
        -------
        RecentVote:
            Parsed and typed representation of the vote summary.
        """
        chamber = str(raw["chamber"]).lower()
        congress_vote_id = f"{raw['congress']}/{chamber}/{raw['session']}/{raw['roll_call']}"

        # ``bill`` may be explicitly ``null`` in the JSON for procedural votes,
        # so we normalise to an empty dict before accessing keys.
        bill = raw.get("bill") or {}
        return RecentVote(
            congress_vote_id=congress_vote_id,
            congress=int(raw["congress"]),
            chamber=chamber,
            session=int(raw["session"]),
            roll_call=int(raw["roll_call"]),
            date=raw["date"],
            time=raw["time"],
            congress_bill_id=bill.get("bill_id") or None,
            bill_title=bill.get("title") or None,
            result=raw.get("result", ""),
        )


def get_congress_client() -> CongressClient:
    """FastAPI dependency factory — return a configured ProPublica client.

    Reads ``CONGRESS_API_KEY`` from the environment. Raises ``KeyError`` if
    the variable is not set, which will crash the request rather than silently
    making unauthenticated calls.

    This function is registered as a FastAPI dependency in the admin router.
    In tests, override it via ``app.dependency_overrides`` to inject a
    ``FakeCongressClient`` that never makes network calls.

    Returns
    -------
    CongressClient:
        A ``ProPublicaCongressClient`` configured with the API key from the
        environment.
    """
    return ProPublicaCongressClient(api_key=os.environ["CONGRESS_API_KEY"])
