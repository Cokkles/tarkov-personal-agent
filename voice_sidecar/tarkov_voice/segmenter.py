from __future__ import annotations

from collections import deque
from collections.abc import Iterator

import numpy as np

from tarkov_voice.config import VadConfig
from tarkov_voice.types import Utterance

FRAME_MS = 30  # webrtcvad accepts 10, 20 or 30 ms frames


class SpeechSegmenter:
    """Cuts a continuous mic stream into utterances using webrtcvad.

    Feed it 30 ms frames of 16-bit mono PCM together with the wall-clock time of each
    frame. It emits an utterance when speech stops for ``end_silence_ms``, or when speech
    runs past ``max_utterance_s`` (a forced split that keeps ``overlap_s`` of audio so
    words on the boundary are not cut in half).
    """

    def __init__(self, config: VadConfig, sample_rate: int = 16000) -> None:
        import webrtcvad

        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("webrtcvad needs 8, 16, 32 or 48 kHz audio")
        self._vad = webrtcvad.Vad(config.aggressiveness)
        self._config = config
        self._rate = sample_rate
        self._frame_samples = sample_rate * FRAME_MS // 1000
        self._end_frames = max(1, config.end_silence_ms // FRAME_MS)
        self._min_frames = max(1, config.min_utterance_ms // FRAME_MS)
        self._max_frames = int(config.max_utterance_s * 1000 / FRAME_MS)
        self._overlap_frames = int(config.overlap_s * 1000 / FRAME_MS)
        self._pre_roll: deque[tuple[bytes, float]] = deque(
            maxlen=max(1, config.pre_roll_ms // FRAME_MS)
        )
        self._recent_flags: deque[bool] = deque(maxlen=10)
        self._active: list[tuple[bytes, float]] = []
        self._silence_run = 0
        self._speaking = False
        self._counter = 0
        self._continuation = False

    @property
    def frame_bytes(self) -> int:
        return self._frame_samples * 2

    def feed(self, frame: bytes, wall_time: float) -> Iterator[Utterance]:
        if len(frame) != self.frame_bytes:
            raise ValueError(f"Expected {self.frame_bytes} bytes, got {len(frame)}")

        voiced = self._vad.is_speech(frame, self._rate)
        self._recent_flags.append(voiced)

        if not self._speaking:
            self._pre_roll.append((frame, wall_time))
            # Start once most recent frames are voiced, so single pops do not trigger.
            if sum(self._recent_flags) >= 6:
                self._speaking = True
                self._active = list(self._pre_roll)
                self._pre_roll.clear()
                self._silence_run = 0
            return

        self._active.append((frame, wall_time))
        self._silence_run = 0 if voiced else self._silence_run + 1

        if self._silence_run >= self._end_frames:
            utterance = self._close(forced=False)
            self._reset_after_close()
            if utterance is not None:
                yield utterance
        elif len(self._active) >= self._max_frames:
            utterance = self._close(forced=True)
            if utterance is not None:
                yield utterance
            # Keep the tail so the next utterance starts with repeated audio.
            tail = self._active[-self._overlap_frames :] if self._overlap_frames else []
            self._active = list(tail)
            self._continuation = True
            self._silence_run = 0

    def flush(self) -> Utterance | None:
        utterance = self._close(forced=False) if self._speaking else None
        self._reset_after_close()
        return utterance

    # ---------------------------------------------------------------- internals

    def _reset_after_close(self) -> None:
        self._active = []
        self._speaking = False
        self._silence_run = 0
        self._continuation = False
        self._recent_flags.clear()

    def _close(self, *, forced: bool) -> Utterance | None:
        frames = self._active
        # Trim the trailing silence, keeping a short tail so words are not clipped.
        keep_tail = 3
        if not forced and self._silence_run > keep_tail:
            frames = frames[: len(frames) - (self._silence_run - keep_tail)]
        if len(frames) < self._min_frames:
            return None

        pcm = b"".join(frame for frame, _ in frames)
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        overlap_s = self._config.overlap_s if self._continuation and self._overlap_frames else 0.0
        overlap_s = min(overlap_s, len(frames) * FRAME_MS / 1000.0)
        self._counter += 1
        return Utterance(
            index=self._counter,
            audio=audio,
            start_wall=frames[0][1],
            sample_rate=self._rate,
            overlap_s=overlap_s,
            forced_split=forced,
        )
