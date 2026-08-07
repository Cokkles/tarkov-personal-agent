from __future__ import annotations

import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from tarkov_agent.domain.evidence import (
    EvidenceBundleFile,
    EvidenceBundleManifest,
    EvidenceBundleProfile,
    EvidenceBundleRequest,
    EvidenceBundleResult,
    EvidenceCandidate,
)
from tarkov_agent.domain.media import ClipRequest, MediaClip, RaidMediaIndex
from tarkov_agent.domain.models import EvidenceKind, MarkerType, RaidRecord, TimelineEvent
from tarkov_agent.services.media import (
    MediaDisabledError,
    MediaFinalizationError,
    MediaService,
    MediaToolError,
)
from tarkov_agent.storage.database import RaidRepository


class EvidenceIntelligenceDisabledError(RuntimeError):
    pass


class EvidenceBundleError(RuntimeError):
    pass


_MARKER_PRIORITIES: dict[str, tuple[float, str]] = {
    MarkerType.FIGHT_STARTED.value: (1.00, "Combat engagement has the highest review value"),
    MarkerType.MISTAKE.value: (0.96, "Player explicitly marked a possible mistake"),
    MarkerType.PLAYER_SEEN.value: (0.92, "Visual contact can establish detection and positioning context"),
    MarkerType.GOOD_DECISION.value: (0.88, "Player explicitly marked a decision worth reinforcing"),
    MarkerType.PMC_HEARD.value: (0.84, "Audio contact can establish awareness before visual contact"),
    MarkerType.ROUTE_CHANGED.value: (0.68, "Route changes capture tactical or objective decisions"),
    MarkerType.IMPORTANT_LOOT.value: (0.54, "Important loot can explain route and objective decisions"),
}

_LABEL_TO_MARKER: dict[str, str] = {
    "fight started": MarkerType.FIGHT_STARTED.value,
    "mistake": MarkerType.MISTAKE.value,
    "player seen": MarkerType.PLAYER_SEEN.value,
    "good decision": MarkerType.GOOD_DECISION.value,
    "pmc heard": MarkerType.PMC_HEARD.value,
    "route changed": MarkerType.ROUTE_CHANGED.value,
    "important loot": MarkerType.IMPORTANT_LOOT.value,
}


class EvidenceIntelligenceService:
    """Reduce a raid into a compact, provenance-preserving AI evidence package.

    The original recording remains local and is represented by metadata only. The
    generated bundle contains structured raid context and only selected derivative
    media, keeping upload size bounded while preserving links back to source evidence.
    """

    def __init__(
        self,
        repository: RaidRepository,
        media: MediaService,
        *,
        enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._media = media
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def preview(
        self,
        raid_id: UUID | str,
        request: EvidenceBundleRequest | None = None,
    ) -> EvidenceBundleManifest:
        self._require_enabled()
        raid = self._require_raid(raid_id)
        self._require_package(raid)
        resolved = request or EvidenceBundleRequest()
        return self._prepare_manifest(raid, resolved, allow_generation=False)

    def build(
        self,
        raid_id: UUID | str,
        request: EvidenceBundleRequest | None = None,
    ) -> EvidenceBundleResult:
        self._require_enabled()
        raid = self._require_raid(raid_id)
        self._require_package(raid)
        resolved = request or EvidenceBundleRequest()
        manifest = self._prepare_manifest(raid, resolved, allow_generation=True)

        analysis_root = raid.data_root / "analysis"
        analysis_root.mkdir(parents=True, exist_ok=True)
        manifest_path = analysis_root / "evidence-bundle.json"
        summary_path = analysis_root / "evidence-bundle.md"
        summary = self._summary(raid, manifest)
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        summary_path.write_text(summary, encoding="utf-8")

        exports_root = raid.data_root / "evidence" / "exports"
        exports_root.mkdir(parents=True, exist_ok=True)
        archive_path = exports_root / "chatgpt-evidence.zip"
        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for item in manifest.files:
                archive.write(item.source_path, item.archive_path)
            archive.writestr("bundle-manifest.json", manifest.model_dump_json(indent=2))
            archive.writestr("README.md", summary)

        return EvidenceBundleResult(manifest=manifest, archive_path=archive_path)

    def latest_archive(self, raid_id: UUID | str) -> Path | None:
        raid = self._require_raid(raid_id)
        path = raid.data_root / "evidence" / "exports" / "chatgpt-evidence.zip"
        return path if path.is_file() else None

    def _prepare_manifest(
        self,
        raid: RaidRecord,
        request: EvidenceBundleRequest,
        *,
        allow_generation: bool,
    ) -> EvidenceBundleManifest:
        profile = request.profile
        max_clips = self._max_clips(profile, request.max_clips)
        max_total_bytes = self._max_total_bytes(profile, request.max_total_bytes)
        generate_missing = bool(request.generate_missing_clips) and allow_generation
        warnings: list[str] = []

        media_index = self._media.index_for_raid(raid.id)
        candidates = self._candidate_events(raid, media_index, max_clips=max_clips)
        if generate_missing:
            self._generate_missing_clips(raid, candidates, warnings)
            media_index = self._media.index_for_raid(raid.id)
            candidates = self._candidate_events(raid, media_index, max_clips=max_clips)

        files = self._select_files(
            raid,
            media_index,
            candidates,
            profile=profile,
            max_total_bytes=max_total_bytes,
            warnings=warnings,
        )
        payload_bytes = sum(item.size_bytes for item in files)

        if not media_index.recordings:
            warnings.append("No indexed source recording is available for this raid")
        else:
            warnings.append(
                "Raw source recordings are intentionally excluded; recording hashes and paths "
                "remain in the manifest for provenance"
            )
        if profile is not EvidenceBundleProfile.METADATA:
            missing = [item for item in candidates if item.selected and item.clip_path is None]
            if missing:
                warnings.append(
                    f"{len(missing)} selected event(s) do not yet have derivative clips"
                )

        return EvidenceBundleManifest(
            raid_id=raid.id,
            generated_at=datetime.now(UTC),
            profile=profile,
            raw_recordings_included=False,
            recording_references=media_index.recordings,
            candidates=candidates,
            files=files,
            payload_bytes=payload_bytes,
            warnings=self._dedupe(warnings),
        )

    def _candidate_events(
        self,
        raid: RaidRecord,
        media_index: RaidMediaIndex,
        *,
        max_clips: int,
    ) -> list[EvidenceCandidate]:
        clips_by_event: dict[UUID, MediaClip] = {
            clip.timeline_event_id: clip
            for clip in media_index.clips
            if clip.timeline_event_id is not None and clip.available and clip.path.is_file()
        }
        candidates: list[EvidenceCandidate] = []
        for event in self._repository.list_timeline_events(raid.id):
            if event.event_type != "marker":
                continue
            marker_type = self._marker_type(event)
            base, rationale = _MARKER_PRIORITIES.get(
                marker_type or "",
                (0.45, "Manual marker is potentially useful review context"),
            )
            priority = min(1.0, base * (0.75 + (0.25 * event.confidence)))
            clip = clips_by_event.get(event.id)
            category = event.payload.get("category")
            candidates.append(
                EvidenceCandidate(
                    timeline_event_id=event.id,
                    event_type=event.event_type,
                    label=event.label,
                    source=event.source,
                    category=str(category) if category is not None else None,
                    marker_type=marker_type,
                    raid_offset_ms=event.raid_offset_ms,
                    confidence=event.confidence,
                    priority=priority,
                    rationale=rationale,
                    clip_id=clip.id if clip is not None else None,
                    clip_path=clip.path if clip is not None else None,
                )
            )

        candidates.sort(
            key=lambda item: (
                -item.priority,
                item.raid_offset_ms if item.raid_offset_ms is not None else 2**63,
            )
        )
        selected_ids = {
            item.timeline_event_id
            for item in candidates[:max_clips]
            if item.raid_offset_ms is not None
        }
        return [
            item.model_copy(update={"selected": item.timeline_event_id in selected_ids})
            for item in candidates
        ]

    def _generate_missing_clips(
        self,
        raid: RaidRecord,
        candidates: list[EvidenceCandidate],
        warnings: list[str],
    ) -> None:
        for candidate in candidates:
            if not candidate.selected or candidate.clip_path is not None:
                continue
            if candidate.raid_offset_ms is None:
                warnings.append(f"Cannot clip '{candidate.label}': marker has no raid offset")
                continue
            try:
                self._media.extract_clip(
                    raid.id,
                    ClipRequest(timeline_event_id=candidate.timeline_event_id),
                )
            except (MediaDisabledError, MediaFinalizationError, MediaToolError) as exc:
                warnings.append(f"Could not generate clip for '{candidate.label}': {exc}")

    def _select_files(
        self,
        raid: RaidRecord,
        media_index: RaidMediaIndex,
        candidates: list[EvidenceCandidate],
        *,
        profile: EvidenceBundleProfile,
        max_total_bytes: int,
        warnings: list[str],
    ) -> list[EvidenceBundleFile]:
        selected: list[EvidenceBundleFile] = []
        used_paths: set[str] = set()
        total = 0

        def add(path: Path, archive_path: str, role: str, *, required: bool = False) -> bool:
            nonlocal total
            if not path.is_file():
                return False
            size = path.stat().st_size
            normalized = archive_path.replace("\\", "/")
            if normalized in used_paths:
                return False
            if not required and total + size > max_total_bytes:
                warnings.append(
                    f"Omitted {normalized}: evidence bundle size limit would be exceeded"
                )
                return False
            selected.append(
                EvidenceBundleFile(
                    archive_path=normalized,
                    source_path=path,
                    role=role,
                    size_bytes=size,
                    sha256=self._sha256(path),
                )
            )
            used_paths.add(normalized)
            total += size
            return True

        add(raid.data_root / "raid.json", "raid.json", "raid_manifest", required=True)
        add(raid.data_root / "timeline.jsonl", "timeline.jsonl", "timeline", required=True)

        analysis_root = raid.data_root / "analysis"
        if analysis_root.is_dir():
            for path in sorted(analysis_root.iterdir()):
                if not path.is_file():
                    continue
                if path.name.startswith("evidence-bundle"):
                    continue
                if path.suffix.lower() not in {".json", ".jsonl", ".md", ".txt"}:
                    continue
                add(path, f"analysis/{path.name}", "analysis", required=True)

        if profile is EvidenceBundleProfile.METADATA:
            return selected

        for evidence in raid.evidence:
            if evidence.kind is not EvidenceKind.SCREENSHOT or not evidence.available:
                continue
            path = evidence.path
            add(path, f"screenshots/{path.name}", "screenshot")

        selected_clip_ids = {
            candidate.clip_id
            for candidate in candidates
            if candidate.selected and candidate.clip_id is not None
        }
        for clip in media_index.clips:
            if clip.id not in selected_clip_ids or not clip.available:
                continue
            add(clip.path, f"clips/{clip.path.name}", "selected_clip")

        return selected

    @staticmethod
    def _marker_type(event: TimelineEvent) -> str | None:
        raw = event.payload.get("marker_type")
        if raw is not None and str(raw).strip():
            return str(raw).strip()
        return _LABEL_TO_MARKER.get(event.label.strip().lower())

    @staticmethod
    def _max_clips(profile: EvidenceBundleProfile, requested: int | None) -> int:
        if requested is not None:
            return requested
        if profile is EvidenceBundleProfile.METADATA:
            return 0
        if profile is EvidenceBundleProfile.DEEP:
            return 12
        return 6

    @staticmethod
    def _max_total_bytes(profile: EvidenceBundleProfile, requested: int | None) -> int:
        if requested is not None:
            return requested
        if profile is EvidenceBundleProfile.METADATA:
            return 25_000_000
        if profile is EvidenceBundleProfile.DEEP:
            return 400_000_000
        return 150_000_000

    @staticmethod
    def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _summary(raid: RaidRecord, manifest: EvidenceBundleManifest) -> str:
        lines = [
            "# Tarkov Personal Agent — ChatGPT Evidence Bundle\n\n",
            f"- Raid: `{raid.id}`\n",
            f"- Map: {raid.map_name or 'Unknown'}\n",
            f"- Character: {raid.character_type or 'Unknown'}\n",
            f"- Result: {raid.result or 'Unknown'}\n",
            f"- Profile: `{manifest.profile.value}`\n",
            f"- Payload size before ZIP compression: {manifest.payload_bytes:,} bytes\n",
            "- Full source recordings included: **No**\n\n",
            "The original recording remains local. Recording paths, hashes, probe metadata, "
            "and selected derivative evidence are preserved in `bundle-manifest.json`.\n\n",
            "## Selected review moments\n\n",
        ]
        chosen = [item for item in manifest.candidates if item.selected]
        if not chosen:
            lines.append("_No marker-centered media was selected for this profile._\n")
        for item in chosen:
            offset = (
                f"{item.raid_offset_ms / 1000.0:.1f}s"
                if item.raid_offset_ms is not None
                else "unknown offset"
            )
            clip = "clip included" if item.clip_path is not None else "clip not available"
            lines.append(
                f"- **{item.label}** — {offset} — priority {item.priority:.2f} — {clip}\n"
            )
        if manifest.warnings:
            lines.append("\n## Warnings / limitations\n\n")
            for warning in manifest.warnings:
                lines.append(f"- {warning}\n")
        return "".join(lines)

    def _require_raid(self, raid_id: UUID | str) -> RaidRecord:
        raid = self._repository.get_raid(raid_id)
        if raid is None:
            raise LookupError(f"Raid not found: {raid_id}")
        return raid

    @staticmethod
    def _require_package(raid: RaidRecord) -> None:
        if not (raid.data_root / "raid.json").is_file():
            raise EvidenceBundleError("Raid package is unavailable; evidence bundle cannot be built")

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise EvidenceIntelligenceDisabledError(
                "Evidence Intelligence is disabled in configuration"
            )
