from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import psutil


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    running: bool
    observed_at: datetime
    executable_name: str | None = None
    pid: int | None = None
    create_time: float | None = None


class ProcessObserver:
    """Polls process metadata only; it never opens or reads process memory."""

    def __init__(self, executable_names: Iterable[str], poll_interval_seconds: float = 2.0) -> None:
        self._names = {name.casefold() for name in executable_names}
        self._poll_interval = poll_interval_seconds

    def snapshot(self) -> ProcessSnapshot:
        for process in psutil.process_iter(("pid", "name", "create_time")):
            try:
                name = process.info.get("name")
                if isinstance(name, str) and name.casefold() in self._names:
                    return ProcessSnapshot(
                        running=True,
                        observed_at=datetime.now(UTC),
                        executable_name=name,
                        pid=int(process.info["pid"]),
                        create_time=float(process.info["create_time"]),
                    )
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, TypeError):
                continue
        return ProcessSnapshot(running=False, observed_at=datetime.now(UTC))

    async def changes(self) -> AsyncIterator[ProcessSnapshot]:
        previous: ProcessSnapshot | None = None
        while True:
            current = self.snapshot()
            identity = (current.running, current.executable_name, current.pid, current.create_time)
            prior_identity = None
            if previous is not None:
                prior_identity = (
                    previous.running,
                    previous.executable_name,
                    previous.pid,
                    previous.create_time,
                )
            if identity != prior_identity:
                yield current
                previous = current
            await asyncio.sleep(self._poll_interval)
