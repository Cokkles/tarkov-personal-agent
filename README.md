# Tarkov Personal Agent

A local-first, passive companion and analytics platform for **Escape from Tarkov** and **Escape from Tarkov: Arena**.

The project combines four systems:

1. **Source of Truth** — patch-aware, source-ranked game knowledge.
2. **Raid Companion** — passive log monitoring, OBS recording control, event markers, screenshots, and raid packaging.
3. **Personal Playstyle Engine (PPE)** — evidence-based analysis of objectives, encounters, decisions, strengths, limitations, and strategy fit.
4. **Recommendation Engine** — context-aware guidance based on current mechanics, player evidence, raid goals, risk, equipment, and confidence.

## Project status

**Phase 0: Foundation and architecture**

The repository is the canonical blueprint for rebuilding and maintaining the system. Large evidence files such as full raid videos, screenshots, exported logs, PDFs, and research archives belong outside Git in the linked Google Drive project folder.

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
- `schemas/` — versioned JSON schemas and database design
- `apps/raid-companion/` — Windows companion application
- `apps/raid-review/` — post-raid review interface
- `packages/` — shared domain, parsing, timeline, PPE, and source-validation modules
- `prompts/` — versioned AI prompts and output contracts
- `knowledge-base/` — source policies, claim records, and curated notes
- `tests/` — fixtures, unit, integration, and end-to-end tests
- `scripts/` — development and data-maintenance utilities

## Data boundary

Git stores source code, schemas, prompts, documentation, and small test fixtures. It does **not** store normal raid videos, private account exports, credentials, or large raw log archives.

Start with:

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md)
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/SAFETY_AND_COMPLIANCE.md`](docs/SAFETY_AND_COMPLIANCE.md)
