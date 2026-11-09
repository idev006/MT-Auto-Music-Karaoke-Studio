from pathlib import Path

import pytest

from mt_engine.production.openrouter_vision import (
    OpenRouterConfigError,
    OpenRouterVisionConfig,
    _request_payload,
)


def test_openrouter_config_is_disabled_without_local_file(tmp_path: Path):
    config = OpenRouterVisionConfig.from_file(tmp_path / "missing.env")

    assert config.enabled is False
    assert config.frame_count == 12
    assert config.retry_attempts == 3


def test_openrouter_enabled_requires_key(tmp_path: Path):
    config_file = tmp_path / "openrouter.env"
    config_file.write_text("OPENROUTER_VISION_QC_ENABLED=true\n", encoding="utf-8")

    with pytest.raises(OpenRouterConfigError, match="API_KEY is empty"):
        OpenRouterVisionConfig.from_file(config_file)


def test_openrouter_payload_contains_expected_text_and_base64_image(tmp_path: Path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"image-bytes")
    config = OpenRouterVisionConfig(enabled=True, api_key="secret")

    payload = _request_payload(config, frame, "เนื้อเพลงที่คาดหวัง")

    assert "เนื้อเพลงที่คาดหวัง".encode() in payload
    assert b"data:image/png;base64," in payload
    assert b"secret" not in payload
