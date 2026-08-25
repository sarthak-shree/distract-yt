"""SQLAlchemy ORM models describing the distraction-free library.

Tables
------
channels        - channels you have explicitly allowed
videos          - individual videos (curated, or imported via a channel/playlist)
playlists       - playlists you have explicitly allowed
playlist_videos - join table linking a # playlist to its videos
api_cache       - stores YouTube Data API responses so we stay inside the free
                  tier (cached JSON keyed by endpoint + params)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Table,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


playlist_videos = Table(
    "playlist_videos",
    Base.metadata,
    Column("playlist_id", String, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("video_id", String, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, default=0),
)


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True)  # YouTube channel id (UC...)
    handle = Column(String, nullable=True)  # @handle if available
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "handle": self.handle,
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "video_count": len(self.videos),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True)  # YouTube video id (11 chars)
    channel_id = Column(String, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    duration_sec = Column(Integer, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String, nullable=True)  # "direct" | "channel" | "playlist"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("Channel", back_populates="videos")
    playlists = relationship("Playlist", secondary=playlist_videos, back_populates="videos")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "channel_name": self.channel.title if self.channel else None,
            "title": self.title,
            "thumbnail_url": self.thumbnail_url,
            "duration_sec": self.duration_sec,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(String, primary_key=True)  # YouTube playlist id
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    item_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    videos = relationship("Video", secondary=playlist_videos, back_populates="playlists")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "item_count": len(self.videos),
            "video_ids": [v.id for v in self.videos],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ApiCache(Base):
    __tablename__ = "api_cache"

    cache_key = Column(String, primary_key=True)
    payload = Column(Text, nullable=False)  # JSON-encoded response
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())