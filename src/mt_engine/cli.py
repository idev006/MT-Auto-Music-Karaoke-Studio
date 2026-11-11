"""Headless command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from mt_engine.production import produce_song
from mt_engine.production.karaoke_presets import DEFAULT_PRESET_ID, list_karaoke_presets
from mt_engine.production.openrouter_vision import rerun_vision_qc
from mt_engine.production.preset_preview import generate_preset_previews
from mt_engine.production.release import release_reviewed_candidate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mt-karaoke")
    commands = parser.add_subparsers(dest="command", required=True)
    produce = commands.add_parser("produce-song", help="Produce one song folder end to end")
    produce.add_argument("--source", type=Path, required=True)
    produce.add_argument("--dest-root", type=Path, required=True)
    produce.add_argument("--ffmpeg-root", type=Path, required=True)
    produce.add_argument("--model", default="base")
    produce.add_argument("--model-cache", type=Path)
    produce.add_argument("--cpu-threads", type=int, default=8)
    produce.add_argument("--ffmpeg-preset", default="veryfast")
    produce.add_argument("--karaoke-preset", default=DEFAULT_PRESET_ID)
    produce.add_argument("--font-assets-dir", type=Path, default=Path("assets/Fonts"))
    produce.add_argument("--single-image-for-both", action="store_true")
    produce.add_argument("--accept-unreviewed-timing", action="store_true")
    produce.add_argument(
        "--timing-lock",
        type=Path,
        help="Human-reviewed LOCKED timing JSON required for correctness-only rendering",
    )
    produce.add_argument(
        "--openrouter-config", type=Path, default=Path("config/openrouter.env")
    )
    produce.add_argument(
        "--openrouter-mode",
        choices=("off", "auto", "always"),
        help="Override OPENROUTER_MODE for this song",
    )
    vision = commands.add_parser(
        "vision-qc", help="Rerun OpenRouter Vision QC for an existing target"
    )
    vision.add_argument("--target", type=Path, required=True)
    vision.add_argument(
        "--openrouter-config", type=Path, default=Path("config/openrouter.env")
    )
    release = commands.add_parser(
        "release-reviewed", help="Publish a hash-bound candidate after full listening sign-off"
    )
    release.add_argument("--target", type=Path, required=True)
    release.add_argument("--signoff", type=Path, required=True)
    commands.add_parser("list-presets", help="List built-in karaoke visual presets")
    preview = commands.add_parser(
        "preview-presets", help="Render preset PNG previews without producing an MP4"
    )
    preview.add_argument("--background", type=Path, required=True)
    preview.add_argument("--output-dir", type=Path, required=True)
    preview.add_argument("--ffmpeg-root", type=Path, required=True)
    preview.add_argument("--font-assets-dir", type=Path, default=Path("assets/Fonts"))
    preview.add_argument(
        "--text", default="ไม่เคยทำให้ฉัน ต้องทุกข์ร้อนใจ"
    )
    preview.add_argument(
        "--presets", help="Comma-separated preset IDs; default renders the full catalog"
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
            model_cache=args.model_cache,
            cpu_threads=args.cpu_threads,
            single_image_for_both=args.single_image_for_both,
            accept_unreviewed_timing=args.accept_unreviewed_timing,
            ffmpeg_preset=args.ffmpeg_preset,
            karaoke_preset=args.karaoke_preset,
            font_assets_dir=args.font_assets_dir,
            openrouter_config=args.openrouter_config,
            openrouter_mode=args.openrouter_mode,
            timing_lock=args.timing_lock,
        )
        print(
            json.dumps(
                {
                    "job_id": result.job_id,
                    "run_id": result.run_id,
                    "target_dir": str(result.target_dir),
                    "mp3": str(result.mp3_output),
                    "mp4": str(result.mp4_output) if result.mp4_output else None,
                    "manifest": str(result.manifest),
                    "qc_report": str(result.qc_report),
                    "state": result.state,
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
    if args.command == "release-reviewed":
        result = release_reviewed_candidate(args.target, args.signoff)
        print(
            json.dumps(
                {
                    "state": result.state,
                    "mp4": str(result.mp4),
                    "manifest": str(result.manifest),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "list-presets":
        print(json.dumps(list_karaoke_presets(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "preview-presets":
        preset_ids = (
            tuple(item.strip() for item in args.presets.split(",") if item.strip())
            if args.presets
            else None
        )
        result = generate_preset_previews(
            background=args.background,
            output_dir=args.output_dir,
            ffmpeg_root=args.ffmpeg_root,
            fonts_dir=args.font_assets_dir,
            text=args.text,
            preset_ids=preset_ids,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
