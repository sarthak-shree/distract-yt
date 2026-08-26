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


def _migrate(engine) -> None:
    """Add columns introduced after the first release to existing tables.

    `create_all` only makes *new* tables, so tables that already exist need a
    small ALTER TABLE to pick up newly added columns. Missing columns are detected
    via the inspector so this is idempotent for both SQLite and PostgreSQL.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "playlists" not in insp.get_table_names():
        return
    existing = {col["name"] for col in insp.get_columns("playlists")}
    additions = {
        "channel_id": "channel_id VARCHAR",
        "channel_title": "channel_title VARCHAR",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE playlists ADD COLUMN {ddl}"))


def init_db() -> None:
    """Create all tables. Calling this also verifies the DB is reachable."""
    engine = _get_engine()
    Base.metadata.create_all(engine)
    _migrate(engine)


def get_session_factory():
    if _state["session_factory"] is None:
        _state["session_factory"] = scoped_session(
            sessionmaker(bind=_get_engine(), expire_on_commit=False)
        )
    return _state["session_factory"]


def new_session():
    """Return a fresh ORM session (one per request/operation)."""
    return get_session_factory()()