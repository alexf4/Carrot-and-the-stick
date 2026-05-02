---
Status: needs-triage
---

# PRD: Carrot and the Stick — MVP Platform

## Problem Statement

Citizens have no direct financial lever tied to how their representative votes on specific legislation. Existing political donation tools accept money into a general fund, creating no enforceable connection between a constituent's dollars and their rep's actual voting behavior. A constituent who cares deeply about a specific bill has no way to say: "I'll reward you if you vote yes, and fund your opponent if you don't." The result is that representatives bear no immediate, constituent-driven financial consequence for individual votes.

## Solution

Carrot and the Stick is a conditional-donation platform. A constituent pledges money tied to a specific bill and a direction (YES or NO). Stripe charges the pledge immediately and the funds are held in the platform's super PAC HYSA. When the vote resolves, the outcome is evaluated per pledge: if the rep voted correctly, the pledge becomes a **Carrot** (earmarked for the rep's support PAC); if the rep voted wrong, is absent, or votes "present," it becomes a **Stick** (earmarked for the opponent's PAC). All held funds disburse in one batch 60 days before election day.

Constituents are notified via email when a relevant vote is scheduled. They receive an AI-generated plain-language summary of the bill, then pledge directly from that email. A fully public rep dashboard makes pledge pools and voting history transparent to voters, journalists, and campaigns alike.

## User Stories

### Discovery & Awareness
1. As a constituent, I want to receive an email notification when a congressional vote is scheduled that affects my representative, so that I can engage before the vote happens.
2. As a constituent, I want to read a plain-language, three-sentence AI summary of the bill, so that I can understand what I'm pledging on without reading legislative text.
3. As a constituent, I want to see a public dashboard for my representative showing their full voting history and pledge pool totals, so that I can assess their accountability record before pledging.
4. As a journalist, I want to browse any representative's public dashboard without logging in, so that I can report on pledge pool sizes and voting patterns.
5. As a concerned citizen, I want to share a rep's dashboard on social media, so that I can raise awareness about pending votes.

### Account & Identity
6. As a new user, I want to sign up with just my email address via a magic link, so that I don't need to create and remember a password.
7. As a returning user, I want to log in via a magic link sent to my email, so that I can access my pledge history securely.
8. As a new user, I want to enter my zip code so that I can be matched to my House representative and two senators.
9. As a user, I want to confirm which representatives are mine, so that I know exactly who my pledges will target.
10. As a user, I want to see my current verification tier and what I'm eligible to pledge, so that I understand any donation limits before I try to pledge.

### Verification
11. As a user pledging under $50 lifetime, I want my address verified against USPS records, so that I can pledge with minimal friction.
12. As a user whose lifetime pledges reach $50, I want to be prompted to complete Tier 2 identity verification, so that my account is upgraded without interrupting my pledge flow.
13. As a user completing Tier 2 verification, I want to complete a Stripe Identity government ID check, so that my identity is verified and I can continue pledging above the $50 threshold.
14. As a user, I want to be clearly notified when I need to upgrade my verification tier before a pledge is processed, so that I'm not surprised by a failed transaction.

### Pledging
15. As a constituent, I want to pledge a specific dollar amount for my representative to vote YES on a bill, so that I can financially incentivize the outcome I want.
16. As a constituent, I want to pledge a specific dollar amount for my representative to vote NO on a bill, so that I can financially penalize the opposite outcome.
17. As a constituent, I want to see the total pledge pool for my representative on a given vote broken down by YES pledges and NO pledges, so that I know the financial stakes before I pledge.
18. As a constituent, I want to confirm my pledge details (amount, direction, rep, bill) before my card is charged, so that I don't make accidental pledges.
19. As a constituent, I want to receive a confirmation email after my pledge is charged, so that I have a record of my commitment.
20. As a constituent, I want to see all my active (held) pledges in my account, so that I can track my financial exposure.
21. As a constituent, I want to see the history of my resolved pledges (carrot vs. stick outcomes), so that I can see how effective my pledges have been.

### Vote Resolution
22. As a constituent, I want to receive an email when my representative's vote resolves and my pledge outcome is determined (carrot or stick), so that I know whether my rep voted correctly.
23. As a constituent, I want the email to clearly state whether my pledge became a carrot (rep voted correctly) or a stick (rep voted wrong), so that the outcome is unambiguous.
24. As a constituent, I want absent or "present" votes counted as the wrong way, so that my representative cannot dodge accountability by abstaining.

### Disbursement
25. As a constituent, I want to know that all held funds will disburse 60 days before election day, so that I understand the timeline of political impact.
26. As a constituent, I want carrot funds to route to my representative's support super PAC, so that I know my pledge rewards correct votes.
27. As a constituent, I want stick funds to route to the opposing party's super PAC, so that I know my pledge punishes incorrect votes.
28. As a constituent whose rep retires, dies, or loses their primary, I want my held pledges automatically refunded, so that my money isn't disbursed to an inactive race.

### Rep Dashboard (Public)
29. As a visitor, I want to see a representative's name, party, chamber, state, and district on their public dashboard, so that I can identify them immediately.
30. As a visitor, I want to see the total carrot pool and total stick pool for a representative, so that I understand their financial accountability position.
31. As a visitor, I want to see a per-vote breakdown of pledge totals (YES pledges, NO pledges, outcome), so that I can assess which votes attracted the most constituent pressure.
32. As a visitor, I want the rep dashboard to be SEO-indexed, so that searches for a rep's name surface their pledge accountability record.
33. As a visitor, I want to browse all representatives, filterable by state, chamber, and party, so that I can explore the platform without knowing a specific rep.

### Admin & Operations
34. As a platform operator, I want congressional vote data to sync automatically from ProPublica in the background, so that no manual data entry is needed.
35. As a platform operator, I want bill summaries to be auto-generated by the Claude API at sync time, so that every notification email includes a plain-language summary without manual writing.
36. As a platform operator, I want disbursement to be triggered on a scheduled job 60 days before each election day, so that funds route reliably without manual intervention.
37. As a platform operator, I want Stripe webhook events to update pledge statuses automatically, so that payment failures and successes are reflected in real time.

---

## Implementation Decisions

### Modules

**Congress Sync**
Background service that polls the ProPublica Congress API, upserts new `bills`, `votes`, and `vote_outcomes` records, and triggers downstream processing (summarization, notifications, resolution) when new data arrives. Encapsulates all ProPublica API complexity. Runs on a scheduled interval.

**Vote Summarizer**
Stateless service that accepts a `Bill` record and returns a Claude-generated plain-language summary (3 sentences max). Writes the result to `bills.summary_ai`. Isolated from the sync loop so it can be retried independently.

**Rep Matching**
Service that maps a zip code to its congressional representatives (one House member + two senators). Wraps a zip-to-district data source (USPS API or SmartyStreets) and returns a list of `Representative` records. Stateless and cacheable.

**Notification Engine**
Given a newly scheduled `vote_id`, finds all `user_representatives` rows linked to affected representatives, renders an email template (including the AI bill summary), and dispatches via the configured email provider. Tracks sends to prevent duplicates.

**Verification Service**
Manages both verification tiers. Tier 1 calls the USPS/SmartyStreets API to validate a zip code against the user's address. Tier 2 initiates a Stripe Identity session and handles the webhook callback to update the user's `verification_tier`. Emits a domain event when a user upgrades tiers, so in-flight pledges can resume.

**Pledge Engine**
Core transactional module. Validates pledge eligibility (user must be a confirmed constituent of the rep, vote must be unresolved, user's verification tier must allow the amount), creates a Stripe PaymentIntent, and persists the `pledge` record with status `held`. The only module allowed to create pledges.

**Stripe Webhook Handler**
Receives Stripe webhook events, verifies signatures, and routes to the Pledge Engine (payment succeeded/failed) or Verification Service (Stripe Identity result). No business logic lives here — it delegates immediately.

**Vote Resolution Engine**
When a `vote_outcome` is recorded for a vote, loads all `held` pledges for that vote and representative, evaluates direction vs. outcome (`absent`/`present` = wrong), and updates pledge status to `disbursed_carrot` or `disbursed_stick`. Records the resolution timestamp. Idempotent — safe to re-run.

**Disbursement Engine**
Scheduled batch job triggered 60 days before each `next_election_date`. Aggregates all `disbursed_carrot` and `disbursed_stick` pledges per race, calculates PAC routing totals, creates a `disbursements` record, and executes the fund transfers. Handles the refund path for reps who are inactive (`is_active = false`).

**Dashboard API**
Public read-only REST endpoints powering the rep dashboard: rep profile, vote history with pledge breakdowns, and platform-wide aggregate stats. No auth required. Designed for SEO-friendliness (server-renderable data).

**Auth & User Management**
Supabase Auth magic-link flows for signup and login. User profile CRUD (zip code, verification tier). Exposes user's `user_representatives` list and pledge history.

**Frontend**
React + Vite, mobile-web first. Three primary surfaces:
- **Public Rep Dashboard** — rep profile, vote history, pledge pool totals (no auth required)
- **Pledge Flow** — pledge form (amount, direction, rep, confirmation), verification upgrade prompts, post-pledge confirmation screen
- **User Account** — active pledges, pledge history, verification tier status

### Architecture

- Backend: FastAPI (Python) with async background tasks for sync jobs
- Database: Supabase (PostgreSQL). Row-level security via Supabase Auth for user-scoped data; public read access for rep dashboard data
- Hosting: Railway
- Auth: Supabase Auth (magic link only at launch)
- Payments: Stripe (PaymentIntents for immediate charge, Stripe Identity for Tier 2)
- Email: TBD (Resend or SendGrid) — single transactional email provider
- Vote Data: ProPublica Congress API
- Address Validation: USPS API / SmartyStreets (Tier 1)
- AI Summaries: Claude API (claude-sonnet-4-6 or newer)

### Key Business Rules (encoded in modules)

- `absent` and `present` vote outcomes are treated identically to voting the wrong way (stick)
- Stripe charges occur immediately at pledge creation — no authorization holds
- A pledge can only be created by a user who has a confirmed `user_representatives` row for the target rep
- Tier 1 (USPS) covers lifetime pledges under $50; Tier 2 (Stripe Identity) required at $50+
- `is_active = false` on a rep triggers auto-refund of all `held` pledges for that rep
- Disbursement routes carrot funds to the rep's `support_destination` PAC and stick funds to the race's `oppose_destination` PAC
- Standing/recurring pledges are out of scope; all pledges are one-time and manual
- Notifications at launch: email only

### Schema Notes

- `pledges.status` lifecycle: `held` → `disbursed_carrot` | `disbursed_stick` | `refunded`
- `disbursements` table records each batch event with total carrot/stick cents and execution timestamp
- `vote_outcomes.outcome` enum: `yes`, `no`, `absent`, `present`
- `users.total_pledged_lifetime_cents` is an append-only counter used to trigger tier upgrade prompts

---

## Testing Decisions

**Philosophy:** Tests assert observable external behavior — what goes in and what comes out — not internal implementation details. Do not test private methods, internal state, or which sub-functions were called. A test should survive an internal refactor as long as the module's contract stays the same.

**Modules to test (priority order):**

1. **Vote Resolution Engine** — highest business risk. Given a `vote_outcome`, assert that pledges with correct direction become carrot and all others (wrong direction, absent, present) become stick. Test idempotency.

2. **Pledge Engine** — core financial logic. Assert eligibility checks (wrong rep, unresolved vote only, tier limits), Stripe PaymentIntent creation, and pledge record state. Use Stripe test mode; mock only at the HTTP boundary.

3. **Disbursement Engine** — irreversible financial action. Assert correct carrot/stick aggregation per race, PAC routing, and that `is_active = false` reps trigger refunds instead of disbursement.

4. **Verification Service** — tier transition logic. Assert that a user at the $50 lifetime threshold is blocked from pledging until Tier 2 is completed, and that the tier upgrade correctly unlocks subsequent pledges.

5. **Rep Matching** — pure function. Given a zip code, assert correct House rep and senator list. Test edge cases: zip crosses district boundaries, zip with no active rep.

6. **Vote Summarizer** — integration with Claude API. Assert that a bill summary is ≤3 sentences and under the character budget. Use recorded HTTP cassettes or a test Claude key in CI.

7. **Congress Sync** — contract tests against ProPublica response fixtures. Assert correct upsert behavior for bills, votes, and outcomes. Do not test ProPublica's API itself.

8. **Notification Engine** — assert that a new vote triggers one email per constituent, that the email includes the bill summary, and that duplicate sends are suppressed.

**Prior art:** No existing tests in the codebase yet. Establish `pytest` + `pytest-asyncio` as the test harness. Use `respx` or `httpx`'s mock transport for HTTP boundary mocking.

---

## Out of Scope

- Standing/recurring pledges — all pledges are manual and one-time at launch
- SMS or push notifications — email only at launch
- Non-federal (state, local) representatives — federal House and Senate only
- Multiple disbursement events per election cycle — one batch, 60 days pre-election
- Direct bank transfers or ACH payments — Stripe card only at launch
- In-app pledge editing or cancellation after charge
- Support for independent or third-party candidate PACs beyond D/R opposition routing
- Native mobile apps — mobile-web only
- Multi-currency or non-USD pledges
- Pledge anonymization or privacy tiers — all pledge pools are public aggregates

---

## Further Notes

- The platform operates as a super PAC vehicle. Legal/FEC compliance for PAC registration, contribution limits, and disbursement reporting must be validated by counsel before launch.
- The rep-to-PAC mapping (support/oppose destinations) requires an OpenSecrets API integration or manual curation. This mapping must be available before disbursement runs.
- Election day dates for `next_election_date` need to be seeded/maintained. The disbursement trigger depends on accurate dates for all active reps.
- The `total_pledged_lifetime_cents` counter on `users` must be incremented transactionally with pledge creation to avoid race conditions at the tier boundary.
- ProPublica's Congress API has rate limits; the Congress Sync module should implement exponential backoff and respect `Retry-After` headers.
