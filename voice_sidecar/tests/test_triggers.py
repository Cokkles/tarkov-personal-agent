from __future__ import annotations

from pathlib import Path

import pytest

from tarkov_voice.triggers import TriggerEngine
from tarkov_voice.types import Word

RULES = Path(__file__).resolve().parents[1] / "triggers.toml"
BASE = 1_800_000_000.0


def words(text: str, start: float = BASE, step: float = 0.35) -> list[Word]:
    return [
        Word(text=t, start=start + i * step, end=start + i * step + 0.3)
        for i, t in enumerate(text.split())
    ]


@pytest.fixture()
def engine() -> TriggerEngine:
    return TriggerEngine.from_file(RULES)


def types(hits):
    return [h.marker_type for h in hits]


# The three callouts from the original request ---------------------------------------------


def test_hear_something_left(engine):
    hits = engine.scan(words("I hear something to my left."))
    assert types(hits) == ["contact.audio.possible_pmc"]


def test_spotted_a_guy(engine):
    hits = engine.scan(words("Spotted a guy."))
    assert types(hits) == ["contact.visual.player"]


def test_found_item_records_item(engine):
    hits = engine.scan(words("Found a red keycard."))
    assert types(hits) == ["loot.important"]
    assert hits[0].extra["item"] == "red keycard"
    assert "red keycard" in hits[0].details
    assert hits[0].confidence > 0.75  # important loot is boosted


# Timing ----------------------------------------------------------------------------------


def test_marker_time_is_when_phrase_started_not_sentence_start(engine):
    text = "So anyway I was walking along and I hear something to my left."
    hits = engine.scan(words(text))
    tokens = text.split()
    index = tokens.index("hear") - 1  # "i hear" begins at the token before "hear"
    assert hits[0].occurred_at == pytest.approx(BASE + index * 0.35)


# Stream talk --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Chat I always hear footsteps on this map.",
        "Yesterday I found a keycard in the same spot, chat.",
        "You can hear something to your left if you listen for it.",
        "Thanks for the follow, welcome to the stream everybody.",
        "I found out that the wipe is next week.",
        "I got him on the first try.",
        "Found the bug in my overlay.",
    ],
)
def test_stream_talk_does_not_create_markers(engine, line):
    assert engine.scan(words(line)) == []


def test_long_rambling_speech_still_finds_the_callout(engine):
    text = (
        "So the reason I picked this loadout is because the recoil is really manageable. "
        "Okay wait, I hear something to my left. "
        "Anyway that's what I was saying about the meta."
    )
    hits = engine.scan(words(text))
    assert types(hits) == ["contact.audio.possible_pmc"]


# Prefix mode -----------------------------------------------------------------------------


def test_prefix_gives_high_confidence(engine):
    hits = engine.scan(words("Mark mistake."))
    assert types(hits) == ["review.mistake"]
    assert hits[0].confidence >= 0.95
    assert hits[0].prefixed


def test_prefix_works_when_asr_splits_sentence(engine):
    hits = engine.scan(words("Mark. Heard something left."))
    assert types(hits) == ["contact.audio.possible_pmc"]
    assert hits[0].prefixed


def test_prefix_note_creates_free_form_marker(engine):
    hits = engine.scan(words("Mark note check the window on customs."))
    assert len(hits) == 1
    assert hits[0].marker_type is None
    assert "check the window on customs" in hits[0].details


def test_prefix_loot_alias_captures_item(engine):
    hits = engine.scan(words("Mark loot gpu."))
    assert types(hits) == ["loot.important"]
    assert hits[0].extra["item"] == "gpu"


def test_prefix_only_mode_ignores_natural_phrases():
    engine = TriggerEngine.from_file(RULES, mode="prefix_only")
    assert engine.scan(words("I hear something to my left.")) == []
    assert types(engine.scan(words("Mark good call."))) == ["review.good_decision"]


# Recognition quirks -----------------------------------------------------------------------


def test_spoken_letters_collapse_to_pmc(engine):
    hits = engine.scan(words("I hear a P M C behind me."))
    assert types(hits) == ["contact.audio.possible_pmc"]


def test_apostrophes_are_ignored(engine):
    hits = engine.scan(words("There's a guy on the roof."))
    assert types(hits) == ["contact.visual.player"]


# Duplicates ---------------------------------------------------------------------------------


def test_cooldown_suppresses_repeats_then_allows_later(engine):
    first = engine.scan(words("I hear something to my left.", start=BASE))
    repeat = engine.scan(words("I hear something to my left.", start=BASE + 3))
    later = engine.scan(words("I hear something to my left.", start=BASE + 30))
    assert len(first) == 1
    assert repeat == []
    assert len(later) == 1


def test_different_loot_items_are_not_collapsed(engine):
    a = engine.scan(words("Found a keycard.", start=BASE))
    b = engine.scan(words("Found a graphics card.", start=BASE + 2))
    assert len(a) == 1 and len(b) == 1


def test_min_confidence_drops_weak_hits():
    engine = TriggerEngine.from_file(RULES, min_confidence=0.9)
    assert engine.scan(words("I hear something to my left.")) == []
