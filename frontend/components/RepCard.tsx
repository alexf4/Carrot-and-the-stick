"use client";

import type { RepSummary } from "../lib/api";
import styles from "./RepCard.module.css";

interface Props {
  rep: RepSummary;
}

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
  const districtLabel =
    rep.chamber === "house" && rep.district != null ? `District ${rep.district}` : null;

  return (
    <div className={styles.card}>
      {rep.photo_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={rep.photo_url} alt={rep.name} className={styles.photo} />
      ) : (
        <div className={styles.photoPlaceholder}>{getInitials(rep.name)}</div>
      )}

      <div className={styles.info}>
        <div className={styles.badges}>
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
