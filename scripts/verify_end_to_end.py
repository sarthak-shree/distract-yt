"""Temporary end-to-end verification using an in-memory SQLite backend.

This proves the complete REST + DB + serialization layer works, without needing
a live PostgreSQL or a YouTube API key. Delete this file once the real
PostgreSQL connection is configured.
"""

import os
import sys
import tempfile

# Must be set BEFORE importing the app so config.py reads it.
_here = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(_here, "..", "src"))

tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + tmp.name
os.environ["YOUTUBE_API_KEY"] = "TEST_KEY"  # enough to import the client

from distract_yt import create_app  # noqa: E402
from distract_yt.db import init_db  # noqa: E402
from distract_yt import youtube  # noqa: E402
from distract_yt import api as _api_mod  # noqa: E402


class FakeYT(youtube.YouTubeClient):
    def __init__(self, api_key=None, session_factory=None):
        self._sf = session_factory
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")

    def channel_by_id(self, cid):
        return {"id": cid, "handle": "Ch1", "title": "Channel One",
                "description": "d", "thumbnail_url": "http://x/ch.png"}

    def resolve_channel_handle(self, handle):
        return self.channel_by_id("UCAAAAAAAAAAAAAAAAAAAAAA")

    def video_by_id(self, vid):
        return {"id": vid, "channel_id": None, "channel_name": "Solo",
                "title": "My Video", "description": "d",
                "thumbnail_url": "http://x/v.png", "duration_sec": 120,
                "published_at": "2024-01-01T00:00:00Z"}

    def playlist_by_id(self, pid):
        return {"id": pid, "title": "Playlist A", "description": "p",
                "thumbnail_url": None, "item_count": 2}

    def channel_videos(self, cid):
        return [{"id": f"v{i}", "title": f"C video {i}", "description": "",
                 "thumbnail_url": "http://x/c.png",
                 "published_at": "2024-01-01T00:00:00Z"} for i in range(2)]

    def playlist_videos(self, pid):
        return [{"id": f"pv{i}", "title": f"PV {i}", "channel_id": "UCc",
                 "channel_name": "Ch", "thumbnail_url": "http://x/p.png",
                 "published_at": "2024-01-01T00:00:00Z"} for i in range(2)]

    def search(self, q, kind="video", max_results=10):
        return [{"kind": kind, "id": f"id-{i}", "title": f"{kind} {i}",
                 "channel_name": "Ch", "channel_id": "c",
                 "thumbnail_url": "http://x/s.png", "description": ""}
                for i in range(2)]

    def _call(self, *a, **k):
        raise AssertionError("network call made on stub")


def main():
    init_db()
    app = create_app()
    app.config["TESTING"] = True

    # Stub the client in both references.
    youtube.YouTubeClient = FakeYT
    _api_mod.YouTubeClient = FakeYT

    c = app.test_client()

    checks = []

    def ok(cond, label):
        checks.append((bool(cond), label))

    ok(c.get("/").status_code == 200, "GET / serves index")
    ok(b"distract-yt" in c.get("/").data, "index references brand")
    ok(c.get("/watch/abc123def45").status_code == 200, "GET /watch/<id> serves")
    ok(c.get("/api/status").get_json()["ok"] is True, "GET /api/status ok")

    # channel add
    r = c.post("/api/channels", json={"id": "UCabc1234567890123456789"})
    ok(r.status_code == 201, "POST channel 201")
    chan = r.get_json()
    ok(chan["id"].startswith("UC"), "channel id persisted")
    ok(c.get("/api/channels").get_json()[0]["title"] == "Channel One", "channel listed")

    # duplicate add is idempotent (200)
    r2 = c.post("/api/channels", json={"id": "UCabc1234567890123456789"})
    ok(r2.status_code == 200, "duplicate channel -> 200")

    # import channel uploads
    r = c.post("/api/import/channel/UCabc1234567890123456789")
    ok(r.status_code == 200 and r.get_json()["added"] == 2, "import channel adds 2")
    ok(len(c.get("/api/videos").get_json()) >= 2, "videos present after import")

    # add a video directly
    r = c.post("/api/videos", json={"id": "abcdefghijk"})
    ok(r.status_code == 201, "POST video 201")

    # add a second channel so playlist-imported videos can attach to it
    c.post("/api/channels", json={"url": "https://youtube.com/channel/UCc"})

    # playlist
    r = c.post("/api/playlists", json={"id": "PLabc123456"})
    ok(r.status_code == 201, "POST playlist 201")
    r = c.post("/api/import/playlist/PLabc123456")
    ok(r.status_code == 200 and r.get_json()["added"] == 2, "import playlist adds 2")

    # search route works with stub
    r = c.get("/api/search?q=test&type=video")
    ok(r.status_code == 200 and isinstance(r.get_json(), list), "search returns list")

    # deletions
    ok(c.delete("/api/channels/UCabc1234567890123456789").status_code == 200, "del channel")
    ok(c.delete("/api/playlists/PLabc123456").status_code == 200, "del playlist")
    ok(c.get("/api/videos").get_json(), "videos remain after channel/playlist deletion")

    # validation errors
    ok(c.post("/api/videos", json={}).status_code == 400, "video w/o url -> 400")
    ok(c.delete("/api/videos/notfound123").status_code == 404, "delete missing video -> 404")

    # NEW: get single video
    ok(c.get("/api/videos/abcdefghijk").status_code == 200, "GET single video 200")
    ok(c.get("/api/videos/zzzzzzzzzzz").status_code == 404, "GET missing video 404")

    # NEW: channel filter on GET /api/videos
    before = [v["id"] for v in c.get("/api/videos").get_json()]
    fv = c.get("/api/videos?channel_id=UCc").get_json()  # stub imported playlist videos with channel 'UCc'
    ok(isinstance(fv, list) and all(v["channel_id"] == "UCc" for v in fv), "channel filter works")
    ok(len(fv) > 0, "channel filter returns results for playlist-imported videos")

    # NEW: clear all videos (bulk)
    r = c.delete("/api/videos")
    ok(r.status_code == 200 and r.get_json()["deleted"] == len(before), "bulk clear videos deletes count")
    ok(c.get("/api/videos").get_json() == [], "no videos remain after clear")
    # channels & playlists survive a bulk clear
    ok(len(c.get("/api/channels").get_json()) >= 1, "channels survive clear-all")
    ok(len(c.get("/api/playlists").get_json()) >= 1, "playlists survive clear-all")

    print("\n===== DISTRACT-YT END-TO-END (SQLite + stub) =====")
    failed = 0
    for ok_, label in checks:
        mark = "PASS" if ok_ else "FAIL"
        if not ok_:
            failed += 1
        print(f"  [{mark}] {label}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass