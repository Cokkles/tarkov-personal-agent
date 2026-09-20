from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tarkov_agent.observers.maps import MapDetector, map_name_for_preset

T0 = datetime(2026, 8, 8, 11, 23, tzinfo=UTC)
LINE = (
    "2026-08-08 11:23:34.949|1.1.0.0.46657|Info|application|"
    "scene preset path:maps/{}.bundle rcid:x.ScenesPreset.asset"
)


def test_known_presets_map_to_names() -> None:
    assert map_name_for_preset("shopping_mall") == "Interchange"
    assert map_name_for_preset("customs_preset") == "Customs"
    assert map_name_for_preset("sandbox_high_preset") == "Ground Zero"


def test_unknown_preset_is_reported_raw() -> None:
    assert map_name_for_preset("shoreline_preset") == "shoreline_preset"


def test_detector_holds_the_map_until_the_raid_starts() -> None:
    detector = MapDetector()
    assert detector.observe(LINE.format("woods_preset"), T0) == "Woods"
    assert detector.current(T0 + timedelta(minutes=2)) == "Woods"
    detector.clear()
    assert detector.current(T0 + timedelta(minutes=2)) is None


def test_stale_map_is_ignored() -> None:
    detector = MapDetector(max_age=timedelta(minutes=20))
    detector.observe(LINE.format("woods_preset"), T0)
    assert detector.current(T0 + timedelta(minutes=30)) is None


def test_output_log_copy_is_ignored() -> None:
    copy = LINE.replace("|Info|application|", "|Info|output|application|")
    assert MapDetector().observe(copy, T0) is None


def test_latest_preset_wins() -> None:
    detector = MapDetector()
    detector.observe(LINE.format("woods_preset"), T0)
    detector.observe(LINE.format("customs_preset"), T0 + timedelta(minutes=1))
    assert detector.current(T0 + timedelta(minutes=2)) == "Customs"
