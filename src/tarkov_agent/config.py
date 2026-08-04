from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PathSettings(BaseModel):
    data_root: Path = Field(default_factory=lambda: Path.home() / "TarkovPersonalAgent")
    tarkov_log_roots: list[Path] = Field(default_factory=list)

    @property
    def database_path(self) -> Path:
        return self.data_root / "agent.sqlite3"

    @property
    def raids_root(self) -> Path:
        return self.data_root / "raids"

    @property
    def diagnostics_root(self) -> Path:
        return self.data_root / "diagnostics"

    @property
    def ppe_root(self) -> Path:
        return self.data_root / "ppe"

    @property
    def source_truth_root(self) -> Path:
        return self.data_root / "source-truth"

    @property
    def recommendations_root(self) -> Path:
        return self.data_root / "recommendations"

    @property
    def media_root(self) -> Path:
        return self.data_root / "media"

    def ensure_directories(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.raids_root.mkdir(parents=True, exist_ok=True)
        self.diagnostics_root.mkdir(parents=True, exist_ok=True)
        self.ppe_root.mkdir(parents=True, exist_ok=True)
        self.source_truth_root.mkdir(parents=True, exist_ok=True)
        self.recommendations_root.mkdir(parents=True, exist_ok=True)
        self.media_root.mkdir(parents=True, exist_ok=True)


class ProcessSettings(BaseModel):
    executable_names: tuple[str, ...] = (
        "EscapeFromTarkov.exe",
        "EscapeFromTarkov_BE.exe",
        "EscapeFromTarkovArena.exe",
    )
    poll_interval_seconds: float = Field(default=2.0, gt=0.1, le=60.0)


class LogSignalRule(BaseModel):
    name: str
    pattern: str
    signal: str
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class LogSettings(BaseModel):
    file_globs: tuple[str, ...] = ("*.log", "*.txt")
    poll_interval_seconds: float = Field(default=1.0, gt=0.1, le=60.0)
    start_at_end: bool = True
    minimum_auto_signal_confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    rules: list[LogSignalRule] = Field(default_factory=list)


class ObsSettings(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=4455, ge=1, le=65535)
    password: str = ""
    timeout_seconds: float = Field(default=3.0, gt=0.1, le=60.0)
    start_recording_on_raid_start: bool = True
    stop_recording_on_raid_end: bool = True


class ApiSettings(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    token: str = ""
    open_browser: bool = True
    allowed_evidence_roots: list[Path] = Field(default_factory=list)


class DiagnosticSettings(BaseModel):
    default_capture_seconds: float = Field(default=120.0, gt=0.0, le=3600.0)
    maximum_lines: int = Field(default=10000, ge=1, le=1_000_000)


class PpeSettings(BaseModel):
    enabled: bool = True
    neutral_prior_weight: float = Field(default=1.25, ge=0.0, le=20.0)
    confidence_weight_scale: float = Field(default=2.5, gt=0.0, le=100.0)
    maximum_weight_per_raid_dimension: float = Field(default=1.0, gt=0.0, le=20.0)
    minimum_report_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    minimum_established_confidence: float = Field(default=0.50, ge=0.0, le=1.0)
    signal_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    context_difference_threshold: float = Field(default=0.35, ge=0.0, le=2.0)
    minimum_independent_raids: int = Field(default=3, ge=1, le=1000)
    maximum_history: int = Field(default=200, ge=1, le=10000)


class SourceTruthSettings(BaseModel):
    enabled: bool = True
    seed_default_sources: bool = True
    minimum_verification_score: float = Field(default=0.72, ge=0.0, le=1.0)
    minimum_supporting_citations: int = Field(default=1, ge=1, le=20)
    claim_review_interval_days: int = Field(default=30, ge=1, le=3650)
    source_review_interval_days: int = Field(default=30, ge=1, le=3650)
    stale_grace_days: int = Field(default=14, ge=0, le=3650)


class RecommendationSettings(BaseModel):
    enabled: bool = True
    minimum_plan_confidence: float = Field(default=0.40, ge=0.0, le=1.0)
    maximum_history: int = Field(default=200, ge=1, le=10000)


class MediaSettings(BaseModel):
    enabled: bool = True
    copy_recordings_into_package: bool = False
    file_stability_timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        le=300.0,
    )
    file_stability_poll_seconds: float = Field(
        default=0.5,
        gt=0.0,
        le=10.0,
    )
    file_stability_checks: int = Field(default=3, ge=1, le=20)
    ffprobe_path: str = Field(default="ffprobe", min_length=1, max_length=500)
    ffmpeg_path: str = Field(default="ffmpeg", min_length=1, max_length=500)
    probe_timeout_seconds: float = Field(default=20.0, gt=0.0, le=300.0)
    clip_timeout_seconds: float = Field(default=180.0, gt=0.0, le=3600.0)
    default_clip_seconds_before: float = Field(default=10.0, ge=0.0, le=300.0)
    default_clip_seconds_after: float = Field(default=15.0, gt=0.0, le=600.0)


class RuntimeSettings(BaseModel):
    auto_create_raid_package: bool = True
    auto_complete_raid_on_end: bool = False
    copy_evidence_into_package: bool = False
    recover_interrupted_sessions: bool = True
    graceful_shutdown_seconds: float = Field(default=10.0, ge=0.0, le=120.0)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TPA_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    paths: PathSettings = Field(default_factory=PathSettings)
    process: ProcessSettings = Field(default_factory=ProcessSettings)
    logs: LogSettings = Field(default_factory=LogSettings)
    obs: ObsSettings = Field(default_factory=ObsSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    diagnostics: DiagnosticSettings = Field(default_factory=DiagnosticSettings)
    ppe: PpeSettings = Field(default_factory=PpeSettings)
    truth: SourceTruthSettings = Field(default_factory=SourceTruthSettings)
    recommendations: RecommendationSettings = Field(default_factory=RecommendationSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> AppSettings:
        self.paths.data_root = self.paths.data_root.expanduser().resolve()
        self.paths.tarkov_log_roots = [
            path.expanduser().resolve() for path in self.paths.tarkov_log_roots
        ]
        self.api.allowed_evidence_roots = [
            path.expanduser().resolve() for path in self.api.allowed_evidence_roots
        ]
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        if self.api.enabled and self.api.host not in loopback_hosts and not self.api.token:
            raise ValueError("A non-loopback API host requires api.token")
        if self.ppe.minimum_established_confidence < self.ppe.minimum_report_confidence:
            raise ValueError(
                "ppe.minimum_established_confidence must be at least "
                "ppe.minimum_report_confidence"
            )
        return self

    @classmethod
    def from_toml(cls, path: Path | str) -> AppSettings:
        config_path = Path(path).expanduser().resolve()
        with config_path.open("rb") as handle:
            data: dict[str, Any] = tomllib.load(handle)
        return cls.model_validate(data)

    def prepare(self) -> None:
        self.paths.ensure_directories()
