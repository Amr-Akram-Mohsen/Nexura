"""
Nexura Phase 7 — Analytics & Interaction Repository
Handles atomic engagement counters, user interactions (Views, Saves, Reactions,
Comments, Shares), Threaded comments hierarchy, and CTR tracking.
"""
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

    # ---------- Views ----------

    @staticmethod
    def record_view(
        content_id: int,
        *,
        user_id: int | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """
        Record a content view and atomically increment Content.view_count.
        Phase 7 §5 invariant: one identity (user_id OR ip_address).
        """
        if not user_id and not ip_address:
            return False

        # Check for duplicate view in short interval if needed
        view = View(
            content_id=content_id,
            user_id=user_id,
            ip_address=None if user_id else ip_address,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(view)

        # Atomic view_count increment
        db.session.query(Content).filter(Content.id == content_id).update(
            {Content.view_count: Content.view_count + 1}
        )
        db.session.commit()
        return True

    # ---------- Reactions (Likes / Dislikes) ----------

    @staticmethod
    def toggle_reaction(
        user_id: int,
        target_type: str,
        target_id: int,
        reaction_type: str,  # 'like' | 'dislike'
    ) -> dict[str, Any]:
        """
        Toggle or switch user reaction (like/dislike) on content or comment.
        Returns dict with current status and updated counts.
        """
        existing = (
            db.session.query(Reaction)
            .filter(
                Reaction.user_id == user_id,
                Reaction.target_type == target_type,
                Reaction.target_id == target_id,
            )
            .first()
        )

        user_state = None
        if existing:
            if existing.type == reaction_type:
                # Remove reaction (toggle off)
                db.session.delete(existing)
                user_state = None
            else:
                # Switch reaction type
                existing.type = reaction_type
                user_state = reaction_type
        else:
            new_reaction = Reaction(
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                type=reaction_type,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(new_reaction)
            user_state = reaction_type

        db.session.flush()

        # Re-aggregate counts for target
        likes = (
            db.session.query(func.count(Reaction.id))
            .filter(Reaction.target_type == target_type, Reaction.target_id == target_id, Reaction.type == "like")
            .scalar() or 0
        )
        dislikes = (
            db.session.query(func.count(Reaction.id))
            .filter(Reaction.target_type == target_type, Reaction.target_id == target_id, Reaction.type == "dislike")
            .scalar() or 0
        )

        if target_type == "content":
            db.session.query(Content).filter(Content.id == target_id).update(
                {Content.like_count: likes, Content.dislike_count: dislikes}
            )
        elif target_type == "comment":
            db.session.query(Comment).filter(Comment.id == target_id).update(
                {Comment.like_count: likes, Comment.dislike_count: dislikes}
            )

        db.session.commit()
        return {"user_reaction": user_state, "like_count": likes, "dislike_count": dislikes}

    @staticmethod
    def get_user_content_reaction(user_id: int, content_id: int) -> str | None:
        """Fetch current user's reaction on a content item."""
        r = (
            db.session.query(Reaction.type)
            .filter(
                Reaction.user_id == user_id,
                Reaction.target_type == "content",
                Reaction.target_id == content_id,
            )
            .first()
        )
        return r[0] if r else None

    @staticmethod
    def get_user_state(user_id: int, content_id: int) -> dict[str, bool]:
        """Fetch user interaction state for a content item: liked, disliked, saved."""
        reaction = AnalyticsRepository.get_user_content_reaction(user_id, content_id)
        from app.repositories.user_repo import UserRepository
        saved = UserRepository.is_content_saved(user_id, content_id)
        return {
            "liked": reaction == "like",
            "disliked": reaction == "dislike",
            "saved": saved,
        }

    # ---------- Saves / Bookmarks ----------

    @staticmethod
    def toggle_save(
        user_id: int,
        content_id: int,
        collection_name: str = "General",
    ) -> bool:
        """Toggle bookmark save status for user. Returns True if saved, False if unsaved."""
        existing = (
            db.session.query(Save)
            .filter(
                Save.user_id == user_id,
                Save.content_id == content_id,
                Save.collection_name == collection_name,
            )
            .first()
        )

        is_saved = False
        if existing:
            db.session.delete(existing)
            is_saved = False
        else:
            save = Save(
                user_id=user_id,
                content_id=content_id,
                collection_name=collection_name,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(save)
            is_saved = True

        db.session.flush()

        # Update Content.save_count
        save_count = (
            db.session.query(func.count(Save.id))
            .filter(Save.content_id == content_id)
            .scalar() or 0
        )
        db.session.query(Content).filter(Content.id == content_id).update(
            {Content.save_count: save_count}
        )
        db.session.commit()
        return is_saved

    # ---------- Shares ----------

    @staticmethod
    def record_share(
        content_id: int,
        user_id: int,
        channel: str = "copy",
    ) -> int:
        """Record social share and increment share_count."""
        share = Share(
            content_id=content_id,
            user_id=user_id,
            channel=channel,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(share)
        db.session.query(Content).filter(Content.id == content_id).update(
            {Content.share_count: Content.share_count + 1}
        )
        db.session.commit()

        return (
            db.session.query(Content.share_count)
            .filter(Content.id == content_id)
            .scalar() or 0
        )

    # ---------- Comments (Threaded) ----------

    @staticmethod
    def add_comment(
        *,
        user_id: int,
        content_id: int,
        content_text: str,
        parent_id: int | None = None,
        sentiment: str | None = None,
        confidence: float | None = None,
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

        # If replying to a comment, increment parent replies_count
        if parent_id:
            db.session.query(Comment).filter(Comment.id == parent_id).update(
                {Comment.replies_count: Comment.replies_count + 1}
            )

        # Increment Content.comment_count
        db.session.query(Content).filter(Content.id == content_id).update(
            {Content.comment_count: Content.comment_count + 1}
        )
        db.session.commit()
        return comment

    @staticmethod
    def get_comments_tree(content_id: int) -> list[dict[str, Any]]:
        """
        Fetch threaded comments hierarchy for a content item.
        Returns top-level comments with nested replies.
        """
        comments = (
            db.session.query(Comment)
            .options(joinedload(Comment.user))
            .filter(Comment.content_id == content_id)
            .order_by(Comment.parent_id.nullsfirst(), Comment.created_at.asc())
            .all()
        )

        by_id: dict[int, dict[str, Any]] = {}
        top_level: list[dict[str, Any]] = []

        for c in comments:
            dto = {
                "id": c.id,
                "user_id": c.user_id,
                "user_name": c.user.name if c.user and c.user.name else "Community Member",
                "content": c.content,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "like_count": c.like_count,
                "dislike_count": c.dislike_count,
                "replies_count": c.replies_count,
                "sentiment": c.sentiment,
                "parent_id": c.parent_id,
                "replies": [],
            }
            by_id[c.id] = dto

            if c.parent_id is None:
                top_level.append(dto)
            elif c.parent_id in by_id:
                by_id[c.parent_id]["replies"].append(dto)

        return top_level

    # ---------- Recommendation CTR Tracking ----------

    @staticmethod
    def record_impression(
        entity_ids: list[int | str],
        *,
        context_id: str | None = None,
        user_id: int | None = None,
    ) -> None:
        imp = RecommendationImpression(
            entity_type="content",
            entity_ids=entity_ids,
            context_id=context_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(imp)
        db.session.commit()

    @staticmethod
    def record_click(
        entity_id: str | int,
        *,
        context_id: str | None = None,
        user_id: int | None = None,
    ) -> None:
        click = RecommendationClick(
            entity_type="content",
            entity_id=str(entity_id),
            context_id=context_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(click)
        db.session.commit()
