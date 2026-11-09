"""Publish a reviewed MP4 only after hash-bound final listening sign-off."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .media import sha256_file


class ReleaseSignoffError(ValueError):
    """Final listening sign-off is absent, stale or does not bind the candidate."""


@dataclass(frozen=True, slots=True)
class ReleaseResult:
    mp4: Path
    manifest: Path
    state: str


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseSignoffError(f"Cannot read required JSON: {path}") from exc


def release_reviewed_candidate(target_dir: Path, signoff_path: Path) -> ReleaseResult:
    target_dir = target_dir.resolve()
    production_data = target_dir / "production_data"
    manifest_path = production_data / "manifest.json"
    manifest = _read_json(manifest_path)
    timing = _read_json(production_data / "timing.json")
    qc = _read_json(production_data / "qc_report.json")
    signoff = _read_json(signoff_path.resolve())

    if manifest.get("state") != "AWAITING_FINAL_LISTENING_QC":
        raise ReleaseSignoffError("Target is not awaiting final listening QC")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or not isinstance(outputs.get("review_candidate"), dict):
        raise ReleaseSignoffError("Manifest has no review candidate")
    candidate_info = outputs["review_candidate"]
    candidate = (target_dir / str(candidate_info["path"])).resolve()
    if not candidate.is_relative_to(target_dir) or not candidate.is_file():
        raise ReleaseSignoffError("Review candidate path is unsafe or missing")
    candidate_hash = sha256_file(candidate)
    if candidate_hash != candidate_info.get("sha256"):
        raise ReleaseSignoffError("Review candidate hash changed after rendering")

    human_lock = timing.get("human_lock")
    if not isinstance(human_lock, dict):
        raise ReleaseSignoffError("Timing evidence is not human locked")
    required = {
        "schema_version": 1,
        "state": "SIGNED_OFF",
        "candidate_sha256": candidate_hash,
        "audio_sha256": human_lock.get("audio_sha256"),
        "lyrics_sha256": human_lock.get("lyrics_sha256"),
        "full_listening_completed": True,
    }
    for key, expected in required.items():
        if signoff.get(key) != expected:
            raise ReleaseSignoffError(f"Final listening sign-off field {key!r} is invalid")
    signer = str(signoff.get("signed_by", "")).strip()
    signed_at = str(signoff.get("signed_at", "")).strip()
    if not signer or not signed_at:
        raise ReleaseSignoffError("Final listening sign-off requires signed_by and signed_at")
    if qc.get("mp4") is None or qc.get("source_immutable") is not True:
        raise ReleaseSignoffError("Automated media QC is incomplete")

    final_mp4 = target_dir / "karaoke.mp4"
    if final_mp4.exists():
        raise FileExistsError(f"Final MP4 already exists: {final_mp4}")
    temporary = target_dir / ".karaoke.release.tmp.mp4"
    shutil.copy2(candidate, temporary)
    if sha256_file(temporary) != candidate_hash:
        temporary.unlink(missing_ok=True)
        raise ReleaseSignoffError("Candidate changed while preparing final release")
    os.replace(temporary, final_mp4)

    (production_data / "final_listening_signoff.json").write_text(
        json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest["state"] = "RELEASED_VERIFIED"
    outputs["mp4"] = {"path": final_mp4.name, "sha256": candidate_hash}
    manifest["release_signoff"] = {
        "signed_by": signer,
        "signed_at": signed_at,
        "candidate_sha256": candidate_hash,
    }
    temporary_manifest = production_data / ".manifest.release.tmp.json"
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary_manifest, manifest_path)
    return ReleaseResult(final_mp4, manifest_path, "RELEASED_VERIFIED")
