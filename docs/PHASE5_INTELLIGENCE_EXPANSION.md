# Phase 5 — Intelligence Expansion

## Sprint 1: Structured Markers and Native Stream Deck Control

This sprint replaces shell-based Stream Deck marker calls with a native local plugin and establishes a stable marker contract for later media, audiovisual, tactical, and dispute workflows.

## Delivered capabilities

### Structured marker IDs

The seven validated markers now have stable identifiers independent of their display labels:

| Marker | Stable type |
|---|---|
| PMC Heard | `contact.audio.possible_pmc` |
| Player Seen | `contact.visual.player` |
| Fight Started | `combat.engagement.started` |
| Route Changed | `decision.route.changed` |
| Important Loot | `loot.important` |
| Mistake | `review.mistake` |
| Good Decision | `review.good_decision` |

Legacy clients that send only `label` and `category` remain supported.

Each new marker can preserve:

- stable marker type;
- canonical label and category;
- optional details;
- originating client, such as `stream_deck`, `desktop`, or `marker_exe`;
- client request identifier;
- exact raid timestamp and offset.

### Duplicate-press protection

Identical markers from the same source within 750 milliseconds are treated as one event. The original event is returned, so a rapid accidental double press does not create duplicate timeline evidence or produce a false failure.

### Console-free marker helper

The Python package now installs `tarkov-marker.exe` as a Windows GUI entry point. It can be used by external automation without opening a console window.

Example:

```powershell
.\.venv\Scripts\tarkov-marker.exe `
  "contact.audio.possible_pmc" `
  --config "C:\TarkovPersonalAgent\TarkovPersonalAgentCode\config.toml"
```

Failures are written to:

```text
<data_root>/desktop/markers.log
```

The helper is a fallback and general automation interface. The native Stream Deck plugin is the primary Stream Deck workflow.

## Native Stream Deck plugin

The plugin provides:

- Agent Status;
- Start Raid;
- End Raid;
- PMC Heard;
- Player Seen;
- Fight Started;
- Route Changed;
- Important Loot;
- Mistake;
- Good Decision.

Marker actions send structured events directly to the local API. Successful actions display Stream Deck's green confirmation. Failed actions display the warning indicator. Agent Status reports `AGENT ONLINE`, `AGENT OFFLINE`, or `RAID ACTIVE` and refreshes every three seconds.

### Plugin settings

The property inspector supports:

- local agent URL;
- optional API token;
- Start Raid map, character type, and objectives;
- End Raid result;
- connection testing.

The default agent URL is:

```text
http://127.0.0.1:8765
```

### Install or update

Close normal raid activity, then run from the repository root:

```powershell
.\scripts\install_stream_deck_plugin.ps1
```

The script:

1. stops Stream Deck if it is running;
2. copies the plugin to the user's Stream Deck plugin directory;
3. restarts Stream Deck when its executable can be located;
4. leaves existing user profiles intact.

After restart, add actions from the **Tarkov Personal Agent** category. Existing PowerShell marker buttons may remain temporarily as a fallback while the new buttons are tested.

## Validation checklist

1. Launch Tarkov Personal Agent Desktop and confirm the service is online.
2. Install the Stream Deck plugin.
3. Add Agent Status and confirm it displays `AGENT ONLINE`.
4. Start a test raid from the desktop or Start Raid action.
5. Confirm Agent Status changes to `RAID ACTIVE`.
6. Press each marker once and confirm a green check appears.
7. Press one marker twice rapidly and confirm only one timeline event is stored.
8. End the raid and verify all marker events appear in the review package with `source = stream_deck` and their stable `marker_type` values.
9. Keep the full package as the first Stream Deck plugin regression fixture.

## Safety and architecture

The plugin is a thin local API client. It does not:

- read Tarkov memory;
- inject into the game;
- automate gameplay;
- contain PPE or media-analysis logic;
- upload recordings or evidence;
- bypass the agent's active-raid and API-token checks.

All authoritative lifecycle, marker, database, media, review, and PPE behavior remains in the local Tarkov Personal Agent service.

## Next sprint

After the marker/plugin field test passes, Phase 5 continues with:

1. asynchronous End Raid finalization and visible media-job state;
2. FFmpeg and ffprobe dependency diagnostics;
3. automatic marker-centered clips and key frames;
4. compact AI-ready evidence packages;
5. the Operations Center v2 shell and Review Studio workflow.
