"""REST API blueprint for the distraction-free YouTube library.
All routes are mounted under the `/api` prefix by the Flask app factory.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from .db import new_session, init_db
from .models import Channel, Playlist, Video
from .youtube import YouTubeClient, YouTubeError, extract_ids

bp = Blueprint("api", __name__, url_prefix="/api")


def _client() -> YouTubeClient:
    return YouTubeClient(session_factory=new_session)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


# --------------------------------------------------------------------- errors
@bp.errorhandler(YouTubeError)
def _yt_error(err):
    return jsonify({"error": str(err)}), 400


@bp.errorhandler(ValueError)
def _value_error(err):
    return jsonify({"error": str(err)}), 400


# --------------------------------------------------------------------- status
@bp.get("/status")
def status():
    try:
        from sqlalchemy import text

        init_db()  # create tables if missing; real connection happens here
        with new_session() as sess:
            sess.execute(text("SELECT 1"))
        return jsonify({"ok": True})
    except Exception as err:  # pragma: no cover - environment dependent
        return jsonify({"ok": False, "error": str(err)}), 500


# --------------------------------------------------------------------- channels
@bp.get("/channels")
def list_channels():
    with new_session() as sess:
        rows = sess.query(Channel).order_by(Channel.created_at.desc()).all()
        return jsonify([r.to_dict() for r in rows])


@bp.post("/channels")
def add_channel():
    body = request.get_json(silent=True) or {}
    raw = (body.get("url") or body.get("id") or "").strip()
    if not raw:
        return jsonify({"error": "Provide a channel URL or id."}), 400

    key = extract_ids(raw).get("channel")
    if not key:
        return jsonify({"error": "Could not parse that as a channel URL/id."}), 400

    client = _client()
    channel = client.channel_by_id(key) if key.startswith("UC") else client.resolve_channel_handle(key)

    with new_session() as sess:
        existing = sess.get(Channel, channel["id"])
        if existing:
            return jsonify(existing.to_dict()), 200
        row = Channel(
            id=channel["id"],
            handle=channel.get("handle"),
            title=channel.get("title"),
            description=channel.get("description") or "",
            thumbnail_url=channel.get("thumbnail_url"),
        )
        sess.add(row)
        sess.commit()
        return jsonify(row.to_dict()), 201


@bp.post("/channel")
def add_channel_singular():
    return add_channel()


@bp.delete("/channels/<channel_id>")
def delete_channel(channel_id: str):
    with new_session() as sess:
        row = sess.get(Channel, channel_id)
        if not row:
            return jsonify({"error": "Channel not found."}), 404
        sess.delete(row)
        sess.commit()
        return jsonify({"deleted": channel_id})
# --------------------------------------------------------------------- playlists
@bp.get("/playlists")
def list_playlists():
    with new_session() as sess:
        rows = sess.query(Playlist).order_by(Playlist.created_at.desc()).all()
        return jsonify([r.to_dict() for r in rows])


@bp.post("/playlists")
def add_playlist():
    body = request.get_json(silent=True) or {}
    raw = (body.get("url") or body.get("id") or "").strip()
    if not raw:
        return jsonify({"error": "Provide a playlist URL or id."}), 400
    pid = extract_ids(raw).get("playlist")
    if not pid:
        return jsonify({"error": "Could not parse a playlist id from that input."}), 400

    info = _client().playlist_by_id(pid)
    with new_session() as sess:
        existing = sess.get(Playlist, pid)
        if existing:
            return jsonify(existing.to_dict()), 200
        row = Playlist(
            id=pid,
            title=info.get("title"),
            description=info.get("description") or "",
            thumbnail_url=info.get("thumbnail_url"),
            item_count=info.get("item_count", 0),
        )
        sess.add(row)
        sess.commit()
        return jsonify(row.to_dict()), 201


@bp.post("/playlist")
def add_playlist_singular():
    return add_playlist()


@bp.delete("/playlists/<playlist_id>")
def delete_playlist(playlist_id: str):
    with new_session() as sess:
        row = sess.get(Playlist, playlist_id)
        if not row:
            return jsonify({"error": "Playlist not found."}), 404
        sess.delete(row)
        sess.commit()
        return jsonify({"deleted": playlist_id})


# --------------------------------------------------------------------- videos
@bp.get("/videos")
def list_videos():
    channel_id = request.args.get("channel_id") or None
    with new_session() as sess:
        q = sess.query(Video)
        if channel_id:
            q = q.filter(Video.channel_id == channel_id)
        rows = q.order_by(Video.created_at.desc()).all()
        return jsonify([r.to_dict() for r in rows])


@bp.get("/videos/<video_id>")
def get_video(video_id: str):
    with new_session() as sess:
        row = sess.get(Video, video_id)
        if not row:
            return jsonify({"error": "Video not found."}), 404
        return jsonify(row.to_dict())


@bp.delete("/videos")
def clear_videos():
    """Remove EVERY video from the library (channels/playlists are kept)."""
    from sqlalchemy import text

    with new_session() as sess:
        count = sess.query(Video).count()
        # clear join-table rows first so FKs stay happy on every dialect
        sess.execute(text("DELETE FROM playlist_videos"))
        sess.query(Video).delete()
        sess.commit()
    return jsonify({"deleted": count})


@bp.post("/videos")
def add_video():
    body = request.get_json(silent=True) or {}
    raw = (body.get("url") or body.get("id") or "").strip()
    if not raw:
        return jsonify({"error": "Provide a video URL or id."}), 400
    vid = extract_ids(raw).get("video")
    if not vid:
        return jsonify({"error": "Could not parse a video id from that input."}), 400

    info = _client().video_by_id(vid)
    with new_session() as sess:
        existing = sess.get(Video, vid)
        if existing:
            return jsonify(existing.to_dict()), 200
        channel = sess.get(Channel, info.get("channel_id")) if info.get("channel_id") else None
        row = Video(
            id=vid,
            channel_id=info.get("channel_id") if channel else None,
            title=info.get("title"),
            description=info.get("description") or "",
            thumbnail_url=info.get("thumbnail_url"),
            duration_sec=info.get("duration_sec"),
            published_at=_parse_date(info.get("published_at")),
            source="direct",
        )
        sess.add(row)
        sess.commit()
        return jsonify(row.to_dict()), 201


@bp.post("/video")
def add_video_singular():
    return add_video()


@bp.delete("/videos/<video_id>")
def delete_video(video_id: str):
    with new_session() as sess:
        row = sess.get(Video, video_id)
        if not row:
            return jsonify({"error": "Video not found."}), 404
        sess.delete(row)
        sess.commit()
        return jsonify({"deleted": video_id})
# --------------------------------------------------------------------- discovery
@bp.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    kind = (request.args.get("type") or "video").strip().lower()
    if not q:
        return jsonify({"error": "Missing 'q' parameter."}), 400
    if kind not in ("video", "channel", "playlist"):
        kind = "video"
    return jsonify(_client().search(q, kind=kind))


@bp.post("/import/channel/<channel_id>")
def import_channel(channel_id: str):
    """Pull recent uploads of an allowed channel into the library."""
    videos = _client().channel_videos(channel_id)
    added = 0
    with new_session() as sess:
        ch = sess.get(Channel, channel_id)
        if not ch:
            return jsonify({"error": "Add the channel to your library first."}), 404
        for v in videos:
            if sess.get(Video, v["id"]) is None:
                sess.add(Video(
                    id=v["id"],
                    channel_id=channel_id,
                    title=v["title"],
                    description=v.get("description") or "",
                    thumbnail_url=v.get("thumbnail_url"),
                    published_at=_parse_date(v.get("published_at")),
                    source="channel",
                ))
                added += 1
        sess.commit()
    return jsonify({"added": added, "total_known": len(videos)})


@bp.post("/import/playlist/<playlist_id>")
def import_playlist(playlist_id: str):
    """Pull all videos of an allowed playlist into the library."""
    videos = _client().playlist_videos(playlist_id)
    added = 0
    with new_session() as sess:
        pl = sess.get(Playlist, playlist_id)
        if not pl:
            return jsonify({"error": "Add the playlist to your library first."}), 404
        for v in videos:
            vid = sess.get(Video, v["id"])
            if vid is None:
                channel = sess.get(Channel, v.get("channel_id")) if v.get("channel_id") else None
                vid = Video(
                    id=v["id"],
                    channel_id=v.get("channel_id") if channel else None,
                    title=v["title"],
                    description=v.get("description") or "",
                    thumbnail_url=v.get("thumbnail_url"),
                    published_at=_parse_date(v.get("published_at")),
                    source="playlist",
                )
                sess.add(vid)
            if vid not in pl.videos:
                pl.videos.append(vid)
            added += 1
        sess.commit()
    return jsonify({"added": added, "total_known": len(videos)})