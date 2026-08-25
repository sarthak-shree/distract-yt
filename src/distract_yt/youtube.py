"""Thin client for the YouTube Data API v3.

All calls go against the public REST API with a single API key (no OAuth).
Responses are cached in the `api_cache` table for `config.CACHE_TTL_SECONDS`
so the app stays well inside the free-tier quota (10,000 units/day).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import requests

from . import config
from .models import ApiCache

_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeError(Exception):
    """Raised for API/auth/quota problems."""


def _parse_duration_to_seconds(duration: str) -> int | None:
    """Convert an ISO-8601 duration like PT1H2M3S into seconds."""
    if not duration:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not m:
        return None
    h, min_, s_ = m.groups()
    return int(h or 0) * 3600 + int(min_ or 0) * 60 + int(s_ or 0)


def extract_ids(text: str) -> dict[str, str | None]:
    """Best-effort parse of a channel/video/playlist id from a URL or raw id."""
    result: dict[str, str | None] = {"channel": None, "video": None, "playlist": None}
    text = (text or "").strip()
    if not text:
        return result

    if re.fullmatch(r"UC[\w-]{22}", text):
        result["channel"] = text
        return result
    if text.startswith("PL") and len(text) > 10:
        result["playlist"] = text
        return result
    if len(text) == 11 and re.fullmatch(r"[\w-]{11}", text):
        result["video"] = text
        return result
    if text.startswith("@"):
        # bare handle like @Veritasium
        result["channel"] = text[1:].split("/")[0]
        return result

    if "youtu.be" in text or "youtube.com" in text:
        parsed = urlparse(text)
        host = (parsed.netloc or "").lower()
        if "youtu.be" in host:
            vid = parsed.path.strip("/")
            if vid:
                result["video"] = vid
            return result

        query = {}
        if parsed.query:
            for k, val in parse_qs(parsed.query).items():
                query[k] = val[0] if val else None

        path = parsed.path
        if "/channel/" in path:
            result["channel"] = path.rsplit("/channel/", 1)[-1].split("/")[0]
        elif "/playlist" in path:
            result["playlist"] = query.get("list")
        elif "/watch" in path:
            result["video"] = query.get("v")
            result["playlist"] = query.get("list")
        elif "/@" in path:
            result["channel"] = path.rsplit("/@", 1)[-1].split("/")[0]
        elif "/c/" in path or "/user/" in path:
            result["channel"] = path.rsplit("/", 1)[-1].split("/")[0]

    return result


class YouTubeClient:
    def __init__(self, api_key: str | None = None, session_factory=None) -> None:
        self.api_key = api_key or config.YOUTUBE_API_KEY
        if not self.api_key:
            raise YouTubeError(
                "YOUTUBE_API_KEY is not set. Add it to your `.env` file "
                "(see README for how to get a free key)."
            )
        self._sf = session_factory
        self.http = requests.Session()
        self.http.headers["User-Agent"] = "distract-yt/0.1"

    # ------------------------------------------------------------------ helpers
    def _call(self, endpoint: str, params: dict, ttl: int | None = None) -> dict:
        ttl = ttl if ttl is not None else config.CACHE_TTL_SECONDS
        cache_key = endpoint + "?" + "&".join(
            f"{k}={params[k]}" for k in sorted(params) if params[k] is not None
        )

        # 1) try cache
        if self._sf is not None:
            try:
                sess = self._sf()
                row = sess.get(ApiCache, cache_key)
                if row is not None and self._fresh(row.fetched_at, ttl):
                    return json.loads(row.payload)
            except Exception:
                pass  # cache is best-effort; fall through to the network

        # 2) network
        full = dict(params)
        full["key"] = self.api_key
        resp = self.http.get(f"{_BASE}/{endpoint}", params=full, timeout=20)
        if resp.status_code == 403:
            raise YouTubeError("YouTube API rejected the request (invalid key or quota exceeded).")
        if resp.status_code == 404:
            raise YouTubeError("That YouTube resource was not found.")
        if resp.status_code >= 400:
            raise YouTubeError(f"YouTube API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()

        # 3) store in cache
        if self._sf is not None:
            try:
                sess = self._sf()
                row = sess.get(ApiCache, cache_key)
                if row is None:
                    row = ApiCache(cache_key=cache_key, payload=json.dumps(data))
                    sess.add(row)
                else:
                    row.payload = json.dumps(data)
                    row.fetched_at = datetime.now(timezone.utc)
                sess.commit()
            except Exception:
                pass

        return data

    @staticmethod
    def _fresh(fetched_at, ttl: int) -> bool:
        if fetched_at is None or fetched_at.tzinfo is None:
            return False
        return (datetime.now(timezone.utc) - fetched_at).total_seconds() < ttl
# ------------------------------------------------------------------ channels
    def channel_by_id(self, channel_id: str) -> dict:
        data = self._call("channels", {"part": "snippet,statistics,contentDetails", "id": channel_id})
        items = data.get("items") or []
        if not items:
            raise YouTubeError(f"Channel '{channel_id}' was not found.")
        return self._to_channel(items[0])

    def resolve_channel_handle(self, handle: str) -> dict:
        """Resolve a @handle / custom name into a channel id via search."""
        q = handle.lstrip("@")
        data = self._call("search", {"part": "snippet", "q": q, "type": "channel", "maxResults": 1})
        items = data.get("items") or []
        if not items:
            raise YouTubeError(f"No channel found for '{handle}'.")
        return self.channel_by_id(items[0]["snippet"]["channelId"])

    @staticmethod
    def _to_channel(item: dict) -> dict:
        sn = item.get("snippet", {})
        return {
            "id": item["id"],
            "handle": (sn.get("customUrl") or "").lstrip("@") or None,
            "title": sn.get("title"),
            "description": sn.get("description"),
            "thumbnail_url": (sn.get("thumbnails", {}).get("high", {}) or {}).get("url"),
            "uploads_playlist": (
                (item.get("contentDetails", {}).get("relatedPlaylists", {}) or {}).get("uploads")
            ),
        }

    def channel_videos(self, channel_id: str, limit: int | None = None) -> list[dict]:
        """Return the most recent `limit` uploads for a channel (default from config)."""
        limit = limit or config.CHANNEL_IMPORT_LIMIT
        ch = self.channel_by_id(channel_id)
        uploads_id = ch.get("uploads_playlist")
        if not uploads_id:
            raise YouTubeError("Could not locate this channel's uploads playlist.")
        data = self._call("playlistItems", {
            "part": "snippet,contentDetails",
            "playlistId": uploads_id,
            "maxResults": min(limit, 50),
        })
        out = []
        for item in data.get("items") or []:
            vid = item.get("contentDetails", {}).get("videoId")
            if not vid:
                continue
            sn = item.get("snippet", {})
            out.append({
                "id": vid,
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "thumbnail_url": (sn.get("thumbnails", {}).get("high", {}) or {}).get("url"),
                "published_at": sn.get("publishedAt"),
            })
        return out

    # ------------------------------------------------------------------ videos
    def video_by_id(self, video_id: str) -> dict:
        data = self._call("videos", {"part": "snippet,contentDetails", "id": video_id})
        items = data.get("items") or []
        if not items:
            raise ValueError(f"Video '{video_id}' was not found.")
        return self._to_video(items[0])

    @staticmethod
    def _to_video(item: dict) -> dict:
        sn = item.get("snippet", {})
        cd = item.get("contentDetails", {})
        return {
            "id": item["id"],
            "channel_id": sn.get("channelId"),
            "channel_name": sn.get("channelTitle"),
            "title": sn.get("title", ""),
            "description": sn.get("description", ""),
            "thumbnail_url": (sn.get("thumbnails", {}).get("high", {}) or {}).get("url"),
            "published_at": sn.get("publishedAt"),
            "duration_sec": _parse_duration_to_seconds(cd.get("duration", "")),
        }
# ------------------------------------------------------------------ playlists
    def playlist_by_id(self, playlist_id: str) -> dict:
        data = self._call("playlists", {"part": "snippet,contentDetails", "id": playlist_id})
        items = data.get("items") or []
        if not items:
            raise ValueError(f"Playlist '{playlist_id}' was not found.")
        it = items[0]
        sn = it.get("snippet", {})
        return {
            "id": it["id"],
            "title": sn.get("title", ""),
            "description": sn.get("description", ""),
            "thumbnail_url": (sn.get("thumbnails", {}).get("high", {}) or {}).get("url"),
            "item_count": (it.get("contentDetails", {}) or {}).get("itemCount", 0),
        }

    def playlist_videos(self, playlist_id: str, limit: int = 200) -> list[dict]:
        out = []
        page = ""
        for _ in range(20):  # safety cap
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page:
                params["pageToken"] = page
            data = self._call("playlistItems", params)
            for item in data.get("items") or []:
                vid = item.get("contentDetails", {}).get("videoId")
                if not vid:
                    continue
                sn = item.get("snippet", {})
                out.append({
                    "id": vid,
                    "title": sn.get("title", ""),
                    "description": sn.get("description", ""),
                    "thumbnail_url": (sn.get("thumbnails", {}).get("high", {}) or {}).get("url"),
                    "published_at": sn.get("publishedAt"),
                    "channel_id": sn.get("channelId"),
                    "channel_name": sn.get("channelTitle"),
                })
            page = data.get("nextPageToken") or ""
            if not page or len(out) >= limit:
                break
        return out[:limit]

    # ------------------------------------------------------------------ search
    def search(self, query: str, kind: str = "video", max_results: int = 10) -> list[dict]:
        data = self._call("search", {
            "part": "snippet",
            "q": query,
            "type": kind,
            "maxResults": min(max_results, 50),
        })
        results = []
        for it in (data.get("items") or [])[:max_results]:
            r = it.get("id", {})
            kind_id = r.get("videoId") or r.get("channelId") or r.get("playlistId")
            sn = it.get("snippet", {})
            results.append({
                "kind": kind,
                "id": kind_id,
                "title": sn.get("title", ""),
                "channel_name": sn.get("channelTitle"),
                "channel_id": sn.get("channelId"),
                "thumbnail_url": (sn.get("thumbnails", {}).get("high", {}) or {}).get("url"),
                "description": sn.get("description", ""),
            })
        return results