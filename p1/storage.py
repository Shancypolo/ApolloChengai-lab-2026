"""Small, safe JSON storage for PageOne's local archive."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable


DEFAULT_PREFERENCES = (
    "Write a concise academic summary in coherent paragraphs. Explain the central "
    "thesis, key arguments, evidence, and limitations."
)
DEFAULT_SETTINGS = {
    "default_playlist_sort": "original",
    "archive_sort": "recent",
    "auto_summarize_new": True,
}
PLAYLIST_SORT_OPTIONS = {"original", "published_at", "author", "topic", "title"}
ARCHIVE_SORT_OPTIONS = {"recent", "title"}


def empty_archive() -> dict[str, Any]:
    """Return a fresh archive with the current settings defaults."""
    return {
        "schema_version": 2,
        "summary_preferences": DEFAULT_PREFERENCES,
        "settings": dict(DEFAULT_SETTINGS),
        "sources": {},
        "summaries": {},
        "summary_lists": {},
    }


def upgrade_archive(value: Any) -> Any:
    """Read old archive files as version 2 without changing their disk bytes."""
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        return value
    upgraded = {**value, "schema_version": 2, "settings": dict(DEFAULT_SETTINGS), "summary_lists": {}}
    for source_key, source in value.get("sources", {}).items():
        if not isinstance(source, dict) or source.get("kind") != "playlist":
            continue
        videos = source.get("videos", [])
        if not isinstance(videos, list):
            continue
        upgraded["summary_lists"][source_key] = {
            "id": source_key,
            "title": str(source.get("title") or "Untitled playlist"),
            "kind": "playlist",
            "source_key": source_key,
            "video_ids": list(dict.fromkeys(
                video["id"] for video in videos if isinstance(video, dict) and isinstance(video.get("id"), str)
            )),
            "created_at": str(source.get("created_at") or ""),
            "updated_at": str(source.get("updated_at") or ""),
        }
    return upgraded


def validate_archive(value: Any) -> dict[str, Any]:
    """Reject malformed files before they can replace saved user data."""
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ValueError("The archive file has an unsupported format.")
    if not isinstance(value.get("sources"), dict):
        raise ValueError("The archive source list is malformed.")
    if not isinstance(value.get("summaries"), dict):
        raise ValueError("The archive summary list is malformed.")
    if not isinstance(value.get("summary_preferences"), str):
        raise ValueError("The saved summary preference is malformed.")
    settings = value.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("The saved settings are malformed.")
    if settings.get("default_playlist_sort") not in PLAYLIST_SORT_OPTIONS:
        raise ValueError("The saved playlist sort is malformed.")
    if settings.get("archive_sort") not in ARCHIVE_SORT_OPTIONS:
        raise ValueError("The saved archive sort is malformed.")
    if type(settings.get("auto_summarize_new")) is not bool:
        raise ValueError("The saved automatic summary setting is malformed.")
    lists = value.get("summary_lists")
    if not isinstance(lists, dict):
        raise ValueError("The saved summary lists are malformed.")
    for list_id, summary_list in lists.items():
        if not isinstance(list_id, str) or not isinstance(summary_list, dict):
            raise ValueError("A saved summary list is malformed.")
        if summary_list.get("id") != list_id or summary_list.get("kind") not in {"playlist", "custom"}:
            raise ValueError("A saved summary list is malformed.")
        if not isinstance(summary_list.get("title"), str) or not summary_list["title"].strip():
            raise ValueError("A saved summary list title is malformed.")
        video_ids = summary_list.get("video_ids")
        if not isinstance(video_ids, list) or not all(isinstance(item, str) for item in video_ids):
            raise ValueError("A saved summary list membership is malformed.")
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("A saved summary list has duplicate videos.")
    for source_key, source in value["sources"].items():
        if not isinstance(source_key, str) or not isinstance(source, dict):
            raise ValueError("A saved source is malformed.")
        if not isinstance(source.get("videos"), list):
            raise ValueError("A saved video list is malformed.")
        if not all(isinstance(video, dict) and isinstance(video.get("id"), str) for video in source["videos"]):
            raise ValueError("A saved video entry is malformed.")
    for video_id, summary in value["summaries"].items():
        if not isinstance(video_id, str) or not isinstance(summary, dict):
            raise ValueError("A saved summary is malformed.")
        if not isinstance(summary.get("summary"), str) or not isinstance(summary.get("topics"), list):
            raise ValueError("A saved summary is malformed.")
        if not all(isinstance(topic, str) for topic in summary["topics"]):
            raise ValueError("A saved topic list is malformed.")
        if not isinstance(summary.get("chat", []), list):
            raise ValueError("A saved chat history is malformed.")
    return value


class JsonStore:
    """Own one JSON file and serialize local reads and atomic updates."""

    def __init__(self, file_path: str | Path):
        """Remember the data path and create a lock for local updates."""
        self.file_path = Path(file_path)
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        """Read validated data or return defaults when no file exists."""
        with self._lock:
            if not self.file_path.exists():
                return empty_archive()
            try:
                value = json.loads(self.file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError("The archive could not be read; the original was kept.") from error
            return validate_archive(upgrade_archive(value))

    def update(self, change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        """Apply one change and replace the JSON file atomically."""
        with self._lock:
            archive = self.read()
            change(archive)
            validate_archive(archive)
            self._write_atomically(archive)
            return archive

    def _write_atomically(self, archive: dict[str, Any]) -> None:
        """Write beside the destination, then replace it safely."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.file_path.parent,
                prefix="pageone-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(archive, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.file_path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
