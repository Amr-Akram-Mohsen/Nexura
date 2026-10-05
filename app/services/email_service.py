"""Email dispatch service for user verification and password recovery."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from flask import current_app, render_template, url_for
from flask_mail import Message

from app.extensions import mail

if TYPE_CHECKING:
    from app.models.user import User

log = logging.getLogger(__name__)


class EmailService:
    """Service handling transactional emails with graceful fallback when mail is disabled."""

    @staticmethod
    def send_verification_email(user: User, token: str) -> bool:
        """Send account email verification link."""
        try:
            verify_url = url_for("auth.verify_email", token=token, _external=True)
        except Exception:
            verify_url = f"/auth/verify/{token}"

        if not current_app.config.get("MAIL_ENABLED", False):
            log.info("[EMAIL DISABLED] Verification link for %s: %s", user.email, verify_url)
            return False

        try:
            subject = "Verify your Nexura account"
            html_body = render_template("auth/email_verify.html", user=user, verify_url=verify_url)
            plain_body = (
                f"Hi {user.name or 'there'},\n\n"
                f"Please verify your email address by visiting the following link:\n"
                f"{verify_url}\n\n"
                f"If you did not create an account, you can safely ignore this email.\n\n"
                f"— The Nexura Team"
            )

            sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "noreply@nexura.tech"
            msg = Message(subject=subject, recipients=[user.email], html=html_body, body=plain_body, sender=sender)
            mail.send(msg)
            log.info("Verification email sent to %s", user.email)
            return True
        except Exception as e:
            log.error("Failed to send verification email to %s: %s", user.email, e)
            return False

    @staticmethod
    def send_password_reset_email(user: User, token: str) -> bool:
        """Send password reset link to user."""
        try:
            reset_url = url_for("auth.reset_password", token=token, _external=True)
        except Exception:
            reset_url = f"/auth/reset-password/{token}"

        if not current_app.config.get("MAIL_ENABLED", False):
            log.info("[EMAIL DISABLED] Password reset link for %s: %s", user.email, reset_url)
            return False

        try:
            subject = "Reset your Nexura password"
            html_body = render_template("auth/reset_password_email.html", user=user, reset_url=reset_url, expires_in_hours=1)
            plain_body = (
                f"Hi {user.name or 'there'},\n\n"
                f"We received a request to reset your password. Use the link below to set a new password:\n"
                f"{reset_url}\n\n"
                f"This link will expire in 1 hour. If you didn't request a reset, you can safely ignore this email.\n\n"
                f"— The Nexura Team"
            )

            sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "noreply@nexura.tech"
            msg = Message(subject=subject, recipients=[user.email], html=html_body, body=plain_body, sender=sender)
            mail.send(msg)
            log.info("Password reset email sent to %s", user.email)
            return True
        except Exception as e:
            log.error("Failed to send password reset email to %s: %s", user.email, e)
            return False

    @staticmethod
    def send_newsletter_confirmation(email: str, token: str) -> bool:
        """Send newsletter subscription confirmation link."""
        try:
            confirm_url = url_for("public.confirm_newsletter", token=token, _external=True)
        except Exception:
            confirm_url = f"/newsletter/confirm/{token}"

        if not current_app.config.get("MAIL_ENABLED", False):
            log.info("[EMAIL DISABLED] Newsletter confirmation link for %s: %s", email, confirm_url)
            return False

        try:
            subject = "Confirm your Nexura newsletter subscription"
            plain_body = (
                f"Hi,\n\n"
                f"Thank you for subscribing to Nexura's weekly technology digest!\n\n"
                f"Please confirm your subscription by clicking the link below:\n"
                f"{confirm_url}\n\n"
                f"If you did not request this subscription, you can safely ignore this email.\n\n"
                f"— The Nexura Team"
            )
            sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "noreply@nexura.tech"
            msg = Message(subject=subject, recipients=[email], body=plain_body, sender=sender)
            mail.send(msg)
            log.info("Newsletter confirmation email sent to %s", email)
            return True
        except Exception as e:
            log.error("Failed to send newsletter confirmation to %s: %s", email, e)
            return False


__all__ = ["EmailService"]
