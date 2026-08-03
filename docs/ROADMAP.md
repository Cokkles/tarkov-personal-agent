# Roadmap

## Phase 0 — Foundation

Deliverables:

- Project charter and scope
- Safety boundary
- System architecture
- Data and event schemas
- Technology baseline
- Repository conventions
- Initial risk register
- Test strategy

Exit condition: the MVP can be implemented without unresolved architectural dependencies.

## Phase 1 — Raid Companion MVP

- Configuration loader
- Process observer
- Filesystem/log watcher
- Raid state machine
- OBS WebSocket adapter
- Raid package creation
- Manual semantic markers
- SQLite persistence
- Recovery after application or game crash
- CLI status and diagnostic commands

Exit condition: a local test session can create a recoverable raid package and control a mocked or real OBS instance.

## Phase 2 — Raid Review

- Local FastAPI service
- Browser review form
- Prefilled raid metadata
- Multiple encounter records
- Screenshot and recording references
- Markdown and JSON export
- Corrections and audit history

Exit condition: a completed raid can be reviewed and exported without manually rebuilding its metadata.

## Phase 3 — Personal Playstyle Engine

- Profile dimension registry
- Evidence weighting
- Context segmentation
- Encounter classification
- Contradiction handling
- Confidence and decay rules
- Profile history and comparison reports

Exit condition: repeated raid evidence produces explainable, context-specific profile updates.

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

## Deferred

- Cloud hosting
- Multi-user accounts
- Mobile application
- Real-time tactical guidance
- Automatic video understanding at full-raid scale
