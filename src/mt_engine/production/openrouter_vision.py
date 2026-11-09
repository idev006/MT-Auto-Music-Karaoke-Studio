"""Optional, explicit OpenRouter vision adapter for rendered-text QC."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .openrouter_config import (
    OpenRouterConfig,
    OpenRouterMode,
    OpenRouterSpendLedger,
)

OpenRouterVisionConfig = OpenRouterConfig


def _request_payload(config: OpenRouterVisionConfig, frame: Path, expected_text: str) -> bytes:
    encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
    mime = "image/png" if frame.suffix.lower() == ".png" else "image/jpeg"
    prompt = (
        "Inspect only the karaoke subtitle visible near the bottom of this frame. "
        "Expected Thai lyric: "
        + json.dumps(expected_text, ensure_ascii=False)
        + ". Return JSON with visible_text, matches_expected (boolean), confidence "
        "(0..1), and notes. Do not infer text that is not visibly rendered."
    )
    payload = {
        "model": config.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "provider": {"data_collection": "deny"},
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def inspect_frame(
    config: OpenRouterVisionConfig, frame: Path, expected_text: str
) -> dict[str, Any]:
    request = Request(
        f"{config.base_url}/chat/completions",
        data=_request_payload(config, frame, expected_text),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "X-Title": config.app_name,
        },
        method="POST",
    )
    with urlopen(request, timeout=config.timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    result = json.loads(content)
    return {
        "model": config.vision_model,
        "cost_usd": float((body.get("usage") or {}).get("cost") or 0.0),
        "visible_text": result.get("visible_text"),
        "matches_expected": result.get("matches_expected"),
        "confidence": result.get("confidence"),
        "notes": result.get("notes"),
    }


def inspect_samples(
    config: OpenRouterVisionConfig,
    frame_directory: Path,
    samples: tuple[dict[str, object], ...],
    *,
    ledger: OpenRouterSpendLedger | None = None,
    auto_needed: bool = True,
) -> dict[str, object]:
    if not config.enabled:
        return {"status": "SKIPPED_MODE_OFF", "mode": config.mode.value, "results": []}
    if config.mode is OpenRouterMode.AUTO and not auto_needed:
        return {"status": "SKIPPED_AUTO_NOT_NEEDED", "mode": config.mode.value, "results": []}
    ledger = ledger or OpenRouterSpendLedger(config.max_cost_usd)
    results = []
    for sample in samples:
        if not ledger.can_start(config.request_cost_guard_usd):
            results.append(
                {
                    "frame": sample["frame"],
                    "matches_expected": None,
                    "error": "OPENROUTER_BUDGET_GUARD",
                }
            )
            break
        last_error: Exception | None = None
        for attempt in range(config.retry_attempts):
            try:
                result = inspect_frame(
                    config,
                    frame_directory / str(sample["frame"]),
                    str(sample["expected_text"]),
                )
                ledger.record(
                    operation="vision_qc",
                    model=config.vision_model,
                    cost_usd=float(result.pop("cost_usd", 0.0)),
                )
                results.append({"frame": sample["frame"], **result})
                break
            except (OSError, TimeoutError, KeyError, ValueError) as error:
                last_error = error
                if attempt + 1 < config.retry_attempts:
                    time.sleep(2**attempt)
        else:
            results.append(
                {
                    "frame": sample["frame"],
                    "matches_expected": None,
                    "error": f"{type(last_error).__name__}: {last_error}",
                }
            )
    passed = results and all(item.get("matches_expected") is True for item in results)
    return {
        "status": "PASS" if passed else "REVIEW_REQUIRED",
        "mode": config.mode.value,
        "results": results,
        "spend": ledger.to_primitive(),
    }


def rerun_vision_qc(target_dir: Path, config_path: Path) -> dict[str, object]:
    report_path = target_dir / "production_data" / "qc_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sampling = report["karaoke_sampling_qc"]
    samples = tuple(sampling["samples"])
    result = inspect_samples(
        OpenRouterVisionConfig.from_file(config_path),
        target_dir / "production_data" / "qc_frames",
        samples,
    )
    sampling["openrouter_vision_qc"] = result
    temporary = report_path.with_suffix(".json.partial")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(report_path)
    return result
