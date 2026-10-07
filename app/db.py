import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DATABASE_URL = os.getenv("DATABASE_URL")


def normalize_db_url(url: str) -> str:
    """
    Railway injects postgres:// (or postgresql://) with no driver. Name
    psycopg2 explicitly: SQLAlchemy 2.1 changed the default Postgres driver
    to psycopg 3, which is not installed.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


if _DATABASE_URL:
    engine = create_engine(normalize_db_url(_DATABASE_URL))
else:
    _DB_PATH = Path(__file__).parent.parent / "app.db"
    engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from .models import Subscription, User  # noqa: F401 — needed to register metadata
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
