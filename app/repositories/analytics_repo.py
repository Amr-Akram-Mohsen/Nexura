"""Analytics repository for user interactions, view counters, threaded comments, and impressions."""

from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
import math

from sqlalchemy import desc, asc, func, and_
from sqlalchemy.orm import selectinload, joinedload

from app.extensions import db
from app.models.content import Content
from app.models.interaction import View, Save, Reaction, Comment, Share
from app.models.recommendation import RecommendationImpression, RecommendationClick


class AnalyticsRepository:
    """Atomic interaction persistence, counter updates, and engagement metrics."""

    @staticmethod
    def record_view(content_id: int, *, user_id: int | None = None, ip_address: str | None = None) -> bool:
        """Record a content view and atomically increment Content.view_count."""
        if not user_id and not ip_address:
            return False

        view = View(content_id=content_id, user_id=user_id, ip_address=None if user_id else ip_address, created_at=datetime.now(timezone.utc))
        db.session.add(view)

        db.session.query(Content).filter(Content.id == content_id).update({Content.view_count: Content.view_count + 1})
        db.session.commit()
        return True

    @staticmethod
    def toggle_reaction(user_id: int, target_type: str, target_id: int, reaction_type: str) -> dict[str, Any]:
        """Toggle or switch user reaction (like/dislike) on content or comment."""
        existing = db.session.query(Reaction).filter(Reaction.user_id == user_id, Reaction.target_type == target_type, Reaction.target_id == target_id).first()

        user_state = None
        if existing:
            if existing.type == reaction_type:
                db.session.delete(existing)
                user_state = None
            else:
                existing.type = reaction_type
                user_state = reaction_type
        else:
            new_reaction = Reaction(user_id=user_id, target_type=target_type, target_id=target_id, type=reaction_type, created_at=datetime.now(timezone.utc))
            db.session.add(new_reaction)
            user_state = reaction_type

        db.session.flush()

        likes = (
            db.session.query(func.count(Reaction.id))
            .filter(Reaction.target_type == target_type, Reaction.target_id == target_id, Reaction.type == "like")
            .scalar()
            or 0
        )
        dislikes = (
            db.session.query(func.count(Reaction.id))
            .filter(Reaction.target_type == target_type, Reaction.target_id == target_id, Reaction.type == "dislike")
            .scalar()
            or 0
        )

        if target_type == "content":
            db.session.query(Content).filter(Content.id == target_id).update({Content.like_count: likes, Content.dislike_count: dislikes})
        elif target_type == "comment":
            db.session.query(Comment).filter(Comment.id == target_id).update({Comment.like_count: likes, Comment.dislike_count: dislikes})

        db.session.commit()
        return {"user_reaction": user_state, "like_count": likes, "dislike_count": dislikes}

    @staticmethod
    def get_user_content_reaction(user_id: int, content_id: int) -> str | None:
        """Fetch current user's reaction on a content item."""
        r = db.session.query(Reaction.type).filter(Reaction.user_id == user_id, Reaction.target_type == "content", Reaction.target_id == content_id).first()
        return r[0] if r else None

    @staticmethod
    def get_user_state(user_id: int, content_id: int) -> dict[str, bool]:
        """Fetch user interaction state for a content item: liked, disliked, saved."""
        reaction = AnalyticsRepository.get_user_content_reaction(user_id, content_id)
        from app.repositories.user_repo import UserRepository

        saved = UserRepository.is_content_saved(user_id, content_id)
        return {"liked": reaction == "like", "disliked": reaction == "dislike", "saved": saved}

    @staticmethod
    def toggle_save(user_id: int, content_id: int, collection_name: str = "General") -> bool:
        """Toggle bookmark save status for user. Returns True if saved, False if unsaved."""
        existing = db.session.query(Save).filter(Save.user_id == user_id, Save.content_id == content_id, Save.collection_name == collection_name).first()

        is_saved = False
        if existing:
            db.session.delete(existing)
            is_saved = False
        else:
            save = Save(user_id=user_id, content_id=content_id, collection_name=collection_name, created_at=datetime.now(timezone.utc))
            db.session.add(save)
            is_saved = True

        db.session.flush()

        save_count = db.session.query(func.count(Save.id)).filter(Save.content_id == content_id).scalar() or 0
        db.session.query(Content).filter(Content.id == content_id).update({Content.save_count: save_count})
        db.session.commit()
        return is_saved

    @staticmethod
    def record_share(content_id: int, user_id: int, channel: str = "copy") -> int:
        """Record social share and increment share_count."""
        share = Share(content_id=content_id, user_id=user_id, channel=channel, created_at=datetime.now(timezone.utc))
        db.session.add(share)
        db.session.query(Content).filter(Content.id == content_id).update({Content.share_count: Content.share_count + 1})
        db.session.commit()

        return db.session.query(Content.share_count).filter(Content.id == content_id).scalar() or 0

    @staticmethod
    def add_comment(
        *, user_id: int, content_id: int, content_text: str, parent_id: int | None = None, sentiment: str | None = None, confidence: float | None = None
    ) -> Comment:
        """Create a user comment and increment content comment_count."""
        comment = Comment(
            user_id=user_id,
            content_id=content_id,
            parent_id=parent_id,
            content=content_text.strip(),
            sentiment=sentiment,
            confidence=confidence,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(comment)
        db.session.flush()

        if parent_id:
            db.session.query(Comment).filter(Comment.id == parent_id).update({Comment.replies_count: Comment.replies_count + 1})

        db.session.query(Content).filter(Content.id == content_id).update({Content.comment_count: Content.comment_count + 1})
        db.session.commit()
        return comment

    @staticmethod
    def get_comments_tree(content_id: int, current_user_id: int | None = None) -> list[dict[str, Any]]:
        """Fetch threaded comments hierarchy for a content item with replies and reaction state."""
        comments = (
            db.session.query(Comment)
            .options(joinedload(Comment.user))
            .filter(Comment.content_id == content_id)
            .order_by(Comment.parent_id.nullsfirst(), Comment.created_at.asc())
            .all()
        )

        user_reactions: dict[int, str] = {}
        if current_user_id:
            user_rx_rows = (
                db.session.query(Reaction.target_id, Reaction.type).filter(Reaction.user_id == current_user_id, Reaction.target_type == "comment").all()
            )
            user_reactions = {r[0]: r[1] for r in user_rx_rows}

        by_id: dict[int, dict[str, Any]] = {}
        top_level: list[dict[str, Any]] = []

        for c in comments:
            user_display = c.user.name if c.user and c.user.name else (c.user.email.split("@")[0] if c.user and c.user.email else "Community Member")
            dto = {
                "id": c.id,
                "user_id": c.user_id,
                "user_name": user_display,
                "content": c.content,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "formatted_date": c.created_at.strftime("%b %d, %Y") if c.created_at else "Recently",
                "like_count": c.like_count or 0,
                "dislike_count": c.dislike_count or 0,
                "replies_count": c.replies_count or 0,
                "sentiment": c.sentiment,
                "parent_id": c.parent_id,
                "is_own": bool(current_user_id and c.user_id == current_user_id),
                "user_liked": user_reactions.get(c.id) == "like",
                "user_disliked": user_reactions.get(c.id) == "dislike",
                "replies": [],
            }
            by_id[c.id] = dto

            if c.parent_id is None:
                top_level.append(dto)
            elif c.parent_id in by_id:
                by_id[c.parent_id]["replies"].append(dto)

        top_level.reverse()
        return top_level

    @staticmethod
    def record_impression(entity_ids: list[int | str], *, context_id: str | None = None, user_id: int | None = None) -> None:
        """Record recommendation impression events."""
        imp = RecommendationImpression(
            entity_type="content", entity_ids=entity_ids, context_id=context_id, user_id=user_id, created_at=datetime.now(timezone.utc)
        )
        db.session.add(imp)
        db.session.commit()

    @staticmethod
    def record_click(entity_id: str | int, *, context_id: str | None = None, user_id: int | None = None) -> None:
        """Record recommendation click events."""
        click = RecommendationClick(
            entity_type="content", entity_id=str(entity_id), context_id=context_id, user_id=user_id, created_at=datetime.now(timezone.utc)
        )
        db.session.add(click)
        db.session.commit()
