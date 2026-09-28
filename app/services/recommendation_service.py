"""Recommendation service for content relevance scoring and discovery feeds."""

from __future__ import annotations
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Sequence

from sqlalchemy import desc, func, and_, or_
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.content import Content, ContentEntity
from app.models.taxonomy import Entity, Category
from app.models.interaction import View, Save, Reaction
from app.models.recommendation import UserInterest, UserEntityInterest
from app.repositories.content_repo import ContentRepository

log = logging.getLogger(__name__)

HALF_LIFE_DAYS = 30.0
LN_2 = math.log(2)


def calculate_relevance_score(candidate: Content, reference: Content, now: datetime | None = None) -> float:
    """Compute multi-factor relevance between candidate and reference content."""
    if candidate.id == reference.id:
        return 0.0

    now_utc = now or datetime.now(timezone.utc)

    ref_entities = {ce.entity_id: ce.entity.entity_type for ce in (reference.content_entities or []) if ce.entity}
    cand_entities = {ce.entity_id: ce.entity.entity_type for ce in (candidate.content_entities or []) if ce.entity}

    shared_ids = set(ref_entities.keys()) & set(cand_entities.keys())
    shared_topics_count = 0
    shared_brand = False

    for eid in shared_ids:
        etype = ref_entities.get(eid)
        if etype == "brand":
            shared_brand = True
        else:
            shared_topics_count += 1

    score_topics = 3.0 * shared_topics_count
    score_brand = 2.0 if shared_brand else 0.0
    score_category = 1.5 if candidate.category_id and candidate.category_id == reference.category_id else 0.0
    score_section = 0.5 if candidate.section_id and candidate.section_id == reference.section_id else 0.0

    delta_days = 0.0
    if candidate.published_at:
        cand_pub = candidate.published_at
        if cand_pub.tzinfo is None:
            cand_pub = cand_pub.replace(tzinfo=timezone.utc)
        delta_days = max(0.0, (now_utc - cand_pub).total_seconds() / 86400.0)

    decay = math.exp(-1.0 * LN_2 * delta_days / HALF_LIFE_DAYS)
    score_recency = 0.8 * decay

    views = max(0, candidate.view_count or 0)
    score_popularity = 0.4 * math.log(1.0 + views)

    total_score = score_topics + score_brand + score_category + score_section + score_recency + score_popularity
    return round(total_score, 4)


class RecommendationService:
    """Service layer for computing recommendations and managing user interest vectors."""

    @staticmethod
    def get_related_recommendations(content_id: int, limit: int = 6) -> list[Content]:
        """Rank candidate related items using the multi-signal relevance formula."""
        reference = ContentRepository.get_by_id(content_id, published_only=True)
        if not reference:
            return []

        entity_ids = [ce.entity_id for ce in reference.content_entities if ce.entity_id]

        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .filter(Content.id != content_id, Content.is_active.is_(True), Content.is_published.is_(True))
        )

        conditions = []
        if reference.category_id:
            conditions.append(Content.category_id == reference.category_id)
        if reference.section_id:
            conditions.append(Content.section_id == reference.section_id)
        if entity_ids:
            conditions.append(Content.id.in_(db.session.query(ContentEntity.content_id).filter(ContentEntity.entity_id.in_(entity_ids)).scalar_subquery()))

        if conditions:
            query = query.filter(or_(*conditions))

        candidates = query.limit(50).all()
        ContentRepository.resolve_polymorphic_payloads(candidates)

        scored = [(candidate, calculate_relevance_score(candidate, reference)) for candidate in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [item[0] for item in scored[:limit]]

    @staticmethod
    def get_personalized_discovery_feed(user_id: int, limit: int = 24) -> list[Content]:
        """Generate a personalized discovery feed for an authenticated user."""
        seen_views = [r[0] for r in db.session.query(View.content_id).filter(View.user_id == user_id).order_by(desc(View.created_at)).limit(100).all()]
        seen_saves = [r[0] for r in db.session.query(Save.content_id).filter(Save.user_id == user_id).all()]
        seen_ids = set(seen_views + seen_saves)

        history_contents = (
            db.session.query(Content)
            .options(joinedload(Content.category), selectinload(Content.content_entities).joinedload(ContentEntity.entity))
            .filter(Content.id.in_(seen_ids or [-1]))
            .all()
        )

        category_counts: dict[int, int] = {}
        entity_counts: dict[int, int] = {}

        for c in history_contents:
            if c.category_id:
                category_counts[c.category_id] = category_counts.get(c.category_id, 0) + 1
            for ce in c.content_entities:
                if ce.entity_id:
                    entity_counts[ce.entity_id] = entity_counts.get(ce.entity_id, 0) + 1

        top_category_ids = sorted(category_counts, key=category_counts.get, reverse=True)[:5]
        top_entity_ids = sorted(entity_counts, key=entity_counts.get, reverse=True)[:10]

        cat_items: list[Content] = []
        if top_category_ids:
            cat_query = (
                db.session.query(Content)
                .options(
                    joinedload(Content.section),
                    joinedload(Content.category),
                    joinedload(Content.source),
                    selectinload(Content.content_entities).joinedload(ContentEntity.entity),
                )
                .filter(Content.category_id.in_(top_category_ids), Content.is_active.is_(True), Content.is_published.is_(True))
            )
            if seen_ids:
                cat_query = cat_query.filter(~Content.id.in_(seen_ids))

            cat_items = cat_query.order_by(desc(Content.score), desc(Content.published_at)).limit(limit).all()

        entity_items: list[Content] = []
        if top_entity_ids:
            ent_query = (
                db.session.query(Content)
                .options(
                    joinedload(Content.section),
                    joinedload(Content.category),
                    joinedload(Content.source),
                    selectinload(Content.content_entities).joinedload(ContentEntity.entity),
                )
                .join(Content.content_entities)
                .filter(ContentEntity.entity_id.in_(top_entity_ids), Content.is_active.is_(True), Content.is_published.is_(True))
            )
            if seen_ids:
                ent_query = ent_query.filter(~Content.id.in_(seen_ids))

            entity_items = ent_query.order_by(desc(Content.score), desc(Content.published_at)).limit(limit).all()

        interleaved: list[Content] = []
        seen_in_feed: set[int] = set()

        max_len = max(len(cat_items), len(entity_items))
        for i in range(max_len):
            if i < len(cat_items) and cat_items[i].id not in seen_in_feed:
                interleaved.append(cat_items[i])
                seen_in_feed.add(cat_items[i].id)
            if i < len(entity_items) and entity_items[i].id not in seen_in_feed:
                interleaved.append(entity_items[i])
                seen_in_feed.add(entity_items[i].id)
            if len(interleaved) >= limit:
                break

        if len(interleaved) < limit:
            remaining = limit - len(interleaved)
            fallback = (
                db.session.query(Content)
                .options(
                    joinedload(Content.section),
                    joinedload(Content.category),
                    joinedload(Content.source),
                    selectinload(Content.content_entities).joinedload(ContentEntity.entity),
                )
                .filter(
                    Content.is_active.is_(True), Content.is_published.is_(True), ~Content.id.in_(seen_in_feed | seen_ids if (seen_in_feed | seen_ids) else [-1])
                )
                .order_by(desc(Content.score), desc(Content.view_count), desc(Content.published_at))
                .limit(remaining)
                .all()
            )
            interleaved.extend(fallback)

        return ContentRepository.resolve_polymorphic_payloads(interleaved[:limit])

    @staticmethod
    def update_user_interest_graph(user_id: int, content_id: int, interaction_weight: float = 1.0) -> None:
        """Record and update user affinity in UserInterest and UserEntityInterest tables."""
        content = db.session.get(Content, content_id)
        if not content:
            return

        now = datetime.now(timezone.utc)

        user_interest = db.session.query(UserInterest).filter(UserInterest.user_id == user_id, UserInterest.content_id == content_id).first()

        if not user_interest:
            user_interest = UserInterest(user_id=user_id, content_id=content_id, interaction_count=1, last_interaction_at=now)
            db.session.add(user_interest)
            db.session.flush()
        else:
            user_interest.interaction_count += 1
            user_interest.last_interaction_at = now

        if content.category_id:
            cat_interest = (
                db.session.query(UserEntityInterest)
                .filter(UserEntityInterest.user_interest_id == user_interest.id, UserEntityInterest.category_id == content.category_id)
                .first()
            )
            if not cat_interest:
                cat_interest = UserEntityInterest(user_interest_id=user_interest.id, category_id=content.category_id, score=interaction_weight)
                db.session.add(cat_interest)
            else:
                cat_interest.score += interaction_weight

        for ce in content.content_entities or []:
            if ce.entity_id:
                ent_interest = (
                    db.session.query(UserEntityInterest)
                    .filter(UserEntityInterest.user_interest_id == user_interest.id, UserEntityInterest.entity_id == ce.entity_id)
                    .first()
                )
                if not ent_interest:
                    ent_interest = UserEntityInterest(
                        user_interest_id=user_interest.id, entity_id=ce.entity_id, score=interaction_weight * (ce.relevance_score or 1.0)
                    )
                    db.session.add(ent_interest)
                else:
                    ent_interest.score += interaction_weight * (ce.relevance_score or 1.0)

        db.session.commit()
