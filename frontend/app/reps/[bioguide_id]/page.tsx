/**
 * Representative detail page — `/reps/[bioguide_id]`.
 *
 * The public accountability dashboard for a single representative. Shows:
 * 1. Hero card — photo (or initials), name, party/chamber badges, state/district.
 * 2. Pledge summary — two cards showing total Carrot and Stick pool amounts.
 * 3. Vote history — full ledger table of this rep's congressional votes.
 *
 * This page is intentionally public and SEO-indexed (per DESIGN.md). It
 * does not require authentication. `generateMetadata` returns a unique
 * `<title>` and `<meta description>` for every rep so search engines can
 * index each page independently.
 *
 * Data fetching
 * -------------
 * `getRepDetail` fetches from the backend detail endpoint which runs two
 * queries: vote history (with pledge pool aggregates per vote) and lifetime
 * pledge totals. Both queries use `cache: "no-store"` for fresh data.
 *
 * 404 handling
 * ------------
 * `getRepDetail` returns `null` for unknown bioguide IDs. We call Next.js
 * `notFound()` which renders the closest `not-found.tsx` boundary (or the
 * default Next.js 404 page) with a proper 404 HTTP status code.
 *
 * Photo handling
 * --------------
 * Same as RepCard: plain `<img>` rather than Next.js `<Image>` because
 * the ProPublica CDN domain is not enumerable in `next.config.ts`. An
 * initials fallback is shown when `photo_url` is null.
 *
 * Pledge summary cards
 * --------------------
 * Carrot and Stick amounts are the rep's lifetime *disbursed* totals, not
 * the current held balance. Held pledges (pending votes) are excluded because
 * they haven't resolved yet — showing them would misrepresent the rep's
 * actual accountability record. See `RepAggregatePool` in `api.ts`.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRepDetail } from "../../../lib/api";
import { VoteHistoryTable } from "../../../components/VoteHistoryTable";
import styles from "./page.module.css";

interface PageProps {
  /** Next.js App Router passes dynamic route params as a Promise in async RSCs. */
  params: Promise<{ bioguide_id: string }>;
}

/**
 * Derive two-letter initials from a representative's display name.
 *
 * Duplicated from RepCard.tsx rather than shared via a utility module because
 * this page uses the initials in a larger hero avatar (88px vs 64px) and
 * calling a shared utility would require either a client boundary (if the
 * utility is in a "use client" file) or an extra module just for one helper.
 * Three lines of duplication is preferable to a premature abstraction here.
 *
 * @param name - Full display name, e.g. "Jane Smith" → "JS".
 * @returns One or two uppercase initials.
 */
function getInitials(name: string): string {
  return name
    .split(" ")
    .filter((p) => p.length > 1)
    .slice(0, 2)
    .map((p) => p[0])
    .join("");
}

/**
 * Generate per-rep metadata for SEO.
 *
 * Called by Next.js at request time (for dynamic routes). Returns a 404-safe
 * fallback if the rep is not found rather than throwing, so the 404 page can
 * render with its own title.
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { bioguide_id } = await params;
  const rep = await getRepDetail(bioguide_id);
  if (!rep) return { title: "Representative Not Found | Carrot and the Stick" };
  return {
    title: `${rep.name} (${rep.party}-${rep.state}) | Carrot and the Stick`,
    description: `Vote history and pledge pools for ${rep.name}, ${rep.chamber === "house" ? "U.S. Representative" : "U.S. Senator"} from ${rep.state}.`,
  };
}

/**
 * RepDetailPage — server component rendering the rep accountability dashboard.
 *
 * Fetches rep detail, converts cent amounts to dollar strings for display,
 * and renders the three-section layout: hero, pledge summary, vote history.
 *
 * @param params - Resolved route params containing the bioguide_id slug.
 */
export default async function RepDetailPage({ params }: PageProps) {
  const { bioguide_id } = await params;
  const rep = await getRepDetail(bioguide_id);

  // Trigger Next.js 404 page — rep does not exist in the database.
  if (!rep) notFound();

  // Convert stored cent integers to dollar strings for display.
  const carrotDollars = (rep.pledge_aggregate.total_carrot_cents / 100).toFixed(2);
  const stickDollars = (rep.pledge_aggregate.total_stick_cents / 100).toFixed(2);

  // Build human-readable chamber label and optional district suffix.
  const chamberLabel = rep.chamber === "house" ? "U.S. Representative" : "U.S. Senator";
  const districtLabel =
    rep.chamber === "house" && rep.district != null ? `, District ${rep.district}` : "";

  return (
    <div>
      {/* Back navigation — breadcrumb-style, not a full nav bar */}
      <Link href="/reps" className={styles.back}>
        <span className={styles.backArrow}>←</span> All Representatives
      </Link>

      {/* Hero section: photo + name + badges */}
      <div className={styles.hero}>
        {rep.photo_url ? (
          /* Plain <img> — see module docstring for the ProPublica CDN constraint. */
          <img src={rep.photo_url} alt={rep.name} className={styles.heroPhoto} />
        ) : (
          <div className={styles.heroPhotoPlaceholder}>{getInitials(rep.name)}</div>
        )}
        <div className={styles.heroInfo}>
          <div className={styles.heroBadges}>
            {/* data-party drives CSS attribute selectors for party-coded badge colors */}
            <span className={styles.partyBadge} data-party={rep.party}>{rep.party}</span>
            <span className={styles.chamberBadge}>{rep.chamber === "house" ? "House" : "Senate"}</span>
          </div>
          <h1 className={styles.heroName}>{rep.name}</h1>
          <p className={styles.heroMeta}>
            {chamberLabel} · {rep.state}{districtLabel}
          </p>
        </div>
      </div>

      {/* Pledge summary: two cards, amber carrot / red stick */}
      <div className={styles.pledgeSummary}>
        <div className={`${styles.pledgeCard} ${styles.pledgeCardCarrot}`}>
          <div className={`${styles.pledgeLabel} ${styles.pledgeLabelCarrot}`}>Carrot Pool</div>
          <div className={`${styles.pledgeAmount} ${styles.pledgeAmountCarrot}`}>${carrotDollars}</div>
          <div className={styles.pledgeSubtext}>Pledged for compliant votes</div>
        </div>
        <div className={`${styles.pledgeCard} ${styles.pledgeCardStick}`}>
          <div className={`${styles.pledgeLabel} ${styles.pledgeLabelStick}`}>Stick Pool</div>
          <div className={`${styles.pledgeAmount} ${styles.pledgeAmountStick}`}>${stickDollars}</div>
          <div className={styles.pledgeSubtext}>Pledged against non-compliant votes</div>
        </div>
      </div>

      {/* Vote history ledger table */}
      <section>
        <h2 className={styles.sectionHeading}>Vote History</h2>
        <VoteHistoryTable votes={rep.vote_history} />
      </section>
    </div>
  );
}
