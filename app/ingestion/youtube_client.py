"""YouTube Data API v3 client for video ingestion, statistics, and top comments."""

from __future__ import annotations
import logging
import re
from typing import Any
from datetime import datetime, timezone
import requests
from flask import current_app

log = logging.getLogger(__name__)

YOUTUBE_BASE_URL = "https://www.googleapis.com/youtube/v3"
_ISO_DURATION_RE = re.compile(r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?")


def parse_iso_duration(duration_str: str | None) -> int:
    """Parse ISO-8601 duration (e.g. PT14M33S) to total seconds."""
    if not duration_str:
        return 0
    match = _ISO_DURATION_RE.match(duration_str)
    if not match:
        return 0
    parts = match.groupdict()
    days = int(parts.get("days") or 0)
    hours = int(parts.get("hours") or 0)
    minutes = int(parts.get("minutes") or 0)
    seconds = int(parts.get("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YouTubeClient:
    """Client for YouTube Data API v3 video ingestion."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or (current_app.config.get("YOUTUBE_API_KEY") if current_app else None)

    def search_videos(self, query: str, *, max_results: int = 25, order: str = "date", relevance_language: str = "en") -> list[dict[str, Any]]:
        """Search YouTube for videos matching a query and fetch full video statistics."""
        if not self.api_key:
            log.warning("YouTubeClient: No API key configured. Skipping fetch.")
            return []

        search_url = f"{YOUTUBE_BASE_URL}/search"
        params: dict[str, Any] = {
            "key": self.api_key,
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
            "order": order,
            "relevanceLanguage": relevance_language,
        }

        try:
            res = requests.get(search_url, params=params, timeout=20)
            res.raise_for_status()
            items = res.json().get("items", [])
            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]

            if not video_ids:
                return []

            return self.get_videos_details(video_ids)

        except requests.RequestException as exc:
            log.error("YouTubeClient: search failed: %s", exc)
            return []

    def get_videos_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch snippet, contentDetails, and statistics for a batch of video IDs."""
        if not self.api_key or not video_ids:
            return []

        videos_url = f"{YOUTUBE_BASE_URL}/videos"
        params = {"key": self.api_key, "part": "snippet,contentDetails,statistics", "id": ",".join(video_ids[:50])}

        try:
            res = requests.get(videos_url, params=params, timeout=20)
            res.raise_for_status()
            raw_videos = res.json().get("items", [])

            results: list[dict[str, Any]] = []
            for item in raw_videos:
                parsed = self._parse_video_item(item)
                if parsed:
                    results.append(parsed)
            return results

        except requests.RequestException as exc:
            log.error("YouTubeClient: get_videos_details failed: %s", exc)
            return []

    def fetch_top_comments(self, video_id: str, max_results: int = 15) -> list[dict[str, Any]]:
        """Fetch top user comments for a video."""
        if not self.api_key:
            return []

        comments_url = f"{YOUTUBE_BASE_URL}/commentThreads"
        params = {
            "key": self.api_key,
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": min(max_results, 50),
            "textFormat": "plainText",
        }

        try:
            res = requests.get(comments_url, params=params, timeout=15)
            if res.status_code == 403:
                return []
            res.raise_for_status()
            items = res.json().get("items", [])

            comments: list[dict[str, Any]] = []
            for it in items:
                top = it.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                if top and top.get("textDisplay"):
                    pub_str = top.get("publishedAt")
                    pub_dt = None
                    if pub_str:
                        try:
                            pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                        except ValueError:
                            pass

                    comments.append(
                        {
                            "external_id": it.get("id"),
                            "author_name": top.get("authorDisplayName"),
                            "author_channel_id": top.get("authorChannelId", {}).get("value")
                            if isinstance(top.get("authorChannelId"), dict)
                            else top.get("authorChannelId"),
                            "text": top.get("textDisplay"),
                            "like_count": int(top.get("likeCount") or 0),
                            "reply_count": int(it.get("snippet", {}).get("totalReplyCount") or 0),
                            "published_at": pub_dt,
                        }
                    )
            return comments

        except requests.RequestException as exc:
            log.debug("YouTubeClient: fetch_top_comments (%s) error: %s", video_id, exc)
            return []

    def _parse_video_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        video_id = item.get("id")
        snippet = item.get("snippet", {})
        details = item.get("contentDetails", {})
        stats = item.get("statistics", {})

        title = snippet.get("title")
        if not video_id or not title:
            return None

        thumbs = snippet.get("thumbnails", {})
        thumb_url = (
            thumbs.get("maxres", {}).get("url")
            or thumbs.get("high", {}).get("url")
            or thumbs.get("medium", {}).get("url")
            or thumbs.get("default", {}).get("url")
        )

        pub_str = snippet.get("publishedAt")
        pub_dt = None
        if pub_str:
            try:
                pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except ValueError:
                pub_dt = datetime.now(timezone.utc)
        else:
            pub_dt = datetime.now(timezone.utc)

        duration_sec = parse_iso_duration(details.get("duration"))

        return {
            "source_type": "youtube",
            "external_id": video_id,
            "platform": "youtube",
            "title": title.strip(),
            "description": snippet.get("description"),
            "thumbnail_url": thumb_url,
            "channel_name": snippet.get("channelTitle"),
            "channel_id": snippet.get("channelId"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "creator": snippet.get("channelTitle"),
            "duration_seconds": duration_sec,
            "view_count": int(stats.get("viewCount") or 0),
            "like_count": int(stats.get("likeCount") or 0),
            "comments_count": int(stats.get("commentCount") or 0),
            "published_at": pub_dt,
            "tags": snippet.get("tags", []),
            "platform_metadata": {"categoryId": snippet.get("categoryId"), "defaultAudioLanguage": snippet.get("defaultAudioLanguage")},
        }
