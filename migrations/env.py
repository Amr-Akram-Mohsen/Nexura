"""Alembic environment configuration."""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

from config import get_config

cfg = get_config()
alembic_config = context.config
alembic_config.set_main_option("sqlalchemy.url", cfg.SQLALCHEMY_DATABASE_URI)

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

from app.extensions import db  # noqa: E402
import app.models  # noqa: F401, E402

target_metadata = db.metadata

def run_migrations_offline() -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
