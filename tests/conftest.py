"""Pytest configuration and test isolation fixtures."""
from __future__ import annotations
import pytest
from app import create_app, db
from app.models.content import Content, ContentEntity
from app.models.article import Article, ArticleSource
from app.models.interaction import Comment, Reaction, Save, View
from app.models.user import User

TEST_TITLES = [
    "High End GPU Architecture In-Depth",
    "Lifecycle Test Article",
    "Batch Action Test Article",
    "Quantum Computing Breakthrough 2026",
    "Comment Moderation Test Article",
]

TEST_EMAILS = [
    "interaction_tester@nexura.com",
    "regular_test@nexura.tech",
    "admin_test@nexura.tech",
]

def purge_test_artifacts(application) -> None:
    """Purge all test-created contents, articles, comments, and users from the database."""
    with application.app_context():
        try:
            # 1. Find and purge test contents & related interactions
            contents = db.session.query(Content).filter(Content.title.in_(TEST_TITLES)).all()
            if contents:
                c_ids = [c.id for c in contents]
                db.session.query(Comment).filter(Comment.content_id.in_(c_ids)).delete(synchronize_session=False)
                db.session.query(Reaction).filter(Reaction.target_type == "content", Reaction.target_id.in_(c_ids)).delete(synchronize_session=False)
                db.session.query(Save).filter(Save.content_id.in_(c_ids)).delete(synchronize_session=False)
                db.session.query(View).filter(View.content_id.in_(c_ids)).delete(synchronize_session=False)
                db.session.query(ContentEntity).filter(ContentEntity.content_id.in_(c_ids)).delete(synchronize_session=False)
                for c in contents:
                    db.session.delete(c)

            # 2. Purge test articles & sources
            articles = db.session.query(Article).filter(Article.title.in_(TEST_TITLES)).all()
            if articles:
                a_ids = [a.id for a in articles]
                db.session.query(ArticleSource).filter(ArticleSource.article_id.in_(a_ids)).delete(synchronize_session=False)
                for a in articles:
                    db.session.delete(a)

            # 3. Purge test users & any comments they made
            users = db.session.query(User).filter(User.email.in_(TEST_EMAILS)).all()
            if users:
                u_ids = [u.id for u in users]
                db.session.query(Comment).filter(Comment.user_id.in_(u_ids)).delete(synchronize_session=False)
                db.session.query(Reaction).filter(Reaction.user_id.in_(u_ids)).delete(synchronize_session=False)
                for u in users:
                    db.session.delete(u)

            db.session.commit()
        except Exception:
            db.session.rollback()

@pytest.fixture(scope="session")
def app():
    """Create testing application instance."""
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["RATELIMIT_ENABLED"] = False
    from app.extensions import limiter
    limiter.enabled = False
    yield application

@pytest.fixture(autouse=True)
def isolate_and_cleanup_test_db(app):
    """Automatically purge all test artifacts before and after each test."""
    purge_test_artifacts(app)
    yield
    purge_test_artifacts(app)
