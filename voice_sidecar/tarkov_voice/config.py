from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AudioConfig:
    device: str = ""  # substring of the device name, an index, or empty for the default input
    sample_rate: int = 16000


@dataclass(slots=True)
class VadConfig:
    aggressiveness: int = 2  # webrtcvad 0-3; higher filters more non-speech
    end_silence_ms: int = 600  # silence that closes an utterance
    max_utterance_s: float = 12.0  # force a split during long monologues
    overlap_s: float = 1.0  # audio repeated at the start of a forced continuation
    min_utterance_ms: int = 300  # ignore clicks and pops shorter than this
    pre_roll_ms: int = 300  # audio kept from before speech was detected


@dataclass(slots=True)
class ModelConfig:
    name: str = "distil-large-v3"
    device: str = "cuda"
    compute_type: str = "float16"  # "int8_float16" uses less VRAM
    fallback_model: str = "small.en"  # used on CPU if CUDA cannot start
    beam_size: int = 1
    language: str = "en"
    initial_prompt: str = (
        "Escape from Tarkov gameplay. PMC, Scav, extract, Customs, Woods, Interchange, "
        "Shoreline, Reserve, Labs, Factory, Streets of Tarkov, Lighthouse, keycard, "
        "Killa, Tagilla, Reshala, Glukhar."
    )
    dll_search: bool = True  # add pip-installed NVIDIA DLL folders (Windows)


@dataclass(slots=True)
class TriggerConfig:
    file: str = "triggers.toml"
    mode: str = "hybrid"  # "hybrid": natural + prefix, "prefix_only": prefix required
    min_confidence: float = 0.5
    prefix_words: list[str] = field(default_factory=lambda: ["mark", "marker", "tag"])


@dataclass(slots=True)
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""
    timeout_s: float = 3.0


@dataclass(slots=True)
class VoiceConfig:
    base_dir: Path
    repo_config: Path | None = None
    data_root: Path = Path("~/TarkovPersonalAgent")
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    triggers: TriggerConfig = field(default_factory=TriggerConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    send_markers: bool = True

    @property
    def transcript_dir(self) -> Path:
        return self.data_root.expanduser() / "voice" / "transcripts"

    @property
    def triggers_path(self) -> Path:
        path = Path(self.triggers.file).expanduser()
        return path if path.is_absolute() else self.base_dir / path


def _apply(target: Any, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if hasattr(target, key):
            setattr(target, key, value)


def load_config(path: Path) -> VoiceConfig:
    path = path.expanduser().resolve()
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as handle:
            raw = tomllib.load(handle)

    cfg = VoiceConfig(base_dir=path.parent)
    _apply(cfg.audio, raw.get("audio", {}))
    _apply(cfg.vad, raw.get("vad", {}))
    _apply(cfg.model, raw.get("model", {}))
    _apply(cfg.triggers, raw.get("triggers", {}))
    _apply(cfg.api, raw.get("api", {}))
    cfg.send_markers = bool(raw.get("send_markers", True))

    repo_config = raw.get("repo_config")
    if repo_config:
        candidate = Path(str(repo_config)).expanduser()
        if not candidate.is_absolute():
            candidate = (cfg.base_dir / candidate).resolve()
        cfg.repo_config = candidate
        _merge_repo_config(cfg, cfg.repo_config)
    if "data_root" in raw:
        cfg.data_root = Path(str(raw["data_root"])).expanduser()
    return cfg


def _merge_repo_config(cfg: VoiceConfig, repo_config: Path) -> None:
    """Reuse host, port, token and data root from the agent's own config.toml.

    This avoids copying the API token into a second file.
    """
    if not repo_config.exists():
        return
    with repo_config.open("rb") as handle:
        repo = tomllib.load(handle)
    api = repo.get("api", {})
    if "host" in api:
        cfg.api.host = str(api["host"])
    if "port" in api:
        cfg.api.port = int(api["port"])
    if api.get("token"):
        cfg.api.token = str(api["token"])
    data_root = repo.get("paths", {}).get("data_root")
    if data_root:
        cfg.data_root = Path(str(data_root)).expanduser()
