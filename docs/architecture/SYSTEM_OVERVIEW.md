# System Overview

## Architectural style

The platform uses a modular, local-first architecture with append-only evidence ingestion and separately generated interpretations.

```text
Escape from Tarkov / Arena
          |
          | passive files and process state only
          v
+------------------------+
| Raid Companion         |
| - process observer     |
| - log watcher          |
| - OBS adapter          |
| - marker service       |
+-----------+------------+
            |
            v
+------------------------+
| Raid Package Builder   |
| - identity             |
| - manifest             |
| - evidence references  |
+-----------+------------+
            |
            +------------------+
            |                  |
            v                  v
+------------------+   +--------------------+
| SQLite Metadata  |   | External Evidence  |
| and indexes      |   | videos/logs/images |
+--------+---------+   +--------------------+
         |
         v
+------------------------+
| Timeline Engine        |
| normalized events      |
+-----------+------------+
            |
     +------+------+
     |             |
     v             v
+----------+  +-------------------+
| Raid UI  |  | Analysis Pipeline |
+----------+  | SoT -> PPE -> Rec  |
              +-------------------+
```

## Trust boundaries

### Observed evidence

Examples: raw log lines, recording file metadata, screenshots, hotkey markers, and user notes. Evidence is not silently altered after ingestion.

### Derived facts

Examples: parsed raid start, probable map, elapsed timestamp, or detected recording state. Every derived fact records its source, parser version, and confidence.

### Interpretations

Examples: fight classification, profile evidence, or recommendations. Interpretations can be regenerated when prompts, rules, or models change.

## Core components

### Process Observer

Detects configured executable state. It does not inspect game memory. Process state alone must not be treated as proof that a raid began.

### Log Watcher

Tails configured text files, checkpoints offsets, handles file rotation, and emits normalized candidate events. Parsers are versioned and replaceable.

### Raid State Machine

Correlates multiple signals into states:

```text
IDLE -> GAME_RUNNING -> MATCHMAKING -> RAID_CANDIDATE -> IN_RAID
IN_RAID -> ENDING -> REVIEW_PENDING -> COMPLETE
```

Transitions require explicit evidence rules, timeouts, and recovery behavior. Reconnects and crashes must not create duplicate raids.

### OBS Adapter

Uses OBS WebSocket through a narrow interface. It can query state, start recording, stop recording, and obtain the active output path. The adapter must be mockable for tests.

### Marker Service

Accepts user hotkeys or UI actions and writes timestamped semantic markers. Markers are local annotations, not game inputs.

### Raid Package Builder

Creates a stable raid ID and manifest. Large evidence remains in configured external storage; the database stores checksums, paths, size, media metadata, and availability.

### Timeline Engine

Normalizes events from logs, markers, recordings, screenshots, and notes onto a raid-relative clock. Conflicting events are preserved rather than silently collapsed.

### Source-of-Truth Layer

Stores claims separately from sources. Claims have patch applicability, verification status, source rank, retrieval date, and conflict state.

### Personal Playstyle Engine

Consumes encounter evidence and updates context-specific profile dimensions using explicit scores, evidence weights, contradictions, and confidence.

### Recommendation Engine

Generates valid candidate strategies, rejects mechanically invalid options, scores remaining plans for objective fit and player fit, and reports assumptions.

## Technology baseline

- Python 3.12+
- SQLite for local metadata
- Pydantic for domain validation
- SQLAlchemy and Alembic for persistence and migrations
- `watchdog` or equivalent for filesystem observation
- `psutil` for process presence only
- OBS WebSocket 5.x client through an adapter
- FastAPI for a local API
- Browser-based review UI initially; desktop packaging deferred
- Pytest for automated tests

## Storage strategy

```text
Configured data root/
  raids/YYYY/MM/<raid-id>/
    manifest.json
    recording.mkv or external link
    events.ndjson
    screenshots/
    imported-logs/
    exports/
    analysis/
```

The data root is configurable and should normally be outside the Git checkout.

## Failure principles

- Missing OBS must not prevent manual logging.
- Unrecognized Tarkov logs must be preserved as raw evidence.
- A parser failure must not destroy or truncate files.
- A crash during a raid must leave a recoverable package.
- Automatic actions must be idempotent.
- The user must always be able to correct derived metadata.
