"""Resolve archive selections and apply membership-only bulk changes."""

from __future__ import annotations

from typing import Any


def video_row_for_id(archive: dict[str, Any], video_id: str) -> dict[str, Any]:
    """Find saved metadata for a video or create a summary-backed row."""
    for source in archive["sources"].values():
        for video in source.get("videos", []):
            if video.get("id") == video_id:
                return video
    saved = archive["summaries"].get(video_id, {})
    return {
        "id": video_id, "title": saved.get("title", "Untitled video"),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": "Unknown", "author": "Unknown",
        "topic": ", ".join(saved.get("topics", [])) or "Other",
    }


def list_source(archive: dict[str, Any], summary_list: dict[str, Any]) -> dict[str, Any]:
    """Shape a saved list for the archive detail view."""
    return {
        "source_key": summary_list["id"], "kind": summary_list["kind"],
        "title": summary_list["title"], "url": "",
        "videos": [video_row_for_id(archive, video_id) for video_id in summary_list["video_ids"]],
    }


def selected_sources(archive: dict[str, Any], entry_ids: list[str]) -> list[dict[str, Any]]:
    """Resolve archive index IDs to their saved source or list snapshots."""
    sources = []
    for entry_id in dict.fromkeys(entry_ids):
        summary_list = archive["summary_lists"].get(entry_id)
        source = list_source(archive, summary_list) if summary_list else archive["sources"].get(entry_id)
        if source and source.get("kind") == "playlist" and not summary_list:
            source = None
        if source is None and entry_id.startswith("video:"):
            video_id = entry_id.removeprefix("video:")
            if video_id in archive["summaries"]:
                source = {
                    "source_key": entry_id, "kind": "video", "id": video_id,
                    "title": archive["summaries"][video_id].get("title", "Untitled video"),
                    "videos": [video_row_for_id(archive, video_id)],
                }
        if not source:
            raise ValueError("One or more selected archive entries are no longer available.")
        sources.append(source)
    if not sources:
        raise ValueError("Select at least one saved entry or video.")
    return sources


def selected_detail_source(archive: dict[str, Any], source_key: str) -> dict[str, Any]:
    """Resolve a saved list, inspected source, or orphan summary for detail actions."""
    summary_list = archive["summary_lists"].get(source_key)
    source = list_source(archive, summary_list) if summary_list else archive["sources"].get(source_key)
    if source and source.get("kind") == "playlist" and not summary_list:
        source = None
    if source is None and source_key.startswith("video:"):
        video_id = source_key.removeprefix("video:")
        if video_id in archive["summaries"]:
            source = {
                "source_key": source_key, "kind": "video", "id": video_id,
                "title": archive["summaries"][video_id].get("title", "Untitled video"),
                "videos": [video_row_for_id(archive, video_id)],
            }
    if not source:
        raise ValueError("That archive entry is no longer available.")
    return source


def selected_video_sources(
    sources: list[dict[str, Any]], video_ids: list[str] | None = None,
) -> tuple[list[str], dict[str, str], dict[str, dict[str, Any]]]:
    """Return unique valid video IDs and the source snapshot for each selection."""
    requested = set(video_ids) if video_ids is not None else None
    source_by_video: dict[str, str] = {}
    videos_by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_key = source["source_key"]
        for video in source.get("videos", []):
            video_id = video["id"]
            if requested is not None and video_id not in requested:
                continue
            source_by_video.setdefault(video_id, source_key)
            videos_by_id.setdefault(video_id, video)
    if requested is not None and not requested.issubset(videos_by_id):
        raise ValueError("One or more selected videos are not in this archive entry.")
    if not videos_by_id:
        raise ValueError("Select at least one saved video.")
    return list(videos_by_id), source_by_video, videos_by_id


def transfer_memberships(
    archive: dict[str, Any], source_keys: dict[str, str], video_ids: list[str],
    target_id: str, action: str, now: str,
) -> None:
    """Copy or move selected memberships while preserving canonical summaries."""
    target = archive["summary_lists"].get(target_id)
    if not target:
        raise ValueError("Choose an existing summary list.")
    for video_id in video_ids:
        source_key = source_keys[video_id]
        origin = archive["summary_lists"].get(source_key)
        single = archive["sources"].get(source_key)
        is_orphan = source_key == f"video:{video_id}" and video_id in archive["summaries"]
        if source_key == target_id or (not origin and not is_orphan and not single):
            raise ValueError("Choose a video and another saved list.")
        if origin and video_id not in origin["video_ids"]:
            raise ValueError("A selected video is no longer in its source list.")
        if video_id not in target["video_ids"]:
            target["video_ids"].append(video_id)
            target["updated_at"] = now
        if action == "move" and origin:
            origin["video_ids"].remove(video_id)
            origin["updated_at"] = now
        if action == "move" and not origin and single:
            single["archive_as_single"] = False


def delete_selected_summaries(archive: dict[str, Any], video_ids: list[str], now: str) -> None:
    """Delete selected canonical summaries and remove all their list links."""
    for video_id in video_ids:
        if video_id not in archive["summaries"]:
            raise ValueError("A selected summary is no longer available.")
    for video_id in video_ids:
        del archive["summaries"][video_id]
        archive["sources"].pop(f"video:{video_id}", None)
        for summary_list in archive["summary_lists"].values():
            if video_id in summary_list["video_ids"]:
                summary_list["video_ids"].remove(video_id)
                summary_list["updated_at"] = now
