# Safety and Compliance Boundary

## Allowed integration surface

The project is intentionally limited to ordinary user-space, passive or user-initiated operations:

- Observe whether configured processes are running.
- Read ordinary files written to disk by the game or launcher.
- Record the user's screen and configured audio through OBS.
- Receive explicit keyboard, Stream Deck, or UI marker commands.
- Read screenshots and files the user intentionally imports.
- Store and analyze the user's own raid evidence.
- Query public web sources outside of gameplay.

## Prohibited capabilities

The project must not implement or accept contributions that:

- Read, scan, scrape, or modify Escape from Tarkov process memory.
- Inject DLLs, hooks, overlays, drivers, or code into the game or anti-cheat processes.
- Intercept or manipulate game network traffic.
- Reveal information not ordinarily available to the player.
- Automate aiming, recoil control, movement, firing, looting, inventory actions, or matchmaking.
- Simulate gameplay input based on detected game state.
- Evade, disable, interfere with, or test bypasses against anti-cheat.
- Modify game files to change behavior.

## Real-time guidance boundary

The MVP is a recording and retrospective analysis system. It does not provide a real-time tactical overlay. Any future live feature must be limited to user-authored reminders or recording state and must undergo a separate compliance review.

## Data privacy

- Credentials must never be committed.
- API keys belong in environment variables or the operating system credential store.
- Full raid video and private account exports remain outside Git.
- Logs may contain identifiers or local paths and should be treated as private evidence.
- Exports intended for sharing should support redaction.

## Source and copyright handling

The knowledge base stores citations, summaries, structured facts, and short compliant excerpts. It does not mirror entire copyrighted guides, videos, wiki databases, or books without permission.

## Change review checklist

Every integration feature must answer:

1. Does it touch game memory, network traffic, or process internals?
2. Does it create gameplay input?
3. Does it expose information unavailable through normal play?
4. Can it be tested with mocks and fixtures instead of a live raid?
5. Is all collected data visible to and controllable by the user?

A "yes" to questions 1–3 blocks implementation pending explicit redesign.
