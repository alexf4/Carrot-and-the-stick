# Software Fundamentals in the AI Age
**Speaker:** Matt Pocock (aihero.dev) — conference talk

## Core Thesis

> Code is NOT cheap. Bad code is the most expensive it's ever been.
> Software fundamentals matter MORE now, not less.

AI performs well in good codebases and degrades rapidly in bad ones — so the quality of your codebase directly multiplies (or limits) what AI can do for you.

**Mental model:**
```
You         →  Strategic / architect layer
              (design, interfaces, modules, planning)

AI          →  Tactical / implementation layer
              (code changes, filling in implementation)
```

**Anti-pattern: Specs-to-Code**
```
spec → AI → code → spec → AI → worse code → spec → AI → garbage
```
Every pass without design investment increases entropy (Pragmatic Programmer: *software entropy*).

---

## Failure Modes & Solutions

### Failure Mode 1 — "AI didn't do what I wanted"

**Root cause:** No shared *design concept* (Frederick P. Brooks, *The Design of Design*).
The design concept is the invisible, shared theory of what you're building — it can't be put in a file, it floats between collaborators.

**Fix → `grill-me` skill**
```
Prompt: "Interview me relentlessly about every aspect of this plan
         until we reach a shared understanding. Walk down each branch
         of the design tree, resolving dependencies between decisions
         one by one."
```
```
You ──[idea]──► AI asks 40–100 clarifying questions
                         │
                         ▼
              Shared design concept
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
           PRD / doc           Issues for AFK agent
```
Prefer this over plan mode — plan mode is eager to create an asset; grill-me builds shared understanding first.

---

### Failure Mode 2 — "AI is too verbose / talking across purposes"

**Root cause:** Language gap — same problem as developer ↔ domain expert communication.

**Fix → Ubiquitous Language (Domain-Driven Design)**

A shared markdown glossary of domain terms used consistently in:
- Code identifiers
- Developer conversations
- AI prompts and planning

**`ubiquitous-language` skill:** scans codebase → generates markdown tables of terminology.

```
Domain Model
     │
     ├── Code (identifiers, module names)
     ├── Developer conversations
     └── AI prompts / planning sessions
          (keep the file open during all planning)
```
Benefit observed in AI thinking traces: less verbosity, more aligned implementation.

---

### Failure Mode 3 — "AI built the right thing but it doesn't work"

**Root cause:** AI outrunning its headlights (Pragmatic Programmer).

> "The rate of feedback is your speed limit."

AI tends to write large chunks of code, *then* type-check or test — instead of the reverse.

**Fix → TDD skill**
```
Write test  →  Make test pass  →  Refactor for design
    │                                      │
    └──────────── small step ──────────────┘
```
Required feedback loops:
- Static types (TypeScript / mypy / etc.)
- Browser access for frontend LLM work
- Automated test suite

---

### Failure Mode 4 — "Hard to test / AI doesn't understand my code"

**Root cause:** Shallow modules (John Ousterhout, *A Philosophy of Software Design*).

```
Shallow modules              Deep modules
────────────────             ─────────────────────────────
Many tiny blobs    →   Few large modules with simple interfaces
Complex interfaces     Complexity hidden behind clean boundaries

 ○ ○ ○ ○ ○ ○            ┌──────────────┐  ┌──────────────┐
○ ○ ○ ○ ○ ○ ○     →     │  interface   │  │  interface   │
 ○ ○ ○ ○ ○ ○            │─────────────│  │─────────────│
                         │    impl     │  │    impl     │
(AI gets lost)           └──────────────┘  └──────────────┘
                         (AI tests at interface, ignores internals)
```

**Fix → `improve-codebase-architecture` skill**
- Scan for related code scattered across shallow modules
- Wrap in a deep module with a designed interface
- Test at the interface boundary → testable codebase → TDD works

---

### Failure Mode 5 — "Brain can't keep up"

**Root cause:** Shallow module codebases require holding too many details in your head — for both you and the AI.

**Fix → Design the interface, delegate the implementation**
```
You own:    the interface design + module map + ubiquitous language
AI owns:    everything inside the implementation boundary

Test at the interface → verify behavior → don't review internals
(except for critical paths: finance, security, etc.)
```
Module map should be part of your ubiquitous language and referenced explicitly in every PRD.

From Kent Beck: *"Invest in the design of the system every day."*

---

## Workflow Summary

```
1. ALIGN      grill-me skill
              → reach shared design concept before touching code

2. SPEAK      ubiquitous language
              → shared glossary in all code, conversations, prompts

3. STRUCTURE  deep modules
              → designed interfaces, delegated implementation

4. BUILD      TDD
              → test first, small steps, rate of feedback = speed limit

5. SUSTAIN    invest in design daily
              → update module map, interfaces, ubiquitous language in every PRD
```

---

## Key References

| Book | Concept Used |
|------|-------------|
| *A Philosophy of Software Design* — John Ousterhout | Deep vs shallow modules, complexity definition |
| *The Pragmatic Programmer* | Software entropy, outrunning your headlights |
| *The Design of Design* — Frederick P. Brooks | Design concept, design tree |
| *Domain-Driven Design* | Ubiquitous language |
| Kent Beck | Invest in system design daily |

## Skills from mattpocock/skills

| Skill | Failure Mode Addressed |
|-------|----------------------|
| `productivity/grill-me` | No shared design concept |
| `engineering/improve-codebase-architecture` | Shallow modules / untestable codebase |
| `engineering/tdd` | AI outrunning feedback loops |
| `engineering/to-prd` | Turning aligned understanding into a spec |
| `engineering/to-issues` | Breaking PRD into actionable work |
