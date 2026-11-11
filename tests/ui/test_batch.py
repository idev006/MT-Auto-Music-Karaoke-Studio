import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from mt_engine.application import (
    TERMINAL_STATES,
    ApplicationOrchestrator,
    BatchJobState,
    BatchSettings,
    EngineEventKind,
)


@dataclass(frozen=True)
class FakeResult:
    target_dir: Path
    state: str = "SUCCEEDED"


def _settings(tmp_path: Path) -> BatchSettings:
    ffmpeg_root = tmp_path / "ffmpeg"
    (ffmpeg_root / "bin").mkdir(parents=True, exist_ok=True)
    (ffmpeg_root / "bin" / "ffmpeg.exe").touch()
    (ffmpeg_root / "bin" / "ffprobe.exe").touch()
    fonts = tmp_path / "fonts"
    fonts.mkdir(exist_ok=True)
    config = tmp_path / "openrouter.env"
    config.touch()
    return BatchSettings(
        tmp_path / "outputs",
        ffmpeg_root,
        fonts,
        openrouter_config=config,
        accept_unreviewed_timing=True,
    )


def _wait_terminal(orchestrator: ApplicationOrchestrator, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshots = orchestrator.snapshots()
        if snapshots and all(item.state in TERMINAL_STATES for item in snapshots):
            return snapshots
        time.sleep(0.01)
    raise AssertionError("Batch did not become terminal")


def test_worker_limit_and_folder_isolation(tmp_path: Path):
    lock = threading.Lock()
    active = 0
    maximum_active = 0
    seen: list[Path] = []

    def producer(source, settings, progress):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
            seen.append(source)
        progress(25, "Analyzing")
        time.sleep(0.04)
        progress(80, "Rendering")
        with lock:
            active -= 1
        return FakeResult(settings.dest_root / source.name)

    folders = []
    for index in range(5):
        folder = tmp_path / f"song-{index}"
        folder.mkdir()
        folders.append(folder)
    coordinator = ApplicationOrchestrator(producer)
    assert len(coordinator.add(tuple(folders))) == 5
    coordinator.start(_settings(tmp_path), max_workers=2)

    snapshots = _wait_terminal(coordinator)

    assert maximum_active == 2
    assert set(seen) == {folder.resolve() for folder in folders}
    assert all(item.state == BatchJobState.SUCCEEDED for item in snapshots)
    assert all(item.progress == 100 for item in snapshots)


def test_duplicate_active_source_is_not_enqueued_twice(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()
    coordinator = ApplicationOrchestrator(lambda source, settings, progress: None)

    assert coordinator.add((source, source)) == ("J0001",)
    assert coordinator.add((source,)) == ()


def test_cancelled_queued_jobs_never_enter_producer(tmp_path: Path):
    release = threading.Event()
    entered: list[str] = []

    def producer(source, settings, progress):
        entered.append(source.name)
        release.wait(timeout=2)
        progress(50, "Resuming")
        return FakeResult(settings.dest_root / source.name)

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    coordinator = ApplicationOrchestrator(producer)
    first_id, second_id = coordinator.add((first, second))
    coordinator.start(_settings(tmp_path), max_workers=1)
    deadline = time.monotonic() + 2
    while not entered and time.monotonic() < deadline:
        time.sleep(0.01)
    coordinator.cancel((second_id,))
    release.set()

    snapshots = _wait_terminal(coordinator)
    states = {item.job_id: item.state for item in snapshots}
    assert entered == ["first"]
    assert states[first_id] == BatchJobState.SUCCEEDED
    assert states[second_id] == BatchJobState.CANCELLED


def test_executor_is_released_and_a_new_batch_can_start(tmp_path: Path):
    def producer(source, settings, progress):
        return FakeResult(settings.dest_root / source.name)

    coordinator = ApplicationOrchestrator(producer)
    first = tmp_path / "first"
    first.mkdir()
    coordinator.add((first,))
    coordinator.start(_settings(tmp_path), max_workers=1)
    _wait_terminal(coordinator)

    second = tmp_path / "second"
    second.mkdir()
    coordinator.add((second,))
    coordinator.start(_settings(tmp_path), max_workers=1)
    snapshots = _wait_terminal(coordinator)

    assert snapshots[-1].state == BatchJobState.SUCCEEDED


def test_terminal_job_can_be_removed_before_next_batch(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()
    coordinator = ApplicationOrchestrator(
        lambda source, settings, progress: FakeResult(settings.dest_root / source.name)
    )
    job_id = coordinator.add((source,))[0]
    coordinator.start(_settings(tmp_path), max_workers=1)
    _wait_terminal(coordinator)

    coordinator.remove_queued((job_id,))

    assert coordinator.snapshots() == ()


def test_queued_jobs_do_not_count_as_running(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()
    coordinator = ApplicationOrchestrator(lambda source, settings, progress: object())

    coordinator.add((source,))

    assert not coordinator.is_running()


def test_queue_cannot_mutate_during_active_batch(tmp_path: Path):
    entered = threading.Event()
    release = threading.Event()

    def producer(source, settings, progress):
        entered.set()
        release.wait(timeout=2)
        return FakeResult(settings.dest_root / source.name)

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    coordinator = ApplicationOrchestrator(producer)
    first_id = coordinator.add((first,))[0]
    coordinator.start(_settings(tmp_path), max_workers=1)
    assert entered.wait(timeout=2)

    with pytest.raises(RuntimeError):
        coordinator.add((second,))
    with pytest.raises(RuntimeError):
        coordinator.remove_queued((first_id,))

    release.set()
    _wait_terminal(coordinator)


def test_cpu_budget_rejects_oversubscription(tmp_path: Path, monkeypatch):
    source = tmp_path / "song"
    source.mkdir()
    coordinator = ApplicationOrchestrator(lambda source, settings, progress: object())
    coordinator.add((source,))
    monkeypatch.setattr("mt_engine.application.orchestrator.os.cpu_count", lambda: 2)

    with pytest.raises(ValueError, match="must not exceed 2"):
        coordinator.start(_settings(tmp_path), max_workers=2)


def test_batch_requires_review_lock_or_explicit_diagnostic_mode(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()
    coordinator = ApplicationOrchestrator(lambda source, settings, progress: object())
    coordinator.add((source,))

    with pytest.raises(ValueError, match="diagnostic timing"):
        coordinator.start(
            replace(_settings(tmp_path), accept_unreviewed_timing=False), max_workers=1
        )


def test_engine_events_are_ordered_and_view_owns_business_projection(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()
    coordinator = ApplicationOrchestrator(
        lambda source, settings, progress: FakeResult(settings.dest_root / source.name)
    )

    coordinator.add((source,))
    queued_view = coordinator.view()
    events, cursor = coordinator.events_since(0)
    assert queued_view.can_start
    assert queued_view.active_jobs == 1
    assert [event.sequence for event in events] == list(range(1, cursor + 1))
    assert events[-1].kind == EngineEventKind.QUEUE_CHANGED

    coordinator.start(_settings(tmp_path), max_workers=1)
    _wait_terminal(coordinator)
    final_events, final_cursor = coordinator.events_since(cursor)
    final_view = coordinator.view()

    assert final_cursor > cursor
    assert final_view.terminal_jobs == 1
    assert final_view.active_jobs == 0
    assert not final_view.can_start
    assert final_events[-1].kind == EngineEventKind.BATCH_FINISHED


def test_structured_worker_metrics_reach_snapshot_and_event(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()

    def producer(source, settings, progress):
        progress(85, "FFmpeg render 45%", {"fps": "29.97", "speed": "1.2x"})
        return FakeResult(settings.dest_root / source.name)

    coordinator = ApplicationOrchestrator(producer)
    coordinator.add((source,))
    coordinator.start(_settings(tmp_path), max_workers=1)
    _wait_terminal(coordinator)
    events, _cursor = coordinator.events_since(0)

    progress_event = next(
        event
        for event in events
        if event.kind == EngineEventKind.JOB_PROGRESS and ("speed", "1.2x") in event.data
    )
    assert ("fps", "29.97") in progress_event.data


def test_worker_failure_records_stage_traceback_and_log(tmp_path: Path):
    source = tmp_path / "song"
    source.mkdir()
    settings = _settings(tmp_path)
    state_dir = settings.dest_root / source.name / "production_data"
    state_dir.mkdir(parents=True)
    (state_dir / "run_state.json").write_text(
        '{"stage":"QC"}', encoding="utf-8"
    )

    def failing_producer(source, settings, progress):
        raise ValueError("frame inspection failed")

    coordinator = ApplicationOrchestrator(failing_producer)
    coordinator.add((source,))
    coordinator.start(settings, max_workers=1)
    snapshot = _wait_terminal(coordinator)[0]

    assert snapshot.state == BatchJobState.FAILED
    assert snapshot.detail == "Failed at QC"
    assert snapshot.error == "[QC] ValueError: frame inspection failed"
    assert "Traceback" in (snapshot.error_detail or "")
    failure_log = state_dir / "failure.log"
    assert "stage=QC" in failure_log.read_text(encoding="utf-8")
