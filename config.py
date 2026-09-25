"""
Nexura Phase 7 — Application Configuration
Reads all sensitive values from environment variables; never hard-codes secrets.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration shared by all environments."""

    # ---------- Core Flask ----------
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-key-change-me")
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ---------- Database ----------
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/nexura_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # ---------- External APIs ----------
    DIFFBOT_TOKEN: str | None = os.environ.get("DIFFBOT_API_KEY") or os.environ.get("DIFFBOT_TOKEN")
    YOUTUBE_API_KEY: str | None = os.environ.get("YOUTUBE_API_KEY")
    NEWS_API_KEY: str | None = os.environ.get("NEWSAPI_AI_API_KEY") or os.environ.get("NEWS_API_KEY")
    HUGGINGFACE_API_KEY: str | None = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    HF_API_URL: str | None = os.environ.get("HF_API_URL", "https://amrmohsen-nexora-sentiment-api.hf.space/predict")

    # ---------- Google OAuth ----------
    GOOGLE_CLIENT_ID: str | None = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = os.environ.get("GOOGLE_CLIENT_SECRET")

    # ---------- Cache ----------
    REDIS_URL: str | None = os.environ.get("REDIS_URL")
    # SimpleCache fallback used when REDIS_URL is absent (see extensions.py)
    CACHE_TYPE: str = "RedisCache" if os.environ.get("REDIS_URL") else "SimpleCache"
    CACHE_REDIS_URL: str | None = os.environ.get("REDIS_URL")
    CACHE_DEFAULT_TIMEOUT: int = 300

    # ---------- Mail ----------
    MAIL_SERVER: str | None = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT: int = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS: bool = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME: str | None = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD: str | None = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER: str | None = os.environ.get("MAIL_DEFAULT_SENDER")
    MAIL_ENABLED: bool = os.environ.get("MAIL_ENABLED", "False").lower() == "true"

    # ---------- Rate Limiting ----------
    # Newsletter: 5/min, handle-interaction: 30/min (Phase 7 §26)
    RATELIMIT_STORAGE_URI: str = os.environ.get("REDIS_URL", "memory://")
    RATELIMIT_DEFAULT: str = "200 per minute"

    # ---------- Task Tracker ----------
    TASK_STATE_DIR: str = os.environ.get("TASK_STATE_DIR", "instance/tasks")


class DevelopmentConfig(Config):
    DEBUG: bool = True
    SESSION_COOKIE_SECURE: bool = False


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SAMESITE: str = "Strict"
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_size": 20,
        "max_overflow": 40,
        "pool_timeout": 30,
    }


class TestingConfig(Config):
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    WTF_CSRF_ENABLED: bool = False
    CACHE_TYPE: str = "SimpleCache"
    MAIL_ENABLED: bool = False
    RATELIMIT_ENABLED: bool = False


config_map: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    env = env or os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)

# ================================================
SOCIAL_LINKS = [
  ("facebook", "https://www.facebook.com/profile.php?id=61590735370977"),
  ("instagram", "https://instagram.com/nexorasignals"),
  ("pinterest", "https://pinterest.com/nexorasignals"),
  ("youtube", "https://youtube.com/@nexorasignals"),
  ("tiktok", "https://tiktok.com/@nexora.signals"),
  ("x", "https://x.com/nexorasignals")
]
