from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tarkov_agent.config import RecommendationSettings
from tarkov_agent.domain.ppe import PPEContext, ProfileSnapshot
from tarkov_agent.domain.recommendations import (
    CandidateEvaluation,
    CandidateStatus,
    ExperimentDesign,
    MechanicCheck,
    MechanicRequirement,
    PlayerFitCheck,
    RecommendationPlan,
    RecommendationPurpose,
    RecommendationRequest,
    RiskPosture,
    StrategyCandidate,
)
from tarkov_agent.domain.source_truth import MechanicsQuery
from tarkov_agent.services.ppe import PPEDisabledError, PPEProfileService
from tarkov_agent.services.source_truth import SourceTruthDisabledError, SourceTruthService


class RecommendationDisabledError(RuntimeError):
    pass


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


class RecommendationService:
    def __init__(
        self,
        truth: SourceTruthService,
        ppe: PPEProfileService,
        output_root: Path | str,
        settings: RecommendationSettings,
    ) -> None:
        self._truth = truth
        self._ppe = ppe
        self._root = Path(output_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def generate(self, request: RecommendationRequest) -> RecommendationPlan:
        self._require_enabled()
        profile = self._profile_or_none()
        candidates = self._generate_candidates(request)
        evaluations = [self._evaluate(item, request, profile) for item in candidates]
        evaluations.sort(
            key=lambda item: (
                item.status is CandidateStatus.ELIGIBLE,
                item.total_score,
                item.confidence,
                item.candidate.key,
            ),
            reverse=True,
        )
        eligible = [item for item in evaluations if item.status is CandidateStatus.ELIGIBLE]
        primary = eligible[0] if eligible else None
        fallback = eligible[1] if len(eligible) > 1 else None
        research_tasks = self._research_tasks(evaluations)
        assumptions = self._assumptions(request, profile, primary)
        evidence_references = self._evidence_references(evaluations)
        can_recommend = primary is not None and primary.confidence >= self._settings.minimum_plan_confidence
        refusal_reason: str | None = None
        if primary is None:
            refusal_reason = "Every generated strategy was blocked by unresolved hard mechanics."
        elif not can_recommend:
            refusal_reason = (
                "The best eligible strategy is below the configured minimum plan confidence; "
                "collect more player evidence or verify its mechanics before relying on it."
            )
        experiment = (
            self._experiment(request, primary)
            if request.purpose is RecommendationPurpose.TRAINING and primary is not None
            else None
        )
        plan = RecommendationPlan(
            request=request,
            can_recommend=can_recommend,
            profile_version=profile.version if profile is not None else None,
            primary=primary,
            fallback=fallback,
            evaluated_candidates=evaluations,
            assumptions=assumptions,
            research_tasks=research_tasks,
            evidence_references=evidence_references,
            experiment=experiment,
            refusal_reason=refusal_reason,
        )
        self._write(plan)
        return plan

    def latest(self) -> RecommendationPlan | None:
        path = self._root / "latest.json"
        if not path.exists():
            return None
        return RecommendationPlan.model_validate_json(path.read_text(encoding="utf-8"))

    def latest_markdown(self) -> str:
        latest = self.latest()
        if latest is None:
            raise LookupError("No recommendation plan has been generated")
        return recommendation_to_markdown(latest)

    def templates(self, request: RecommendationRequest) -> list[StrategyCandidate]:
        self._require_enabled()
        return self._generate_candidates(request)

    def _evaluate(
        self,
        candidate: StrategyCandidate,
        request: RecommendationRequest,
        profile: ProfileSnapshot | None,
    ) -> CandidateEvaluation:
        requirements = self._requirements(candidate, request)
        mechanic_checks: list[MechanicCheck] = []
        blockers: list[str] = []
        reasons: list[str] = []
        mechanic_confidences: list[float] = []
        for requirement in requirements:
            try:
                resolution = self._truth.query(
                    MechanicsQuery(
                        key=requirement.key,
                        game=request.game,
                        patch_version=request.patch_version,
                    )
                )
            except SourceTruthDisabledError:
                resolution = self._truth_unavailable(requirement, request)
            blocking = requirement.required and not resolution.can_recommend
            mechanic_checks.append(
                MechanicCheck(
                    requirement=requirement,
                    resolution=resolution,
                    blocking=blocking,
                )
            )
            if blocking:
                blockers.append(f"{requirement.key}: {resolution.reason}")
            elif not resolution.can_recommend:
                reasons.append(f"Optional mechanic unresolved: {requirement.key}")
            else:
                mechanic_confidences.append(resolution.confidence)
                reasons.append(f"Verified mechanic: {requirement.key}")

        fit_checks, player_fit_score, profile_confidence = self._player_fit(candidate, request, profile)
        risk_fit_score = self._risk_fit(candidate.risk_level, request.risk_posture)
        objective_score = candidate.objective_alignment
        total_score = (
            (objective_score * 0.40)
            + (player_fit_score * 0.35)
            + (risk_fit_score * 0.25)
        )
        mechanics_confidence = (
            sum(mechanic_confidences) / len(mechanic_confidences)
            if mechanic_confidences
            else (0.75 if not requirements else 0.35)
        )
        confidence = min(
            1.0,
            (mechanics_confidence * 0.45)
            + (profile_confidence * 0.35)
            + (objective_score * 0.20),
        )
        status = CandidateStatus.BLOCKED if blockers else CandidateStatus.ELIGIBLE
        if profile is None:
            reasons.append("No established PPE snapshot was available; player fit remains neutral.")
        reasons.append(
            f"Risk level {candidate.risk_level:.2f} compared with {request.risk_posture.value} posture."
        )
        return CandidateEvaluation(
            candidate=candidate.model_copy(update={"mechanic_requirements": requirements}),
            status=status,
            objective_score=objective_score,
            player_fit_score=player_fit_score,
            risk_fit_score=risk_fit_score,
            total_score=total_score,
            confidence=confidence,
            mechanic_checks=mechanic_checks,
            player_fit_checks=fit_checks,
            reasons=reasons,
            blockers=blockers,
        )

    def _player_fit(
        self,
        candidate: StrategyCandidate,
        request: RecommendationRequest,
        profile: ProfileSnapshot | None,
    ) -> tuple[list[PlayerFitCheck], float, float]:
        if profile is None or not candidate.fit_weights:
            return [], 0.5, 0.20 if profile is None else 0.45
        checks: list[PlayerFitCheck] = []
        weighted_total = 0.0
        confidence_total = 0.0
        weight_total = 0.0
        map_key = PPEContext.normalize(request.map_name)
        for dimension_key, fit_weight in sorted(candidate.fit_weights.items()):
            context_key = f"map_name={map_key}" if map_key else "global"
            estimate = profile.estimate(dimension_key, context_key)
            if estimate is None:
                context_key = "global"
                estimate = profile.estimate(dimension_key)
            if estimate is None:
                continue
            contribution = max(0.0, min(1.0, 0.5 + (estimate.score * fit_weight * 0.5)))
            importance = max(0.05, abs(fit_weight))
            weighted_total += contribution * importance
            confidence_total += estimate.confidence * importance
            weight_total += importance
            checks.append(
                PlayerFitCheck(
                    dimension_key=dimension_key,
                    context_key=context_key,
                    estimate_score=estimate.score,
                    estimate_confidence=estimate.confidence,
                    fit_weight=fit_weight,
                    contribution=contribution,
                    supporting_evidence_ids=estimate.supporting_evidence_ids,
                    rationale=(
                        f"Profile score {estimate.score:.2f} with confidence "
                        f"{estimate.confidence:.2f} was compared with strategy weight "
                        f"{fit_weight:.2f}."
                    ),
                )
            )
        if weight_total == 0.0:
            return checks, 0.5, 0.25
        return checks, weighted_total / weight_total, confidence_total / weight_total

    @staticmethod
    def _risk_fit(level: float, posture: RiskPosture) -> float:
        target = {
            RiskPosture.LOW: 0.20,
            RiskPosture.BALANCED: 0.50,
            RiskPosture.HIGH: 0.80,
        }[posture]
        return max(0.0, 1.0 - abs(level - target))

    @staticmethod
    def _requirements(
        candidate: StrategyCandidate,
        request: RecommendationRequest,
    ) -> list[MechanicRequirement]:
        combined = list(candidate.mechanic_requirements)
        combined.extend(
            MechanicRequirement(
                key=key,
                rationale="The user marked this mechanic as a hard dependency for the plan.",
            )
            for key in request.mechanic_keys
        )
        deduplicated: dict[str, MechanicRequirement] = {}
        for item in combined:
            previous = deduplicated.get(item.key)
            if previous is None or (item.required and not previous.required):
                deduplicated[item.key] = item
        return list(deduplicated.values())

    def _generate_candidates(self, request: RecommendationRequest) -> list[StrategyCandidate]:
        is_scav = (request.character_type or "").casefold().strip() == "scav"
        location = request.map_name or "the selected map"
        if request.purpose is RecommendationPurpose.TRAINING:
            return [
                StrategyCandidate(
                    key="training.controlled-single-variable",
                    title="Controlled single-variable practice",
                    summary=(
                        "Isolate one decision or mechanical behavior while keeping equipment, "
                        "route intent, and review criteria stable."
                    ),
                    purpose=request.purpose,
                    risk_level=0.25,
                    objective_alignment=0.88,
                    fit_weights={
                        "execution_decisiveness": -0.30,
                        "pressure_stability": -0.25,
                        "objective_discipline": 0.45,
                    },
                    steps=[
                        f"Choose one repeatable section of {location} or use Arena/offline practice.",
                        "State one hypothesis before starting and change only one variable.",
                        "Use markers for the first cue, decision, result, and immediate self-assessment.",
                        "Review the same signals across several attempts before changing the plan.",
                    ],
                    assumptions=["Training should not place progression-critical gear or tasks at risk."],
                ),
                StrategyCandidate(
                    key="training.live-transfer",
                    title="Low-cost live transfer experiment",
                    summary=(
                        "Test whether a controlled skill transfers into a normal raid while preserving "
                        "an explicit exit condition."
                    ),
                    purpose=request.purpose,
                    risk_level=0.50,
                    objective_alignment=0.72,
                    fit_weights={
                        "risk_management": 0.35,
                        "disengagement": 0.55,
                        "overcommitment_control": 0.60,
                    },
                    steps=[
                        "Use a repeatable low-cost loadout and one clearly defined success condition.",
                        "Attempt the trained behavior only when the planned context appears.",
                        "Disengage when the context no longer matches the experiment.",
                        "Record outcome, decision quality, and whether the variable was actually isolated.",
                    ],
                    assumptions=["A failed outcome is still useful when the controlled variable was tested."],
                ),
            ]

        if is_scav:
            shared = [
                MechanicRequirement(
                    key="scav.extracted_loot_transfers",
                    rationale="The progression value of the plan depends on extracted Scav loot transferring.",
                ),
                MechanicRequirement(
                    key="scav.random_loadout",
                    rationale="The plan must remain viable without assuming a chosen starting kit.",
                ),
            ]
            return [
                StrategyCandidate(
                    key="scav.survival-first-transfer",
                    title="Survival-first transfer run",
                    summary=(
                        "Prioritize a clean extraction and transferable value over optional contested "
                        "areas or unnecessary contact."
                    ),
                    purpose=request.purpose,
                    risk_level=0.20,
                    objective_alignment=0.92,
                    mechanic_requirements=shared,
                    fit_weights={
                        "objective_discipline": 0.80,
                        "risk_management": 0.75,
                        "disengagement": 0.65,
                        "reactive_close_range_effectiveness": -0.35,
                    },
                    steps=[
                        "Confirm extracts and choose a route with an early safe exit option.",
                        f"Collect objective-relevant or compact high-value items on {location}.",
                        "Avoid uncertain contacts unless they block the extraction path.",
                        "Commit to extraction once the primary value threshold is reached.",
                    ],
                    assumptions=["The raid objective values extraction more than optional combat."],
                ),
                StrategyCandidate(
                    key="scav.information-first-flexible",
                    title="Information-first flexible route",
                    summary=(
                        "Use sound, visible activity, and time remaining to select among several route "
                        "branches instead of committing immediately."
                    ),
                    purpose=request.purpose,
                    risk_level=0.40,
                    objective_alignment=0.82,
                    mechanic_requirements=shared,
                    fit_weights={
                        "route_prediction": 0.70,
                        "audio_interpretation": 0.65,
                        "information_patience": 0.75,
                        "repositioning": 0.45,
                    },
                    steps=[
                        "Begin with a short information-gathering segment near spawn.",
                        "Choose the quiet, balanced, or contested branch based on actual cues.",
                        "Mark meaningful route changes and the cue that caused each change.",
                        "Preserve enough time for a low-complexity extraction route.",
                    ],
                    assumptions=["Several viable route branches are available from the spawn area."],
                ),
                StrategyCandidate(
                    key="scav.opportunistic-contested",
                    title="Opportunistic contested route",
                    summary=(
                        "Accept selected contact and contested loot when the information advantage is "
                        "clear, while retaining a disengagement threshold."
                    ),
                    purpose=request.purpose,
                    risk_level=0.70,
                    objective_alignment=0.70,
                    mechanic_requirements=shared,
                    fit_weights={
                        "fight_selection": 0.65,
                        "contact_conversion": 0.70,
                        "reactive_close_range_effectiveness": 0.70,
                        "pressure_stability": 0.50,
                        "overcommitment_control": 0.55,
                    },
                    steps=[
                        "Approach contested areas only after identifying a concrete information edge.",
                        "Define the disengagement cue before entering the contact area.",
                        "Take compact value and avoid extending the fight after the objective is met.",
                        "Transition immediately to an extraction route after the chosen opportunity.",
                    ],
                    assumptions=["The objective permits elevated risk and possible player contact."],
                ),
            ]

        return [
            StrategyCandidate(
                key="pmc.objective-first-low-exposure",
                title="Objective-first low-exposure route",
                summary=(
                    "Protect the primary objective with conservative timing, limited exposure, and a "
                    "predefined disengagement route."
                ),
                purpose=request.purpose,
                risk_level=0.25,
                objective_alignment=0.94,
                fit_weights={
                    "objective_discipline": 0.85,
                    "risk_management": 0.75,
                    "disengagement": 0.60,
                    "reactive_close_range_effectiveness": -0.40,
                },
                steps=[
                    f"Select the shortest defensible route to the objective on {location}.",
                    "Delay or reroute when early cues indicate equal-information contact.",
                    "Complete the objective before accepting optional loot or combat.",
                    "Use the predefined extraction branch after the success condition is met.",
                ],
                assumptions=["The objective can be completed without a required player engagement."],
            ),
            StrategyCandidate(
                key="pmc.information-first-flexible",
                title="Information-first flexible route",
                summary=(
                    "Gather early information and choose among route branches instead of forcing a "
                    "single pre-raid path."
                ),
                purpose=request.purpose,
                risk_level=0.50,
                objective_alignment=0.82,
                fit_weights={
                    "route_prediction": 0.75,
                    "audio_interpretation": 0.65,
                    "information_patience": 0.75,
                    "map_timing": 0.55,
                },
                steps=[
                    "Use the opening minute to identify traffic and likely route conflicts.",
                    "Select a quiet, balanced, or fast branch from observed information.",
                    "Reassess after every major sound event or route obstruction.",
                    "Retain a fallback objective when the primary route becomes unreliable.",
                ],
                assumptions=["The objective supports more than one viable route or timing window."],
            ),
            StrategyCandidate(
                key="pmc.contact-capable-balanced",
                title="Contact-capable balanced route",
                summary=(
                    "Pursue the objective while accepting selected engagements that begin with a "
                    "positioning or information advantage."
                ),
                purpose=request.purpose,
                risk_level=0.65,
                objective_alignment=0.76,
                fit_weights={
                    "prepared_engagement_effectiveness": 0.65,
                    "fight_selection": 0.70,
                    "contact_conversion": 0.65,
                    "pressure_stability": 0.50,
                    "overcommitment_control": 0.55,
                },
                steps=[
                    "Move through positions that preserve cover and an exit route.",
                    "Accept contact only with a defined information or positioning advantage.",
                    "Reposition after the first exchange rather than repeating an exposed angle.",
                    "Return to the objective or extract when the engagement no longer serves the plan.",
                ],
                assumptions=["Selected combat can support the objective without becoming the objective."],
            ),
        ]

    @staticmethod
    def _experiment(
        request: RecommendationRequest,
        primary: CandidateEvaluation,
    ) -> ExperimentDesign:
        return ExperimentDesign(
            hypothesis=(
                f"Using '{primary.candidate.title}' will improve decision quality for "
                f"'{request.objective}' without increasing uncontrolled risk."
            ),
            independent_variable="Use the selected strategy while holding the review criteria constant.",
            controls=[
                "Use the same map or mode when practical.",
                "Keep budget/loadout family within one tier.",
                "Use the same marker definitions and review questions.",
            ],
            success_signals=[
                "The planned decision was executed in the intended context.",
                "The disengagement or stop condition was respected.",
                "Review evidence supports the targeted PPE dimension without relying only on outcome.",
            ],
            recommended_sample_size=5,
        )

    def _profile_or_none(self) -> ProfileSnapshot | None:
        try:
            return self._ppe.current_or_build()
        except PPEDisabledError:
            return None

    @staticmethod
    def _assumptions(
        request: RecommendationRequest,
        profile: ProfileSnapshot | None,
        primary: CandidateEvaluation | None,
    ) -> list[str]:
        assumptions = list(request.constraints)
        if primary is not None:
            assumptions.extend(primary.candidate.assumptions)
        if profile is None:
            assumptions.append("Player-fit scoring uses a neutral prior because PPE is unavailable.")
        elif profile.evidence_count < 3:
            assumptions.append("The PPE profile is early and should not be treated as an established trait model.")
        return list(dict.fromkeys(assumptions))

    @staticmethod
    def _research_tasks(evaluations: list[CandidateEvaluation]) -> list[str]:
        tasks: list[str] = []
        for evaluation in evaluations:
            for check in evaluation.mechanic_checks:
                if not check.resolution.can_recommend:
                    tasks.append(
                        f"Verify `{check.requirement.key}`: {check.resolution.reason}"
                    )
        return list(dict.fromkeys(tasks))

    @staticmethod
    def _evidence_references(evaluations: list[CandidateEvaluation]) -> list[str]:
        references: list[str] = []
        for evaluation in evaluations:
            for check in evaluation.mechanic_checks:
                references.extend(citation.url for citation in check.resolution.citations)
            for fit in evaluation.player_fit_checks:
                references.extend(f"ppe:{item}" for item in fit.supporting_evidence_ids)
        return list(dict.fromkeys(references))

    @staticmethod
    def _truth_unavailable(
        requirement: MechanicRequirement,
        request: RecommendationRequest,
    ) -> object:
        from tarkov_agent.domain.source_truth import ClaimResolution, QueryResolution

        return ClaimResolution(
            query=MechanicsQuery(
                key=requirement.key,
                game=request.game,
                patch_version=request.patch_version,
            ),
            resolution=QueryResolution.UNRESOLVED,
            can_recommend=False,
            reason="The Source-of-Truth service is disabled.",
        )

    def _write(self, plan: RecommendationPlan) -> None:
        _atomic_write(self._root / "latest.json", plan.model_dump_json(indent=2))
        _atomic_write(self._root / "latest.md", recommendation_to_markdown(plan))
        history = self._root / "history"
        stamp = plan.generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S")
        _atomic_write(history / f"{stamp}_{str(plan.id)[:8]}.json", plan.model_dump_json(indent=2))
        entries = sorted(history.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for stale in entries[self._settings.maximum_history :]:
            stale.unlink(missing_ok=True)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RecommendationDisabledError("The Recommendation Engine is disabled in configuration")


def recommendation_to_markdown(plan: RecommendationPlan) -> str:
    lines = [
        "# Tarkov Recommendation Plan",
        "",
        f"Generated: {plan.generated_at.isoformat()}",
        f"Objective: {plan.request.objective}",
        f"Purpose: {plan.request.purpose.value}",
        f"Can recommend: {'yes' if plan.can_recommend else 'no'}",
        "",
    ]
    if plan.refusal_reason:
        lines.extend(["## Refusal / caution", "", plan.refusal_reason, ""])
    for heading, evaluation in (("Primary plan", plan.primary), ("Fallback plan", plan.fallback)):
        lines.extend([f"## {heading}", ""])
        if evaluation is None:
            lines.extend(["No eligible candidate.", ""])
            continue
        lines.extend(
            [
                f"### {evaluation.candidate.title}",
                "",
                evaluation.candidate.summary,
                "",
                f"- Total score: {evaluation.total_score:.3f}",
                f"- Confidence: {evaluation.confidence:.3f}",
                f"- Objective score: {evaluation.objective_score:.3f}",
                f"- Player-fit score: {evaluation.player_fit_score:.3f}",
                f"- Risk-fit score: {evaluation.risk_fit_score:.3f}",
                "",
                "Steps:",
                "",
            ]
        )
        lines.extend(f"1. {step}" for step in evaluation.candidate.steps)
        lines.append("")
        if evaluation.mechanic_checks:
            lines.extend(["Mechanics:", ""])
            for check in evaluation.mechanic_checks:
                resolution = check.resolution
                selected = resolution.selected_claim
                value = f" — `{selected.value}`" if selected is not None else ""
                lines.append(
                    f"- `{check.requirement.key}`: {resolution.resolution.value}{value}; "
                    f"{resolution.reason}"
                )
            lines.append("")
    if plan.experiment is not None:
        lines.extend(
            [
                "## Experiment",
                "",
                f"**Hypothesis:** {plan.experiment.hypothesis}",
                "",
                f"**Independent variable:** {plan.experiment.independent_variable}",
                "",
                f"**Recommended attempts:** {plan.experiment.recommended_sample_size}",
                "",
            ]
        )
    lines.extend(["## Assumptions", ""])
    lines.extend(f"- {item}" for item in plan.assumptions or ["No additional assumptions recorded."])
    lines.extend(["", "## Research tasks", ""])
    lines.extend(f"- {item}" for item in plan.research_tasks or ["No blocking research tasks."])
    return "\n".join(lines).rstrip() + "\n"
