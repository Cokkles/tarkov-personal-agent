from __future__ import annotations

import asyncio
import logging

from tarkov_agent.config import AppSettings
from tarkov_agent.domain.state_machine import InvalidTransition
from tarkov_agent.observers.logs import LogSignalClassifier, LogTailObserver
from tarkov_agent.observers.process import ProcessObserver
from tarkov_agent.services.coordinator import RaidCoordinator

LOGGER = logging.getLogger(__name__)


class CompanionRuntime:
    """Runs passive observers and serializes their lifecycle effects on one asyncio loop."""

    def __init__(self, settings: AppSettings, coordinator: RaidCoordinator) -> None:
        self._settings = settings
        self._coordinator = coordinator
        self._stop_event = asyncio.Event()
        self._process_observer = ProcessObserver(
            settings.process.executable_names,
            settings.process.poll_interval_seconds,
        )
        self._log_observer = LogTailObserver(
            settings.paths.tarkov_log_roots,
            settings.logs.file_globs,
            start_at_end=settings.logs.start_at_end,
            poll_interval_seconds=settings.logs.poll_interval_seconds,
        )
        self._classifier = LogSignalClassifier(settings.logs.rules)

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self._watch_process(), name="process-observer"),
            asyncio.create_task(self._watch_logs(), name="log-observer"),
        ]
        stop_task = asyncio.create_task(self._stop_event.wait(), name="shutdown-waiter")
        try:
            await stop_task
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _watch_process(self) -> None:
        async for snapshot in self._process_observer.changes():
            try:
                transition = self._coordinator.handle_process_snapshot(snapshot)
                if transition is not None:
                    LOGGER.info(
                        "Lifecycle: %s -> %s (%s)",
                        transition.from_state,
                        transition.to_state,
                        transition.signal,
                    )
            except InvalidTransition:
                LOGGER.debug("Ignored process transition that is invalid for current lifecycle")

    async def _watch_logs(self) -> None:
        async for line in self._log_observer.lines():
            for classified in self._classifier.classify(line):
                if classified.confidence < self._settings.logs.minimum_auto_signal_confidence:
                    LOGGER.info(
                        "Observed low-confidence signal %s from %s:%s; not applying automatically",
                        classified.signal,
                        line.path,
                        line.line_number,
                    )
                    continue
                if not self._coordinator.lifecycle.can_apply(classified.signal):
                    LOGGER.debug(
                        "Signal %s is not valid from %s",
                        classified.signal,
                        self._coordinator.lifecycle.state,
                    )
                    continue
                try:
                    self._coordinator.handle_signal(
                        classified.signal,
                        occurred_at=line.observed_at,
                        reason=(
                            f"Log rule {classified.rule_name} matched "
                            f"{line.path.name}:{line.line_number}"
                        ),
                    )
                except InvalidTransition:
                    LOGGER.debug("Lifecycle changed before classified log signal was applied")
