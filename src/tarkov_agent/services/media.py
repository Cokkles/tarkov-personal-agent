from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from tarkov_agent.config import MediaSettings
from tarkov_agent.domain.media import (
    ClipRequest,
    MediaClip,
    MediaNavigationPoint,
    MediaSource,
    ProbeStatus,
    RaidMediaIndex,
    RecordingAsset,
)
from tarkov_agent.domain.models import EvidenceKind, RaidRecord
from tarkov_agent.services.packages import RaidPackageBuilder, RaidPackageError
from tarkov_agent.storage.database import RaidRepository


class MediaDisabledError(RuntimeError):
    pass


class MediaPathError(ValueError):
    pass


class MediaFinalizationError(RuntimeError):
    pass


class MediaToolError(RuntimeError):
    pass


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _safe_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned[:80] or fallback


class MediaService:
    def __init__(
        self,
        repository: RaidRepository,
        packages: RaidPackageBuilder,
        media_root: Path | str,
        settings: MediaSettings,
        allowed_roots: list[Path],
    ) -> None:
        self._repository = repository
        self._packages = packages
        self._root = Path(media_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._settings = settings
        self._allowed_roots = [
            root.expanduser().resolve() for root in allowed_roots
        ]

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def index_recording(
        self,
        raid_id: UUID | str,
        source: Path | str,
        *,
        media_source: MediaSource = MediaSource.MANUAL,
        copy_into_package: bool | None = None,
    ) -> tuple[RaidRecord, RecordingAsset]:
        self._require_enabled()
        raid = self._require_raid(raid_id)
        source_path = Path(source).expanduser().resolve()
        self._validate_source_path(source_path)
        self._wait_for_stability(source_path)

        existing = self._matching_recording(raid, source_path)
        if existing is not None:
            return raid, existing

        should_copy = (
            self._settings.copy_recordings_into_package
            if copy_into_package is None
            else copy_into_package
        )
        try:
            updated, evidence = self._packages.attach_file(
                raid,
                source_path,
                EvidenceKind.RECORDING,
                copy_into_package=should_copy,
                metadata={
                    "source": media_source.value,
                    "original_path": str(source_path),
                    "indexed_at": datetime.now(UTC).isoformat(),
                },
            )
        except RaidPackageError as exc:
            raise MediaFinalizationError(str(exc)) from exc

        self._repository.save_raid(updated)
        probe = self._probe(evidence.path)
        asset = RecordingAsset(
            raid_id=updated.id,
            evidence_id=evidence.id,
            source=media_source,
            original_path=source_path,
            canonical_path=evidence.path,
            size_bytes=evidence.size_bytes or 0,
            sha256=evidence.sha256 or "",
            copied_into_package=should_copy,
            available=evidence.available,
            **probe,
        )
        index = self._load_index(updated)
        index.recordings.append(asset)
        self._write_index(updated, index)
        return updated, asset

    def index_for_raid(self, raid_id: UUID | str) -> RaidMediaIndex:
        raid = self._require_raid(raid_id)
        return self._load_index(raid)

    def navigation_for_raid(
        self,
        raid_id: UUID | str,
    ) -> list[MediaNavigationPoint]:
        raid = self._require_raid(raid_id)
        index = self._load_index(raid)
        recording = self._latest_available_recording(index)
        if recording is None:
            return []
        points: list[MediaNavigationPoint] = []
        for event in self._repository.list_timeline_events(raid.id):
            if event.raid_offset_ms is None:
                continue
            category = event.payload.get("category")
            points.append(
                MediaNavigationPoint(
                    recording_id=recording.id,
                    timeline_event_id=event.id,
                    event_type=event.event_type,
                    label=event.label,
                    raid_offset_ms=event.raid_offset_ms,
                    seek_seconds=event.raid_offset_ms / 1000.0,
                    source=event.source,
                    category=(
                        str(category) if category is not None else None
                    ),
                )
            )
        return points

    def extract_clip(
        self,
        raid_id: UUID | str,
        request: ClipRequest,
    ) -> tuple[RaidRecord, MediaClip]:
        self._require_enabled()
        raid = self._require_raid(raid_id)
        index = self._load_index(raid)
        recording = self._latest_available_recording(index)
        if recording is None:
            raise MediaFinalizationError(
                "No available indexed recording exists for this raid"
            )
        offset_ms, event_id, default_label = self._resolve_clip_anchor(
            raid,
            request,
        )
        start_seconds = max(
            0.0,
            (offset_ms / 1000.0) - request.seconds_before,
        )
        duration_seconds = request.seconds_before + request.seconds_after
        label = request.label or default_label
        clip_path = self._clip_path(
            raid,
            label,
            offset_ms,
        )
        self._run_ffmpeg(
            recording.canonical_path,
            clip_path,
            start_seconds,
            duration_seconds,
        )
        try:
            updated, evidence = self._packages.attach_file(
                raid,
                clip_path,
                EvidenceKind.CLIP,
                copy_into_package=False,
                metadata={
                    "source": MediaSource.GENERATED.value,
                    "recording_id": str(recording.id),
                    "anchor_offset_ms": offset_ms,
                },
            )
        except RaidPackageError as exc:
            raise MediaFinalizationError(str(exc)) from exc
        self._repository.save_raid(updated)
        clip = MediaClip(
            raid_id=updated.id,
            recording_id=recording.id,
            evidence_id=evidence.id,
            path=evidence.path,
            anchor_offset_ms=offset_ms,
            start_seconds=start_seconds,
            duration_seconds=duration_seconds,
            label=label,
            timeline_event_id=event_id,
            available=evidence.available,
        )
        index.clips.append(clip)
        self._write_index(updated, index)
        return updated, clip

    def refresh_availability(
        self,
        raid_id: UUID | str,
    ) -> RaidMediaIndex:
        raid = self._require_raid(raid_id)
        index = self._load_index(raid)
        index.recordings = [
            item.model_copy(
                update={"available": item.canonical_path.is_file()}
            )
            for item in index.recordings
        ]
        index.clips = [
            item.model_copy(update={"available": item.path.is_file()})
            for item in index.clips
        ]
        self._write_index(raid, index)
        return index

    def _wait_for_stability(self, path: Path) -> None:
        deadline = (
            time.monotonic()
            + self._settings.file_stability_timeout_seconds
        )
        previous: tuple[int, int] | None = None
        stable_checks = 0
        while True:
            try:
                stat = path.stat()
            except OSError as exc:
                raise MediaPathError(
                    f"Unable to inspect media file: {path}"
                ) from exc
            current = (stat.st_size, stat.st_mtime_ns)
            if current == previous and stat.st_size > 0:
                stable_checks += 1
            else:
                stable_checks = 1 if stat.st_size > 0 else 0
                previous = current
            if stable_checks >= self._settings.file_stability_checks:
                return
            if time.monotonic() >= deadline:
                raise MediaFinalizationError(
                    "Recording did not become stable before the configured "
                    "timeout"
                )
            time.sleep(self._settings.file_stability_poll_seconds)

    def _validate_source_path(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise MediaPathError(f"Media file does not exist: {path}")
        for root in self._allowed_roots:
            try:
                path.relative_to(root)
                return
            except ValueError:
                continue
        raise MediaPathError(
            "Media path is outside data_root and "
            "api.allowed_evidence_roots"
        )

    def _matching_recording(
        self,
        raid: RaidRecord,
        source_path: Path,
    ) -> RecordingAsset | None:
        index = self._load_index(raid)
        size = source_path.stat().st_size
        for recording in reversed(index.recordings):
            same_path = recording.original_path == source_path
            if same_path and recording.size_bytes == size:
                return recording.model_copy(
                    update={
                        "available": recording.canonical_path.is_file()
                    }
                )
        return None

    def _probe(self, path: Path) -> dict[str, Any]:
        executable = shutil.which(self._settings.ffprobe_path)
        if executable is None:
            return {
                "probe_status": ProbeStatus.UNAVAILABLE,
                "probe_error": "ffprobe was not found on PATH",
            }
        command = [
            executable,
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:"
                "stream=index,codec_type,codec_name,width,height,"
                "r_frame_rate,channels"
            ),
            "-of",
            "json",
            str(path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._settings.probe_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "probe_status": ProbeStatus.FAILED,
                "probe_error": str(exc),
            }
        if result.returncode != 0:
            return {
                "probe_status": ProbeStatus.FAILED,
                "probe_error": result.stderr.strip() or "ffprobe failed",
            }
        try:
            payload = json.loads(result.stdout)
            return self._probe_payload(payload)
        except (TypeError, ValueError, KeyError) as exc:
            return {
                "probe_status": ProbeStatus.FAILED,
                "probe_error": f"Unable to parse ffprobe output: {exc}",
            }

    @staticmethod
    def _probe_payload(payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("ffprobe payload must be an object")
        format_data = payload.get("format", {})
        streams_data = payload.get("streams", [])
        if not isinstance(format_data, dict):
            format_data = {}
        if not isinstance(streams_data, list):
            streams_data = []
        streams = [
            item for item in streams_data if isinstance(item, dict)
        ]
        video = next(
            (
                item
                for item in streams
                if item.get("codec_type") == "video"
            ),
            None,
        )
        audio = [
            item
            for item in streams
            if item.get("codec_type") == "audio"
        ]
        duration = MediaService._optional_float(
            format_data.get("duration")
        )
        fps = None
        if video is not None:
            fps = MediaService._fraction(video.get("r_frame_rate"))
        return {
            "probe_status": ProbeStatus.COMPLETE,
            "duration_seconds": duration,
            "width": MediaService._optional_int(
                video.get("width") if video else None
            ),
            "height": MediaService._optional_int(
                video.get("height") if video else None
            ),
            "fps": fps,
            "video_codec": (
                str(video.get("codec_name"))
                if video and video.get("codec_name")
                else None
            ),
            "audio_stream_count": len(audio),
            "audio_codecs": [
                str(item["codec_name"])
                for item in audio
                if item.get("codec_name")
            ],
        }

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value))
        except ValueError:
            return None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value))
        except ValueError:
            return None

    @staticmethod
    def _fraction(value: object) -> float | None:
        if value is None:
            return None
        text = str(value)
        if "/" not in text:
            return MediaService._optional_float(text)
        numerator, denominator = text.split("/", maxsplit=1)
        try:
            divisor = float(denominator)
            return float(numerator) / divisor if divisor else None
        except ValueError:
            return None

    def _resolve_clip_anchor(
        self,
        raid: RaidRecord,
        request: ClipRequest,
    ) -> tuple[int, UUID | None, str]:
        if request.raid_offset_ms is not None:
            return request.raid_offset_ms, None, "manual-clip"
        event_id = request.timeline_event_id
        for event in self._repository.list_timeline_events(raid.id):
            if event.id == event_id:
                if event.raid_offset_ms is None:
                    raise MediaFinalizationError(
                        "The selected timeline event has no raid offset"
                    )
                return event.raid_offset_ms, event.id, event.label
        raise LookupError(f"Timeline event not found: {event_id}")

    def _clip_path(
        self,
        raid: RaidRecord,
        label: str,
        offset_ms: int,
    ) -> Path:
        folder = self._root / "clips" / str(raid.id)
        folder.mkdir(parents=True, exist_ok=True)
        name = _safe_component(label, "clip")
        path = folder / f"{offset_ms:010d}_{name}.mkv"
        counter = 1
        while path.exists():
            path = folder / f"{offset_ms:010d}_{name}-{counter}.mkv"
            counter += 1
        return path

    def _run_ffmpeg(
        self,
        recording: Path,
        destination: Path,
        start_seconds: float,
        duration_seconds: float,
    ) -> None:
        executable = shutil.which(self._settings.ffmpeg_path)
        if executable is None:
            raise MediaToolError("ffmpeg was not found on PATH")
        command = [
            executable,
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(recording),
            "-t",
            f"{duration_seconds:.3f}",
            "-map",
            "0",
            "-c",
            "copy",
            str(destination),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._settings.clip_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MediaToolError(
                f"Unable to run ffmpeg: {exc}"
            ) from exc
        if result.returncode != 0 or not destination.is_file():
            destination.unlink(missing_ok=True)
            detail = (
                result.stderr.strip()
                or "ffmpeg did not create a clip"
            )
            raise MediaToolError(detail)

    def _load_index(self, raid: RaidRecord) -> RaidMediaIndex:
        path = self._index_path(raid)
        if not path.exists():
            return RaidMediaIndex(raid_id=raid.id)
        return RaidMediaIndex.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def _write_index(
        self,
        raid: RaidRecord,
        index: RaidMediaIndex,
    ) -> None:
        updated = index.model_copy(
            update={"generated_at": datetime.now(UTC)}
        )
        _atomic_write(
            self._index_path(raid),
            updated.model_dump_json(indent=2),
        )

    @staticmethod
    def _index_path(raid: RaidRecord) -> Path:
        return raid.data_root / "analysis" / "media-index.json"

    @staticmethod
    def _latest_available_recording(
        index: RaidMediaIndex,
    ) -> RecordingAsset | None:
        available = [
            item
            for item in index.recordings
            if item.available and item.canonical_path.is_file()
        ]
        return available[-1] if available else None

    def _require_raid(self, raid_id: UUID | str) -> RaidRecord:
        raid = self._repository.get_raid(raid_id)
        if raid is None:
            raise LookupError(f"Raid not found: {raid_id}")
        return raid

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise MediaDisabledError(
                "The Media Assistance subsystem is disabled in "
                "configuration"
            )
