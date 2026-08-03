# Tarkov Personal Agent

A local-first, passive companion and analytics platform for **Escape from Tarkov** and **Escape from Tarkov: Arena**.

The project combines four systems:

1. **Source of Truth** — patch-aware, source-ranked game knowledge.
2. **Raid Companion** — passive log monitoring, OBS recording control, event markers, screenshots, and raid packaging.
3. **Personal Playstyle Engine (PPE)** — evidence-based analysis of objectives, encounters, decisions, strengths, limitations, and strategy fit.
4. **Recommendation Engine** — context-aware guidance based on current mechanics, player evidence, raid goals, risk, equipment, and confidence.

## Project status

**Phase 1 core is in active development.**

The repository now contains the first runnable local foundation: typed configuration, process and log observers, a raid lifecycle state machine, OBS recording control, raid packages, SQLite persistence, markers, CLI diagnostics, migrations, and tests.

No Tarkov log signatures ship enabled yet. Automatic raid detection remains disabled until current log samples are collected and the rules are verified against false positives.

## Quick start

Requirements: Python 3.12 and a local clone of this repository.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
tarkov-agent init --output config.toml
tarkov-agent doctor --config config.toml
```

After adding verified local log paths and enabling OBS WebSocket in `config.toml`:

```powershell
tarkov-agent run --config config.toml
```

## Core principles

- Local-first and privacy-conscious
- Passive observation only; no game-memory reading, injection, gameplay automation, or anti-cheat interference
- Evidence preserved separately from interpretation
- Current mechanics verified before strategy is generated
- Confidence and uncertainty are explicit
- Player adaptation and player training are separate concerns
- Every recommendation should be explainable and reversible

## Repository areas

- `docs/` — charter, requirements, architecture, safety, decisions, roadmap
- `src/tarkov_agent/` — current Python application and domain packages
- `migrations/` — versioned database migrations
- `schemas/` — planned versioned interchange schemas
- `prompts/` — planned AI prompts and output contracts
- `knowledge-base/` — planned source policies, claim records, and curated notes
- `tests/` — unit and integration tests
- `scripts/` — planned development and data-maintenance utilities

## Data boundary

Git stores source code, schemas, prompts, documentation, and small test fixtures. It does **not** store normal raid videos, private account exports, credentials, or large raw log archives. Large evidence files belong in the local data root and, when deliberately archived, the linked Google Drive project folder.

Start with:

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md)
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md)
- [`docs/implementation/PHASE1_CORE.md`](docs/implementation/PHASE1_CORE.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/SAFETY_AND_COMPLIANCE.md`](docs/SAFETY_AND_COMPLIANCE.md)
