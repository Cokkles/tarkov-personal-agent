# Phase 6 Validation Checklist

- Ruff passes without new exclusions.
- Strict mypy passes for all `tarkov_agent` modules.
- Pytest passes on Windows and Ubuntu with Python 3.12.
- A stable recording under an allowed root is indexed with final size and SHA-256.
- Re-indexing the same unchanged recording does not duplicate raid evidence.
- Reference-first mode preserves the original path without copying the full file.
- Copy mode places the recording under `evidence/recordings`.
- Missing `ffprobe` leaves indexing functional and records probe status as unavailable.
- Timestamped markers produce navigation points with matching millisecond and second offsets.
- Missing `ffmpeg` produces a clear clip-tool error without damaging the raid or recording.
- OBS stop output is persisted before review queueing.
- Media indexing failure is recorded on the timeline and does not discard the raid.
- Manual recording paths outside approved roots are rejected.
- Media API and dashboard remain loopback-first under the existing API security boundary.
- Recording, clip, and media-index files remain local.
