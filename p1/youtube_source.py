"""Public YouTube URL validation, listing, and English caption extraction."""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from typing import Any


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYLIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
UNKNOWN_VALUE = "Unknown"
YOUTUBE_LOGGER = logging.getLogger("pageone.yt_dlp")
YOUTUBE_LOGGER.addHandler(logging.NullHandler())
YOUTUBE_LOGGER.propagate = False


class SourceError(ValueError):
    """Describe a safe, user-facing problem with a public YouTube source."""


def parse_youtube_url(raw_url: str) -> dict[str, str | None]:
    """Validate HTTPS and return recognized video and playlist IDs."""
    if not raw_url or not raw_url.strip():
        raise SourceError("Enter a YouTube video or playlist link.")
    parts = urlsplit(raw_url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in YOUTUBE_HOSTS:
        raise SourceError("Use an HTTPS link from youtube.com or youtu.be.")
    query = parse_qs(parts.query)
    video_id = query.get("v", [None])[0]
    playlist_id = query.get("list", [None])[0]
    if host == "youtu.be":
        video_id = parts.path.strip("/").split("/")[0] or None
    if not video_id and parts.path.startswith("/shorts/"):
        video_id = parts.path.split("/")[2] if len(parts.path.split("/")) > 2 else None
    if video_id and not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise SourceError("That video link does not contain a valid video ID.")
    if playlist_id and not PLAYLIST_ID_PATTERN.fullmatch(playlist_id):
        raise SourceError("That playlist link does not contain a valid playlist ID.")
    if not video_id and not playlist_id:
        raise SourceError("That link does not contain a video or playlist ID.")
    return {"video_id": video_id, "playlist_id": playlist_id}


def canonical_video_url(video_id: str) -> str:
    """Build a canonical HTTPS watch link from a validated video ID."""
    return f"https://www.youtube.com/watch?{urlencode({'v': video_id})}"


def canonical_playlist_url(playlist_id: str) -> str:
    """Build a canonical HTTPS playlist link from a validated playlist ID."""
    return f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}"


def parse_caption_json(caption_data: dict[str, Any]) -> str:
    """Join non-empty JSON3 caption segments into plain transcript text."""
    events = caption_data.get("events", [])
    if not isinstance(events, list):
        raise SourceError("The English captions were not in a readable format.")
    segments = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_segments = event.get("segs", [])
        if not isinstance(event_segments, list):
            continue
        for segment in event_segments:
            text = segment.get("utf8", "") if isinstance(segment, dict) else ""
            if isinstance(text, str) and text.strip():
                segments.append(text.strip())
    transcript = " ".join(segments).strip()
    if not transcript:
        raise SourceError("No English captions were found for this video.")
    return transcript[:100_000]


def _youtube_dl(options: dict[str, Any]):
    """Create a quiet yt-dlp client for public metadata or subtitle access."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError as error:
        raise SourceError("Install the app dependencies to access YouTube.") from error
    safe_options = {**options, "logger": YOUTUBE_LOGGER}
    return YoutubeDL(safe_options)


def fetch_source(source_kind: str, source_id: str) -> dict[str, Any]:
    """List a public playlist's videos or build a one-video source record."""
    if source_kind == "video":
        if not VIDEO_ID_PATTERN.fullmatch(source_id):
            raise SourceError("That video ID is invalid.")
        options = {"quiet": True, "no_warnings": True, "skip_download": True}
        try:
            with _youtube_dl(options) as downloader:
                info = downloader.extract_info(canonical_video_url(source_id), download=False)
        except SourceError:
            raise
        except Exception as error:
            raise SourceError("YouTube could not return that public video.") from error
        if not isinstance(info, dict):
            raise SourceError("YouTube returned no video information.")
        video = make_video_entry({**info, "id": source_id})
        return {
            "source_key": f"video:{source_id}",
            "kind": "video",
            "id": source_id,
            "title": video["title"],
            "url": canonical_video_url(source_id),
            "videos": [video],
            "omitted_video_entries": 0,
        }
    if source_kind != "playlist" or not PLAYLIST_ID_PATTERN.fullmatch(source_id):
        raise SourceError("That playlist ID is invalid.")
    options = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    try:
        with _youtube_dl(options) as downloader:
            info = downloader.extract_info(canonical_playlist_url(source_id), download=False)
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("YouTube could not return that public playlist.") from error
    if not isinstance(info, dict):
        raise SourceError("YouTube returned no playlist information.")
    entries = info.get("entries") or []
    videos = []
    for entry in entries:
        if not isinstance(entry, dict) or not VIDEO_ID_PATTERN.fullmatch(str(entry.get("id", ""))):
            continue
        videos.append(make_video_entry(entry))
    return {
        "source_key": f"playlist:{source_id}",
        "kind": "playlist",
        "id": source_id,
        "title": normalize_text(info.get("title")) or "Untitled playlist",
        "url": canonical_playlist_url(source_id),
        "videos": videos,
        "omitted_video_entries": len(entries) - len(videos),
    }


def make_video_entry(entry: dict[str, Any]) -> dict[str, str]:
    """Normalize yt-dlp video metadata for display and local storage."""
    video_id = str(entry.get("id", ""))
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise SourceError("The playlist contained an invalid video ID.")
    upload_date = entry.get("upload_date") or entry.get("release_date")
    published_at = normalize_date(upload_date)
    author = normalize_text(entry.get("uploader") or entry.get("channel")) or UNKNOWN_VALUE
    title = normalize_text(entry.get("title")) or "Untitled video"
    return {
        "id": video_id,
        "title": title,
        "url": canonical_video_url(video_id),
        "published_at": published_at,
        "author": author,
        "topic": "Topic pending",
    }


def normalize_date(value: Any) -> str:
    """Convert YYYYMMDD metadata to YYYY-MM-DD or return Unknown."""
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4:5] == "-":
        return text[:10]
    return UNKNOWN_VALUE


def normalize_text(value: Any) -> str:
    """Collapse metadata whitespace and remove empty values."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def fetch_english_transcript(video_id: str) -> str:
    """Fetch English subtitle JSON3 only; never download video or audio."""
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise SourceError("That video ID is invalid.")
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "json3",
        "outtmpl": "%(id)s.%(ext)s",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="pageone-captions-") as folder:
            options["paths"] = {"home": folder}
            with _youtube_dl(options) as downloader:
                downloader.download([canonical_video_url(video_id)])
            caption_files = list(Path(folder).glob("*.json3"))
            if not caption_files:
                raise SourceError("No English captions were found for this video.")
            caption_data = json.loads(caption_files[0].read_text(encoding="utf-8"))
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("YouTube could not return English captions for this video.") from error
    if not isinstance(caption_data, dict):
        raise SourceError("The English captions were not in a readable format.")
    return parse_caption_json(caption_data)
