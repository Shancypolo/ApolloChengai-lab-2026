"""Offline contracts for inline retry actions and cross-page selection."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from app import create_app


def source_with_many_videos(kind: str, source_id: str) -> dict:
    """Create a 50-title playlist fixture that crosses one page boundary."""
    videos = [
        {
            "id": f"vid{i:08d}", "title": f"Fixture lecture {i:02d}",
            "url": f"https://www.youtube.com/watch?v=vid{i:08d}",
            "published_at": f"2024-01-{(i % 28) + 1:02d}", "author": f"Author {i % 3}",
            "topic": "Fixture",
        }
        for i in range(50)
    ]
    return {
        "source_key": f"{kind}:{source_id}", "kind": kind, "id": source_id,
        "title": "Fixture playlist", "url": "https://www.youtube.com/playlist?list=PLfixture123",
        "videos": videos, "omitted_video_entries": 0,
    }


class InlineActionContracts(unittest.TestCase):
    """Check offline retry, job ownership, and pagination state contracts."""

    def setUp(self):
        """Create a temporary archive and deterministic fake service providers."""
        self.directory = tempfile.TemporaryDirectory(prefix="pageone-inline-")

        def topics(titles, usage_callback=None):
            return ["Fixture"] * len(titles)

        self.app = create_app(
            self.directory.name,
            source_fetcher=source_with_many_videos,
            transcript_fetcher=lambda video_id: f"Transcript for {video_id}",
            topic_function=topics,
            batch_summary_function=lambda videos, preferences, usage_callback=None: {
                item["video_id"]: {"summary": "Recovered fixture summary."} for item in videos
            },
            chat_function=lambda *args, **kwargs: "Fixture answer.",
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.csrf = session["csrf_token"]
            self.session_id = session["usage_session_id"]

    def tearDown(self):
        """Remove the per-test archive directory."""
        self.directory.cleanup()

    def wait_for_job(self, job_id):
        """Wait briefly for a fake background task to reach a terminal state."""
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = self.app.config["JOBS"].get(job_id)
            if job["status"] in {"complete", "partial", "error"}:
                return job
            time.sleep(0.01)
        self.fail("Background job did not finish.")

    def test_selection_survives_pagination_and_is_submitted_as_one_batch(self):
        """Carry selected IDs from the first page into one summary batch."""
        inspected = self.client.post("/inspect", data={
            "csrf_token": self.csrf,
            "source_url": "https://www.youtube.com/playlist?list=PLfixture123",
        })
        self.assertEqual(inspected.status_code, 200)
        job_id = next(iter(self.app.config["JOBS"]._jobs))
        self.wait_for_job(job_id)
        source_key = "playlist:PLfixture123"

        page_two = self.client.post(f"/sources/{source_key}", data={
            "csrf_token": self.csrf, "page": "1", "page_choice": "2",
            "video_ids": ["vid00000000", "vid00000048"],
        })
        self.assertIn(b"2 selected", page_two.data)
        self.assertIn(b'name="video_ids" value="vid00000000"', page_two.data)
        self.assertIn(b'value="vid00000048" checked', page_two.data)

        previous_jobs = set(self.app.config["JOBS"]._jobs)
        submitted = self.client.post(f"/sources/{source_key}", data={
            "csrf_token": self.csrf, "page": "2", "list_action": "summarize",
            "video_ids": ["vid00000000", "vid00000048"],
        })
        self.assertEqual(submitted.status_code, 200)
        summary_job_id = (set(self.app.config["JOBS"]._jobs) - previous_jobs).pop()
        job = self.wait_for_job(summary_job_id)
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["total"], 2)
        saved = self.app.config["STORE"].read()["summaries"]
        self.assertIn("vid00000000", saved)
        self.assertIn("vid00000048", saved)

    def test_failed_video_retry_recovers_and_job_is_session_scoped(self):
        """Retry one failed title and reject reads of its job from another session."""
        self.app.config["SOURCE_FETCHER"] = lambda kind, source_id: source_with_many_videos(kind, source_id)
        self.client.post("/inspect", data={
            "csrf_token": self.csrf,
            "source_url": "https://www.youtube.com/playlist?list=PLfixture123",
        })
        inspection_id = max(self.app.config["JOBS"]._jobs)
        self.wait_for_job(inspection_id)
        source_key = "playlist:PLfixture123"

        def fails(videos, preferences, usage_callback=None):
            raise RuntimeError("synthetic provider outage")

        self.app.config["BATCH_SUMMARY_FUNCTION"] = fails
        previous_jobs = set(self.app.config["JOBS"]._jobs)
        first = self.client.post(f"/sources/{source_key}", data={
            "csrf_token": self.csrf, "list_action": "summarize", "video_ids": ["vid00000000"],
        })
        self.assertEqual(first.status_code, 200)
        first_job_id = (set(self.app.config["JOBS"]._jobs) - previous_jobs).pop()
        failed_job = self.wait_for_job(first_job_id)
        self.assertEqual(failed_job["status"], "partial")
        failed_result = self.client.get(f"/jobs/{first_job_id}")
        self.assertIn(b"Try again", failed_result.data)
        self.assertIn(b"csrf_token", failed_result.data)

        other_client = self.app.test_client()
        other_client.get("/")
        self.assertEqual(other_client.get(f"/jobs/{first_job_id}").status_code, 403)

        self.app.config["BATCH_SUMMARY_FUNCTION"] = lambda videos, preferences, usage_callback=None: {
            item["video_id"]: {"summary": "Recovered fixture summary."} for item in videos
        }
        previous_jobs = set(self.app.config["JOBS"]._jobs)
        retried = self.client.post(f"/retry-video/{source_key}/vid00000000", data={"csrf_token": self.csrf})
        self.assertEqual(retried.status_code, 200)
        retry_job_id = (set(self.app.config["JOBS"]._jobs) - previous_jobs).pop()
        self.assertEqual(self.app.config["JOBS"].get(retry_job_id)["retry_video"], "vid00000000")
        retry_job = self.wait_for_job(retry_job_id)
        self.assertEqual(retry_job["status"], "complete")
        result = self.client.get(f"/jobs/{retry_job_id}")
        self.assertIn(b"Recovered fixture summary", result.data)
        self.assertNotIn(b"Try again", result.data)
        self.assertEqual(
            self.app.config["STORE"].read()["summaries"]["vid00000000"]["summary"],
            "Recovered fixture summary.",
        )


if __name__ == "__main__":
    unittest.main()
