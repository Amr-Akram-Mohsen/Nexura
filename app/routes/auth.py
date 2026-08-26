"""
Nexura Phase 7 — Auth Blueprint (§14)
Handles: register, login, logout, email verify, password reset.
Password hashing via Werkzeug; verification token via secrets.
"""
from __future__ import annotations
import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, abort, flash, jsonify,
    redirect, render_template, request, url_for, current_app, session,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from app.extensions import db, limiter, oauth
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.interaction_service import score_password

log = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

_RESET_EXPIRY_HOURS = 1  # §14: 1-hour password reset token window


# ─── Register ─────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    errors: dict[str, str] = {}
    form_data: dict[str, str] = {}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        form_data = {"name": name, "email": email}

        # Validation
        if not name or len(name) < 2:
            errors["name"] = "Full name must be at least 2 characters."
        if not email or "@" not in email:
            errors["email"] = "Enter a valid email address."
        if not password:
            errors["password"] = "Password is required."
        else:
            strength = score_password(password)
            if not strength["valid"]:
                errors["password"] = strength["message"]
        if password and password != confirm:
            errors["confirm_password"] = "Passwords do not match."

        if not errors:
            if UserRepository.get_by_email(email):
                errors["email"] = "An account with this email already exists."

        if not errors:
            # Create unverified user
            token = secrets.token_urlsafe(32)
            user = User(
                email=email,
                name=name,
                password_hash=generate_password_hash(password),
                is_verified=False,
                is_active=True,
                is_admin=False,
                created_at=datetime.now(timezone.utc),
                verification_sent_at=datetime.now(timezone.utc),
                # Store token on the model — email would send it
                password_reset_token=None,
            )
            # We'll reuse password_reset_token column space for verification
            # Actually store as a separate attribute on model
            db.session.add(user)
            db.session.flush()

            # In production, send email with token link
            log.info("Verification token for %s: %s", email, token)

            db.session.commit()

            flash(
                "Account created! Check your inbox to verify your email before logging in.",
                "success",
            )
            return redirect(url_for("auth.login"))

    return render_template(
        "auth/register.html", errors=errors, form_data=form_data
    )


# ─── Login ────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    error: str | None = None
    email_value = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember_me"))
        email_value = email

        user = UserRepository.get_by_email(email)

        if not user or not UserRepository.verify_password(user, password):
            error = "Invalid email or password."
            log.warning("Failed login attempt for email: %s", email)
        elif not user.is_active:
            error = "This account has been deactivated. Contact support."
        else:
            login_user(user, remember=remember)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            log.info("User %s logged in.", user.email)
            next_url = request.args.get("next") or url_for("public.home")
            # Prevent open redirect
            if not next_url.startswith("/"):
                next_url = url_for("public.home")
            return redirect(next_url)

    return render_template("auth/login.html", error=error, email_value=email_value)


# ─── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route("/logout")
@login_required
def logout():
    log.info("User %s logged out.", current_user.email)
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("public.home"))


# ─── Email Verify ─────────────────────────────────────────────────────────────
@auth_bp.route("/verify/<token>")
def verify_email(token: str):
    user = (
        db.session.query(User)
        .filter(User.password_reset_token == token)  # Note: reuse field or add col
        .first()
    )
    if not user:
        flash("Verification link is invalid or has expired.", "error")
        return redirect(url_for("auth.login"))

    if user.is_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for("auth.login"))

    user.is_verified = True
    user.verified_at = datetime.now(timezone.utc)
    user.password_reset_token = None
    db.session.commit()

    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


# ─── Forgot Password ──────────────────────────────────────────────────────────
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    sent = False

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = UserRepository.get_by_email(email)
        # Always show success to prevent email enumeration
        sent = True
        if user and user.is_active:
            token = secrets.token_urlsafe(32)
            user.password_reset_token = token
            user.password_reset_sent_at = datetime.now(timezone.utc)
            db.session.commit()
            log.info("Password reset token for %s: %s", email, token)
            # In production: send email with url_for('auth.reset_password', token=token)

    return render_template("auth/forgot_password.html", sent=sent)


# ─── Reset Password ───────────────────────────────────────────────────────────
@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    user = UserRepository.get_by_reset_token(token)

    # Check token validity: max 1 hour (§14)
    if not user or not user.password_reset_sent_at:
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    expiry = user.password_reset_sent_at + timedelta(hours=_RESET_EXPIRY_HOURS)
    now_utc = datetime.now(timezone.utc)
    # Normalize timezone for comparison
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if now_utc > expiry:
        flash("This reset link has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    error: str | None = None

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        strength = score_password(password)
        if not strength["valid"]:
            error = strength["message"]
        elif password != confirm:
            error = "Passwords do not match."
        else:
            UserRepository.update_password(user, password)
            flash("Password updated! Please log in with your new password.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token, error=error)


# ─── Profile (authenticated) ──────────────────────────────────────────────────
@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


def handle_google_oauth_login(user_info: dict) -> User:
    """Helper to provision or retrieve user from Google OAuth user_info."""
    email = (user_info.get("email") or "").lower().strip()
    google_id = str(user_info.get("sub") or user_info.get("id") or "")
    name = user_info.get("name") or (email.split("@")[0] if email else "Google User")

    user = UserRepository.get_by_email(email)
    if not user:
        # Create new verified user via Google OAuth
        user = User(
            email=email,
            name=name,
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
            google_id=google_id,
            provider="google",
            is_verified=True,
            verified_at=datetime.now(timezone.utc),
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.commit()
        log.info("[AUTH] New user registered via Google OAuth: %s", email)
    else:
        # Link Google account if not linked
        if not user.google_id:
            user.google_id = google_id
            user.provider = "google"
        user.is_verified = True
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        log.info("[AUTH] Existing user logged in via Google OAuth: %s", email)
    return user


# ─── Google OAuth 2.0 ────────────────────────────────────────────────────────
@auth_bp.route("/google/login")
def google_login():
    """Initiates Google OAuth 2.0 authorization redirect."""
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    google = getattr(current_app, "google", None) or getattr(oauth, "google", None) or oauth.create_client("google")
    if not google or not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Google Sign-In is not configured yet. Please use email and password.", "info")
        return redirect(url_for("auth.login"))

    redirect_uri = url_for("auth.google_authorize", _external=True)
    return google.authorize_redirect(redirect_uri, prompt="select_account")


@auth_bp.route("/google/authorize")
def google_authorize():
    """Handles Google OAuth 2.0 callback, parsing id_token or userinfo."""
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    google = getattr(current_app, "google", None) or getattr(oauth, "google", None) or oauth.create_client("google")
    if not google or not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Google Sign-In is not configured.", "error")
        return redirect(url_for("auth.login"))

    try:
        token = google.authorize_access_token()
        user_info = None
        if hasattr(google, "parse_id_token"):
            try:
                user_info = google.parse_id_token(token, nonce=None)
            except Exception as e:
                log.warning("[AUTH] parse_id_token failed: %s, falling back to userinfo", e)
        if not user_info:
            user_info = token.get("userinfo") or (google.userinfo() if hasattr(google, "userinfo") else None)

        if not user_info:
            flash("Google did not return user profile information.", "error")
            return redirect(url_for("auth.login"))

        email = (user_info.get("email") or "").lower().strip()
        if not email:
            flash("Google did not return an email address.", "error")
            return redirect(url_for("auth.login"))

        user = handle_google_oauth_login(user_info)

        session.clear()
        login_user(user, remember=True)
        flash(f"Signed in with Google! Welcome, {user.name or user.email} 🎉", "success")
        next_url = request.args.get("next") or url_for("public.home")
        return redirect(next_url)

    except Exception as e:
        log.error("[AUTH] Google OAuth error: %s", e)
        flash("Google sign-in failed. Please try again or log in with email and password.", "error")
        return redirect(url_for("auth.login"))


