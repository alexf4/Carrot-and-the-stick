"use client";

import type { VoteHistoryItem } from "../lib/api";
import styles from "./VoteHistoryTable.module.css";

function formatDollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

interface Props {
  votes: VoteHistoryItem[];
}

type Outcome = "yes" | "no" | "absent" | "present" | "pending";

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
            <th>Outcome</th>
            <th className={styles.right}>Carrot Pool</th>
            <th className={styles.right}>Stick Pool</th>
          </tr>
        </thead>
        <tbody>
          {votes.map((v) => {
            const outcome: Outcome = v.rep_outcome ?? "pending";
            const yesPool = v.pledges.yes_pool_cents;
            const noPool = v.pledges.no_pool_cents;

            return (
              <tr key={v.vote_id}>
                <td>
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
                  <span className={styles.outcomeBadge} data-outcome={outcome}>
                    {OUTCOME_LABELS[outcome]}
                  </span>
                </td>
                <td className={styles.money}>
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
