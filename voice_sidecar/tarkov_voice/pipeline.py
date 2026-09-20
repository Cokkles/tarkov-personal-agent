from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Iterable
from datetime import datetime

from tarkov_voice.config import VoiceConfig
from tarkov_voice.segmenter import SpeechSegmenter
from tarkov_voice.sender import MarkerSender
from tarkov_voice.transcriber import Transcriber
from tarkov_voice.transcript_log import TranscriptLog
from tarkov_voice.triggers import TriggerEngine
from tarkov_voice.types import Hit, Utterance

log = logging.getLogger("tarkov_voice.pipeline")


def _clock(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).strftime("%H:%M:%S")


class Pipeline:
    """mic frames -> utterances -> words -> marker hits -> API.

    Audio capture and VAD run in the calling thread. Transcription runs in a worker so a slow
    GPU moment never drops audio; frames keep their capture time, so markers stay accurate.
    """

    def __init__(
        self,
        config: VoiceConfig,
        transcriber: Transcriber,
        engine: TriggerEngine,
        sender: MarkerSender | None,
        transcript: TranscriptLog,
    ) -> None:
        self._config = config
        self._transcriber = transcriber
        self._engine = engine
        self._sender = sender
        self._transcript = transcript
        self._queue: queue.Queue[Utterance | None] = queue.Queue(maxsize=100)
        self._worker = threading.Thread(target=self._work, name="transcriber", daemon=True)
        self._no_raid_notice_at = 0.0

    def run(self, frames: Iterable[tuple[bytes, float]]) -> None:
        segmenter = SpeechSegmenter(self._config.vad, self._config.audio.sample_rate)
        self._worker.start()
        try:
            for frame, wall_time in frames:
                for utterance in segmenter.feed(frame, wall_time):
                    if self._queue.qsize() > 5:
                        log.warning("Transcription is %d utterances behind", self._queue.qsize())
                    self._queue.put(utterance)
            tail = segmenter.flush()
            if tail is not None:
                self._queue.put(tail)
        finally:
            self._queue.put(None)
            self._worker.join()

    # ---------------------------------------------------------------- worker

    def _work(self) -> None:
        while True:
            utterance = self._queue.get()
            if utterance is None:
                return
            try:
                self._handle(utterance)
            except Exception:  # keep listening no matter what one utterance does
                log.exception("Failed to process utterance %d", utterance.index)

    def _handle(self, utterance: Utterance) -> None:
        words = self._transcriber.transcribe(utterance)
        if not words:
            return
        text = " ".join(w.text.strip() for w in words)
        print(f"[{_clock(words[0].start)}] {text}", flush=True)

        outcomes: list[tuple[Hit, str]] = []
        for hit in self._engine.scan(words):
            status = self._dispatch(hit)
            outcomes.append((hit, status))
            kind = hit.marker_type or "voice note"
            print(
                f"    -> {kind}  conf={hit.confidence:.2f}  at {_clock(hit.occurred_at)}"
                f"  [{status}]",
                flush=True,
            )
        self._transcript.write(words, outcomes)

    def _dispatch(self, hit: Hit) -> str:
        if self._sender is None:
            return "dry_run"
        result = self._sender.send(hit)
        if result.status == "no_raid":
            # Talking in the lobby is normal; do not spam the console.
            return "no_raid"
        if result.status != "sent":
            log.warning("Marker not delivered: %s %s", result.status, result.detail)
        return result.status
