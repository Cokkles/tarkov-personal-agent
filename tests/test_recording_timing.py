from __future__ import annotations

from types import SimpleNamespace

from tarkov_agent.config import MediaSettings
from tarkov_agent.services.media import MediaService


def _shift(events: list[SimpleNamespace], fixed: int = 0) -> int:
    service = MediaService.__new__(MediaService)
    service._settings = MediaSettings(timing_offset_ms=fixed)  # noqa: SLF001
    return service._video_shift_ms(events)  # noqa: SLF001


def _event(lag: object) -> SimpleNamespace:
    return SimpleNamespace(
        event_type="recording_started", payload={"recording_lag_ms": lag}
    )


def test_video_lags_the_raid_clock() -> None:
    assert _shift([_event(1500)]) == -1500


def test_no_recording_event_means_no_shift() -> None:
    assert _shift([SimpleNamespace(event_type="marker", payload={})]) == 0


def test_fixed_offset_stacks_on_lag() -> None:
    assert _shift([_event(1000)], fixed=400) == -600


def test_bad_lag_values_are_ignored() -> None:
    assert _shift([_event("soon")]) == 0
    assert _shift([_event(-5)]) == 0
