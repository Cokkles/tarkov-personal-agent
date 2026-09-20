from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from tarkov_voice import __version__
from tarkov_voice.config import VoiceConfig, load_config
from tarkov_voice.triggers import TriggerEngine
from tarkov_voice.types import Word


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarkov-voice",
        description="Voice marker sidecar for Tarkov Personal Agent",
    )
    parser.add_argument("--config", default="voice.toml", help="path to voice.toml")
    parser.add_argument("--list-devices", action="store_true", help="list microphones and exit")
    parser.add_argument("--dry-run", action="store_true", help="transcribe but do not post markers")
    parser.add_argument("--wav", type=Path, help="run on a 16 kHz mono wav instead of the mic")
    parser.add_argument(
        "--wav-start",
        help="ISO time of the wav's first sample (default: now); sets marker timestamps",
    )
    parser.add_argument(
        "--text-test",
        nargs="+",
        metavar="TEXT",
        help="run trigger rules on typed text (no audio, no model) and print the markers",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
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
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = load_config(Path(args.config))

    if args.list_devices:
        from tarkov_voice.audio import list_devices

        print(list_devices())
        return 0

    if args.text_test:
        return _text_test(cfg, args.text_test)

    from tarkov_voice.audio import MicStream, wav_frames
    from tarkov_voice.pipeline import Pipeline
    from tarkov_voice.sender import MarkerSender
    from tarkov_voice.transcriber import Transcriber
    from tarkov_voice.transcript_log import TranscriptLog

    engine = _build_engine(cfg)
    transcriber = Transcriber(cfg.model)
    transcript = TranscriptLog(cfg.transcript_dir)
    sender = None if (args.dry_run or not cfg.send_markers) else MarkerSender(cfg.api)
    pipeline = Pipeline(cfg, transcriber, engine, sender, transcript)

    print(f"Transcript: {transcript.path}")
    print(f"Markers: {'dry run' if sender is None else sender._config.host}")  # noqa: SLF001

    if args.wav:
        start = (
            datetime.fromisoformat(args.wav_start).timestamp() if args.wav_start else time.time()
        )
        pipeline.run(wav_frames(args.wav, start))
        return 0

    print("Listening. Press Ctrl+C to stop.")
    with MicStream(cfg.audio.device, cfg.audio.sample_rate) as mic:
        try:
            pipeline.run(mic.frames())
        except KeyboardInterrupt:
            print("\nStopping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
