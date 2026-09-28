"""AuditLog model for recording security, authentication, and administrative actions."""
from __future__ import annotations
from sqlalchemy import Column, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db


class AuditLog(db.Model):
    """Security, authentication, and editorial audit trail."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<AuditLog {self.id} {self.event_type} user={self.user_id}>"
