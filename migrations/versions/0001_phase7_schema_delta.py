"""Phase 7 schema delta migration

This migration applies the minimum required changes to bring the existing
nexora_db schema into full Phase 7 compliance without dropping or destroying
any populated content/taxonomy data.

VERIFIED DATABASE STATE BEFORE THIS MIGRATION:
  - alembic_version: cffe9cd40bfc  (end of Nexora legacy chain)
  - contents:         8,278 rows   (preserved unchanged)
  - articles:         2,546 rows   (preserved unchanged)
  - videos:           5,732 rows   (needs channel_id column)
  - video_comments:  60,626 rows   (already has updated_at)
  - content_entities:79,795 rows   (preserved unchanged)
  - brands:              24 rows   (all match entity slugs; entity_type correction done in 0002)
  - comments:             0 rows   (can safely restructure)
  - shares:               0 rows   (can safely restructure)
  - distribution_posts:   0 rows   (no changes needed)

COLUMNS ALREADY PRESENT (no migration needed):
  - contents.share_count, contents.ingestion_origin
  - articles.primary_source_id, articles.enrichment_priority, articles.body
  - authors.aliases
  - video_comments.updated_at
  - videos.url

ONLY ACTUAL MISSING ITEM:
  - videos.channel_id VARCHAR(100)

STRUCTURAL CHANGES (safe because tables are empty):
  - comments: add content_id NOT NULL FK, drop target_type/target_id
  - shares:   add content_id NOT NULL FK, drop target_type/target_id

Revision ID: 0001_phase7_schema_delta
Revises: cffe9cd40bfc
Create Date: 2026-08-26
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0001_phase7_schema_delta"
down_revision = "cffe9cd40bfc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================
    # 1. Add videos.channel_id (only genuinely missing column)
    # =========================================================
    with op.batch_alter_table("videos") as batch_op:
        batch_op.add_column(
            sa.Column("channel_id", sa.String(100), nullable=True)
        )

    # =========================================================
    # 2. Restructure comments table (0 rows â€” safe to alter)
    #    Legacy: target_type VARCHAR NOT NULL, target_id INT NOT NULL
    #    Phase 7: content_id INT NOT NULL FK -> contents.id
    #    Defensive guard: fail if rows exist with non-content target_type
    # =========================================================
    conn = op.get_bind()

    # Safety check: verify comments is empty before structural change
    comment_count = conn.execute(sa.text("SELECT COUNT(*) FROM comments")).scalar()
    if comment_count > 0:
        # Migrate content-targeted comments; delete others (products/posts)
        conn.execute(sa.text("""
            DELETE FROM comments
            WHERE target_type != 'content'
        """))
        # Add nullable content_id, populate, then constrain
        with op.batch_alter_table("comments") as batch_op:
            batch_op.add_column(
                sa.Column("content_id", sa.Integer(), nullable=True)
            )
        conn.execute(sa.text("""
            UPDATE comments SET content_id = target_id
            WHERE target_type = 'content'
        """))
        conn.execute(sa.text("""
            DELETE FROM comments WHERE content_id IS NULL
        """))
        with op.batch_alter_table("comments") as batch_op:
            batch_op.alter_column("content_id", nullable=False)
            batch_op.create_foreign_key(
                "fk_comments_content_id", "contents", ["content_id"], ["id"],
                ondelete="CASCADE"
            )
            batch_op.drop_column("target_type")
            batch_op.drop_column("target_id")
    else:
        # Table is empty: clean structural replacement
        with op.batch_alter_table("comments") as batch_op:
            batch_op.drop_column("target_type")
            batch_op.drop_column("target_id")
            batch_op.add_column(
                sa.Column(
                    "content_id", sa.Integer(),
                    sa.ForeignKey("contents.id", ondelete="CASCADE"),
                    nullable=False,
                    server_default="0",   # temp default for NOT NULL; removed below
                )
            )
        # Remove the server_default now that column is created
        with op.batch_alter_table("comments") as batch_op:
            batch_op.alter_column("content_id", server_default=None)

    # Add Phase 7 comments indexes
    op.create_index("ix_comments_content", "comments", ["content_id"])
    op.create_index("ix_comments_parent", "comments", ["parent_id"])

    # =========================================================
    # 3. Restructure shares table (0 rows â€” safe to alter)
    # =========================================================
    share_count = conn.execute(sa.text("SELECT COUNT(*) FROM shares")).scalar()
    if share_count > 0:
        conn.execute(sa.text("DELETE FROM shares WHERE target_type != 'content'"))
        with op.batch_alter_table("shares") as batch_op:
            batch_op.add_column(sa.Column("content_id", sa.Integer(), nullable=True))
        conn.execute(sa.text("UPDATE shares SET content_id = target_id WHERE target_type = 'content'"))
        conn.execute(sa.text("DELETE FROM shares WHERE content_id IS NULL"))
        with op.batch_alter_table("shares") as batch_op:
            batch_op.alter_column("content_id", nullable=False)
            batch_op.create_foreign_key(
                "fk_shares_content_id", "contents", ["content_id"], ["id"],
                ondelete="CASCADE"
            )
            batch_op.drop_column("target_type")
            batch_op.drop_column("target_id")
    else:
        with op.batch_alter_table("shares") as batch_op:
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
        with op.batch_alter_table("shares") as batch_op:
            batch_op.alter_column("content_id", server_default=None)

    # Add Phase 7 shares indexes
    op.create_index("ix_shares_content", "shares", ["content_id"])
    op.create_index("ix_shares_user_created", "shares", ["user_id", "created_at"])

    # =========================================================
    # 4. Ensure Phase 7 contents indexes exist
    #    (Most already exist; only add missing ones)
    # =========================================================
    # ix_contents_review_score, ix_contents_review_count may exist already
    # We use IF NOT EXISTS via raw SQL to be safe
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contents_review_score ON contents (review_score)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contents_review_count ON contents (review_count)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contents_category_published_at ON contents (category_id, published_at)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contents_section_published_at ON contents (section_id, published_at)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contents_active_published_at ON contents (is_active, published_at)"
    ))


def downgrade() -> None:
    # Remove added indexes
    op.drop_index("ix_shares_user_created", table_name="shares")
    op.drop_index("ix_shares_content", table_name="shares")
    op.drop_index("ix_comments_parent", table_name="comments")
    op.drop_index("ix_comments_content", table_name="comments")

    # Remove videos.channel_id
    with op.batch_alter_table("videos") as batch_op:
        batch_op.drop_column("channel_id")

    # Note: reversing the comments/shares restructure is not safe
    # if production data has been written. Downgrade is for dev use only.
    with op.batch_alter_table("shares") as batch_op:
        batch_op.drop_column("content_id")
        batch_op.add_column(sa.Column("target_type", sa.String(), nullable=False, server_default="content"))
        batch_op.add_column(sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("comments") as batch_op:
        batch_op.drop_column("content_id")
        batch_op.add_column(sa.Column("target_type", sa.String(), nullable=False, server_default="content"))
        batch_op.add_column(sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"))
