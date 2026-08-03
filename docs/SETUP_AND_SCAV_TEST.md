# Full Setup, Configuration, and First Scav Raid Test

This guide starts from a fresh Windows checkout and ends with one reviewed Scav raid, an updated PPE evidence corpus, and a working Source-of-Truth query.

## 1. What the first test validates

The Scav test is intended to validate the local workflow, not automatic Tarkov log detection. It confirms that:

- the Python application starts;
- the local SQLite database and output folders are created;
- the browser applications load;
- manual raid start and end controls work;
- OBS recording starts and stops when enabled;
- live markers are timestamped;
- a completed raid enters the review queue;
- a finalized review generates PPE evidence conservatively;
- Source-of-Truth queries return citations and refusal states correctly;
- Markdown and JSON exports are written.

Automatic log rules remain empty for this first run. Do not add guessed signatures merely to make the test automatic.

## 2. Prerequisites

Install or confirm:

- Windows 10 or Windows 11;
- Git;
- Python 3.12, including the Python launcher;
- OBS Studio with WebSocket server support enabled;
- Escape from Tarkov;
- enough disk space for the selected OBS recording settings.

Use PowerShell for all commands below.

Check Python:

```powershell
py -3.12 --version
```

Check Git:

```powershell
git --version
```

## 3. Clone or update the repository

For a new installation:

```powershell
cd C:\
git clone https://github.com/Cokkles/tarkov-personal-agent.git TarkovPersonalAgentCode
cd C:\TarkovPersonalAgentCode
```

For an existing checkout:

```powershell
cd C:\TarkovPersonalAgentCode
git switch main
git pull
```

## 4. Create the Python environment

From the repository folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The prompt should show `(.venv)`. Reactivate it with the same activation command whenever a new PowerShell window is opened.

When PowerShell blocks activation, run this once in the current window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 5. Create the configuration

```powershell
tarkov-agent init --output config.toml
```

Open `config.toml` in a text editor.

A safe first-test configuration is:

```toml
[paths]
data_root = "C:/TarkovPersonalAgentData"
tarkov_log_roots = []

[process]
executable_names = [
  "EscapeFromTarkov.exe",
  "EscapeFromTarkov_BE.exe",
  "EscapeFromTarkovArena.exe",
]
poll_interval_seconds = 2.0

[logs]
file_globs = ["*.log", "*.txt"]
poll_interval_seconds = 1.0
start_at_end = true
minimum_auto_signal_confidence = 0.90
rules = []

[obs]
enabled = true
host = "127.0.0.1"
port = 4455
password = "REPLACE_WITH_YOUR_OBS_WEBSOCKET_PASSWORD"
timeout_seconds = 3.0
start_recording_on_raid_start = true
stop_recording_on_raid_end = true

[api]
enabled = true
host = "127.0.0.1"
port = 8765
token = ""
open_browser = true
allowed_evidence_roots = []

[diagnostics]
default_capture_seconds = 120.0
maximum_lines = 10000

[ppe]
enabled = true
neutral_prior_weight = 1.25
confidence_weight_scale = 2.5
maximum_weight_per_raid_dimension = 1.0
minimum_report_confidence = 0.25
minimum_established_confidence = 0.50
signal_threshold = 0.20
context_difference_threshold = 0.35
minimum_independent_raids = 3
maximum_history = 200

[truth]
enabled = true
seed_default_sources = true
minimum_verification_score = 0.72
minimum_supporting_citations = 1
claim_review_interval_days = 30
source_review_interval_days = 30
stale_grace_days = 14

[runtime]
auto_create_raid_package = true
auto_complete_raid_on_end = false
copy_evidence_into_package = false
recover_interrupted_sessions = true
graceful_shutdown_seconds = 10.0
```

### Path rules

Use a data directory outside the Git repository. The example separates application code from private raid data:

```text
C:\TarkovPersonalAgentCode\   source code
C:\TarkovPersonalAgentData\   database, raids, diagnostics, PPE, truth exports
```

Do not place recordings, account exports, or raw log archives in Git.

### OBS WebSocket settings

In OBS:

1. Open **Tools → WebSocket Server Settings**.
2. Enable the WebSocket server.
3. Keep the port at `4455` unless intentionally changed.
4. Enable authentication.
5. Copy the password into `[obs].password`.
6. Keep OBS running during the test.

The companion controls OBS recording; it does not change your encoder, resolution, track, or file-format settings.

### API settings

Keep the service on `127.0.0.1` for the first test. A token is not required for loopback-only access. Do not bind to the LAN unless a strong API token is configured and remote access is genuinely needed.

### Tarkov log settings

Leave `tarkov_log_roots` and `rules` empty for the first Scav raid. The application will use manual start/end controls. Process observation may report whether Tarkov is running, but process state alone does not prove that a raid started or ended.

## 6. Run diagnostics

Start OBS, then run:

```powershell
tarkov-agent doctor --config config.toml
```

Confirm in the JSON output:

```text
database_initialized: true
api.enabled: true
api.host: 127.0.0.1
obs.enabled: true
obs.connected: true
source_truth.enabled: true
source_truth.source_count: 4 or more
source_truth.verified_claim_count: 3 or more
automatic_log_rules: 0
```

A missing OBS connection should be corrected before the raid test. Typical causes are OBS not running, the server being disabled, a wrong password, or a mismatched port.

## 7. Verify Phase 4 before the raid

Show the corpus summary:

```powershell
tarkov-agent truth-status --config config.toml
```

Resolve a seeded Scav mechanic:

```powershell
tarkov-agent truth-query scav.extracted_loot_transfers `
  --game tarkov `
  --config config.toml
```

Confirm:

```text
resolution: verified
can_recommend: true
selected_claim.value: true
one or more citations are present
```

A query with an unknown key should refuse cleanly:

```powershell
tarkov-agent truth-query test.does_not_exist `
  --game tarkov `
  --config config.toml
```

That command intentionally returns a nonzero exit code because the claim is not safe for recommendation use.

## 8. Start the full local application

```powershell
tarkov-agent serve --config config.toml
```

Keep that PowerShell window open. The browser should open automatically.

Interfaces:

```text
http://127.0.0.1:8765/        Raid Review
http://127.0.0.1:8765/ppe     Personal Playstyle Engine
http://127.0.0.1:8765/truth   Source of Truth
```

Before entering Tarkov, open all three pages in browser tabs and confirm they load.

## 9. Start the Scav test raid

On the **Raid Review** page, select **Manual Start** and enter:

```text
Game: Tarkov
Map: the map selected in Tarkov
Character: Scav
Primary objective: Validate recording, markers, review, and exports
Secondary objective: Extract useful loot without forcing unnecessary combat
```

Start the manual record when the raid is actually loading into play, not when Tarkov merely launches. When manual start succeeds:

- a raid package is created;
- the timeline begins;
- OBS recording should start;
- the page should show an active raid.

Check OBS briefly before moving. The recording indicator should be active.

## 10. Use markers during the raid

Markers are optional but strongly recommended. Use the browser or your configured hotkey/Stream Deck call to record meaningful moments.

Suggested first-test markers:

```text
Spawn identified
First important audio cue
Possible PMC or player-Scav contact
High-value or objective-relevant loot
Route changed
Fight accepted
Fight avoided
Extract decision
Reached extract
```

A marker should capture an event or decision, not every routine action. Add short details when they change the interpretation, such as:

```text
Possible PMC — metal steps above; chose parallel route instead of pushing
```

## 11. End the raid correctly

After the post-raid result is known, use **End Raid** and enter a result such as:

```text
Survived
Killed
Missing in Action
Run Through
Disconnected
```

Do not use **Abort** for a normal death. Abort is for a false start, canceled test, or corrupted lifecycle record.

Ending the raid should:

- stop OBS recording when configured;
- close the active timeline;
- place the raid in the review queue;
- preserve the raid package even if some fields remain incomplete.

## 12. Complete the post-raid review

Select the raid in **Review Queue**. Correct and fill the fields that matter.

### Overview

Record:

- map;
- character type `Scav`;
- result;
- time of day;
- primary and secondary objective progress;
- objective priority;
- solo or group context.

### Loadout

A Scav loadout is random, so record what you actually spawned with:

- weapon;
- ammunition when known;
- optic or notable weapon configuration;
- armor, helmet, headset, and rig;
- start, first-contact, and extract weight when available;
- current patch when known.

Unknown values should remain unknown rather than guessed.

### Route and decisions

Record:

- spawn;
- extract;
- planned route, even when the plan formed after spawning;
- actual route;
- meaningful audio or visual information;
- major choices;
- what worked;
- uncertainty or problems.

### Encounters

Add one encounter for each meaningful hostile interaction. A heard player who was never found can still be recorded when it caused a decision, but do not fabricate detection order, range, shots, or outcome.

Useful structured fields include:

- opponent type;
- location;
- range;
- detection order;
- cover state;
- fired first;
- result classification;
- repositioning;
- same-angle re-peek;
- whether disengagement was available.

### Statistics and loot

Use the end-of-raid screens where available. Record:

- raid time;
- PMC and Scav kills;
- ammunition used and hits;
- damage;
- accuracy;
- XP;
- notable loot.

### Finalize

Save a draft first, review it, and then select **Finalize**.

Finalization is the point at which explicit structured fields become PPE evidence. Free-text narrative remains available to a human but is not silently converted into a skill claim.

## 13. Inspect PPE results

Open:

```text
http://127.0.0.1:8765/ppe
```

After one Scav raid, many dimensions should remain uncertain. That is correct. The engine uses neutral priors, confidence thresholds, and per-raid caps.

Expected conservative behavior includes:

- no PvP weakness claim when no qualifying contact occurred;
- low weight for survival or death by itself;
- objective and decision evidence only when the structured review supports it;
- contextual estimates separated by relevant conditions;
- adaptation and deliberate training shown separately.

The global files are written under:

```text
C:\TarkovPersonalAgentData\ppe\
```

The raid package may contain:

```text
analysis\ppe-evidence.json
analysis\ppe-profile-impact.json
```

## 14. Inspect Source-of-Truth results

Open:

```text
http://127.0.0.1:8765/truth
```

Run the three seeded queries:

```text
scav.main_stash_isolated
scav.extracted_loot_transfers
scav.random_loadout
```

Each should show a verified resolution, `can_recommend=true`, a canonical value, and a preserved citation.

The global exports are under:

```text
C:\TarkovPersonalAgentData\source-truth\
├── source-truth.json
└── source-truth.md
```

## 15. Inspect the raid package

Open:

```text
C:\TarkovPersonalAgentData\raids\
```

Find the most recent raid folder. Confirm that it contains the raid record, timeline, review/export artifacts, evidence references, and analysis outputs produced by the enabled phases.

OBS may store the video elsewhere according to its recording-path setting. The raid package can reference that recording; it does not need to copy a large video into the package.

## 16. Stop the service

Return to the PowerShell window running the service and press:

```text
Ctrl+C
```

Wait for the shutdown message. Avoid killing the terminal during an active write unless necessary.

## 17. After the first successful test

Recommended next steps are:

1. run two or three additional Scav raids to verify repeatability;
2. compare survived and killed outcomes;
3. test at least one real encounter with clear structured fields;
4. verify OBS file references and timestamps;
5. export a raid to Markdown and JSON;
6. export the Source-of-Truth corpus;
7. collect a short redacted log sample separately before considering automatic rules.

To collect a diagnostic sample after log paths are configured:

```powershell
tarkov-agent capture-logs `
  --config config.toml `
  --seconds 180 `
  --label scav-survived
```

Review the captured files manually before sharing or committing them.

## 18. Troubleshooting

### `tarkov-agent` is not recognized

Activate the virtual environment and reinstall:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### The browser page does not load

Confirm the service window is still running and that port `8765` is not already in use. Test:

```text
http://127.0.0.1:8765/api/health
```

### OBS does not start recording

Run `doctor`, then verify OBS WebSocket host, port, password, server state, and authentication. Confirm OBS can record manually with the selected profile and output path.

### A raid remains active after the game ends

Use manual **End Raid**. Automatic log signatures are not enabled in the initial configuration.

### The Source-of-Truth query refuses a claim

Read the returned `reason`. Common causes are:

- unknown key;
- no applicable patch;
- missing patch context;
- insufficient source score or support;
- stale review;
- conflicting values.

The refusal is a safety feature, not a service failure.

### The PPE shows almost no conclusions after one raid

That is expected. One raid is evidence, not a stable profile. Continue reviewing raids accurately rather than lowering thresholds merely to produce more labels.

## 19. First-test completion checklist

The initial Scav test is complete when all of these are true:

- `doctor` reports a healthy database, API, OBS connection, and Source of Truth;
- the three browser pages load;
- manual start creates an active Scav raid;
- OBS starts recording;
- at least one marker appears in the timeline;
- manual end stops recording and queues the raid;
- the review saves and finalizes;
- PPE evidence is generated without unsupported conclusions;
- a seeded Source-of-Truth query resolves as verified;
- Markdown and JSON exports exist;
- the service shuts down cleanly.
