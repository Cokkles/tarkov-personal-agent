# Tarkov Voice Sidecar (phase 2: trigger engine)

This phase contains only the part that decides *what counts as a marker*: the trigger rules,
the word-timestamp handling, and their tests. There is no microphone or speech model yet
(that is phase 3), so it needs nothing installed beyond Python 3.12.

Try the rules on typed text:

```bat
cd voice_sidecar
python -m tarkov_voice --text-test "I hear something to my left" "Found a red keycard" "Chat I always hear footsteps here"
```

Run the tests:

```bat
cd voice_sidecar
python -m pytest
```

`triggers.toml` holds every phrase. Patterns are regular expressions written against lower-case
text with punctuation and apostrophes removed ("there's" becomes "theres").

Requires the marker contract from phase 1 (`voice/01-marker-contract`) to place markers at the
moment you spoke rather than the moment they were received.
