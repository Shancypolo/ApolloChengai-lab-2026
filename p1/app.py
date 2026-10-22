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

from storage import DEFAULT_PREFERENCES, JsonStore
from summary_service import SummaryError, answer_video_question, label_video_titles, summarize_video
from usage_accounting import SessionUsageLedger
from youtube_source import (
    SourceError,
    fetch_english_transcript,
    fetch_source,
    parse_youtube_url,
)


APP_NAME = "PageOne"
DEFAULT_DATA_DIRECTORY = Path(
    os.environ.get("PAGEONE_DATA_DIR", str(Path(__file__).parent / "instance"))
).expanduser()
LOG_FILE_NAME = "pageone.log"
MAX_PREFERENCE_LENGTH = 2_000
MAX_QUESTION_LENGTH = 1_000
MAX_FILTER_LENGTH = 200
VIDEO_SORT_OPTIONS = {"original", "published_at", "author", "topic", "title"}


class JobRegistry:
    """Own in-memory progress for summary batches until this app stops."""

    def __init__(self):
        """Start with no jobs and protect updates from worker threads."""
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, job_type: str, session_id: str, source_key: str = "", total: int = 0) -> str:
        """Create a queued inspection or summary job and return its ID."""
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
    store: JsonStore,
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
        archive["summaries"][video_id] = {
            "video_id": video_id,
            "title": title,
            "source_keys": old_source_keys,
            "summary": result["summary"],
            "topics": [clean_video_topic(archive["sources"].get(source_key, {}), video_id)],
            "created_at": old_summary.get("created_at", now_utc()),
            "updated_at": now_utc(),
            "chat": chat_history,
        }
        saved_source = archive["sources"].get(source_key)
        if saved_source:
            archive["sources"][source_key] = attach_summary_to_source(
                saved_source, video_id, archive["summaries"][video_id]
            )
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
):
    """Render a complete source page with server-sorted selection state."""
    all_ids = [video["id"] for video in source.get("videos", [])]
    selected = set(all_ids) if selected_ids is None else selected_ids
    visible_videos = ordered_source_videos(source, sort_by, filter_text)
    visible_ids = {video["id"] for video in visible_videos}
    return render_template(
        "source_results.html",
        source=source,
        summaries=summaries,
        videos=visible_videos,
        selected_ids=selected,
        hidden_selected_ids=selected - visible_ids,
        sort_by=sort_by if sort_by in VIDEO_SORT_OPTIONS else "original",
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


def save_inspected_source(store: JsonStore, source: dict[str, Any]) -> None:
    """Save title topics and refresh matching archived summary labels."""
    def change(archive: dict[str, Any]) -> None:
        """Update the source and reuse its title label in saved summaries."""
        archive["sources"][source["source_key"]] = source
        for video in source.get("videos", []):
            saved = archive["summaries"].get(video["id"])
            if saved:
                saved["topics"] = [video.get("topic") or "Other"]
    store.update(change)


def link_existing_summary(store: JsonStore, source_key: str, video_id: str) -> None:
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
    store.update(change)


def run_summary_job(
    app: Flask,
    job_id: str,
    source: dict[str, Any],
    video_ids: list[str],
    refresh: bool,
    session_id: str,
) -> None:
    """Summarize selected videos sequentially and update batch progress."""
    registry: JobRegistry = app.config["JOBS"]
    store: JsonStore = app.config["STORE"]
    registry.update(job_id, status="running", message="Fetching captions and writing summaries.")
    try:
        archive = store.read()
        preferences = archive["summary_preferences"]
        failed: list[dict[str, str]] = []
        succeeded = 0
        for index, video_id in enumerate(video_ids, start=1):
            registry.update(job_id, finished=index - 1, message=f"Working on video {index} of {len(video_ids)}.")
            existing = store.read()["summaries"].get(video_id)
            if existing and not refresh:
                link_existing_summary(store, source["source_key"], video_id)
                succeeded += 1
                continue
            try:
                transcript = app.config["TRANSCRIPT_FETCHER"](video_id)
                result = app.config["SUMMARY_FUNCTION"](
                    clean_video_title(source, video_id),
                    transcript,
                    preferences,
                    usage_callback=lambda usage: app.config["USAGE"].record(session_id, usage),
                )
                update_saved_summary(
                    store,
                    source["source_key"],
                    video_id,
                    clean_video_title(source, video_id),
                    result,
                )
                succeeded += 1
            except (SourceError, SummaryError) as error:
                failed.append({"video_id": video_id, "title": clean_video_title(source, video_id), "message": failure_notice(error)})
                safe_log(app, f"Video {video_id} could not be summarized", error)
            except Exception as error:
                failed.append({
                    "video_id": video_id,
                    "title": clean_video_title(source, video_id),
                    "message": failure_notice(error),
                })
                safe_log(app, f"Video {video_id} request failed", error)
            registry.update(job_id, finished=index, succeeded=succeeded, failed=list(failed))
        final_status = "complete" if not failed else "partial"
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
) -> None:
    """Fetch source titles, classify only those titles, and save the list."""
    registry: JobRegistry = app.config["JOBS"]
    store: JsonStore = app.config["STORE"]
    registry.update(job_id, status="running", message="Fetching video titles.")
    try:
        source = app.config["SOURCE_FETCHER"](kind, source_id)
        previous = store.read()["sources"].get(source["source_key"])
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
        save_inspected_source(store, source)
        registry.update(
            job_id,
            status="complete",
            source_key=source["source_key"],
            source=source,
            warning=warning,
            finished=len(titles),
            total=len(titles),
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
def create_app(
    data_directory: str | Path | None = None,
    source_fetcher: Callable[[str, str], dict[str, Any]] = fetch_source,
    transcript_fetcher: Callable[[str], str] = fetch_english_transcript,
    topic_function: Callable[..., list[str]] = label_video_titles,
    summary_function: Callable[..., dict[str, Any]] = summarize_video,
    chat_function: Callable[..., str] = answer_video_question,
) -> Flask:
    """Build a testable local app with replaceable YouTube and AI services."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),
        DATA_DIRECTORY=Path(data_directory or DEFAULT_DATA_DIRECTORY),
        STORE=JsonStore(Path(data_directory or DEFAULT_DATA_DIRECTORY) / "pageone.json"),
        JOBS=JobRegistry(),
        USAGE=SessionUsageLedger(),
        SOURCE_FETCHER=source_fetcher,
        TRANSCRIPT_FETCHER=transcript_fetcher,
        TOPIC_FUNCTION=topic_function,
        SUMMARY_FUNCTION=summary_function,
        CHAT_FUNCTION=chat_function,
        MAX_CONTENT_LENGTH=1_000_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
    )
    configure_safe_logging(app)

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
        """Share form security and the current session's usage counter."""
        usage = app.config["USAGE"].snapshot(getattr(g, "usage_session_id", "missing"))
        return {"csrf_token": getattr(g, "csrf_token", ""), "app_name": APP_NAME, "usage": usage}

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
            "default-src 'self'; script-src 'none'; "
            "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/")
    def home():
        """Show the source search across the available viewport."""
        return render_template("home.html")

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
            return render_template("ambiguity.html", source_url=raw_url)
        kind = selected_kind or ("playlist" if identifiers["playlist_id"] else "video")
        source_id = identifiers["playlist_id"] if kind == "playlist" else identifiers["video_id"]
        if not source_id:
            safe_log(app, "Source selection was incomplete")
            return render_template("notice.html", message="Choose a video or playlist from the link.", tone="error")
        session_id = session["usage_session_id"]
        job_id = app.config["JOBS"].create("inspection", session_id)
        job = app.config["JOBS"].get(job_id)
        worker = threading.Thread(
            target=run_source_inspection_job,
            args=(app, job_id, kind, source_id, session_id),
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
        sort_by = request.values.get("sort_by", "original")
        filter_text = request.values.get("filter_text", "")
        warning = request.values.get("warning", "")
        selected_ids = all_ids
        if request.method == "POST":
            action = request.form.get("list_action", "")
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
        )

    @app.get("/jobs/<job_id>")
    def job_progress(job_id: str):
        """Return current progress or the completed summary batch."""
        job = app.config["JOBS"].get(job_id)
        if not job:
            safe_log(app, "A missing summary job was requested")
            return render_template("notice.html", message="That summary job is no longer available.", tone="error"), 404
        if job["status"] in {"complete", "partial", "error"}:
            if job["type"] == "inspection":
                if job["status"] == "error":
                    return render_template("notice.html", message=job["message"], tone="error")
                archive = app.config["STORE"].read()
                return render_source_results(
                    job["source"],
                    archive["summaries"],
                    warning=job.get("warning", ""),
                )
            try:
                archive = app.config["STORE"].read()
            except ValueError as error:
                safe_log(app, "Could not render a completed batch", error)
                return render_template("notice.html", message="Saved items could not be opened. Your data has been kept.", tone="error"), 500
            source = archive["sources"].get(job["source_key"], {})
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
        """Show saved playlists and videos in newest-first order."""
        archive = app.config["STORE"].read()
        sources = sorted(archive["sources"].values(), key=lambda item: item.get("updated_at", ""), reverse=True)
        query = request.args.get("q", "")[:MAX_FILTER_LENGTH]
        return render_template("archive.html", sources=archive_rows(sources, query), query=query)

    @app.get("/archive/<path:source_key>")
    def archive_detail(source_key: str):
        """Show the saved video list and summaries for one source."""
        archive = app.config["STORE"].read()
        source = archive["sources"].get(source_key)
        if not source:
            abort(404)
        filter_text = request.args.get("filter_text", "")[:MAX_FILTER_LENGTH]
        videos = filter_summary_videos(source.get("videos", []), archive["summaries"], filter_text)
        return render_template(
            "archive_detail.html",
            source=source,
            summaries=archive["summaries"],
            videos=videos,
            filter_text=filter_text,
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        """Display and persist the user's reusable summary preferences."""
        store: JsonStore = app.config["STORE"]
        message = ""
        tone = "success"
        if request.method == "POST":
            preferences = request.form.get("summary_preferences", "").strip()
            if not preferences:
                message, tone = "Preferences cannot be blank.", "error"
            elif len(preferences) > MAX_PREFERENCE_LENGTH:
                message, tone = f"Keep preferences under {MAX_PREFERENCE_LENGTH} characters.", "error"
            else:
                store.update(lambda archive: archive.__setitem__("summary_preferences", preferences))
                message = "Summary preferences saved."
        archive = store.read()
        if tone == "error":
            safe_log(app, "Summary preference validation failed")
        return render_template(
            "settings.html",
            preferences=archive["summary_preferences"] or DEFAULT_PREFERENCES,
            message=message,
            tone=tone,
            error_notice_message=message if tone == "error" else "",
            dismiss_url=url_for("settings"),
        )

    @app.post("/chat/<video_id>")
    def chat_about_video(video_id: str):
        """Fetch fresh captions, answer a follow-up, and save only Q&A text."""
        archive = app.config["STORE"].read()
        saved = archive["summaries"].get(video_id)
        if not saved:
            safe_log(app, "A follow-up was requested without a saved summary")
            return render_template("notice.html", message="Summarize this video before starting a chat.", tone="error")
        question = request.form.get("question", "").strip()
        if not question or len(question) > MAX_QUESTION_LENGTH:
            safe_log(app, "A follow-up question failed validation")
            return render_template("chat_answer.html", question=question, answer="Enter a question up to 1,000 characters.", tone="error", error_notice_message="Enter a question up to 1,000 characters.", dismiss_url=url_for("archive_index"))
        try:
            transcript = app.config["TRANSCRIPT_FETCHER"](video_id)
            session_id = session["usage_session_id"]
            answer = app.config["CHAT_FUNCTION"](
                saved["title"],
                transcript,
                saved["summary"],
                question,
                saved.get("chat", []),
                usage_callback=lambda usage: app.config["USAGE"].record(session_id, usage),
            )
            chat_turn = {"question": question, "answer": answer, "created_at": now_utc()}
            def save_chat(archive_data: dict[str, Any]) -> None:
                """Append this answer to the video's compact chat history."""
                archive_data["summaries"][video_id].setdefault("chat", []).append(chat_turn)
            app.config["STORE"].update(save_chat)
            source_key = (saved.get("source_keys") or [""])[-1]
            if source_key:
                return redirect(url_for("archive_detail", source_key=source_key))
            return render_template("chat_answer.html", question=question, answer=answer, tone="success")
        except (SourceError, SummaryError) as error:
            safe_log(app, f"Video {video_id} follow-up failed", error)
            message = failure_notice(error)
            return render_template("chat_answer.html", question=question, answer=message, tone="error", error_notice_message=message, dismiss_url=url_for("archive_index"))
        except Exception as error:
            safe_log(app, f"Video {video_id} follow-up failed", error)
            return render_template(
                "chat_answer.html",
                question=question,
                answer=failure_notice(error),
                tone="error",
                error_notice_message=failure_notice(error),
                dismiss_url=url_for("archive_index"),
            )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
