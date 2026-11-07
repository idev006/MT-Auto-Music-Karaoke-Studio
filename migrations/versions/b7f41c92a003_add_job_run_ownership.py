"""add job run ownership

Revision ID: b7f41c92a003
Revises: 106a0b13ddd3
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f41c92a003"
down_revision: str | Sequence[str] | None = "106a0b13ddd3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consumer_cursors",
        sa.Column("consumer_id", sa.String(length=128), nullable=False),
        sa.Column("last_seq", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("consumer_id"),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=True),
        sa.Column("owner_epoch", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at_ms", sa.Integer(), nullable=True),
        sa.Column("heartbeat_at_ms", sa.Integer(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("finished_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "run_number"),
    )
    op.create_index("ix_job_runs_queue", "job_runs", ["state", "created_at"])
    op.create_index(
        "uq_job_runs_one_active_per_job",
        "job_runs",
        ["job_id"],
        unique=True,
        sqlite_where=sa.text(
            "state IN ('CREATED','QUEUED','RUNNING','NEEDS_INPUT','NEEDS_REVIEW',"
            "'CANCEL_REQUESTED')"
        ),
    )
    op.create_table(
        "job_run_branches",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("branch", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["job_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "branch"),
    )
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("active_run_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_jobs_active_run_id", "job_runs", ["active_run_id"], ["id"])
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("operation_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("owner_epoch", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("input_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("config_hash", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_artifacts_run_id", "job_runs", ["run_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.drop_constraint("fk_artifacts_run_id", type_="foreignkey")
        batch_op.drop_column("config_hash")
        batch_op.drop_column("input_hash")
        batch_op.drop_column("owner_epoch")
        batch_op.drop_column("operation_id")
        batch_op.drop_column("run_id")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("fk_jobs_active_run_id", type_="foreignkey")
        batch_op.drop_column("active_run_id")
    op.drop_table("job_run_branches")
    op.drop_index("uq_job_runs_one_active_per_job", table_name="job_runs")
    op.drop_index("ix_job_runs_queue", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_table("consumer_cursors")
