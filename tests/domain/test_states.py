import pytest

from mt_engine.domain.states import (
    ArtifactState,
    BatchState,
    BranchState,
    JobState,
    ReviewState,
    RunState,
    StateTransitionError,
    aggregate_run,
    require_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BatchState.NEW, BatchState.READY),
        (BatchState.RUNNING, BatchState.PAUSING),
        (BatchState.PAUSING, BatchState.PAUSED),
        (JobState.DISCOVERED, JobState.READY),
        (JobState.READY, JobState.QUEUED),
        (JobState.FAILED, JobState.QUEUED),
        (RunState.CREATED, RunState.QUEUED),
        (RunState.RUNNING, RunState.NEEDS_REVIEW),
        (RunState.CANCEL_REQUESTED, RunState.CANCELLED),
        (BranchState.NOT_STARTED, BranchState.RUNNING),
        (ArtifactState.STAGING, ArtifactState.GENERATED),
        (ArtifactState.VERIFIED, ArtifactState.PUBLISHING),
        (ReviewState.REVIEW_REQUIRED, ReviewState.IN_REVIEW),
    ],
)
def test_legal_transitions(current, target):
    require_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BatchState.COMPLETED, BatchState.RUNNING),
        (JobState.COMPLETED, JobState.RUNNING),
        (RunState.FAILED, RunState.RUNNING),
        (RunState.CANCELLED, RunState.SUCCEEDED),
        (BranchState.SUCCEEDED, BranchState.RUNNING),
        (ArtifactState.PUBLISHED, ArtifactState.STAGING),
        (ReviewState.APPROVED, ReviewState.IN_REVIEW),
    ],
)
def test_illegal_or_terminal_transitions_are_rejected(current, target):
    with pytest.raises(StateTransitionError):
        require_transition(current, target)


@pytest.mark.parametrize(
    ("mp3", "mp4", "expected"),
    [
        (BranchState.SUCCEEDED, BranchState.SUCCEEDED, RunState.SUCCEEDED),
        (BranchState.SUCCEEDED, BranchState.FAILED, RunState.PARTIAL_SUCCESS),
        (BranchState.SUCCEEDED, BranchState.NEEDS_INPUT, RunState.NEEDS_INPUT),
        (BranchState.SUCCEEDED, BranchState.NEEDS_REVIEW, RunState.NEEDS_REVIEW),
        (BranchState.FAILED, BranchState.SUCCEEDED, RunState.FAILED),
        (BranchState.CANCELLED, BranchState.NOT_STARTED, RunState.CANCELLED),
        (BranchState.RUNNING, BranchState.NOT_STARTED, RunState.RUNNING),
    ],
)
def test_branch_aggregation_is_truthful(mp3, mp4, expected):
    assert aggregate_run(mp3, mp4) is expected
