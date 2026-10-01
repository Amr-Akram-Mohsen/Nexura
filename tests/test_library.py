"""
Tests for Nexura Library Page Polish & Endpoints:
- Library views (history and saved tabs)
- AJAX history removal and clear endpoints
- Reading history query deduplication
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import pytest

from app import create_app, db
from app.models.content import Content
from app.models.article import Article
from app.models.interaction import View, Save
from app.models.user import User
from app.repositories.user_repo import UserRepository


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["MAIL_ENABLED"] = False
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _get_or_create_library_user():
    user = UserRepository.get_by_email("library_user@nexura.tech")
    if not user:
        user = UserRepository.create(
            email="library_user@nexura.tech",
            password="Password123!",
            name="Library User",
            is_admin=False,
            is_verified=True,
        )
    else:
        user.is_admin = False
        user.is_verified = True
        UserRepository.update_password(user, "Password123!")
    return user


def _get_or_create_test_article(title="Library Test Article"):
    content = db.session.query(Content).filter(Content.title == title).first()
    if not content:
        article = Article(
            title=title,
            summary="Test summary for library tests.",
            status="published",
            word_count=200,
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
    return content


def test_library_index_unauthenticated(client):
    """Unauthenticated users should be redirected to login."""
    res = client.get("/library")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_library_index_authenticated(app, client):
    """Authenticated user should see the library page with both tabs."""
    with app.app_context():
        _get_or_create_library_user()

    client.post("/auth/login", data={"email": "library_user@nexura.tech", "password": "Password123!"})

    res = client.get("/library?tab=history")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "My Library" in html
    assert "Reading History" in html

    res_saved = client.get("/library?tab=saved")
    assert res_saved.status_code == 200
    html_saved = res_saved.get_data(as_text=True)
    assert "Saved Items" in html_saved


def test_library_history_remove_ajax(app, client):
    """Removing a history item via AJAX returns success: True."""
    with app.app_context():
        user = _get_or_create_library_user()
        article = _get_or_create_test_article("lib-history-remove-test")
        user_id = user.id
        article_id = article.id

        # Record a view
        v = View(user_id=user_id, content_id=article_id)
        db.session.add(v)
        db.session.commit()

    client.post("/auth/login", data={"email": "library_user@nexura.tech", "password": "Password123!"})

    res = client.post(
        f"/library/history/remove/{article_id}",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Verify removed from database
    with app.app_context():
        views = db.session.query(View).filter(View.user_id == user_id, View.content_id == article_id).all()
        assert len(views) == 0


def test_library_history_clear_ajax(app, client):
    """Clearing history via AJAX returns JSON success message."""
    with app.app_context():
        user = _get_or_create_library_user()
        article = _get_or_create_test_article("lib-history-clear-test")
        user_id = user.id
        article_id = article.id

        v = View(user_id=user_id, content_id=article_id)
        db.session.add(v)
        db.session.commit()

    client.post("/auth/login", data={"email": "library_user@nexura.tech", "password": "Password123!"})

    res = client.post(
        "/library/history/clear",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "cleared" in data["message"].lower()

    # Verify all views cleared for user
    with app.app_context():
        views = db.session.query(View).filter(View.user_id == user_id).all()
        assert len(views) == 0


def test_user_history_deduplication(app):
    """Reading history should deduplicate views of the same content item."""
    with app.app_context():
        user = _get_or_create_library_user()
        article = _get_or_create_test_article("lib-dedup-article")

        # Clear existing views for this user
        UserRepository.clear_user_history(user.id)

        # Add 3 views at different timestamps
        now = datetime.now(timezone.utc)
        v1 = View(user_id=user.id, content_id=article.id, created_at=now - timedelta(hours=3))
        v2 = View(user_id=user.id, content_id=article.id, created_at=now - timedelta(hours=2))
        v3 = View(user_id=user.id, content_id=article.id, created_at=now - timedelta(hours=1))
        db.session.add_all([v1, v2, v3])
        db.session.commit()

        items, total = UserRepository.get_user_history(user.id)
        assert total == 1
        assert len(items) == 1
        assert items[0].id == article.id
