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
  searchParams: Promise<{ state?: string; chamber?: string; party?: string }>;
}

export default async function BrowseRepsPage({ searchParams }: PageProps) {
  const params = await searchParams;
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
