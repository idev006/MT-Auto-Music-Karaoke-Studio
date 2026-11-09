from pathlib import Path

import pytest

from mt_engine.production.openrouter_config import (
    OpenRouterConfigError,
    OpenRouterMode,
    OpenRouterSpendLedger,
    should_use_openrouter_transcription,
)
from mt_engine.production.openrouter_vision import (
    OpenRouterVisionConfig,
    _request_payload,
)


def test_openrouter_config_is_disabled_without_local_file(tmp_path: Path):
    config = OpenRouterVisionConfig.from_file(tmp_path / "missing.env")

    assert config.enabled is False
    assert config.mode is OpenRouterMode.OFF
    assert config.frame_count == 12
    assert config.retry_attempts == 2


def test_openrouter_enabled_requires_key(tmp_path: Path):
    config_file = tmp_path / "openrouter.env"
    config_file.write_text("OPENROUTER_VISION_QC_ENABLED=true\n", encoding="utf-8")

    with pytest.raises(OpenRouterConfigError, match="API_KEY is empty"):
        OpenRouterVisionConfig.from_file(config_file)


def test_openrouter_supports_three_modes_and_enforces_cost_ceiling(tmp_path: Path):
    config_file = tmp_path / "openrouter.env"
    config_file.write_text(
        "OPENROUTER_MODE=auto\n"
        "OPENROUTER_API_KEY=secret\n"
        "OPENROUTER_MAX_COST_USD_PER_SONG=0.20\n",
        encoding="utf-8",
    )

    config = OpenRouterVisionConfig.from_file(config_file)
    ledger = OpenRouterSpendLedger(config.max_cost_usd)
    ledger.record(operation="transcription", model="test", cost_usd=0.19)

    assert config.mode is OpenRouterMode.AUTO
    assert config.enabled is True
    assert ledger.can_start(config.request_cost_guard_usd) is False
    with pytest.raises(RuntimeError, match="budget exceeded"):
        ledger.record(operation="vision_qc", model="test", cost_usd=0.02)


def test_openrouter_rejects_budget_over_twenty_cents(tmp_path: Path):
    config_file = tmp_path / "openrouter.env"
    config_file.write_text(
        "OPENROUTER_MODE=always\n"
        "OPENROUTER_API_KEY=secret\n"
        "OPENROUTER_MAX_COST_USD_PER_SONG=0.21\n",
        encoding="utf-8",
    )

    with pytest.raises(OpenRouterConfigError, match="at most 0.20"):
        OpenRouterVisionConfig.from_file(config_file)


@pytest.mark.parametrize(
    ("mode", "status", "coverage", "review_count", "expected"),
    [
        (OpenRouterMode.OFF, "BLOCKED", 0.2, 10, False),
        (OpenRouterMode.AUTO, "PASS", 0.9, 0, False),
        (OpenRouterMode.AUTO, "BLOCKED", 0.9, 0, True),
        (OpenRouterMode.AUTO, "PASS", 0.7, 0, True),
        (OpenRouterMode.AUTO, "PASS", 0.9, 1, True),
        (OpenRouterMode.ALWAYS, "PASS", 0.9, 0, True),
    ],
)
def test_openrouter_transcription_mode_policy(
    mode, status, coverage, review_count, expected
):
    use_cloud, _auto_triggered = should_use_openrouter_transcription(
        mode,
        timeline_status=status,
        asr_window_ratio=coverage,
        alignment_review_count=review_count,
    )

    assert use_cloud is expected


def test_openrouter_payload_contains_expected_text_and_base64_image(tmp_path: Path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"image-bytes")
    config = OpenRouterVisionConfig(mode=OpenRouterMode.ALWAYS, api_key="secret")

    payload = _request_payload(config, frame, "เนื้อเพลงที่คาดหวัง")

    assert "เนื้อเพลงที่คาดหวัง".encode() in payload
    assert b"data:image/png;base64," in payload
    assert b"secret" not in payload
