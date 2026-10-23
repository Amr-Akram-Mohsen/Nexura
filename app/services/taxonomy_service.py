"""Taxonomy service for entity deduplication and taxonomy domain workflows."""

from __future__ import annotations
import difflib
from typing import Any

from app.models.taxonomy import Entity
from app.extensions import db


class TaxonomyService:
    """Domain workflows for taxonomy, entities, and deduplication."""

    @staticmethod
    def find_duplicate_entities(threshold: float = 0.85, limit: int = 20) -> list[dict[str, Any]]:
        """Find entity pairs with high string similarity for editorial merge review."""
        entities = db.session.query(Entity.id, Entity.name, Entity.slug, Entity.entity_type).order_by(Entity.name.asc()).limit(300).all()

        candidates: list[dict[str, Any]] = []
        visited: set[tuple[int, int]] = set()

        for i in range(len(entities)):
            e1 = entities[i]
            for j in range(i + 1, len(entities)):
                e2 = entities[j]
                pair_key = (min(e1.id, e2.id), max(e1.id, e2.id))
                if pair_key in visited:
                    continue

                ratio = difflib.SequenceMatcher(None, e1.name.lower(), e2.name.lower()).ratio()
                if ratio >= threshold and e1.name.lower() != e2.name.lower():
                    visited.add(pair_key)
                    candidates.append(
                        {
                            "entity_1": {"id": e1.id, "name": e1.name, "slug": e1.slug, "type": e1.entity_type},
                            "entity_2": {"id": e2.id, "name": e2.name, "slug": e2.slug, "type": e2.entity_type},
                            "similarity_pct": int(ratio * 100),
                        }
                    )
                    if len(candidates) >= limit:
                        return candidates

        return candidates
