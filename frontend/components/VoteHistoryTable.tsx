/**
 * VoteHistoryTable — ledger-style table of a representative's vote record.
 *
 * Renders the full vote history for a single rep on their detail page. Each
 * row represents one congressional floor vote and shows:
 *
 * - Bill title (truncated with CSS overflow ellipsis; full title in the
 *   `title` attribute for hover tooltips)
 * - Scheduled date (formatted as "MMM D, YYYY" for scannability)
 * - Rep outcome badge (color-coded: green=yes, red=no, gray=absent,
 *   yellow=present, muted=pending)
 * - Carrot pool total (amber — pledges that become carrots if rep voted yes)
 * - Stick pool total (red — pledges that become sticks if rep voted wrong)
 *
 * Domain language reminder
 * ------------------------
 * The column headers say "Carrot Pool" and "Stick Pool", not "Yes Pool" and
 * "No Pool". A Carrot is a pledge that resolved in the constituent's favour;
 * a Stick is one that didn't. The column header labels the intent, not the
 * raw direction — consistent with UBIQUITOUS_LANGUAGE.md.
 *
 * Money formatting
 * ----------------
 * All amounts are stored as integer cents in the database. `formatDollars`
 * converts to dollars with two decimal places. Money is rendered in
 * JetBrains Mono (via `--font-mono`) for alignment in the right-aligned
 * columns. Zero amounts render in the muted text color to reduce visual
 * noise on votes with no pledges yet.
 *
 * Pending votes
 * -------------
 * When `rep_outcome` is null the vote has not yet resolved. The outcome
 * badge shows "Pending" in a neutral muted style. Pool amounts may already
 * be non-zero if constituents have placed pledges in advance.
 */

"use client";

import type { VoteHistoryItem } from "../lib/api";
import styles from "./VoteHistoryTable.module.css";

/**
 * Convert a cent integer to a formatted dollar string.
 *
 * @param cents - Integer amount in US cents (e.g. 5000 → "$50.00").
 * @returns Dollar string with exactly two decimal places.
 */
function formatDollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

interface Props {
  /** Ordered list of vote history items for a single representative.
   *  Should be pre-sorted descending by scheduled_at (most recent first),
   *  as returned by the backend `/reps/{bioguide_id}` endpoint. */
  votes: VoteHistoryItem[];
}

/** Union of all possible rep outcome strings plus the synthetic "pending" state. */
type Outcome = "yes" | "no" | "absent" | "present" | "pending";

/**
 * Human-readable labels for each outcome value, used in the badge text.
 * Capitalised so CSS `text-transform: uppercase` is not required in the
 * badge styles (the CSS badge already applies its own letter-spacing).
 */
const OUTCOME_LABELS: Record<Outcome, string> = {
  yes: "Yes",
  no: "No",
  absent: "Absent",
  present: "Present",
  pending: "Pending",
};

export function VoteHistoryTable({ votes }: Props) {
  if (votes.length === 0) {
    return <p className={styles.empty}>No votes on record.</p>;
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Bill</th>
            <th>Date</th>
            {/* "Outcome" = how the rep actually voted, not what constituents wanted */}
            <th>Outcome</th>
            {/* Carrot/Stick pool headers use domain language from UBIQUITOUS_LANGUAGE.md */}
            <th className={styles.right}>Carrot Pool</th>
            <th className={styles.right}>Stick Pool</th>
          </tr>
        </thead>
        <tbody>
          {votes.map((v) => {
            // Coerce null rep_outcome to our synthetic "pending" sentinel so
            // OUTCOME_LABELS lookup is always defined.
            const outcome: Outcome = v.rep_outcome ?? "pending";
            const yesPool = v.pledges.yes_pool_cents;
            const noPool = v.pledges.no_pool_cents;

            return (
              <tr key={v.vote_id}>
                <td>
                  {/* title attr provides full text on hover when the cell truncates */}
                  <div className={styles.billTitle} title={v.bill_title}>
                    {v.bill_title}
                  </div>
                </td>
                <td className={styles.date}>
                  {new Date(v.scheduled_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </td>
                <td>
                  {/* data-outcome drives CSS attribute selectors for color-coded badges */}
                  <span className={styles.outcomeBadge} data-outcome={outcome}>
                    {OUTCOME_LABELS[outcome]}
                  </span>
                </td>
                <td className={styles.money}>
                  {/* Amber color only when there's actual money; muted gray for $0 */}
                  <span className={yesPool > 0 ? styles.moneyCarrot : styles.moneyZero}>
                    {formatDollars(yesPool)}
                  </span>
                </td>
                <td className={styles.money}>
                  <span className={noPool > 0 ? styles.moneyStick : styles.moneyZero}>
                    {formatDollars(noPool)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
