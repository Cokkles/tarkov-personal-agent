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

## Phase 4 — Source of Truth

- Source registry
- Claim model
- Patch applicability
- Source ranking
- Conflict detection
- Scheduled review workflow
- Citation-preserving exports

Exit condition: recommendations can query verified mechanics and refuse unresolved claims.

## Phase 5 — Recommendation Engine

- Candidate strategy generation
- Hard mechanical constraint filtering
- Objective and player-fit scoring
- Progression versus training recommendations
- Assumption and confidence reporting
- Experiment design

Exit condition: the system produces a primary and fallback plan with traceable evidence.

## Phase 6 — Media Assistance

- Recording indexing
- User marker navigation
- Optional local transcription
- Optional scene-change assistance
- Clip extraction with FFmpeg
- End-of-raid screenshot workflow

Computer vision and OCR remain optional and must not become prerequisites for core logging.

## Phase 7 — Arena and Squad Extensions

- Arena match schema
- Mode-specific outcomes
- Mechanical practice reports
- Squad-role context
- Team communication markers

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
- Real-time tactical guidance
- Automatic video understanding at full-raid scale
