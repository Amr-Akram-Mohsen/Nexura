"""
Nexura Phase 7 â€” Editorial Publishing Readiness Index (0â€“100)
Â§9.2: 5-dimension admin inspection score (separate from binary worker gate).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ReadinessResult:
    total: int
    core_metadata: int
    body_extraction: int
    taxonomy_mapping: int
    media_assets: int
    source_attribution: int

    @property
    def tier(self) -> str:
        if self.total >= 80:
            return "Ready"
        if self.total >= 60:
            return "Almost Ready"
        if self.total >= 40:
            return "Needs Work"
        return "Not Ready"

    @property
    def tier_class(self) -> str:
        return {
            "Ready": "success",
            "Almost Ready": "warning",
            "Needs Work": "warning",
            "Not Ready": "danger",
        }[self.tier]


def compute_readiness(article, content) -> ReadinessResult:
    """
    Compute the Editorial Readiness Index for an article.

    Phase 7 Â§9.2 components:
      Core Metadata     25 pts  â€” title, description, canonical_url
      Body & Extraction 30 pts  â€” word_count >= 150, content_html present
      Taxonomy Mapping  20 pts  â€” category assigned, >= 2 entity tags
      Media Assets      15 pts  â€” valid image_url
      Source Attribution 10 pts â€” known publisher, authority >= 40
    """
    core = 0
    if article.title:
        core += 10
    if article.description or article.summary:
        core += 8
    if article.canonical_url:
        core += 7

    body = 0
    if article.content_html:
        body += 15
    if article.word_count and article.word_count >= 150:
        body += 15

    taxonomy = 0
    if content and content.category_id:
        taxonomy += 10
    entity_count = len(content.content_entities) if content else 0
    if entity_count >= 2:
        taxonomy += 10

    media = 0
    if article.image_url:
        media += 15

    source = 0
    if content and content.source_id:
        source += 5
        if content.source and content.source.authority_score >= 40:
            source += 5

    total = core + body + taxonomy + media + source
    return ReadinessResult(
        total=min(total, 100),
        core_metadata=core,
        body_extraction=body,
        taxonomy_mapping=taxonomy,
        media_assets=media,
        source_attribution=source,
    )
