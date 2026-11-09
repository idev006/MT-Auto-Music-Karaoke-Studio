import json
from pathlib import Path

from mt_engine.production.openrouter_config import (
    OpenRouterConfig,
    OpenRouterMode,
    OpenRouterSpendLedger,
)
from mt_engine.production.openrouter_transcription import transcribe_openrouter


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "language": "th",
                "duration": 2.0,
                "segments": [{"start": 0.2, "end": 1.8, "text": "สวัสดี"}],
                "words": [
                    {"start": 0.2, "end": 1.8, "word": "สวัสดี", "probability": 0.9}
                ],
                "usage": {"cost": 0.003},
            }
        ).encode()


def test_transcription_records_provider_cost(monkeypatch, tmp_path: Path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"audio")
    config = OpenRouterConfig(mode=OpenRouterMode.ALWAYS, api_key="secret")
    ledger = OpenRouterSpendLedger(0.20)
    monkeypatch.setattr(
        "mt_engine.production.openrouter_transcription.urlopen",
        lambda *_args, **_kwargs: _Response(),
    )

    transcript, info = transcribe_openrouter(config, ledger, audio)

    assert transcript[0].text == "สวัสดี"
    assert transcript[0].words[0].text == "สวัสดี"
    assert info["cost_usd"] == 0.003
    assert ledger.spent_usd == 0.003
