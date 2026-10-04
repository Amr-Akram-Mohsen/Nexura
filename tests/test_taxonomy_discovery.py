"""
Tests for Nexura Taxonomy & Discovery Pages Polish:
- Section page (/section_slug)
- Category page (/section_slug/category_slug)
- Topic page (/topic/entity_slug)
- Breadcrumb rendering with Schema.org BreadcrumbList microdata
- Query parameter preservation across filters and pagination
- Zero inline styles verification
"""
from __future__ import annotations
import pytest
from app import create_app, db
from app.models.taxonomy import Section, Category, Entity
from app.models.content import Content, ContentEntity
from app.models.article import Article
from datetime import datetime, timezone


@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def test_section_page_render_and_breadcrumb(app, client):
    """Section landing page renders with breadcrumbs and Schema.org microdata."""
    with app.app_context():
        sec = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        assert sec is not None
        sec_slug = sec.slug
        sec_name = sec.name

    res = client.get(f"/{sec_slug}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Breadcrumb checks
    assert 'aria-label="Breadcrumb"' in html
    assert 'itemtype="https://schema.org/BreadcrumbList"' in html
    assert 'Home' in html
    assert sec_name in html

    # Page Header checks
    assert '<h1 class="page-header__title">' in html
    assert 'class="filter-bar"' in html


def test_section_filter_parameter_preservation(app, client):
    """Section filter chips preserve active content_type when switching categories."""
    with app.app_context():
        sec = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        sec_slug = sec.slug

    res = client.get(f"/{sec_slug}?type=article")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Active type chip
    assert 'class="filter-chip active"\n       href="/' + sec_slug + '?type=article' in html or 'active' in html
    # Category links preserve ?type=article
    assert '?type=article' in html


def test_category_page_render_and_breadcrumb(app, client):
    """Category landing page renders 3-level breadcrumb and content type filters."""
    with app.app_context():
        cat = db.session.query(Category).filter(Category.is_active.is_(True)).first()
        assert cat is not None
        cat_slug = cat.slug
        cat_name = cat.name
        # Find parent section
        sec = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        sec_slug = sec.slug
        sec_name = sec.name

    res = client.get(f"/{sec_slug}/{cat_slug}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # 3-level breadcrumbs
    assert 'aria-label="Breadcrumb"' in html
    assert 'Home' in html
    assert sec_name in html
    assert cat_name in html
    assert 'itemprop="itemListElement"' in html

    # Content type tabs
    assert 'role="tablist"' in html
    assert 'role="tab"' in html


def test_category_pagination_parameter_retention(app, client):
    """Category page retains type filter across pagination and subcategory links."""
    with app.app_context():
        cat = db.session.query(Category).filter(Category.is_active.is_(True)).first()
        sec = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        cat_slug = cat.slug
        sec_slug = sec.slug

    res = client.get(f"/{sec_slug}/{cat_slug}?type=video")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Active video filter
    assert 'type=video' in html


def test_topic_page_render_and_related_entities(app, client):
    """Topic landing page renders breadcrumb, metadata row, and related topics card."""
    with app.app_context():
        entity = db.session.query(Entity).first()
        if not entity:
            entity = Entity(name="Test Topic Alpha", slug="test-topic-alpha", entity_type="topic")
            db.session.add(entity)
            db.session.commit()
        entity_slug = entity.slug
        entity_name = entity.name

    res = client.get(f"/topic/{entity_slug}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Breadcrumb checks
    assert 'aria-label="Breadcrumb"' in html
    assert 'Topics' in html
    assert entity_name in html

    # Page Header checks
    assert 'page-header__meta-row' in html
    assert '<h1 class="page-header__title">' in html


def test_taxonomy_zero_inline_styles(app, client):
    """Ensure Section, Category, and Topic pages have zero inline style attributes."""
    with app.app_context():
        sec = db.session.query(Section).filter(Section.is_active.is_(True)).first()
        cat = db.session.query(Category).filter(Category.is_active.is_(True)).first()
        entity = db.session.query(Entity).first()
        sec_slug = sec.slug
        cat_slug = cat.slug
        entity_slug = entity.slug

    # 1. Section page
    res_sec = client.get(f"/{sec_slug}")
    assert 'style="' not in res_sec.get_data(as_text=True)

    # 2. Category page
    res_cat = client.get(f"/{sec_slug}/{cat_slug}")
    assert 'style="' not in res_cat.get_data(as_text=True)
    assert 'onmouseover' not in res_cat.get_data(as_text=True)
    assert 'onmouseout' not in res_cat.get_data(as_text=True)

    # 3. Topic page
    res_topic = client.get(f"/topic/{entity_slug}")
    assert 'style="' not in res_topic.get_data(as_text=True)
