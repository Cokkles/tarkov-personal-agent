from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from tarkov_agent.domain.models import RaidRecord, RaidState, TimelineEvent
from tarkov_agent.domain.reviews import RaidReview, ReviewAuditEntry, ReviewStatus
from tarkov_agent.services.packages import RaidPackageBuilder
from tarkov_agent.storage.database import RaidRepository


class ReviewNotFoundError(LookupError):
    pass


class ReviewConflictError(RuntimeError):
    pass


def _changed_fields(before: RaidReview, after: RaidReview) -> list[str]:
    old = before.model_dump(mode="json")
    new = after.model_dump(mode="json")
    ignored = {"version", "updated_at", "finalized_at"}
    changed: list[str] = []

    def walk(prefix: str, left: object, right: object) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                if not prefix and key in ignored:
                    continue
                path = f"{prefix}.{key}" if prefix else key
                walk(path, left.get(key), right.get(key))
            return
        if left != right:
            changed.append(prefix)

    walk("", old, new)
    return changed


def review_to_markdown(raid: RaidRecord, review: RaidReview) -> str:
    def line(label: str, value: object | None) -> str:
        if value is None or value == "" or value == []:
            return ""
        return f"**{label}:** {value}\n"

    objective = review.objectives
    loadout = review.loadout
    route = review.route
    stats = review.statistics
    analysis = review.analysis_request
    date = raid.started_at.date().isoformat() if raid.started_at else raid.created_at.date().isoformat()
    map_name = review.map_name or raid.map_name or "Unknown Map"

    output = [f"# Tarkov Raid Review — {date} — {map_name}\n\n"]
    output.append("## Raid Overview\n\n")
    output.append(line("Game", raid.game.value))
    output.append(line("Map", map_name))
    output.append(line("Character", review.character_type or raid.character_type))
    output.append(line("Result", review.result or raid.result))
    output.append(line("Time of day", review.time_of_day))
    output.append(line("Group", review.group_size))
    output.append(line("Patch", review.patch))
    output.append(line("Started", raid.started_at))
    output.append(line("Ended", raid.ended_at))

    output.append("\n## Objectives\n\n")
    output.append(line("Primary", objective.primary))
    output.append(line("Primary progress", objective.primary_progress))
    output.append(line("Secondary", objective.secondary))
    output.append(line("Secondary progress", objective.secondary_progress))
    output.append(line("Priority", objective.priority))
    output.append(line("Details", objective.details))

    output.append("\n## Loadout and Weight\n\n")
    output.append(line("Weapon", loadout.weapon))
    output.append(line("Ammunition", loadout.ammunition))
    output.append(line("Optic / configuration", loadout.optic_configuration))
    output.append(line("Armor", loadout.armor))
    output.append(line("Helmet", loadout.helmet))
    output.append(line("Headset", loadout.headset))
    output.append(line("Rig", loadout.rig))
    output.append(line("Starting weight (kg)", loadout.starting_weight_kg))
    output.append(line("First-contact weight (kg)", loadout.first_contact_weight_kg))
    output.append(line("Extract weight (kg)", loadout.extract_weight_kg))
    output.append(line("Notes", loadout.notes))

    output.append("\n## Route, Information and Decisions\n\n")
    output.append(line("Spawn", route.spawn))
    output.append(line("Extract", route.extract))
    output.append(line("Planned route", route.planned_route))
    output.append(line("Actual route", route.actual_route))
    output.append(line("Information received", route.information_received))
    output.append(line("Important choices", route.important_choices))
    output.append(line("What went well", route.went_well))
    output.append(line("Problems / uncertainty", route.problems))

    output.append("\n## Encounters\n\n")
    if not review.encounters:
        output.append("_No encounters recorded._\n")
    for index, encounter in enumerate(review.encounters, start=1):
        output.append(f"### Encounter {index}\n\n")
        output.append(line("Opponent", encounter.opponent_type))
        output.append(line("Location", encounter.location))
        output.append(line("Range", encounter.range_band))
        output.append(line("Detection order", encounter.detection_order))
        output.append(line("Posture", encounter.posture))
        output.append(line("Cover", encounter.cover_state))
        output.append(line("Fired first", encounter.fired_first))
        output.append(line("Outcome", encounter.outcome))
        output.append(line("Objective progress", encounter.objective_progress))
        output.append(line("Description", encounter.description))
        output.append(line("What worked", encounter.worked))
        output.append(line("Change next time", encounter.change_next_time))
        output.append(line("Repositioned", encounter.repositioned))
        output.append(line("Re-peeked same angle", encounter.repeeked_same_angle))
        output.append(line("Could disengage", encounter.could_disengage))
        output.append(line("Video offset (ms)", encounter.video_offset_ms))
        output.append("\n")

    output.append("## End-of-Raid Statistics\n\n")
    output.append(line("Raid time", stats.raid_time))
    output.append(line("PMC kills", stats.pmc_kills))
    output.append(line("Scav kills", stats.scav_kills))
    output.append(line("Ammo used", stats.ammo_used))
    output.append(line("Hit count", stats.hit_count))
    output.append(line("Damage to body", stats.damage_to_body))
    output.append(line("Accuracy", stats.accuracy))
    output.append(line("Distance (km)", stats.distance_km))
    output.append(line("XP", stats.xp))
    output.append(line("Notable loot", stats.notable_loot))

    output.append("\n## Analysis Request\n\n")
    output.append(line("Analysis types", ", ".join(analysis.analysis_types)))
    output.append(line("Question", analysis.question))
    output.append(line("Additional analysis notes", analysis.additional_notes))
    output.append(line("Media notes", review.media_notes))
    output.append(line("Additional notes", review.additional_notes))
    return "".join(output)


class RaidReviewService:
    def __init__(self, repository: RaidRepository, packages: RaidPackageBuilder) -> None:
        self._repository = repository
        self._packages = packages

    def get_or_create(self, raid_id: UUID | str, *, actor: str = "system") -> RaidReview:
        raid = self._require_raid(raid_id)
        existing = self._repository.get_review(raid.id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        review = RaidReview(
            raid_id=raid.id,
            created_at=now,
            updated_at=now,
            map_name=raid.map_name,
            character_type=raid.character_type,
            result=raid.result,
        )
        review.objectives.primary = raid.primary_objective
        review.objectives.secondary = raid.secondary_objective
        self._repository.save_review(review)
        self._repository.add_review_audit(
            ReviewAuditEntry(
                raid_id=raid.id,
                version=review.version,
                action="created",
                actor=actor,
                changed_fields=[],
                snapshot=review,
            )
        )
        return review

    def save(
        self,
        raid_id: UUID | str,
        review: RaidReview,
        *,
        expected_version: int | None = None,
        actor: str = "local-user",
        action: str = "saved",
    ) -> RaidReview:
        raid = self._require_raid(raid_id)
        current = self.get_or_create(raid.id)
        if expected_version is not None and current.version != expected_version:
            raise ReviewConflictError(
                f"Review version changed: expected {expected_version}, current {current.version}"
            )
        now = datetime.now(UTC)
        updated = review.model_copy(
            update={
                "raid_id": raid.id,
                "version": current.version + 1,
                "created_at": current.created_at,
                "updated_at": now,
                "status": ReviewStatus.DRAFT,
                "finalized_at": None,
            }
        )
        changes = _changed_fields(current, updated)
        self._repository.save_review(updated)
        self._repository.add_review_audit(
            ReviewAuditEntry(
                raid_id=raid.id,
                version=updated.version,
                action=action,
                actor=actor,
                changed_fields=changes,
                snapshot=updated,
            )
        )
        raid = raid.model_copy(
            update={
                "map_name": updated.map_name or raid.map_name,
                "character_type": updated.character_type or raid.character_type,
                "result": updated.result or raid.result,
                "primary_objective": updated.objectives.primary or raid.primary_objective,
                "secondary_objective": updated.objectives.secondary or raid.secondary_objective,
            }
        )
        self._repository.save_raid(raid)
        if self._has_package(raid):
            self._packages.write_manifest(raid)
        return updated

    def finalize(
        self,
        raid_id: UUID | str,
        review: RaidReview,
        *,
        expected_version: int | None = None,
        actor: str = "local-user",
    ) -> RaidReview:
        saved = self.save(
            raid_id,
            review,
            expected_version=expected_version,
            actor=actor,
            action="finalize_requested",
        )
        raid = self._require_raid(raid_id)
        now = datetime.now(UTC)
        finalized = saved.model_copy(
            update={
                "version": saved.version + 1,
                "status": ReviewStatus.FINALIZED,
                "updated_at": now,
                "finalized_at": now,
            }
        )
        self._repository.save_review(finalized)
        self._repository.add_review_audit(
            ReviewAuditEntry(
                raid_id=raid.id,
                version=finalized.version,
                action="finalized",
                actor=actor,
                changed_fields=["status", "finalized_at"],
                snapshot=finalized,
            )
        )
        if raid.state in {RaidState.ENDING, RaidState.REVIEW_PENDING}:
            raid = raid.model_copy(update={"state": RaidState.COMPLETE})
            self._repository.save_raid(raid)
            event = TimelineEvent(
                raid_id=raid.id,
                occurred_at=now,
                raid_offset_ms=self._offset_ms(raid, now),
                event_type="review_finalized",
                label="Post-raid review finalized",
                source="user",
                payload={"review_version": finalized.version},
            )
            self._repository.add_timeline_event(event)
            if self._has_package(raid):
                self._packages.append_timeline_event(raid, event)
                self._packages.write_manifest(raid)
        self.write_exports(raid, finalized)
        return finalized

    def write_exports(self, raid: RaidRecord, review: RaidReview) -> dict[str, Path]:
        if not self._has_package(raid):
            raise ReviewNotFoundError("Raid package is unavailable; exports cannot be written")
        analysis_root = raid.data_root / "analysis"
        analysis_root.mkdir(parents=True, exist_ok=True)
        json_path = analysis_root / "review.json"
        markdown_path = analysis_root / "review.md"
        json_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
        markdown_path.write_text(review_to_markdown(raid, review), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path}

    def markdown(self, raid_id: UUID | str) -> str:
        raid = self._require_raid(raid_id)
        review = self.get_or_create(raid.id)
        return review_to_markdown(raid, review)

    def audit_history(self, raid_id: UUID | str) -> list[ReviewAuditEntry]:
        self._require_raid(raid_id)
        return self._repository.list_review_audits(raid_id)

    def _require_raid(self, raid_id: UUID | str) -> RaidRecord:
        raid = self._repository.get_raid(raid_id)
        if raid is None:
            raise ReviewNotFoundError(f"Raid not found: {raid_id}")
        return raid

    @staticmethod
    def _offset_ms(raid: RaidRecord, timestamp: datetime) -> int | None:
        if raid.started_at is None:
            return None
        return max(0, int((timestamp - raid.started_at).total_seconds() * 1000))

    @staticmethod
    def _has_package(raid: RaidRecord) -> bool:
        return (raid.data_root / "raid.json").exists()
