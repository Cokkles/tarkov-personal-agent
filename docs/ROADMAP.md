# Roadmap

## Phase 0 — Foundation — Complete

Delivered:

- Project charter and scope
- Safety boundary
- System architecture
- Data and event schemas
- Technology baseline
- Repository conventions
- Initial risk register
- Test strategy

Exit condition met: the MVP implementation proceeded without unresolved architectural dependencies.

## Phase 1 — Raid Companion MVP — Complete

Delivered:

- Typed configuration loader
- Passive process observer
- Rotation-tolerant filesystem/log observer
- Deterministic raid state machine
- OBS WebSocket adapter
- Recoverable raid package creation
- Manual semantic markers
- SQLite persistence and migrations
- CLI status and diagnostic commands
- Cross-platform automated tests

Exit condition met: local test sessions can create recoverable raid packages and control mocked or real OBS instances.

## Phase 2 — Raid Review — Complete

Delivered:

- Local FastAPI service
- Browser review form
- Manual raid start, end, and abort fallback controls
- Prefilled raid metadata
- Multiple encounter records
- Controlled screenshot and recording references
- Markdown and JSON export
- Versioned corrections and audit history
- Post-raid review queue
- Interrupted-session recovery
- Privacy-aware diagnostic log capture
- Loopback-first API security and token requirement for non-loopback binding

Exit condition met: a completed raid can be queued, reviewed, corrected, finalized, and exported without manually rebuilding its metadata.

## Phase 3 — Personal Playstyle Engine — Complete

Delivered:

- Versioned profile-dimension registry
- Explicit evidence roles, source reliability, strength, confidence, and rationale
- Conservative extraction from finalized structured raid reviews
- Global and context-specific profile estimates
- Per-raid evidence caps to prevent one raid from dominating a dimension
- Neutral priors and recency half-life decay
- Contradiction detection and confidence reduction
- Independent raid counts and supporting evidence references
- Immutable profile snapshots and profile-update audit history
- Evidence-corpus fingerprints and idempotent rebuilds
- Manual evidence workflow with dimension validation
- Adaptation guidance separated from optional deliberate training
- Browser PPE dashboard
- PPE API and CLI rebuild command
- Per-raid PPE evidence and profile-impact exports
- Cross-platform automated tests

Exit condition met: repeated raid evidence produces explainable, context-specific profile updates without treating isolated outcomes as permanent traits.

## Phase 4 — Source of Truth — Complete

Delivered:

- Source registry with authority, reliability, game scope, topics, lifecycle, and review schedule
- Patch-aware claim model with canonical values and preserved citations
- Inclusive introduction and exclusive removal patch windows
- Source ranking with freshness and review penalties
- Claim verification scores and minimum-support requirements
- Draft, verified, disputed, stale, rejected, and refusal states
- Automatic conflict detection for overlapping claims with different values
- Blocking conflict and overdue review queue
- Mechanics query contract with explicit `can_recommend` gating
- Refusal for unknown, ambiguous, stale, unsupported, or conflicting mechanics
- Citation-preserving Markdown and JSON exports
- Seeded publisher, wiki, structured-data, and Scav validation records
- Browser Source-of-Truth dashboard
- Source-of-Truth API and CLI commands
- SQLite migration and cross-platform automated tests
- Full Windows setup and Scav test guide

Exit condition met: recommendations can query verified mechanics and refuse unresolved claims.

## Phase 5 — Recommendation Engine — Complete

Delivered:

- Deterministic PMC, Scav, progression, and training candidate generation
- Hard mechanical filtering through the Source-of-Truth query contract
- Explicit blocking for missing, stale, disputed, conflicting, and patch-ambiguous mechanics
- Objective, player-fit, and risk-posture scoring
- PPE context preference with global fallback
- Supporting PPE evidence references and mechanic citations
- Primary and fallback strategy selection
- Assumption, confidence, blocker, and research-task reporting
- Controlled single-variable experiment designs for training requests
- Local Markdown and JSON history
- Browser dashboard, local API, and CLI command
- Cross-platform automated tests

Exit condition met: the system produces a primary and fallback plan with traceable mechanics and player evidence.

## Phase 6 — Media Assistance — Complete

Delivered:

- Reliable OBS output association after file finalization
- Configurable file-size and modification-time stability checks
- Recording index with canonical path, duration, dimensions, codecs, stream count, size, SHA-256, and availability
- Reference-first storage with optional package copying
- Idempotent re-indexing for unchanged recordings
- Timeline and Stream Deck marker navigation offsets
- Optional FFmpeg clip extraction around selected markers
- Optional ffprobe media inspection
- Manual association for earlier or externally managed recordings
- Media index, browser dashboard, and local API
- Clear timeline events for indexed, unindexed, and failed recording finalization
- Approved-root enforcement for media paths
- Cross-platform automated tests

Exit condition met: completed recordings can be indexed after stabilization, preserved by reference or copy, mapped to timeline events, and used for optional local clips without becoming a dependency for raid logging or review.

## Phase 6.5 — Desktop Companion — Complete

Delivered:

- Native PySide6 desktop dashboard
- One-shortcut embedded local service startup
- Ownership-aware connection to independently running services
- Lifecycle, active raid, OBS, review queue, PPE, and parser-rule status
- Manual Start Raid, End Raid, and Abort Raid controls
- Seven validated live marker buttons
- One-click access to Raid Review, PPE, Source of Truth, Recommendations, Media, and API docs
- Windows system-tray operation
- Optional start-with-Windows shortcut
- One-command dependency installation and shortcut creation
- Local desktop logs and typed desktop-status API
- Headless-safe optional GUI dependency
- Cross-platform automated tests for the API client, service ownership, and status route

Exit condition met: one native shortcut can start or connect to the local service, display operational status, control the manual raid lifecycle, create markers, open every workspace, remain in the system tray, and stop only the service instance it owns.

## Phase 7 — Arena and Squad Extensions

- Arena match schema
- Mode-specific outcomes
- Mechanical practice reports
- Squad-role context
- Team communication markers

## Phase 8 — Advanced Audiovisual Analysis

- Isolated OBS tracks for game audio, microphone, team communication, and full mix
- Tarkov-specific sound-event detection
- Missed-audio-cue analysis
- Communication masking analysis
- Visual event detection for brief distant movement and partially obscured contacts
- Cognitive-load modeling that separates objective cues from what the player could reasonably perceive
- Dispute and correction workflow for false positives, missed events, bad timestamps, and mistaken conclusions

## Parallel validation track — Tarkov log signatures

This track remains deliberately separate from feature phases:

- Collect redacted PMC, Scav, Arena, death, extract, disconnect, reconnect, and crash samples
- Compare start/end candidates across patches
- Test false positives against launcher, menus, Hideout, matchmaking, and cancellation
- Version parser rules and fixtures
- Keep manual controls available even after automatic rules are enabled

## Deferred

- Cloud hosting
- Multi-user accounts
- Mobile application
- Hidden real-time tactical direction
- Full-raid video understanding as a mandatory dependency
