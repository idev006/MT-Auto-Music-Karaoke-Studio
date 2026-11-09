"""Optional, explicit OpenRouter vision adapter for rendered-text QC."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


class OpenRouterConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OpenRouterVisionConfig:
    enabled: bool
    api_key: str = field(repr=False)
    model: str = "google/gemini-2.5-flash"
    base_url: str = "https://openrouter.ai/api/v1"
    frame_count: int = 12
    timeout_seconds: int = 90
    app_name: str = "MT Auto Music Karaoke Studio"
    retry_attempts: int = 3

    @classmethod
    def from_file(cls, path: Path) -> OpenRouterVisionConfig:
        file_values: dict[str, str] = {}
        if path.is_file():
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                file_values[key.strip()] = value.strip()

        def setting(name: str, default: str = "") -> str:
            return os.environ.get(name, file_values.get(name, default))

        enabled = setting("OPENROUTER_VISION_QC_ENABLED", "false").casefold() in {
            "1",
            "true",
            "yes",
            "on",
        }
        api_key = setting("OPENROUTER_API_KEY")
        if enabled and not api_key:
            raise OpenRouterConfigError(
                f"OpenRouter Vision QC is enabled but OPENROUTER_API_KEY is empty in {path}"
            )
        frame_count = int(setting("OPENROUTER_VISION_QC_FRAME_COUNT", "12"))
        if not 10 <= frame_count <= 15:
            raise OpenRouterConfigError("Vision QC frame count must be between 10 and 15")
        return cls(
            enabled=enabled,
            api_key=api_key,
            model=setting("OPENROUTER_VISION_MODEL", "google/gemini-2.5-flash"),
            base_url=setting("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
            frame_count=frame_count,
            timeout_seconds=int(setting("OPENROUTER_TIMEOUT_SECONDS", "90")),
            app_name=setting("OPENROUTER_APP_NAME", "MT Auto Music Karaoke Studio"),
            retry_attempts=int(setting("OPENROUTER_RETRY_ATTEMPTS", "3")),
        )


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
        "model": config.model,
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
        "model": config.model,
        "visible_text": result.get("visible_text"),
        "matches_expected": result.get("matches_expected"),
        "confidence": result.get("confidence"),
        "notes": result.get("notes"),
    }


def inspect_samples(
    config: OpenRouterVisionConfig,
    frame_directory: Path,
    samples: tuple[dict[str, object], ...],
) -> dict[str, object]:
    if not config.enabled:
        return {"status": "NOT_CONFIGURED", "results": []}
    results = []
    for sample in samples:
        last_error: Exception | None = None
        for attempt in range(config.retry_attempts):
            try:
                result = inspect_frame(
                    config,
                    frame_directory / str(sample["frame"]),
                    str(sample["expected_text"]),
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
    return {"status": "PASS" if passed else "REVIEW_REQUIRED", "results": results}


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
