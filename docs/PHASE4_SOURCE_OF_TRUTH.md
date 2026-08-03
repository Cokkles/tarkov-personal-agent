# Phase 4 — Source of Truth

## Purpose

The Source-of-Truth system stores mechanics as patch-aware claims rather than loose notes. It is the gate between research and recommendations. A recommendation may use a mechanic only when the query resolves to one verified, applicable value with preserved citations and no unresolved conflict.

The system is deliberately conservative. A claim can exist without being usable. Draft, stale, disputed, rejected, patch-ambiguous, and missing claims all produce an explicit refusal instead of a guessed answer.

## Core model

### Sources

Each source record contains:

- a stable key and URL;
- game scope and covered topics;
- authority class and manual reliability estimate;
- active, disabled, or retired status;
- last and next review timestamps;
- notes explaining limitations.

Initial authority classes, from strongest to weakest, are:

1. official publisher;
2. officially branded wiki;
3. verified structured data;
4. documented primary testing;
5. maintained community reference;
6. community discussion.

Authority is not treated as infallibility. Freshness, review status, citation role, patch scope, and agreement still matter. The officially branded wiki is stored separately from publisher material because it is maintained by community editors and volatile values still require patch review.

### Claims

Each claim stores:

- a stable mechanics key;
- a human-readable statement;
- a canonical value and optional unit;
- claim kind and game scope;
- patch applicability;
- citations with page or section locators;
- manual confidence;
- calculated verification score;
- review interval and due date;
- current status.

Claim statuses are:

- `draft` — recorded but below verification requirements;
- `verified` — supported, current, applicable, and conflict-free;
- `disputed` — involved in an unresolved conflict;
- `stale` — review is overdue beyond the configured grace period;
- `rejected` — deliberately excluded from conflict and recommendation use.

### Patch applicability

A claim may be:

- valid for all patches;
- introduced at a patch and valid afterward;
- removed at a patch, using an exclusive upper bound;
- valid within an introduced/removed range;
- valid only for explicitly listed versions.

When several values exist under different patch windows, a query without a patch is refused. This prevents a historically correct number from being applied to the current game accidentally.

### Citations

Citations preserve:

- source identity;
- exact URL;
- page title;
- page, section, table, endpoint, test, or line locator;
- supporting, opposing, or contextual role;
- publication and access time when available;
- source revision or patch identifier;
- reviewer notes.

Markdown and JSON exports keep those fields intact.

## Source ranking and verification

The initial source score combines authority and the configured reliability estimate. Disabled or retired sources score zero. Unreviewed sources receive a penalty, and overdue sources lose rank progressively.

A claim verification score is calculated from its supporting citations, source ranks, citation freshness, and the claim's manual confidence. Verification also requires the configured minimum number of supporting citations.

A high score alone is not enough. A claim is not verified when it:

- participates in a conflict;
- is overdue beyond the stale grace period;
- cites an unknown or inactive source;
- has insufficient support;
- has been explicitly rejected.

## Conflict detection

Claims conflict when they share the same stable key, apply to overlapping game and patch scopes, and contain different normalized canonical values.

The conflict record preserves:

- the claim key;
- both claim identifiers;
- both values;
- the overlapping patch description;
- detection time and status.

Any applicable open conflict blocks recommendation use. A reviewer resolves the underlying data by rejecting the invalid claim, correcting a value, or separating the claims into accurate patch windows, then rebuilding conflicts.

## Query contract

A mechanics query contains:

- stable claim key;
- game scope;
- optional patch version;
- whether stale material may be displayed for review.

The response always includes a resolution state, explanation, candidate claims, citations, and a `can_recommend` flag.

Only this combination permits recommendation use:

```text
resolution = verified
can_recommend = true
one applicable canonical value
no open conflict
current verification requirements satisfied
```

Stale claims may be displayed with `include_stale`, but they still return `can_recommend=false`.

## Review workflow

Sources and claims receive a next-review timestamp when created or reviewed. The review queue collects:

- active sources whose authority, availability, or freshness review is due;
- claims whose citations and patch scope are due for review;
- all open conflicts as blocking tasks.

The queue is available through the browser, API, and CLI. It does not silently refresh internet content. A human or later source-ingestion process must inspect the material, preserve the evidence, and mark it reviewed.

## Seeded registry

A new data root receives initial records for:

- Battlestate Games — Escape from Tarkov;
- Battlestate Games — Escape from Tarkov: Arena;
- The Official Escape from Tarkov Wiki;
- Tarkov.dev GraphQL API.

Three low-volatility Scav claims are seeded so the complete query and citation workflow can be tested immediately:

- `scav.main_stash_isolated`;
- `scav.extracted_loot_transfers`;
- `scav.random_loadout`.

The seed is intentionally small. Phase 4 provides the validation system, not an unreviewed bulk scrape.

## Local outputs

The live records are stored in the same SQLite database as the raid system. Citation-preserving snapshots are written to:

```text
<data_root>/source-truth/
├── source-truth.json
└── source-truth.md
```

## Browser and API

Start the local service:

```powershell
tarkov-agent serve --config config.toml
```

Open:

```text
http://127.0.0.1:8765/truth
```

The dashboard supports:

- source and claim creation;
- live verification status;
- mechanics queries;
- conflict rebuilding;
- review queue inspection;
- Markdown and JSON export.

Key API routes are:

```text
GET  /api/truth/status
GET  /api/truth/sources
POST /api/truth/sources
POST /api/truth/sources/{source_id}/review
GET  /api/truth/claims
POST /api/truth/claims
POST /api/truth/claims/{claim_id}/review
GET  /api/truth/conflicts
POST /api/truth/conflicts/rebuild
GET  /api/truth/review-queue
POST /api/truth/query
GET  /api/truth/export/markdown
GET  /api/truth/export/json
```

## CLI

Show corpus status:

```powershell
tarkov-agent truth-status --config config.toml
```

Resolve a claim:

```powershell
tarkov-agent truth-query scav.extracted_loot_transfers --game tarkov --config config.toml
```

A successful, recommendation-safe resolution exits with code `0`. A valid query that is not safe for recommendation use exits with code `3` so scripts cannot mistake an unresolved response for success.

Supply a patch when required:

```powershell
tarkov-agent truth-query ammo.example.penetration `
  --game tarkov `
  --patch 1.0.5.0.45581 `
  --config config.toml
```

Inspect due reviews:

```powershell
tarkov-agent truth-review-queue --config config.toml
```

Write a citation-preserving export:

```powershell
tarkov-agent truth-export `
  --config config.toml `
  --format markdown `
  --output .\exports\tarkov-source-truth.md
```

## Recommendation-engine boundary

Phase 5 must query this service for every hard mechanical dependency. It must not copy a value from a source page, memory, prompt, or strategy note and bypass the claim-resolution contract.

When the result is unresolved, stale, conflicted, or missing, Phase 5 must either:

- ask for a patch or other missing context;
- use a plan that does not depend on the disputed mechanic;
- identify the claim as a research task;
- refuse the unsupported part of the recommendation.

## Exit condition

Phase 4 is complete when mechanics can be stored as ranked, patch-aware, citation-preserving claims; conflicts and review deadlines are visible; and a query can reliably permit verified values while refusing unresolved ones.
