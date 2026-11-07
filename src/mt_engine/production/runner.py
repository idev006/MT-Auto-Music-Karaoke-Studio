"""Single-folder headless producer used by the first real end-to-end slice."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mutagen.mp3 import MP3

from .intake import discover_song
from .lyrics import extract_lyrics, propose_timing, transcribe
from .media import embed_cover, run_ffmpeg_render, sha256_file, video_canvas, write_ass
from .openrouter_vision import OpenRouterVisionConfig, inspect_samples
from .qc import build_alignment_checks, extract_qc_frames, select_frame_samples


@dataclass(frozen=True, slots=True)
class ProductionResult:
    job_id: str
    run_id: str
    source_dir: Path
    target_dir: Path
    mp3_output: Path
    mp4_output: Path
    manifest: Path
    qc_report: Path


def _tool_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "-version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.splitlines()[0]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def produce_song(
    source_dir: Path,
    dest_root: Path,
    *,
    ffmpeg_root: Path,
    model_name: str = "base",
    cpu_threads: int = 8,
    single_image_for_both: bool = False,
    accept_unreviewed_timing: bool = False,
    ffmpeg_preset: str = "veryfast",
    openrouter_config: Path = Path("config/openrouter.env"),
) -> ProductionResult:
    assets = discover_song(source_dir, single_image_for_both=single_image_for_both)
    if not accept_unreviewed_timing:
        raise ValueError("This first ASR-guided timing proposal requires explicit test approval")
    ffmpeg = (ffmpeg_root / "bin" / "ffmpeg.exe").resolve()
    ffprobe = (ffmpeg_root / "bin" / "ffprobe.exe").resolve()
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise FileNotFoundError(f"FFmpeg tools were not found below {ffmpeg_root}")

    target_dir = dest_root.resolve() / assets.source_dir.name
    published_markers = (
        target_dir / "song_with_cover.mp3",
        target_dir / "karaoke.mp4",
        target_dir / "production_data" / "manifest.json",
    )
    if any(path.exists() for path in published_markers):
        raise FileExistsError(f"Target folder already contains published output: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)
    production_data = target_dir / "production_data"
    production_data.mkdir(exist_ok=True)
    job_id = uuid4().hex
    run_id = uuid4().hex
    staging = target_dir / ".work" / run_id
    staging.mkdir(parents=True)
    events_path = staging / "events.jsonl"

    source_hash_before = sha256_file(assets.mp3)
    image_hash = sha256_file(assets.image)
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    events_path.write_text(
        json.dumps({"event": "job_run.started", "run_id": run_id, "at": started_at}) + "\n",
        encoding="utf-8",
    )

    staged_mp3 = staging / "song_with_cover.mp3"
    mp3_qc = embed_cover(assets.mp3, assets.image, staged_mp3)
    mp3_qc["audio_frames_unchanged"] = (
        mp3_qc["source_audio_payload_sha256"] == mp3_qc["output_audio_payload_sha256"]
    )
    mp3_qc["cover_matches_input"] = mp3_qc["cover_sha256"] == image_hash
    if not mp3_qc["audio_frames_unchanged"] or not mp3_qc["cover_matches_input"]:
        raise RuntimeError("MP3 integrity verification failed")

    lyric_lines = extract_lyrics(assets.mp3)
    transcript, transcription_info = transcribe(
        assets.mp3,
        canonical_lyrics=lyric_lines,
        model_name=model_name,
        model_cache=dest_root.resolve() / ".models" / "faster-whisper",
        cpu_threads=cpu_threads,
    )
    audio_duration = float(MP3(assets.mp3).info.length)
    asr_window_duration = transcript[-1].end - transcript[0].start
    full_song_fallback_used = asr_window_duration < audio_duration * 0.35
    timing = propose_timing(lyric_lines, transcript, audio_duration=audio_duration)
    canvas = video_canvas(assets.image)
    ass_path = staging / "karaoke.ass"
    write_ass(timing, ass_path, canvas=canvas)
    staged_mp4 = staging / "karaoke.mp4"
    video_probe = run_ffmpeg_render(
        ffmpeg,
        ffprobe,
        image=assets.image,
        audio=assets.mp3,
        ass_path=ass_path,
        destination=staged_mp4,
        preset=ffmpeg_preset,
        canvas=canvas,
    )

    source_hash_after = sha256_file(assets.mp3)
    if source_hash_after != source_hash_before:
        raise RuntimeError("Source MP3 changed during production")

    timing_payload = {
        "schema_version": 1,
        "method": (
            "whole-song proportional fallback after insufficient faster-whisper coverage"
            if full_song_fallback_used
            else "monotonic canonical-lyrics alignment to faster-whisper segments"
        ),
        "full_song_fallback_used": full_song_fallback_used,
        "asr_window_duration_seconds": asr_window_duration,
        "audio_duration_seconds": audio_duration,
        "review_required": True,
        "test_approval_override": True,
        "transcription": transcription_info,
        "segments": [asdict(segment) for segment in timing],
        "transcript_evidence": [asdict(segment) for segment in transcript],
    }
    _write_json(production_data / "timing.json", timing_payload)
    (production_data / "karaoke.ass").write_bytes(ass_path.read_bytes())

    final_mp3 = target_dir / "song_with_cover.mp3"
    final_mp4 = target_dir / "karaoke.mp4"
    os.replace(staged_mp3, final_mp3)
    os.replace(staged_mp4, final_mp4)
    alignment_checks = build_alignment_checks(timing, transcript)
    frame_samples = select_frame_samples(alignment_checks, count=12)
    frame_evidence = extract_qc_frames(
        ffmpeg,
        final_mp4,
        frame_samples,
        production_data / "qc_frames",
    )
    vision_config = OpenRouterVisionConfig.from_file(openrouter_config.resolve())
    vision_qc = inspect_samples(
        vision_config,
        production_data / "qc_frames",
        frame_evidence,
    )
    alignment_review_count = sum(
        check.status == "REVIEW_REQUIRED" for check in alignment_checks
    )
    qc_payload = {
        "schema_version": 1,
        "source_immutable": source_hash_before == source_hash_after,
        "mp3": mp3_qc,
        "mp4": {
            "decode_passed": True,
            "probe": video_probe,
            "sha256": sha256_file(final_mp4),
        },
        "timing": {
            "review_required": True,
            "accepted_for_test_only": True,
            "measured_alignment_kpi": False,
        },
        "karaoke_sampling_qc": {
            "status": "REVIEW_REQUIRED",
            "sample_count": len(frame_evidence),
            "all_sampled_frames_have_subtitle_pixels": all(
                bool(item["subtitle_pixels_present"]) for item in frame_evidence
            ),
            "exact_text_comparison": "HUMAN_REVIEW_REQUIRED_NO_THAI_OCR",
            "alignment_lines_checked": len(alignment_checks),
            "alignment_lines_requiring_review": alignment_review_count,
            "samples": frame_evidence,
            "openrouter_vision_qc": vision_qc,
        },
    }
    qc_path = production_data / "qc_report.json"
    _write_json(qc_path, qc_payload)
    manifest_payload = {
        "schema_version": 1,
        "job_id": job_id,
        "run_id": run_id,
        "state": "SUCCEEDED_WITH_TEST_TIMING_OVERRIDE",
        "source": {
            "folder": str(assets.source_dir),
            "mp3": assets.mp3.name,
            "mp3_sha256": source_hash_before,
            "image": assets.image.name,
            "image_sha256": image_hash,
            "single_image_explicitly_mapped_to_both_roles": True,
        },
        "outputs": {
            "mp3": {"path": final_mp3.name, "sha256": sha256_file(final_mp3)},
            "mp4": {"path": final_mp4.name, "sha256": sha256_file(final_mp4)},
        },
        "tools": {
            "ffmpeg": _tool_version(ffmpeg),
            "ffprobe": _tool_version(ffprobe),
            "faster_whisper_model": model_name,
        },
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    manifest_path = production_data / "manifest.json"
    _write_json(manifest_path, manifest_payload)
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps({"event": "job_run.completed", "run_id": run_id}, ensure_ascii=False) + "\n"
        )
    return ProductionResult(
        job_id,
        run_id,
        assets.source_dir,
        target_dir,
        final_mp3,
        final_mp4,
        manifest_path,
        qc_path,
    )
