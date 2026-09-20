from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True, slots=True)
class Word:
    """One transcribed word. ``start`` and ``end`` are absolute wall-clock epoch seconds."""

    text: str
    start: float
    end: float
    probability: float = 1.0


@dataclass(slots=True)
class Utterance:
    """A stretch of speech cut out of the mic stream."""

    index: int
    audio: np.ndarray  # float32, mono, sample_rate Hz
    start_wall: float  # epoch seconds of the first sample
    sample_rate: int
    overlap_s: float = 0.0  # leading audio that repeats the previous utterance
    forced_split: bool = False

    @property
    def duration_s(self) -> float:
        return len(self.audio) / float(self.sample_rate)


@dataclass(slots=True)
class Hit:
    """A marker candidate found in the transcript."""

    marker_type: str | None  # None means a free-form voice note
    label: str
    confidence: float
    occurred_at: float  # epoch seconds when the trigger phrase began
    details: str
    prefixed: bool = False
    rule: str = ""
    extra: dict[str, str] = field(default_factory=dict)
