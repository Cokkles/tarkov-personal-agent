from __future__ import annotations

import asyncio
import hashlib
import json
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tarkov_agent.observers.logs import LogLine, LogTailObserver


@dataclass(frozen=True, slots=True)
class DiagnosticCaptureResult:
    folder: Path
    events_path: Path
    manifest_path: Path
    line_count: int


class DiagnosticRedactor:
    """Best-effort redaction for log samples before they become fixtures."""

    _PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
        ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
        (
            "guid",
            re.compile(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}"
                r"-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
                re.I,
            ),
        ),
        (
            "secret",
            re.compile(
                r"(?i)\b(token|authorization|cookie|session(?:id)?|password)\b"
                r"\s*[:=]\s*([^\s,;]+)"
            ),
        ),
        ("long_hex", re.compile(r"\b[0-9a-f]{24,}\b", re.I)),
        ("windows_user", re.compile(r"(?i)(?:[A-Z]:\\Users\\)([^\\\r\n]+)")),
    )

    def redact(self, value: str) -> str:
        redacted = value
        for kind, pattern in self._PATTERNS:
            if kind == "secret":
                redacted = pattern.sub(
                    lambda match, label=kind: (
                        f"{match.group(1)}=<REDACTED:{label}>"
                    ),
                    redacted,
                )
            elif kind == "windows_user":
                redacted = pattern.sub(r"C:\\Users\\<REDACTED:user>", redacted)
            else:
                redacted = pattern.sub(
                    lambda match, label=kind: self._placeholder(
                        label,
                        match.group(0),
                    ),
                    redacted,
                )
        return redacted

    @staticmethod
    def _placeholder(kind: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:8]
        return f"<REDACTED:{kind}:{digest}>"


class DiagnosticCaptureService:
    def __init__(
        self,
        diagnostics_root: Path | str,
        redactor: DiagnosticRedactor | None = None,
    ) -> None:
        self._root = Path(diagnostics_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._redactor = redactor or DiagnosticRedactor()

    async def capture(
        self,
        observer: LogTailObserver,
        *,
        duration_seconds: float,
        label: str = "log-capture",
        maximum_lines: int = 10000,
    ) -> DiagnosticCaptureResult:
        started = datetime.now(UTC)
        safe_label = (
            re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-._")
            or "log-capture"
        )
        folder = self._root / f"{started.strftime('%Y%m%d_%H%M%S')}_{safe_label}"
        folder.mkdir(parents=True, exist_ok=False)
        events_path = folder / "events.jsonl"
        manifest_path = folder / "manifest.json"
        line_count = 0

        async def collect() -> None:
            nonlocal line_count
            async for line in observer.lines():
                self._append(events_path, line)
                line_count += 1
                if line_count >= maximum_lines:
                    return

        with suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=duration_seconds)

        finished = datetime.now(UTC)
        manifest = {
            "schema_version": 1,
            "label": safe_label,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": (finished - started).total_seconds(),
            "line_count": line_count,
            "redaction": "best-effort",
            "warning": "Review captured data manually before sharing or committing fixtures.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return DiagnosticCaptureResult(folder, events_path, manifest_path, line_count)

    def _append(self, path: Path, line: LogLine) -> None:
        source_hash = hashlib.sha256(
            str(line.path).encode("utf-8")
        ).hexdigest()[:12]
        payload = {
            "observed_at": line.observed_at.isoformat(),
            "source": f"log-{source_hash}",
            "line_number": line.line_number,
            "content": self._redactor.redact(line.text),
        }
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
