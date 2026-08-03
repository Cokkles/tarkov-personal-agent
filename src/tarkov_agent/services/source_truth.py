from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import fmean
from uuid import NAMESPACE_URL, UUID, uuid5

from tarkov_agent.config import SourceTruthSettings
from tarkov_agent.domain.source_truth import (
    CitationRecord,
    CitationRole,
    ClaimKind,
    ClaimRecord,
    ClaimResolution,
    ClaimStatus,
    ConflictRecord,
    ConflictStatus,
    GameScope,
    MechanicsQuery,
    QueryResolution,
    ReviewEntityType,
    ReviewSeverity,
    ReviewTask,
    SourceAuthority,
    SourceRecord,
    SourceStatus,
    SourceTruthBundle,
)
from tarkov_agent.storage.source_truth import SourceTruthRepository

_AUTHORITY_SCORES: dict[SourceAuthority, float] = {
    SourceAuthority.OFFICIAL_PUBLISHER: 1.00,
    SourceAuthority.OFFICIAL_WIKI: 0.86,
    SourceAuthority.VERIFIED_DATA: 0.82,
    SourceAuthority.PRIMARY_TEST: 0.78,
    SourceAuthority.COMMUNITY_REFERENCE: 0.62,
    SourceAuthority.COMMUNITY_DISCUSSION: 0.40,
}


class SourceTruthDisabledError(RuntimeError):
    pass


class SourceTruthValidationError(ValueError):
    pass


def _stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"tarkov-personal-agent:{kind}:{key}")


def _game_scopes_overlap(left: GameScope, right: GameScope) -> bool:
    return left is GameScope.BOTH or right is GameScope.BOTH or left is right


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SourceTruthService:
    def __init__(
        self,
        repository: SourceTruthRepository,
        output_root: Path,
        settings: SourceTruthSettings,
    ) -> None:
        self._repository = repository
        self._output_root = output_root
        self._settings = settings
        self._output_root.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def initialize(self) -> None:
        if not self.enabled:
            return
        if self._settings.seed_default_sources:
            self._seed_defaults()
        self.rebuild_conflicts(write_exports=False)
        self._refresh_claim_statuses()
        self.write_exports()

    def sources(self, *, limit: int = 1000) -> list[SourceRecord]:
        return self._repository.list_sources(limit=limit)

    def claims(
        self,
        *,
        key: str | None = None,
        status: ClaimStatus | None = None,
        limit: int = 5000,
    ) -> list[ClaimRecord]:
        return self._repository.list_claims(key=key, status=status, limit=limit)

    def conflicts(
        self,
        *,
        status: ConflictStatus | None = None,
        limit: int = 5000,
    ) -> list[ConflictRecord]:
        return self._repository.list_conflicts(status=status, limit=limit)

    def source_rank(self, source: SourceRecord, *, as_of: datetime | None = None) -> float:
        current = _aware(as_of or datetime.now(UTC))
        if source.status is not SourceStatus.ACTIVE:
            return 0.0
        authority = _AUTHORITY_SCORES[source.authority]
        score = (authority * 0.75) + (source.reliability * 0.25)
        if source.last_reviewed_at is None:
            score *= 0.80
        if source.next_review_at is not None and current > _aware(source.next_review_at):
            overdue_days = (current - _aware(source.next_review_at)).total_seconds() / 86400.0
            interval = max(float(source.review_interval_days), 1.0)
            score *= max(0.40, 1.0 - (overdue_days / (interval * 2.0)))
        return max(0.0, min(1.0, score))

    def upsert_source(self, source: SourceRecord) -> SourceRecord:
        self._require_enabled()
        existing_key = self._repository.get_source_by_key(source.key)
        if existing_key is not None and existing_key.id != source.id:
            raise SourceTruthValidationError(f"Source key already exists: {source.key}")
        existing = self._repository.get_source(source.id)
        now = datetime.now(UTC)
        reviewed_at = _aware(source.last_reviewed_at or now)
        next_review = source.next_review_at or (
            reviewed_at + timedelta(days=source.review_interval_days)
        )
        stored = source.model_copy(
            update={
                "created_at": existing.created_at if existing is not None else source.created_at,
                "updated_at": now,
                "last_reviewed_at": reviewed_at,
                "next_review_at": next_review,
            }
        )
        self._repository.save_source(stored)
        self._refresh_claim_statuses()
        self.write_exports()
        return stored

    def upsert_claim(self, claim: ClaimRecord) -> ClaimRecord:
        self._require_enabled()
        self._validate_citations(claim)
        existing = self._repository.get_claim(claim.id)
        now = datetime.now(UTC)
        reviewed_at = _aware(claim.last_reviewed_at or now)
        next_review = claim.next_review_at or (
            reviewed_at + timedelta(days=claim.review_interval_days)
        )
        initial_status = (
            ClaimStatus.REJECTED if claim.status is ClaimStatus.REJECTED else ClaimStatus.DRAFT
        )
        stored = claim.model_copy(
            update={
                "created_at": existing.created_at if existing is not None else claim.created_at,
                "updated_at": now,
                "last_reviewed_at": reviewed_at,
                "next_review_at": next_review,
                "status": initial_status,
            }
        )
        self._repository.save_claim(stored)
        self.rebuild_conflicts(write_exports=False)
        self._refresh_claim_statuses()
        refreshed = self._repository.get_claim(stored.id)
        if refreshed is None:
            raise RuntimeError("Claim disappeared after persistence")
        self.write_exports()
        return refreshed

    def mark_source_reviewed(
        self,
        source_id: UUID | str,
        *,
        reviewed_at: datetime | None = None,
    ) -> SourceRecord:
        source = self._repository.get_source(source_id)
        if source is None:
            raise LookupError(f"Source not found: {source_id}")
        when = _aware(reviewed_at or datetime.now(UTC))
        return self.upsert_source(
            source.model_copy(
                update={
                    "last_reviewed_at": when,
                    "next_review_at": when + timedelta(days=source.review_interval_days),
                }
            )
        )

    def mark_claim_reviewed(
        self,
        claim_id: UUID | str,
        *,
        reviewed_at: datetime | None = None,
    ) -> ClaimRecord:
        claim = self._repository.get_claim(claim_id)
        if claim is None:
            raise LookupError(f"Claim not found: {claim_id}")
        when = _aware(reviewed_at or datetime.now(UTC))
        return self.upsert_claim(
            claim.model_copy(
                update={
                    "last_reviewed_at": when,
                    "next_review_at": when + timedelta(days=claim.review_interval_days),
                }
            )
        )

    def rebuild_conflicts(self, *, write_exports: bool = True) -> list[ConflictRecord]:
        self._require_enabled()
        grouped: dict[str, list[ClaimRecord]] = defaultdict(list)
        for claim in self._repository.list_claims(limit=10000):
            if claim.status is not ClaimStatus.REJECTED:
                grouped[claim.key].append(claim)
        detected: list[ConflictRecord] = []
        now = datetime.now(UTC)
        for claim_key, claims in grouped.items():
            for index, left in enumerate(claims):
                for right in claims[index + 1 :]:
                    if not _game_scopes_overlap(left.game_scope, right.game_scope):
                        continue
                    if not left.patch_window.overlaps(right.patch_window):
                        continue
                    if left.normalized_value == right.normalized_value:
                        continue
                    pair = sorted((str(left.id), str(right.id)))
                    conflict_key = f"{claim_key}:{pair[0]}:{pair[1]}"
                    detected.append(
                        ConflictRecord(
                            id=_stable_id("conflict", conflict_key),
                            claim_key=claim_key,
                            claim_ids=[left.id, right.id],
                            values={str(left.id): left.value, str(right.id): right.value},
                            patch_description=(
                                f"{left.patch_window.label()} overlaps "
                                f"{right.patch_window.label()}"
                            ),
                            detected_at=now,
                        )
                    )
        self._repository.replace_conflicts(detected)
        if write_exports:
            self._refresh_claim_statuses()
            self.write_exports()
        return detected

    def query(self, request: MechanicsQuery) -> ClaimResolution:
        self._require_enabled()
        candidates = [
            claim
            for claim in self._repository.list_claims(key=request.key, limit=1000)
            if claim.game_scope.includes(request.game)
        ]
        if not candidates:
            return ClaimResolution(
                query=request,
                resolution=QueryResolution.NO_MATCH,
                can_recommend=False,
                reason="No claim exists for this key and game scope.",
            )

        applicable = candidates
        if request.patch_version is not None:
            applicable = [
                claim
                for claim in candidates
                if claim.patch_window.applies_to(request.patch_version)
            ]
            if not applicable:
                return ClaimResolution(
                    query=request,
                    resolution=QueryResolution.NO_MATCH,
                    can_recommend=False,
                    reason="Claims exist, but none applies to the requested patch.",
                    candidate_claims=candidates,
                )
        elif self._requires_patch(candidates):
            return ClaimResolution(
                query=request,
                resolution=QueryResolution.UNRESOLVED,
                can_recommend=False,
                reason=(
                    "Multiple patch-specific values exist. Supply a patch version before using "
                    "this mechanic in a recommendation."
                ),
                candidate_claims=candidates,
            )

        open_conflicts = self._conflicts_for_claims(applicable)
        if open_conflicts:
            return ClaimResolution(
                query=request,
                resolution=QueryResolution.CONFLICTED,
                can_recommend=False,
                reason="Applicable claims conflict and require review.",
                candidate_claims=applicable,
                conflict_ids=[item.id for item in open_conflicts],
            )

        verified = [claim for claim in applicable if claim.status is ClaimStatus.VERIFIED]
        stale = [claim for claim in applicable if claim.status is ClaimStatus.STALE]
        if not verified and stale and not request.include_stale:
            return ClaimResolution(
                query=request,
                resolution=QueryResolution.STALE,
                can_recommend=False,
                reason="Only stale claims are available; review them before recommendation use.",
                candidate_claims=applicable,
            )
        if not verified and request.include_stale:
            verified = stale
        if not verified:
            return ClaimResolution(
                query=request,
                resolution=QueryResolution.UNRESOLVED,
                can_recommend=False,
                reason="No applicable claim currently meets verification requirements.",
                candidate_claims=applicable,
            )

        values = {claim.normalized_value for claim in verified}
        if len(values) > 1:
            return ClaimResolution(
                query=request,
                resolution=QueryResolution.CONFLICTED,
                can_recommend=False,
                reason="Verified candidates disagree even though no conflict record was present.",
                candidate_claims=verified,
            )

        selected = max(
            verified,
            key=lambda claim: (claim.verification_score, claim.confidence),
        )
        citations = sorted(
            selected.citations,
            key=lambda citation: (
                citation.role is not CitationRole.SUPPORTS,
                citation.title.casefold(),
            ),
        )
        resolution = (
            QueryResolution.STALE
            if selected.status is ClaimStatus.STALE
            else QueryResolution.VERIFIED
        )
        return ClaimResolution(
            query=request,
            resolution=resolution,
            can_recommend=selected.status is ClaimStatus.VERIFIED,
            reason=(
                "Verified claim with applicable patch scope and no unresolved conflict."
                if selected.status is ClaimStatus.VERIFIED
                else "Stale claim returned only because include_stale was requested."
            ),
            confidence=selected.verification_score,
            selected_claim=selected,
            candidate_claims=verified,
            citations=citations,
        )

    def review_queue(self, *, as_of: datetime | None = None) -> list[ReviewTask]:
        current = _aware(as_of or datetime.now(UTC))
        tasks: list[ReviewTask] = []
        for source in self._repository.list_sources(limit=10000):
            if (
                source.status is SourceStatus.ACTIVE
                and source.next_review_at is not None
                and _aware(source.next_review_at) <= current
            ):
                tasks.append(
                    ReviewTask(
                        entity_type=ReviewEntityType.SOURCE,
                        entity_id=source.id,
                        label=source.name,
                        due_at=_aware(source.next_review_at),
                        severity=ReviewSeverity.IMPORTANT,
                        reason=(
                            "Source authority, availability, and freshness are due for "
                            "review."
                        ),
                    )
                )
        for claim in self._repository.list_claims(limit=10000):
            if (
                claim.status is not ClaimStatus.REJECTED
                and claim.next_review_at is not None
                and _aware(claim.next_review_at) <= current
            ):
                tasks.append(
                    ReviewTask(
                        entity_type=ReviewEntityType.CLAIM,
                        entity_id=claim.id,
                        label=claim.key,
                        due_at=_aware(claim.next_review_at),
                        severity=(
                            ReviewSeverity.BLOCKING
                            if claim.status is ClaimStatus.STALE
                            else ReviewSeverity.ROUTINE
                        ),
                        reason="Claim citations and patch applicability are due for review.",
                    )
                )
        for conflict in self._repository.list_conflicts(
            status=ConflictStatus.OPEN,
            limit=10000,
        ):
            tasks.append(
                ReviewTask(
                    entity_type=ReviewEntityType.CONFLICT,
                    entity_id=conflict.id,
                    label=conflict.claim_key,
                    due_at=conflict.detected_at,
                    severity=ReviewSeverity.BLOCKING,
                    reason="Conflicting values prevent recommendation use.",
                )
            )
        return sorted(tasks, key=lambda task: (task.due_at, task.entity_type.value, task.label))

    def bundle(self) -> SourceTruthBundle:
        return SourceTruthBundle(
            sources=self._repository.list_sources(limit=10000),
            claims=self._repository.list_claims(limit=10000),
            conflicts=self._repository.list_conflicts(limit=10000),
            review_queue=self.review_queue(),
        )

    def export_json(self) -> str:
        return self.bundle().model_dump_json(indent=2)

    def export_markdown(self) -> str:
        bundle = self.bundle()
        lines = [
            "# Tarkov Source of Truth",
            "",
            f"Generated: {bundle.generated_at.isoformat()}",
            "",
            "## Sources",
            "",
            "| Key | Authority | Status | Rank | Next review |",
            "|---|---|---|---:|---|",
        ]
        for source in bundle.sources:
            due = (
                source.next_review_at.date().isoformat()
                if source.next_review_at
                else "unscheduled"
            )
            lines.append(
                f"| `{source.key}` | {source.authority.value} | {source.status.value} | "
                f"{self.source_rank(source):.3f} | {due} |"
            )
        lines.extend(["", "## Claims", ""])
        footnotes: list[str] = []
        footnote_index = 1
        sources = {source.id: source for source in bundle.sources}
        for claim in bundle.claims:
            references: list[str] = []
            for citation in claim.citations:
                marker = f"truth-{footnote_index}"
                footnote_index += 1
                references.append(f"[^{marker}]")
                source = sources.get(citation.source_id)
                source_name = source.name if source is not None else "Unknown source"
                locator = f"; {citation.locator}" if citation.locator else ""
                revision = (
                    f"; revision {citation.source_revision}"
                    if citation.source_revision
                    else ""
                )
                footnotes.append(
                    f"[^{marker}]: {source_name}. {citation.title}. {citation.url}"
                    f"{locator}{revision}; accessed {citation.accessed_at.date().isoformat()}."
                )
            citation_text = " ".join(references)
            lines.extend(
                [
                    f"### `{claim.key}`",
                    "",
                    f"- **Status:** {claim.status.value}",
                    f"- **Game:** {claim.game_scope.value}",
                    f"- **Patch:** {claim.patch_window.label()}",
                    f"- **Verification score:** {claim.verification_score:.3f}",
                    f"- **Statement:** {claim.statement} {citation_text}".rstrip(),
                    f"- **Canonical value:** `{claim.value}`",
                    "",
                ]
            )
        lines.extend(["## Conflicts", ""])
        if bundle.conflicts:
            for conflict in bundle.conflicts:
                lines.append(
                    f"- `{conflict.claim_key}` — {conflict.status.value}: "
                    f"{conflict.patch_description}"
                )
        else:
            lines.append("No conflicts detected.")
        if footnotes:
            lines.extend(["", "## Citations", "", *footnotes])
        return "\n".join(lines).rstrip() + "\n"

    def write_exports(self) -> None:
        if not self.enabled:
            return
        self._output_root.mkdir(parents=True, exist_ok=True)
        (self._output_root / "source-truth.json").write_text(
            self.export_json(),
            encoding="utf-8",
        )
        (self._output_root / "source-truth.md").write_text(
            self.export_markdown(),
            encoding="utf-8",
        )

    def status(self) -> dict[str, object]:
        sources = self._repository.list_sources(limit=10000)
        claims = self._repository.list_claims(limit=10000)
        conflicts = self._repository.list_conflicts(status=ConflictStatus.OPEN, limit=10000)
        return {
            "enabled": self.enabled,
            "source_count": len(sources),
            "claim_count": len(claims),
            "verified_claim_count": len(
                [claim for claim in claims if claim.status is ClaimStatus.VERIFIED]
            ),
            "open_conflict_count": len(conflicts),
            "review_queue_count": len(self.review_queue()),
            "output_root": str(self._output_root),
        }

    def _claim_score(
        self,
        claim: ClaimRecord,
        sources: dict[UUID, SourceRecord],
        *,
        as_of: datetime,
    ) -> tuple[float, int]:
        supporting_scores: list[float] = []
        opposing_scores: list[float] = []
        for citation in claim.citations:
            source = sources.get(citation.source_id)
            if source is None:
                continue
            citation_score = self.source_rank(source, as_of=as_of)
            age_days = max(
                0.0,
                (as_of - _aware(citation.accessed_at)).total_seconds() / 86400.0,
            )
            freshness = max(
                0.55,
                1.0 - (age_days / max(claim.review_interval_days * 3.0, 1.0)),
            )
            weighted = citation_score * freshness
            if citation.role is CitationRole.SUPPORTS:
                supporting_scores.append(weighted)
            elif citation.role is CitationRole.OPPOSES:
                opposing_scores.append(weighted)
        if not supporting_scores:
            return 0.0, 0
        opposition = max(opposing_scores, default=0.0)
        opposition_penalty = max(0.10, 1.0 - (opposition * 0.75))
        score = fmean(supporting_scores) * claim.confidence * opposition_penalty
        return max(0.0, min(1.0, score)), len(supporting_scores)

    def _refresh_claim_statuses(self) -> None:
        now = datetime.now(UTC)
        sources = {source.id: source for source in self._repository.list_sources(limit=10000)}
        conflicted_ids = {
            claim_id
            for conflict in self._repository.list_conflicts(
                status=ConflictStatus.OPEN,
                limit=10000,
            )
            for claim_id in conflict.claim_ids
        }
        for claim in self._repository.list_claims(limit=10000):
            score, supporting_count = self._claim_score(claim, sources, as_of=now)
            if claim.status is ClaimStatus.REJECTED:
                status = ClaimStatus.REJECTED
            elif claim.id in conflicted_ids:
                status = ClaimStatus.DISPUTED
            elif self._is_stale(claim, now):
                status = ClaimStatus.STALE
            elif (
                supporting_count >= self._settings.minimum_supporting_citations
                and score >= self._settings.minimum_verification_score
            ):
                status = ClaimStatus.VERIFIED
            else:
                status = ClaimStatus.DRAFT
            if status is not claim.status or abs(score - claim.verification_score) >= 0.0001:
                self._repository.save_claim(
                    claim.model_copy(
                        update={
                            "status": status,
                            "verification_score": score,
                            "updated_at": now,
                        }
                    )
                )

    def _is_stale(self, claim: ClaimRecord, now: datetime) -> bool:
        if claim.next_review_at is None:
            return False
        stale_after = _aware(claim.next_review_at) + timedelta(
            days=self._settings.stale_grace_days
        )
        return now > stale_after

    def _validate_citations(self, claim: ClaimRecord) -> None:
        for citation in claim.citations:
            source = self._repository.get_source(citation.source_id)
            if source is None:
                raise SourceTruthValidationError(
                    f"Citation references an unknown source: {citation.source_id}"
                )
            if source.status is not SourceStatus.ACTIVE:
                raise SourceTruthValidationError(
                    f"Citation source is not active: {source.key}"
                )
            if not _game_scopes_overlap(source.game_scope, claim.game_scope):
                raise SourceTruthValidationError(
                    f"Citation source {source.key} does not cover {claim.game_scope.value}"
                )

    def _conflicts_for_claims(self, claims: list[ClaimRecord]) -> list[ConflictRecord]:
        claim_ids = {claim.id for claim in claims}
        return [
            conflict
            for conflict in self._repository.list_conflicts(
                status=ConflictStatus.OPEN,
                limit=10000,
            )
            if claim_ids.intersection(conflict.claim_ids)
        ]

    @staticmethod
    def _requires_patch(claims: list[ClaimRecord]) -> bool:
        values = {claim.normalized_value for claim in claims}
        windows = {claim.patch_window.label() for claim in claims}
        return len(values) > 1 and len(windows) > 1

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise SourceTruthDisabledError("Source of Truth is disabled")

    def _seed_defaults(self) -> None:
        now = datetime.now(UTC)
        source_specs = [
            SourceRecord(
                id=_stable_id("source", "bsg-eft"),
                key="bsg.escapefromtarkov",
                name="Battlestate Games — Escape from Tarkov",
                base_url="https://www.escapefromtarkov.com/",
                authority=SourceAuthority.OFFICIAL_PUBLISHER,
                game_scope=GameScope.TARKOV,
                topics={"patches", "announcements", "support", "game"},
                reliability=0.98,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.source_review_interval_days),
                review_interval_days=self._settings.source_review_interval_days,
            ),
            SourceRecord(
                id=_stable_id("source", "bsg-arena"),
                key="bsg.arena",
                name="Battlestate Games — Escape from Tarkov: Arena",
                base_url="https://arena.tarkov.com/",
                authority=SourceAuthority.OFFICIAL_PUBLISHER,
                game_scope=GameScope.ARENA,
                topics={"patches", "announcements", "game"},
                reliability=0.98,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.source_review_interval_days),
                review_interval_days=self._settings.source_review_interval_days,
            ),
            SourceRecord(
                id=_stable_id("source", "official-wiki"),
                key="wiki.official",
                name="The Official Escape from Tarkov Wiki",
                base_url=(
                    "https://escapefromtarkov.fandom.com/wiki/"
                    "Escape_from_Tarkov_Wiki"
                ),
                authority=SourceAuthority.OFFICIAL_WIKI,
                game_scope=GameScope.BOTH,
                topics={"items", "quests", "maps", "mechanics", "patches"},
                reliability=0.92,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.source_review_interval_days),
                review_interval_days=self._settings.source_review_interval_days,
                notes=(
                    "Officially branded wiki maintained by community editors. Preserve page and "
                    "section locators and review volatile values against publisher notes or tests."
                ),
            ),
            SourceRecord(
                id=_stable_id("source", "tarkov-dev"),
                key="data.tarkov-dev",
                name="Tarkov.dev GraphQL API",
                base_url="https://api.tarkov.dev/",
                authority=SourceAuthority.VERIFIED_DATA,
                game_scope=GameScope.TARKOV,
                topics={"items", "ammo", "armor", "quests", "traders", "economy"},
                reliability=0.90,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.source_review_interval_days),
                review_interval_days=self._settings.source_review_interval_days,
                notes=(
                    "Community-operated structured data source; volatile values require "
                    "freshness checks."
                ),
            ),
        ]
        for source in source_specs:
            if self._repository.get_source_by_key(source.key) is None:
                self._repository.save_source(source)

        wiki = self._repository.get_source_by_key("wiki.official")
        if wiki is None:
            raise RuntimeError("Default wiki source was not created")
        scav_page = "https://escapefromtarkov.fandom.com/wiki/Escape_from_Tarkov"
        claim_specs = [
            ClaimRecord(
                id=_stable_id("claim", "scav.main-stash-isolated"),
                key="scav.main_stash_isolated",
                statement=(
                    "Playing as a Scav does not risk equipment stored in the PMC's main inventory."
                ),
                value="true",
                kind=ClaimKind.MECHANIC,
                game_scope=GameScope.TARKOV,
                topics={"scav", "inventory", "risk"},
                confidence=0.95,
                review_interval_days=self._settings.claim_review_interval_days,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.claim_review_interval_days),
                citations=[
                    CitationRecord(
                        id=_stable_id("citation", "scav-main-stash-isolated"),
                        source_id=wiki.id,
                        url=scav_page,
                        title="Escape from Tarkov",
                        locator="Beware of Scavs",
                        accessed_at=now,
                    )
                ],
            ),
            ClaimRecord(
                id=_stable_id("claim", "scav.extracted-loot-transfers"),
                key="scav.extracted_loot_transfers",
                statement=(
                    "Loot successfully extracted during a Scav raid can be transferred to the "
                    "player's main stash."
                ),
                value="true",
                kind=ClaimKind.MECHANIC,
                game_scope=GameScope.TARKOV,
                topics={"scav", "loot", "inventory", "extract"},
                confidence=0.95,
                review_interval_days=self._settings.claim_review_interval_days,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.claim_review_interval_days),
                citations=[
                    CitationRecord(
                        id=_stable_id("citation", "scav-extracted-loot-transfers"),
                        source_id=wiki.id,
                        url=scav_page,
                        title="Escape from Tarkov",
                        locator="Beware of Scavs",
                        accessed_at=now,
                    )
                ],
            ),
            ClaimRecord(
                id=_stable_id("claim", "scav.random-loadout"),
                key="scav.random_loadout",
                statement=(
                    "A Scav raid begins with a random gear loadout, weapons, and health state."
                ),
                value="random loadout and health state",
                kind=ClaimKind.MECHANIC,
                game_scope=GameScope.TARKOV,
                topics={"scav", "loadout"},
                confidence=0.95,
                review_interval_days=self._settings.claim_review_interval_days,
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=self._settings.claim_review_interval_days),
                citations=[
                    CitationRecord(
                        id=_stable_id("citation", "scav-random-loadout"),
                        source_id=wiki.id,
                        url=scav_page,
                        title="Escape from Tarkov",
                        locator="Beware of Scavs",
                        accessed_at=now,
                    )
                ],
            ),
        ]
        for claim in claim_specs:
            if not self._repository.list_claims(key=claim.key, limit=1):
                self._repository.save_claim(claim)
