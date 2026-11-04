"""Offline checks for checked Archive actions and saved summary safety."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from app import archive_groups, create_app, save_inspected_source


def fixture_source(kind: str, source_id: str) -> dict:
    """Return two predictable rows for a local archive source."""
    videos = [
        {
            "id": f"arc{i:08d}", "title": f"Archive fixture {i}",
            "url": f"https://www.youtube.com/watch?v=arc{i:08d}",
            "published_at": "2024-01-01", "author": "Fixture", "topic": "Fixture",
        }
        for i in range(2)
    ]
    return {
        "source_key": f"{kind}:{source_id}", "kind": kind, "id": source_id,
        "title": "Fixture playlist", "url": "", "videos": videos,
    }


class ArchiveActionContracts(unittest.TestCase):
    """Check selection validation, no-overwrite defaults, and list transfers."""

    def setUp(self):
        """Create a temporary app with providers that never use the network."""
        self.directory = tempfile.TemporaryDirectory(prefix="pageone-archive-actions-")
        self.calls = []
        self.app = create_app(
            self.directory.name,
            source_fetcher=fixture_source,
            transcript_fetcher=lambda video_id: f"Transcript {video_id}",
            topic_function=lambda titles, usage_callback=None: ["Fixture"] * len(titles),
            batch_summary_function=self.summarize,
            chat_function=lambda *args, **kwargs: "Fixture answer.",
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as current_session:
            self.csrf = current_session["csrf_token"]
        store = self.app.config["STORE"]
        save_inspected_source(store, fixture_source("playlist", "PLfixture123"))
        self.source_key = "playlist:PLfixture123"
        self.video_ids = ["arc00000000", "arc00000001"]
        store.update(lambda archive: archive["summary_lists"].update({
            "list:target": {
                "id": "list:target", "title": "Target", "kind": "custom",
                "source_key": "", "video_ids": [], "created_at": "", "updated_at": "",
            },
        }))

    def summarize(self, videos, preferences, usage_callback=None):
        """Count model calls and return one result for each requested ID."""
        self.calls.append([video["video_id"] for video in videos])
        return {video["video_id"]: {"summary": "New fixture summary."} for video in videos}

    def tearDown(self):
        """Remove the temporary archive directory."""
        self.directory.cleanup()

    def post_action(self, action, **values):
        """Send one CSRF-protected action form."""
        return self.client.post("/archive/actions", data={"csrf_token": self.csrf, "action": action, **values})

    def wait_for_job(self, response):
        """Wait for the returned summary job to finish its fake providers."""
        job_id = response.get_data(as_text=True).split("url=/jobs/", 1)[1].split('"', 1)[0]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = self.app.config["JOBS"].get(job_id)
            if job["status"] in {"complete", "partial", "error"}:
                return job
            time.sleep(0.01)
        self.fail("Archive action job did not finish.")

    def test_bulk_summary_deduplicates_videos_and_skips_saved_items(self):
        """Summarize a list once, then retry without replacing its saved text."""
        first = self.post_action("summarize", entry_ids=[self.source_key])
        self.assertIn('http-equiv="refresh"', first.get_data(as_text=True))
        self.assertIn("url=/jobs/", first.get_data(as_text=True))
        self.assertEqual(self.wait_for_job(first)["status"], "complete")
        self.assertEqual(self.calls, [self.video_ids])
        store = self.app.config["STORE"]
        store.update(lambda archive: archive["summaries"][self.video_ids[0]].update({"summary": "Keep this."}))
        second = self.post_action("retry", entry_ids=[self.source_key])
        self.assertEqual(self.wait_for_job(second)["status"], "complete")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(store.read()["summaries"][self.video_ids[0]]["summary"], "Keep this.")

    def test_explicit_replace_and_membership_copy(self):
        """Require explicit replacement approval and copy list membership only."""
        store = self.app.config["STORE"]
        store.update(lambda archive: archive["summaries"].update({
            self.video_ids[0]: {"video_id": self.video_ids[0], "title": "Saved", "summary": "Old.", "topics": [], "chat": []},
        }))
        response = self.post_action(
            "summarize", source_key=self.source_key,
            video_ids=[self.video_ids[0]], replace_saved="yes",
        )
        job = self.wait_for_job(response)
        self.assertEqual(job["status"], "complete")
        results = self.client.get(f"/jobs/{job['id']}")
        self.assertIn(b"Showing 1 of 1 videos.", results.data)
        self.assertEqual(store.read()["summaries"][self.video_ids[0]]["summary"], "New fixture summary.")
        self.assertEqual(store.read()["summaries"][self.video_ids[0]]["topics"], ["Fixture"])
        self.post_action(
            "copy", source_key=self.source_key, video_ids=[self.video_ids[0]], target_list="list:target",
        )
        archive = store.read()
        self.assertEqual(archive["summary_lists"]["list:target"]["video_ids"], [self.video_ids[0]])
        self.assertEqual(archive["summaries"][self.video_ids[0]]["summary"], "New fixture summary.")

    def test_invalid_selection_and_unconfirmed_delete_are_rejected(self):
        """Reject foreign IDs, blank selection, and destructive work without consent."""
        self.assertEqual(self.post_action("summarize", entry_ids=[]).status_code, 400)
        self.assertEqual(self.post_action("summarize", source_key=self.source_key, video_ids=["foreign"]).status_code, 400)
        self.assertEqual(self.post_action(
            "delete_summaries", source_key=self.source_key, video_ids=[self.video_ids[0]],
        ).status_code, 400)

    def test_index_selection_controls_match_query_scope(self):
        """Allow Archive index select-all without a detail source key."""
        response = self.post_action("select_all", q="Fixture")
        self.assertEqual(response.status_code, 302)
        self.assertIn("selected_entry=matching", response.headers["Location"])
        self.assertIn("q=Fixture", response.headers["Location"])

    def test_reopen_empty_custom_list(self):
        """Opening an empty saved list does not require a selected video."""
        self.app.config["STORE"].update(lambda archive: archive["summary_lists"].update({
            "list:empty": {
                "id": "list:empty", "title": "Empty list", "kind": "custom",
                "source_key": "", "video_ids": [], "created_at": "", "updated_at": "",
            },
        }))
        response = self.post_action("reopen", entry_ids=["list:empty"])
        self.assertEqual(response.status_code, 302)
        self.assertIn("/archive/list:empty", response.headers["Location"])

    def test_overlapping_bulk_sources_deduplicate_without_phantom_sources(self):
        """Summarize overlapping entry selections once and keep their true links."""
        overlapping = fixture_source("playlist", "PLoverlap123")
        overlapping["videos"] = [
            {**fixture_source("playlist", "unused")["videos"][0]},
            {
                "id": "arc00000002", "title": "Archive fixture extra",
                "url": "https://www.youtube.com/watch?v=arc00000002",
                "published_at": "2024-01-02", "author": "Fixture", "topic": "Fixture",
            },
        ]
        save_inspected_source(self.app.config["STORE"], overlapping)
        second_key = overlapping["source_key"]
        response = self.post_action("summarize", entry_ids=[self.source_key, second_key])
        self.assertEqual(self.wait_for_job(response)["status"], "complete")
        self.assertEqual(self.calls, [[*self.video_ids, "arc00000002"]])
        archive = self.app.config["STORE"].read()
        self.assertEqual(set(archive["sources"]), {self.source_key, second_key})
        self.assertEqual(archive["summaries"][self.video_ids[0]]["source_keys"], [self.source_key])
        self.assertEqual(archive["summaries"]["arc00000002"]["source_keys"], [second_key])

    def test_move_and_confirmed_delete_update_memberships(self):
        """Move selected membership, then delete the canonical summary explicitly."""
        store = self.app.config["STORE"]
        store.update(lambda archive: archive["summaries"].update({
            video_id: {
                "video_id": video_id, "title": f"Saved {index}", "summary": "Saved text.",
                "topics": ["Fixture"], "chat": [], "source_keys": [self.source_key],
            }
            for index, video_id in enumerate(self.video_ids)
        }))
        self.post_action(
            "move", source_key=self.source_key, video_ids=[self.video_ids[0]], target_list="list:target",
        )
        archive = store.read()
        self.assertNotIn(self.video_ids[0], archive["summary_lists"][self.source_key]["video_ids"])
        self.assertEqual(archive["summary_lists"]["list:target"]["video_ids"], [self.video_ids[0]])
        deleted = self.post_action(
            "delete_summaries", source_key="list:target", video_ids=[self.video_ids[0]], confirm="yes",
        )
        self.assertEqual(deleted.status_code, 302)
        archive = store.read()
        self.assertNotIn(self.video_ids[0], archive["summaries"])
        self.assertEqual(archive["summary_lists"]["list:target"]["video_ids"], [])
        self.assertIn(self.video_ids[1], archive["summaries"])

    def test_delete_orphan_video_redirects_to_archive_index(self):
        """Deleting a single-video summary does not redirect to a removed detail."""
        video_id = "arc00000010"
        source_key = f"video:{video_id}"
        source = {
            "source_key": source_key, "kind": "video", "id": video_id,
            "title": "Single fixture", "videos": [{
                "id": video_id, "title": "Single fixture",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": "Unknown", "author": "Fixture", "topic": "Fixture",
            }],
        }
        store = self.app.config["STORE"]
        save_inspected_source(store, source)
        store.update(lambda archive: archive["summaries"].update({
            video_id: {
                "video_id": video_id, "title": "Single fixture", "summary": "Saved text.",
                "topics": ["Fixture"], "chat": [], "source_keys": [source_key],
            },
        }))
        response = self.client.post("/archive/actions", data={
            "csrf_token": self.csrf, "action": "delete_summaries", "source_key": source_key,
            "video_ids": [video_id], "confirm": "yes",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request.path, "/archive")

    def test_move_single_video_preserves_metadata_and_hides_duplicate(self):
        """Bulk and per-video moves keep source details and canonical summary."""
        store = self.app.config["STORE"]
        video_ids = ["arc00000011", "arc00000012"]
        for index, video_id in enumerate(video_ids):
            source_key = f"video:{video_id}"
            save_inspected_source(store, {
                "source_key": source_key, "kind": "video", "id": video_id,
                "title": f"Single metadata {index}", "archive_as_single": True,
                "videos": [{
                    "id": video_id, "title": f"Single metadata {index}",
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_at": "2024-05-06", "author": "Metadata author", "topic": "Metadata topic",
                }],
            })
            store.update(lambda archive: archive["summaries"].update({
                video_id: {
                    "video_id": video_id, "title": f"Single metadata {index}",
                    "summary": "Canonical summary.", "topics": ["Metadata topic"], "chat": [],
                    "source_keys": [source_key],
                },
            }))

        response = self.post_action(
            "move", source_key=f"video:{video_ids[0]}", video_ids=[video_ids[0]], target_list="list:target",
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(f"/archive/video:{video_ids[1]}/transfer", data={
            "csrf_token": self.csrf, "video_id": video_ids[1], "target_list": "list:target", "action": "move",
        })
        self.assertEqual(response.status_code, 302)
        archive = store.read()
        for video_id in video_ids:
            source = archive["sources"][f"video:{video_id}"]
            self.assertFalse(source["archive_as_single"])
            row = next(video for video in source["videos"] if video["id"] == video_id)
            self.assertEqual(row["author"], "Metadata author")
            self.assertEqual(row["published_at"], "2024-05-06")
            self.assertEqual(archive["summaries"][video_id]["summary"], "Canonical summary.")
            detail = next(video for video in archive_groups(archive, "")["custom"][0]["videos"] if video["id"] == video_id)
            self.assertEqual(detail["topic"], "Metadata topic")
        self.assertFalse(any(item.get("id") in video_ids for item in archive_groups(archive, "")["single"]))


if __name__ == "__main__":
    unittest.main()
