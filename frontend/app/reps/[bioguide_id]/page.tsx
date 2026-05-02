import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRepDetail } from "../../../lib/api";
import { VoteHistoryTable } from "../../../components/VoteHistoryTable";
import styles from "./page.module.css";

interface PageProps {
  params: Promise<{ bioguide_id: string }>;
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter((p) => p.length > 1)
    .slice(0, 2)
    .map((p) => p[0])
    .join("");
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { bioguide_id } = await params;
  const rep = await getRepDetail(bioguide_id);
  if (!rep) return { title: "Representative Not Found | Carrot and the Stick" };
  return {
    title: `${rep.name} (${rep.party}-${rep.state}) | Carrot and the Stick`,
    description: `Vote history and pledge pools for ${rep.name}, ${rep.chamber === "house" ? "U.S. Representative" : "U.S. Senator"} from ${rep.state}.`,
  };
}

export default async function RepDetailPage({ params }: PageProps) {
  const { bioguide_id } = await params;
  const rep = await getRepDetail(bioguide_id);
  if (!rep) notFound();

  const carrotDollars = (rep.pledge_aggregate.total_carrot_cents / 100).toFixed(2);
  const stickDollars = (rep.pledge_aggregate.total_stick_cents / 100).toFixed(2);
  const chamberLabel = rep.chamber === "house" ? "U.S. Representative" : "U.S. Senator";
  const districtLabel =
    rep.chamber === "house" && rep.district != null ? `, District ${rep.district}` : "";

  return (
    <div>
      <Link href="/reps" className={styles.back}>
        <span className={styles.backArrow}>←</span> All Representatives
      </Link>

      <div className={styles.hero}>
        {rep.photo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={rep.photo_url} alt={rep.name} className={styles.heroPhoto} />
        ) : (
          <div className={styles.heroPhotoPlaceholder}>{getInitials(rep.name)}</div>
        )}
        <div className={styles.heroInfo}>
          <div className={styles.heroBadges}>
            <span className={styles.partyBadge} data-party={rep.party}>{rep.party}</span>
            <span className={styles.chamberBadge}>{rep.chamber === "house" ? "House" : "Senate"}</span>
          </div>
          <h1 className={styles.heroName}>{rep.name}</h1>
          <p className={styles.heroMeta}>
            {chamberLabel} · {rep.state}{districtLabel}
          </p>
        </div>
      </div>

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

      <section>
        <h2 className={styles.sectionHeading}>Vote History</h2>
        <VoteHistoryTable votes={rep.vote_history} />
      </section>
    </div>
  );
}
