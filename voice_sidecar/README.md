# Tarkov Voice Sidecar

Listens to your microphone while you play or stream, transcribes everything locally on your GPU,
and turns callouts into markers on the raid timeline:

| You say | Marker |
|---|---|
| "I hear something to my left" | PMC Heard |
| "Spotted a guy" / "there's a guy on the roof" | Player Seen |
| "Found a red keycard" | Important Loot (item name saved) |
| "I'm engaging" / "taking fire" | Fight Started |
| "Changing plans" / "rotating to..." | Route Changed |
| "That was a mistake" / "my bad" | Mistake |
| "Good call" / "nailed it" | Good Decision |

Audio never leaves your PC. The only download is the speech model, once, on first run.

## How it copes with stream talk

The sidecar transcribes everything you say, but only reacts to short callout phrases. Sentences that
look like talking to chat or telling a story ("chat, I always hear footsteps here", "yesterday I
found a keycard") have their confidence cut and are dropped. You can also be explicit:

- Say **"mark"** first for a certain marker: "mark mistake", "mark heard left", "mark loot gpu".
- **"mark note ..."** saves anything you say as a free-form note on the timeline.

Each marker is timestamped when the phrase **began**, using the audio clock, so it lands on the
right frame even when transcription takes a couple of seconds. This needs the marker contract from
branch `voice/01-marker-contract`; without it markers are stamped when the agent receives them.

The full transcript is saved to `<data_root>\voice\transcripts\session_*.jsonl` with word-level
times, so a post-raid pass can find callouts the live rules missed.

## Install (Windows, once)

```bat
cd voice_sidecar
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

The two `nvidia-*` packages supply the CUDA libraries for an RTX GPU. If the GPU cannot start, the
sidecar falls back to `small.en` on the CPU and says so in the console.

## Use

```bat
run_voice.bat --list-devices        rem find your mic; set [audio] device in voice.toml
run_voice.bat --dry-run             rem transcribe and show markers, send nothing
run_voice.bat                       rem live: posts markers to the agent
```

Start it before you play. Callouts made outside a raid are kept in the transcript and skipped for
markers (the agent only accepts markers during a raid).

Tune the rules without a microphone:

```bat
run_voice.bat --text-test "I hear something to my left" "Chat I always hear footsteps here"
```

Test on an old recording (16 kHz mono wav; `--wav-start` is when the wav's first sample was recorded):

```bat
ffmpeg -i "raid.mkv" -vn -ac 1 -ar 16000 -sample_fmt s16 mic.wav
run_voice.bat --dry-run --wav mic.wav
```

## Settings

`voice.toml` holds the microphone, model and sensitivity. It reads the API address, token and data
folder from the agent's own `config.toml` (the file one level up), so the token is not copied.
`triggers.toml` holds every phrase.

Model choices, fastest to most accurate: `small.en`, `distil-large-v3` (default), `large-v3-turbo`.
Set `compute_type = "int8_float16"` to free about 1 GB of VRAM for the game.

## What is tested

The trigger rules (including stream-talk false positives), speech segmentation on synthetic audio,
and the sender against a fake agent server (`python -m pytest` in this folder). Not covered by
automated tests: live microphone capture, the Whisper model on a GPU, and long sessions. Run
`--dry-run` for a few minutes first and compare the transcript with what you actually said.
