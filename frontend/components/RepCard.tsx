/**
 * RepCard — compact representative profile card.
 *
 * Renders a single active or inactive Representative's photo (or initials
 * fallback), party/chamber badges, full name, and state/district metadata.
 * Used in two contexts:
 *
 * 1. Browse grid (`/reps`): wrapped in a Next.js `<Link>` so the whole card
 *    is clickable and navigates to the rep's detail page.
 * 2. Detail page (`/reps/[bioguide_id]`): rendered standalone as a hero
 *    card above the vote history table. In this context there is no outer
 *    link wrapper.
 *
 * The component is marked `"use client"` because it may eventually add
 * interactivity (e.g. a follow/pledge CTA button). Server-component usage
 * is still safe — the client boundary only activates when JS is loaded.
 *
 * Photo handling
 * --------------
 * ProPublica provides `photo_url` for most reps, but some have no photo on
 * file. Rather than showing a blank box, we derive two-letter initials from
 * the rep's name and display them in a styled placeholder circle. The
 * `getInitials` helper is intentionally limited to two characters so it
 * fits the fixed-size circle at all font sizes.
 *
 * We use a plain `<img>` element rather than Next.js `<Image>` because the
 * ProPublica CDN domain is not predictable across all deployments and would
 * require enumerating domains in `next.config.ts`. The trade-off is that we
 * lose automatic format optimisation for these images.
 */

"use client";

import type { RepSummary } from "../lib/api";
import styles from "./RepCard.module.css";

interface Props {
  /** The representative to render. Accepts both RepSummary and RepDetail
   *  (which extends RepSummary), so this card can be used on both pages. */
  rep: RepSummary;
}

/**
 * Derive a two-letter initials string from a representative's display name.
 *
 * Splits on spaces, filters out single-character particles (e.g. "O'" prefixes
 * that get split oddly), takes the first two qualifying parts, and returns
 * their first characters uppercased. Returns at most two characters so the
 * result always fits in the fixed-size avatar circle.
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

export function RepCard({ rep }: Props) {
  const chamberLabel = rep.chamber === "house" ? "House" : "Senate";

  // District label is only shown for House members; senators have null district.
  const districtLabel =
    rep.chamber === "house" && rep.district != null ? `District ${rep.district}` : null;

  return (
    <div className={styles.card}>
      {rep.photo_url ? (
        /* Plain <img> — see module docstring for why we don't use Next/Image here. */
        <img src={rep.photo_url} alt={rep.name} className={styles.photo} />
      ) : (
        <div className={styles.photoPlaceholder}>{getInitials(rep.name)}</div>
      )}

      <div className={styles.info}>
        <div className={styles.badges}>
          {/* data-party drives CSS attribute selectors for party-coded colors */}
          <span className={styles.partyBadge} data-party={rep.party}>
            {rep.party}
          </span>
          <span className={styles.chamberBadge}>{chamberLabel}</span>
          {!rep.is_active && <span className={styles.inactiveChip}>Inactive</span>}
        </div>
        <div className={styles.name}>{rep.name}</div>
        <div className={styles.meta}>
          <span>{rep.state}</span>
          {districtLabel && (
            <>
              <span className={styles.metaDot}>•</span>
              <span>{districtLabel}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
