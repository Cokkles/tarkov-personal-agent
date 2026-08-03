# Tarkov Personal Agent

A local-first, passive companion and analytics platform for **Escape from Tarkov** and **Escape from Tarkov: Arena**.

The project combines four systems:

1. **Source of Truth** — patch-aware, source-ranked game knowledge.
2. **Raid Companion** — passive log monitoring, OBS recording control, event markers, screenshots, and raid packaging.
3. **Personal Playstyle Engine (PPE)** — evidence-based analysis of objectives, encounters, decisions, strengths, limitations, and strategy fit.
4. **Recommendation Engine** — context-aware guidance based on current mechanics, player evidence, raid goals, risk, equipment, and confidence.

## Project status

**Phase 2: local raid capture and review workflow.**

The repository contains a runnable local companion with typed configuration, passive process and log observers, a raid lifecycle state machine, OBS recording control, recoverable raid packages, SQLite persistence, semantic markers, diagnostic log capture, manual controls, a local FastAPI service, and a browser-based post-raid review queue.

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

After configuring OBS WebSocket and any local log paths, launch the companion and browser review application:

```powershell
tarkov-agent serve --config config.toml
```

The default local address is:

```text
http://127.0.0.1:8765/
```

The review application supports manual raid start/end controls, live markers, pending-review selection, multiple encounter records, corrected metadata, review audit history, and Markdown or JSON export.

To collect a limited redacted log sample for parser research:

```powershell
tarkov-agent capture-logs --config config.toml --seconds 180 --label pmc-survived
```

Captured diagnostics must still be reviewed manually before sharing or committing.

## Core principles

- Local-first and privacy-conscious
- Passive observation only; no game-memory reading, injection, gameplay automation, or anti-cheat interference
- Evidence preserved separately from interpretation
- Current mechanics verified before strategy is generated
- Confidence and uncertainty are explicit
- Player adaptation and player training are separate concerns
- Every recommendation should be explainable and reversible

## Repository areas

- `docs/` — charter, requirements, architecture, safety, implementation notes, and roadmap
- `src/tarkov_agent/` — Python companion, local API, browser review application, and domain services
- `migrations/` — versioned SQLite migrations
- `schemas/` — planned versioned interchange schemas
- `prompts/` — planned PPE and recommendation prompts and output contracts
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
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/SAFETY_AND_COMPLIANCE.md`](docs/SAFETY_AND_COMPLIANCE.md)
