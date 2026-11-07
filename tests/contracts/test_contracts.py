from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from mt_engine.contracts import (
    CONTRACT_SCHEMA_VERSION,
    ArtifactManifest,
    DomainEvent,
    ToolRequest,
    ToolResult,
    ToolResultStatus,
    to_primitive,
)


def test_tool_contract_round_trip_shape_is_versioned_and_fenced():
    request = ToolRequest(
        schema_version=CONTRACT_SCHEMA_VERSION,
        job_id="job-1",
        run_id="run-2",
        owner_epoch=3,
        operation_id="operation-4",
        input_hash="a" * 64,
        config_hash="b" * 64,
        deadline_utc=datetime(2026, 11, 7, 8, 30, tzinfo=UTC),
        payload={"source": {"root_id": "source", "relpath": "เพลง/song.mp3"}},
    )

    assert to_primitive(request) == {
        "schema_version": 1,
        "job_id": "job-1",
        "run_id": "run-2",
        "owner_epoch": 3,
        "operation_id": "operation-4",
        "input_hash": "a" * 64,
        "config_hash": "b" * 64,
        "deadline_utc": "2026-11-07T08:30:00Z",
        "payload": {"source": {"root_id": "source", "relpath": "เพลง/song.mp3"}},
    }

    with pytest.raises(FrozenInstanceError):
        request.owner_epoch = 4  # type: ignore[misc]


def test_tool_result_and_artifact_carry_stale_result_fencing_identity():
    artifact = ArtifactManifest(
        schema_version=1,
        artifact_id="artifact-1",
        job_id="job-1",
        run_id="run-1",
        owner_epoch=7,
        operation_id="operation-1",
        branch="MP3",
        root_id="output",
        relpath="song/song_with_cover.mp3",
        sha256="c" * 64,
        input_hash="a" * 64,
        config_hash="b" * 64,
        validation={"audio_frames_unchanged": True},
        tool_versions={"mutagen": "test"},
    )
    result = ToolResult(
        schema_version=1,
        job_id="job-1",
        run_id="run-1",
        owner_epoch=7,
        operation_id="operation-1",
        status=ToolResultStatus.SUCCEEDED,
        artifacts=(artifact,),
        metrics={},
        error=None,
    )

    encoded = to_primitive(result)
    assert encoded["status"] == "SUCCEEDED"
    assert encoded["artifacts"][0]["owner_epoch"] == 7
    assert encoded["artifacts"][0]["operation_id"] == "operation-1"


def test_domain_event_contains_replay_and_correlation_fields():
    event = DomainEvent(
        schema_version=1,
        event_id="event-1",
        sequence=42,
        event_type="job_run.started",
        occurred_at_utc=datetime(2026, 11, 7, tzinfo=UTC),
        correlation_id="correlation-1",
        batch_id="batch-1",
        job_id="job-1",
        run_id="run-1",
        owner_epoch=1,
        payload={},
    )

    assert to_primitive(event)["sequence"] == 42
    assert to_primitive(event)["occurred_at_utc"] == "2026-11-07T00:00:00Z"
