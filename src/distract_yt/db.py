"""Database engine, session management and schema initialisation."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .config import DATABASE_URL
from .models import Base

_state: dict = {"engine": None, "session_factory": None}


def _get_engine():
    if _state["engine"] is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Create a `.env` file in the project root "
                "with e.g. DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@"
                "localhost:5000/distract_yt"
            )
        _state["engine"] = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            echo=False,
        )
    return _state["engine"]


def init_db() -> None:
    """Create all tables. Calling this also verifies the DB is reachable."""
    Base.metadata.create_all(_get_engine())


def get_session_factory():
    if _state["session_factory"] is None:
        _state["session_factory"] = scoped_session(
            sessionmaker(bind=_get_engine(), expire_on_commit=False)
        )
    return _state["session_factory"]


def new_session():
    """Return a fresh ORM session (one per request/operation)."""
    return get_session_factory()()