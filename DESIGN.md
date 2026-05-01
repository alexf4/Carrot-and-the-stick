# Carrot and the Stick — Design Concept

## One-Line Pitch
The Venmo of political accountability: citizens make conditional donations to their federal representatives, earned only if the rep votes the right way.

## Core Loop
1. A vote is scheduled in Congress
2. Constituent gets an email notification with an AI-generated plain-language summary
3. Constituent pledges $X for their rep to vote YES or NO
4. Money is charged immediately via Stripe and parked in the platform's super PAC HYSA
5. Vote resolves — rep voted correctly → money routes to their support PAC at disbursement; rep voted wrong (or absent/present) → money routes to their opponent's PAC
6. 60 days before election day, all held funds disburse in one batch

---

## Ubiquitous Language

| Term | Definition |
|------|-----------|
| **Pledge** | A conditional donation from a constituent tied to a specific vote direction (YES or NO) |
| **Representative / Rep** | A federal elected official — House member or Senator |
| **Vote** | A recorded congressional vote on a bill or resolution |
| **Bill** | Proposed legislation being voted on |
| **Vote Outcome** | How a rep voted: `yes`, `no`, `absent`, or `present` (absent/present = wrong way) |
| **Direction** | The constituent's desired outcome for a pledge: `yes` or `no` |
| **Carrot** | Pledged money a rep earns by voting correctly — routes to their support super PAC |
| **Stick** | Pledged money that routes to the opponent's super PAC when a rep votes wrong |
| **Pledge Pool** | Total conditional funds held for a representative across all constituents |
| **Constituent** | A citizen matched to a representative by zip code |
| **Verification Tier** | Identity verification level — Tier 1 (<$50 lifetime): USPS validation; Tier 2 (>$50): government ID |
| **Disbursement** | The batch transfer of all held funds 60 days before election day |
| **Election Window** | The 60-day period before election day that triggers disbursement |
| **Support Destination** | The super PAC receiving carrot funds for a given rep |
| **Oppose Destination** | The opposing party's super PAC receiving stick funds for a given race |
| **Vote Summary** | AI-generated plain-language description of a bill, 3 sentences max |
| **PAC Balance** | Total funds currently held in the platform's HYSA |
| **District** | A geographic congressional district mapping a constituent to their House rep |

---

## Data Model

### `representatives`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| bioguide_id | text | ProPublica/Congress identifier |
| name | text | |
| party | text | D, R, I |
| chamber | enum | `house`, `senate` |
| state | text | 2-letter code |
| district | int | House only, null for Senate |
| photo_url | text | |
| is_active | bool | False if retired/lost primary |
| next_election_date | date | |

### `bills`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| congress_bill_id | text | e.g. "hr1234-118" |
| title | text | |
| summary_ai | text | Claude-generated 3-sentence summary |
| introduced_date | date | |
| status | text | |

### `votes`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| bill_id | uuid | FK → bills |
| scheduled_at | timestamptz | |
| resolved_at | timestamptz | null until vote happens |
| congress_vote_id | text | |

### `vote_outcomes`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| vote_id | uuid | FK → votes |
| representative_id | uuid | FK → representatives |
| outcome | enum | `yes`, `no`, `absent`, `present` |

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK (Supabase Auth) |
| email | text | |
| zip_code | text | |
| verification_tier | int | 1 or 2 |
| total_pledged_lifetime_cents | int | For tier upgrade trigger |
| stripe_customer_id | text | |

### `user_representatives`
| Column | Type | Notes |
|--------|------|-------|
| user_id | uuid | FK → users |
| representative_id | uuid | FK → representatives |
| is_confirmed | bool | User confirmed this is their rep |

### `pledges`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK → users |
| vote_id | uuid | FK → votes |
| representative_id | uuid | FK → representatives |
| direction | enum | `yes`, `no` |
| amount_cents | int | |
| stripe_payment_intent_id | text | |
| status | enum | `held`, `disbursed_carrot`, `disbursed_stick`, `refunded` |
| created_at | timestamptz | |

### `disbursements`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| election_date | date | |
| executed_at | timestamptz | |
| total_carrot_cents | int | |
| total_stick_cents | int | |
| status | enum | `pending`, `executed` |

---

## Module Map

```
┌─────────────────────────────────────────────────────────────┐
│                        External APIs                         │
│   ProPublica Congress API    OpenSecrets API    Claude API   │
└──────────────┬───────────────────┬──────────────────────────┘
               │                   │
┌──────────────▼───────────────────▼──────────────────────────┐
│                      Backend (FastAPI)                        │
│                                                               │
│  ┌─────────────────┐   ┌─────────────────┐                  │
│  │  Congress Sync  │   │ Vote Summarizer  │                  │
│  │  (background)   │   │  (Claude API)   │                  │
│  └────────┬────────┘   └────────┬────────┘                  │
│           │                     │                             │
│  ┌────────▼─────────────────────▼────────┐                  │
│  │           Notification Engine          │ ──► Email        │
│  │     (new vote → email constituents)    │                  │
│  └───────────────────────────────────────┘                  │
│                                                               │
│  ┌─────────────────┐   ┌─────────────────┐                  │
│  │  Pledge Engine  │◄──│  Stripe Webhooks │                  │
│  │                 │   │                 │                  │
│  └────────┬────────┘   └─────────────────┘                  │
│           │                                                   │
│  ┌────────▼────────┐   ┌─────────────────┐                  │
│  │  Verification   │   │  Rep Matching   │                  │
│  │    Service      │   │  (zip → reps)   │                  │
│  │ Tier1: USPS     │   └─────────────────┘                  │
│  │ Tier2: Stripe   │                                         │
│  │        Identity │   ┌─────────────────┐                  │
│  └─────────────────┘   │ Disbursement    │                  │
│                         │ Engine (batch,  │                  │
│  ┌─────────────────┐   │ 60d pre-election│                  │
│  │  Dashboard API  │   └─────────────────┘                  │
│  │  (public read)  │                                         │
│  └─────────────────┘                                         │
└─────────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│               Frontend (React + Vite, mobile-web first)      │
│                                                              │
│  Public Rep Dashboard    Pledge Flow    User Account         │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python) |
| Frontend | React + Vite (mobile-web first) |
| Database | Supabase (PostgreSQL) |
| Hosting | Railway |
| Auth | Supabase Auth (magic link) |
| Payments | Stripe |
| Email | TBD (Resend or SendGrid) |
| ID Verification | Stripe Identity (Tier 2) |
| Address Validation | USPS API / SmartyStreets |
| Vote Data | ProPublica Congress API |
| Finance Data | OpenSecrets API |
| AI Summaries | Claude API |
| Visual Assets | Claude Design (TBD) |

---

## Key Business Rules

- Absent or "present" votes count as voting the wrong way
- Money transfers immediately at pledge time (Stripe charge)
- All funds disbursed in one batch 60 days before election day
- If rep retires, dies, or loses primary: auto-refund to constituent
- Disbursement routes to general election opponent's PAC
- Rep dashboard is fully public and SEO-indexed
- Users can only pledge for their own representatives (verified by zip)
- Tier 1 verification (USPS): lifetime pledges < $50
- Tier 2 verification (Stripe Identity / government ID): lifetime pledges ≥ $50
- Standing pledges: not at launch — all pledges are manual
- Notifications: email only at launch
