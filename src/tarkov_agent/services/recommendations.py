from __future__ import annotations

from datetime import UTC
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
from tarkov_agent.domain.source_truth import (
    ClaimResolution,
    MechanicsQuery,
    QueryResolution,
)
from tarkov_agent.services.ppe import PPEDisabledError, PPEProfileService
from tarkov_agent.services.source_truth import (
    SourceTruthDisabledError,
    SourceTruthService,
)


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
        evaluations = [
            self._evaluate(candidate, request, profile)
            for candidate in self._generate_candidates(request)
        ]
        evaluations.sort(
            key=lambda item: (
                item.status is CandidateStatus.ELIGIBLE,
                item.total_score,
                item.confidence,
                item.candidate.key,
            ),
            reverse=True,
        )
        eligible = [
            item
            for item in evaluations
            if item.status is CandidateStatus.ELIGIBLE
        ]
        primary = eligible[0] if eligible else None
        fallback = eligible[1] if len(eligible) > 1 else None
        can_recommend = bool(
            primary is not None
            and primary.confidence >= self._settings.minimum_plan_confidence
        )
        refusal_reason = self._refusal_reason(primary, can_recommend)
        experiment = None
        if request.purpose is RecommendationPurpose.TRAINING and primary:
            experiment = self._experiment(request, primary)
        plan = RecommendationPlan(
            request=request,
            can_recommend=can_recommend,
            profile_version=profile.version if profile else None,
            primary=primary,
            fallback=fallback,
            evaluated_candidates=evaluations,
            assumptions=self._assumptions(request, profile, primary),
            research_tasks=self._research_tasks(evaluations),
            evidence_references=self._evidence_references(evaluations),
            experiment=experiment,
            refusal_reason=refusal_reason,
        )
        self._write(plan)
        return plan

    def latest(self) -> RecommendationPlan | None:
        path = self._root / "latest.json"
        if not path.exists():
            return None
        return RecommendationPlan.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def latest_markdown(self) -> str:
        latest = self.latest()
        if latest is None:
            raise LookupError("No recommendation plan has been generated")
        return recommendation_to_markdown(latest)

    def templates(
        self,
        request: RecommendationRequest,
    ) -> list[StrategyCandidate]:
        self._require_enabled()
        return self._generate_candidates(request)

    def _evaluate(
        self,
        candidate: StrategyCandidate,
        request: RecommendationRequest,
        profile: ProfileSnapshot | None,
    ) -> CandidateEvaluation:
        requirements = self._requirements(candidate, request)
        mechanic_checks = [
            self._check_requirement(requirement, request)
            for requirement in requirements
        ]
        blockers = [
            f"{check.requirement.key}: {check.resolution.reason}"
            for check in mechanic_checks
            if check.blocking
        ]
        mechanic_confidences = [
            check.resolution.confidence
            for check in mechanic_checks
            if check.resolution.can_recommend
        ]
        fit_checks, player_fit, profile_confidence = self._player_fit(
            candidate,
            request,
            profile,
        )
        risk_fit = self._risk_fit(
            candidate.risk_level,
            request.risk_posture,
        )
        objective_score = candidate.objective_alignment
        total_score = (
            (objective_score * 0.40)
            + (player_fit * 0.35)
            + (risk_fit * 0.25)
        )
        mechanic_confidence = self._mechanic_confidence(
            requirements,
            mechanic_confidences,
        )
        confidence = min(
            1.0,
            (mechanic_confidence * 0.45)
            + (profile_confidence * 0.35)
            + (objective_score * 0.20),
        )
        reasons = self._evaluation_reasons(
            candidate,
            request,
            profile,
            mechanic_checks,
        )
        return CandidateEvaluation(
            candidate=candidate.model_copy(
                update={"mechanic_requirements": requirements}
            ),
            status=(
                CandidateStatus.BLOCKED
                if blockers
                else CandidateStatus.ELIGIBLE
            ),
            objective_score=objective_score,
            player_fit_score=player_fit,
            risk_fit_score=risk_fit,
            total_score=total_score,
            confidence=confidence,
            mechanic_checks=mechanic_checks,
            player_fit_checks=fit_checks,
            reasons=reasons,
            blockers=blockers,
        )

    def _check_requirement(
        self,
        requirement: MechanicRequirement,
        request: RecommendationRequest,
    ) -> MechanicCheck:
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
        return MechanicCheck(
            requirement=requirement,
            resolution=resolution,
            blocking=requirement.required and not resolution.can_recommend,
        )

    def _player_fit(
        self,
        candidate: StrategyCandidate,
        request: RecommendationRequest,
        profile: ProfileSnapshot | None,
    ) -> tuple[list[PlayerFitCheck], float, float]:
        if profile is None or not candidate.fit_weights:
            confidence = 0.20 if profile is None else 0.45
            return [], 0.50, confidence
        checks: list[PlayerFitCheck] = []
        fit_total = 0.0
        confidence_total = 0.0
        weight_total = 0.0
        map_key = PPEContext.normalize(request.map_name)
        for dimension_key, fit_weight in sorted(
            candidate.fit_weights.items()
        ):
            context_key = f"map_name={map_key}" if map_key else "global"
            estimate = profile.estimate(dimension_key, context_key)
            if estimate is None:
                context_key = "global"
                estimate = profile.estimate(dimension_key)
            if estimate is None:
                continue
            contribution = max(
                0.0,
                min(1.0, 0.5 + (estimate.score * fit_weight * 0.5)),
            )
            weight = max(0.05, abs(fit_weight))
            fit_total += contribution * weight
            confidence_total += estimate.confidence * weight
            weight_total += weight
            checks.append(
                PlayerFitCheck(
                    dimension_key=dimension_key,
                    context_key=context_key,
                    estimate_score=estimate.score,
                    estimate_confidence=estimate.confidence,
                    fit_weight=fit_weight,
                    contribution=contribution,
                    supporting_evidence_ids=(
                        estimate.supporting_evidence_ids
                    ),
                    rationale=(
                        f"Profile score {estimate.score:.2f} at confidence "
                        f"{estimate.confidence:.2f} was compared with "
                        f"strategy weight {fit_weight:.2f}."
                    ),
                )
            )
        if weight_total == 0.0:
            return checks, 0.50, 0.25
        return (
            checks,
            fit_total / weight_total,
            confidence_total / weight_total,
        )

    @staticmethod
    def _risk_fit(level: float, posture: RiskPosture) -> float:
        target = {
            RiskPosture.LOW: 0.20,
            RiskPosture.BALANCED: 0.50,
            RiskPosture.HIGH: 0.80,
        }[posture]
        return max(0.0, 1.0 - abs(level - target))

    @staticmethod
    def _mechanic_confidence(
        requirements: list[MechanicRequirement],
        confidences: list[float],
    ) -> float:
        if confidences:
            return sum(confidences) / len(confidences)
        return 0.75 if not requirements else 0.35

    @staticmethod
    def _requirements(
        candidate: StrategyCandidate,
        request: RecommendationRequest,
    ) -> list[MechanicRequirement]:
        combined = list(candidate.mechanic_requirements)
        combined.extend(
            MechanicRequirement(
                key=key,
                rationale=(
                    "The user marked this mechanic as a hard dependency "
                    "for the plan."
                ),
            )
            for key in request.mechanic_keys
        )
        selected: dict[str, MechanicRequirement] = {}
        for item in combined:
            previous = selected.get(item.key)
            if previous is None or (item.required and not previous.required):
                selected[item.key] = item
        return list(selected.values())

    @staticmethod
    def _evaluation_reasons(
        candidate: StrategyCandidate,
        request: RecommendationRequest,
        profile: ProfileSnapshot | None,
        checks: list[MechanicCheck],
    ) -> list[str]:
        reasons = [
            f"Verified mechanic: {check.requirement.key}"
            for check in checks
            if check.resolution.can_recommend
        ]
        reasons.extend(
            f"Optional mechanic unresolved: {check.requirement.key}"
            for check in checks
            if not check.resolution.can_recommend
            and not check.requirement.required
        )
        if profile is None:
            reasons.append(
                "No PPE snapshot was available; player fit remains neutral."
            )
        reasons.append(
            f"Risk level {candidate.risk_level:.2f} was compared with "
            f"the {request.risk_posture.value} posture."
        )
        return reasons

    def _generate_candidates(
        self,
        request: RecommendationRequest,
    ) -> list[StrategyCandidate]:
        if request.purpose is RecommendationPurpose.TRAINING:
            return self._training_candidates(request)
        is_scav = (
            (request.character_type or "").casefold().strip() == "scav"
        )
        return (
            self._scav_candidates(request)
            if is_scav
            else self._pmc_candidates(request)
        )

    @staticmethod
    def _training_candidates(
        request: RecommendationRequest,
    ) -> list[StrategyCandidate]:
        location = request.map_name or "a repeatable location"
        return [
            StrategyCandidate(
                key="training.controlled-single-variable",
                title="Controlled single-variable practice",
                summary=(
                    "Isolate one decision or mechanical behavior while "
                    "keeping review criteria stable."
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
                    f"Choose one repeatable section of {location}.",
                    "State one hypothesis and change only one variable.",
                    "Mark the first cue, decision, result, and assessment.",
                    "Compare several attempts before changing the plan.",
                ],
                assumptions=[
                    "Training should not risk progression-critical gear."
                ],
            ),
            StrategyCandidate(
                key="training.live-transfer",
                title="Low-cost live transfer experiment",
                summary=(
                    "Test whether a controlled skill transfers into a "
                    "normal raid with an explicit exit condition."
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
                    "Use a repeatable low-cost loadout and success signal.",
                    "Attempt the behavior only in the planned context.",
                    "Disengage when the experiment context disappears.",
                    "Record execution quality separately from outcome.",
                ],
                assumptions=[
                    "A failed outcome can still test the chosen variable."
                ],
            ),
        ]

    @staticmethod
    def _scav_candidates(
        request: RecommendationRequest,
    ) -> list[StrategyCandidate]:
        location = request.map_name or "the selected map"
        requirements = [
            MechanicRequirement(
                key="scav.extracted_loot_transfers",
                rationale=(
                    "The plan depends on extracted Scav loot transferring "
                    "to the main stash."
                ),
            ),
            MechanicRequirement(
                key="scav.random_loadout",
                rationale=(
                    "The plan must remain viable without a chosen loadout."
                ),
            ),
        ]
        return [
            StrategyCandidate(
                key="scav.survival-first-transfer",
                title="Survival-first transfer run",
                summary=(
                    "Prioritize a clean extraction and transferable value "
                    "over optional contested areas."
                ),
                purpose=request.purpose,
                risk_level=0.20,
                objective_alignment=0.92,
                mechanic_requirements=requirements,
                fit_weights={
                    "objective_discipline": 0.80,
                    "risk_management": 0.75,
                    "disengagement": 0.65,
                    "reactive_close_range_effectiveness": -0.35,
                },
                steps=[
                    "Choose a route with an early safe exit option.",
                    f"Collect objective-relevant value on {location}.",
                    "Avoid uncertain contact unless it blocks extraction.",
                    "Extract when the primary value threshold is reached.",
                ],
                assumptions=[
                    "Extraction matters more than optional combat."
                ],
            ),
            StrategyCandidate(
                key="scav.information-first-flexible",
                title="Information-first flexible route",
                summary=(
                    "Use sound, activity, and time remaining to select "
                    "among several route branches."
                ),
                purpose=request.purpose,
                risk_level=0.40,
                objective_alignment=0.82,
                mechanic_requirements=requirements,
                fit_weights={
                    "route_prediction": 0.70,
                    "audio_interpretation": 0.65,
                    "information_patience": 0.75,
                    "repositioning": 0.45,
                },
                steps=[
                    "Begin with a short information-gathering segment.",
                    "Choose a branch based on actual cues.",
                    "Mark route changes and the cue behind each one.",
                    "Preserve enough time for simple extraction.",
                ],
                assumptions=[
                    "Several route branches are practically available."
                ],
            ),
            StrategyCandidate(
                key="scav.opportunistic-contested",
                title="Opportunistic contested route",
                summary=(
                    "Accept selected contact only when the information "
                    "advantage is clear."
                ),
                purpose=request.purpose,
                risk_level=0.70,
                objective_alignment=0.70,
                mechanic_requirements=requirements,
                fit_weights={
                    "fight_selection": 0.65,
                    "contact_conversion": 0.70,
                    "reactive_close_range_effectiveness": 0.70,
                    "pressure_stability": 0.50,
                    "overcommitment_control": 0.55,
                },
                steps=[
                    "Enter contested areas only with an information edge.",
                    "Define the disengagement cue before contact.",
                    "Take compact value without extending the fight.",
                    "Transition to extraction after the opportunity.",
                ],
                assumptions=[
                    "The objective permits elevated contact risk."
                ],
            ),
        ]

    @staticmethod
    def _pmc_candidates(
        request: RecommendationRequest,
    ) -> list[StrategyCandidate]:
        location = request.map_name or "the selected map"
        return [
            StrategyCandidate(
                key="pmc.objective-first-low-exposure",
                title="Objective-first low-exposure route",
                summary=(
                    "Protect the objective with conservative timing, "
                    "limited exposure, and a disengagement route."
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
                    f"Choose a short defensible route on {location}.",
                    "Reroute when early cues imply equal-information contact.",
                    "Complete the objective before optional combat or loot.",
                    "Use the fallback extraction branch after success.",
                ],
                assumptions=[
                    "The objective does not require player engagement."
                ],
            ),
            StrategyCandidate(
                key="pmc.information-first-flexible",
                title="Information-first flexible route",
                summary=(
                    "Gather early information and choose among branches "
                    "instead of forcing one route."
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
                    "Use the opening to identify traffic conflicts.",
                    "Select a route branch from observed information.",
                    "Reassess after major sound or route events.",
                    "Retain a fallback objective when needed.",
                ],
                assumptions=[
                    "The objective supports more than one route."
                ],
            ),
            StrategyCandidate(
                key="pmc.contact-capable-balanced",
                title="Contact-capable balanced route",
                summary=(
                    "Pursue the objective while accepting engagements "
                    "that begin with a clear advantage."
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
                    "Move through cover with an exit route.",
                    "Accept contact only with a defined advantage.",
                    "Reposition after the first exchange.",
                    "Return to the objective when contact no longer helps.",
                ],
                assumptions=[
                    "Selected combat can support the objective."
                ],
            ),
        ]

    @staticmethod
    def _experiment(
        request: RecommendationRequest,
        primary: CandidateEvaluation,
    ) -> ExperimentDesign:
        return ExperimentDesign(
            hypothesis=(
                f"Using '{primary.candidate.title}' will improve decision "
                f"quality for '{request.objective}' without uncontrolled risk."
            ),
            independent_variable=(
                "Use the selected strategy while holding review criteria "
                "constant."
            ),
            controls=[
                "Use the same map or mode when practical.",
                "Keep the loadout within one budget tier.",
                "Use the same markers and review questions.",
            ],
            success_signals=[
                "The decision was executed in its intended context.",
                "The disengagement or stop condition was respected.",
                "Evidence supports the target beyond outcome alone.",
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
        if primary:
            assumptions.extend(primary.candidate.assumptions)
        if profile is None:
            assumptions.append(
                "Player-fit scoring uses a neutral prior because PPE is off."
            )
        elif profile.evidence_count < 3:
            assumptions.append(
                "The PPE profile is early and is not an established trait model."
            )
        return list(dict.fromkeys(assumptions))

    @staticmethod
    def _research_tasks(
        evaluations: list[CandidateEvaluation],
    ) -> list[str]:
        tasks = [
            f"Verify `{check.requirement.key}`: {check.resolution.reason}"
            for evaluation in evaluations
            for check in evaluation.mechanic_checks
            if not check.resolution.can_recommend
        ]
        return list(dict.fromkeys(tasks))

    @staticmethod
    def _evidence_references(
        evaluations: list[CandidateEvaluation],
    ) -> list[str]:
        references: list[str] = []
        for evaluation in evaluations:
            for check in evaluation.mechanic_checks:
                references.extend(
                    citation.url for citation in check.resolution.citations
                )
            for fit in evaluation.player_fit_checks:
                references.extend(
                    f"ppe:{evidence_id}"
                    for evidence_id in fit.supporting_evidence_ids
                )
        return list(dict.fromkeys(references))

    @staticmethod
    def _truth_unavailable(
        requirement: MechanicRequirement,
        request: RecommendationRequest,
    ) -> ClaimResolution:
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

    @staticmethod
    def _refusal_reason(
        primary: CandidateEvaluation | None,
        can_recommend: bool,
    ) -> str | None:
        if primary is None:
            return (
                "Every strategy was blocked by unresolved hard mechanics."
            )
        if not can_recommend:
            return (
                "The best eligible strategy is below the minimum plan "
                "confidence. Gather player evidence or verify mechanics."
            )
        return None

    def _write(self, plan: RecommendationPlan) -> None:
        payload = plan.model_dump_json(indent=2)
        _atomic_write(self._root / "latest.json", payload)
        _atomic_write(
            self._root / "latest.md",
            recommendation_to_markdown(plan),
        )
        history = self._root / "history"
        stamp = plan.generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S")
        history_path = history / f"{stamp}_{str(plan.id)[:8]}.json"
        _atomic_write(history_path, payload)
        entries = sorted(
            history.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in entries[self._settings.maximum_history :]:
            stale.unlink(missing_ok=True)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RecommendationDisabledError(
                "The Recommendation Engine is disabled in configuration"
            )


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
        lines.extend(
            ["## Refusal / caution", "", plan.refusal_reason, ""]
        )
    for heading, evaluation in (
        ("Primary plan", plan.primary),
        ("Fallback plan", plan.fallback),
    ):
        lines.extend([f"## {heading}", ""])
        if evaluation is None:
            lines.extend(["No eligible candidate.", ""])
            continue
        lines.extend(_evaluation_markdown(evaluation))
    if plan.experiment:
        lines.extend(_experiment_markdown(plan.experiment))
    lines.extend(["## Assumptions", ""])
    assumptions = plan.assumptions or ["No additional assumptions recorded."]
    lines.extend(f"- {item}" for item in assumptions)
    lines.extend(["", "## Research tasks", ""])
    tasks = plan.research_tasks or ["No blocking research tasks."]
    lines.extend(f"- {item}" for item in tasks)
    return "\n".join(lines).rstrip() + "\n"


def _evaluation_markdown(
    evaluation: CandidateEvaluation,
) -> list[str]:
    lines = [
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
    lines.extend(
        f"{index}. {step}"
        for index, step in enumerate(evaluation.candidate.steps, start=1)
    )
    lines.append("")
    if evaluation.mechanic_checks:
        lines.extend(["Mechanics:", ""])
        for check in evaluation.mechanic_checks:
            selected = check.resolution.selected_claim
            value = f" — `{selected.value}`" if selected else ""
            lines.append(
                f"- `{check.requirement.key}`: "
                f"{check.resolution.resolution.value}{value}; "
                f"{check.resolution.reason}"
            )
        lines.append("")
    return lines


def _experiment_markdown(experiment: ExperimentDesign) -> list[str]:
    return [
        "## Experiment",
        "",
        f"**Hypothesis:** {experiment.hypothesis}",
        "",
        f"**Independent variable:** {experiment.independent_variable}",
        "",
        f"**Recommended attempts:** {experiment.recommended_sample_size}",
        "",
    ]
