"""Add a single account interest description.

Revision ID: f29a6c310b82
Revises: e7f45b290ac1
"""

import sqlalchemy as sa
from alembic import op

revision = "f29a6c310b82"
down_revision = "e7f45b290ac1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("interest_description", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("users", "interest_description")
