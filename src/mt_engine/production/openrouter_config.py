"""Shared OpenRouter policy and per-song spend controls."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path


class OpenRouterConfigError(ValueError):
    pass


class OpenRouterMode(StrEnum):
    OFF = "off"
    AUTO = "auto"
    ALWAYS = "always"


@dataclass(frozen=True, slots=True)
class OpenRouterConfig:
    mode: OpenRouterMode = OpenRouterMode.OFF
    api_key: str = field(default="", repr=False)
    base_url: str = "https://openrouter.ai/api/v1"
    transcription_model: str = "openai/whisper-large-v3-turbo"
    vision_model: str = "google/gemini-2.5-flash"
    max_cost_usd: float = 0.20
    request_cost_guard_usd: float = 0.10
    frame_count: int = 12
    timeout_seconds: int = 90
    retry_attempts: int = 2
    app_name: str = "MT Auto Music Karaoke Studio"

    @property
    def enabled(self) -> bool:
        return self.mode is not OpenRouterMode.OFF

    def with_mode(self, mode: str | OpenRouterMode | None) -> OpenRouterConfig:
        if mode is None:
            return self
        selected = OpenRouterMode(mode)
        if selected is not OpenRouterMode.OFF and not self.api_key:
            raise OpenRouterConfigError(
                f"OpenRouter mode is {selected.value} but OPENROUTER_API_KEY is empty"
            )
        return replace(self, mode=selected)

    @classmethod
    def from_file(cls, path: Path) -> OpenRouterConfig:
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

        raw_mode = setting("OPENROUTER_MODE", "").casefold()
        if not raw_mode:
            legacy_enabled = setting(
                "OPENROUTER_VISION_QC_ENABLED", "false"
            ).casefold() in {"1", "true", "yes", "on"}
            raw_mode = "always" if legacy_enabled else "off"
        try:
            mode = OpenRouterMode(raw_mode)
        except ValueError as error:
            raise OpenRouterConfigError(
                "OPENROUTER_MODE must be off, auto, or always"
            ) from error

        api_key = setting("OPENROUTER_API_KEY")
        if mode is not OpenRouterMode.OFF and not api_key:
            raise OpenRouterConfigError(
                f"OpenRouter mode is {mode.value} but OPENROUTER_API_KEY is empty in {path}"
            )
        frame_count = int(setting("OPENROUTER_VISION_QC_FRAME_COUNT", "12"))
        if not 10 <= frame_count <= 15:
            raise OpenRouterConfigError("Vision QC frame count must be between 10 and 15")
        max_cost = float(setting("OPENROUTER_MAX_COST_USD_PER_SONG", "0.20"))
        request_guard = float(setting("OPENROUTER_REQUEST_COST_GUARD_USD", "0.10"))
        if not 0 < max_cost <= 0.20:
            raise OpenRouterConfigError(
                "OPENROUTER_MAX_COST_USD_PER_SONG must be greater than 0 and at most 0.20"
            )
        if not 0 < request_guard <= max_cost:
            raise OpenRouterConfigError(
                "OPENROUTER_REQUEST_COST_GUARD_USD must be greater than 0 and no more than the song budget"
            )
        retries = int(setting("OPENROUTER_RETRY_ATTEMPTS", "2"))
        if not 1 <= retries <= 3:
            raise OpenRouterConfigError("OpenRouter retry attempts must be between 1 and 3")
        return cls(
            mode=mode,
            api_key=api_key,
            base_url=setting(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ).rstrip("/"),
            transcription_model=setting(
                "OPENROUTER_TRANSCRIPTION_MODEL", "openai/whisper-large-v3-turbo"
            ),
            vision_model=setting(
                "OPENROUTER_VISION_MODEL", "google/gemini-2.5-flash"
            ),
            max_cost_usd=max_cost,
            request_cost_guard_usd=request_guard,
            frame_count=frame_count,
            timeout_seconds=int(setting("OPENROUTER_TIMEOUT_SECONDS", "90")),
            retry_attempts=retries,
            app_name=setting("OPENROUTER_APP_NAME", "MT Auto Music Karaoke Studio"),
        )


@dataclass(slots=True)
class OpenRouterSpendLedger:
    limit_usd: float
    spent_usd: float = 0.0
    requests: list[dict[str, object]] = field(default_factory=list)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.limit_usd - self.spent_usd)

    def can_start(self, request_guard_usd: float) -> bool:
        return self.remaining_usd >= request_guard_usd

    def record(self, *, operation: str, model: str, cost_usd: float) -> None:
        if cost_usd < 0:
            raise ValueError("OpenRouter reported a negative cost")
        projected = self.spent_usd + cost_usd
        if projected > self.limit_usd + 1e-9:
            raise RuntimeError(
                f"OpenRouter song budget exceeded: ${projected:.6f} > ${self.limit_usd:.6f}"
            )
        self.spent_usd = projected
        self.requests.append(
            {"operation": operation, "model": model, "cost_usd": cost_usd}
        )

    def to_primitive(self) -> dict[str, object]:
        return {
            "limit_usd": self.limit_usd,
            "spent_usd": round(self.spent_usd, 8),
            "remaining_usd": round(self.remaining_usd, 8),
            "requests": list(self.requests),
        }


def should_use_openrouter_transcription(
    mode: OpenRouterMode,
    *,
    timeline_status: str,
    asr_window_ratio: float,
    alignment_review_count: int,
) -> tuple[bool, bool]:
    """Return (use_cloud, auto_triggered) from deterministic local evidence."""
    auto_triggered = (
        timeline_status == "BLOCKED"
        or asr_window_ratio < 0.75
        or alignment_review_count > 0
    )
    return (
        mode is OpenRouterMode.ALWAYS
        or (mode is OpenRouterMode.AUTO and auto_triggered),
        auto_triggered,
    )
