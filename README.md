# Tarkov Personal Agent

A local-first, passive companion and analytics platform for **Escape from Tarkov** and **Escape from Tarkov: Arena**.

The project combines six systems:

1. **Source of Truth** — patch-aware, source-ranked game knowledge.
2. **Raid Companion** — passive log monitoring, OBS recording control, event markers, screenshots, and raid packaging.
3. **Personal Playstyle Engine (PPE)** — evidence-based analysis of objectives, encounters, decisions, strengths, limitations, and strategy fit.
4. **Recommendation Engine** — traceable plans based on verified mechanics, player evidence, objectives, risk, and confidence.
5. **Media Assistance** — finalized recording indexing, marker navigation, evidence integrity, and optional local clips.
6. **Desktop Companion** — a native dashboard, system tray, manual raid controls, markers, and one-click workspace access.

## Project status

**Phase 6.5: Desktop Companion.**

The repository contains a runnable local service, native desktop dashboard, browser raid-review workflow, explainable PPE, patch-aware Source-of-Truth registry, deterministic Recommendation Engine, and reference-first media manager. The desktop app can start or connect to the service, show raid and OBS status, control the manual raid lifecycle, create the seven validated markers, and open every detailed browser workspace.

No Tarkov log signatures ship enabled yet. Automatic raid detection remains disabled until current redacted samples are validated against false positives. Manual lifecycle controls remain the safe fallback.

## Quick start

Requirements: Python 3.12 and a local clone of this repository.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
tarkov-agent init --output config.toml
tarkov-agent doctor --config config.toml
```

Run only the local service and browser applications:

```powershell
tarkov-agent serve --config config.toml
```

Install the native Desktop Companion and create a Windows desktop shortcut:

```powershell
.\scripts\install_desktop_companion.ps1 `
  -ConfigPath "C:\TarkovPersonalAgent\TarkovPersonalAgentCode\config.toml"
```

Or install and run it manually:

```powershell
python -m pip install -e ".[desktop]"
tarkov-agent-desktop --config config.toml
```

The desktop starts the local service automatically when needed. When an independently launched service is already running, the desktop connects to it without claiming ownership.

## Interfaces

```text
Native application                         Tarkov Personal Agent Desktop
http://127.0.0.1:8765/                     Raid Review
http://127.0.0.1:8765/ppe                  Personal Playstyle Engine
http://127.0.0.1:8765/truth                Source of Truth
http://127.0.0.1:8765/recommendations      Recommendation Engine
http://127.0.0.1:8765/media                Media Assistance
http://127.0.0.1:8765/docs                 API documentation
```

The native dashboard provides:

- service status and ownership-aware start/stop controls;
- current lifecycle, active raid, OBS, review queue, PPE, and parser-rule status;
- manual Start Raid, End Raid, and Abort Raid controls;
- seven live marker buttons;
- system-tray operation;
- one-click access to all detailed browser workspaces.

## Desktop configuration

```toml
[desktop]
enabled = true
auto_start_service = true
minimize_to_tray = true
stop_service_on_exit = true
poll_interval_seconds = 2.0
request_timeout_seconds = 1.5
service_start_timeout_seconds = 15.0
```

Desktop logs are written under:

```text
<data_root>/desktop/desktop.log
```

The Windows installer script can create either a normal desktop shortcut or a Startup-folder shortcut. The launcher always points to the project virtual environment and the selected `config.toml`.

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

## Useful commands

Recalculate the profile:

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

Collect a limited redacted log sample:

```powershell
tarkov-agent capture-logs --config config.toml --seconds 180 --label scav-survived
```

Captured diagnostics must still be reviewed manually before sharing or committing.

## Safeguards

### Desktop

- PySide6 remains an optional dependency; the CLI, API, tests, and browser applications remain headless-capable.
- The desktop stops only the embedded service instance it owns.
- Manual lifecycle and marker actions use the established local API.
- The native application does not introduce a game overlay.

### Media

- OBS files stabilize before size and SHA-256 are calculated.
- Recording references remain local and are not uploaded.
- Manual media paths must be under the data root or an explicitly approved evidence root.
- Full recordings are referenced rather than copied by default.
- Missing FFmpeg or ffprobe does not break raid logging, review, or PPE processing.

### Recommendations

- Required mechanics must resolve through the Source-of-Truth refusal contract.
- Unknown, stale, disputed, conflicting, or patch-ambiguous mechanics block dependent strategies.
- Missing PPE evidence remains neutral and low-confidence instead of becoming an inferred trait.
- Progression plans and controlled training experiments remain separate.
- Primary, fallback, blocked candidates, assumptions, research tasks, and confidence survive exports.

### Source of Truth and PPE

- Only verified, applicable, conflict-free claims can authorize recommendations.
- Patch-specific values require patch context when several historical values exist.
- A single raid cannot dominate a PPE dimension.
- Outcome-only evidence is deliberately low weight.
- Contradictory evidence lowers confidence.
- Free-text narratives are not silently converted into skill claims.
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

- `docs/` — charter, requirements, architecture, safety, phase guides, roadmap, and setup
- `src/tarkov_agent/` — Python companion, local API, browser applications, desktop client, and domain services
- `src/tarkov_agent/desktop/` — native API client, embedded service ownership, and PySide6 dashboard
- `src/tarkov_agent/ppe/` — profile registry, extractor, weighting engine, and report logic
- `src/tarkov_agent/domain/source_truth.py` — patch, source, claim, citation, conflict, query, and review models
- `src/tarkov_agent/services/source_truth.py` — ranking, verification, conflict, review, query, and export logic
- `src/tarkov_agent/domain/recommendations.py` — recommendation request, candidate, scoring, and output models
- `src/tarkov_agent/services/recommendations.py` — candidate generation, filtering, scoring, experiments, and exports
- `src/tarkov_agent/domain/media.py` — recording, navigation, clip, and media-index models
- `src/tarkov_agent/services/media.py` — stabilization, hashing, probing, navigation, and clip extraction
- `migrations/` — versioned SQLite migrations
- `tests/` — unit and integration tests
- `scripts/` — installation, shortcut, development, and maintenance utilities

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
- [`docs/PHASE6_5_DESKTOP_COMPANION.md`](docs/PHASE6_5_DESKTOP_COMPANION.md)
- [`docs/SETUP_AND_SCAV_TEST.md`](docs/SETUP_AND_SCAV_TEST.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/SAFETY_AND_COMPLIANCE.md`](docs/SAFETY_AND_COMPLIANCE.md)
