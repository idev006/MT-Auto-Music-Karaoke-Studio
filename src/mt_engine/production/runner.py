"""Single-folder headless producer used by the first real end-to-end slice."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mutagen.mp3 import MP3

from mt_engine.paths import PathManager

from .intake import discover_song
from .karaoke_presets import DEFAULT_PRESET_ID, get_karaoke_preset
from .lyrics import propose_timing, resolve_canonical_lyrics, transcribe
from .media import (
    embed_cover,
    run_ffmpeg_render,
    sha256_file,
    verify_rendered_video,
    video_canvas,
    write_ass,
)
from .openrouter_config import (
    OpenRouterConfig,
    OpenRouterSpendLedger,
    should_use_openrouter_transcription,
)
from .openrouter_transcription import transcribe_openrouter
from .openrouter_vision import OpenRouterVisionConfig, inspect_samples
from .pre_render import build_pre_render_validation_report
from .qc import (
    build_alignment_checks,
    build_timing_diagnostics,
    extract_qc_frames,
    select_frame_samples,
)
from .review_package import build_timing_review_package
from .timing_domain import validate_timeline
from .timing_lock import load_verified_timing_lock


@dataclass(frozen=True, slots=True)
class ProductionResult:
    job_id: str
    run_id: str
    source_dir: Path
    target_dir: Path
    mp3_output: Path
    mp4_output: Path | None
    manifest: Path
    qc_report: Path
    state: str


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
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_run_state(
    production_data: Path,
    *,
    job_id: str,
    run_id: str,
    stage: str,
    detail: str,
    artifacts: Mapping[str, str] | None = None,
) -> None:
    _write_json(
        production_data / "run_state.json",
        {
            "schema_version": 1,
            "job_id": job_id,
            "run_id": run_id,
            "stage": stage,
            "detail": detail,
            "artifacts": dict(artifacts or {}),
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    )


def _read_run_state(production_data: Path) -> dict[str, object] | None:
    path = production_data / "run_state.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    artifacts = payload.get("artifacts")
    if payload.get("stage") != "COMPLETE" or (
        isinstance(artifacts, dict) and artifacts.get("source_sha256")
    ):
        return payload
    try:
        manifest = json.loads(
            (production_data / "manifest.json").read_text(encoding="utf-8")
        )
        if manifest.get("run_id") != payload.get("run_id"):
            return payload
        diagnostic = manifest["outputs"]["diagnostic_candidate"]
        ass_path = production_data / "karaoke.ass"
        payload["artifacts"] = {
            "source_sha256": manifest["source"]["mp3_sha256"],
            "background_sha256": manifest["source"]["background_sha256"],
            "ass_sha256": sha256_file(ass_path),
            "rendered_mp4": diagnostic["path"],
            "rendered_mp4_sha256": diagnostic["sha256"],
        }
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        pass
    return payload


def _reusable_diagnostic_render(
    prior_state: Mapping[str, object] | None,
    target_dir: Path,
    *,
    source_sha256: str,
    background_sha256: str,
    ass_sha256: str,
) -> Path | None:
    if not prior_state or prior_state.get("stage") not in {"QC", "COMPLETE"}:
        return None
    artifacts = prior_state.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    expected = {
        "source_sha256": source_sha256,
        "background_sha256": background_sha256,
        "ass_sha256": ass_sha256,
    }
    if any(artifacts.get(key) != value for key, value in expected.items()):
        return None
    relative = artifacts.get("rendered_mp4")
    expected_video_hash = artifacts.get("rendered_mp4_sha256")
    if not isinstance(relative, str) or not isinstance(expected_video_hash, str):
        return None
    candidate = (target_dir / relative).resolve()
    try:
        candidate.relative_to(target_dir.resolve())
    except ValueError:
        return None
    if not candidate.is_file() or sha256_file(candidate) != expected_video_hash:
        return None
    return candidate


def _validate_target_is_retryable(target_dir: Path) -> None:
    release_output = target_dir / "karaoke.mp4"
    manifest_path = target_dir / "production_data" / "manifest.json"
    covered_mp3 = target_dir / "song_with_cover.mp3"
    if release_output.exists():
        raise FileExistsError(f"Target folder already contains published output: {target_dir}")
    if not manifest_path.exists():
        if covered_mp3.exists():
            raise FileExistsError(
                f"Target folder contains an unmanaged prior output: {covered_mp3}"
            )
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FileExistsError(f"Cannot verify prior output ownership: {manifest_path}") from error
    state = manifest.get("state")
    if state == "RELEASED_VERIFIED":
        raise FileExistsError(f"Target folder already contains a released run: {target_dir}")


def produce_song(
    source_dir: Path,
    dest_root: Path,
    *,
    ffmpeg_root: Path,
    model_name: str = "base",
    model_cache: Path | None = None,
    cpu_threads: int = 8,
    single_image_for_both: bool = False,
    accept_unreviewed_timing: bool = False,
    ffmpeg_preset: str = "veryfast",
    karaoke_preset: str = DEFAULT_PRESET_ID,
    font_assets_dir: Path = Path("assets/Fonts"),
    openrouter_config: Path = Path("config/openrouter.env"),
    openrouter_mode: str | None = None,
    timing_lock: Path | None = None,
    progress_callback: Callable[[int, str, Mapping[str, str] | None], None] | None = None,
) -> ProductionResult:
    def report(value: int, detail: str, data: Mapping[str, str] | None = None) -> None:
        if progress_callback is not None:
            progress_callback(value, detail, data)

    report(2, "Validating inputs")
    assets = discover_song(source_dir, single_image_for_both=single_image_for_both)
    selected_karaoke_preset = get_karaoke_preset(karaoke_preset)
    resolved_font_assets = font_assets_dir.resolve()
    selected_font_file = resolved_font_assets / selected_karaoke_preset.font_asset_file
    if not selected_font_file.is_file():
        raise FileNotFoundError(f"Karaoke font asset was not found: {selected_font_file}")
    if timing_lock is None and not accept_unreviewed_timing:
        raise ValueError("This first ASR-guided timing proposal requires explicit test approval")
    ffmpeg = (ffmpeg_root / "bin" / "ffmpeg.exe").resolve()
    ffprobe = (ffmpeg_root / "bin" / "ffprobe.exe").resolve()
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise FileNotFoundError(f"FFmpeg tools were not found below {ffmpeg_root}")

    target_dir = dest_root.resolve() / assets.source_dir.name
    _validate_target_is_retryable(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    production_data = target_dir / "production_data"
    production_data.mkdir(exist_ok=True)
    prior_run_state = _read_run_state(production_data)
    router_config = OpenRouterConfig.from_file(openrouter_config.resolve()).with_mode(
        openrouter_mode
    )
    router_spend = OpenRouterSpendLedger(router_config.max_cost_usd)
    job_id = uuid4().hex
    run_id = uuid4().hex
    staging = target_dir / ".work" / run_id
    staging.mkdir(parents=True)
    events_path = staging / "events.jsonl"

    _write_run_state(
        production_data,
        job_id=job_id,
        run_id=run_id,
        stage="INTAKE",
        detail="Inputs validated and isolated staging created",
    )

    source_hash_before = sha256_file(assets.mp3)
    cover_hash = sha256_file(assets.cover)
    background_hash = sha256_file(assets.background)
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    events_path.write_text(
        json.dumps({"event": "job_run.started", "run_id": run_id, "at": started_at}) + "\n",
        encoding="utf-8",
    )

    report(10, "Embedding cover artwork")
    staged_mp3 = staging / "song_with_cover.mp3"
    mp3_qc = embed_cover(assets.mp3, assets.cover, staged_mp3)
    mp3_qc["audio_frames_unchanged"] = (
        mp3_qc["source_audio_payload_sha256"] == mp3_qc["output_audio_payload_sha256"]
    )
    mp3_qc["cover_matches_input"] = mp3_qc["cover_sha256"] == cover_hash
    if not mp3_qc["audio_frames_unchanged"] or not mp3_qc["cover_matches_input"]:
        raise RuntimeError("MP3 integrity verification failed")

    report(20, "Resolving canonical lyrics")
    canonical_lyrics = resolve_canonical_lyrics(assets.source_dir, assets.mp3)
    lyric_lines = canonical_lyrics.lines
    embedded_lyrics_inventory = canonical_lyrics.inventory
    embedded_payload = asdict(embedded_lyrics_inventory)
    embedded_payload["source_kind"] = canonical_lyrics.source_kind
    embedded_payload["source_file"] = canonical_lyrics.source_path.name
    _write_json(production_data / "embedded_lyrics.json", embedded_payload)
    _write_run_state(
        production_data,
        job_id=job_id,
        run_id=run_id,
        stage="LYRICS",
        detail=f"Canonical lyrics resolved from {canonical_lyrics.source_kind}",
        artifacts={"lyrics_sha256": embedded_lyrics_inventory.selected_uslt_sha256},
    )
    audio_duration = float(MP3(assets.mp3).info.length)
    verified_lock = None
    if timing_lock is not None:
        verified_lock = load_verified_timing_lock(
            timing_lock.resolve(),
            expected_audio_sha256=source_hash_before,
            expected_lyrics=lyric_lines,
        )
        transcript = ()
        transcription_info = {"model": "none_human_locked"}
        asr_window_duration = 0.0
        full_song_fallback_used = False
        timing = verified_lock.timing
    else:
        report(30, "Transcribing audio")
        _write_run_state(
            production_data,
            job_id=job_id,
            run_id=run_id,
            stage="TRANSCRIBE",
            detail=f"Transcribing with Faster Whisper {model_name}",
        )
        transcript, transcription_info = transcribe(
            assets.mp3,
            canonical_lyrics=lyric_lines,
            model_name=model_name,
            model_cache=(
                model_cache.resolve()
                if model_cache is not None
                else PathManager.detect().model_cache("faster-whisper")
            ),
            cpu_threads=cpu_threads,
        )
        asr_window_duration = transcript[-1].end - transcript[0].start
        full_song_fallback_used = asr_window_duration < audio_duration * 0.35
        timing = propose_timing(lyric_lines, transcript, audio_duration=audio_duration)
    timeline_validation = validate_timeline(
        timing,
        maximum_normalized_characters_per_second=None if verified_lock else 12.0,
    )
    timing_diagnostics = build_timing_diagnostics(timing, transcript, audio_duration=audio_duration)
    openrouter_transcription: dict[str, object] = {
        "mode": router_config.mode.value,
        "status": "SKIPPED_HUMAN_TIMING_LOCK" if verified_lock else "SKIPPED_MODE_OFF",
    }
    if not verified_lock:
        should_use_cloud, auto_needed = should_use_openrouter_transcription(
            router_config.mode,
            timeline_status=timeline_validation.status,
            asr_window_ratio=float(timing_diagnostics["asr_window_ratio"]),
            alignment_review_count=int(timing_diagnostics["alignment_review_count"]),
        )
        if router_config.mode.value == "auto" and not auto_needed:
            openrouter_transcription["status"] = "SKIPPED_AUTO_NOT_NEEDED"
        if should_use_cloud:
            last_error: Exception | None = None
            for _attempt in range(router_config.retry_attempts):
                try:
                    cloud_transcript, cloud_info = transcribe_openrouter(
                        router_config, router_spend, assets.mp3
                    )
                    cloud_timing = propose_timing(
                        lyric_lines, cloud_transcript, audio_duration=audio_duration
                    )
                    cloud_validation = validate_timeline(cloud_timing)
                    cloud_diagnostics = build_timing_diagnostics(
                        cloud_timing, cloud_transcript, audio_duration=audio_duration
                    )
                    status_rank = {"BLOCKED": 0, "REVIEW_REQUIRED": 1, "PASS": 2}
                    local_score = (
                        status_rank[timeline_validation.status],
                        int(timing_diagnostics["alignment_pass_count"]),
                        float(timing_diagnostics["asr_window_ratio"]),
                    )
                    cloud_score = (
                        status_rank[cloud_validation.status],
                        int(cloud_diagnostics["alignment_pass_count"]),
                        float(cloud_diagnostics["asr_window_ratio"]),
                    )
                    selected = cloud_score > local_score
                    openrouter_transcription = {
                        "mode": router_config.mode.value,
                        "status": "USED" if selected else "COMPLETED_LOCAL_RETAINED",
                        "auto_triggered": auto_needed,
                        "candidate_score": cloud_score,
                        "local_score": local_score,
                        "provider_result": cloud_info,
                    }
                    if selected:
                        transcript = cloud_transcript
                        timing = cloud_timing
                        timeline_validation = cloud_validation
                        timing_diagnostics = cloud_diagnostics
                        transcription_info = cloud_info
                    break
                except (OSError, TimeoutError, KeyError, ValueError, RuntimeError) as error:
                    last_error = error
            else:
                openrouter_transcription = {
                    "mode": router_config.mode.value,
                    "status": "REVIEW_REQUIRED_PROVIDER_ERROR",
                    "auto_triggered": auto_needed,
                    "error": f"{type(last_error).__name__}: {last_error}",
                }
    report(55, "Validating lyric timing")
    timing_payload = {
        "schema_version": 1,
        "method": (
            "human-reviewed hash-bound timing lock"
            if verified_lock
            else (
                "whole-song proportional fallback after insufficient faster-whisper coverage"
                if full_song_fallback_used
                else "monotonic canonical-lyrics alignment to faster-whisper segments"
            )
        ),
        "full_song_fallback_used": full_song_fallback_used,
        "asr_window_duration_seconds": asr_window_duration,
        "audio_duration_seconds": audio_duration,
        "review_required": verified_lock is None,
        "test_approval_override": verified_lock is None,
        "human_lock": (
            {
                "reviewer": verified_lock.reviewer,
                "reviewed_at": verified_lock.reviewed_at,
                "audio_sha256": verified_lock.audio_sha256,
                "lyrics_sha256": verified_lock.lyrics_sha256,
            }
            if verified_lock
            else None
        ),
        "transcription": transcription_info,
        "openrouter_transcription": openrouter_transcription,
        "openrouter_spend": router_spend.to_primitive(),
        "segments": [asdict(segment) for segment in timing],
        "transcript_evidence": [asdict(segment) for segment in transcript],
    }
    _write_json(production_data / "timing.json", timing_payload)
    _write_json(
        production_data / "diagnostics.json",
        timing_diagnostics,
    )
    _write_json(
        production_data / "timing_review_package.json",
        build_timing_review_package(
            timing,
            transcript,
            timeline_validation,
            audio_sha256=source_hash_before,
            lyrics_sha256=verified_lock.lyrics_sha256
            if verified_lock
            else embedded_lyrics_inventory.selected_uslt_sha256,
        ),
    )
    _write_run_state(
        production_data,
        job_id=job_id,
        run_id=run_id,
        stage="TIMING",
        detail=f"Timing proposal status: {timeline_validation.status}",
        artifacts={"timing_status": timeline_validation.status},
    )
    report(65, "Running pre-render validation")
    pre_render_report = build_pre_render_validation_report(
        audio_payload_sha256=mp3_qc["source_audio_payload_sha256"],
        audio_duration_seconds=audio_duration,
        inventory=embedded_lyrics_inventory,
        timing_lock_path=timing_lock.resolve() if timing_lock else None,
        verified_lock=verified_lock,
        timeline_validation=timeline_validation,
    )
    _write_json(production_data / "pre_render_validation.json", pre_render_report)
    if verified_lock and pre_render_report["release_decision"] != "PASS_FOR_REVIEW_RENDER":
        raise RuntimeError("Human-locked timing failed pre-render validation")

    canvas = video_canvas(assets.background)
    ass_path = staging / "karaoke.ass"
    report(75, "Generating karaoke layout")
    write_ass(
        timing,
        ass_path,
        canvas=canvas,
        progressive=verified_lock is not None,
        visual_preset=selected_karaoke_preset,
        font_path=selected_font_file,
    )
    staged_mp4 = staging / "karaoke.mp4"
    ass_sha256 = sha256_file(ass_path)
    reusable_render = (
        _reusable_diagnostic_render(
            prior_run_state,
            target_dir,
            source_sha256=source_hash_before,
            background_sha256=background_hash,
            ass_sha256=ass_sha256,
        )
        if verified_lock is None
        else None
    )
    report(80, "Verifying previous render" if reusable_render else "Rendering video")
    _write_run_state(
        production_data,
        job_id=job_id,
        run_id=run_id,
        stage="RENDER",
        detail="Verifying checkpoint render" if reusable_render else "FFmpeg render in progress",
        artifacts={"ass_sha256": ass_sha256},
    )
    if reusable_render:
        video_probe = verify_rendered_video(ffmpeg, ffprobe, reusable_render)
    else:
        video_probe = run_ffmpeg_render(
            ffmpeg,
            ffprobe,
            image=assets.background,
            audio=assets.mp3,
            ass_path=ass_path,
            destination=staged_mp4,
            preset=ffmpeg_preset,
            canvas=canvas,
            fonts_dir=resolved_font_assets,
            progress_callback=lambda fraction, detail, data: report(
                80 + round(fraction * 11), detail, data
            ),
        )

    source_hash_after = sha256_file(assets.mp3)
    if source_hash_after != source_hash_before:
        raise RuntimeError("Source MP3 changed during production")

    (production_data / "karaoke.ass").write_bytes(ass_path.read_bytes())

    final_mp3 = target_dir / "song_with_cover.mp3"
    rendered_mp4 = (
        production_data / "review_candidate.mp4"
        if verified_lock
        else target_dir / "karaoke_diagnostic.mp4"
    )
    os.replace(staged_mp3, final_mp3)
    if reusable_render is None:
        os.replace(staged_mp4, rendered_mp4)
    _write_run_state(
        production_data,
        job_id=job_id,
        run_id=run_id,
        stage="QC",
        detail="Render complete; media and sampled-frame QC in progress",
        artifacts={
            "rendered_mp4": str(rendered_mp4.relative_to(target_dir)),
            "rendered_mp4_sha256": sha256_file(rendered_mp4),
            "source_sha256": source_hash_before,
            "background_sha256": background_hash,
            "ass_sha256": ass_sha256,
        },
    )
    alignment_checks = build_alignment_checks(timing, transcript)
    frame_samples = select_frame_samples(alignment_checks, count=12)
    report(92, "Running media quality checks")
    frame_evidence = extract_qc_frames(
        ffmpeg,
        rendered_mp4,
        frame_samples,
        production_data / "qc_frames",
    )
    alignment_review_count = sum(check.status == "REVIEW_REQUIRED" for check in alignment_checks)
    vision_config = OpenRouterVisionConfig.from_file(openrouter_config.resolve())
    vision_qc = inspect_samples(
        vision_config,
        production_data / "qc_frames",
        frame_evidence,
        ledger=router_spend,
        auto_needed=verified_lock is not None or alignment_review_count > 0,
    )
    qc_payload = {
        "schema_version": 1,
        "source_immutable": source_hash_before == source_hash_after,
        "mp3": mp3_qc,
        "mp4": {
            "decode_passed": True,
            "probe": video_probe,
            "sha256": sha256_file(rendered_mp4),
        },
        "timing": {
            "review_required": verified_lock is None,
            "accepted_for_test_only": verified_lock is None,
            "measured_alignment_kpi": False,
            "human_locked": verified_lock is not None,
            "structural_validation": timeline_validation.to_primitive(),
        },
        "karaoke_sampling_qc": {
            "status": (
                "AWAITING_FINAL_LISTENING_QC"
                if verified_lock
                else (
                    "DIAGNOSTIC_RENDER_TIMING_BLOCKED"
                    if timeline_validation.status == "BLOCKED"
                    else "REVIEW_REQUIRED"
                )
            ),
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
        "openrouter": {
            "mode": router_config.mode.value,
            "transcription": openrouter_transcription,
            "spend": router_spend.to_primitive(),
        },
    }
    qc_path = production_data / "qc_report.json"
    _write_json(qc_path, qc_payload)
    production_state = (
        "AWAITING_FINAL_LISTENING_QC"
        if verified_lock
        else (
            "DIAGNOSTIC_VIDEO_READY_TIMING_BLOCKED"
            if timeline_validation.status == "BLOCKED"
            else "AWAITING_TIMING_REVIEW"
        )
    )
    manifest_payload = {
        "schema_version": 1,
        "job_id": job_id,
        "run_id": run_id,
        "state": production_state,
        "source": {
            "folder": str(assets.source_dir),
            "mp3": assets.mp3.name,
            "mp3_sha256": source_hash_before,
            "cover": assets.cover.name,
            "cover_sha256": cover_hash,
            "background": assets.background.name,
            "background_sha256": background_hash,
            "single_image_explicitly_mapped_to_both_roles": (assets.cover == assets.background),
        },
        "outputs": {
            "mp3": {"path": final_mp3.name, "sha256": sha256_file(final_mp3)},
            "mp4": None,
            "review_candidate": (
                {
                    "path": str(rendered_mp4.relative_to(target_dir)),
                    "sha256": sha256_file(rendered_mp4),
                }
                if verified_lock
                else None
            ),
            "diagnostic_candidate": (
                {
                    "path": str(rendered_mp4.relative_to(target_dir)),
                    "sha256": sha256_file(rendered_mp4),
                }
                if not verified_lock
                else None
            ),
        },
        "tools": {
            "ffmpeg": _tool_version(ffmpeg),
            "ffprobe": _tool_version(ffprobe),
            "faster_whisper_model": model_name if not verified_lock else None,
            "openrouter_mode": router_config.mode.value,
            "openrouter_spend": router_spend.to_primitive(),
        },
        "karaoke_visual_preset": selected_karaoke_preset.to_primitive(),
        "karaoke_font_asset": {
            "file": selected_font_file.name,
            "family": selected_karaoke_preset.font_family,
            "sha256": sha256_file(selected_font_file),
        },
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    report(98, "Writing production manifest")
    manifest_path = production_data / "manifest.json"
    _write_json(manifest_path, manifest_payload)
    _write_run_state(
        production_data,
        job_id=job_id,
        run_id=run_id,
        stage="COMPLETE",
        detail=production_state,
        artifacts={
            "manifest": str(manifest_path.relative_to(target_dir)),
            "production_state": production_state,
            "source_sha256": source_hash_before,
            "background_sha256": background_hash,
            "ass_sha256": ass_sha256,
            "rendered_mp4": str(rendered_mp4.relative_to(target_dir)),
            "rendered_mp4_sha256": sha256_file(rendered_mp4),
        },
    )
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
        None if verified_lock else rendered_mp4,
        manifest_path,
        qc_path,
        production_state,
    )
