from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from tarkov_voice import __version__
from tarkov_voice.config import VoiceConfig, load_config
from tarkov_voice.triggers import TriggerEngine
from tarkov_voice.types import Word


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarkov-voice",
        description="Voice marker sidecar for Tarkov Personal Agent (phase 2: trigger rules only)",
    )
    parser.add_argument("--config", default="voice.toml", help="path to voice.toml")
    parser.add_argument(
        "--text-test",
        nargs="+",
        metavar="TEXT",
        help="run trigger rules on typed text (no audio, no model) and print the markers",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _build_engine(cfg: VoiceConfig) -> TriggerEngine:
    return TriggerEngine.from_file(
        cfg.triggers_path,
        mode=cfg.triggers.mode,
        min_confidence=cfg.triggers.min_confidence,
        prefix_words=cfg.triggers.prefix_words,
    )


def _text_test(cfg: VoiceConfig, lines: list[str]) -> int:
    engine = _build_engine(cfg)
    base = time.time()
    for line in lines:
        engine.reset()
        words = [
            Word(text=token, start=base + i * 0.35, end=base + i * 0.35 + 0.3)
            for i, token in enumerate(line.split())
        ]
        hits = engine.scan(words)
        print(f'"{line}"')
        if not hits:
            print("    (no marker)")
        for hit in hits:
            kind = hit.marker_type or "voice note"
            offset = hit.occurred_at - base
            print(f"    -> {kind}  conf={hit.confidence:.2f}  +{offset:.2f}s  rule={hit.rule}")
            print(f"       {hit.details}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cfg = load_config(Path(args.config))
    if args.text_test:
        return _text_test(cfg, args.text_test)
    print("Nothing to do yet: microphone capture arrives in phase 3. Try --text-test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
