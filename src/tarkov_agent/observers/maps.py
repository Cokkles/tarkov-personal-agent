from __future__ import annotations

import re
from datetime import datetime, timedelta

# Map names come from real EFT session logs (client 1.0.5 to 1.1.5). A preset that is not
# listed is reported under its raw file name so nothing is lost; add it here once seen.
PRESET_MAP_NAMES: dict[str, str] = {
    "shopping_mall": "Interchange",
    "woods_preset": "Woods",
    "customs_preset": "Customs",
    "factory_day_preset": "Factory",
    "city_preset": "Streets of Tarkov",
    "sandbox_preset": "Ground Zero",
    "sandbox_high_preset": "Ground Zero",
    "sandbox_start_preset": "Ground Zero",
}

_PRESET = re.compile(
    r"\|Info\|application\|scene preset path:maps/(?P<preset>[A-Za-z0-9_]+)(?:\.bundle)?",
)


def map_name_for_preset(preset: str) -> str:
    return PRESET_MAP_NAMES.get(preset.lower(), preset)


class MapDetector:
    """Remembers the map the game most recently loaded so it can label the next raid.

    The preset line is logged while the raid is loading, before the raid start line, so the
    runtime asks for the map when the start signal arrives. A stale value is ignored.
    """

    def __init__(self, max_age: timedelta = timedelta(minutes=20)) -> None:
        self._max_age = max_age
        self._map_name: str | None = None
        self._seen_at: datetime | None = None

    def observe(self, text: str, observed_at: datetime) -> str | None:
        match = _PRESET.search(text)
        if match is None:
            return None
        self._map_name = map_name_for_preset(match.group("preset"))
        self._seen_at = observed_at
        return self._map_name

    def current(self, now: datetime) -> str | None:
        if self._map_name is None or self._seen_at is None:
            return None
        if now - self._seen_at > self._max_age:
            return None
        return self._map_name

    def clear(self) -> None:
        self._map_name = None
        self._seen_at = None
