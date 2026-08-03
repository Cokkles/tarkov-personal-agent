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

## Phase 3 — Personal Playstyle Engine

- Profile dimension registry
- Evidence weighting and source reliability
- Context segmentation by map, objective, range, loadout, group size, and raid state
- Encounter classification
- Decision-point and outcome records
- Contradiction handling
- Confidence and decay rules
- Player adaptation versus deliberate training recommendations
- Profile history and comparison reports
- Explainable profile-update audit trail

Exit condition: repeated raid evidence produces explainable, context-specific profile updates without treating isolated outcomes as permanent traits.

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
