"""
Nexura Phase 7 â€” Model package
Import all model modules here so SQLAlchemy/Alembic discovers them.
"""
from app.models import taxonomy  # noqa: F401
from app.models import source    # noqa: F401
from app.models import content   # noqa: F401
from app.models import video     # noqa: F401
from app.models import user      # noqa: F401
from app.models import interaction   # noqa: F401
from app.models import recommendation  # noqa: F401
from app.models import distribution  # noqa: F401
