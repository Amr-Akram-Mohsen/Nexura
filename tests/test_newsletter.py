"""
Tests for Nexura Newsletter & Weekly Digest feature:
- Subscription creation and duplicate handling
- Double opt-in confirmation token verification and database updates
- One-click unsubscribe token verification and status updates
- Recommendation-powered weekly digest compilation with reason attribution
- Zero forbidden inline styles across home, article, and video newsletter blocks
"""
from __future__ import annotations
import pytest
from app import create_app, db
from app.models.user import User, NewsletterSubscriber
from app.models.content import Content
from app.repositories.user_repo import UserRepository
from app.services.newsletter_service import (
    subscribe_newsletter,
    confirm_subscription,
    unsubscribe_newsletter,
    unsubscribe_current_user,
    unsubscribe_by_email,
    generate_weekly_digest,
)


@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["RATELIMIT_ENABLED"] = False
    from app.extensions import limiter
    limiter.enabled = False
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def test_newsletter_subscription_and_duplicate_handling(app, client):
    """Registering a new subscriber generates confirmation and unsubscribe tokens."""
    test_email = "newsletter_unit_tester@nexura.tech"

    # Clean up any existing record
    with app.app_context():
        existing = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

    # 1. Valid subscription via POST /subscribe
    res = client.post("/subscribe", data={"email": test_email})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "confirm your subscription" in data["message"].lower()

    # Verify database state
    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        assert sub is not None
        assert sub.is_confirmed is False
        assert sub.confirmation_token is not None
        assert sub.unsubscribe_token is not None
        assert sub.unsubscribed_at is None

    # 2. Duplicate submission before confirmation
    res_dup = client.post("/subscribe", data={"email": test_email})
    assert res_dup.status_code == 200
    assert res_dup.get_json()["success"] is True

    # 3. Duplicate submission after confirmation returns already_subscribed without asking to check inbox
    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        sub.is_confirmed = True
        db.session.commit()

    res_conf_dup = client.post("/subscribe", data={"email": test_email})
    assert res_conf_dup.status_code == 200
    dup_data = res_conf_dup.get_json()
    assert dup_data["success"] is True
    assert dup_data["already_subscribed"] is True
    assert dup_data["is_confirmed"] is True
    assert "already subscribed" in dup_data["message"].lower()
    assert "check your inbox" not in dup_data["message"].lower()

    # 4. Invalid email rejection
    res_inv = client.post("/subscribe", data={"email": "invalid-email-address"})
    assert res_inv.status_code == 400
    assert res_inv.get_json()["success"] is False


def test_newsletter_confirmation_flow(app, client):
    """Confirming subscription via token marks subscriber confirmed and clears token."""
    test_email = "confirm_test@nexura.tech"

    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        if sub:
            db.session.delete(sub)
            db.session.commit()

    # Subscribe to obtain token
    client.post("/subscribe", data={"email": test_email})

    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        assert sub is not None
        token = sub.confirmation_token

    # 1. Successful confirmation
    res_confirm = client.get(f"/newsletter/confirm/{token}")
    assert res_confirm.status_code == 200
    html = res_confirm.get_data(as_text=True)
    assert "Subscription Confirmed" in html
    assert "confirmed" in html.lower()

    # Verify DB state
    with app.app_context():
        sub_updated = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        assert sub_updated.is_confirmed is True
        assert sub_updated.confirmation_token is None

    # 2. Invalid / reused token
    res_invalid = client.get("/newsletter/confirm/non_existent_token_12345")
    assert res_invalid.status_code == 400
    html_inv = res_invalid.get_data(as_text=True)
    assert "Confirmation Failed" in html_inv


def test_newsletter_unsubscribe_flow(app, client):
    """Unsubscribing via token sets unsubscribed_at timestamp and sets is_confirmed to false."""
    test_email = "unsub_test@nexura.tech"

    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        if sub:
            db.session.delete(sub)
            db.session.commit()

    client.post("/subscribe", data={"email": test_email})

    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        unsub_token = sub.unsubscribe_token
        # First confirm the subscriber
        sub.is_confirmed = True
        db.session.commit()

    # 1. Unsubscribe via token
    res_unsub = client.get(f"/newsletter/unsubscribe/{unsub_token}")
    assert res_unsub.status_code == 200
    html = res_unsub.get_data(as_text=True)
    assert "Unsubscribed" in html

    # Verify DB state
    with app.app_context():
        sub_unsubbed = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == test_email).first()
        assert sub_unsubbed.is_confirmed is False
        assert sub_unsubbed.unsubscribed_at is not None

    # 2. Invalid token
    res_invalid = client.get("/newsletter/unsubscribe/bogus_unsub_token")
    assert res_invalid.status_code == 400
    assert "Unsubscribe Failed" in res_invalid.get_data(as_text=True)


def test_authenticated_newsletter_1click_and_conflict_protection(app, client):
    """Authenticated users get instant 1-click subscription and account conflict protection."""
    user_email = "newsletter_auth_tester@nexura.tech"
    with app.app_context():
        user = UserRepository.get_by_email(user_email)
        if not user:
            user = UserRepository.create(
                email=user_email,
                password="Password123!",
                name="Newsletter Auth Tester",
                is_admin=False,
                is_verified=True,
            )
        user_id = user.id
        # Clean up any subscriber record for this user or email
        existing_sub = db.session.query(NewsletterSubscriber).filter(
            (NewsletterSubscriber.email == user_email) | (NewsletterSubscriber.user_id == user_id)
        ).first()
        if existing_sub:
            db.session.delete(existing_sub)
            db.session.commit()

    # Login user
    res_login = client.post("/auth/login", data={"email": user_email, "password": "Password123!"})
    assert res_login.status_code in (200, 302)

    # 1. 1-Click Subscribe as authenticated user
    res_sub = client.post("/subscribe", data={"email": user_email})
    assert res_sub.status_code == 200
    data = res_sub.get_json()
    assert data["success"] is True
    assert data["is_confirmed"] is True
    assert data["already_subscribed"] is False
    assert "subscribed to nexura weekly" in data["message"].lower()

    # Verify database state
    with app.app_context():
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == user_email).first()
        assert sub is not None
        assert sub.is_confirmed is True
        assert sub.confirmation_token is None
        assert sub.user_id == user_id
        u = db.session.get(User, user_id)
        assert u.is_subscribed_to_newsletter is True

    # 2. Duplicate submission with same email returns already_subscribed without asking to check inbox
    res_dup = client.post("/subscribe", data={"email": user_email})
    assert res_dup.status_code == 200
    dup_data = res_dup.get_json()
    assert dup_data["success"] is True
    assert dup_data["already_subscribed"] is True
    assert dup_data["is_confirmed"] is True
    assert "already subscribed" in dup_data["message"].lower()
    assert "check your inbox" not in dup_data["message"].lower()

    # 3. Collision protection: attempt to subscribe with a different email while already subscribed
    res_conflict = client.post("/subscribe", data={"email": "different_auth_email@nexura.tech"})
    assert res_conflict.status_code == 400
    conflict_data = res_conflict.get_json()
    assert conflict_data["success"] is False
    assert "already subscribed as" in conflict_data["message"].lower()
    assert "unsubscribe first" in conflict_data["message"].lower()


def test_in_app_unsubscribe_endpoints(app, client):
    """POST /unsubscribe allows authenticated users and guests to unsubscribe directly."""
    user_email = "unsub_endpoint_user@nexura.tech"
    with app.app_context():
        user = UserRepository.get_by_email(user_email)
        if not user:
            user = UserRepository.create(
                email=user_email,
                password="Password123!",
                name="Unsub Tester",
                is_admin=False,
                is_verified=True,
            )
        existing_sub = db.session.query(NewsletterSubscriber).filter(
            (NewsletterSubscriber.email == user_email) | (NewsletterSubscriber.user_id == user.id)
        ).first()
        if existing_sub:
            db.session.delete(existing_sub)
            db.session.commit()

    # Login and subscribe
    client.post("/auth/login", data={"email": user_email, "password": "Password123!"})
    client.post("/subscribe", data={"email": user_email})

    with app.app_context():
        u = db.session.query(User).filter(User.email == user_email).first()
        assert u.is_subscribed_to_newsletter is True

    # 1. In-App Unsubscribe for authenticated user (no body required)
    res_unsub = client.post("/unsubscribe", data={})
    assert res_unsub.status_code == 200
    unsub_data = res_unsub.get_json()
    assert unsub_data["success"] is True
    assert "unsubscribed" in unsub_data["message"].lower()

    with app.app_context():
        u = db.session.query(User).filter(User.email == user_email).first()
        assert u.is_subscribed_to_newsletter is False
        sub = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == user_email).first()
        assert sub.is_confirmed is False
        assert sub.unsubscribed_at is not None

    # Logout client
    client.get("/auth/logout")

    # 2. Guest unsubscribe by email
    guest_email = "guest_unsub@nexura.tech"
    with app.app_context():
        sub_guest, _ = UserRepository.upsert_subscriber(guest_email)
        sub_guest.is_confirmed = True
        sub_guest.unsubscribed_at = None
        db.session.commit()

    res_guest_unsub = client.post("/unsubscribe", data={"email": guest_email})
    assert res_guest_unsub.status_code == 200
    assert res_guest_unsub.get_json()["success"] is True

    with app.app_context():
        sub_g = db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == guest_email).first()
        assert sub_g.is_confirmed is False
        assert sub_g.unsubscribed_at is not None

    # 3. Guest unsubscribe missing email
    res_no_email = client.post("/unsubscribe", data={})
    assert res_no_email.status_code == 400


def test_newsletter_template_rendering_states(app, client):
    """Verify templates correctly render guest form vs authenticated subscribed state."""
    # Logout first to guarantee guest state
    client.get("/auth/logout")

    # 1. Guest visits homepage: form visible, subscribed badge hidden
    res_guest = client.get("/")
    assert res_guest.status_code == 200
    guest_html = res_guest.get_data(as_text=True)
    assert 'data-newsletter-box' in guest_html
    assert 'class="newsletter-box__state-subscribed is-hidden"' in guest_html
    assert 'data-newsletter-form-container' in guest_html

    # 2. Authenticated subscribed user visits homepage
    user_email = "state_render_user@nexura.tech"
    with app.app_context():
        user = UserRepository.get_by_email(user_email)
        if not user:
            user = UserRepository.create(
                email=user_email,
                password="Password123!",
                name="State Render User",
                is_admin=False,
                is_verified=True,
            )
        sub, _ = UserRepository.upsert_subscriber(user_email, user_id=user.id)
        sub.is_confirmed = True
        sub.unsubscribed_at = None
        db.session.commit()

    client.post("/auth/login", data={"email": user_email, "password": "Password123!"})
    res_auth = client.get("/")
    assert res_auth.status_code == 200
    auth_html = res_auth.get_data(as_text=True)
    assert 'data-newsletter-subscribed' in auth_html
    assert 'class="newsletter-box__state-form is-hidden"' in auth_html
    assert user_email in auth_html
    assert 'data-action="unsubscribe-newsletter"' in auth_html

    # 3. Authenticated UNsubscribed user visits homepage:
    # Sees 1-click button and their email mentioned, but NO text input field!
    with app.app_context():
        sub.is_confirmed = False
        db.session.commit()

    res_auth_unsub = client.get("/")
    assert res_auth_unsub.status_code == 200
    unsub_html = res_auth_unsub.get_data(as_text=True)
    assert 'data-newsletter-auth-email' in unsub_html
    assert user_email in unsub_html
    assert 'Subscribe with 1-Click' in unsub_html
    assert '<input class="newsletter-form__input"' not in unsub_html
    assert '<input type="hidden" name="email"' in unsub_html


def test_newsletter_weekly_digest_generation(app):
    """Weekly digest compiler produces cards enriched with recommendation attribution reasons."""
    with app.app_context():
        # 1. Guest digest (trending-based)
        digest = generate_weekly_digest(user_id=None, limit=5)
        assert isinstance(digest, list)
        if digest:
            first = digest[0]
            assert "title" in first
            assert "url" in first
            assert "recommendation_reason" in first
            assert first["recommendation_reason"] is not None

        # 2. Authenticated digest
        user_digest = generate_weekly_digest(user_id=1, limit=5)
        assert isinstance(user_digest, list)


def test_newsletter_zero_inline_styles(app, client):
    """Confirm newsletter CTA boxes on homepage, article, and video pages have zero forbidden inline styles."""
    with app.app_context():
        art = db.session.query(Content).filter(Content.object_type == "article", Content.is_published.is_(True)).first()
        vid = db.session.query(Content).filter(Content.object_type == "video", Content.is_published.is_(True)).first()
        art_slug = art.slug_id if art else "1"
        vid_slug = vid.slug_id if vid else "2"

    forbidden_patterns = [
        "margin-bottom: var(--space-16);",
        "max-width: 560px;",
        "flex-direction: row;",
        "font-size:var(--text-md);",
        "flex: 1;",
    ]

    # Homepage
    home_html = client.get("/").get_data(as_text=True)
    assert 'class="newsletter-section"' in home_html
    assert 'class="newsletter-box newsletter-box--featured"' in home_html
    assert 'class="newsletter-form newsletter-form--inline"' in home_html
    for pat in forbidden_patterns:
        assert pat not in home_html

    # Article Page
    art_html = client.get(f"/article/{art_slug}").get_data(as_text=True)
    assert 'class="newsletter-box"' in art_html
    assert 'id="sidebar-subscribe-btn"' in art_html
    for pat in forbidden_patterns:
        assert pat not in art_html

    # Video Page
    vid_html = client.get(f"/video/{vid_slug}").get_data(as_text=True)
    assert 'class="newsletter-box"' in vid_html
    assert 'id="video-sidebar-subscribe-btn"' in vid_html
    for pat in forbidden_patterns:
        assert pat not in vid_html
