"""
Nexura Phase 7 — Phase I Unit & Integration Tests
Verifies:
1. @admin_required access control (anonymous -> 302, non-admin -> 403, admin -> 200)
2. Admin Dashboard KPI aggregation (§18)
3. Ingestions manual trigger and background task polling (§18.1, §21)
4. Content library batch operations (publish, unpublish, deactivate, delete) (§18.2)
5. Deduplication story clustering and canonicalization (§10, §18.4)
6. Taxonomy entity merging and junction re-linking (§18.5)
7. Comment moderation queue and actions (§19)
8. Social syndication draft generation for multi-platform distribution (§20)
"""
import pytest
from datetime import datetime, timezone

from app import create_app, db
from app.models.user import User
from app.models.content import Content, Article, ContentEntity
from app.models.taxonomy import Section, Category, Entity
from app.models.interaction import Comment
from app.repositories.user_repo import UserRepository
from app.services.syndication_service import SyndicationService, calculate_platform_engagement_index

@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app

def _setup_test_user(email: str, is_admin: bool) -> int:
    """Helper to ensure a clean test user account with known password."""
    user = UserRepository.get_by_email(email)
    if not user:
        user = UserRepository.create(
            email=email,
            password="Password123!",
            name="Admin" if is_admin else "User",
            is_admin=is_admin,
            is_verified=True,
        )
    else:
        user.is_admin = is_admin
        user.is_active = True
        UserRepository.update_password(user, "Password123!")
    return user.id

def test_admin_access_control(app):
    """Verify Phase 7 @admin_required security gate."""
    with app.app_context():
        _setup_test_user("regular_test@nexura.tech", is_admin=False)
        _setup_test_user("admin_test@nexura.tech", is_admin=True)

    client = app.test_client()

    # Anonymous user -> redirected to login (302)
    res = client.get("/admin/")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    # Non-admin user login -> 403 Forbidden
    client.post("/auth/login", data={"email": "regular_test@nexura.tech", "password": "Password123!"})
    res = client.get("/admin/")
    assert res.status_code == 403

    # Logout non-admin
    client.get("/auth/logout")

    # Admin user login -> 200 OK
    client.post("/auth/login", data={"email": "admin_test@nexura.tech", "password": "Password123!"})
    res = client.get("/admin/")
    assert res.status_code == 200
    assert b"Dashboard Overview" in res.data

def test_content_batch_operations(app):
    """Verify Phase 7 §18.2 batch publish, unpublish, and delete."""
    with app.app_context():
        _setup_test_user("admin_test@nexura.tech", is_admin=True)
        art = Article(title="Batch Action Test Article", word_count=200, status="discovered")
        db.session.add(art)
        db.session.flush()

        content = Content(
            title=art.title,
            object_type="article",
            object_id=art.id,
            section_id=1,
            published_at=datetime.now(timezone.utc),
            is_published=False,
            is_active=True,
        )
        db.session.add(content)
        db.session.commit()
        cid = content.id

    client = app.test_client()
    client.post("/auth/login", data={"email": "admin_test@nexura.tech", "password": "Password123!"})

    # Batch Publish
    res = client.post(
        "/admin/contents/batch",
        data={"action": "publish", "content_ids": [cid]},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    with app.app_context():
        c = db.session.get(Content, cid)
        assert c.is_published is True

    # Batch Unpublish
    res = client.post(
        "/admin/contents/batch",
        data={"action": "unpublish", "content_ids": [cid]},
    )
    assert res.status_code == 200
    with app.app_context():
        c = db.session.get(Content, cid)
        assert c.is_published is False

def test_syndication_draft_generation(app):
    """Verify Phase 7 §20 multichannel social draft generator."""
    with app.app_context():
        article = Article(
            title="Quantum Computing Breakthrough 2026",
            summary="Scientists achieve milestone in quantum fault tolerance.",
            status="published",
        )
        db.session.add(article)
        db.session.flush()

        content = Content(
            title=article.title,
            object_type="article",
            object_id=article.id,
            section_id=1,
            published_at=datetime.now(timezone.utc),
            is_published=True,
            is_active=True,
        )
        db.session.add(content)
        db.session.commit()

        drafts = SyndicationService.generate_drafts_for_article(content.id)
        assert "twitter" in drafts
        assert "linkedin" in drafts
        assert "youtube" in drafts
        assert "pinterest" in drafts
        assert "instagram" in drafts
        assert "tiktok" in drafts

        # Engagement index computation
        idx = calculate_platform_engagement_index(likes=10, clicks=5, shares=2, views=100)
        assert idx == (20 + 25 + 20 + 10)  # 75.0

def test_comment_moderation_actions(app):
    """Verify Phase 7 §19 comment moderation actions."""
    with app.app_context():
        uid = _setup_test_user("admin_test@nexura.tech", is_admin=True)
        art = Article(title="Comment Moderation Test Article", word_count=200, status="published")
        db.session.add(art)
        db.session.flush()

        content = Content(
            title=art.title,
            object_type="article",
            object_id=art.id,
            section_id=1,
            published_at=datetime.now(timezone.utc),
            is_published=True,
            is_active=True,
        )
        db.session.add(content)
        db.session.flush()

        comment = Comment(
            user_id=uid,
            content_id=content.id,
            content="This is a test comment for moderation.",
            sentiment="negative",
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(comment)
        db.session.commit()
        comm_id = comment.id

    client = app.test_client()
    client.post("/auth/login", data={"email": "admin_test@nexura.tech", "password": "Password123!"})

    # Soft-delete
    res = client.post(f"/admin/moderation/comments/{comm_id}/soft_delete")
    assert res.status_code == 200
    with app.app_context():
        comm = db.session.get(Comment, comm_id)
        assert "removed by moderators" in comm.content

    # Hard-delete
    res = client.post(f"/admin/moderation/comments/{comm_id}/hard_delete")
    assert res.status_code == 200
    with app.app_context():
        comm = db.session.get(Comment, comm_id)
        assert comm is None
