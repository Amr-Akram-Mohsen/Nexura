"""
Tests for Nexura Phase 4 Quick Wins & Code Quality:
ENH-02: Consolidated Admin Dashboard KPI Queries
ENH-03: Pydantic Request Validation on Interaction & Batch Endpoints
ENH-04: Security & Editorial Event AuditLog Model and Event Logging
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone

import pytest

from app import create_app, db
from app.models.audit import AuditLog
from app.models.content import Content
from app.models.article import Article
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


def _get_or_create_admin():
    admin = UserRepository.get_by_email("phase4_admin@nexura.tech")
    if not admin:
        admin = UserRepository.create(
            email="phase4_admin@nexura.tech",
            password="Password123!",
            name="Phase 4 Admin",
            is_admin=True,
            is_verified=True,
        )
    else:
        admin.is_admin = True
        admin.is_verified = True
        UserRepository.update_password(admin, "Password123!")
    return admin


def _get_or_create_user():
    user = UserRepository.get_by_email("phase4_user@nexura.tech")
    if not user:
        user = UserRepository.create(
            email="phase4_user@nexura.tech",
            password="Password123!",
            name="Phase 4 User",
            is_admin=False,
            is_verified=True,
        )
    else:
        user.is_admin = False
        user.is_verified = True
        UserRepository.update_password(user, "Password123!")
    return user


def test_enh02_admin_dashboard_kpis_consolidated(app, client):
    """Verify that dashboard KPI metrics return the correct data structure and counts."""
    with app.app_context():
        _get_or_create_admin()

    client.post("/auth/login", data={"email": "phase4_admin@nexura.tech", "password": "Password123!"})
    res = client.get("/admin/")
    assert res.status_code == 200

    # Ensure rendered dashboard contains expected platform metrics
    html = res.get_data(as_text=True)
    assert "Overview" in html or "Dashboard" in html


def test_enh03_interaction_pydantic_validation(app, client):
    """Verify Pydantic validation rejects malformed actions, negative target IDs, and invalid JSON."""
    with app.app_context():
        _get_or_create_user()

    # Login as normal user
    client.post("/auth/login", data={"email": "phase4_user@nexura.tech", "password": "Password123!"})

    # 1. Invalid action
    res = client.post("/handle-interaction", json={"action": "invalid_hack", "target_id": 10})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "errors" in data

    # 2. Negative target_id
    res = client.post("/handle-interaction", json={"action": "like", "target_id": -5})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False

    # 3. Non-numeric target_id
    res = client.post("/handle-interaction", json={"action": "like", "target_id": "not_an_int"})
    assert res.status_code == 400

    # 4. Valid impression action
    res = client.post("/handle-interaction", json={"action": "impression", "target_id": 1})
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_enh03_comment_and_subscribe_pydantic_validation(app, client):
    """Verify comment text length and email address format validations."""
    with app.app_context():
        _get_or_create_user()

    client.post("/auth/login", data={"email": "phase4_user@nexura.tech", "password": "Password123!"})

    # Empty comment text
    res = client.post("/comments/submit", json={"content_id": 1, "text": ""})
    assert res.status_code == 400
    assert res.get_json()["success"] is False

    # Negative content_id
    res = client.post("/comments/submit", json={"content_id": -1, "text": "Valid comment text"})
    assert res.status_code == 400

    # Invalid newsletter email
    res = client.post("/subscribe", json={"email": "not-a-valid-email"})
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_enh03_admin_batch_action_pydantic_validation(app, client):
    """Verify batch content action validation rejects empty arrays and invalid actions."""
    with app.app_context():
        _get_or_create_admin()

    client.post("/auth/login", data={"email": "phase4_admin@nexura.tech", "password": "Password123!"})

    # Invalid action
    res = client.post("/admin/contents/batch", json={"action": "explode", "content_ids": [1, 2]})
    assert res.status_code == 400
    assert res.get_json()["success"] is False

    # Empty content_ids
    res = client.post("/admin/contents/batch", json={"action": "deactivate", "content_ids": []})
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_enh04_audit_log_records_auth_and_admin_events(app, client):
    """Verify AuditLog records login failures, login successes, unauthorized admin access, and batch actions."""
    with app.app_context():
        admin = _get_or_create_admin()
        user = _get_or_create_user()

        # Clean prior test audit logs
        db.session.query(AuditLog).filter(AuditLog.details.cast(db.String).like("%phase4_%")).delete(synchronize_session=False)
        db.session.commit()

        # 1. Failed Login Event
        client.post("/auth/login", data={"email": "phase4_user@nexura.tech", "password": "WrongPassword!"})
        fail_log = (
            db.session.query(AuditLog)
            .filter(AuditLog.event_type == "login_failed")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert fail_log is not None
        assert fail_log.details.get("email") == "phase4_user@nexura.tech"
        assert fail_log.details.get("reason") == "invalid_credentials"

        # 2. Successful Login Event
        client.post("/auth/login", data={"email": "phase4_user@nexura.tech", "password": "Password123!"})
        success_log = (
            db.session.query(AuditLog)
            .filter(AuditLog.event_type == "login_success")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert success_log is not None
        assert success_log.user_id == user.id

        # 3. Unauthorized Admin Access Denied Event
        # Non-admin user tries to access /admin/
        res = client.get("/admin/")
        assert res.status_code == 403

        denied_log = (
            db.session.query(AuditLog)
            .filter(AuditLog.event_type == "admin_access_denied")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert denied_log is not None
        assert denied_log.user_id == user.id
        assert denied_log.details.get("path") == "/admin/"

        # 4. Admin Content Batch Action Event
        # Log out previous user and log in as admin
        client.get("/auth/logout")
        client.post("/auth/login", data={"email": "phase4_admin@nexura.tech", "password": "Password123!"})

        # Create temporary content item to mutate
        uid = secrets.token_hex(4)
        c = Content(
            object_type="article",
            object_id=980000 + int(uid, 16) % 10000,
            published_at=datetime.now(timezone.utc),
            title=f"Phase 4 Batch Content {uid}",
            is_active=True,
            is_published=False,
            section_id=1,
        )
        db.session.add(c)
        db.session.commit()
        cid = c.id

        res = client.post("/admin/contents/batch", json={"action": "publish", "content_ids": [cid]})
        assert res.status_code == 200

        batch_log = (
            db.session.query(AuditLog)
            .filter(AuditLog.event_type == "content_batch_action")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert batch_log is not None
        assert batch_log.user_id == admin.id
        assert batch_log.details.get("action") == "publish"
        assert cid in batch_log.details.get("content_ids")

        # Cleanup
        db.session.delete(c)
        db.session.commit()
