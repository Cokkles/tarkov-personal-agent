from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tarkov_agent.config import PpeSettings
from tarkov_agent.domain.models import RaidRecord
from tarkov_agent.domain.ppe import (
    DimensionDefinition,
    EvidenceSource,
    ManualEvidenceRequest,
    PPEEvidence,
    ProfileAuditEntry,
    ProfileReport,
    ProfileSnapshot,
)
from tarkov_agent.domain.reviews import RaidReview, ReviewStatus
from tarkov_agent.ppe.engine import PPEEngine, ProfileBuildResult, report_to_markdown
from tarkov_agent.ppe.extractor import ReviewEvidenceExtractor
from tarkov_agent.ppe.registry import DEFAULT_DIMENSION_REGISTRY, DimensionRegistry
from tarkov_agent.storage.database import RaidRepository


class PPEDisabledError(RuntimeError):
    pass


class PPEValidationError(ValueError):
    pass


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


class PPEProfileService:
    def __init__(
        self,
        repository: RaidRepository,
        ppe_root: Path | str,
        settings: PpeSettings,
        registry: DimensionRegistry = DEFAULT_DIMENSION_REGISTRY,
    ) -> None:
        self._repository = repository
        self._root = Path(ppe_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._settings = settings
        self._registry = registry
        self._extractor = ReviewEvidenceExtractor(registry)
        self._engine = PPEEngine(registry, settings)

    def dimensions(self) -> list[DimensionDefinition]:
        return self._registry.list()

    def ingest_finalized_review(
        self,
        raid: RaidRecord,
        review: RaidReview,
    ) -> ProfileSnapshot | None:
        if not self._settings.enabled:
            return None
        if review.status is not ReviewStatus.FINALIZED:
            raise PPEValidationError("Only finalized reviews may update the player profile")
        evidence = self._extractor.extract(raid, review)
        self._repository.replace_ppe_evidence_for_raid(raid.id, evidence)
        self._write_raid_evidence(raid, review, evidence)
        build = self.rebuild(trigger=f"finalized-review:{raid.id}:v{review.version}")
        self._write_raid_profile_impact(raid, evidence, build.snapshot)
        return build.snapshot

    def add_manual_evidence(
        self,
        request: ManualEvidenceRequest,
    ) -> tuple[PPEEvidence, ProfileSnapshot]:
        self._require_enabled()
        unknown = [
            impact.dimension_key
            for impact in request.impacts
            if not self._registry.contains(impact.dimension_key)
        ]
        if unknown:
            raise PPEValidationError(f"Unknown PPE dimensions: {sorted(set(unknown))}")
        evidence_id = uuid4()
        evidence = PPEEvidence(
            id=evidence_id,
            source=EvidenceSource.MANUAL_ASSESSMENT,
            source_reference=f"manual:{request.actor}:{evidence_id}",
            observed_at=request.observed_at or datetime.now(UTC),
            reliability=request.reliability,
            context=request.context,
            impacts=request.impacts,
            notes=request.notes,
        )
        self._repository.save_ppe_evidence(evidence)
        snapshot = self.rebuild(trigger=f"manual-evidence:{evidence.id}").snapshot
        return evidence, snapshot

    def rebuild(
        self,
        *,
        trigger: str = "manual-rebuild",
        force: bool = False,
    ) -> ProfileBuildResult:
        self._require_enabled()
        evidence = self._repository.list_ppe_evidence()
        fingerprint = self._fingerprint(evidence)
        previous = self._repository.get_latest_profile_snapshot()
        unchanged = previous is not None and previous.evidence_fingerprint == fingerprint
        if unchanged and not force:
            assert previous is not None
            return ProfileBuildResult(
                snapshot=previous,
                audit=ProfileAuditEntry(
                    snapshot_id=previous.id,
                    previous_snapshot_id=previous.id,
                    trigger="no-change",
                    evidence_ids=[item.id for item in evidence],
                    changes=[],
                ),
                report=self._engine.report(previous),
            )
        version = 1 if previous is None else previous.version + 1
        result = self._engine.build(
            evidence,
            version=version,
            evidence_fingerprint=fingerprint,
            previous=previous,
            trigger=trigger,
        )
        self._repository.save_profile_snapshot(result.snapshot)
        self._repository.add_profile_audit(result.audit)
        self._write_current(result.snapshot, result.report)
        return result

    def current(self) -> ProfileSnapshot | None:
        return self._repository.get_latest_profile_snapshot()

    def current_or_build(self) -> ProfileSnapshot:
        current = self.current()
        if current is not None:
            return current
        return self.rebuild(trigger="initial-profile").snapshot

    def report(self) -> ProfileReport:
        return self._engine.report(self.current_or_build())

    def history(self, limit: int | None = None) -> list[ProfileSnapshot]:
        selected_limit = limit or self._settings.maximum_history
        return self._repository.list_profile_snapshots(limit=selected_limit)

    def audit_history(self, limit: int | None = None) -> list[ProfileAuditEntry]:
        selected_limit = limit or self._settings.maximum_history
        return self._repository.list_profile_audits(limit=selected_limit)

    def evidence(self, limit: int | None = None) -> list[PPEEvidence]:
        return self._repository.list_ppe_evidence(limit=limit)

    def evidence_for_raid(self, raid_id: str) -> list[PPEEvidence]:
        return self._repository.list_ppe_evidence_for_raid(raid_id)

    def report_markdown(self) -> str:
        return report_to_markdown(self.report())

    def _write_current(self, snapshot: ProfileSnapshot, report: ProfileReport) -> None:
        _atomic_write(
            self._root / "profile-current.json",
            snapshot.model_dump_json(indent=2),
        )
        _atomic_write(
            self._root / "profile-report.json",
            report.model_dump_json(indent=2),
        )
        _atomic_write(self._root / "profile-report.md", report_to_markdown(report))
        history_root = self._root / "history"
        _atomic_write(
            history_root / f"profile-v{snapshot.version:04d}.json",
            snapshot.model_dump_json(indent=2),
        )

    @staticmethod
    def _write_raid_evidence(
        raid: RaidRecord,
        review: RaidReview,
        evidence: list[PPEEvidence],
    ) -> None:
        if not (raid.data_root / "raid.json").exists():
            return
        payload = {
            "schema_version": 1,
            "raid_id": str(raid.id),
            "review_version": review.version,
            "generated_at": datetime.now(UTC).isoformat(),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        _atomic_write(
            raid.data_root / "analysis" / "ppe-evidence.json",
            json.dumps(payload, indent=2, default=str),
        )

    @staticmethod
    def _write_raid_profile_impact(
        raid: RaidRecord,
        evidence: list[PPEEvidence],
        snapshot: ProfileSnapshot,
    ) -> None:
        if not (raid.data_root / "raid.json").exists():
            return
        dimensions = sorted(
            {impact.dimension_key for item in evidence for impact in item.impacts}
        )
        payload = {
            "schema_version": 1,
            "raid_id": str(raid.id),
            "profile_snapshot_version": snapshot.version,
            "evidence_ids": [str(item.id) for item in evidence],
            "dimensions_touched": dimensions,
            "warning": (
                "This file records profile inputs. It does not claim that one raid "
                "establishes a trait."
            ),
        }
        _atomic_write(
            raid.data_root / "analysis" / "ppe-profile-impact.json",
            json.dumps(payload, indent=2),
        )

    @staticmethod
    def _fingerprint(evidence: list[PPEEvidence]) -> str:
        canonical = [
            item.model_dump(mode="json")
            for item in sorted(evidence, key=lambda entry: str(entry.id))
        ]
        encoded = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _require_enabled(self) -> None:
        if not self._settings.enabled:
            raise PPEDisabledError("The Personal Playstyle Engine is disabled in configuration")
