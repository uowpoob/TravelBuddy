"""Create planning execution runs and replayable public events.

Revision ID: d39a782e1f04
Revises: c6a1e7d4b930
"""

import sqlalchemy as sa
from alembic import op

revision = "d39a782e1f04"
down_revision = "c6a1e7d4b930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep historical migration values explicit, independent of application enums.
    op.create_table(
        "planning_runs",
        sa.Column(
            "id",
            sa.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("trigger", sa.String(16), server_default="message", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "last_event_sequence",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'waiting_clarification', 'waiting_approval', 'completed', 'failed')",
            name=op.f("ck_planning_runs_status_valid"),
        ),
        sa.CheckConstraint(
            "trigger IN ('message', 'resume', 'retry')",
            name=op.f("ck_planning_runs_trigger_valid"),
        ),
        sa.CheckConstraint(
            "last_event_sequence >= 0",
            name=op.f("ck_planning_runs_event_sequence_nonnegative"),
        ),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR (status <> 'running' AND finished_at IS NOT NULL)",
            name=op.f("ck_planning_runs_finish_matches_status"),
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= created_at",
            name=op.f("ck_planning_runs_finish_after_creation"),
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name=op.f("ck_planning_runs_expiry_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_planning_runs_conversation_id_conversations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planning_runs")),
    )
    op.create_index(
        "ix_planning_runs_conversation_created",
        "planning_runs",
        ["conversation_id", "created_at", "id"],
    )
    op.create_index(
        "uq_planning_runs_active_conversation",
        "planning_runs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_table(
        "planning_events",
        sa.Column("run_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("sequence", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("execution_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence >= 1", name=op.f("ck_planning_events_sequence_positive")
        ),
        sa.CheckConstraint(
            "event_type IN ('run_started', 'run_waiting_clarification', 'run_waiting_approval', "
            "'run_completed', 'run_failed', 'node_started', 'node_completed', 'node_failed', "
            "'tool_started', 'tool_completed', 'tool_failed')",
            name=op.f("ck_planning_events_event_type_valid"),
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name=op.f("ck_planning_events_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["planning_runs.id"],
            name=op.f("fk_planning_events_run_id_planning_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "sequence", name=op.f("pk_planning_events")),
    )


def downgrade() -> None:
    op.drop_table("planning_events")
    op.drop_index("uq_planning_runs_active_conversation", table_name="planning_runs")
    op.drop_index("ix_planning_runs_conversation_created", table_name="planning_runs")
    op.drop_table("planning_runs")
