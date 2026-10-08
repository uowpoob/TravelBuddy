"""Create users, conversations, and confirmed itinerary versions.

Revision ID: 118ebaead2fc
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "118ebaead2fc"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(password_hash)) > 0",
            name=op.f("ck_users_password_hash_not_blank"),
        ),
        sa.CheckConstraint(
            "length(btrim(username)) > 0", name=op.f("ck_users_username_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), server_default="新旅行", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name=op.f("ck_conversations_title_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversations_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        "ix_conversations_user_id_updated_at",
        "conversations",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_table(
        "itineraries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("conversation_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("destination_city", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column(
            "trip_request",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "itinerary",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "candidates",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "travel_constraints",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "review_result",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(candidates) = 'object'",
            name=op.f("ck_itineraries_candidates_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(itinerary) = 'object'",
            name=op.f("ck_itineraries_itinerary_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(trip_request) = 'object'",
            name=op.f("ck_itineraries_trip_request_object"),
        ),
        sa.CheckConstraint(
            "review_result IS NULL OR jsonb_typeof(review_result) = 'object'",
            name=op.f("ck_itineraries_review_result_object"),
        ),
        sa.CheckConstraint(
            "travel_constraints IS NULL OR jsonb_typeof(travel_constraints) = 'object'",
            name=op.f("ck_itineraries_travel_constraints_object"),
        ),
        sa.CheckConstraint(
            "days BETWEEN 1 AND 5", name=op.f("ck_itineraries_days_range")
        ),
        sa.CheckConstraint(
            "length(btrim(destination_city)) > 0",
            name=op.f("ck_itineraries_destination_city_not_blank"),
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name=op.f("ck_itineraries_title_not_blank")
        ),
        sa.CheckConstraint(
            "version >= 1", name=op.f("ck_itineraries_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_itineraries_conversation_id_conversations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itineraries")),
        sa.UniqueConstraint(
            "conversation_id",
            "version",
            name=op.f("uq_itineraries_conversation_id_version"),
        ),
    )


def downgrade() -> None:
    op.drop_table("itineraries")
    op.drop_index("ix_conversations_user_id_updated_at", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("users")
