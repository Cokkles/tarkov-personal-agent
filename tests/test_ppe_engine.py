from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tarkov_agent.config import PpeSettings
from tarkov_agent.domain.ppe import (
    DimensionImpact,
    EvidenceSource,
    PPEContext,
    PPEEvidence,
)
from tarkov_agent.ppe.engine import PPEEngine
from tarkov_agent.ppe.registry import DEFAULT_DIMENSION_REGISTRY


def _evidence(
    value: float,
    *,
    raid_id: object | None = None,
    age_days: int = 0,
    map_name: str | None = None,
) -> PPEEvidence:
    return PPEEvidence(
        raid_id=raid_id or uuid4(),  # type: ignore[arg-type]
        source=EvidenceSource.ENCOUNTER_REVIEW,
        source_reference=str(uuid4()),
        observed_at=datetime.now(UTC) - timedelta(days=age_days),
        reliability=0.9,
        context=PPEContext(map_name=map_name, range_band="close"),
        impacts=[
            DimensionImpact(
                dimension_key="reactive_close_range_effectiveness",
                value=value,
                strength=0.9,
                confidence=0.9,
                rationale="Synthetic test observation",
            )
        ],
    )


def _engine() -> PPEEngine:
    return PPEEngine(
        DEFAULT_DIMENSION_REGISTRY,
        PpeSettings(
            neutral_prior_weight=0.5,
            confidence_weight_scale=1.0,
            minimum_report_confidence=0.1,
            minimum_established_confidence=0.2,
        ),
    )


def test_repeated_independent_evidence_builds_directional_profile() -> None:
    evidence = [_evidence(0.9) for _ in range(4)]
    result = _engine().build(
        evidence,
        version=1,
        evidence_fingerprint="a" * 64,
    )

    estimate = result.snapshot.estimate("reactive_close_range_effectiveness")
    assert estimate is not None
    assert estimate.score > 0.45
    assert estimate.confidence > 0.5
    assert estimate.independent_raid_count == 4
    assert "Reactive close-range effectiveness" in result.snapshot.established_strengths


def test_contradictory_evidence_reduces_confidence() -> None:
    consistent = _engine().build(
        [_evidence(0.9), _evidence(0.9), _evidence(0.9), _evidence(0.9)],
        version=1,
        evidence_fingerprint="b" * 64,
    ).snapshot.estimate("reactive_close_range_effectiveness")
    mixed = _engine().build(
        [_evidence(0.9), _evidence(0.9), _evidence(-0.9), _evidence(-0.9)],
        version=1,
        evidence_fingerprint="c" * 64,
    ).snapshot.estimate("reactive_close_range_effectiveness")

    assert consistent is not None and mixed is not None
    assert mixed.contradiction_ratio > 0.8
    assert mixed.confidence < consistent.confidence
    assert abs(mixed.score) < abs(consistent.score)


def test_context_estimates_are_kept_separate() -> None:
    evidence = [
        _evidence(0.9, map_name="Interchange"),
        _evidence(0.9, map_name="Interchange"),
        _evidence(-0.9, map_name="Factory"),
        _evidence(-0.9, map_name="Factory"),
    ]
    snapshot = _engine().build(
        evidence,
        version=1,
        evidence_fingerprint="d" * 64,
    ).snapshot

    interchange = snapshot.estimate(
        "reactive_close_range_effectiveness",
        "map_name=interchange",
    )
    factory = snapshot.estimate(
        "reactive_close_range_effectiveness",
        "map_name=factory",
    )
    assert interchange is not None and factory is not None
    assert interchange.score > 0
    assert factory.score < 0


def test_recent_evidence_outweighs_old_evidence() -> None:
    snapshot = _engine().build(
        [_evidence(1.0, age_days=365), _evidence(-1.0, age_days=0)],
        version=1,
        evidence_fingerprint="e" * 64,
    ).snapshot

    estimate = snapshot.estimate("reactive_close_range_effectiveness")
    assert estimate is not None
    assert estimate.score < 0
