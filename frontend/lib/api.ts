const API_URL = process.env.API_URL ?? "http://localhost:8000";

export interface RepSummary {
  id: string;
  bioguide_id: string;
  name: string;
  party: string;
  chamber: "house" | "senate";
  state: string;
  district: number | null;
  photo_url: string | null;
  is_active: boolean;
}

export interface VotePledgeAggregates {
  yes_pool_cents: number;
  no_pool_cents: number;
}

export interface VoteHistoryItem {
  vote_id: string;
  bill_title: string;
  scheduled_at: string;
  resolved_at: string | null;
  rep_outcome: "yes" | "no" | "absent" | "present" | null;
  pledges: VotePledgeAggregates;
}

export interface RepAggregatePool {
  total_carrot_cents: number;
  total_stick_cents: number;
}

export interface RepDetail extends RepSummary {
  vote_history: VoteHistoryItem[];
  pledge_aggregate: RepAggregatePool;
}

export interface BrowseRepsResponse {
  reps: RepSummary[];
  total: number;
}

export interface BrowseParams {
  state?: string;
  chamber?: "house" | "senate";
  party?: string;
}

export async function getBrowseReps(params?: BrowseParams): Promise<BrowseRepsResponse> {
  const url = new URL(`${API_URL}/reps/browse`);
  if (params?.state) url.searchParams.set("state", params.state);
  if (params?.chamber) url.searchParams.set("chamber", params.chamber);
  if (params?.party) url.searchParams.set("party", params.party);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch reps: ${res.status}`);
  return res.json() as Promise<BrowseRepsResponse>;
}

export async function getRepDetail(bioguideId: string): Promise<RepDetail | null> {
  const res = await fetch(`${API_URL}/reps/${bioguideId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to fetch rep ${bioguideId}: ${res.status}`);
  return res.json() as Promise<RepDetail>;
}
