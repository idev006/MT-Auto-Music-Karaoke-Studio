"""SQLAlchemy models for the operational source of truth."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative model registry used by Alembic autogeneration."""


class TimestampMixin:
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Configuration(TimestampMixin, Base):
    __tablename__ = "configurations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    config_id: Mapped[str] = mapped_column(ForeignKey("configurations.id", ondelete="RESTRICT"))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    source_root_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_relpath: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("batch_id", "source_root_id", "source_relpath"),)


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    root_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relpath: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (UniqueConstraint("job_id", "role", "root_id", "relpath"),)


class LyricsRevision(TimestampMixin, Base):
    __tablename__ = "lyrics_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    source_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_json: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint("job_id", "revision"),)


class TimingRevision(TimestampMixin, Base):
    __tablename__ = "timing_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    lyrics_revision_id: Mapped[str] = mapped_column(
        ForeignKey("lyrics_revisions.id", ondelete="RESTRICT")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    timeline_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint("job_id", "revision"),)


class WorkflowStep(TimestampMixin, Base):
    __tablename__ = "workflow_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    latest_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("job_id", "kind"),)


class ErrorRecord(TimestampMixin, Base):
    __tablename__ = "errors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    step_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message_for_user: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    technical_details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)


class StepAttempt(Base):
    __tablename__ = "step_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("workflow_steps.id", ondelete="CASCADE"))
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_id: Mapped[str | None] = mapped_column(ForeignKey("errors.id"), nullable=True)
    worker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("step_id", "attempt_number"),)


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    branch: Mapped[str] = mapped_column(String(16), nullable=False)
    root_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relpath: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (UniqueConstraint("root_id", "relpath"),)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    emitted_at: Mapped[str] = mapped_column(String(32), nullable=False)
    delivered_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    __table_args__ = (Index("ix_outbox_events_pending", "delivered_at", "seq"),)


class WorkerLease(Base):
    __tablename__ = "worker_leases"
    step_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), primary_key=True
    )
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("step_attempts.id", ondelete="CASCADE"), unique=True
    )
    worker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_expiration: Mapped[str] = mapped_column(String(32), nullable=False)
    heartbeat: Mapped[str] = mapped_column(String(32), nullable=False)


class SchemaMetadata(Base):
    __tablename__ = "schema_metadata"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
