from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from tarkov_agent.config import SourceTruthSettings
from tarkov_agent.domain.source_truth import (
    CitationRecord,
    ClaimRecord,
    ClaimStatus,
    GameScope,
    MechanicsQuery,
    PatchWindow,
    QueryResolution,
    SourceAuthority,
    SourceRecord,
)
from tarkov_agent.services.source_truth import SourceTruthService
from tarkov_agent.storage.source_truth import SourceTruthRepository


def _service(tmp_path: Path) -> SourceTruthService:
    repository = SourceTruthRepository(tmp_path / "truth.sqlite3")
    repository.initialize()
    service = SourceTruthService(
        repository,
        tmp_path / "exports",
        SourceTruthSettings(),
    )
    service.initialize()
    return service


def test_seeded_scav_claim_is_verified_and_citation_preserved(tmp_path: Path) -> None:
    service = _service(tmp_path)

    result = service.query(
        MechanicsQuery(
            key="scav.extracted_loot_transfers",
            game=GameScope.TARKOV,
        )
    )

    assert result.resolution is QueryResolution.VERIFIED
    assert result.can_recommend is True
    assert result.selected_claim is not None
    assert result.selected_claim.value == "true"
    assert result.citations
    assert result.citations[0].locator == "Beware of Scavs"

    markdown = service.export_markdown()
    assert "scav.extracted_loot_transfers" in markdown
    assert "https://escapefromtarkov.fandom.com/wiki/Escape_from_Tarkov" in markdown
    assert "Beware of Scavs" in markdown


def test_patch_window_uses_inclusive_start_and_exclusive_end() -> None:
    window = PatchWindow(introduced_in="1.0.2", removed_in="1.1.0")

    assert window.applies_to("1.0.2") is True
    assert window.applies_to("1.0.9") is True
    assert window.applies_to("1.1.0") is False
    assert window.applies_to("0.16.9") is False


def test_conflicting_applicable_claims_block_recommendation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = next(item for item in service.sources() if item.key == "wiki.official")
    now = datetime.now(UTC)

    for value in ("10", "12"):
        service.upsert_claim(
            ClaimRecord(
                id=uuid4(),
                key="test.conflicting_value",
                statement="Synthetic conflicting mechanic for validation.",
                value=value,
                game_scope=GameScope.TARKOV,
                confidence=0.95,
                last_reviewed_at=now,
                citations=[
                    CitationRecord(
                        source_id=source.id,
                        url=source.base_url,
                        title="Synthetic source section",
                        locator=f"Value {value}",
                        accessed_at=now,
                    )
                ],
            )
        )

    result = service.query(
        MechanicsQuery(key="test.conflicting_value", game=GameScope.TARKOV)
    )

    assert result.resolution is QueryResolution.CONFLICTED
    assert result.can_recommend is False
    assert result.conflict_ids
    assert all(
        claim.status is ClaimStatus.DISPUTED
        for claim in service.claims(key="test.conflicting_value")
    )


def test_low_authority_claim_remains_unresolved(tmp_path: Path) -> None:
    service = _service(tmp_path)
    now = datetime.now(UTC)
    source = service.upsert_source(
        SourceRecord(
            key="community.synthetic",
            name="Synthetic discussion",
            base_url="https://example.invalid/discussion",
            authority=SourceAuthority.COMMUNITY_DISCUSSION,
            game_scope=GameScope.TARKOV,
            reliability=0.40,
            last_reviewed_at=now,
        )
    )
    claim = service.upsert_claim(
        ClaimRecord(
            key="test.weak_claim",
            statement="A low-authority source says this mechanic is true.",
            value="true",
            game_scope=GameScope.TARKOV,
            confidence=0.80,
            last_reviewed_at=now,
            citations=[
                CitationRecord(
                    source_id=source.id,
                    url=source.base_url,
                    title="Discussion post",
                    accessed_at=now,
                )
            ],
        )
    )

    result = service.query(MechanicsQuery(key=claim.key, game=GameScope.TARKOV))

    assert claim.status is ClaimStatus.DRAFT
    assert result.resolution is QueryResolution.UNRESOLVED
    assert result.can_recommend is False


def test_overdue_claim_enters_review_queue_and_becomes_stale(tmp_path: Path) -> None:
    service = _service(tmp_path)
    claim = next(
        item
        for item in service.claims()
        if item.key == "scav.main_stash_isolated"
    )
    old = datetime.now(UTC) - timedelta(days=60)
    stale = service.upsert_claim(
        claim.model_copy(
            update={
                "last_reviewed_at": old,
                "next_review_at": old + timedelta(days=30),
            }
        )
    )

    tasks = service.review_queue()
    result = service.query(MechanicsQuery(key=stale.key, game=GameScope.TARKOV))

    assert stale.status is ClaimStatus.STALE
    assert any(task.entity_id == stale.id for task in tasks)
    assert result.resolution is QueryResolution.STALE
    assert result.can_recommend is False
