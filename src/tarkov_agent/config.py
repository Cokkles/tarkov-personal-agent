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

    def ensure_directories(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.raids_root.mkdir(parents=True, exist_ok=True)
        self.diagnostics_root.mkdir(parents=True, exist_ok=True)


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


class RuntimeSettings(BaseModel):
    auto_create_raid_package: bool = True
    copy_evidence_into_package: bool = False
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
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    @model_validator(mode="after")
    def normalize_paths(self) -> AppSettings:
        self.paths.data_root = self.paths.data_root.expanduser().resolve()
        self.paths.tarkov_log_roots = [
            path.expanduser().resolve() for path in self.paths.tarkov_log_roots
        ]
        return self

    @classmethod
    def from_toml(cls, path: Path | str) -> AppSettings:
        config_path = Path(path).expanduser().resolve()
        with config_path.open("rb") as handle:
            data: dict[str, Any] = tomllib.load(handle)
        return cls.model_validate(data)

    def prepare(self) -> None:
        self.paths.ensure_directories()
