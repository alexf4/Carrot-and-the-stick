# Ubiquitous Language

## The Core Transaction

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Pledge** | A conditional payment a constituent makes, tied to a specific vote and a direction | Donation, contribution, commitment |
| **Direction** | The constituent's desired vote outcome for a pledge: `yes` or `no` | Preference, choice, side |
| **Carrot** | A pledge that resolved in the constituent's favor — the rep voted correctly | Reward, support funds |
| **Stick** | A pledge that resolved against the constituent — the rep voted wrong, was absent, or voted present | Penalty, punishment funds |
| **Pledge Pool** | The total held pledge amounts for a representative, broken down by direction and vote | Fund pool, donation pool |
| **Held** | The status of a pledge that has been charged but whose vote has not yet resolved | Pending, escrowed, locked |

## People & Roles

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Constituent** | The domain role of a user in relation to a representative — a citizen whose zip code maps to that rep's district | Donor, citizen, supporter |
| **User** | An authenticated identity in the system — may act as a Constituent for one or more Representatives | Account, login, member |
| **Representative** | A currently active federal elected official — a House member or Senator | Rep, politician, lawmaker, official |

## Legislation & Voting

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Bill** | Proposed federal legislation that is the subject of a Vote | Legislation, law, act (before passed) |
| **Vote** | A scheduled or resolved congressional floor vote on a Bill | Ballot, poll |
| **Vote Outcome** | How a Representative actually voted: `yes`, `no`, `absent`, or `present` | Result, tally, record |
| **Compliant Vote** | A Vote Outcome that matches the constituent's Direction (`yes` or `no`) | Correct vote, right vote |
| **Non-compliant Vote** | A Vote Outcome of the wrong direction, `absent`, or `present` — triggers a Stick | Wrong vote, bad vote, voting the wrong way |
| **Vote Summary** | An AI-generated plain-language description of a Bill, three sentences maximum | Summary, description, explainer |
| **Race** | An election contest for a specific seat between two or more candidates | Election, contest, matchup |

## Money & Compliance

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Disbursement** | The single batch transfer of all held pledge funds executed 60 days before Election Day | Payout, distribution, transfer |
| **Election Window** | The 60-day period before Election Day that triggers Disbursement | Disbursement window, election period |
| **Support Destination** | The super PAC that receives Carrot funds for a given Representative | Support PAC, rep's PAC |
| **Oppose Destination** | The opposing party's super PAC that receives Stick funds for a given Race | Opponent PAC, oppose PAC |
| **PAC Balance** | The total funds currently held across all pledges in the platform's HYSA | Escrow balance, total held funds |

## Identity & Verification

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Verification Tier** | The identity verification level of a User — determines the pledge amount they are authorized to make | Verification level, KYC tier |
| **Tier 1** | Address verification via USPS — required for lifetime pledges under $50 | Basic verification |
| **Tier 2** | Government ID check via Stripe Identity — required when lifetime pledges reach $50 or more | Full verification, identity verification |
| **Lifetime Pledges** | The running total of all pledge amounts charged to a User, used to determine Verification Tier | Total pledged, pledge history amount |

---

## Relationships

- A **Pledge** belongs to exactly one **Constituent**, one **Vote**, and one **Representative**
- A **Constituent** is a **User** in the context of a specific **Representative** — one User may be a Constituent of multiple Representatives
- A **Vote** belongs to one **Bill**; a **Bill** may have multiple **Votes**
- A **Vote Outcome** belongs to one **Vote** and one **Representative**
- A **Pledge** becomes a **Carrot** when its **Direction** matches the **Vote Outcome** (Compliant Vote)
- A **Pledge** becomes a **Stick** when the **Vote Outcome** is Non-compliant (`absent` and `present` count as Non-compliant)
- A **Pledge Pool** is the aggregate of all **Pledges** in `held`, `disbursed_carrot`, or `disbursed_stick` status for a given Representative
- **Disbursement** routes **Carrot** funds to the **Support Destination** and **Stick** funds to the **Oppose Destination**

---

## Example dialogue

> **Dev:** "When a **Constituent** makes a **Pledge**, do they choose which **Representative** it targets?"

> **Domain expert:** "Only their own Representatives — the ones confirmed by zip code. A **User** in Virginia who has confirmed their House rep and two senators can only **Pledge** against those three."

> **Dev:** "And if the rep votes present — is that a **Carrot** or a **Stick**?"

> **Domain expert:** "Always a **Stick**. Only a `yes` or `no` **Vote Outcome** that matches the **Direction** is a **Compliant Vote**. Absent and present are **Non-compliant** by definition — there's no neutral outcome."

> **Dev:** "So when does the **Pledge Pool** for a rep actually move? At **Disbursement**?"

> **Domain expert:** "Right. Pledges are charged immediately but stay **Held** in the **PAC Balance** until the **Election Window** opens. Then a single **Disbursement** routes all resolved funds — **Carrots** to the **Support Destination**, **Sticks** to the **Oppose Destination**."

> **Dev:** "What if the rep retires before the **Election Window**?"

> **Domain expert:** "Any **Held** pledges refund to the **Constituent**. Once a **Representative** is inactive, there's no **Race** to route funds to."

---

## Flagged ambiguities

- **"Donation" vs "Pledge"** — the word "donation" appears informally in conversation and in the pitch ("the Venmo of political accountability"). In the domain, the correct term is always **Pledge** — a donation is unconditional, a Pledge is not.

- **"User" vs "Constituent"** — these are distinct concepts that were used interchangeably in parts of the PRD. A **User** is an authentication identity. A **Constituent** is the relationship between a User and a Representative. One User can be a Constituent of up to three Representatives (one House rep, two senators). Code and conversation should never say "user pledges to their rep" — say "constituent pledges against their representative's vote."

- **"Support PAC" and "Support Destination"** — both appeared. **Support Destination** is canonical; "Support PAC" implies it is always a PAC, which may not hold for all rep types. Use Support Destination.

- **"Oppose PAC" and "Oppose Destination"** — same issue. **Oppose Destination** is canonical.

- **"Wrong vote" / "bad vote" / "voting the wrong way"** — multiple informal phrases used to describe the same concept. Canonical terms: **Non-compliant Vote** (for the outcome) and **Stick** (for the pledge consequence). Avoid all informal variants in code, API contracts, and documentation.

- **"Race"** — used in the PRD ("routes to opponent's PAC for the race") but absent from the original design glossary. Defined above. Distinct from **Vote** (a single floor vote) and **Election** (the broader event). A Race is the specific contest that determines which candidate wins a seat.
