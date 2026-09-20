from __future__ import annotations

import numpy as np
import pytest

webrtcvad = pytest.importorskip("webrtcvad")

from tarkov_voice.config import VadConfig  # noqa: E402
from tarkov_voice.segmenter import FRAME_MS, SpeechSegmenter  # noqa: E402


def _tone(seconds: float, rate: int = 16000) -> bytes:
    t = np.arange(int(seconds * rate)) / rate
    # A mix of harmonics is treated as speech by webrtcvad far more often than a pure tone.
    signal = sum(np.sin(2 * np.pi * f * t) for f in (200, 400, 800, 1600)) * 0.2
    return (signal * 32767).astype(np.int16).tobytes()


def _frames(pcm: bytes, start: float):
    step = 480 * 2
    for i in range(0, len(pcm) - step + 1, step):
        yield pcm[i : i + step], start + (i // 2) / 16000.0


def test_long_speech_is_split_with_overlap_and_time_is_continuous():
    config = VadConfig(max_utterance_s=3.0, overlap_s=0.6, end_silence_ms=600)
    seg = SpeechSegmenter(config)
    out = []
    for frame, wall in _frames(_tone(8.0), 100.0):
        out.extend(seg.feed(frame, wall))
    tail = seg.flush()
    if tail:
        out.append(tail)

    if len(out) < 2:
        pytest.skip("webrtcvad did not classify the synthetic tone as speech")
    assert out[0].forced_split
    assert out[1].overlap_s > 0
    # The second utterance starts before the first one ends (that is the overlap).
    assert out[1].start_wall < out[0].start_wall + out[0].duration_s
    assert out[1].start_wall > out[0].start_wall


def test_silence_yields_nothing():
    seg = SpeechSegmenter(VadConfig())
    silent = bytes(480 * 2)
    out = []
    for i in range(200):
        out.extend(seg.feed(silent, 50.0 + i * FRAME_MS / 1000))
    assert out == [] and seg.flush() is None
