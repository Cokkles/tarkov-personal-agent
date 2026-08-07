# Phase 7 — Evidence Intelligence Foundation

Phase 7 begins the transition from raid capture to evidence-driven analysis. The first sprint adds an Evidence Reduction Pipeline that turns a large local raid recording and its structured context into a compact, provenance-preserving package suitable for AI review.

## Core rule

The full source recording stays local by default. Evidence bundles contain recording references, hashes, probe metadata, structured raid data, and selected derivative media rather than blindly copying multi-gigabyte recordings into an upload package.

## Evidence profiles

- `metadata` — structured raid, review, PPE, timeline, and media metadata only.
- `standard` — structured evidence plus up to six highest-priority marker-centered derivative clips when available.
- `deep` — structured evidence plus up to twelve selected derivative clips when available.

Callers may override clip count and maximum payload bytes per bundle.

## Marker prioritization

The first deterministic ranking pass uses stable marker types rather than button labels. Combat, mistakes, visual contacts, and explicit good decisions are weighted above route and loot context. Timeline confidence is preserved and contributes to the final priority score.

This is evidence triage, not tactical judgment. It decides what deserves review first; it does not claim that an event was correct, incorrect, or fully understood.

## API

Preview a bundle without writing files:

```text
POST /api/raids/{raid_id}/evidence/preview
```

Build the latest ChatGPT-ready ZIP:

```text
POST /api/raids/{raid_id}/evidence/build
```

Download the latest bundle:

```text
GET /api/raids/{raid_id}/evidence/latest
```

Example request:

```json
{
  "profile": "standard",
  "max_clips": 6,
  "max_total_bytes": 150000000,
  "generate_missing_clips": false
}
```

Setting `generate_missing_clips` to `true` asks the existing FFmpeg media subsystem to create missing marker-centered clips. Failures are recorded as warnings rather than silently dropping provenance.

## Bundle contents

A bundle can contain:

- `raid.json`
- `timeline.jsonl`
- structured files under `analysis/`, including review, PPE, and media index exports
- selected screenshots already attached to the raid
- selected derivative clips
- `bundle-manifest.json`
- `README.md`

The manifest explicitly states that raw recordings were excluded and keeps the source recording references needed to trace any derivative evidence back to the original file.

## Next Phase 7 sprint

The next sprint should add frame extraction, encounter candidate clustering, evidence-to-review synchronization, and native Operations Center controls for previewing and building evidence packages. Later audiovisual classifiers can feed the same candidate model without changing the provenance contract.
