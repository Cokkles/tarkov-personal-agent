from __future__ import annotations

from dataclasses import dataclass

from tarkov_agent.config import AppSettings
from tarkov_agent.integrations.obs import (
    RecordingController,
    build_recording_controller,
)
from tarkov_agent.observers.process import ProcessObserver
from tarkov_agent.runtime import CompanionRuntime
from tarkov_agent.services.control import ManualControlService
from tarkov_agent.services.coordinator import RaidCoordinator
from tarkov_agent.services.markers import MarkerService
from tarkov_agent.services.media import MediaService
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.services.ppe import PPEProfileService
from tarkov_agent.services.recommendations import RecommendationService
from tarkov_agent.services.recovery import RecoveryService
from tarkov_agent.services.reviews import RaidReviewService
from tarkov_agent.services.source_truth import SourceTruthService
from tarkov_agent.storage.database import RaidRepository
from tarkov_agent.storage.source_truth import SourceTruthRepository


@dataclass(slots=True)
class AgentContext:
    settings: AppSettings
    repository: RaidRepository
    packages: RaidPackageBuilder
    recording: RecordingController
    markers: MarkerService
    media: MediaService
    coordinator: RaidCoordinator
    runtime: CompanionRuntime
    reviews: RaidReviewService
    ppe: PPEProfileService
    truth: SourceTruthService
    recommendations: RecommendationService
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
        if (
            recovered is not None
            and recovered.state.value == "in_raid"
            and snapshot.running
        ):
            self.coordinator.restore_active_raid(recovered)


def build_context(settings: AppSettings) -> AgentContext:
    settings.prepare()
    repository = RaidRepository(settings.paths.database_path)
    repository.initialize()
    truth_repository = SourceTruthRepository(settings.paths.database_path)
    truth_repository.initialize()
    packages = RaidPackageBuilder(settings.paths.raids_root)
    recording = build_recording_controller(settings.obs)
    markers = MarkerService(repository, packages)
    media = MediaService(
        repository,
        packages,
        settings.paths.media_root,
        settings.media,
        [
            settings.paths.data_root,
            *settings.api.allowed_evidence_roots,
        ],
    )
    coordinator = RaidCoordinator(
        settings,
        repository,
        packages,
        markers,
        recording,
        media,
    )
    runtime = CompanionRuntime(settings, coordinator)
    reviews = RaidReviewService(repository, packages)
    ppe = PPEProfileService(repository, settings.paths.ppe_root, settings.ppe)
    truth = SourceTruthService(
        truth_repository,
        settings.paths.source_truth_root,
        settings.truth,
    )
    truth.initialize()
    recommendations = RecommendationService(
        truth,
        ppe,
        settings.paths.recommendations_root,
        settings.recommendations,
    )
    recovery = RecoveryService(repository, packages)
    controls = ManualControlService(
        settings,
        coordinator,
        markers,
        repository,
        packages,
    )
    return AgentContext(
        settings=settings,
        repository=repository,
        packages=packages,
        recording=recording,
        markers=markers,
        media=media,
        coordinator=coordinator,
        runtime=runtime,
        reviews=reviews,
        ppe=ppe,
        truth=truth,
        recommendations=recommendations,
        recovery=recovery,
        controls=controls,
    )
