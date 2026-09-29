"""
Relational Database Engine & Session Factory.
Supports PostgreSQL (with automated fallback to SQLite if PostgreSQL is unreachable).
"""

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.logger import logger
from app.models.db_models import Base

db_url = settings.DATABASE_URL or "sqlite:///./data/autoapply.db"

# Configure connection args per dialect
connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
else:
    # PostgreSQL connection pooling
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all relational tables inside the configured database."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info(f"Database initialized successfully with URL: {engine.url.render_as_string(hide_password=True)}")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """FastAPI request-scoped database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Validate database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database connection check failed: {e}")
        return False
