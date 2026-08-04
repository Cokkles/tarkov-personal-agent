# Phase 5 — Recommendation Engine

## Purpose

The Recommendation Engine turns a raid objective into a primary plan, fallback plan, and optional training experiment. It is deterministic, local-first, and deliberately conservative: hard mechanics must pass the Source-of-Truth query contract, while player-fit scoring must cite PPE estimates rather than inventing a player profile.

The engine does not provide hidden live tactical direction. It prepares plans before a raid or structured experiments for later review.

## Inputs

A recommendation request contains:

- game and optional patch;
- objective;
- map and character type;
- progression or training purpose;
- preferred risk posture;
- group-size context;
- optional hard mechanic keys;
- explicit constraints and notes.

## Candidate generation

The initial deterministic library generates several distinct approaches:

- objective-first, low-exposure progression;
- information-first flexible routing;
- contact-capable balanced routing;
- Scav survival-first transfer runs;
- Scav opportunistic contested runs;
- controlled single-variable training;
- low-cost live transfer experiments.

Templates are intentionally generic. They do not claim map-specific paths, loot locations, item values, spawn logic, or combat mechanics unless those facts are represented as verified Source-of-Truth claims.

## Hard mechanical filtering

Every candidate lists its mechanic requirements. The service resolves each one through `SourceTruthService.query()` with the requested game and patch.

A required mechanic blocks the candidate when it is:

- missing;
- patch-ambiguous;
- stale;
- disputed;
- conflicting;
- below verification requirements;
- unavailable because Source of Truth is disabled.

Optional unresolved mechanics remain visible but cannot silently authorize a recommendation.

Scav templates currently exercise the seeded verified claims:

- `scav.extracted_loot_transfers`;
- `scav.random_loadout`.

User-supplied `mechanic_keys` become hard dependencies for every generated candidate.

## Player-fit scoring

Each strategy declares PPE fit weights. Positive weights favor a supported strength; negative weights favor an adaptation strategy when a dimension is currently weak. The engine first checks a matching map context and then falls back to the global estimate.

The output preserves:

- dimension key;
- context key;
- score and confidence;
- fit weight and contribution;
- supporting PPE evidence identifiers;
- calculation rationale.

When PPE is disabled or too early, fit remains neutral and confidence stays low. One raid cannot become an established recommendation basis because the engine consumes the PPE snapshot rather than raw outcomes.

## Scoring

Eligible candidates are ordered by:

1. objective alignment;
2. player-fit score;
3. risk-posture fit;
4. plan confidence.

The initial total score uses:

```text
40% objective alignment
35% player fit
25% risk fit
```

Confidence combines mechanic verification, PPE confidence, and objective alignment. A candidate can be mechanically eligible but still fail the configured minimum plan confidence.

## Output contract

A recommendation plan includes:

- primary candidate;
- fallback candidate;
- all evaluated and blocked candidates;
- mechanics resolutions and citations;
- PPE fit checks and evidence references;
- assumptions;
- research tasks;
- refusal or caution reason;
- optional controlled experiment design.

The current files are written under:

```text
<data_root>/recommendations/
├── latest.json
├── latest.md
└── history/
    └── <timestamp>_<plan-id>.json
```

## Browser and API

Start the service and open:

```text
http://127.0.0.1:8765/recommendations
```

Routes:

```text
POST /api/recommendations/generate
POST /api/recommendations/templates
GET  /api/recommendations/latest
GET  /api/recommendations/export/markdown
GET  /api/recommendations/export/json
```

## CLI

Example Scav progression plan:

```powershell
tarkov-agent recommend `
  "Extract hideout and task value safely" `
  --character Scav `
  --map Customs `
  --risk low `
  --config config.toml
```

Require an additional verified mechanic:

```powershell
tarkov-agent recommend `
  "Complete the planned objective" `
  --mechanic scav.extracted_loot_transfers `
  --config config.toml
```

Generate a training experiment:

```powershell
tarkov-agent recommend `
  "Practice disciplined disengagement" `
  --purpose training `
  --risk low `
  --config config.toml
```

The command exits with code `0` when the plan clears the recommendation threshold, `3` when it produces a structured refusal or caution, and `2` when the subsystem is disabled.

## Safety boundary

The Recommendation Engine:

- does not read game memory;
- does not inject into Tarkov;
- does not automate gameplay;
- does not bypass the Source-of-Truth refusal contract;
- does not turn uncertain PPE signals into authoritative traits;
- does not provide a hidden real-time tactical overlay.

## Exit condition

Phase 5 is complete when the system can generate several candidate strategies, block unsupported mechanics, score objective/risk/player fit, return a primary and fallback plan, preserve evidence and assumptions, and create a controlled experiment for training requests.
