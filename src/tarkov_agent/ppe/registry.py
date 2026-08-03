from __future__ import annotations

from collections.abc import Iterable

from tarkov_agent.domain.ppe import DimensionDefinition


_DIMENSIONS: tuple[DimensionDefinition, ...] = (
    DimensionDefinition(
        key="prepared_engagement_effectiveness",
        label="Prepared engagement effectiveness",
        category="combat",
        description=(
            "Effectiveness when the player has time to interpret information, establish an angle, "
            "and begin the engagement on deliberate terms."
        ),
        positive_label="converts prepared advantages reliably",
        negative_label="struggles to convert prepared advantages",
        context_fields=("map_name", "range_band", "detection_order"),
        adaptation_guidance=(
            "Create engagements through information, timing, and pre-positioning instead of "
            "accepting equal-information reaction duels."
        ),
        training_guidance=(
            "Review prepared fights for aim placement, shot timing, and whether the first advantage "
            "was converted before the opponent could reset."
        ),
    ),
    DimensionDefinition(
        key="reactive_close_range_effectiveness",
        label="Reactive close-range effectiveness",
        category="combat",
        description=(
            "Effectiveness in short-range encounters where both sides are aware and decisions must "
            "be made with little preparation time."
        ),
        positive_label="stable in mutual close-range reactions",
        negative_label="vulnerable in mutual close-range reactions",
        context_fields=("range_band", "detection_order", "movement_state"),
        adaptation_guidance=(
            "Reduce mutually detected close-range entries by using standoff distance, utility, "
            "off-angles, and disengagement routes."
        ),
        training_guidance=(
            "Use low-cost Arena or offline drills that isolate crosshair placement, target pickup, "
            "and the first two seconds of mutual-contact fights."
        ),
    ),
    DimensionDefinition(
        key="first_shot_execution",
        label="First-shot execution",
        category="mechanics",
        description="Ability to make the first meaningful shot convert an earned opening.",
        positive_label="converts opening shots efficiently",
        negative_label="loses value from earned first-shot opportunities",
        context_fields=("range_band", "detection_order", "loadout_family"),
        adaptation_guidance=(
            "Favor stable firing positions and weapons that preserve the first-shot advantage."
        ),
        training_guidance=(
            "Review first-shot placement separately from the rest of the spray and practice deliberate "
            "single-target acquisition."
        ),
    ),
    DimensionDefinition(
        key="target_tracking",
        label="Target tracking",
        category="mechanics",
        description="Ability to maintain accurate aim on a moving or partially obscured target.",
        positive_label="maintains target contact during movement",
        negative_label="loses target contact during movement",
        context_fields=("range_band", "movement_state", "loadout_family"),
        adaptation_guidance="Prefer shorter exposure windows and controllable engagement distances.",
        training_guidance=(
            "Use repeatable moving-target drills and compare tracking performance by range and optic."
        ),
    ),
    DimensionDefinition(
        key="recoil_recovery",
        label="Recoil recovery",
        category="mechanics",
        description="Ability to recover sight picture and continue accurate fire after initial recoil.",
        positive_label="recovers sight picture consistently",
        negative_label="loses control after the opening shots",
        context_fields=("range_band", "loadout_family", "position_state"),
        adaptation_guidance="Use fire cadence, stance, and weapon configurations that reduce recovery demand.",
        training_guidance="Compare burst lengths and recovery time with the same weapon across controlled drills.",
    ),
    DimensionDefinition(
        key="angle_discipline",
        label="Angle discipline",
        category="positioning",
        description="Quality of peeks, exposure management, and avoidance of predictable repeat angles.",
        positive_label="changes exposure intelligently",
        negative_label="repeats predictable or overexposed angles",
        context_fields=("map_name", "position_state", "range_band"),
        adaptation_guidance="Pre-plan a second angle or exit before taking the first exposure.",
        training_guidance="Tag every same-angle re-peek and review whether new information justified it.",
    ),
    DimensionDefinition(
        key="cover_utilization",
        label="Cover utilization",
        category="positioning",
        description="Use of hard cover, concealment, and exposure timing during engagements.",
        positive_label="uses cover to control exposure",
        negative_label="fights without sufficient cover control",
        context_fields=("map_name", "position_state", "range_band"),
        adaptation_guidance="Route through positions that provide hard-cover transitions and fallback options.",
        training_guidance="Review body exposure and time spent visible during each marked engagement.",
    ),
    DimensionDefinition(
        key="repositioning",
        label="Repositioning",
        category="positioning",
        description="Ability to change location after contact to preserve uncertainty and regain advantage.",
        positive_label="repositions before becoming predictable",
        negative_label="remains static after information is exchanged",
        context_fields=("map_name", "range_band", "position_state"),
        adaptation_guidance="Build routes with nearby secondary angles and protected lateral movement.",
        training_guidance="Set a deliberate rule to evaluate repositioning after each exchange, then review compliance.",
    ),
    DimensionDefinition(
        key="route_prediction",
        label="Route prediction",
        category="information",
        description="Ability to infer where players are likely to move from sound, timing, objectives, and spawns.",
        positive_label="predicts likely movement routes",
        negative_label="misreads or fails to exploit likely routes",
        context_fields=("map_name", "objective_priority", "opponent_type"),
        adaptation_guidance="Use predictive interception rather than direct pursuit whenever route information is available.",
        training_guidance="Before moving, record the predicted destination and compare it with the observed outcome.",
    ),
    DimensionDefinition(
        key="audio_interpretation",
        label="Audio interpretation",
        category="information",
        description="Ability to convert sound cues into useful estimates of position, direction, level, and intent.",
        positive_label="translates audio into useful action",
        negative_label="misreads or underuses audio information",
        context_fields=("map_name", "position_state", "opponent_type"),
        adaptation_guidance="Pause at acoustically readable positions and avoid committing on ambiguous vertical audio alone.",
        training_guidance="Mark uncertain sound cues and compare the interpretation with later visual confirmation.",
    ),
    DimensionDefinition(
        key="map_timing",
        label="Map timing",
        category="information",
        description="Use of spawn, travel, objective, and extraction timing to anticipate contact windows.",
        positive_label="uses timing to anticipate traffic",
        negative_label="arrives without accounting for likely traffic windows",
        context_fields=("map_name", "objective_priority", "character_type"),
        adaptation_guidance="Choose routes based on expected traffic windows, not only shortest distance.",
        training_guidance="Compare predicted and actual contact times at recurring landmarks.",
    ),
    DimensionDefinition(
        key="fight_selection",
        label="Fight selection",
        category="decision_making",
        description="Ability to choose engagements that fit the raid objective, information state, and available advantage.",
        positive_label="selects fights that support the raid plan",
        negative_label="accepts fights that conflict with the raid plan",
        context_fields=("map_name", "objective_priority", "group_size"),
        adaptation_guidance="Define a contact budget and only escalate when the fight supports the current raid objective.",
        training_guidance="Classify each optional fight as justified, avoidable, or strategically harmful after the raid.",
    ),
    DimensionDefinition(
        key="disengagement",
        label="Disengagement",
        category="decision_making",
        description="Ability to exit or reset an unfavorable fight before losses become irreversible.",
        positive_label="exits unfavorable fights in time",
        negative_label="remains committed after the advantage is lost",
        context_fields=("range_band", "position_state", "objective_priority"),
        adaptation_guidance="Preserve a retreat route and define a clear trigger for breaking contact.",
        training_guidance="Practice disengagement decisions in low-stakes raids and review the trigger timing.",
    ),
    DimensionDefinition(
        key="objective_discipline",
        label="Objective discipline",
        category="decision_making",
        description="Consistency in protecting the primary raid objective from distractions and unnecessary risk.",
        positive_label="protects the primary objective",
        negative_label="abandons or endangers the primary objective",
        context_fields=("map_name", "objective_priority", "character_type"),
        adaptation_guidance="Make the primary objective the explicit tie-breaker when deciding whether to pursue contact.",
        training_guidance="Track objective abandonment and identify the decision that displaced the original plan.",
    ),
    DimensionDefinition(
        key="risk_management",
        label="Risk management",
        category="decision_making",
        description="Calibration of exposure, equipment risk, loot value, and survival probability.",
        positive_label="matches risk to expected value",
        negative_label="takes risk without sufficient expected value",
        context_fields=("map_name", "objective_priority", "loadout_family"),
        adaptation_guidance="Use loadout cost, current loot, and objective progress to tighten or loosen the risk budget.",
        training_guidance="Review high-cost decisions separately from mechanical execution to identify risk-calibration errors.",
    ),
    DimensionDefinition(
        key="pressure_stability",
        label="Pressure stability",
        category="mental",
        description="Decision and execution stability when surprised, injured, carrying value, or under time pressure.",
        positive_label="maintains decision quality under pressure",
        negative_label="decision quality degrades under pressure",
        context_fields=("range_band", "objective_priority", "position_state"),
        adaptation_guidance="Reduce simultaneous demands by simplifying routes, healing plans, and fallback decisions.",
        training_guidance="Use controlled pressure drills and compare choices before and after surprise contact.",
    ),
    DimensionDefinition(
        key="gear_risk_stability",
        label="Gear-risk stability",
        category="mental",
        description="Degree to which loadout value changes confidence, aggression, or decision quality.",
        positive_label="plays consistently across gear values",
        negative_label="decision quality changes sharply with gear value",
        context_fields=("loadout_family", "objective_priority", "map_name"),
        adaptation_guidance="Use repeatable budget tiers so decision rules remain familiar across raids.",
        training_guidance="Compare identical objectives across low-, medium-, and high-cost loadouts.",
    ),
    DimensionDefinition(
        key="information_patience",
        label="Information patience",
        category="information",
        description="Ability to wait for enough information before committing without becoming inert.",
        positive_label="waits for useful confirmation without stalling",
        negative_label="commits too early or waits past the useful window",
        context_fields=("map_name", "detection_order", "objective_priority"),
        adaptation_guidance="Use a time-limited observation window followed by a predetermined action choice.",
        training_guidance="Record how long information was held before action and whether the delay improved the decision.",
    ),
    DimensionDefinition(
        key="contact_conversion",
        label="Contact conversion",
        category="decision_making",
        description="Ability to turn partial contact information into a controlled engagement opportunity.",
        positive_label="converts information into controlled pressure",
        negative_label="gathers information without creating a usable opportunity",
        context_fields=("map_name", "detection_order", "range_band"),
        adaptation_guidance="Use parallel tracking or interception to create a prepared contact window.",
        training_guidance="Set one deliberate contact-conversion attempt per suitable raid and review the decision chain.",
    ),
    DimensionDefinition(
        key="interception_prediction",
        label="Interception prediction",
        category="information",
        description="Ability to predict and occupy a future crossing point rather than following directly behind contact.",
        positive_label="creates effective predictive interceptions",
        negative_label="pursues contact without gaining positional leverage",
        context_fields=("map_name", "opponent_type", "objective_priority"),
        adaptation_guidance="Move toward likely destinations and crossing points instead of the last known position.",
        training_guidance="Write the predicted route and interception point before moving, then compare with the video.",
    ),
    DimensionDefinition(
        key="execution_decisiveness",
        label="Execution decisiveness",
        category="decision_making",
        description="Ability to act promptly once sufficient advantage and information have been established.",
        positive_label="acts decisively when the window is valid",
        negative_label="hesitates until the advantage disappears",
        context_fields=("detection_order", "range_band", "objective_priority"),
        adaptation_guidance="Define the exact evidence threshold that changes observation into action.",
        training_guidance="Review missed windows and distinguish justified patience from avoidable hesitation.",
    ),
    DimensionDefinition(
        key="overcommitment_control",
        label="Overcommitment control",
        category="decision_making",
        description="Ability to stop escalation when the original advantage, information, or objective alignment is gone.",
        positive_label="limits escalation after conditions change",
        negative_label="continues escalation after the advantage is gone",
        context_fields=("range_band", "objective_priority", "position_state"),
        adaptation_guidance="Use explicit stop conditions for chase distance, exposure count, and lost information.",
        training_guidance="Mark the first moment a fight became unfavorable and compare it with the actual disengagement time.",
    ),
)


class DimensionRegistry:
    def __init__(self, dimensions: Iterable[DimensionDefinition] = _DIMENSIONS) -> None:
        self._dimensions = {definition.key: definition for definition in dimensions}
        if len(self._dimensions) != len(tuple(dimensions)):
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
