from __future__ import annotations

from collections.abc import Iterable

from tarkov_agent.domain.ppe import DimensionDefinition


def _definition(
    key: str,
    label: str,
    category: str,
    description: str,
    positive_label: str,
    negative_label: str,
    context_fields: tuple[str, ...],
    adaptation_guidance: str,
    training_guidance: str,
) -> DimensionDefinition:
    return DimensionDefinition(
        key=key,
        label=label,
        category=category,
        description=description,
        positive_label=positive_label,
        negative_label=negative_label,
        context_fields=context_fields,
        adaptation_guidance=adaptation_guidance,
        training_guidance=training_guidance,
    )


_DIMENSIONS: tuple[DimensionDefinition, ...] = (
    _definition(
        "prepared_engagement_effectiveness",
        "Prepared engagement effectiveness",
        "combat",
        "Effectiveness after interpreting information and establishing a deliberate opening.",
        "converts prepared advantages reliably",
        "struggles to convert prepared advantages",
        ("map_name", "range_band", "detection_order"),
        "Create fights through information, timing, and pre-positioning rather than equal reactions.",
        "Review whether earned openings were converted before the opponent could reset.",
    ),
    _definition(
        "reactive_close_range_effectiveness",
        "Reactive close-range effectiveness",
        "combat",
        "Effectiveness in short-range encounters with little preparation time.",
        "is stable in mutual close-range reactions",
        "is vulnerable in mutual close-range reactions",
        ("range_band", "detection_order", "movement_state"),
        "Reduce mutual close-range entries with distance, utility, off-angles, and exit routes.",
        "Use low-cost drills that isolate target pickup and the first two seconds of contact.",
    ),
    _definition(
        "first_shot_execution",
        "First-shot execution",
        "mechanics",
        "Ability to make the first meaningful shot convert an earned opening.",
        "converts opening shots efficiently",
        "loses value from earned first-shot opportunities",
        ("range_band", "detection_order", "loadout_family"),
        "Favor stable firing positions and weapons that preserve the opening advantage.",
        "Review first-shot placement separately from later recoil and follow-up fire.",
    ),
    _definition(
        "target_tracking",
        "Target tracking",
        "mechanics",
        "Ability to maintain accurate aim on a moving or partially obscured target.",
        "maintains target contact during movement",
        "loses target contact during movement",
        ("range_band", "movement_state", "loadout_family"),
        "Prefer shorter exposure windows and controllable engagement distances.",
        "Use repeatable moving-target drills and compare results by range and optic.",
    ),
    _definition(
        "recoil_recovery",
        "Recoil recovery",
        "mechanics",
        "Ability to recover sight picture and continue accurate fire after initial recoil.",
        "recovers sight picture consistently",
        "loses control after the opening shots",
        ("range_band", "loadout_family", "position_state"),
        "Use cadence, stance, and weapon configurations that reduce recovery demand.",
        "Compare burst lengths and recovery time with the same weapon in controlled drills.",
    ),
    _definition(
        "angle_discipline",
        "Angle discipline",
        "positioning",
        "Quality of peeks, exposure management, and avoidance of predictable repeat angles.",
        "changes exposure intelligently",
        "repeats predictable or overexposed angles",
        ("map_name", "position_state", "range_band"),
        "Pre-plan a second angle or exit before taking the first exposure.",
        "Tag same-angle re-peeks and review whether new information justified each one.",
    ),
    _definition(
        "cover_utilization",
        "Cover utilization",
        "positioning",
        "Use of hard cover, concealment, and exposure timing during engagements.",
        "uses cover to control exposure",
        "fights without sufficient cover control",
        ("map_name", "position_state", "range_band"),
        "Route through positions with hard-cover transitions and fallback options.",
        "Review body exposure and time visible during each marked engagement.",
    ),
    _definition(
        "repositioning",
        "Repositioning",
        "positioning",
        "Ability to move after contact to preserve uncertainty and regain advantage.",
        "repositions before becoming predictable",
        "remains static after information is exchanged",
        ("map_name", "range_band", "position_state"),
        "Build routes with nearby secondary angles and protected lateral movement.",
        "Evaluate repositioning after each exchange and review whether the choice was timely.",
    ),
    _definition(
        "route_prediction",
        "Route prediction",
        "information",
        "Ability to infer likely movement from sound, timing, objectives, and spawns.",
        "predicts likely movement routes",
        "misreads or fails to exploit likely routes",
        ("map_name", "objective_priority", "opponent_type"),
        "Use predictive interception rather than direct pursuit when route data is available.",
        "Record the predicted destination before moving and compare it with the outcome.",
    ),
    _definition(
        "audio_interpretation",
        "Audio interpretation",
        "information",
        "Ability to turn sound cues into useful estimates of position, level, and intent.",
        "translates audio into useful action",
        "misreads or underuses audio information",
        ("map_name", "position_state", "opponent_type"),
        "Pause at readable positions and avoid committing on ambiguous vertical audio alone.",
        "Mark uncertain sounds and compare the interpretation with later confirmation.",
    ),
    _definition(
        "map_timing",
        "Map timing",
        "information",
        "Use of spawn, travel, objective, and extraction timing to anticipate contact.",
        "uses timing to anticipate traffic",
        "arrives without accounting for likely traffic windows",
        ("map_name", "objective_priority", "character_type"),
        "Choose routes using expected traffic windows, not only shortest distance.",
        "Compare predicted and actual contact times at recurring landmarks.",
    ),
    _definition(
        "fight_selection",
        "Fight selection",
        "decision_making",
        "Ability to choose fights that fit the objective, information, and available advantage.",
        "selects fights that support the raid plan",
        "accepts fights that conflict with the raid plan",
        ("map_name", "objective_priority", "group_size"),
        "Define a contact budget and escalate only when the fight supports the raid objective.",
        "Classify optional fights as justified, avoidable, or strategically harmful.",
    ),
    _definition(
        "disengagement",
        "Disengagement",
        "decision_making",
        "Ability to exit or reset an unfavorable fight before losses become irreversible.",
        "exits unfavorable fights in time",
        "remains committed after the advantage is lost",
        ("range_band", "position_state", "objective_priority"),
        "Preserve a retreat route and define a clear trigger for breaking contact.",
        "Practice disengagement in low-stakes raids and review the trigger timing.",
    ),
    _definition(
        "objective_discipline",
        "Objective discipline",
        "decision_making",
        "Consistency in protecting the primary objective from distraction and excess risk.",
        "protects the primary objective",
        "abandons or endangers the primary objective",
        ("map_name", "objective_priority", "character_type"),
        "Use the primary objective as the tie-breaker when deciding whether to pursue contact.",
        "Track objective abandonment and identify which decision displaced the plan.",
    ),
    _definition(
        "risk_management",
        "Risk management",
        "decision_making",
        "Calibration of exposure, equipment risk, loot value, and survival probability.",
        "matches risk to expected value",
        "takes risk without sufficient expected value",
        ("map_name", "objective_priority", "loadout_family"),
        "Use loadout cost, loot, and objective progress to adjust the risk budget.",
        "Review high-cost decisions separately from mechanical execution.",
    ),
    _definition(
        "pressure_stability",
        "Pressure stability",
        "mental",
        "Decision and execution stability when surprised, injured, valuable, or rushed.",
        "maintains decision quality under pressure",
        "shows degraded decision quality under pressure",
        ("range_band", "objective_priority", "position_state"),
        "Reduce simultaneous demands by simplifying routes, healing, and fallback choices.",
        "Use controlled pressure drills and compare choices before and after surprise contact.",
    ),
    _definition(
        "gear_risk_stability",
        "Gear-risk stability",
        "mental",
        "Degree to which loadout value changes confidence, aggression, or decision quality.",
        "plays consistently across gear values",
        "changes decision quality sharply with gear value",
        ("loadout_family", "objective_priority", "map_name"),
        "Use repeatable budget tiers so decision rules remain familiar across raids.",
        "Compare the same objective across low-, medium-, and high-cost loadouts.",
    ),
    _definition(
        "information_patience",
        "Information patience",
        "information",
        "Ability to wait for enough information without becoming inactive.",
        "waits for useful confirmation without stalling",
        "commits too early or waits past the useful window",
        ("map_name", "detection_order", "objective_priority"),
        "Use a time-limited observation window followed by a predetermined action.",
        "Record observation time and whether the delay improved the decision.",
    ),
    _definition(
        "contact_conversion",
        "Contact conversion",
        "decision_making",
        "Ability to turn partial contact information into a controlled opportunity.",
        "converts information into controlled pressure",
        "gathers information without creating a usable opportunity",
        ("map_name", "detection_order", "range_band"),
        "Use parallel tracking or interception to create a prepared contact window.",
        "Attempt one deliberate contact conversion in suitable low-risk raids.",
    ),
    _definition(
        "interception_prediction",
        "Interception prediction",
        "information",
        "Ability to occupy a future crossing point instead of following last known contact.",
        "creates effective predictive interceptions",
        "pursues contact without gaining positional leverage",
        ("map_name", "opponent_type", "objective_priority"),
        "Move toward likely destinations and crossing points, not the last known position.",
        "Write the predicted route and interception point before moving.",
    ),
    _definition(
        "execution_decisiveness",
        "Execution decisiveness",
        "decision_making",
        "Ability to act promptly once sufficient information and advantage exist.",
        "acts decisively when the window is valid",
        "hesitates until the advantage disappears",
        ("detection_order", "range_band", "objective_priority"),
        "Define the evidence threshold that changes observation into action.",
        "Review missed windows and separate justified patience from hesitation.",
    ),
    _definition(
        "overcommitment_control",
        "Overcommitment control",
        "decision_making",
        "Ability to stop escalation after advantage, information, or alignment is gone.",
        "limits escalation after conditions change",
        "continues escalation after the advantage is gone",
        ("range_band", "objective_priority", "position_state"),
        "Use stop conditions for chase distance, exposure count, and lost information.",
        "Mark when a fight became unfavorable and compare it with disengagement time.",
    ),
)


class DimensionRegistry:
    def __init__(self, dimensions: Iterable[DimensionDefinition] = _DIMENSIONS) -> None:
        definitions = tuple(dimensions)
        self._dimensions = {definition.key: definition for definition in definitions}
        if len(self._dimensions) != len(definitions):
            raise ValueError("PPE dimension keys must be unique")

    def get(self, key: str) -> DimensionDefinition:
        try:
            return self._dimensions[key]
        except KeyError as exc:
            raise KeyError(f"Unknown PPE dimension: {key}") from exc

    def contains(self, key: str) -> bool:
        return key in self._dimensions

    def list(self) -> list[DimensionDefinition]:
        return sorted(self._dimensions.values(), key=lambda item: (item.category, item.label))


DEFAULT_DIMENSION_REGISTRY = DimensionRegistry()
