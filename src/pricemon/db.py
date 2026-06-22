"""Database engine/session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DB_PATH
from .models import Base

_engine = None
_SessionFactory = None


def init_engine(db_path: Path = DB_PATH):
    global _engine, _SessionFactory
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", future=True)
    _SessionFactory = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    return _engine


@contextmanager
def session_scope():
    if _SessionFactory is None:
        init_engine()
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """Non-context session for FastAPI dependency use."""
    if _SessionFactory is None:
        init_engine()
    return _SessionFactory()
