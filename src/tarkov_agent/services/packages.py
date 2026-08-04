from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC
from pathlib import Path

from tarkov_agent.domain.models import (
    EvidenceKind,
    EvidenceReference,
    RaidRecord,
    TimelineEvent,
)


class RaidPackageError(RuntimeError):
    pass


def _safe_component(value: str | None, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-._")
    return cleaned[:60] or fallback


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


class RaidPackageBuilder:
    """Creates durable per-raid folders and writes manifests atomically."""

    def __init__(self, raids_root: Path | str) -> None:
        self._raids_root = Path(raids_root).expanduser().resolve()
        self._raids_root.mkdir(parents=True, exist_ok=True)

    def create(self, raid: RaidRecord) -> RaidRecord:
        timestamp = raid.created_at.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
        map_component = _safe_component(raid.map_name, "unknown-map")
        package_name = f"{timestamp}_{map_component}_{str(raid.id)[:8]}"
        package_root = self._raids_root / package_name
        if package_root.exists():
            raise RaidPackageError(f"Raid package already exists: {package_root}")

        for relative in (
            "evidence/logs",
            "evidence/recordings",
            "evidence/screenshots",
            "evidence/clips",
            "evidence/exports",
            "analysis",
        ):
            (package_root / relative).mkdir(parents=True, exist_ok=True)

        updated = raid.model_copy(update={"data_root": package_root})
        self.write_manifest(updated)
        (package_root / "timeline.jsonl").touch()
        return updated

    def write_manifest(self, raid: RaidRecord) -> Path:
        raid.data_root.mkdir(parents=True, exist_ok=True)
        manifest_path = raid.data_root / "raid.json"
        _atomic_write(manifest_path, raid.model_dump_json(indent=2))
        return manifest_path

    def append_timeline_event(
        self,
        raid: RaidRecord,
        event: TimelineEvent,
    ) -> Path:
        if event.raid_id != raid.id:
            raise RaidPackageError(
                "Timeline event does not belong to the supplied raid"
            )
        timeline_path = raid.data_root / "timeline.jsonl"
        with timeline_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")
        return timeline_path

    def attach_file(
        self,
        raid: RaidRecord,
        source: Path | str,
        kind: EvidenceKind,
        *,
        copy_into_package: bool,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> tuple[RaidRecord, EvidenceReference]:
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise RaidPackageError(f"Evidence file not found: {source_path}")

        destination = source_path
        if copy_into_package:
            folder_by_kind = {
                EvidenceKind.LOG: "logs",
                EvidenceKind.RECORDING: "recordings",
                EvidenceKind.SCREENSHOT: "screenshots",
                EvidenceKind.CLIP: "clips",
                EvidenceKind.EXPORT: "exports",
            }
            subfolder = folder_by_kind.get(kind, "exports")
            destination_dir = raid.data_root / "evidence" / subfolder
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / source_path.name
            counter = 1
            while destination.exists():
                destination = (
                    destination_dir
                    / f"{source_path.stem}-{counter}{source_path.suffix}"
                )
                counter += 1
            shutil.copy2(source_path, destination)

        evidence = EvidenceReference(
            kind=kind,
            path=destination,
            sha256=_sha256(destination),
            size_bytes=destination.stat().st_size,
            metadata=metadata or {},
        )
        updated = raid.model_copy(
            update={"evidence": [*raid.evidence, evidence]}
        )
        self.write_manifest(updated)
        return updated, evidence

    def write_summary(
        self,
        raid: RaidRecord,
        summary: dict[str, object],
    ) -> Path:
        path = raid.data_root / "analysis" / "summary.json"
        _atomic_write(path, json.dumps(summary, indent=2, default=str))
        return path
