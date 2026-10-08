"""Add a stable key for retrying confirmed itinerary saves.

Revision ID: c6a1e7d4b930
Revises: 118ebaead2fc
"""

import sqlalchemy as sa
from alembic import op

revision = "c6a1e7d4b930"
down_revision = "118ebaead2fc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The default also backfills existing snapshots with independent keys.
    op.add_column(
        "itineraries",
        sa.Column(
            "save_key",
            sa.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        op.f("uq_itineraries_conversation_id_save_key"),
        "itineraries",
        ["conversation_id", "save_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_itineraries_conversation_id_save_key"),
        "itineraries",
        type_="unique",
    )
    op.drop_column("itineraries", "save_key")
