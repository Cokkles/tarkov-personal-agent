# Phase 2 — Raid Review, Diagnostic Capture and Recovery

## Purpose

Phase 2 turns the Phase 1 recorder foundation into a usable local workflow. A completed or interrupted raid can be found in a review queue, corrected in a browser, enriched with encounters and notes, and exported without reconstructing its metadata by hand.

## Delivered components

### Local FastAPI service

The `tarkov-agent serve` command runs the passive companion and a loopback web application together. The default address is `http://127.0.0.1:8765/`.

The API exposes:

- health and runtime status;
- recent raids and the pending review queue;
- raid manifests and timelines;
- manual raid start, end, and abort controls;
- live semantic markers for Stream Deck or hotkey tools;
- review draft, finalization, and audit-history endpoints;
- Markdown and JSON exports;
- controlled local evidence-file references.

The service binds to loopback by default. A non-loopback host is rejected unless an API token is configured.

### Browser review form

The bundled single-page form preloads raid metadata and supports:

- objectives and progress;
- loadout and weight;
- route, sound information, and decisions;
- multiple encounter records;
- end-of-raid statistics;
- analysis requests;
- draft saves and finalization;
- Markdown and JSON downloads.

### Review persistence and audit history

Reviews are stored as versioned JSON documents in SQLite. Each save records an immutable audit snapshot with the actor, action, version, time, and changed field paths. Optimistic version checks prevent a stale browser tab from silently overwriting newer work.

Finalized reviews are written into the raid package as:

```text
analysis/review.json
analysis/review.md
```

### Interrupted-session recovery

At startup the application checks unfinished raid records:

- an in-raid record is restored only when the Tarkov process is still running;
- an in-raid or ending record with no game process is moved to `review_pending` without inventing a survival result;
- an interrupted matchmaking candidate is marked `aborted`;
- all repairs are recorded as timeline events.

### Diagnostic log capture

The `capture-logs` command records only newly appended log lines for a limited duration and applies best-effort redaction for common identifiers such as user paths, email addresses, IP addresses, GUIDs, session values, and long hexadecimal identifiers.

Example:

```powershell
tarkov-agent capture-logs --config config.toml --seconds 180 --label pmc-survived
```

Captured samples must still be reviewed manually before sharing or committing. Redaction reduces risk; it does not prove that a sample is anonymous.

## Manual controls

Manual controls are a required fallback while current Tarkov log signatures remain unverified. They do not interact with the game client. They only change the companion's local lifecycle and OBS state.

Typical Stream Deck HTTP actions can call:

```text
POST /api/control/raid/start
POST /api/markers
POST /api/control/raid/end
```

## Evidence-path security

A manually referenced screenshot or recording must be located under either:

- the configured `data_root`; or
- a directory explicitly listed in `api.allowed_evidence_roots`.

This prevents an exposed local endpoint from being used as an unrestricted file browser.

## Exit condition

Phase 2 is complete when a real raid can be started manually, recorded through OBS, ended into the review queue, reviewed in the browser, finalized, and exported with timeline and evidence references intact.

Automatic log-driven raid start/end remains disabled until redacted samples have been validated across PMC, Scav, Arena, death, extract, disconnect, crash, Hideout, menu, and matchmaking cases.
