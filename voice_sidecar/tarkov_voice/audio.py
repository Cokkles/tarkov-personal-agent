from __future__ import annotations

import logging
import queue
import time
import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np

log = logging.getLogger("tarkov_voice.audio")

FRAME_SAMPLES_16K = 480  # 30 ms at 16 kHz


def list_devices() -> str:
    import sounddevice as sd

    lines: list[str] = []
    default_in = sd.default.device[0]
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            marker = "*" if index == default_in else " "
            api = sd.query_hostapis(device["hostapi"])["name"]
            lines.append(f"{marker} [{index}] {device['name']}  ({api})")
    return "\n".join(lines)


def resolve_device(selector: str) -> int | None:
    import sounddevice as sd

    if not selector.strip():
        return None
    if selector.strip().isdigit():
        return int(selector.strip())
    wanted = selector.lower()
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0 and wanted in device["name"].lower():
            return index
    raise ValueError(f"No input device matches {selector!r}. Run with --list-devices.")


class MicStream:
    """Captures the microphone as 30 ms mono 16 kHz frames with accurate wall-clock times.

    Each frame carries the wall time of its first sample, computed from the audio
    driver's own clock, so marker times stay correct even if processing falls behind.
    """

    def __init__(self, device: str = "", sample_rate: int = 16000) -> None:
        self._device = resolve_device(device)
        self._rate = sample_rate
        self._queue: queue.Queue[tuple[bytes, float] | None] = queue.Queue(maxsize=2000)
        self._stream = None
        self.dropped_frames = 0

    def _callback(self, indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        if status:
            log.debug("Audio status: %s", status)
        # Wall time of the first sample = now minus how far the driver clock has advanced
        # since this block was captured.
        age = float(time_info.currentTime) - float(time_info.inputBufferAdcTime)  # type: ignore[attr-defined]
        wall_start = time.time() - max(0.0, age)
        try:
            self._queue.put_nowait((indata[:, 0].tobytes(), wall_start))
        except queue.Full:
            self.dropped_frames += 1

    def __enter__(self) -> MicStream:
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=self._rate,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES_16K,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._queue.put(None)

    def frames(self) -> Iterator[tuple[bytes, float]]:
        while True:
            item = self._queue.get()
            if item is None:
                return
            yield item


def wav_frames(path: Path, start_wall: float) -> Iterator[tuple[bytes, float]]:
    """Feed a 16 kHz mono 16-bit wav file through the pipeline (for offline testing).

    Extract one from a recording with:
      ffmpeg -i raid.mkv -vn -ac 1 -ar 16000 -sample_fmt s16 mic.wav
    """
    with wave.open(str(path), "rb") as handle:
        ok = (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) == (16000, 1, 2)
        if not ok:
            raise ValueError(
                "Wav must be 16 kHz, mono, 16-bit. See the ffmpeg command in the README."
            )
        index = 0
        while True:
            chunk = handle.readframes(FRAME_SAMPLES_16K)
            if len(chunk) < FRAME_SAMPLES_16K * 2:
                return
            yield chunk, start_wall + index * FRAME_SAMPLES_16K / 16000.0
            index += 1
