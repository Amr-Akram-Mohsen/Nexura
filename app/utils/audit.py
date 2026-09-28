"""Security and administrative audit event logger."""
from __future__ import annotations
import logging
from typing import Any
from app.extensions import db
from app.models.audit import AuditLog

log = logging.getLogger(__name__)


def log_event(
    event_type: str,
    *,
    user_id: int | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog | None:
    """Safely record an audit log event without raising exceptions into request flow."""
    try:
        entry = AuditLog(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
        )
        db.session.add(entry)
        db.session.commit()
        return entry
    except Exception as exc:
        db.session.rollback()
        log.warning("Failed to record audit event %s: %s", event_type, exc)
        return None
