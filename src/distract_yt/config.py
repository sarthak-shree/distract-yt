"""Application configuration.

Reads environment variables from a `.env` file located at the project root and
exposes the values the rest of the app needs.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# config.py lives at <root>/src/distract_yt/config.py, so we climb two levels
# to reach the project root (where `.env`  and the package live together).
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"

load_dotenv(ROOT_DIR / ".env", override=True)


def get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# PostgreSQL connection string. SQLAlchemy + psycopg3 dialect.
# NOTE: your local PostgreSQL currently listens on port 5000 (not 5432).
DATABASE_URL: str = get_env(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5000/distract_yt",
) or ""

# YouTube Data API v3 key (no OAuth needed for read-only public data).
YOUTUBE_API_KEY: str = get_env("YOUTUBE_API_KEY", "") or ""

# Web server settings. We default to 8000 because PostgreSQL already owns 5000.
HOST: str = get_env("HOST", "127.0.0.1") or "127.0.0.1"
PORT: int = int(get_env("PORT", "8000") or "8000")
DEBUG: bool = (get_env("DEBUG", "1") or "1") == "1"

# How long to keep YouTube API responses in the cache before refetching.
CACHE_TTL_SECONDS: int = int(get_env("CACHE_TTL_SECONDS", "86400") or "86400")

# Sign for the session cookies. In production set a long random value in `.env`.
SECRET_KEY: str = get_env("SECRET_KEY", "distract-yt-dev-secret-change-me") or "distract-yt-dev-secret-change-me"

# How many videos to pull when importing a channel (keeps quotas low).
CHANNEL_IMPORT_LIMIT: int = int(get_env("CHANNEL_IMPORT_LIMIT", "15") or "15")