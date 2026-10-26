"""merge divergent migration heads

Revision ID: c7202c7942e3
Revises: 0006_add_audit_logs, 3bfe72c14c42
Create Date: 2026-10-26 22:33:29.998269

"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7202c7942e3'
down_revision: Union[str, None] = ('0006_add_audit_logs', '3bfe72c14c42')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
