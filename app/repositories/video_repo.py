"""Video repository for YouTube video data and synced comments."""

from __future__ import annotations
from typing import Sequence
from datetime import datetime, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.video import Video, VideoComment


class VideoRepository:
    """Data access operations for Video and VideoComment records."""

    @staticmethod
    def get_by_id(video_id: int) -> Video | None:
        """Fetch video with its top comments eager-loaded."""
        return db.session.query(Video).options(selectinload(Video.video_comments)).filter(Video.id == video_id).first()

    @staticmethod
    def get_top_comments(video_id: int, limit: int = 15) -> list[VideoComment]:
        """Fetch top comments for a video ordered by like count."""
        return db.session.query(VideoComment).filter(VideoComment.video_id == video_id).order_by(desc(VideoComment.like_count)).limit(limit).all()

    @staticmethod
    def get_by_external_id(external_id: str, platform: str = "youtube") -> Video | None:
        """Fetch video by external ID for deduplication."""
        return db.session.query(Video).filter(Video.external_id == external_id, Video.platform == platform).first()

    @staticmethod
    def list_videos(*, channel_name: str | None = None, creator: str | None = None, page: int = 1, per_page: int = 24) -> tuple[list[Video], int]:
        """List videos with optional channel or creator filter and pagination."""
        query = db.session.query(Video)

        if channel_name:
            query = query.filter(Video.channel_name == channel_name)
        if creator:
            query = query.filter(Video.creator == creator)

        total = query.with_entities(func.count(Video.id)).scalar() or 0
        videos = query.order_by(desc(Video.published_at)).offset(max(0, (page - 1) * per_page)).limit(per_page).all()
        return videos, total

    @staticmethod
    def create(
        *,
        external_id: str,
        platform: str = "youtube",
        title: str,
        description: str | None = None,
        description_display_rule: str = "review",
        thumbnail_url: str | None = None,
        channel_name: str | None = None,
        channel_id: str | None = None,
        url: str | None = None,
        creator: str | None = None,
        duration_seconds: int | None = None,
        view_count: int = 0,
        like_count: int = 0,
        comments_count: int = 0,
        published_at: datetime | None = None,
        platform_metadata: dict | None = None,
    ) -> Video:
        """Create and persist a new Video record."""
        video = Video(
            external_id=external_id,
            platform=platform,
            title=title,
            description=description,
            description_display_rule=description_display_rule,
            thumbnail_url=thumbnail_url,
            channel_name=channel_name,
            channel_id=channel_id,
            url=url,
            creator=creator,
            duration_seconds=duration_seconds,
            view_count=view_count,
            like_count=like_count,
            comments_count=comments_count,
            published_at=published_at or datetime.now(timezone.utc),
            platform_metadata=platform_metadata or {},
        )
        db.session.add(video)
        db.session.flush()
        return video

    @staticmethod
    def upsert_comment(
        *,
        video_id: int,
        external_id: str,
        author_name: str | None = None,
        author_channel_id: str | None = None,
        text: str,
        like_count: int = 0,
        reply_count: int = 0,
        published_at: datetime | None = None,
    ) -> VideoComment:
        """Upsert a top YouTube comment for a video."""
        comment = db.session.query(VideoComment).filter(VideoComment.external_id == external_id).first()
        if comment:
            comment.like_count = like_count
            comment.reply_count = reply_count
            comment.updated_at = datetime.now(timezone.utc)
        else:
            comment = VideoComment(
                video_id=video_id,
                external_id=external_id,
                author_name=author_name,
                author_channel_id=author_channel_id,
                text=text,
                like_count=like_count,
                reply_count=reply_count,
                published_at=published_at,
                updated_at=datetime.now(timezone.utc),
            )
            db.session.add(comment)
        db.session.flush()
        return comment
