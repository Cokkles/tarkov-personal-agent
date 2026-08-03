# Phase 1 Core Implementation

## Status

This block establishes a runnable local foundation. It does **not** yet ship verified Tarkov log signatures or a graphical interface.

## Implemented

- Typed TOML and environment-variable configuration
- Passive process-presence observer using `psutil`
- Rotation- and truncation-tolerant append-only log observer
- Explicit regular-expression log classifier
- Confidence gate before a log signal may alter lifecycle state
- Deterministic raid lifecycle state machine
- OBS WebSocket v5 recording adapter through `obsws-python`
- No-op OBS adapter for disabled or test configurations
- Per-raid package folders with atomic manifests and JSONL timelines
- SHA-256 evidence references and optional evidence copying
- SQLite raid and timeline repository
- Initial Alembic migration
- User marker service
- Coordinator for lifecycle, recording, package, and persistence actions
- CLI commands for configuration creation, diagnostics, and runtime execution
- Cross-platform CI, linting, strict type checking, and unit tests

## Deliberate safety defaults

1. OBS control is disabled until explicitly configured.
2. No automatic log rules are enabled.
3. A rule must meet the configured confidence threshold before it can drive state.
4. Evidence files remain external references unless copying is explicitly enabled.
5. The process observer reads operating-system process metadata only.
6. No memory access, game injection, packet interception, gameplay input, or hidden-information processing exists.

## Quick start for development

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
tarkov-agent init --output config.toml
tarkov-agent doctor --config config.toml
```

After configuring verified local paths and OBS WebSocket:

```powershell
tarkov-agent run --config config.toml
```

## Validation still required

Before enabling automatic raid start or end detection, collect current log samples from:

- Normal PMC extract
- PMC death
- Scav extract and death
- Disconnect and reconnect
- Client crash
- Match cancellation before deployment
- Arena match start and completion

Each proposed rule must be tested for false positives against launcher, menu, Hideout, matchmaking, and unrelated log activity.

## Next implementation block

- Diagnostic log-capture command with redaction
- Log-fixture corpus and parser versioning
- Manual lifecycle controls as a safe fallback
- Local HTTP API for the raid form and Stream Deck actions
- Post-raid review queue
- Recovery of interrupted active raids after application restart
- Structured application logs and health status
- Windows packaging and installer prototype
