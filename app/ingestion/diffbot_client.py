"""
Nexura Phase 7 — Diffbot Extraction Client (§8.1)
2-Phase extraction:
  Phase 1: Full Article Body Extraction (HTML, word count, media assets)
  Phase 2: Named Entity Recognition & Classification (Entities, Wikidata, Wikipedia)
"""
from __future__ import annotations
import logging
from typing import Any
import requests

from flask import current_app

log = logging.getLogger(__name__)

DIFFBOT_ARTICLE_API_URL = "https://api.diffbot.com/v3/article"


class DiffbotClient:
    """Client for Diffbot Article and Entity Extraction."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or (
            current_app.config.get("DIFFBOT_TOKEN") if current_app else None
        )

    def extract_article(self, target_url: str) -> dict[str, Any] | None:
        """
        Phase 1: Extract article body HTML, text, word count, images, and author.
        Phase 2: Extract tags/entities with confidence and relevance scores.
        """
        if not self.token:
            log.warning("DiffbotClient: No DIFFBOT_TOKEN configured. Skipping extraction.")
            return None

        params = {
            "token": self.token,
            "url": target_url,
            "discussion": "false",
            "extractPresence": "true",
        }

        try:
            res = requests.get(DIFFBOT_ARTICLE_API_URL, params=params, timeout=30)
            res.raise_for_status()
            data = res.json()

            objects = data.get("objects", [])
            if not objects:
                log.warning("DiffbotClient: No objects extracted for %s", target_url)
                return None

            obj = objects[0]

            # Phase 1: Core content payload
            content_html = obj.get("html") or ""
            content_text = obj.get("text") or ""
            word_count = len(content_text.split()) if content_text else 0

            # Images
            images = obj.get("images", [])
            primary_image = None
            if images and isinstance(images, list):
                primary_image = images[0].get("url")

            # Authors
            authors = []
            if obj.get("author"):
                authors.append(obj.get("author"))
            if obj.get("authors"):
                for a in obj.get("authors"):
                    name = a.get("name") if isinstance(a, dict) else str(a)
                    if name and name not in authors:
                        authors.append(name)

            # Phase 2: Entity tags
            raw_tags = obj.get("tags", [])
            extracted_entities: list[dict[str, Any]] = []
            for tag in raw_tags:
                label = tag.get("label")
                if not label:
                    continue

                extracted_entities.append({
                    "name": label.strip(),
                    "type": self._classify_entity_type(tag),
                    "wikidata_id": tag.get("wikidataUri", "").split("/")[-1] if tag.get("wikidataUri") else None,
                    "wikipedia_url": tag.get("wikipediaUrl") or tag.get("uri"),
                    "relevance_score": float(tag.get("score") or 0.0),
                    "confidence": float(tag.get("confidence") or 0.5),
                })

            return {
                "title": obj.get("title"),
                "content_html": content_html,
                "content_text": content_text,
                "summary": obj.get("summary") or (content_text[:400] if content_text else None),
                "word_count": word_count,
                "primary_image_url": primary_image or obj.get("icon"),
                "images": images,
                "videos": obj.get("videos", []),
                "authors": authors,
                "canonical_url": obj.get("pageUrl") or target_url,
                "language": obj.get("humanLanguage") or "en",
                "sentiment": float(obj.get("sentiment") or 0.0),
                "entities": extracted_entities,
            }

        except requests.RequestException as exc:
            log.error("DiffbotClient: extraction failed for %s: %s", target_url, exc)
            return None

    def _classify_entity_type(self, tag: dict[str, Any]) -> str:
        """Map Diffbot tag types to Phase 7 entity_type categories."""
        types = tag.get("types", [])
        if any("Brand" in t or "Product" in t for t in types):
            return "brand"
        if any("Organization" in t or "Company" in t for t in types):
            return "org"
        if any("Person" in t for t in types):
            return "person"
        if any("Location" in t or "Place" in t for t in types):
            return "loc"
        return "topic"
