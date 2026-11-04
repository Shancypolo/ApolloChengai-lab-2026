"""Run PageOne, a loopback-only Flask app for YouTube video summaries."""

from __future__ import annotations

import ipaddress
import logging
import os
import secrets
import sys
import threading
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from archive_storage import (
    ArchiveStore, DEFAULT_PREFERENCES, DEFAULT_SETTINGS,
    INTERFACE_SCALE_OPTIONS, READING_WIDTH_OPTIONS,
)
from archive_actions import (
    delete_selected_summaries, list_source, selected_detail_source,
    selected_sources, selected_video_sources, transfer_memberships, video_row_for_id,
)
from data_paths import (
    ARCHIVE_FILE_NAME, LOG_FILE_NAME, default_data_directory, migrate_data_files,
)
from ai_summaries import (
    SummaryError, answer_video_question, label_video_titles,
    split_summary_batches, summarize_video_batch,
)
from usage_accounting import SessionUsageLedger
from youtube_source import (
    SourceError,
    fetch_english_transcript,
    fetch_source,
    parse_youtube_url,
)


APP_NAME = "PageOne"
DEFAULT_DATA_DIRECTORY = default_data_directory(Path(__file__).resolve().parent)
MAX_PREFERENCE_LENGTH = 2_000
MAX_QUESTION_LENGTH = 1_000
MAX_FILTER_LENGTH = 200
MAX_LIST_TITLE_LENGTH = 120
VIDEOS_PER_PAGE = 48
VIDEO_SORT_OPTIONS = {"original", "published_at", "author", "topic", "title"}
ARCHIVE_ACTIONS = {
    "select_all", "select_none", "reopen", "summarize", "retry",
    "copy", "move", "delete_summaries",
}
VIDEO_SORT_LABELS = (
    ("original", "Playlist order"),
    ("published_at", "Publish date"),
    ("author", "Author"),
    ("topic", "Topic"),
    ("title", "Title"),
)


class JobRegistry:
    """Own in-memory progress for summary batches until this app stops."""

    def __init__(self):
        """Start with no jobs and protect updates from worker threads."""
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, job_type: str, session_id: str, source_key: str = "", total: int = 0) -> str:
        """Create a queued inspection, summary, or chat job and return its ID."""
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "type": job_type,
                "session_id": session_id,
                "source_key": source_key,
                "status": "queued",
                "total": total,
                "finished": 0,
                "succeeded": 0,
                "failed": [],
                "message": "Waiting to start.",
            }
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a copy of progress so templates cannot mutate it."""
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def update(self, job_id: str, **changes: Any) -> None:
        """Change progress fields while holding the registry lock."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(changes)


def now_utc() -> str:
    """Return an ISO timestamp for locally saved archive entries."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def configure_safe_logging(app: Flask) -> None:
    """Write privacy-safe failures to the rotating log and launch terminal."""
    log_path = Path(app.config["DATA_DIRECTORY"]) / LOG_FILE_NAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("pageone")
    logger.setLevel(logging.INFO)
    for existing in list(logger.handlers):
        if isinstance(existing, RotatingFileHandler) and existing.baseFilename != str(log_path):
            logger.removeHandler(existing)
            existing.close()
    if not any(isinstance(item, RotatingFileHandler) and item.baseFilename == str(log_path) for item in logger.handlers):
        logger.addHandler(handler)
    else:
        handler.close()
    if not any(type(item) is logging.StreamHandler for item in logger.handlers):
        terminal_handler = logging.StreamHandler(sys.stderr)
        terminal_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(terminal_handler)
    logger.propagate = False
    app.config["PAGEONE_LOGGER"] = logger


def safe_log(app: Flask, message: str, error: Exception | None = None) -> None:
    """Record a short event and exception type without sensitive text."""
    logger: logging.Logger = app.config["PAGEONE_LOGGER"]
    if error is None:
        logger.warning(message)
        return
    safe_error_type = type(error.__cause__ or error).__name__
    logger.error("%s (%s)", message, safe_error_type)


def failure_notice(error: Exception) -> str:
    """Turn provider and setup failures into safe, short product messages."""
    cause = error.__cause__ or error
    error_type = type(cause).__name__.casefold()
    if any(word in error_type for word in ("connection", "connect", "timeout", "network")):
        return "Connection unavailable. Check your connection and try again."
    if isinstance(error, (SourceError, SummaryError)) and "install" in str(error).casefold():
        return "PageOne needs an update. Reinstall it and try again."
    if isinstance(error, SummaryError) and "OPENAI_API_KEY" in str(error):
        return "AI is unavailable. Add your API key and try again."
    if isinstance(error, SummaryError):
        return "AI could not finish. Please try again."
    if isinstance(error, SourceError):
        return str(error)
    return "Something went wrong. Please try again."


def clean_video_title(source: dict[str, Any], video_id: str) -> str:
    """Find a display title in a listed source or use a safe fallback."""
    for video in source.get("videos", []):
        if video.get("id") == video_id:
            return str(video.get("title") or "Untitled video")
    return "Untitled video"


def source_record(source: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prepare a saved source while retaining its original archive date."""
    return {
        **source,
        "created_at": (previous or {}).get("created_at", now_utc()),
        "updated_at": now_utc(),
    }


def attach_summary_to_source(source: dict[str, Any], video_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Keep a title-derived topic on the source's matching video row."""
    copied = dict(source)
    copied["videos"] = [dict(video) for video in source.get("videos", [])]
    topic_text = ", ".join(summary.get("topics", [])) or "Other"
    for video in copied["videos"]:
        if video.get("id") == video_id:
            video["topic"] = topic_text
    return copied


def update_saved_summary(
    store: ArchiveStore,
    source_key: str,
    video_id: str,
    title: str,
    result: dict[str, Any],
) -> None:
    """Save a summary and its topic labels, never the transcript."""
    def change(archive: dict[str, Any]) -> None:
        """Merge the new summary into saved data without losing chats."""
        old_summary = archive["summaries"].get(video_id, {})
        old_source_keys = list(old_summary.get("source_keys", []))
        if source_key not in old_source_keys:
            old_source_keys.append(source_key)
        chat_history = old_summary.get("chat", [])
        topic = clean_video_topic(archive["sources"].get(source_key, {}), video_id)
        if topic == "Other":
            topic = str(video_row_for_id(archive, video_id).get("topic") or "Other")
        archive["summaries"][video_id] = {
            "video_id": video_id,
            "title": title,
            "source_keys": old_source_keys,
            "summary": result["summary"],
            "topics": [topic],
            "created_at": old_summary.get("created_at", now_utc()),
            "updated_at": now_utc(),
            "chat": chat_history,
        }
        saved_source = archive["sources"].get(source_key)
        if saved_source:
            archive["sources"][source_key] = attach_summary_to_source(
                saved_source, video_id, archive["summaries"][video_id]
            )
        summary_list = archive["summary_lists"].get(source_key)
        if summary_list and video_id not in summary_list["video_ids"]:
            summary_list["video_ids"].append(video_id)
            summary_list["updated_at"] = now_utc()
    store.update(change)


def clean_video_topic(source: dict[str, Any], video_id: str) -> str:
    """Return the already-classified title topic or the Other fallback."""
    for video in source.get("videos", []):
        if video.get("id") == video_id:
            return str(video.get("topic") or "Other")
    return "Other"


def ordered_source_videos(source: dict[str, Any], sort_by: str, filter_text: str) -> list[dict[str, Any]]:
    """Sort and filter listed videos using only their saved metadata."""
    videos = list(source.get("videos", []))
    if sort_by not in VIDEO_SORT_OPTIONS:
        sort_by = "original"
    if sort_by != "original":
        videos.sort(
            key=lambda video: (
                str(video.get(sort_by) or "Unknown").casefold() == "unknown",
                str(video.get(sort_by) or "Unknown").casefold(),
            )
        )
    query = filter_text.strip().casefold()
    if query:
        videos = [video for video in videos if query in str(video.get("title", "")).casefold()]
    return videos


def filter_summary_videos(
    videos: list[dict[str, Any]], summaries: dict[str, Any], filter_text: str
) -> list[dict[str, Any]]:
    """Find saved video rows by title, topic, or summary text."""
    query = filter_text.strip().casefold()[:MAX_FILTER_LENGTH]
    if not query:
        return list(videos)
    matches = []
    for video in videos:
        saved = summaries.get(video.get("id", ""), {})
        searchable_text = " ".join((
            str(video.get("title", "")),
            str(video.get("topic", "")),
            str(saved.get("summary", "")),
        )).casefold()
        if query in searchable_text:
            matches.append(video)
    return matches


def archive_rows(sources: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Find saved sources by source or video title before rendering HTML."""
    search_text = query.strip().casefold()[:MAX_FILTER_LENGTH]
    rows = []
    for source in sources:
        videos = source.get("videos", [])
        searchable = " ".join([str(source.get("title", "")), *[str(video.get("title", "")) for video in videos]])
        if search_text and search_text not in searchable.casefold():
            continue
        rows.append(source)
    return rows


def render_source_results(
    source: dict[str, Any],
    summaries: dict[str, Any],
    sort_by: str = "original",
    filter_text: str = "",
    selected_ids: set[str] | None = None,
    warning: str = "",
    page: str = "1",
):
    """Render a complete source page with server-sorted selection state."""
    all_ids = [video["id"] for video in source.get("videos", [])]
    selected = set(all_ids) if selected_ids is None else selected_ids
    visible_videos = ordered_source_videos(source, sort_by, filter_text)
    matching_count = len(visible_videos)
    page_count = max(1, (matching_count + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE)
    page_text = str(page)
    valid_page = page_text.isascii() and page_text.isdigit() and len(page_text) < 8
    page_number = min(max(1, int(page_text)), page_count) if valid_page else 1
    start = (page_number - 1) * VIDEOS_PER_PAGE
    visible_videos = visible_videos[start:start + VIDEOS_PER_PAGE]
    visible_videos = [
        {**video, "display_index": f"{start + index:02d}"}
        for index, video in enumerate(visible_videos, start=1)
    ]
    visible_ids = {video["id"] for video in visible_videos}
    return render_template(
        "source_results.html",
        source=source,
        summaries=summaries,
        videos=visible_videos,
        page_number=page_number, page_count=page_count,
        matching_count=matching_count, selected_count=len(selected),
        selected_ids=selected,
        hidden_selected_ids=selected - visible_ids,
        sort_by=sort_by if sort_by in VIDEO_SORT_OPTIONS else "original",
        sort_options=VIDEO_SORT_LABELS,
        filter_text=filter_text,
        warning=warning,
        error_notice_message=warning,
        dismiss_url=url_for("source_results", source_key=source["source_key"]),
    )


def apply_title_topics(source: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """Copy title-only topic labels onto videos in their original order."""
    copied = {**source, "videos": [dict(video) for video in source.get("videos", [])]}
    for index, video in enumerate(copied["videos"]):
        video["topic"] = labels[index] if index < len(labels) and labels[index] else "Other"
    return copied


def save_inspected_source(store: ArchiveStore, source: dict[str, Any], create_playlist_list: bool = True) -> None:
    """Save metadata and reconcile a playlist's editable list membership."""
    def change(archive: dict[str, Any]) -> None:
        """Keep deliberate list moves while adding newly found playlist videos."""
        previous = archive["sources"].get(source["source_key"], {})
        source_key = source["source_key"]
        if source.get("kind") == "playlist" and create_playlist_list:
            existing = archive["summary_lists"].get(source_key, {})
            old_remote = {video["id"] for video in previous.get("videos", [])} if existing else set()
            members = existing.get("video_ids", [])
            manual_ids = [video_id for video_id in members if video_id not in old_remote]
            excluded_ids = old_remote - set(members)
            remote_ids = [video["id"] for video in source.get("videos", []) if video["id"] not in excluded_ids]
            archive["summary_lists"][source_key] = {
                "id": source_key, "title": source["title"], "kind": "playlist",
                "source_key": source_key,
                "video_ids": list(dict.fromkeys([*remote_ids, *manual_ids])),
                "created_at": existing.get("created_at", now_utc()),
                "updated_at": now_utc(),
            }
        archive["sources"][source["source_key"]] = source
        for video in source.get("videos", []):
            saved = archive["summaries"].get(video["id"])
            if saved:
                saved["topics"] = [video.get("topic") or "Other"]
    store.update(change)


def add_video_to_list(store: ArchiveStore, list_id: str, video_id: str) -> None:
    """Add one video to an existing summary list exactly once."""
    def change(archive: dict[str, Any]) -> None:
        """Append a membership and update its displayed date."""
        summary_list = archive["summary_lists"].get(list_id)
        if not summary_list:
            raise ValueError("The selected summary list no longer exists.")
        if video_id not in summary_list["video_ids"]:
            summary_list["video_ids"].append(video_id)
            summary_list["updated_at"] = now_utc()
    store.update(change)


def archive_groups(archive: dict[str, Any], query: str) -> dict[str, list[dict[str, Any]]]:
    """Group matching playlist lists, custom lists, and single videos."""
    search_text = query.strip().casefold()[:MAX_FILTER_LENGTH]
    groups: dict[str, list[dict[str, Any]]] = {"playlists": [], "custom": [], "single": []}
    for summary_list in archive["summary_lists"].values():
        source = list_source(archive, summary_list)
        titles = " ".join(video["title"] for video in source["videos"])
        if search_text and search_text not in f"{source['title']} {titles}".casefold():
            continue
        group = "playlists" if summary_list["kind"] == "playlist" else "custom"
        groups[group].append(source)
    listed_ids = {video_id for item in archive["summary_lists"].values() for video_id in item["video_ids"]}
    single_ids: set[str] = set()
    for source in archive["sources"].values():
        if source.get("kind") != "video":
            continue
        video_id = source.get("id")
        if video_id not in archive["summaries"]:
            continue
        if source.get("archive_as_single") is False and video_id in listed_ids:
            continue
        single_ids.add(video_id)
        if search_text and search_text not in source.get("title", "").casefold():
            continue
        groups["single"].append(source)
    for video_id, saved in archive["summaries"].items():
        if video_id in listed_ids or video_id in single_ids:
            continue
        if search_text and search_text not in saved.get("title", "").casefold():
            continue
        groups["single"].append({
            "source_key": f"video:{video_id}", "kind": "video", "id": video_id,
            "title": saved["title"], "url": f"https://www.youtube.com/watch?v={video_id}",
            "videos": [video_row_for_id(archive, video_id)],
            "updated_at": saved.get("updated_at", ""),
        })
    sort_name = archive["settings"]["archive_sort"]
    for rows in groups.values():
        rows.sort(key=lambda item: item.get("title", "").casefold() if sort_name == "title" else archive["summary_lists"].get(item["source_key"], item).get("updated_at", ""), reverse=sort_name == "recent")
    return groups


def settings_error_message(
    preferences: str, playlist_sort: str, archive_sort: str,
    interface_scale: str, reading_width: str,
) -> str:
    """Return a short notice for invalid preference and display choices."""
    if not preferences:
        return "Preferences cannot be blank."
    if len(preferences) > MAX_PREFERENCE_LENGTH:
        return f"Keep preferences under {MAX_PREFERENCE_LENGTH} characters."
    if playlist_sort not in VIDEO_SORT_OPTIONS or archive_sort not in {"recent", "title"}:
        return "Choose a valid sort option."
    if interface_scale not in INTERFACE_SCALE_OPTIONS or reading_width not in READING_WIDTH_OPTIONS:
        return "Choose a valid display size."
    return ""


def save_general_settings(
    store: ArchiveStore, preferences: str, playlist_sort: str, archive_sort: str,
    auto_summarize_new: bool | None, interface_scale: str, reading_width: str,
) -> None:
    """Persist validated summary and general preferences together."""
    def change(archive: dict[str, Any]) -> None:
        """Change saved settings in one atomic archive write."""
        archive["summary_preferences"] = preferences
        archive["settings"]["default_playlist_sort"] = playlist_sort
        archive["settings"]["archive_sort"] = archive_sort
        archive["settings"]["interface_scale"] = interface_scale
        archive["settings"]["reading_width"] = reading_width
        if auto_summarize_new is not None:
            archive["settings"]["auto_summarize_new"] = auto_summarize_new
    store.update(change)


def link_existing_summary(store: ArchiveStore, source_key: str, video_id: str) -> None:
    """Attach an existing video summary to another archived playlist."""
    def change(archive: dict[str, Any]) -> None:
        """Add the source reference and restore the topic label."""
        summary = archive["summaries"].get(video_id)
        source = archive["sources"].get(source_key)
        if not summary or not source:
            return
        source_keys = summary.setdefault("source_keys", [])
        if source_key not in source_keys:
            source_keys.append(source_key)
        archive["sources"][source_key] = attach_summary_to_source(source, video_id, summary)
        summary_list = archive["summary_lists"].get(source_key)
        if summary_list and video_id not in summary_list["video_ids"]:
            summary_list["video_ids"].append(video_id)
            summary_list["updated_at"] = now_utc()
    store.update(change)


def save_batch_results(
    app: Flask,
    job_id: str,
    source_key: str,
    batch: list[dict[str, str]],
    results: dict[str, dict[str, str]],
    succeeded: int,
    failed: list[dict[str, str]],
    source_keys: dict[str, str] | None = None,
) -> int:
    """Save each returned summary and report individual storage failures."""
    registry: JobRegistry = app.config["JOBS"]
    store: ArchiveStore = app.config["STORE"]
    for video in batch:
        try:
            update_saved_summary(
                store, (source_keys or {}).get(video["video_id"], source_key), video["video_id"],
                video["video_title"], results[video["video_id"]],
            )
            succeeded += 1
        except Exception as error:
            failed.append({
                "video_id": video["video_id"], "title": video["video_title"],
                "message": failure_notice(error),
            })
            safe_log(app, f"Video {video['video_id']} save failed", error)
        registry.update(job_id, finished=succeeded + len(failed), succeeded=succeeded, failed=list(failed))
    return succeeded


def run_summary_job(
    app: Flask,
    job_id: str,
    source: dict[str, Any],
    video_ids: list[str],
    refresh: bool,
    session_id: str,
    source_keys: dict[str, str] | None = None,
) -> None:
    """Fetch captions, then summarize bounded groups without parallel calls."""
    registry: JobRegistry = app.config["JOBS"]
    store: ArchiveStore = app.config["STORE"]
    registry.update(job_id, status="running", message="Fetching captions and writing summaries.")
    try:
        archive = store.read()
        preferences = archive["summary_preferences"]
        failed: list[dict[str, str]] = []
        succeeded = 0
        pending: list[dict[str, str]] = []
        for index, video_id in enumerate(video_ids, start=1):
            video_source_key = (source_keys or {}).get(video_id, source["source_key"])
            registry.update(job_id, message=f"Reading captions {index} of {len(video_ids)}.")
            existing = store.read()["summaries"].get(video_id)
            if existing and not refresh:
                link_existing_summary(store, video_source_key, video_id)
                succeeded += 1
                registry.update(job_id, finished=succeeded + len(failed), succeeded=succeeded)
                continue
            try:
                transcript = app.config["TRANSCRIPT_FETCHER"](video_id)
                pending.append({
                    "video_id": video_id,
                    "video_title": clean_video_title(source, video_id),
                    "transcript": transcript,
                })
            except Exception as error:
                failed.append({
                    "video_id": video_id,
                    "title": clean_video_title(source, video_id),
                    "message": failure_notice(error),
                })
                safe_log(app, f"Video {video_id} captions failed", error)
                registry.update(job_id, finished=succeeded + len(failed), failed=list(failed))
        batches = split_summary_batches(pending)
        for batch_number, batch in enumerate(batches, start=1):
            registry.update(job_id, message=f"Writing summaries {batch_number} of {len(batches)}.")
            try:
                results = app.config["BATCH_SUMMARY_FUNCTION"](
                    batch, preferences,
                    usage_callback=lambda usage: app.config["USAGE"].record(session_id, usage),
                )
            except Exception as error:
                safe_log(app, f"Summary request {batch_number} failed", error)
                for video in batch:
                    failed.append({
                        "video_id": video["video_id"], "title": video["video_title"],
                        "message": failure_notice(error),
                    })
                registry.update(job_id, finished=succeeded + len(failed), failed=list(failed))
                continue
            succeeded = save_batch_results(
                app, job_id, source["source_key"], batch, results, succeeded, failed,
                source_keys=source_keys,
            )
        final_status = "complete" if not failed else "partial"
        for failure in failed:
            failure["source_key"] = (source_keys or {}).get(failure.get("video_id", ""), source["source_key"])
        registry.update(
            job_id,
            status=final_status,
            finished=len(video_ids),
            succeeded=succeeded,
            failed=failed,
            message="Summary batch finished.",
        )
    except Exception as error:
        safe_log(app, f"Summary batch {job_id[:8]} stopped", error)
        registry.update(
            job_id,
            status="error",
            failed=[{"video_id": "", "title": "Batch", "message": failure_notice(error)}],
            message=failure_notice(error),
        )


def run_source_inspection_job(
    app: Flask,
    job_id: str,
    kind: str,
    source_id: str,
    session_id: str,
    target_list: str = "",
    replace_saved: bool = False,
) -> None:
    """Fetch titles, update a list, and summarize new or approved videos."""
    registry: JobRegistry = app.config["JOBS"]
    store: ArchiveStore = app.config["STORE"]
    registry.update(job_id, status="running", message="Fetching video titles.")
    try:
        source = app.config["SOURCE_FETCHER"](kind, source_id)
        if kind == "video":
            source["archive_as_single"] = not bool(target_list)
        prior_archive = store.read()
        previous = prior_archive["sources"].get(source["source_key"])
        source = source_record(source, previous)
        titles = [str(video.get("title") or "") for video in source.get("videos", [])]
        registry.update(job_id, total=len(titles), message="Finding topics.")
        warning = ""
        try:
            labels = app.config["TOPIC_FUNCTION"](
                titles,
                usage_callback=lambda usage: app.config["USAGE"].record(session_id, usage),
            )
        except Exception as error:
            labels = ["Other"] * len(titles)
            warning = f"{failure_notice(error)} Titles are grouped under Other."
            safe_log(app, f"Source {source_id} title topic request failed", error)
        source = apply_title_topics(source, labels)
        single_target_video = source["videos"][0]["id"] if target_list and len(source["videos"]) == 1 else ""
        save_inspected_source(store, source, create_playlist_list=not (kind == "playlist" and single_target_video))
        if single_target_video:
            add_video_to_list(store, target_list, single_target_video)
        old_ids = {video["id"] for video in (previous or {}).get("videos", [])}
        new_ids = [video["id"] for video in source["videos"] if video["id"] not in old_ids]
        chosen_ids: list[str] = []
        if single_target_video and single_target_video not in prior_archive["summaries"]:
            chosen_ids = [single_target_video]
        elif previous and kind == "playlist" and replace_saved:
            chosen_ids = [video["id"] for video in source["videos"]]
        elif previous and kind == "playlist" and prior_archive["settings"]["auto_summarize_new"]:
            chosen_ids = new_ids
        if chosen_ids:
            registry.update(job_id, total=len(chosen_ids), message="Writing new video summaries.")
            run_summary_job(app, job_id, source, chosen_ids, replace_saved, session_id)
            failed = registry.get(job_id)["failed"]
            if failed:
                warning = f"{len(failed)} video summaries could not be completed."
        registry.update(
            job_id,
            status="complete",
            source_key=source["source_key"],
            source=source,
            warning=warning,
            finished=len(chosen_ids) if chosen_ids else len(titles),
            total=len(chosen_ids) if chosen_ids else len(titles),
            message="Title list is ready.",
        )
    except (SourceError, ValueError) as error:
        safe_log(app, f"Source {source_id} listing failed", error)
        registry.update(job_id, status="error", message=failure_notice(error))
    except Exception as error:
        safe_log(app, f"Source {source_id} listing failed", error)
        registry.update(
            job_id,
            status="error",
            message=failure_notice(error),
        )


def run_chat_job(app: Flask, job_id: str, video_id: str, question: str, session_id: str) -> None:
    """Answer one saved video's question and report progress to its page."""
    registry: JobRegistry = app.config["JOBS"]
    store: ArchiveStore = app.config["STORE"]
    registry.update(job_id, status="running", message="Reading captions for your question.")
    try:
        saved = store.read()["summaries"][video_id]
        transcript = app.config["TRANSCRIPT_FETCHER"](video_id)
        registry.update(job_id, message="Writing your answer.")
        answer = app.config["CHAT_FUNCTION"](
            saved["title"], transcript, saved["summary"], question, saved.get("chat", []),
            usage_callback=lambda usage: app.config["USAGE"].record(session_id, usage),
        )
        chat_turn = {"question": question, "answer": answer, "created_at": now_utc()}

        def save_chat(archive_data: dict[str, Any]) -> None:
            """Append this answer to the saved video's chat history."""
            archive_data["summaries"][video_id].setdefault("chat", []).append(chat_turn)

        store.update(save_chat)
        updated_archive = store.read()
        matching_lists = [
            item["id"] for item in updated_archive["summary_lists"].values()
            if video_id in item["video_ids"]
        ]
        source_key = matching_lists[-1] if matching_lists else f"video:{video_id}"
        registry.update(
            job_id, status="complete", question=question, answer=answer,
            source_key=source_key, video_id=video_id, message="Answer ready.",
        )
    except Exception as error:
        safe_log(app, f"Video {video_id} follow-up failed", error)
        registry.update(job_id, status="error", question=question, message=failure_notice(error))


def create_app(
    data_directory: str | Path | None = None,
    source_fetcher: Callable[[str, str], dict[str, Any]] = fetch_source,
    transcript_fetcher: Callable[[str], str] = fetch_english_transcript,
    topic_function: Callable[..., list[str]] = label_video_titles,
    batch_summary_function: Callable[..., dict[str, dict[str, str]]] = summarize_video_batch,
    chat_function: Callable[..., str] = answer_video_question,
) -> Flask:
    """Build a testable local app with replaceable YouTube and AI services."""
    app = Flask(__name__)
    configured_directory = Path(data_directory).expanduser() if data_directory is not None else DEFAULT_DATA_DIRECTORY
    is_explicit_directory = data_directory is not None or "PAGEONE_DATA_DIR" in os.environ
    legacy_directory = None if is_explicit_directory else Path(__file__).resolve().parent / "instance"
    migration_messages = migrate_data_files(configured_directory, legacy_directory)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),
        DATA_DIRECTORY=configured_directory,
        STORE=ArchiveStore(configured_directory / ARCHIVE_FILE_NAME),
        JOBS=JobRegistry(),
        USAGE=SessionUsageLedger(),
        SOURCE_FETCHER=source_fetcher,
        TRANSCRIPT_FETCHER=transcript_fetcher,
        TOPIC_FUNCTION=topic_function,
        BATCH_SUMMARY_FUNCTION=batch_summary_function,
        CHAT_FUNCTION=chat_function,
        MAX_CONTENT_LENGTH=1_000_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
    )
    configure_safe_logging(app)
    for migration_message in migration_messages:
        app.config["PAGEONE_LOGGER"].info(migration_message)

    @app.before_request
    def enforce_local_request() -> Any:
        """Prepare session counters and allow only loopback form requests."""
        session.permanent = False
        session.setdefault("usage_session_id", secrets.token_urlsafe(32))
        g.usage_session_id = session["usage_session_id"]
        if request.method == "GET":
            session.setdefault("csrf_token", secrets.token_urlsafe(32))
        g.csrf_token = session.get("csrf_token", "")
        host = (urlsplit(f"//{request.host}").hostname or "").lower()
        remote_address = request.remote_addr or "127.0.0.1"
        try:
            is_loopback = ipaddress.ip_address(remote_address).is_loopback
        except ValueError:
            is_loopback = False
        if host not in {"localhost", "127.0.0.1", "::1"} or not is_loopback:
            abort(403)
        if request.method == "GET":
            return None
        origin = request.headers.get("Origin")
        if origin:
            origin_parts = urlsplit(origin)
            if origin_parts.netloc.lower() != request.host.lower() or origin_parts.scheme != request.scheme:
                abort(403)
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            abort(403)
        return None

    @app.context_processor
    def page_template_values() -> dict[str, Any]:
        """Share form security, usage, and saved visual scale on every page."""
        usage = app.config["USAGE"].snapshot(getattr(g, "usage_session_id", "missing"))
        try:
            display_settings = app.config["STORE"].read()["settings"]
        except ValueError:
            display_settings = DEFAULT_SETTINGS
        return {
            "csrf_token": getattr(g, "csrf_token", ""), "app_name": APP_NAME,
            "usage": usage, "display_settings": display_settings,
            "answer_window": request.values.get("answer_window") == "1",
        }

    @app.errorhandler(ValueError)
    def unreadable_local_data(error: ValueError):
        """Explain archive validation errors without replacing saved bytes."""
        safe_log(app, "Local archive validation failed", error)
        return render_template(
            "notice.html",
            message="Saved items could not be opened. Your data has been kept.",
            tone="error",
        ), 500

    @app.errorhandler(403)
    def local_request_forbidden(error: Any):
        """Show a local error page with the session usage meter."""
        safe_log(app, "A forbidden page request was rejected")
        return render_template("notice.html", message="That request is not allowed.", tone="error"), 403

    @app.errorhandler(404)
    def page_not_found(error: Any):
        """Show a local not-found page with the session usage meter."""
        safe_log(app, "A missing page was requested")
        return render_template("notice.html", message="That PageOne page was not found.", tone="error"), 404

    @app.errorhandler(500)
    def internal_error(error: Any):
        """Render unexpected server errors with the always-visible meter."""
        original = getattr(error, "original_exception", None)
        if original:
            safe_log(app, "A local page request failed", original)
        else:
            safe_log(app, "A local page request returned an internal error")
        return render_template(
            "notice.html",
            message="Something went wrong. Please try again.",
            tone="error",
        ), 500

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        """Show a safe popup and log an error class for uncaught requests."""
        safe_log(app, "An unhandled page request failed", error)
        status = error.code if isinstance(error, HTTPException) else 500
        return render_template(
            "notice.html", message="Something went wrong. Please try again.", tone="error"
        ), status

    @app.after_request
    def set_safety_headers(response):
        """Limit framing, inline scripts, caching, and MIME sniffing."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/")
    def home():
        """Show the source search across the available viewport."""
        archive = app.config["STORE"].read()
        lists = sorted(archive["summary_lists"].values(), key=lambda item: item["title"].casefold())
        groups = archive_groups(archive, "")
        saved_entries = [entry for group in groups.values() for entry in group]
        saved_entries.sort(key=lambda item: item.get("title", "").casefold())
        return render_template("home.html", summary_lists=lists, saved_entries=saved_entries)

    @app.post("/inspect")
    def inspect_source():
        """Validate a link and start title listing as a local background job."""
        raw_url = request.form.get("source_url", "")
        try:
            identifiers = parse_youtube_url(raw_url)
        except SourceError as error:
            safe_log(app, "Source link validation failed", error)
            return render_template("notice.html", message=failure_notice(error), tone="error")
        selected_kind = request.form.get("source_kind", "")
        if identifiers["video_id"] and identifiers["playlist_id"] and selected_kind not in {"video", "playlist"}:
            return render_template(
                "ambiguity.html", source_url=raw_url,
                target_list=request.form.get("target_list", ""),
                replace_saved=request.form.get("replace_saved", ""),
            )
        kind = selected_kind or ("playlist" if identifiers["playlist_id"] else "video")
        target_list = request.form.get("target_list", "")
        if target_list and target_list not in app.config["STORE"].read()["summary_lists"]:
            return render_template("notice.html", message="Choose an existing summary list.", tone="error")
        source_id = identifiers["playlist_id"] if kind == "playlist" else identifiers["video_id"]
        if not source_id:
            safe_log(app, "Source selection was incomplete")
            return render_template("notice.html", message="Choose a video or playlist from the link.", tone="error")
        session_id = session["usage_session_id"]
        job_id = app.config["JOBS"].create("inspection", session_id)
        app.config["JOBS"].update(
            job_id, source_url=raw_url, source_kind=kind, target_list=target_list,
            replace_saved=request.form.get("replace_saved") == "yes",
        )
        job = app.config["JOBS"].get(job_id)
        worker = threading.Thread(
            target=run_source_inspection_job,
            args=(app, job_id, kind, source_id, session_id, target_list, request.form.get("replace_saved") == "yes"),
            daemon=True,
            name=f"pageone-{job_id[:8]}",
        )
        worker.start()
        return render_template("inspection_progress.html", job=job)

    @app.route("/sources/<path:source_key>", methods=["GET", "POST"])
    def source_results(source_key: str):
        """Show stored source titles with server-side sorting and selection."""
        archive = app.config["STORE"].read()
        source = archive["sources"].get(source_key)
        if not source:
            abort(404)
        all_ids = {video["id"] for video in source.get("videos", [])}
        sort_by = request.values.get("sort_choice") or request.values.get("sort_by", archive["settings"]["default_playlist_sort"])
        filter_text = request.values.get("filter_text", "")
        warning = request.values.get("warning", "")
        page = request.values.get("page_choice") or request.values.get("page", "1")
        if request.form.get("list_action") == "filter" or request.form.get("sort_choice"):
            page = "1"
        selected_ids = all_ids
        if request.method == "POST":
            action = request.form.get("list_action", "")
            if request.form.get("sort_choice") in VIDEO_SORT_OPTIONS:
                action = "sort"
            if action == "select_none":
                selected_ids = set()
            elif action == "select_all":
                selected_ids = all_ids
            else:
                selected_ids = set(request.form.getlist("video_ids")) & all_ids
            if action == "summarize":
                if not selected_ids:
                    return render_source_results(
                        source, archive["summaries"], sort_by, filter_text, selected_ids,
                        "Select at least one video to summarize.",
                    )
                session_id = session["usage_session_id"]
                job_id = app.config["JOBS"].create("summary", session_id, source_key, len(selected_ids))
                job = app.config["JOBS"].get(job_id)
                worker = threading.Thread(
                    target=run_summary_job,
                    args=(
                        app, job_id, source,
                        [video["id"] for video in source.get("videos", []) if video["id"] in selected_ids],
                        request.form.get("refresh") == "yes", session_id,
                    ),
                    daemon=True,
                    name=f"pageone-{job_id[:8]}",
                )
                worker.start()
                return render_template("job_progress.html", job=job)
        return render_source_results(
            source,
            archive["summaries"],
            sort_by,
            filter_text,
            selected_ids,
            warning,
            page,
        )

    @app.get("/jobs/<job_id>")
    def job_progress(job_id: str):
        """Return current progress or a completed inspection, batch, or chat."""
        job = app.config["JOBS"].get(job_id)
        if not job:
            safe_log(app, "A missing summary job was requested")
            return render_template("notice.html", message="That summary job is no longer available.", tone="error"), 404
        if job["session_id"] != session["usage_session_id"]:
            abort(403)
        if job["type"] == "chat":
            if job["status"] not in {"complete", "error"}:
                return render_template("chat_progress.html", job=job, answer_window=job.get("answer_window", False))
            if job["status"] == "complete" and job.get("source_key") and not job.get("answer_window"):
                return redirect(url_for(
                    "archive_detail", source_key=job["source_key"],
                    open_video=job["video_id"], _anchor=f"video-{job['video_id']}",
                ))
            message = job.get("answer") if job["status"] == "complete" else job["message"]
            return render_template(
                "chat_answer.html", question=job.get("question", ""), answer=message,
                tone="success" if job["status"] == "complete" else "error",
                video_id=job.get("video_id"), answer_window=job.get("answer_window", False),
                error_notice_message=message if job["status"] == "error" else "",
                dismiss_url=url_for("archive_index"),
            )
        if job["status"] in {"complete", "partial", "error"}:
            if job.get("retry_video"):
                saved = app.config["STORE"].read()["summaries"].get(job["retry_video"])
                return render_template("retry_result.html", job=job, saved=saved)
            if job["type"] == "inspection":
                if job["status"] == "error":
                    return render_template("inspection_failure.html", job=job)
                archive = app.config["STORE"].read()
                return render_source_results(
                    job["source"],
                    archive["summaries"],
                    sort_by=archive["settings"]["default_playlist_sort"],
                    warning=job.get("warning", ""),
                )
            try:
                archive = app.config["STORE"].read()
            except ValueError as error:
                safe_log(app, "Could not render a completed batch", error)
                return render_template("notice.html", message="Saved items could not be opened. Your data has been kept.", tone="error"), 500
            source = job.get("source") or archive["sources"].get(job["source_key"], {})
            filter_text = request.args.get("filter_text", "")[:MAX_FILTER_LENGTH]
            return render_template(
                "job_results.html",
                job=job,
                source=source,
                summaries=archive["summaries"],
                videos=filter_summary_videos(source.get("videos", []), archive["summaries"], filter_text),
                filter_text=filter_text,
                error_notice_message="Some videos could not be summarized." if job["failed"] and request.args.get("hide_notice") != "1" else "",
                dismiss_url=url_for("job_progress", job_id=job_id, hide_notice=1),
            )
        return render_template("job_progress.html", job=job)

    @app.get("/archive")
    def archive_index():
        """Show playlist, custom-list, and single-video archive groups."""
        archive = app.config["STORE"].read()
        query = request.args.get("q", "")[:MAX_FILTER_LENGTH]
        groups = archive_groups(archive, query)
        selected_entries = request.args.getlist("selected_entry")
        if request.args.get("selected_entry") == "matching":
            selected_entries = [entry["source_key"] for rows in groups.values() for entry in rows]
        return render_template(
            "archive.html", groups=groups, query=query, selected_entries=selected_entries,
            selection_notice=request.args.get("selection_notice", ""),
            archive_file=str(app.config["STORE"].file_path.resolve()),
        )

    @app.get("/archive/<path:source_key>")
    def archive_detail(source_key: str):
        """Show the saved video list and summaries for one source."""
        archive = app.config["STORE"].read()
        summary_list = archive["summary_lists"].get(source_key)
        source = list_source(archive, summary_list) if summary_list else archive["sources"].get(source_key)
        if source and source.get("kind") == "playlist" and not summary_list:
            source = None
        if not source and source_key.startswith("video:"):
            video_id = source_key.removeprefix("video:")
            saved = archive["summaries"].get(video_id)
            if saved:
                source = {
                    "source_key": source_key, "kind": "video", "id": video_id,
                    "title": saved["title"], "url": f"https://www.youtube.com/watch?v={video_id}",
                    "videos": [video_row_for_id(archive, video_id)],
                }
        if not source:
            abort(404)
        filter_text = request.args.get("filter_text", "")[:MAX_FILTER_LENGTH]
        open_video = request.args.get("open_video", "")
        selected_ids = request.args.getlist("selected")
        if request.args.get("selected") == "all":
            selected_ids = [video["id"] for video in source.get("videos", [])]
        elif request.args.get("selected") == "matching":
            selected_ids = [video["id"] for video in filter_summary_videos(source.get("videos", []), archive["summaries"], filter_text)]
        source_video_ids = {video["id"] for video in source.get("videos", [])}
        selected_ids = [video_id for video_id in selected_ids if video_id in source_video_ids]
        videos = filter_summary_videos(source.get("videos", []), archive["summaries"], filter_text)
        return render_template(
            "archive_detail.html",
            source=source,
            summaries=archive["summaries"],
            videos=videos,
            filter_text=filter_text,
            open_video=open_video,
            selected_ids=selected_ids,
            selection_notice=request.args.get("selection_notice", ""),
            targets=sorted(
                [item for item in archive["summary_lists"].values() if item["id"] != source_key],
                key=lambda item: item["title"].casefold(),
            ),
            can_delete_list=summary_list is not None,
        )

    @app.post("/archive/actions")
    def archive_actions():
        """Apply a checked Home or Archive action to saved entries and videos."""
        action = request.form.get("action", "")
        if action not in ARCHIVE_ACTIONS:
            abort(400)
        store: ArchiveStore = app.config["STORE"]
        archive = store.read()
        source_key = request.form.get("source_key", "")
        entry_ids = request.form.getlist("entry_ids")
        selected_ids = request.form.getlist("video_ids")
        try:
            if action in {"select_all", "select_none"}:
                if source_key:
                    selected_detail_source(archive, source_key)
                    filter_text = request.form.get("filter_text", "")[:MAX_FILTER_LENGTH]
                    query = {"selected": "matching", "filter_text": filter_text} if action == "select_all" else {"selection_notice": "Selection cleared.", "filter_text": filter_text}
                    return redirect(url_for("archive_detail", source_key=source_key, **query))
                index_query = request.form.get("q", "")[:MAX_FILTER_LENGTH]
                query = {"selected_entry": "matching", "q": index_query} if action == "select_all" else {"selection_notice": "Selection cleared.", "q": index_query}
                return redirect(url_for("archive_index", **query))

            detail_source = selected_detail_source(archive, source_key) if source_key else None
            if detail_source:
                sources = [detail_source]
                if action == "reopen":
                    if selected_ids:
                        selected_video_sources(sources, selected_ids)
                        return redirect(url_for("archive_detail", source_key=source_key, selected=selected_ids, filter_text=request.form.get("filter_text", "")[:MAX_FILTER_LENGTH]))
                    return redirect(url_for("archive_detail", source_key=source_key))
                video_ids, source_keys, videos_by_id = selected_video_sources(sources, selected_ids)
            else:
                if action in {"copy", "move", "delete_summaries"}:
                    raise ValueError("Choose videos from an archive entry first.")
                index_query = request.form.get("q", "")[:MAX_FILTER_LENGTH]
                visible_groups = archive_groups(archive, index_query)
                visible_ids = {entry["source_key"] for rows in visible_groups.values() for entry in rows}
                if not entry_ids or not set(entry_ids).issubset(visible_ids):
                    raise ValueError("One or more selected entries are not visible in this archive view.")
                sources = selected_sources(archive, entry_ids)
                if action == "reopen":
                    if len(sources) != 1:
                        raise ValueError("Reopen one saved entry at a time.")
                    return redirect(url_for("archive_detail", source_key=sources[0]["source_key"], selected="matching"))
                video_ids, source_keys, videos_by_id = selected_video_sources(sources)

            if action in {"summarize", "retry"}:
                replacement = action == "summarize" and request.form.get("replace_saved") == "yes"
                source_key_for_job = sources[0]["source_key"] if len(sources) == 1 else ""
                batch_source = {
                    "source_key": source_key_for_job,
                    "kind": "selection",
                    "title": "Selected archive videos",
                    "videos": list(videos_by_id.values()),
                }
                session_id = session["usage_session_id"]
                job_id = app.config["JOBS"].create("summary", session_id, source_key_for_job, len(video_ids))
                app.config["JOBS"].update(job_id, source=batch_source)
                job = app.config["JOBS"].get(job_id)
                worker = threading.Thread(
                    target=run_summary_job,
                    args=(app, job_id, batch_source, video_ids, replacement, session_id, source_keys),
                    daemon=True, name=f"pageone-{job_id[:8]}",
                )
                worker.start()
                return render_template("job_progress.html", job=job)

            if action in {"copy", "move"}:
                target_id = request.form.get("target_list", "")
                def transfer(archive_data: dict[str, Any]) -> None:
                    """Save the selected list memberships in one atomic write."""
                    transfer_memberships(archive_data, source_keys, video_ids, target_id, action, now_utc())
                store.update(transfer)
                return redirect(url_for("archive_detail", source_key=target_id if action == "move" else source_key, filter_text=request.form.get("filter_text", "")[:MAX_FILTER_LENGTH]))

            if action == "delete_summaries":
                if request.form.get("confirm") != "yes":
                    raise ValueError("Confirm the selected summary deletion first.")
                def delete(archive_data: dict[str, Any]) -> None:
                    """Remove the confirmed summaries and all their list links."""
                    delete_selected_summaries(archive_data, video_ids, now_utc())
                store.update(delete)
                updated_archive = store.read()
                if source_key not in updated_archive["summary_lists"] and source_key not in updated_archive["sources"]:
                    return redirect(url_for("archive_index"))
                return redirect(url_for("archive_detail", source_key=source_key, filter_text=request.form.get("filter_text", "")[:MAX_FILTER_LENGTH]))
        except ValueError as error:
            safe_log(app, "Archive action validation failed", error)
            return render_template("notice.html", message=str(error), tone="error"), 400
        return redirect(url_for("archive_index"))

    @app.post("/lists")
    def create_summary_list():
        """Create an empty named list in the local archive."""
        title = request.form.get("title", "").strip()
        if not title or len(title) > MAX_LIST_TITLE_LENGTH:
            safe_log(app, "Summary list title validation failed")
            return render_template("notice.html", message="Enter a list name up to 120 characters.", tone="error")
        list_id = f"list:{uuid.uuid4().hex}"

        def change(archive: dict[str, Any]) -> None:
            """Store the new list with no duplicated video summaries."""
            archive["summary_lists"][list_id] = {
                "id": list_id, "title": title, "kind": "custom", "source_key": "",
                "video_ids": [], "created_at": now_utc(), "updated_at": now_utc(),
            }

        app.config["STORE"].update(change)
        return redirect(url_for("archive_detail", source_key=list_id))

    @app.post("/lists/<path:list_id>/delete")
    def delete_summary_list(list_id: str):
        """Delete one list and keep each shared video summary intact."""
        if request.form.get("confirm") != "yes":
            return render_template("notice.html", message="Confirm the list deletion first.", tone="error")
        def change(archive: dict[str, Any]) -> None:
            """Remove only the requested list membership container."""
            if list_id not in archive["summary_lists"]:
                raise ValueError("The summary list no longer exists.")
            del archive["summary_lists"][list_id]

        try:
            app.config["STORE"].update(change)
        except ValueError as error:
            safe_log(app, "Summary list deletion failed", error)
            return render_template("notice.html", message="That summary list is no longer available.", tone="error")
        return redirect(url_for("archive_index"))

    @app.post("/videos/<video_id>/delete")
    def delete_video_summary(video_id: str):
        """Remove one saved summary and its memberships after confirmation."""
        if request.form.get("confirm") != "yes":
            return render_template("notice.html", message="Confirm the summary deletion first.", tone="error")
        source_key = request.form.get("return_to", "")

        def change(archive: dict[str, Any]) -> None:
            """Remove the summary, chat, and list links for one video."""
            if video_id not in archive["summaries"]:
                raise ValueError("The video summary no longer exists.")
            del archive["summaries"][video_id]
            archive["sources"].pop(f"video:{video_id}", None)
            for item in archive["summary_lists"].values():
                if video_id in item["video_ids"]:
                    item["video_ids"].remove(video_id)
                    item["updated_at"] = now_utc()

        try:
            app.config["STORE"].update(change)
        except ValueError as error:
            safe_log(app, "Video summary deletion failed", error)
            return render_template("notice.html", message="That video summary is no longer available.", tone="error")
        archive = app.config["STORE"].read()
        if source_key in archive["summary_lists"]:
            return redirect(url_for("archive_detail", source_key=source_key))
        return redirect(url_for("archive_index"))

    @app.post("/archive/<path:source_key>/transfer")
    def transfer_video(source_key: str):
        """Copy or move one video into another saved summary list."""
        video_id = request.form.get("video_id", "")
        target_id = request.form.get("target_list", "")
        action = request.form.get("action", "")
        if action not in {"copy", "move"}:
            safe_log(app, "Video list action validation failed")
            abort(400)

        def change(archive: dict[str, Any]) -> None:
            """Change list memberships atomically without copying AI text."""
            target = archive["summary_lists"].get(target_id)
            origin = archive["summary_lists"].get(source_key)
            single = archive["sources"].get(source_key)
            if not target or target_id == source_key:
                raise ValueError("Choose a saved video and another summary list.")
            if origin and video_id not in origin["video_ids"]:
                raise ValueError("That video is no longer in this list.")
            is_orphan = source_key == f"video:{video_id}" and video_id in archive["summaries"]
            if not origin and not is_orphan and (not single or single.get("id") != video_id):
                raise ValueError("That single video is no longer available.")
            if video_id not in target["video_ids"]:
                target["video_ids"].append(video_id)
                target["updated_at"] = now_utc()
            if action == "move" and origin:
                origin["video_ids"].remove(video_id)
                origin["updated_at"] = now_utc()
            if action == "move" and not origin and single:
                single["archive_as_single"] = False

        try:
            app.config["STORE"].update(change)
        except ValueError as error:
            safe_log(app, "Video list transfer failed", error)
            return render_template("notice.html", message="Choose a video and another saved list.", tone="error")
        return redirect(url_for("archive_detail", source_key=target_id if action == "move" else source_key))

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        """Display and persist the user's reusable summary preferences."""
        store: ArchiveStore = app.config["STORE"]
        message = ""
        tone = "success"
        if request.method == "POST":
            preferences = request.form.get("summary_preferences", "").strip()
            current_settings = store.read()["settings"]
            playlist_sort = request.form.get("default_playlist_sort", current_settings["default_playlist_sort"])
            archive_sort = request.form.get("archive_sort", current_settings["archive_sort"])
            interface_scale = request.form.get("interface_scale", current_settings["interface_scale"])
            reading_width = request.form.get("reading_width", current_settings["reading_width"])
            message = settings_error_message(
                preferences, playlist_sort, archive_sort, interface_scale, reading_width,
            )
            if message:
                tone = "error"
            else:
                auto_new = request.form.get("auto_summarize_new") == "yes" if request.form.get("settings_form") == "yes" else None
                save_general_settings(
                    store, preferences, playlist_sort, archive_sort, auto_new,
                    interface_scale, reading_width,
                )
                message = "Summary preferences saved."
        archive = store.read()
        if tone == "error":
            safe_log(app, "Summary preference validation failed")
        return render_template(
            "settings.html",
            preferences=archive["summary_preferences"] or DEFAULT_PREFERENCES,
            general_settings=archive["settings"],
            playlist_sort_options=VIDEO_SORT_LABELS,
            message=message,
            tone=tone,
            error_notice_message=message if tone == "error" else "",
            dismiss_url=url_for("settings"),
            log_file=str((app.config["DATA_DIRECTORY"] / LOG_FILE_NAME).resolve()),
        )

    @app.post("/chat/<video_id>")
    def chat_about_video(video_id: str):
        """Validate a follow-up and show progress while its answer is written."""
        archive = app.config["STORE"].read()
        saved = archive["summaries"].get(video_id)
        if not saved:
            safe_log(app, "A follow-up was requested without a saved summary")
            return render_template("notice.html", message="Summarize this video before starting a chat.", tone="error")
        question = request.form.get("question", "").strip()
        if not question or len(question) > MAX_QUESTION_LENGTH:
            safe_log(app, "A follow-up question failed validation")
            return render_template("chat_answer.html", question=question, answer="Enter a question up to 1,000 characters.", tone="error", error_notice_message="Enter a question up to 1,000 characters.", dismiss_url=url_for("archive_index"))
        session_id = session["usage_session_id"]
        job_id = app.config["JOBS"].create("chat", session_id)
        app.config["JOBS"].update(job_id, video_id=video_id, answer_window=request.form.get("answer_window") == "1")
        job = app.config["JOBS"].get(job_id)
        worker = threading.Thread(
            target=run_chat_job, args=(app, job_id, video_id, question, session_id),
            daemon=True, name=f"pageone-{job_id[:8]}",
        )
        worker.start()
        return render_template("chat_progress.html", job=job)

    @app.post("/retry-video/<path:source_key>/<video_id>")
    def retry_video_summary(source_key: str, video_id: str):
        """Retry one failed video without repeating successful summaries."""
        archive = app.config["STORE"].read()
        try:
            source = selected_detail_source(archive, source_key)
            selected_video_sources([source], [video_id])
        except ValueError:
            abort(404)
        session_id = session["usage_session_id"]
        job_id = app.config["JOBS"].create("summary", session_id, source_key, 1)
        app.config["JOBS"].update(job_id, retry_video=video_id, source=source)
        job = app.config["JOBS"].get(job_id)
        worker = threading.Thread(
            target=run_summary_job,
            args=(app, job_id, source, [video_id], False, session_id),
            daemon=True, name=f"pageone-retry-{job_id[:8]}",
        )
        worker.start()
        return render_template("job_progress.html", job=job)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
