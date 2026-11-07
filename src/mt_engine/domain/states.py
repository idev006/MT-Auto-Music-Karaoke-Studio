"""Typed state machines and branch aggregation rules from the architecture SSOT."""

from __future__ import annotations

from enum import StrEnum


class BatchState(StrEnum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ISSUES = "COMPLETED_WITH_ISSUES"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"


class JobState(StrEnum):
    DISCOVERED = "DISCOVERED"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    NEEDS_INPUT = "NEEDS_INPUT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"


class RunState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    NEEDS_INPUT = "NEEDS_INPUT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    CANCELLED = "CANCELLED"


class BranchState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    NEEDS_INPUT = "NEEDS_INPUT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class ArtifactState(StrEnum):
    PLANNED = "PLANNED"
    STAGING = "STAGING"
    GENERATED = "GENERATED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    ORPHANED = "ORPHANED"
    SUPERSEDED = "SUPERSEDED"


class ReviewState(StrEnum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class StateTransitionError(ValueError):
    """A requested durable state transition is not part of the approved graph."""


TRANSITIONS: dict[type[StrEnum], dict[StrEnum, frozenset[StrEnum]]] = {
    BatchState: {
        BatchState.NEW: frozenset({BatchState.READY, BatchState.CANCELLED}),
        BatchState.READY: frozenset({BatchState.RUNNING, BatchState.CANCELLING}),
        BatchState.RUNNING: frozenset(
            {
                BatchState.PAUSING,
                BatchState.COMPLETED,
                BatchState.COMPLETED_WITH_ISSUES,
                BatchState.FAILED,
                BatchState.CANCELLING,
            }
        ),
        BatchState.PAUSING: frozenset({BatchState.PAUSED, BatchState.CANCELLING}),
        BatchState.PAUSED: frozenset({BatchState.RUNNING, BatchState.CANCELLING}),
        BatchState.CANCELLING: frozenset({BatchState.CANCELLED}),
    },
    JobState: {
        JobState.DISCOVERED: frozenset(
            {JobState.READY, JobState.NEEDS_INPUT, JobState.FAILED, JobState.CANCELLED}
        ),
        JobState.READY: frozenset({JobState.QUEUED, JobState.CANCELLING}),
        JobState.QUEUED: frozenset({JobState.RUNNING, JobState.CANCELLING}),
        JobState.RUNNING: frozenset(
            {
                JobState.NEEDS_INPUT,
                JobState.NEEDS_REVIEW,
                JobState.PARTIAL_SUCCESS,
                JobState.COMPLETED,
                JobState.FAILED,
                JobState.CANCELLING,
            }
        ),
        JobState.NEEDS_INPUT: frozenset({JobState.QUEUED, JobState.CANCELLING}),
        JobState.NEEDS_REVIEW: frozenset({JobState.RUNNING, JobState.CANCELLING}),
        JobState.PARTIAL_SUCCESS: frozenset({JobState.QUEUED}),
        JobState.FAILED: frozenset({JobState.QUEUED}),
        JobState.CANCELLED: frozenset({JobState.QUEUED}),
        JobState.CANCELLING: frozenset({JobState.CANCELLED}),
    },
    RunState: {
        RunState.CREATED: frozenset({RunState.QUEUED, RunState.CANCELLED}),
        RunState.QUEUED: frozenset({RunState.RUNNING, RunState.CANCEL_REQUESTED}),
        RunState.RUNNING: frozenset(
            {
                RunState.NEEDS_INPUT,
                RunState.NEEDS_REVIEW,
                RunState.CANCEL_REQUESTED,
                RunState.SUCCEEDED,
                RunState.PARTIAL_SUCCESS,
                RunState.FAILED,
                RunState.INTERRUPTED,
            }
        ),
        RunState.NEEDS_INPUT: frozenset(
            {RunState.RUNNING, RunState.CANCEL_REQUESTED, RunState.FAILED}
        ),
        RunState.NEEDS_REVIEW: frozenset(
            {RunState.RUNNING, RunState.CANCEL_REQUESTED, RunState.FAILED}
        ),
        RunState.CANCEL_REQUESTED: frozenset({RunState.CANCELLED, RunState.FAILED}),
    },
    BranchState: {
        BranchState.NOT_STARTED: frozenset(
            {BranchState.RUNNING, BranchState.SKIPPED, BranchState.CANCELLED}
        ),
        BranchState.RUNNING: frozenset(
            {
                BranchState.NEEDS_INPUT,
                BranchState.NEEDS_REVIEW,
                BranchState.SUCCEEDED,
                BranchState.FAILED,
                BranchState.CANCELLED,
            }
        ),
        BranchState.NEEDS_INPUT: frozenset({BranchState.RUNNING, BranchState.FAILED}),
        BranchState.NEEDS_REVIEW: frozenset({BranchState.RUNNING, BranchState.FAILED}),
    },
    ArtifactState: {
        ArtifactState.PLANNED: frozenset({ArtifactState.STAGING, ArtifactState.REJECTED}),
        ArtifactState.STAGING: frozenset(
            {ArtifactState.GENERATED, ArtifactState.REJECTED, ArtifactState.ORPHANED}
        ),
        ArtifactState.GENERATED: frozenset(
            {ArtifactState.VERIFYING, ArtifactState.REJECTED, ArtifactState.ORPHANED}
        ),
        ArtifactState.VERIFYING: frozenset(
            {ArtifactState.VERIFIED, ArtifactState.REJECTED, ArtifactState.ORPHANED}
        ),
        ArtifactState.VERIFIED: frozenset({ArtifactState.PUBLISHING, ArtifactState.SUPERSEDED}),
        ArtifactState.PUBLISHING: frozenset(
            {ArtifactState.PUBLISHED, ArtifactState.REJECTED, ArtifactState.ORPHANED}
        ),
        ArtifactState.PUBLISHED: frozenset({ArtifactState.SUPERSEDED}),
    },
    ReviewState: {
        ReviewState.DRAFT: frozenset({ReviewState.REVIEW_REQUIRED, ReviewState.SUPERSEDED}),
        ReviewState.REVIEW_REQUIRED: frozenset({ReviewState.IN_REVIEW, ReviewState.SUPERSEDED}),
        ReviewState.IN_REVIEW: frozenset(
            {ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.SUPERSEDED}
        ),
    },
}


def require_transition[State: StrEnum](current: State, target: State) -> None:
    """Raise unless current -> target is an approved transition for the same state type."""
    if type(current) is not type(target):
        raise StateTransitionError(
            f"Cannot transition between {type(current).__name__} and {type(target).__name__}"
        )
    allowed = TRANSITIONS.get(type(current), {}).get(current, frozenset())
    if target not in allowed:
        raise StateTransitionError(f"Illegal transition: {current.value} -> {target.value}")


def aggregate_run(mp3: BranchState, mp4: BranchState) -> RunState:
    """Derive the truthful run state from MP3 and MP4 branch outcomes."""
    if mp3 is BranchState.SUCCEEDED:
        if mp4 is BranchState.SUCCEEDED:
            return RunState.SUCCEEDED
        if mp4 is BranchState.NEEDS_INPUT:
            return RunState.NEEDS_INPUT
        if mp4 is BranchState.NEEDS_REVIEW:
            return RunState.NEEDS_REVIEW
        if mp4 in {BranchState.FAILED, BranchState.CANCELLED, BranchState.SKIPPED}:
            return RunState.PARTIAL_SUCCESS
        return RunState.RUNNING
    if mp3 is BranchState.NEEDS_INPUT:
        return RunState.NEEDS_INPUT
    if mp3 is BranchState.NEEDS_REVIEW:
        return RunState.NEEDS_REVIEW
    if mp3 is BranchState.CANCELLED and mp4 in {
        BranchState.CANCELLED,
        BranchState.NOT_STARTED,
    }:
        return RunState.CANCELLED
    if mp3 is BranchState.FAILED:
        return RunState.FAILED
    return RunState.RUNNING
