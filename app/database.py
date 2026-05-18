from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# connect_args only needed for SQLite (handles threading)
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,      # logs all SQL when DEBUG=true
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency. Yields a session, closes it after the
    request finishes — even if an exception is raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Call once at startup to create all tables."""
    # Import all models here so Base knows about them
    from app.models import claim, audit, policy, risk  # noqa: F401
    Base.metadata.create_all(bind=engine)