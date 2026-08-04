# Phase 6 — Media Assistance

## Purpose

Media Assistance turns an OBS output file into durable, traceable raid evidence without making video analysis a prerequisite for the core companion. It waits for a recording to finish writing, indexes the completed file, maps raid timeline events to seek offsets, and can create optional marker-centered clips.

The subsystem is reference-first. A normal raid does not duplicate its full recording inside the raid package unless copying is explicitly requested.

## Recording lifecycle

When a raid ends and OBS returns an output path, the coordinator now:

1. saves the ended raid state;
2. requests OBS recording stop;
3. waits until file size and modification time remain stable for the configured number of checks;
4. attaches the completed recording as raid evidence;
5. calculates SHA-256 and final size only after stabilization;
6. optionally reads duration, resolution, frame rate, codecs, and audio-stream count with `ffprobe`;
7. writes `analysis/media-index.json`;
8. appends a `recording_indexed` timeline event;
9. queues the raid for review.

A failure to index media does not discard or invalidate the raid. The timeline receives a `recording_index_error` or `recording_unindexed` event with the reason.

## Storage model

Default behavior:

```text
OBS recording folder
└── raid-recording.mkv

TarkovPersonalAgentData/
├── raids/<raid-package>/
│   ├── raid.json
│   ├── timeline.jsonl
│   └── analysis/media-index.json
└── media/
    └── clips/<raid-id>/
```

The recording evidence stores its canonical path, final size, SHA-256, availability, source, and probe metadata. The raid package points to the original recording.

Set this only when every full recording should be copied into its raid package:

```toml
[media]
copy_recordings_into_package = true
```

Reference-first storage is recommended because normal raid recordings can be large and copying them doubles storage use.

## Configuration

Add the OBS recording folder to the allowed evidence roots when it is outside the agent data root:

```toml
[api]
allowed_evidence_roots = [
  "D:/OBS Recordings"
]
```

Media settings:

```toml
[media]
enabled = true
copy_recordings_into_package = false
file_stability_timeout_seconds = 30.0
file_stability_poll_seconds = 0.5
file_stability_checks = 3
ffprobe_path = "ffprobe"
ffmpeg_path = "ffmpeg"
probe_timeout_seconds = 20.0
clip_timeout_seconds = 180.0
default_clip_seconds_before = 10.0
default_clip_seconds_after = 15.0
```

`ffprobe` and `ffmpeg` are optional. Recording indexing, hashing, availability tracking, and timeline navigation still work without them. Probe metadata is marked unavailable when `ffprobe` is not installed. Clip extraction returns a clear tool-unavailable error when `ffmpeg` is missing.

## Browser workflow

Start the companion and open:

```text
http://127.0.0.1:8765/media
```

The Media Assistance page can:

- load a raid media index;
- manually associate an existing recording;
- choose reference or copy behavior;
- display indexed recording path, size, hash, probe state, and duration;
- list timestamped timeline events and Stream Deck markers;
- request a clip around a selected marker.

Manual association is useful for older raids or recordings created before automatic indexing was enabled.

## API

```text
GET  /api/raids/{raid_id}/media
GET  /api/raids/{raid_id}/media/navigation
POST /api/raids/{raid_id}/media/recordings
POST /api/raids/{raid_id}/media/clips
POST /api/raids/{raid_id}/media/refresh
```

Manual recording request:

```json
{
  "path": "D:/OBS Recordings/2026-08-04_raid.mkv",
  "copy_into_package": false
}
```

Marker-centered clip request:

```json
{
  "timeline_event_id": "00000000-0000-0000-0000-000000000000",
  "seconds_before": 10,
  "seconds_after": 15,
  "label": "PMC Heard"
}
```

A clip may instead use an explicit `raid_offset_ms`, but exactly one anchor must be supplied.

## Marker navigation

Every timestamped timeline event becomes a `MediaNavigationPoint` containing:

- recording identifier;
- timeline event identifier;
- event type and label;
- raid offset in milliseconds;
- seek time in seconds;
- event source and optional marker category.

This creates the stable contract needed for a later integrated video player. The current browser page exposes offsets and clip generation; direct browser playback is intentionally not required because OBS container and codec combinations vary.

## Evidence integrity

The final recording hash is not calculated immediately when the stop request is sent. File stabilization must complete first. This prevents the metadata mismatch that can occur while OBS is still finishing the container.

Repeated indexing of the same unchanged path is idempotent: it returns the existing indexed asset instead of adding duplicate evidence.

## Safety boundary

Media Assistance:

- does not read Tarkov memory;
- does not inject into the game;
- does not automate gameplay;
- does not upload recordings;
- restricts manual paths to the data root or configured allowed evidence roots;
- treats FFmpeg, transcription, scene detection, OCR, and computer vision as optional local tools;
- preserves the original recording separately from future interpretations.

## Exit condition

Phase 6 is complete when a finalized OBS or manually selected recording can be indexed after file stabilization, preserved by reference or copy, mapped to timeline offsets, checked for availability, and used to create optional local clips without becoming a dependency for raid logging or review.
