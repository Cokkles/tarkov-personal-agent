from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tarkov_agent.config import AppSettings
from tarkov_agent.domain.models import EvidenceKind, RaidRecord, RaidState, TimelineEvent
from tarkov_agent.domain.state_machine import RaidLifecycle, RaidSignal, StateTransition
from tarkov_agent.integrations.obs import ObsIntegrationError, RecordingController
from tarkov_agent.observers.process import ProcessSnapshot
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.packages import RaidPackageBuilder, RaidPackageError
from tarkov_agent.storage.database import RaidRepository


class RaidCoordinator:
    """Coordinates lifecycle changes without reading or influencing game state."""

    def __init__(
        self,
        settings: AppSettings,
        repository: RaidRepository,
        packages: RaidPackageBuilder,
        markers: MarkerService,
        recording: RecordingController,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.packages = packages
        self.markers = markers
        self.recording = recording
        self.lifecycle = RaidLifecycle()
        self.active_raid: RaidRecord | None = None

    def handle_process_snapshot(self, snapshot: ProcessSnapshot) -> StateTransition | None:
        if snapshot.running and self.lifecycle.can_apply(RaidSignal.GAME_FOUND):
            return self.handle_signal(
                RaidSignal.GAME_FOUND,
                occurred_at=snapshot.observed_at,
                reason=f"Observed process {snapshot.executable_name} ({snapshot.pid})",
            )
        if not snapshot.running and self.lifecycle.can_apply(RaidSignal.GAME_LOST):
            return self.handle_signal(
                RaidSignal.GAME_LOST,
                occurred_at=snapshot.observed_at,
                reason="Configured Tarkov process no longer observed",
            )
        return None

    def handle_signal(
        self,
        signal: RaidSignal,
        *,
        occurred_at: datetime | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> StateTransition:
        timestamp = occurred_at or datetime.now(UTC)
        transition = self.lifecycle.apply(signal, occurred_at=timestamp, reason=reason)
        details = payload or {}

        if signal is RaidSignal.RAID_STARTED:
            self._start_raid(timestamp, details, transition)
        elif signal is RaidSignal.RAID_ENDED:
            self._end_raid(timestamp, transition)
            if self.settings.runtime.auto_complete_raid_on_end:
                completion = self.lifecycle.apply(
                    RaidSignal.REVIEW_COMPLETED,
                    occurred_at=timestamp,
                    reason="Headless runtime auto-completed post-raid review",
                )
                self._complete_review(completion)
        elif signal is RaidSignal.REVIEW_COMPLETED:
            self._complete_review(transition)
        elif signal in {RaidSignal.ABORT, RaidSignal.GAME_LOST} and self.active_raid is not None:
            self._abort_or_interrupt(timestamp, transition)
        elif self.active_raid is not None:
            self._update_active_state(transition)

        return transition

    def _start_raid(
        self,
        timestamp: datetime,
        payload: dict[str, Any],
        transition: StateTransition,
    ) -> None:
        if self.active_raid is not None:
            raise RuntimeError("Cannot start a new raid while another raid is active")

        raid = RaidRecord(
            state=transition.to_state,
            started_at=timestamp,
            map_name=self._optional_text(payload.get("map_name")),
            character_type=self._optional_text(payload.get("character_type")),
            primary_objective=self._optional_text(payload.get("primary_objective")),
            secondary_objective=self._optional_text(payload.get("secondary_objective")),
            data_root=self.settings.paths.raids_root,
        )
        if self.settings.runtime.auto_create_raid_package:
            raid = self.packages.create(raid)
        self.active_raid = raid
        self.markers.activate(raid)
        self.repository.save_raid(raid)
        self._append_transition_event(raid, transition)

        if self.settings.obs.enabled and self.settings.obs.start_recording_on_raid_start:
            try:
                status = self.recording.start()
                self._append_system_event(
                    raid,
                    "recording_started",
                    "OBS recording start requested",
                    timestamp,
                    {"active": status.active, "connected": status.connected},
                )
            except ObsIntegrationError as exc:
                self._append_system_event(
                    raid,
                    "recording_error",
                    "OBS recording could not be started",
                    timestamp,
                    {"error": str(exc)},
                    confidence=1.0,
                )

    def _end_raid(self, timestamp: datetime, transition: StateTransition) -> None:
        raid = self._require_active_raid()
        raid = raid.model_copy(update={"state": transition.to_state, "ended_at": timestamp})
        self.active_raid = raid
        self.markers.activate(raid)
        self._append_transition_event(raid, transition)

        if self.settings.obs.enabled and self.settings.obs.stop_recording_on_raid_end:
            try:
                status = self.recording.stop()
                self._append_system_event(
                    raid,
                    "recording_stopped",
                    "OBS recording stop requested",
                    timestamp,
                    {"output_path": status.output_path},
                )
                if status.output_path:
                    recording_path = Path(status.output_path)
                    if recording_path.exists():
                        raid, _ = self.packages.attach_file(
                            raid,
                            recording_path,
                            EvidenceKind.RECORDING,
                            copy_into_package=self.settings.runtime.copy_evidence_into_package,
                            metadata={"source": "obs"},
                        )
                        self.active_raid = raid
                        self.markers.activate(raid)
            except (ObsIntegrationError, RaidPackageError) as exc:
                self._append_system_event(
                    raid,
                    "recording_error",
                    "OBS recording could not be finalized",
                    timestamp,
                    {"error": str(exc)},
                )

        self._persist_active()

    def _complete_review(self, transition: StateTransition) -> None:
        raid = self._require_active_raid()
        raid = raid.model_copy(update={"state": transition.to_state})
        self.active_raid = raid
        self._append_transition_event(raid, transition)
        self._persist_active()
        self.markers.deactivate()
        self.active_raid = None

    def _abort_or_interrupt(self, timestamp: datetime, transition: StateTransition) -> None:
        raid = self._require_active_raid()
        raid = raid.model_copy(
            update={
                "state": transition.to_state,
                "ended_at": raid.ended_at or timestamp,
            }
        )
        self.active_raid = raid
        self.markers.activate(raid)
        self._append_transition_event(raid, transition)
        if self.settings.obs.enabled:
            try:
                self.recording.stop()
            except ObsIntegrationError as exc:
                self._append_system_event(
                    raid,
                    "recording_error",
                    "OBS recording could not be stopped during interruption",
                    timestamp,
                    {"error": str(exc)},
                )
        self._persist_active()
        if transition.to_state is RaidState.ABORTED:
            self.markers.deactivate()
            self.active_raid = None

    def _update_active_state(self, transition: StateTransition) -> None:
        raid = self._require_active_raid().model_copy(update={"state": transition.to_state})
        self.active_raid = raid
        self.markers.activate(raid)
        self._append_transition_event(raid, transition)
        self._persist_active()

    def _append_transition_event(self, raid: RaidRecord, transition: StateTransition) -> None:
        self._append_system_event(
            raid,
            "lifecycle_transition",
            f"{transition.from_state.value} -> {transition.to_state.value}",
            transition.occurred_at,
            {"signal": transition.signal.value, "reason": transition.reason},
        )

    def _append_system_event(
        self,
        raid: RaidRecord,
        event_type: str,
        label: str,
        occurred_at: datetime,
        payload: dict[str, Any],
        *,
        confidence: float = 1.0,
    ) -> TimelineEvent:
        offset_ms = None
        if raid.started_at is not None:
            offset_ms = max(0, int((occurred_at - raid.started_at).total_seconds() * 1000))
        event = TimelineEvent(
            raid_id=raid.id,
            occurred_at=occurred_at,
            raid_offset_ms=offset_ms,
            event_type=event_type,
            label=label,
            source="system",
            confidence=confidence,
            payload=payload,
        )
        self.repository.add_timeline_event(event)
        if raid.data_root != self.settings.paths.raids_root:
            self.packages.append_timeline_event(raid, event)
        return event

    def _persist_active(self) -> None:
        raid = self._require_active_raid()
        self.repository.save_raid(raid)
        if raid.data_root != self.settings.paths.raids_root:
            self.packages.write_manifest(raid)

    def _require_active_raid(self) -> RaidRecord:
        if self.active_raid is None:
            raise RuntimeError("No raid is currently active")
        return self.active_raid

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
