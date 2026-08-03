# Project Charter

## Mission

Build a local-first Tarkov intelligence platform that records raid evidence, preserves trustworthy game knowledge, learns how the player performs in context, and produces explainable recommendations for progression, survival, PvP, economy, and training.

## Primary user

The initial system is designed for one player and one Windows workstation. Multi-user support is a future concern, not an MVP requirement.

## Goals

- Capture raid metadata with minimal manual work.
- Associate recordings, screenshots, logs, markers, and notes with one raid identity.
- Maintain a patch-aware Source of Truth for Escape from Tarkov and Arena.
- Analyze encounters without reducing every result to aim or reaction speed.
- Maintain a multidimensional Personal Playstyle Engine with evidence and confidence.
- Distinguish progression advice from training advice.
- Preserve enough documentation and schema history to rebuild the project.
- Keep integrations modular so OBS, parsers, storage, and AI providers can change independently.

## Non-goals

- Reading or modifying game memory.
- Injecting into the game process.
- Automating movement, aiming, looting, combat, or other gameplay.
- Providing real-time hidden-information advantages.
- Replacing Battlestate Games services or bypassing anti-cheat.
- Treating community anecdotes as verified game mechanics.
- Storing large videos or private account data in Git.

## Major subsystems

1. Raid Companion
2. Raid Evidence Store
3. Timeline Engine
4. Source-of-Truth Knowledge Base
5. Personal Playstyle Engine
6. Recommendation Engine
7. Raid Review UI
8. Export and Backup System

## Success criteria for the MVP

The MVP is successful when it can:

- Detect a configured Tarkov session and monitor a configured log directory.
- Start and stop an OBS recording through OBS WebSocket using explicit state rules.
- Create a unique raid package folder.
- Record manual timestamped markers.
- Store raid metadata in SQLite.
- Open a post-raid review form with known fields prefilled.
- Export a complete raid summary as JSON and Markdown.
- Run deterministic validation against versioned schemas.
- Operate without touching game memory or automating gameplay.

## Governance

- `main` contains stable, reviewed project state.
- Significant design choices receive an Architecture Decision Record.
- Schemas are versioned and migrations are required for breaking changes.
- Raw evidence is immutable by default; interpretations may be regenerated.
- AI outputs never overwrite source evidence.
