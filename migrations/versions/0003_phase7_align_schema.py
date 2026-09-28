"""Phase 7 align interaction & distribution schema

Revises views, saves, user_interests, distribution_posts to concrete content_id,
preserves existing 112 views, and adds users password reset columns.

Revision ID: 0003_phase7_align
Revises: 0002_phase7_brands
Create Date: 2026-08-26
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0003_phase7_align"
down_revision = "0002_phase7_brands"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()

    # 1. users: add password reset columns
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_reset_token", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("password_reset_sent_at", TIMESTAMP(timezone=True), nullable=True))

    # 2. views: preserve existing 112 content views and convert to concrete content_id
    conn.execute(sa.text("ALTER TABLE views DROP CONSTRAINT IF EXISTS unique_view"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_views_target"))

    with op.batch_alter_table("views") as batch_op:
        batch_op.add_column(sa.Column("content_id", sa.Integer(), nullable=True))

    conn.execute(sa.text("""
        UPDATE views SET content_id = target_id
        WHERE target_type = 'content'
    """))
    conn.execute(sa.text("DELETE FROM views WHERE content_id IS NULL"))

    with op.batch_alter_table("views") as batch_op:
        batch_op.alter_column("content_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_views_content_id", "contents", ["content_id"], ["id"],
            ondelete="CASCADE"
        )
        batch_op.drop_column("target_type")
        batch_op.drop_column("target_id")

    op.create_index("ix_views_content", "views", ["content_id"])

    # 3. saves (0 rows): restructure to content_id
    conn.execute(sa.text("ALTER TABLE saves DROP CONSTRAINT IF EXISTS uq_user_save_collection"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_save_target"))

    with op.batch_alter_table("saves") as batch_op:
        batch_op.drop_column("target_type")
        batch_op.drop_column("target_id")
        batch_op.add_column(
            sa.Column(
                "content_id", sa.Integer(),
                sa.ForeignKey("contents.id", ondelete="CASCADE"),
                nullable=False,
                server_default="0",
            )
        )
    with op.batch_alter_table("saves") as batch_op:
        batch_op.alter_column("content_id", server_default=None)

    op.create_unique_constraint(
        "uq_user_save_collection", "saves", ["user_id", "content_id", "collection_name"]
    )
    op.create_index("ix_saves_content", "saves", ["content_id"])

    # 4. user_interests (0 rows): restructure to content_id
    conn.execute(sa.text("ALTER TABLE user_interests DROP CONSTRAINT IF EXISTS uq_user_target"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_user_interest_user_target"))

    with op.batch_alter_table("user_interests") as batch_op:
        batch_op.drop_column("target_type")
        batch_op.drop_column("target_id")
        batch_op.add_column(
            sa.Column(
                "content_id", sa.Integer(),
                sa.ForeignKey("contents.id", ondelete="CASCADE"),
                nullable=False,
                server_default="0",
            )
        )
    with op.batch_alter_table("user_interests") as batch_op:
        batch_op.alter_column("content_id", server_default=None)

    op.create_unique_constraint(
        "uq_user_content_interest", "user_interests", ["user_id", "content_id"]
    )
    op.create_index("ix_user_interest_lookup", "user_interests", ["user_id", "content_id"])

    # 5. distribution_posts (0 rows): restructure to content_id
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_distribution_post_target"))

    with op.batch_alter_table("distribution_posts") as batch_op:
        batch_op.drop_column("source_target_type")
        batch_op.drop_column("source_target_id")
        batch_op.add_column(
            sa.Column(
                "content_id", sa.Integer(),
                sa.ForeignKey("contents.id", ondelete="CASCADE"),
                nullable=False,
                server_default="0",
            )
        )
    with op.batch_alter_table("distribution_posts") as batch_op:
        batch_op.alter_column("content_id", server_default=None)

    op.create_index("ix_distribution_posts_content", "distribution_posts", ["content_id"])

def downgrade() -> None:
    pass
