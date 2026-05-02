/**
 * Browse Representatives page — `/reps`.
 *
 * This is the main public landing page (the home route redirects here).
 * It renders a filterable grid of all active representatives, powered by
 * the backend `GET /reps/browse` endpoint.
 *
 * Filtering
 * ---------
 * Filters are applied via native HTML form submission (GET method), so the
 * URL query string always reflects the current filter state. This means:
 * - Filter state is shareable via URL.
 * - No client-side JavaScript is needed for filtering (works with JS
 *   disabled — important for an SEO-indexed public page).
 * - Server component re-renders on each navigation, fetching fresh data.
 *
 * The three available filters map directly to backend query params:
 * - `state`: two-letter state code (case-sensitive, stored uppercase in DB)
 * - `chamber`: "house" or "senate"
 * - `party`: party code ("D", "R", "I")
 *
 * Data fetching
 * -------------
 * `getBrowseReps` is called with `cache: "no-store"` — rep data updates
 * when the congress sync job runs, so we always want the freshest list.
 *
 * Rendering
 * ---------
 * Each rep card is wrapped in a Next.js `<Link>` pointing to
 * `/reps/{bioguide_id}`. The card itself is a `<div>` (not a button or
 * anchor) so the outer Link provides the only interactive affordance.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { getBrowseReps } from "../../lib/api";
import { RepCard } from "../../components/RepCard";
import type { BrowseParams } from "../../lib/api";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Browse Representatives | Carrot and the Stick",
  description: "Find and follow your representatives in Congress.",
};

interface PageProps {
  /** Next.js App Router passes search params as a Promise in async RSCs. */
  searchParams: Promise<{ state?: string; chamber?: string; party?: string }>;
}

/**
 * BrowseRepsPage — server component that fetches and renders the rep grid.
 *
 * Reads filter params from the URL search string, forwards them to the
 * backend browse endpoint, and renders a grid of RepCard components.
 * Shows an empty state message if no reps match the current filters.
 *
 * @param searchParams - Resolved URL search params with optional filter keys.
 */
export default async function BrowseRepsPage({ searchParams }: PageProps) {
  const params = await searchParams;

  // Build the typed BrowseParams object, ignoring invalid chamber values
  // (the select only emits "house" or "senate", but URL manipulation is possible).
  const browseParams: BrowseParams = {};
  if (params.state) browseParams.state = params.state;
  if (params.chamber === "house" || params.chamber === "senate") browseParams.chamber = params.chamber;
  if (params.party) browseParams.party = params.party;

  const { reps, total } = await getBrowseReps(browseParams);

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.heading}>Representatives</h1>
        <span className={styles.count}>{total}</span>
      </div>

      {/* Native GET form — no JS required for filtering */}
      <form method="get" className={styles.filterBar}>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel} htmlFor="state">State</label>
          <input
            id="state"
            name="state"
            className={styles.filterInput}
            defaultValue={params.state ?? ""}
            placeholder="e.g. VA"
          />
        </div>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel} htmlFor="chamber">Chamber</label>
          <select
            id="chamber"
            name="chamber"
            className={styles.filterSelect}
            defaultValue={params.chamber ?? ""}
          >
            <option value="">All</option>
            <option value="house">House</option>
            <option value="senate">Senate</option>
          </select>
        </div>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel} htmlFor="party">Party</label>
          <input
            id="party"
            name="party"
            className={styles.filterInput}
            defaultValue={params.party ?? ""}
            placeholder="e.g. D or R"
          />
        </div>
        <div className={styles.filterActions}>
          <button type="submit" className={styles.filterSubmit}>Filter</button>
          {/* Link to /reps with no query string clears all filters */}
          <Link href="/reps" className={styles.filterClear}>Clear</Link>
        </div>
      </form>

      {reps.length === 0 ? (
        <p className={styles.empty}>No representatives found for the selected filters.</p>
      ) : (
        <div className={styles.grid}>
          {reps.map((rep) => (
            <Link key={rep.bioguide_id} href={`/reps/${rep.bioguide_id}`} className={styles.repLink}>
              <RepCard rep={rep} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
