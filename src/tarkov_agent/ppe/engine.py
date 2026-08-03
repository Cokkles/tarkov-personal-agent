from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from tarkov_agent.config import PpeSettings
from tarkov_agent.domain.ppe import (
    DimensionChange,
    DimensionImpact,
    EvidenceSource,
    PPEEvidence,
    ProfileAuditEntry,
    ProfileEstimate,
    ProfileGuidance,
    ProfileReport,
    ProfileSignal,
    ProfileSignalKind,
    ProfileSnapshot,
    RecommendationMode,
)
from tarkov_agent.ppe.registry import DimensionRegistry

_SOURCE_MULTIPLIERS: dict[EvidenceSource, float] = {
    EvidenceSource.SELF_REPORT: 0.45,
    EvidenceSource.RAID_REVIEW: 0.65,
    EvidenceSource.ENCOUNTER_REVIEW: 0.90,
    EvidenceSource.RAID_STATISTICS: 0.50,
    EvidenceSource.MANUAL_ASSESSMENT: 0.75,
    EvidenceSource.EXPERIMENT: 1.00,
}


@dataclass(frozen=True, slots=True)
class _Observation:
    evidence_id: UUID
    raid_key: str
    occurred_at: datetime
    value: float
    weight: float


@dataclass(frozen=True, slots=True)
class ProfileBuildResult:
    snapshot: ProfileSnapshot
    audit: ProfileAuditEntry
    report: ProfileReport


class PPEEngine:
    def __init__(self, registry: DimensionRegistry, settings: PpeSettings) -> None:
        self._registry = registry
        self._settings = settings

    def build(
        self,
        evidence: list[PPEEvidence],
        *,
        version: int,
        evidence_fingerprint: str,
        previous: ProfileSnapshot | None = None,
        trigger: str = "rebuild",
        now: datetime | None = None,
    ) -> ProfileBuildResult:
        generated_at = now or datetime.now(UTC)
        observations = self._collect_observations(evidence, generated_at)
        estimates = [
            self._estimate(dimension_key, context_key, bucket)
            for (dimension_key, context_key), bucket in sorted(observations.items())
        ]
        strengths, constraints, uncertain = self._summaries(estimates)
        caveats = self._caveats(evidence, estimates)
        snapshot = ProfileSnapshot(
            version=version,
            generated_at=generated_at,
            evidence_fingerprint=evidence_fingerprint,
            evidence_count=len(evidence),
            estimates=estimates,
            established_strengths=strengths,
            likely_constraints=constraints,
            uncertain_dimensions=uncertain,
            caveats=caveats,
        )
        audit = ProfileAuditEntry(
            snapshot_id=snapshot.id,
            previous_snapshot_id=previous.id if previous is not None else None,
            generated_at=generated_at,
            trigger=trigger,
            evidence_ids=[item.id for item in evidence],
            changes=self._changes(previous, snapshot),
        )
        report = self.report(snapshot)
        return ProfileBuildResult(snapshot=snapshot, audit=audit, report=report)

    def report(self, snapshot: ProfileSnapshot) -> ProfileReport:
        global_estimates = {
            estimate.dimension_key: estimate
            for estimate in snapshot.estimates
            if estimate.context_key == "global"
        }
        signals: list[ProfileSignal] = []
        adaptations: list[ProfileGuidance] = []
        training: list[ProfileGuidance] = []

        for definition in self._registry.list():
            estimate = global_estimates.get(definition.key)
            if estimate is None:
                signals.append(
                    ProfileSignal(
                        kind=ProfileSignalKind.UNCERTAIN,
                        dimension_key=definition.key,
                        label=definition.label,
                        score=0.0,
                        confidence=0.0,
                        explanation="No usable evidence has been recorded for this dimension.",
                    )
                )
                continue
            if estimate.confidence < self._settings.minimum_report_confidence:
                signals.append(
                    ProfileSignal(
                        kind=ProfileSignalKind.UNCERTAIN,
                        dimension_key=definition.key,
                        label=definition.label,
                        score=estimate.score,
                        confidence=estimate.confidence,
                        explanation=(
                            f"Evidence is still limited: {estimate.evidence_count} observations "
                            f"across {estimate.independent_raid_count} independent raids."
                        ),
                    )
                )
                continue

            if estimate.score >= self._settings.signal_threshold:
                signals.append(
                    ProfileSignal(
                        kind=ProfileSignalKind.STRENGTH,
                        dimension_key=definition.key,
                        label=definition.label,
                        score=estimate.score,
                        confidence=estimate.confidence,
                        explanation=estimate.interpretation,
                    )
                )
            elif estimate.score <= -self._settings.signal_threshold:
                signals.append(
                    ProfileSignal(
                        kind=ProfileSignalKind.CONSTRAINT,
                        dimension_key=definition.key,
                        label=definition.label,
                        score=estimate.score,
                        confidence=estimate.confidence,
                        explanation=estimate.interpretation,
                    )
                )
                adaptations.append(
                    ProfileGuidance(
                        mode=RecommendationMode.ADAPTATION,
                        dimension_key=definition.key,
                        label=definition.label,
                        confidence=estimate.confidence,
                        guidance=definition.adaptation_guidance,
                        reason=estimate.interpretation,
                    )
                )
                training.append(
                    ProfileGuidance(
                        mode=RecommendationMode.TRAINING,
                        dimension_key=definition.key,
                        label=definition.label,
                        confidence=estimate.confidence,
                        guidance=definition.training_guidance,
                        reason=(
                            "This is a training option, not a requirement for progression. "
                            f"Current evidence: {estimate.interpretation}"
                        ),
                    )
                )

        context_variations = self._context_variations(snapshot)
        for dimension_key, explanation in context_variations:
            definition = self._registry.get(dimension_key)
            global_estimate = global_estimates.get(dimension_key)
            signals.append(
                ProfileSignal(
                    kind=ProfileSignalKind.CONTEXT_DEPENDENT,
                    dimension_key=dimension_key,
                    label=definition.label,
                    score=global_estimate.score if global_estimate is not None else 0.0,
                    confidence=(
                        global_estimate.confidence if global_estimate is not None else 0.0
                    ),
                    explanation=explanation,
                )
            )

        established = sum(
            signal.kind is not ProfileSignalKind.UNCERTAIN for signal in signals
        )
        overview = (
            f"Profile version {snapshot.version} uses {snapshot.evidence_count} evidence records. "
            f"It currently contains {established} reportable signals. Scores describe observed "
            "patterns, not fixed traits, and remain segmented by context where evidence permits."
        )
        return ProfileReport(
            generated_at=snapshot.generated_at,
            snapshot_version=snapshot.version,
            overview=overview,
            signals=signals,
            adaptation_guidance=adaptations,
            training_guidance=training,
            context_variations=[explanation for _, explanation in context_variations],
            caveats=snapshot.caveats,
        )

    def _collect_observations(
        self,
        evidence: list[PPEEvidence],
        now: datetime,
    ) -> dict[tuple[str, str], list[_Observation]]:
        buckets: dict[tuple[str, str], list[_Observation]] = defaultdict(list)
        for item in evidence:
            for impact in item.impacts:
                if not self._registry.contains(impact.dimension_key):
                    raise ValueError(f"Unknown PPE dimension: {impact.dimension_key}")
                definition = self._registry.get(impact.dimension_key)
                weight = self._weight(item, impact, definition.half_life_days, now)
                if weight <= 0.0:
                    continue
                observation = _Observation(
                    evidence_id=item.id,
                    raid_key=str(item.raid_id or item.id),
                    occurred_at=item.observed_at,
                    value=impact.value,
                    weight=weight,
                )
                for context_key in item.context.segment_keys(definition.context_fields):
                    buckets[(impact.dimension_key, context_key)].append(observation)
        return buckets

    def _weight(
        self,
        evidence: PPEEvidence,
        impact: DimensionImpact,
        half_life_days: float,
        now: datetime,
    ) -> float:
        observed_at = evidence.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        age_days = max(0.0, (now - observed_at).total_seconds() / 86400.0)
        recency = math.pow(0.5, age_days / half_life_days)
        return (
            evidence.reliability
            * impact.strength
            * impact.confidence
            * _SOURCE_MULTIPLIERS[evidence.source]
            * recency
        )

    def _estimate(
        self,
        dimension_key: str,
        context_key: str,
        observations: list[_Observation],
    ) -> ProfileEstimate:
        capped = self._cap_by_raid(observations)
        total_weight = sum(item.weight for item in capped)
        numerator = sum(item.value * item.weight for item in capped)
        score = numerator / (self._settings.neutral_prior_weight + total_weight)
        positive = sum(item.weight for item in capped if item.value > 0.0)
        negative = sum(item.weight for item in capped if item.value < 0.0)
        signed_total = positive + negative
        contradiction_ratio = (
            2.0 * min(positive, negative) / signed_total
            if signed_total > 0.0
            else 0.0
        )
        contradictory_weight = min(positive, negative)
        consistency = 1.0 - (0.55 * contradiction_ratio)
        base_confidence = 1.0 - math.exp(
            -total_weight / self._settings.confidence_weight_scale
        )
        definition = self._registry.get(dimension_key)
        sufficiency = min(
            1.0,
            total_weight / max(definition.minimum_evidence_weight, 0.001),
        )
        confidence = min(
            1.0,
            base_confidence * consistency * (0.65 + 0.35 * sufficiency),
        )
        latest = max((item.occurred_at for item in capped), default=None)
        supporting = sorted(capped, key=lambda item: item.weight, reverse=True)
        return ProfileEstimate(
            dimension_key=dimension_key,
            context_key=context_key,
            score=max(-1.0, min(1.0, score)),
            confidence=max(0.0, min(1.0, confidence)),
            effective_weight=total_weight,
            evidence_count=len(capped),
            independent_raid_count=len({item.raid_key for item in capped}),
            contradiction_ratio=max(0.0, min(1.0, contradiction_ratio)),
            contradictory_weight=contradictory_weight,
            last_evidence_at=latest,
            supporting_evidence_ids=[item.evidence_id for item in supporting[:20]],
            interpretation=self._interpret(
                dimension_key,
                score,
                confidence,
                contradiction_ratio,
            ),
        )

    def _cap_by_raid(self, observations: list[_Observation]) -> list[_Observation]:
        grouped: dict[str, list[_Observation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.raid_key].append(observation)
        result: list[_Observation] = []
        for items in grouped.values():
            total = sum(item.weight for item in items)
            scale = min(
                1.0,
                self._settings.maximum_weight_per_raid_dimension / total,
            )
            result.extend(
                _Observation(
                    evidence_id=item.evidence_id,
                    raid_key=item.raid_key,
                    occurred_at=item.occurred_at,
                    value=item.value,
                    weight=item.weight * scale,
                )
                for item in items
            )
        return result

    def _interpret(
        self,
        dimension_key: str,
        score: float,
        confidence: float,
        contradiction_ratio: float,
    ) -> str:
        definition = self._registry.get(dimension_key)
        if confidence < self._settings.minimum_report_confidence:
            return "Evidence is currently insufficient for a stable interpretation."
        if contradiction_ratio >= 0.55:
            return (
                "Evidence is meaningfully contradictory; performance likely depends on context "
                "or the current sample is too mixed for one conclusion."
            )
        if score >= self._settings.signal_threshold:
            return f"Current evidence indicates the player {definition.positive_label}."
        if score <= -self._settings.signal_threshold:
            return f"Current evidence indicates the player {definition.negative_label}."
        return (
            "Current evidence is near neutral or does not yet show a consistent "
            "directional pattern."
        )

    def _summaries(
        self,
        estimates: list[ProfileEstimate],
    ) -> tuple[list[str], list[str], list[str]]:
        strengths: list[str] = []
        constraints: list[str] = []
        uncertain: list[str] = []
        for estimate in estimates:
            if estimate.context_key != "global":
                continue
            definition = self._registry.get(estimate.dimension_key)
            if estimate.confidence < self._settings.minimum_established_confidence:
                uncertain.append(definition.label)
            elif estimate.score >= self._settings.signal_threshold:
                strengths.append(definition.label)
            elif estimate.score <= -self._settings.signal_threshold:
                constraints.append(definition.label)
        return sorted(strengths), sorted(constraints), sorted(uncertain)

    def _caveats(
        self,
        evidence: list[PPEEvidence],
        estimates: list[ProfileEstimate],
    ) -> list[str]:
        caveats = [
            (
                "A profile estimate is a weighted description of recorded evidence, "
                "not a permanent trait."
            ),
            (
                "Raid outcomes are not pure skill measurements; low-control outcomes "
                "retain low weight."
            ),
            "Adaptation guidance and deliberate training guidance remain separate.",
        ]
        raid_count = len({item.raid_id for item in evidence if item.raid_id is not None})
        if raid_count < self._settings.minimum_independent_raids:
            caveats.append(
                f"Only {raid_count} independent raids are represented; avoid broad conclusions."
            )
        contradictory = [
            estimate
            for estimate in estimates
            if estimate.context_key == "global" and estimate.contradiction_ratio >= 0.55
        ]
        if contradictory:
            caveats.append(
                "Several dimensions contain contradictory evidence and require contextual review."
            )
        return caveats

    def _changes(
        self,
        previous: ProfileSnapshot | None,
        current: ProfileSnapshot,
    ) -> list[DimensionChange]:
        prior: dict[tuple[str, str], ProfileEstimate] = {}
        if previous is not None:
            prior = {
                (item.dimension_key, item.context_key): item
                for item in previous.estimates
            }
        changes: list[DimensionChange] = []
        for estimate in current.estimates:
            old = prior.get((estimate.dimension_key, estimate.context_key))
            if old is not None:
                score_delta = abs(old.score - estimate.score)
                confidence_delta = abs(old.confidence - estimate.confidence)
                if score_delta < 0.01 and confidence_delta < 0.01:
                    continue
            changes.append(
                DimensionChange(
                    dimension_key=estimate.dimension_key,
                    context_key=estimate.context_key,
                    previous_score=old.score if old is not None else None,
                    current_score=estimate.score,
                    previous_confidence=old.confidence if old is not None else None,
                    current_confidence=estimate.confidence,
                )
            )
        return changes

    def _context_variations(
        self,
        snapshot: ProfileSnapshot,
    ) -> list[tuple[str, str]]:
        by_dimension: dict[str, list[ProfileEstimate]] = defaultdict(list)
        for estimate in snapshot.estimates:
            by_dimension[estimate.dimension_key].append(estimate)
        variations: list[tuple[str, str]] = []
        for dimension_key, estimates in by_dimension.items():
            global_estimate = next(
                (item for item in estimates if item.context_key == "global"),
                None,
            )
            if global_estimate is None:
                continue
            for contextual in estimates:
                if contextual.context_key == "global":
                    continue
                if contextual.confidence < self._settings.minimum_report_confidence:
                    continue
                delta = contextual.score - global_estimate.score
                if abs(delta) < self._settings.context_difference_threshold:
                    continue
                direction = "stronger" if delta > 0 else "weaker"
                explanation = (
                    f"{self._registry.get(dimension_key).label} appears {direction} in "
                    f"context `{contextual.context_key}` (context score "
                    f"{contextual.score:+.2f}, global {global_estimate.score:+.2f})."
                )
                variations.append((dimension_key, explanation))
        return sorted(variations, key=lambda item: (item[0], item[1]))


def report_to_markdown(report: ProfileReport) -> str:
    lines = [
        "# Personal Playstyle Engine Report\n\n",
        f"**Snapshot version:** {report.snapshot_version}\n\n",
        f"**Generated:** {report.generated_at.isoformat()}\n\n",
        f"{report.overview}\n\n",
        "## Signals\n\n",
    ]
    for signal in report.signals:
        lines.append(
            f"- **{signal.label}** — {signal.kind.value}; score {signal.score:+.2f}; "
            f"confidence {signal.confidence:.0%}. {signal.explanation}\n"
        )
    lines.append("\n## Adaptation Guidance\n\n")
    if report.adaptation_guidance:
        for guidance in report.adaptation_guidance:
            lines.append(f"- **{guidance.label}:** {guidance.guidance}\n")
    else:
        lines.append("_No high-confidence adaptation guidance yet._\n")
    lines.append("\n## Deliberate Training Options\n\n")
    if report.training_guidance:
        for guidance in report.training_guidance:
            lines.append(f"- **{guidance.label}:** {guidance.guidance}\n")
    else:
        lines.append("_No high-confidence training targets yet._\n")
    lines.append("\n## Context Variations\n\n")
    if report.context_variations:
        lines.extend(f"- {variation}\n" for variation in report.context_variations)
    else:
        lines.append("_No stable context-specific differences yet._\n")
    lines.append("\n## Caveats\n\n")
    lines.extend(f"- {caveat}\n" for caveat in report.caveats)
    return "".join(lines)
