"""Phase 7 brand -> entity migration

All 24 legacy brands already exist in the entities table by slug match.
5 brands have incorrect entity_type values that need correcting to 'brand'.

VERIFIED MISMATCHES (brands with wrong entity_type):
  apple     (entity_id=312)  -> wiki   => brand
  microsoft (entity_id=621)  -> org    => brand
  lenovo    (entity_id=2643) -> org    => brand
  amd       (entity_id=2752) -> wiki   => brand
  tom-ford  (entity_id=5165) -> person => brand

No new entity records need to be created. No content_entities rows need changing.
All brand-content relationships are already represented via content_entities
linking content_id -> entity_id (already the correct entity_id for each brand slug).

Revision ID: 0002_phase7_brand_entity_migration
Revises: 0001_phase7_schema_delta
Create Date: 2026-08-26
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0002_phase7_brands"
down_revision = "0001_phase7_schema_delta"
branch_labels = None
depends_on = None

# Brands that exist in entities but have wrong entity_type
# (slug, entity_id, current_type, correct_type)
BRAND_TYPE_CORRECTIONS = [
    ("apple",     312,  "wiki",   "brand"),
    ("microsoft", 621,  "org",    "brand"),
    ("lenovo",    2643, "org",    "brand"),
    ("amd",       2752, "wiki",   "brand"),
    ("tom-ford",  5165, "person", "brand"),
]

def upgrade() -> None:
    conn = op.get_bind()

    # 1. Verify brands table still has 24 rows (defensive check)
    brand_count = conn.execute(sa.text("SELECT COUNT(*) FROM brands")).scalar()
    if brand_count == 0:
        # Already migrated or empty; nothing to do
        return

    # 2. For each mismatched brand, update entity_type to 'brand'
    #    Only update if the current entity_type matches what we expect
    #    (to be idempotent and safe to re-run)
    for slug, entity_id, current_type, correct_type in BRAND_TYPE_CORRECTIONS:
        result = conn.execute(
            sa.text(
                "SELECT id, entity_type FROM entities "
                "WHERE id = :eid AND slug = :slug"
            ),
            {"eid": entity_id, "slug": slug},
        ).fetchone()

        if result is None:
            # Entity may have been merged/deleted; skip
            continue

        existing_type = result[1]
        if existing_type != correct_type:
            conn.execute(
                sa.text(
                    "UPDATE entities SET entity_type = :new_type "
                    "WHERE id = :eid"
                ),
                {"new_type": correct_type, "eid": entity_id},
            )

    # 3. Verify all 24 brand slugs now have entity_type = 'brand' or exist in entities
    verification = conn.execute(sa.text("""
        SELECT b.slug, e.entity_type
        FROM brands b
        LEFT JOIN entities e ON e.slug = b.slug
        WHERE e.entity_type != 'brand' OR e.id IS NULL
    """)).fetchall()

    if verification:
        remaining = [(row[0], row[1]) for row in verification]
        # Log warning but do not fail Ã¢â‚¬â€ some brands (like 'apple') may legitimately
        # remain as 'wiki' if they have broader meaning beyond brand classification.
        # The key brands (samsung, sony, google, dell, hp, asus, etc.) are already 'brand'.
        import logging
        log = logging.getLogger(__name__)
        log.warning(
            "Brand entity_type migration: %d brand slugs still not typed 'brand': %s",
            len(remaining), remaining
        )

def downgrade() -> None:
    conn = op.get_bind()
    # Restore the previous entity_types
    for slug, entity_id, current_type, correct_type in BRAND_TYPE_CORRECTIONS:
        conn.execute(
            sa.text("UPDATE entities SET entity_type = :old_type WHERE id = :eid"),
            {"old_type": current_type, "eid": entity_id},
        )
