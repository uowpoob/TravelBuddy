"""Keep one current progress document per conversation, removing run history.

Revision ID: e7f45b290ac1
Revises: d39a782e1f04
"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e7f45b290ac1"
down_revision = "d39a782e1f04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "planning_progress", postgresql.JSONB(none_as_null=True), nullable=True
        ),
    )
    op.create_check_constraint(
        op.f("ck_conversations_planning_progress_object"),
        "conversations",
        "planning_progress IS NULL OR jsonb_typeof(planning_progress) = 'object'",
    )
    default_nodes = json.dumps(
        {
            name: "pending"
            for name in (
                "understand",
                "clarify",
                "researcher",
                "context_analyst",
                "planner",
                "reviewer",
                "confirm",
                "save",
            )
        }
    )
    # Preserve the latest visible state before removing the append-only history.
    op.execute(
        sa.text("""
        WITH latest AS (
            SELECT DISTINCT ON (conversation_id) id, conversation_id, status, error
            FROM planning_runs ORDER BY conversation_id, created_at DESC, id DESC
        ), node_states AS (
            SELECT DISTINCT ON (e.run_id, e.name) e.run_id, e.name,
                CASE
                    WHEN e.event_type = 'node_completed' THEN 'completed'
                    WHEN e.event_type = 'node_failed' THEN 'failed'
                    WHEN l.status = 'waiting_clarification' AND e.name = 'clarify' THEN 'waiting'
                    WHEN l.status = 'waiting_approval' AND e.name = 'confirm' THEN 'waiting'
                    WHEN l.status = 'running' THEN 'running'
                    ELSE 'failed'
                END AS status
            FROM planning_events e JOIN latest l ON l.id = e.run_id
            WHERE e.event_type IN ('node_started', 'node_completed', 'node_failed')
            ORDER BY e.run_id, e.name, e.sequence DESC
        ), nodes AS (
            SELECT run_id, jsonb_object_agg(name, status) AS node_values
            FROM node_states GROUP BY run_id
        )
        UPDATE conversations c
        SET planning_progress = jsonb_build_object(
            'status', l.status, 'error', l.error,
            'nodes', CAST(:default_nodes AS jsonb) || COALESCE(n.node_values, '{}'::jsonb)
        )
        FROM latest l LEFT JOIN nodes n ON n.run_id = l.id
        WHERE c.id = l.conversation_id
    """).bindparams(default_nodes=default_nodes)
    )
    op.drop_table("planning_events")
    op.drop_table("planning_runs")


def downgrade() -> None:
    # Recreate the prior schema and restore the current state only. Deleted
    # historical runs/events cannot be reconstructed by downgrading.
    from backend.migrations.versions.d39a782e1f04_add_planning_progress import (
        upgrade as recreate_old_tables,
    )

    recreate_old_tables()
    op.execute(
        sa.text("""
        INSERT INTO planning_runs (conversation_id, status, trigger, error, created_at, updated_at, finished_at)
        SELECT id, planning_progress->>'status', 'message', planning_progress->>'error',
            statement_timestamp(), statement_timestamp(),
            CASE WHEN planning_progress->>'status' = 'running' THEN NULL ELSE statement_timestamp() END
        FROM conversations
        WHERE planning_progress IS NOT NULL AND planning_progress->>'status' <> 'idle'
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO planning_events (run_id, sequence, execution_id, event_type, name)
        SELECT r.id, row_number() OVER (PARTITION BY r.id ORDER BY n.key), gen_random_uuid(),
            CASE n.value
                WHEN 'completed' THEN 'node_completed'
                WHEN 'failed' THEN 'node_failed'
                ELSE 'node_started'
            END, n.key
        FROM planning_runs r JOIN conversations c ON c.id = r.conversation_id
        CROSS JOIN LATERAL jsonb_each_text(c.planning_progress->'nodes') n
        WHERE n.value <> 'pending'
    """)
    )
    op.execute(
        sa.text("""
        UPDATE planning_runs r
        SET last_event_sequence = (SELECT count(*) FROM planning_events e WHERE e.run_id = r.id)
    """)
    )
    op.drop_constraint(
        op.f("ck_conversations_planning_progress_object"),
        "conversations",
        type_="check",
    )
    op.drop_column("conversations", "planning_progress")
