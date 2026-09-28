"""Add email_verification_token and email_verification_sent_at to users

Revision ID: 0004_email_verify_token
Revises: 0003_phase7_align
Create Date: 2026-09-28
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0004_email_verify_token"
down_revision = "0003_phase7_align"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email_verification_token", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("email_verification_sent_at", TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("email_verification_sent_at")
        batch_op.drop_column("email_verification_token")
