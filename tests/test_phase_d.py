import pytest
from app import create_app, db
from app.repositories import (
    ContentRepository, ArticleRepository, VideoRepository,
    TaxonomyRepository, UserRepository, SearchRepository, AnalyticsRepository
)
from app.serializers.content_serializers import (
    serialize_content_card, serialize_content_detail,
    serialize_section, serialize_category, serialize_entity
)
from app.serializers.utils import compact_dict
from app.utils.sanitizer import sanitize_html, sanitize_text, canonicalize_url
from app.utils.readiness import compute_readiness
from app.utils.slugify import make_slug


@pytest.fixture(scope="module")
def app():
    app = create_app()
    yield app


def test_content_repository_listing_and_filtering(app):
    with app.app_context():
        # General list
        contents, total = ContentRepository.list_contents(page=1, per_page=10)
        assert len(contents) > 0
        assert total > 0

        # Section filter
        sections = TaxonomyRepository.get_sections()
        if sections:
            s_contents, s_total = ContentRepository.list_contents(section_slug=sections[0].slug, page=1, per_page=5)
            assert isinstance(s_contents, list)

        # Category filter
        categories = TaxonomyRepository.get_categories(leaf_only=True)
        if categories:
            c_contents, c_total = ContentRepository.list_contents(category_slug=categories[0].slug, page=1, per_page=5)
            assert isinstance(c_contents, list)

        # Sort variants
        for sort_key in ["latest", "popular", "score", "top_reviewed"]:
            res, _ = ContentRepository.list_contents(sort=sort_key, page=1, per_page=3)
            assert len(res) <= 3


def test_content_hero_and_trending(app):
    with app.app_context():
        hero = ContentRepository.get_featured_hero()
        if hero:
            assert hero.is_published is True
            assert hero.is_active is True

        trending = ContentRepository.get_trending(limit=5)
        assert len(trending) <= 5


def test_article_and_video_repositories(app):
    with app.app_context():
        contents, _ = ContentRepository.list_contents(object_type="article", page=1, per_page=1)
        if contents:
            article = ArticleRepository.get_by_id(contents[0].object_id)
            assert article is not None
            assert article.id == contents[0].object_id

        v_contents, _ = ContentRepository.list_contents(object_type="video", page=1, per_page=1)
        if v_contents:
            video = VideoRepository.get_by_id(v_contents[0].object_id)
            assert video is not None
            assert video.id == v_contents[0].object_id


def test_taxonomy_repository(app):
    with app.app_context():
        sections = TaxonomyRepository.get_sections()
        assert len(sections) >= 5

        categories = TaxonomyRepository.get_categories()
        assert len(categories) > 0

        brands = TaxonomyRepository.get_entities_by_type("brand", limit=10)
        assert len(brands) == 10

        popular_entities = TaxonomyRepository.get_popular_entities(limit=5)
        assert len(popular_entities) > 0

        sources = TaxonomyRepository.get_sources()
        assert len(sources) > 0

        facets = TaxonomyRepository.get_facets()
        assert len(facets["intents"]) == 11
        assert len(facets["genders"]) == 3
        assert len(facets["price_tiers"]) == 4


def test_search_and_autocomplete(app):
    with app.app_context():
        results, total = SearchRepository.search("apple", page=1, per_page=5)
        assert isinstance(results, list)

        suggestions = SearchRepository.autocomplete_suggestions("app", limit=6)
        assert isinstance(suggestions, list)
        for s in suggestions:
            assert "label" in s
            assert "url" in s


def test_analytics_and_interactions(app):
    with app.app_context():
        contents, _ = ContentRepository.list_contents(page=1, per_page=1)
        if contents:
            cid = contents[0].id
            initial_views = contents[0].view_count or 0

            # Record anonymous view
            AnalyticsRepository.record_view(cid, ip_address="127.0.0.1")
            updated = ContentRepository.get_by_id(cid)
            assert updated.view_count == initial_views + 1

            # Test reaction service
            from app.models.user import User
            from app.services.interaction_service import toggle_reaction, toggle_save
            user = db.session.query(User).first()
            if not user:
                user = User(email="interaction_tester@nexura.com", name="Tester", password_hash="hash")
                db.session.add(user)
                db.session.commit()

            test_user_id = user.id

            # 1. Like
            res_like = toggle_reaction(test_user_id, cid, "like")
            assert res_like["success"] is True
            assert res_like["liked"] is True
            assert res_like["disliked"] is False
            assert res_like["like_count"] >= 1

            # 2. Swap to Dislike
            res_dislike = toggle_reaction(test_user_id, cid, "dislike")
            assert res_dislike["success"] is True
            assert res_dislike["liked"] is False
            assert res_dislike["disliked"] is True
            assert res_dislike["dislike_count"] >= 1

            # 3. Untoggle Dislike
            res_untoggle = toggle_reaction(test_user_id, cid, "dislike")
            assert res_untoggle["success"] is True
            assert res_untoggle["liked"] is False
            assert res_untoggle["disliked"] is False

            # 4. Save and Unsave
            res_save = toggle_save(test_user_id, cid)
            assert res_save["success"] is True
            assert res_save["saved"] is True

            res_unsave = toggle_save(test_user_id, cid)
            assert res_unsave["success"] is True
            assert res_unsave["saved"] is False




def test_serializers_and_compaction(app):
    with app.app_context():
        contents, _ = ContentRepository.list_contents(page=1, per_page=2)
        assert len(contents) > 0

        card = serialize_content_card(contents[0])
        assert isinstance(card, dict)
        assert "id" in card
        assert "title" in card

        # Test compact_dict
        sparse = {"a": 1, "b": None, "c": "", "d": [], "e": {"nested": None, "val": 2}}
        compacted = compact_dict(sparse)
        assert "b" not in compacted
        assert "c" not in compacted
        assert "d" not in compacted
        assert compacted["e"] == {"val": 2}


def test_sanitizer_and_readiness():
    raw_html = '<p>Hello <script>alert("xss")</script><style>body{color:red}</style><a href="https://example.com?utm_source=test&ref=123">World</a></p>'
    clean = sanitize_html(raw_html)
    assert "<script>" not in clean
    assert "alert" not in clean
    assert "<style>" not in clean
    assert "body{color:red}" not in clean
    assert "<p>" in clean

    plain = sanitize_text("<p>Hello <strong>World</strong></p>")
    assert plain == "Hello World"

    clean_url = canonicalize_url("https://example.com/article?utm_source=news&fbclid=abc&page=2")
    assert "utm_source" not in clean_url
    assert "fbclid" not in clean_url
    assert "page=2" in clean_url

    slug = make_slug("Tech & Science 2026: The Next Wave")
    assert slug == "tech-science-2026-the-next-wave"
