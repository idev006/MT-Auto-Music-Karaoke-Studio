"""Headless command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from mt_engine.production import produce_song
from mt_engine.production.openrouter_vision import rerun_vision_qc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mt-karaoke")
    commands = parser.add_subparsers(dest="command", required=True)
    produce = commands.add_parser("produce-song", help="Produce one song folder end to end")
    produce.add_argument("--source", type=Path, required=True)
    produce.add_argument("--dest-root", type=Path, required=True)
    produce.add_argument("--ffmpeg-root", type=Path, required=True)
    produce.add_argument("--model", default="base")
    produce.add_argument("--cpu-threads", type=int, default=8)
    produce.add_argument("--ffmpeg-preset", default="veryfast")
    produce.add_argument("--single-image-for-both", action="store_true")
    produce.add_argument("--accept-unreviewed-timing", action="store_true")
    produce.add_argument(
        "--openrouter-config", type=Path, default=Path("config/openrouter.env")
    )
    vision = commands.add_parser(
        "vision-qc", help="Rerun OpenRouter Vision QC for an existing target"
    )
    vision.add_argument("--target", type=Path, required=True)
    vision.add_argument(
        "--openrouter-config", type=Path, default=Path("config/openrouter.env")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Windows may expose a legacy console encoding even when paths contain
    # Thai characters. Avoid failing after a successful production run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = _parser().parse_args(argv)
    if args.command == "produce-song":
        result = produce_song(
            args.source,
            args.dest_root,
            ffmpeg_root=args.ffmpeg_root,
            model_name=args.model,
            cpu_threads=args.cpu_threads,
            single_image_for_both=args.single_image_for_both,
            accept_unreviewed_timing=args.accept_unreviewed_timing,
            ffmpeg_preset=args.ffmpeg_preset,
            openrouter_config=args.openrouter_config,
        )
        print(
            json.dumps(
                {
                    "job_id": result.job_id,
                    "run_id": result.run_id,
                    "target_dir": str(result.target_dir),
                    "mp3": str(result.mp3_output),
                    "mp4": str(result.mp4_output),
                    "manifest": str(result.manifest),
                    "qc_report": str(result.qc_report),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "vision-qc":
        result = rerun_vision_qc(args.target.resolve(), args.openrouter_config.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
