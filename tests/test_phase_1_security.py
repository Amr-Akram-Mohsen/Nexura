"""
Tests for Nexura Phase 1 Critical Security Fixes:
FIX-01: Email dispatch service & templates (graceful degradation)
FIX-02: Separation of email verification token and password reset token
FIX-03: Gated login on email verification + resend verification endpoint
FIX-04: Google OAuth nonce generation and replay protection
"""
from __future__ import annotations
from unittest.mock import patch

import pytest
from flask import session

from app import create_app, db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["MAIL_ENABLED"] = False
    yield app


@pytest.fixture(autouse=True)
def cleanup_users(app):
    with app.app_context():
        db.session.query(User).filter(User.email.in_([
            "phase1_test@nexura.tech",
            "phase1_reset@nexura.tech",
            "phase1_resend@nexura.tech",
        ])).delete(synchronize_session=False)
        db.session.commit()
    yield
    with app.app_context():
        db.session.query(User).filter(User.email.in_([
            "phase1_test@nexura.tech",
            "phase1_reset@nexura.tech",
            "phase1_resend@nexura.tech",
        ])).delete(synchronize_session=False)
        db.session.commit()


def test_fix01_and_fix02_registration_verification_flow(app):
    """Verify FIX-01 (email dispatch) and FIX-02 (separate verification token column)."""
    client = app.test_client()

    with patch.object(EmailService, "send_verification_email", return_value=True) as mock_send:
        res = client.post("/auth/register", data={
            "name": "Phase1 Tester",
            "email": "phase1_test@nexura.tech",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }, follow_redirects=True)

        assert res.status_code == 200
        assert mock_send.called

    with app.app_context():
        user = UserRepository.get_by_email("phase1_test@nexura.tech")
        assert user is not None
        assert user.is_verified is False
        assert user.email_verification_token is not None
        assert user.password_reset_token is None  # FIX-02: verification token must NOT be in password_reset_token
        verification_token = user.email_verification_token

        # Repository method works
        found_user = UserRepository.get_by_verification_token(verification_token)
        assert found_user is not None
        assert found_user.id == user.id

    # FIX-03: Attempt login before verification -> blocked
    res_login = client.post("/auth/login", data={
        "email": "phase1_test@nexura.tech",
        "password": "StrongPassword123!",
    })
    assert res_login.status_code == 200
    assert b"Please verify your email address before logging in" in res_login.data
    assert b"Resend verification email" in res_login.data

    # Verify email via link
    res_verify = client.get(f"/auth/verify/{verification_token}", follow_redirects=True)
    assert res_verify.status_code == 200
    assert b"Email verified! You can now log in." in res_verify.data

    with app.app_context():
        user = UserRepository.get_by_email("phase1_test@nexura.tech")
        assert user.is_verified is True
        assert user.email_verification_token is None

    # Now login succeeds
    res_success_login = client.post("/auth/login", data={
        "email": "phase1_test@nexura.tech",
        "password": "StrongPassword123!",
    }, follow_redirects=False)
    assert res_success_login.status_code == 302


def test_fix03_resend_verification_endpoint(app):
    """Verify FIX-03 /auth/resend-verification generates new token and dispatches email."""
    client = app.test_client()

    # Create unverified user
    with app.app_context():
        user = UserRepository.create(
            email="phase1_resend@nexura.tech",
            password="StrongPassword123!",
            name="Resend Tester",
            is_verified=False,
        )
        user.email_verification_token = "old_token_123"
        db.session.commit()

    with patch.object(EmailService, "send_verification_email", return_value=True) as mock_send:
        res = client.post("/auth/resend-verification", data={
            "email": "phase1_resend@nexura.tech",
        })
        assert res.status_code == 200
        assert mock_send.called
        assert b"Check your email" in res.data

    with app.app_context():
        user = UserRepository.get_by_email("phase1_resend@nexura.tech")
        assert user.email_verification_token is not None
        assert user.email_verification_token != "old_token_123"


def test_fix02_password_reset_separation(app):
    """Verify password reset uses password_reset_token and doesn't collide with verification."""
    client = app.test_client()

    with app.app_context():
        user = UserRepository.create(
            email="phase1_reset@nexura.tech",
            password="OriginalPassword123!",
            name="Reset Tester",
            is_verified=True,
        )

    with patch.object(EmailService, "send_password_reset_email", return_value=True) as mock_send:
        res = client.post("/auth/forgot-password", data={
            "email": "phase1_reset@nexura.tech",
        })
        assert res.status_code == 200
        assert mock_send.called

    with app.app_context():
        user = UserRepository.get_by_email("phase1_reset@nexura.tech")
        assert user.password_reset_token is not None
        assert user.email_verification_token is None


def test_fix04_google_oauth_nonce(app):
    """Verify FIX-04 stores nonce in session and passes it to authorize_redirect."""
    client = app.test_client()

    with app.test_request_context():
        with client.session_transaction() as sess:
            assert "oauth_nonce" not in sess

    # Test that /auth/google/login sets nonce
    from unittest.mock import MagicMock
    mock_google = MagicMock()
    mock_google.authorize_redirect.return_value = "redirected"

    original_client_id = app.config.get("GOOGLE_CLIENT_ID")
    original_google = getattr(app, "google", None)
    app.config["GOOGLE_CLIENT_ID"] = "mock_client_id"
    app.google = mock_google

    try:
        with client:
            client.get("/auth/google/login")
            assert "oauth_nonce" in session
            nonce = session["oauth_nonce"]
            assert len(nonce) > 10
            # Ensure authorize_redirect was called with nonce
            mock_google.authorize_redirect.assert_called_once()
            _, kwargs = mock_google.authorize_redirect.call_args
            assert kwargs.get("nonce") == nonce
    finally:
        app.config["GOOGLE_CLIENT_ID"] = original_client_id
        app.google = original_google


def test_email_service_graceful_degradation(app):
    """Verify EmailService logs link and returns False when MAIL_ENABLED is False."""
    with app.app_context():
        user = User(email="test_mail@nexura.tech", name="Mail Tester")
        assert EmailService.send_verification_email(user, "test-token-123") is False
        assert EmailService.send_password_reset_email(user, "test-token-456") is False
