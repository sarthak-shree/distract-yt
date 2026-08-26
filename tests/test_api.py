"""Smoke tests that exercise the REST API against the configured PostgreSQL DB.

These require:
  - PostgreSQL up (port 5000 on this machine) and the `distract_yt` DB created
  - a valid YOUTUBE_API_KEY in `.env` (network calls are latency-based)

Run with:  uv run pytest -s
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def app():
    from distract_yt import create_app
    from distract_yt.db import init_db

    init_db()  # create tables (also surfaces DB config problems early)
    return create_app()


@pytest.fixture()
def client(app):
    client = app.test_client()
    # The library routes now require login. Register a user, logging in if the
    # account already exists from a previous run against the shared DB.
    r = client.post("/api/auth/register", json={"username": "tester", "password": "secret123"})
    if r.status_code not in (200, 201):
        client.post("/api/auth/login", json={"username": "tester", "password": "secret123"})
    return client


def test_index_serves(app):
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"distract-yt" in resp.data


def test_watch_page_serves(client):
    resp = client.get("/watch/dQw4w9WgXcQ")
    assert resp.status_code == 200
    assert b"video_id" in resp.data or b"youtube.com/iframe_api" in resp.data


def test_status_endpoint(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_list_endpoints_authenticated(client):
    # Authenticated client: library endpoints return JSON lists (the shared DB
    # may hold real data from previous runs, so we only assert shape, not size).
    assert isinstance(client.get("/api/videos").get_json(), list)
    assert isinstance(client.get("/api/channels").get_json(), list)
    assert isinstance(client.get("/api/playlists").get_json(), list)


def test_library_requires_login(app):
    # Unauthenticated requests to the library API are rejected with 401.
    anon = app.test_client()
    assert anon.get("/api/videos").status_code == 401
    assert anon.get("/api/channels").status_code == 401
    assert anon.get("/api/playlists").status_code == 401
    # ...but the health check stays public.
    assert anon.get("/api/status").status_code == 200


def test_add_requires_url(client):
    assert client.post("/api/videos", json={}).status_code == 400
    assert client.post("/api/channels", json={}).status_code == 400
    assert client.post("/api/playlists", json={"url": ""}).status_code == 400


@pytest.mark.skipif(not os.environ.get("YOUTUBE_API_KEY", "").strip(), reason="no API key")
def test_add_and_delete_video(client):
    # Rick Astley - Never Gonna Give You Up, a stable well-known video id
    rid = client.post("/api/videos", json={"id": "dQw4w9WgXcQ"})
    assert rid.status_code in (200, 201)
    vid = rid.get_json()["id"]
    assert vid == "dQw4w9WgXcQ"
    assert client.get("/api/videos").get_json()  # non-empty

    d = client.delete(f"/api/videos/{vid}")
    assert d.status_code == 200


@pytest.mark.skip("Set a real API key to enable live YouTube discovery tests.")
def test_search_live(client):
    r = client.get("/api/search?q=coding&type=video")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)