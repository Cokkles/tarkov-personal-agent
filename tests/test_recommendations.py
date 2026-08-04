from pathlib import Path

from tarkov_agent.app_context import build_context
from tarkov_agent.config import AppSettings, PathSettings, RuntimeSettings
from tarkov_agent.domain.recommendations import (
    CandidateStatus,
    RecommendationPurpose,
    RecommendationRequest,
    RiskPosture,
)


def _context(tmp_path: Path):  # type: ignore[no-untyped-def]
    return build_context(
        AppSettings(
            paths=PathSettings(data_root=tmp_path),
            runtime=RuntimeSettings(recover_interrupted_sessions=False),
        )
    )


def test_scav_plan_uses_verified_mechanics_and_writes_exports(tmp_path: Path) -> None:
    context = _context(tmp_path)
    plan = context.recommendations.generate(
        RecommendationRequest(
            objective="Extract task and hideout value safely",
            map_name="Customs",
            character_type="Scav",
            risk_posture=RiskPosture.LOW,
        )
    )

    assert plan.can_recommend is True
    assert plan.primary is not None
    assert plan.fallback is not None
    assert plan.primary.status is CandidateStatus.ELIGIBLE
    mechanic_keys = {
        check.requirement.key for check in plan.primary.mechanic_checks
    }
    assert "scav.extracted_loot_transfers" in mechanic_keys
    assert "scav.random_loadout" in mechanic_keys
    assert all(check.resolution.can_recommend for check in plan.primary.mechanic_checks)
    assert (tmp_path / "recommendations" / "latest.json").exists()
    assert (tmp_path / "recommendations" / "latest.md").exists()


def test_unknown_hard_mechanic_blocks_every_candidate(tmp_path: Path) -> None:
    context = _context(tmp_path)
    plan = context.recommendations.generate(
        RecommendationRequest(
            objective="Use a mechanic that has not been verified",
            character_type="PMC",
            mechanic_keys=["unknown.required.mechanic"],
        )
    )

    assert plan.can_recommend is False
    assert plan.primary is None
    assert plan.refusal_reason is not None
    assert plan.research_tasks
    assert all(
        evaluation.status is CandidateStatus.BLOCKED
        for evaluation in plan.evaluated_candidates
    )


def test_training_request_produces_controlled_experiment(tmp_path: Path) -> None:
    context = _context(tmp_path)
    plan = context.recommendations.generate(
        RecommendationRequest(
            objective="Practice disciplined disengagement",
            purpose=RecommendationPurpose.TRAINING,
            risk_posture=RiskPosture.LOW,
        )
    )

    assert plan.primary is not None
    assert plan.experiment is not None
    assert plan.experiment.recommended_sample_size == 5
    assert plan.primary.candidate.purpose is RecommendationPurpose.TRAINING
