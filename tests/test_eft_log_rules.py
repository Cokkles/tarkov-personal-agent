from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

from tarkov_agent.config import LogSignalRule
from tarkov_agent.observers.logs import LogLine, LogSignalClassifier

ROOT = Path(__file__).resolve().parents[1]

APP = "2026-05-25 13:54:48.961|1.0.5.0.45272|Info|application|"
OUT = "2026-05-25 13:54:48.961|1.0.5.0.45272|Info|output|application|"


def _classifier() -> LogSignalClassifier:
    data = tomllib.loads((ROOT / "config.example.toml").read_text(encoding="utf-8"))
    return LogSignalClassifier(LogSignalRule(**rule) for rule in data["logs"]["rules"])


def _signals(text: str) -> list[str]:
    line = LogLine(Path("application_000.log"), 1, text, datetime.now(UTC))
    return [hit.signal.value for hit in _classifier().classify(line)]


def test_matching_completed_is_raid_candidate() -> None:
    line = APP + "MatchingCompleted:19.96 real:22.69 diff:2.71"
    assert _signals(line) == ["raid_candidate_found"]


def test_game_started_is_raid_start() -> None:
    assert _signals(APP + "GameStarted:99.96(0) real:116.12(0) diff:16.16") == ["raid_started"]


def test_gc_enabled_is_raid_end() -> None:
    # The application log writes this line at Debug level, not Info.
    debug = APP.replace("|Info|", "|Debug|")
    assert _signals(debug + "GC mode switched to Enabled") == ["raid_ended"]
    assert _signals(APP + "GC mode switched to Enabled") == ["raid_ended"]


def test_output_log_duplicates_are_ignored() -> None:
    assert _signals(OUT + "GameStarted:99.96(0) real:116.12(0) diff:16.16") == []
    assert _signals(OUT + "GC mode switched to Enabled") == []
    assert _signals(OUT.replace("|Info|", "|Debug|") + "GC mode switched to Enabled") == []


def test_unrelated_lines_do_nothing() -> None:
    for text in (
        APP + "GameStarting:99.96(0) real:116.12(0) diff:16.16",
        APP + "GC mode switched to Disabled",
        APP + "LocationLoaded:67.48 real:75.54 diff:8.05",
    ):
        assert _signals(text) == []


def test_rules_meet_auto_signal_threshold() -> None:
    data = tomllib.loads((ROOT / "config.example.toml").read_text(encoding="utf-8"))
    assert all(rule["confidence"] >= 0.90 for rule in data["logs"]["rules"])
