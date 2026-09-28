"""Add PostgreSQL full-text search trigger, GIN index, and backfill search_vector

Revision ID: 0005_fts_trigger_and_index
Revises: 0004_email_verify_token
Create Date: 2026-09-29
"""
from __future__ import annotations
from alembic import op


revision = "0005_fts_trigger_and_index"
down_revision = "0004_email_verify_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. GIN index for fast full-text search on search_vector
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contents_search_vector
        ON contents USING GIN (search_vector);
    """)

    # 2. Trigger function: automatically calculate weighted search_vector on INSERT or UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION update_content_search_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.preview_text, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.search_text, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 3. Trigger on contents table
    op.execute("""
        DROP TRIGGER IF EXISTS trg_update_content_search_vector ON contents;
        CREATE TRIGGER trg_update_content_search_vector
        BEFORE INSERT OR UPDATE OF title, preview_text, search_text
        ON contents
        FOR EACH ROW EXECUTE FUNCTION update_content_search_vector();
    """)

    # 4. Backfill existing rows with weighted tsvector
    op.execute("""
        UPDATE contents SET search_vector =
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(preview_text, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(search_text, '')), 'C');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_update_content_search_vector ON contents;")
    op.execute("DROP FUNCTION IF EXISTS update_content_search_vector();")
    op.execute("DROP INDEX IF EXISTS ix_contents_search_vector;")
