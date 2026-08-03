from __future__ import annotations

from dataclasses import dataclass

from tarkov_agent.config import AppSettings
from tarkov_agent.integrations.obs import RecordingController, build_recording_controller
from tarkov_agent.observers.process import ProcessObserver
from tarkov_agent.runtime import CompanionRuntime
from tarkov_agent.services.control import ManualControlService
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.services.recovery import RecoveryService
from tarkov_agent.services.reviews import RaidReviewService
from tarkov_agent.storage.database import RaidRepository


@dataclass(slots=True)
class AgentContext:
    settings: AppSettings
    repository: RaidRepository
    packages: RaidPackageBuilder
    recording: RecordingController
    markers: MarkerService
    coordinator: RaidCoordinator
    runtime: CompanionRuntime
    reviews: RaidReviewService
    recovery: RecoveryService
    controls: ManualControlService

    def recover_interrupted_session(self) -> None:
        if not self.settings.runtime.recover_interrupted_sessions:
            return
        snapshot = ProcessObserver(
            self.settings.process.executable_names,
            self.settings.process.poll_interval_seconds,
        ).snapshot()
        recovered = self.recovery.recover(game_running=snapshot.running)
        if recovered is not None and recovered.state.value == "in_raid" and snapshot.running:
            self.coordinator.restore_active_raid(recovered)


def build_context(settings: AppSettings) -> AgentContext:
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()
    packages = RaidPackageBuilder(settings.paths.raids_root)
    recording = build_recording_controller(settings.obs)
    markers = MarkerService(repository, packages)
    coordinator = RaidCoordinator(settings, repository, packages, markers, recording)
    runtime = CompanionRuntime(settings, coordinator)
    reviews = RaidReviewService(repository, packages)
    recovery = RecoveryService(repository, packages)
    controls = ManualControlService(settings, coordinator, markers, repository, packages)
    return AgentContext(
        settings=settings,
        repository=repository,
        packages=packages,
        recording=recording,
        markers=markers,
        coordinator=coordinator,
        runtime=runtime,
        reviews=reviews,
        recovery=recovery,
        controls=controls,
    )
