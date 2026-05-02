/**
 * API client — typed fetch wrappers for the FastAPI backend.
 *
 * This module is the single source of truth for all HTTP calls from the
 * Next.js frontend to the backend. It owns:
 *
 * - TypeScript interfaces that mirror the backend Pydantic response schemas.
 * - Fetch wrappers with error handling and `cache: "no-store"` (server-side
 *   Next.js components need fresh data on every request; we do not cache
 *   rep data in the CDN layer at this stage).
 *
 * Architecture notes
 * ------------------
 * All functions in this module are intended to be called from Next.js Server
 * Components (async RSC). They are plain `async` functions — not React hooks
 * — so they can be used in any async context without a client boundary.
 *
 * The `API_URL` is read from the environment at runtime, not build time.
 * In development this defaults to `http://localhost:8000`. In production
 * (Railway), `API_URL` is injected via the Next.js `env` config in
 * `next.config.ts`.
 *
 * Error handling
 * --------------
 * All fetchers throw on non-OK HTTP responses. 404 is the one exception:
 * `getRepDetail` returns `null` on 404 so callers can invoke `notFound()`
 * themselves (giving Next.js a chance to render the 404 page with the
 * correct status code rather than a thrown error page).
 */

/** Base URL for the FastAPI backend. Configured via next.config.ts `env`. */
const API_URL = process.env.API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Response types — mirror backend Pydantic schemas in reps.py
// ---------------------------------------------------------------------------

/**
 * Minimal representative summary used in browse lists and as the base for
 * RepDetail. Maps 1:1 to the backend `RepResponse` Pydantic schema.
 */
export interface RepSummary {
  id: string;
  bioguide_id: string;
  name: string;
  party: string;
  chamber: "house" | "senate";
  state: string;
  /** House district number; null for senators. */
  district: number | null;
  /** ProPublica CDN headshot URL; null if no photo on file. */
  photo_url: string | null;
  is_active: boolean;
}

/**
 * Aggregated pledge pool amounts for a single vote, split by constituent
 * direction. Maps to `VotePledgeAggregates` on the backend.
 */
export interface VotePledgeAggregates {
  /** Sum of pledge amounts (cents) from constituents wanting the rep to vote YES. */
  yes_pool_cents: number;
  /** Sum of pledge amounts (cents) from constituents wanting the rep to vote NO. */
  no_pool_cents: number;
}

/**
 * A single vote in a rep's history, with pledge pool totals.
 * Maps to `VoteHistoryItem` on the backend.
 */
export interface VoteHistoryItem {
  vote_id: string;
  bill_title: string;
  /** ISO 8601 timestamp string. */
  scheduled_at: string;
  /** ISO 8601 timestamp string; null if the vote has not yet resolved. */
  resolved_at: string | null;
  /** How the rep voted, or null if the vote is still pending. */
  rep_outcome: "yes" | "no" | "absent" | "present" | null;
  pledges: VotePledgeAggregates;
}

/**
 * Lifetime disbursed pledge totals for a representative.
 * Maps to `RepAggregatePool` on the backend.
 */
export interface RepAggregatePool {
  /** Total carrot disbursements in cents (rep voted correctly). */
  total_carrot_cents: number;
  /** Total stick disbursements in cents (rep voted non-compliantly). */
  total_stick_cents: number;
}

/**
 * Full representative detail including vote history and pledge aggregates.
 * Extends RepSummary; maps to `RepDetailResponse` on the backend.
 */
export interface RepDetail extends RepSummary {
  vote_history: VoteHistoryItem[];
  pledge_aggregate: RepAggregatePool;
}

/** Backend response envelope for the browse endpoint. */
export interface BrowseRepsResponse {
  reps: RepSummary[];
  /** Total count of matching reps (equals reps.length; pagination TBD). */
  total: number;
}

/**
 * Optional filter parameters for the browse endpoint.
 * All fields are optional; omitting them returns all active reps.
 */
export interface BrowseParams {
  /** Two-letter state code, e.g. "VA". Case-sensitive. */
  state?: string;
  chamber?: "house" | "senate";
  /** Party code, e.g. "D" or "R". Case-sensitive. */
  party?: string;
}

// ---------------------------------------------------------------------------
// Fetch wrappers
// ---------------------------------------------------------------------------

/**
 * Fetch a filtered list of active representatives from the browse endpoint.
 *
 * Called from the `/reps` Server Component on every request. Any provided
 * filter params are forwarded as query string parameters.
 *
 * @param params - Optional state/chamber/party filters.
 * @returns Reps list and total count.
 * @throws Error if the backend returns a non-OK status.
 */
export async function getBrowseReps(params?: BrowseParams): Promise<BrowseRepsResponse> {
  const url = new URL(`${API_URL}/reps/browse`);
  if (params?.state) url.searchParams.set("state", params.state);
  if (params?.chamber) url.searchParams.set("chamber", params.chamber);
  if (params?.party) url.searchParams.set("party", params.party);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch reps: ${res.status}`);
  return res.json() as Promise<BrowseRepsResponse>;
}

/**
 * Fetch full detail for a single representative by bioguide_id.
 *
 * Returns null on 404 so callers can invoke Next.js `notFound()` and
 * render the proper 404 page. All other non-OK responses throw.
 *
 * @param bioguideId - ProPublica bioguide identifier, e.g. "H001234".
 * @returns RepDetail if found, null if the rep does not exist.
 * @throws Error if the backend returns a non-OK status other than 404.
 */
export async function getRepDetail(bioguideId: string): Promise<RepDetail | null> {
  const res = await fetch(`${API_URL}/reps/${bioguideId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to fetch rep ${bioguideId}: ${res.status}`);
  return res.json() as Promise<RepDetail>;
}
