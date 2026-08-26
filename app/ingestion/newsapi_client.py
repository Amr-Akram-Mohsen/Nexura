"""
Nexura Phase 7 — NewsAPI / Event Registry Ingestion Client (§7.1)
Fetches articles across international and domain-specific media sources.
"""
from __future__ import annotations
import logging
from typing import Any
from datetime import datetime, timezone
import requests

from flask import current_app

log = logging.getLogger(__name__)

EVENT_REGISTRY_URL = "https://eventregistry.org/api/v1/article/getArticles"
NEWSAPI_AI_DEFAULT_URL = "https://eventregistry.org/api/v1/article/getArticles"


class NewsAPIClient:
    """Client for Event Registry / NewsAPI.ai article discovery."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or (
            current_app.config.get("NEWS_API_KEY") if current_app else None
        )

    def fetch_articles(
        self,
        *,
        keywords: str | None = None,
        category_uri: str | None = None,
        source_uri: str | None = None,
        lang: str = "eng",
        articles_count: int = 30,
        sort_by: str = "date",
    ) -> list[dict[str, Any]]:
        """
        Fetch news articles matching search criteria.
        Returns normalized raw article items ready for Stage 2 pipeline normalization.
        """
        if not self.api_key:
            log.warning("NewsAPIClient: No API key configured. Skipping fetch.")
            return []

        payload: dict[str, Any] = {
            "apiKey": self.api_key,
            "resultType": "articles",
            "articlesCount": min(articles_count, 100),
            "articlesSortBy": sort_by,
            "articlesSortByAsc": False,
            "articleBodyLen": -1,  # Full body if available
            "includeArticleConcepts": True,
            "includeArticleCategories": True,
            "includeArticleImage": True,
            "lang": lang,
        }

        if keywords:
            payload["keyword"] = keywords
        if category_uri:
            payload["categoryUri"] = category_uri
        if source_uri:
            payload["sourceUri"] = source_uri

        try:
            response = requests.post(
                EVENT_REGISTRY_URL,
                json=payload,
                timeout=25,
            )
            response.raise_for_status()
            data = response.json()
            raw_articles = data.get("articles", {}).get("results", [])
            log.info("NewsAPIClient: fetched %d articles successfully", len(raw_articles))

            normalized: list[dict[str, Any]] = []
            for item in raw_articles:
                parsed = self._normalize_item(item)
                if parsed:
                    normalized.append(parsed)
            return normalized

        except requests.RequestException as exc:
            log.error("NewsAPIClient: request failed: %s", exc)
            return []

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Extract standard fields from Event Registry article object."""
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            return None

        # Parse publication date
        published_str = item.get("dateTimePub") or item.get("date")
        published_at = None
        if published_str:
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except ValueError:
                published_at = datetime.now(timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)

        # Source information
        source_info = item.get("source", {})
        source_name = source_info.get("title") or "Unknown Publisher"
        source_uri = source_info.get("uri")
        source_domain = source_info.get("dataType") or source_name.lower().replace(" ", "") + ".com"

        # Authors
        authors_raw = item.get("authors", [])
        authors = [a.get("name") for a in authors_raw if a.get("name")]

        return {
            "source_type": "newsapi",
            "url": url,
            "title": title.strip(),
            "description": item.get("body", "")[:300] if item.get("body") else None,
            "summary": item.get("body", "")[:500] if item.get("body") else None,
            "body": item.get("body"),
            "image_url": item.get("image"),
            "published_at": published_at,
            "language": item.get("lang", "en"),
            "source_name": source_name,
            "source_uri": source_uri,
            "source_domain": source_domain,
            "authors": authors,
            "raw_categories": [c.get("label") for c in item.get("categories", []) if c.get("label")],
            "raw_concepts": [
                {
                    "name": c.get("label", {}).get("eng") or c.get("uri"),
                    "uri": c.get("uri"),
                    "type": c.get("type"),
                    "score": c.get("score", 0.0),
                }
                for c in item.get("concepts", [])
            ],
        }
