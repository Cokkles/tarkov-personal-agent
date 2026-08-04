# Tarkov Personal Agent

A local-first, passive companion and analytics platform for **Escape from Tarkov** and **Escape from Tarkov: Arena**.

The project combines five systems:

1. **Source of Truth** — patch-aware, source-ranked game knowledge.
2. **Raid Companion** — passive log monitoring, OBS recording control, event markers, screenshots, and raid packaging.
3. **Personal Playstyle Engine (PPE)** — evidence-based analysis of objectives, encounters, decisions, strengths, limitations, and strategy fit.
4. **Recommendation Engine** — traceable plans based on verified mechanics, player evidence, objectives, risk, and confidence.
5. **Media Assistance** — finalized recording indexing, marker navigation, evidence integrity, and optional local clips.

## Project status

**Phase 6: Media Assistance.**

The repository contains a runnable local companion, browser raid-review workflow, explainable PPE, patch-aware Source-of-Truth registry, deterministic Recommendation Engine, and reference-first media manager. OBS recordings are indexed only after their files stabilize, preserving final size and SHA-256 metadata. Timeline events and Stream Deck markers are exposed as recording seek offsets, while optional FFmpeg clips can be generated around selected moments.

No Tarkov log signatures ship enabled yet. Automatic raid detection remains disabled until current redacted samples are validated against false positives. Manual lifecycle controls provide the safe fallback in the meantime.

## Quick start

Requirements: Python 3.12 and a local clone of this repository.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
tarkov-agent init --output config.toml
tarkov-agent doctor --config config.toml
```

After configuring OBS WebSocket and any local log paths, launch the companion:

```powershell
tarkov-agent serve --config config.toml
```

Local interfaces:

```text
http://127.0.0.1:8765/                 Raid Review
http://127.0.0.1:8765/ppe              Personal Playstyle Engine
http://127.0.0.1:8765/truth            Source of Truth
http://127.0.0.1:8765/recommendations  Recommendation Engine
http://127.0.0.1:8765/media            Media Assistance
```

The raid-review application supports manual raid start/end controls, live markers, pending-review selection, multiple encounter records, corrected metadata, review audit history, and Markdown or JSON export. Finalizing a review updates the PPE using only explicit structured evidence.

## Recording setup

When the OBS recording folder is outside the agent data root, add it to the approved evidence roots:

```toml
[api]
allowed_evidence_roots = [
  "D:/OBS Recordings"
]

[media]
enabled = true
copy_recordings_into_package = false
```

Reference-first storage is the default: the raid package records the final path, size, SHA-256, availability, and optional probe metadata without duplicating the full recording. Set `copy_recordings_into_package = true` only when every recording should be copied into its raid package.

`ffprobe` and `ffmpeg` are optional. Indexing, hashing, and marker navigation work without them; media probing and clip extraction require the corresponding executable to be available on `PATH` or configured explicitly.

Recalculate the profile from stored evidence:

```powershell
tarkov-agent ppe-rebuild --config config.toml
```

Inspect and query the Source-of-Truth corpus:

```powershell
tarkov-agent truth-status --config config.toml
tarkov-agent truth-query scav.extracted_loot_transfers --game tarkov --config config.toml
tarkov-agent truth-review-queue --config config.toml
```

Generate a traceable Scav plan:

```powershell
tarkov-agent recommend `
  "Extract task and hideout value safely" `
  --character Scav `
  --map Customs `
  --risk low `
  --config config.toml
```

To collect a limited redacted log sample for parser research:

```powershell
tarkov-agent capture-logs --config config.toml --seconds 180 --label scav-survived
```

Captured diagnostics must still be reviewed manually before sharing or committing.

## Media safeguards

- OBS files are allowed to stabilize before size and SHA-256 are calculated.
- Recording references remain local and are not uploaded.
- Manual media paths must be under the data root or an explicitly approved evidence root.
- Full recordings are referenced rather than copied by default.
- Missing FFmpeg or ffprobe does not break raid logging, review, or PPE processing.
- Video, OCR, transcription, and computer vision remain optional assistance layers.

## Recommendation safeguards

- Required mechanics must resolve through the Source-of-Truth refusal contract.
- Unknown, stale, disputed, conflicting, or patch-ambiguous mechanics block dependent strategies.
- Missing PPE evidence remains neutral and low-confidence instead of becoming an inferred trait.
- Progression plans and controlled training experiments remain separate.
- Primary, fallback, blocked candidates, assumptions, research tasks, and confidence survive exports.
- Recommendations are pre-raid or post-raid assistance, not hidden live gameplay automation.

## Source-of-Truth safeguards

- Only verified, applicable, conflict-free claims return `can_recommend=true`.
- Patch-specific values require patch context when several historical values exist.
- Unknown, draft, disputed, stale, and rejected claims are refused for recommendation use.
- Source authority and reliability are reduced by missing or overdue review.
- Citation URLs, locators, revisions, roles, and access times survive exports.
- Official publisher, officially branded wiki, structured data, primary testing, and community sources remain distinct authority classes.
- Open conflicts enter the blocking review queue.

## PPE safeguards

- A single raid cannot dominate a dimension.
- Outcome-only evidence is deliberately low weight.
- Older evidence decays gradually.
- Contradictory evidence lowers confidence.
- Global and contextual estimates coexist.
- Free-text raid narratives are not silently converted into skill claims.
- Adaptation guidance is separate from optional deliberate training.
- Every changed profile has a version, evidence fingerprint, and audit record.

## Core principles

- Local-first and privacy-conscious
- Passive observation only; no game-memory reading, injection, gameplay automation, or anti-cheat interference
- Evidence preserved separately from interpretation
- Current mechanics verified before strategy is generated
- Confidence and uncertainty are explicit
- Player adaptation and player training are separate concerns
- Every recommendation should be explainable and reversible

## Repository areas

- `docs/` — charter, requirements, architecture, safety, implementation notes, roadmap, and setup guide
- `src/tarkov_agent/` — Python companion, local API, browser applications, and domain services
- `src/tarkov_agent/ppe/` — profile registry, extractor, weighting engine, and report logic
- `src/tarkov_agent/domain/source_truth.py` — patch, source, claim, citation, conflict, query, and review models
- `src/tarkov_agent/services/source_truth.py` — ranking, verification, conflict, review, query, and export logic
- `src/tarkov_agent/domain/recommendations.py` — recommendation request, candidate, scoring, and output models
- `src/tarkov_agent/services/recommendations.py` — candidate generation, filtering, scoring, experiments, and exports
- `src/tarkov_agent/domain/media.py` — recording, navigation, clip, and media-index models
- `src/tarkov_agent/services/media.py` — stabilization, hashing, probing, navigation, and clip extraction
- `migrations/` — versioned SQLite migrations
- `schemas/` — planned versioned interchange schemas
- `prompts/` — planned advanced reasoning prompts and output contracts
- `knowledge-base/` — planned source policies, claim records, and curated notes
- `tests/` — unit and integration tests
- `scripts/` — planned development and data-maintenance utilities

## Data boundary

Git stores source code, schemas, prompts, documentation, and small synthetic test fixtures. It does **not** store normal raid videos, private account exports, credentials, or large raw log archives. Large evidence files belong in the local data root and, when deliberately archived, the linked Google Drive project folder.

The local HTTP service binds to loopback by default. A non-loopback bind requires an API token, and manually referenced evidence files must be located under the configured data root or an explicitly allowed evidence directory.

Start with:

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md)
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md)
- [`docs/implementation/PHASE1_CORE.md`](docs/implementation/PHASE1_CORE.md)
- [`docs/PHASE2_RAID_REVIEW.md`](docs/PHASE2_RAID_REVIEW.md)
- [`docs/PHASE3_PERSONAL_PLAYSTYLE_ENGINE.md`](docs/PHASE3_PERSONAL_PLAYSTYLE_ENGINE.md)
- [`docs/PHASE4_SOURCE_OF_TRUTH.md`](docs/PHASE4_SOURCE_OF_TRUTH.md)
- [`docs/PHASE5_RECOMMENDATION_ENGINE.md`](docs/PHASE5_RECOMMENDATION_ENGINE.md)
- [`docs/PHASE6_MEDIA_ASSISTANCE.md`](docs/PHASE6_MEDIA_ASSISTANCE.md)
- [`docs/SETUP_AND_SCAV_TEST.md`](docs/SETUP_AND_SCAV_TEST.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/SAFETY_AND_COMPLIANCE.md`](docs/SAFETY_AND_COMPLIANCE.md)
