from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tarkov_agent.config import LogSignalRule
from tarkov_agent.domain.state_machine import RaidSignal


@dataclass(frozen=True, slots=True)
class LogLine:
    path: Path
    line_number: int
    text: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ClassifiedLogSignal:
    rule_name: str
    signal: RaidSignal
    confidence: float
    log_line: LogLine


@dataclass(slots=True)
class _Cursor:
    offset: int
    line_number: int


class LogTailObserver:
    """Reads only appended bytes from configured log files and tolerates rotation/truncation."""

    def __init__(
        self,
        roots: Iterable[Path],
        file_globs: Iterable[str] = ("*.log", "*.txt"),
        *,
        start_at_end: bool = True,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._roots = tuple(Path(root) for root in roots)
        self._globs = tuple(file_globs)
        self._start_at_end = start_at_end
        self._poll_interval = poll_interval_seconds
        self._cursors: dict[Path, _Cursor] = {}

    def _discover(self) -> list[Path]:
        files: set[Path] = set()
        for root in self._roots:
            if not root.exists() or not root.is_dir():
                continue
            for pattern in self._globs:
                files.update(path for path in root.rglob(pattern) if path.is_file())
        return sorted(files)

    def scan_once(self) -> list[LogLine]:
        observed: list[LogLine] = []
        for path in self._discover():
            try:
                size = path.stat().st_size
            except OSError:
                continue

            cursor = self._cursors.get(path)
            if cursor is None:
                initial_offset = size if self._start_at_end else 0
                cursor = _Cursor(offset=initial_offset, line_number=0)
                self._cursors[path] = cursor
            elif size < cursor.offset:
                cursor.offset = 0
                cursor.line_number = 0

            if size == cursor.offset:
                continue

            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(cursor.offset)
                    for raw_line in handle:
                        cursor.line_number += 1
                        observed.append(
                            LogLine(
                                path=path,
                                line_number=cursor.line_number,
                                text=raw_line.rstrip("\r\n"),
                                observed_at=datetime.now(UTC),
                            )
                        )
                    cursor.offset = handle.tell()
            except OSError:
                continue
        return observed

    async def lines(self) -> AsyncIterator[LogLine]:
        while True:
            for line in self.scan_once():
                yield line
            await asyncio.sleep(self._poll_interval)


class LogSignalClassifier:
    """Maps explicitly configured regular expressions to lifecycle signals.

    No Tarkov log strings are assumed in code. Rules must be validated against current sample logs
    before being trusted for automatic recording control.
    """

    def __init__(self, rules: Iterable[LogSignalRule]) -> None:
        self._rules = [
            (rule, re.compile(rule.pattern, flags=re.IGNORECASE))
            for rule in rules
        ]

    def classify(self, line: LogLine) -> list[ClassifiedLogSignal]:
        results: list[ClassifiedLogSignal] = []
        for rule, pattern in self._rules:
            if pattern.search(line.text) is None:
                continue
            try:
                signal = RaidSignal(rule.signal)
            except ValueError:
                continue
            results.append(
                ClassifiedLogSignal(
                    rule_name=rule.name,
                    signal=signal,
                    confidence=rule.confidence,
                    log_line=line,
                )
            )
        return results
