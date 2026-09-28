"""
Tests for Nexura Phase 3 Search Quality Enhancement:
ENH-01: PostgreSQL Full-Text Search (TSVECTOR, GIN Index, ts_rank_cd, and Trigger)
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone

import pytest

from app import create_app, db
from app.models.content import Content
from app.models.article import Article
from app.models.taxonomy import Section
from app.repositories.search_repo import SearchRepository
from app.repositories.content_repo import ContentRepository


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["MAIL_ENABLED"] = False
    yield app


def _clean_test_records():
    try:
        test_contents = db.session.query(Content).filter(Content.title.like("Phase 3 Test%")).all()
        for c in test_contents:
            db.session.delete(c)
        test_articles = db.session.query(Article).filter(Article.title.like("Phase 3 Test%")).all()
        for a in test_articles:
            a.primary_source_id = None
            db.session.delete(a)
        db.session.commit()
    except Exception:
        db.session.rollback()


@pytest.fixture(autouse=True)
def clean_db(app):
    with app.app_context():
        _clean_test_records()
    yield
    with app.app_context():
        _clean_test_records()


def test_fts_trigger_populates_weighted_search_vector(app):
    """Verify that PostgreSQL trigger automatically populates search_vector with A, B, C weights on INSERT."""
    uid = secrets.token_hex(4)
    with app.app_context():
        section = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        assert section is not None

        c = Content(
            object_type="article",
            object_id=900000 + int(uid, 16) % 10000,
            published_at=datetime.now(timezone.utc),
            title=f"Phase 3 Test QuantumSuperconductor Title {uid}",
            preview_text=f"CryogenicMagnetism preview summary {uid}",
            search_text=f"SubatomicParticle deep technical analysis {uid}",
            is_active=True,
            is_published=True,
            section_id=section.id,
        )
        db.session.add(c)
        db.session.commit()

        # Reload from DB
        saved = db.session.query(Content.search_vector).filter(Content.id == c.id).scalar()
        assert saved is not None
        saved_str = str(saved).lower()

        # Title terms should have weight A
        assert "quantumsuperconductor':" in saved_str
        assert "a" in saved_str.split("quantumsuperconductor':")[1].split(" ")[0]

        # Preview terms should have weight B (stemmed by PostgreSQL English dictionary)
        assert "cryogenicmagnet':" in saved_str
        assert "b" in saved_str.split("cryogenicmagnet':")[1].split(" ")[0]

        # Search_text terms should have weight C (stemmed by PostgreSQL English dictionary)
        assert "subatomicparticl':" in saved_str
        assert "c" in saved_str.split("subatomicparticl':")[1].split(" ")[0]


def test_fts_relevance_ranking_orders_title_matches_above_body(app):
    """Verify that ts_rank_cd orders items with search terms in title (weight A) above body (weight C)."""
    uid = secrets.token_hex(4)
    keyword = f"ZetaProbe{uid}"

    with app.app_context():
        section = db.session.query(Section).filter(Section.is_active.is_(True)).first()

        # Item 1: Keyword only in body (Weight C)
        c1 = Content(
            object_type="article",
            object_id=910000 + int(uid, 16) % 10000,
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            title=f"Phase 3 Test Standard Mission Overview {uid}",
            preview_text="Routine telemetry and flight logs",
            search_text=f"Extensive report mentioning {keyword} deep in paragraph four.",
            is_active=True,
            is_published=True,
            section_id=section.id,
            score=50.0,
        )

        # Item 2: Keyword prominently in title (Weight A)
        c2 = Content(
            object_type="article",
            object_id=920000 + int(uid, 16) % 10000,
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            title=f"Phase 3 Test {keyword} {keyword} Discovery {uid}",
            preview_text=f"Breaking update regarding {keyword}",
            search_text="Brief technical summary.",
            is_active=True,
            is_published=True,
            section_id=section.id,
            score=10.0,
        )

        db.session.add_all([c1, c2])
        db.session.commit()

        # Perform search with sort="relevance"
        results, total = SearchRepository.search(keyword, sort="relevance")
        assert total >= 2

        # Item 2 (Title match with weight A) must rank before Item 1 (Body match with weight C)
        matched_ids = [item.id for item in results]
        assert c2.id in matched_ids
        assert c1.id in matched_ids
        assert matched_ids.index(c2.id) < matched_ids.index(c1.id)


def test_fts_filtering_and_pagination(app):
    """Verify section, object_type, and pagination options in SearchRepository.full_text_search."""
    uid = secrets.token_hex(4)
    keyword = f"HyperDrive{uid}"

    with app.app_context():
        sections = db.session.query(Section).filter(Section.is_active.is_(True)).limit(2).all()
        sec1 = sections[0]
        sec2 = sections[1] if len(sections) > 1 else sec1

        # Article in sec1
        c_art = Content(
            object_type="article",
            object_id=930000 + int(uid, 16) % 10000,
            published_at=datetime.now(timezone.utc),
            title=f"Phase 3 Test Article {keyword} {uid}",
            preview_text="Article preview",
            search_text=f"Details on {keyword}",
            is_active=True,
            is_published=True,
            section_id=sec1.id,
        )

        # Video in sec2
        c_vid = Content(
            object_type="video",
            object_id=940000 + int(uid, 16) % 10000,
            published_at=datetime.now(timezone.utc),
            title=f"Phase 3 Test Video {keyword} {uid}",
            preview_text="Video preview",
            search_text=f"Video footage of {keyword}",
            is_active=True,
            is_published=True,
            section_id=sec2.id,
        )

        db.session.add_all([c_art, c_vid])
        db.session.commit()

        # Filter by object_type="article"
        p_art = SearchRepository.full_text_search(keyword, object_type="article")
        assert all(item.object_type == "article" for item in p_art.items)
        art_ids = [item.id for item in p_art.items]
        assert c_art.id in art_ids
        assert c_vid.id not in art_ids

        # Filter by object_type="video"
        p_vid = SearchRepository.full_text_search(keyword, object_type="video")
        assert all(item.object_type == "video" for item in p_vid.items)
        vid_ids = [item.id for item in p_vid.items]
        assert c_vid.id in vid_ids
        assert c_art.id not in vid_ids

        # Filter by section_id
        p_sec1 = SearchRepository.full_text_search(keyword, section_id=sec1.id)
        sec1_ids = [item.id for item in p_sec1.items]
        assert c_art.id in sec1_ids

        # Test pagination container
        p_pag = SearchRepository.full_text_search(keyword, page=1, per_page=1)
        assert len(p_pag.items) == 1
        assert p_pag.total >= 2
        assert p_pag.pages >= 2


def test_fts_ilike_fallback_on_unindexed_substring(app):
    """Verify that queries matching 0 rows via FTS gracefully fallback to ILIKE pattern matching."""
    uid = secrets.token_hex(4)
    # Rare string with symbols that tsvector stemmer would ignore/strip
    unique_token = f"xyz_{uid}_123"

    with app.app_context():
        section = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        c = Content(
            object_type="article",
            object_id=950000 + int(uid, 16) % 10000,
            published_at=datetime.now(timezone.utc),
            title=f"Phase 3 Test Fallback {unique_token}",
            preview_text="Fallback preview test",
            search_text="Fallback body test",
            is_active=True,
            is_published=True,
            section_id=section.id,
        )
        db.session.add(c)
        db.session.commit()

        # Search with the token
        res, total = SearchRepository.search(unique_token)
        assert total >= 1
        found_ids = [item.id for item in res]
        assert c.id in found_ids
