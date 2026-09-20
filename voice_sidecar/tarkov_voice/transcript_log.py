from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from tarkov_voice.types import Hit, Word


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


class TranscriptLog:
    """Append-only JSONL log of everything you said, with absolute timestamps.

    One line per utterance. The raid timeline can later be joined to this file by time, which
    is what a post-raid pass uses to find callouts the live rules missed.
    """

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = directory / f"session_{stamp}.jsonl"
        self._lock = threading.Lock()

    def write(
        self,
        words: list[Word],
        hits: list[tuple[Hit, str]],
    ) -> None:
        if not words:
            return
        record = {
            "start": _iso(words[0].start),
            "end": _iso(words[-1].end),
            "start_epoch": round(words[0].start, 3),
            "end_epoch": round(words[-1].end, 3),
            "text": " ".join(w.text.strip() for w in words),
            "words": [
                {
                    "w": w.text.strip(),
                    "s": round(w.start, 3),
                    "e": round(w.end, 3),
                    "p": round(w.probability, 3),
                }
                for w in words
            ],
            "markers": [
                {
                    "type": hit.marker_type,
                    "rule": hit.rule,
                    "confidence": hit.confidence,
                    "at": _iso(hit.occurred_at),
                    "details": hit.details,
                    "prefixed": hit.prefixed,
                    "send_status": status,
                }
                for hit, status in hits
            ],
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
