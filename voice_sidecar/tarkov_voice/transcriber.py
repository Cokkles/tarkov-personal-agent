from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from tarkov_voice.config import ModelConfig
from tarkov_voice.types import Utterance, Word

log = logging.getLogger("tarkov_voice.transcriber")

# Whisper tends to invent these on near-silence or background music.
_HALLUCINATIONS = {
    "thank you",
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "bye",
    "you",
    "so",
}


def add_nvidia_dll_dirs() -> None:
    """Make pip-installed CUDA libraries (nvidia-cublas-cu12, nvidia-cudnn-cu12) loadable.

    On Windows the DLLs live inside site-packages/nvidia/*/bin and are not on PATH.
    """
    if sys.platform != "win32":
        return
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in nvidia.glob("*/bin"):
            try:
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            except OSError:
                continue


class Transcriber:
    """faster-whisper wrapper that returns words with absolute wall-clock times."""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        if config.dll_search:
            add_nvidia_dll_dirs()
        self._model = self._load()
        self._last_word_end = 0.0  # absolute epoch seconds, used to drop overlap repeats

    def _load(self) -> object:
        from faster_whisper import WhisperModel

        cfg = self._config
        try:
            log.info("Loading %s on %s (%s)", cfg.name, cfg.device, cfg.compute_type)
            model = WhisperModel(cfg.name, device=cfg.device, compute_type=cfg.compute_type)
            self._warmup(model)
            return model
        except Exception as exc:  # CUDA/cuDNN problems surface as several exception types
            if cfg.device == "cpu":
                raise
            log.warning(
                "GPU model failed to start (%s). Falling back to %s on CPU.",
                exc,
                cfg.fallback_model,
            )
            model = WhisperModel(cfg.fallback_model, device="cpu", compute_type="int8")
            self._warmup(model)
            return model

    @staticmethod
    def _warmup(model: object) -> None:
        import numpy as np

        silence = np.zeros(16000, dtype=np.float32)
        segments, _ = model.transcribe(silence, language="en")  # type: ignore[attr-defined]
        list(segments)

    def transcribe(self, utterance: Utterance) -> list[Word]:
        cfg = self._config
        segments, _info = self._model.transcribe(  # type: ignore[attr-defined]
            utterance.audio,
            language=cfg.language,
            beam_size=cfg.beam_size,
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=cfg.initial_prompt or None,
            temperature=0.0,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            vad_filter=False,  # already segmented by webrtcvad
        )

        words: list[Word] = []
        for segment in segments:
            text = (segment.text or "").strip()
            if not text:
                continue
            if segment.no_speech_prob > 0.6 and segment.avg_logprob < -1.0:
                continue
            if text.lower().strip(" .!?,") in _HALLUCINATIONS and len(text) < 25:
                continue
            for word in segment.words or []:
                start = utterance.start_wall + float(word.start)
                end = utterance.start_wall + float(word.end)
                # Drop words already produced by the previous, overlapping utterance.
                if utterance.overlap_s > 0 and (start + end) / 2.0 <= self._last_word_end:
                    continue
                words.append(
                    Word(
                        text=str(word.word),
                        start=start,
                        end=end,
                        probability=float(getattr(word, "probability", 1.0)),
                    )
                )

        if words:
            self._last_word_end = max(self._last_word_end, words[-1].end)
        return words
