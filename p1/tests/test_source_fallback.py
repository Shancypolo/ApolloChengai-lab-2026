"""Offline checks for public YouTube source fallbacks."""

from __future__ import annotations

import sys
import types
import unittest
from datetime import date
from unittest.mock import patch

from youtube_source import (
    SourceError,
    fetch_english_transcript,
    fetch_source,
    parse_youtube_url,
)


VIDEO_ID = "GmBG-26_Izw"
PLAYLIST_ID = "PLabcdefghij123456"


class SourceFallbackTests(unittest.TestCase):
    """Exercise pytubefix fallback with fake provider objects only."""

    def test_video_listing_falls_back_when_yt_dlp_raises(self):
        """Use pytubefix metadata after a primary extraction failure."""
        class FakeVideo:
            """Expose only the pytubefix metadata properties used by PageOne."""

            video_id = VIDEO_ID
            title = "Fallback title"
            author = "Fallback author"
            publish_date = date(2024, 2, 3)

        module = types.ModuleType("pytubefix")
        module.YouTube = lambda url: FakeVideo()
        with patch("youtube_source._youtube_dl", side_effect=RuntimeError("private provider detail")), \
                patch.dict(sys.modules, {"pytubefix": module}):
            result = fetch_source("video", VIDEO_ID)
        self.assertEqual(result["title"], "Fallback title")
        self.assertEqual(result["videos"][0]["published_at"], "2024-02-03")
        self.assertEqual(result["url"], f"https://www.youtube.com/watch?v={VIDEO_ID}")

    def test_video_fallback_rejects_a_different_returned_id(self):
        """Keep the fallback source ID aligned with the requested video."""
        class WrongVideo:
            """Expose a mismatched pytubefix video ID."""

            video_id = "abcdefghijk"
            title = "Wrong video"
            author = "Channel"
            publish_date = None

        module = types.ModuleType("pytubefix")
        module.YouTube = lambda url: WrongVideo()
        with patch("youtube_source._youtube_dl", side_effect=RuntimeError("offline")), \
                patch.dict(sys.modules, {"pytubefix": module}):
            with self.assertRaisesRegex(SourceError, "could not return that public video"):
                fetch_source("video", VIDEO_ID)

    def test_playlist_listing_falls_back_when_primary_entries_are_unusable(self):
        """Use the public Playlist.videos interface when yt-dlp has no entries."""
        class FakeVideo:
            """Stand in for one pytubefix YouTube item."""

            video_id = VIDEO_ID
            title = "Playlist item"
            author = "Channel"
            publish_date = None

        class FakePlaylist:
            """Stand in for a public pytubefix Playlist."""

            title = "Fallback playlist"
            videos = [FakeVideo()]

        module = types.ModuleType("pytubefix")
        module.Playlist = lambda url: FakePlaylist()

        class FakeDownloader:
            """Return an unusable but non-error primary response."""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, url, download=False):
                return {"entries": []}

        with patch("youtube_source._youtube_dl", return_value=FakeDownloader()), \
                patch.dict(sys.modules, {"pytubefix": module}):
            result = fetch_source("playlist", PLAYLIST_ID)
        self.assertEqual(result["title"], "Fallback playlist")
        self.assertEqual([item["id"] for item in result["videos"]], [VIDEO_ID])
        self.assertEqual(result["omitted_video_entries"], 0)

    def test_caption_fallback_uses_english_track_only(self):
        """Use English captions after yt-dlp leaves no JSON3 file."""
        class FakeCaption:
            """Expose the documented text caption generator."""

            def generate_txt_captions(self):
                return "  English transcript.  "

        class FakeCaptionQuery:
            """Provide English and automatic English caption keys."""

            def get(self, language):
                return FakeCaption() if language == "en" else None

        class FakeVideo:
            """Expose the pytubefix captions property."""

            captions = FakeCaptionQuery()

        module = types.ModuleType("pytubefix")
        module.YouTube = lambda url: FakeVideo()

        class FakeDownloader:
            """Behave like yt-dlp but produce no subtitle output."""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def download(self, urls):
                return 0

        with patch("youtube_source._youtube_dl", return_value=FakeDownloader()), \
                patch.dict(sys.modules, {"pytubefix": module}):
            transcript = fetch_english_transcript(VIDEO_ID)
        self.assertEqual(transcript, "English transcript.")

    def test_caption_fallback_accepts_regional_and_automatic_english(self):
        """Select regional English before an available automatic variant."""
        class FakeCaption:
            """Return text identifying the selected track."""

            def __init__(self, text):
                self.text = text

            def generate_txt_captions(self):
                return self.text

        class FakeCaptionQuery:
            """Expose only automatic British English in this sample."""

            def get(self, language):
                return FakeCaption("Automatic English") if language == "a.en-GB" else None

        class FakeVideo:
            """Expose the fake caption query."""

            captions = FakeCaptionQuery()

        module = types.ModuleType("pytubefix")
        module.YouTube = lambda url: FakeVideo()
        with patch("youtube_source._youtube_dl", side_effect=RuntimeError("offline")), \
                patch.dict(sys.modules, {"pytubefix": module}):
            transcript = fetch_english_transcript(VIDEO_ID)
        self.assertEqual(transcript, "Automatic English")

    def test_caption_fallback_selects_unlisted_english_region(self):
        """Find an English regional track by its language code prefix."""
        class FakeCaption:
            """Represent a caption track and its public language code."""

            code = "en-CA"

            def generate_txt_captions(self):
                return "Canadian English"

        class FakeCaptionQuery:
            """Expose the regional code through CaptionQuery iteration."""

            def __iter__(self):
                return iter([FakeCaption()])

            def get(self, language):
                return FakeCaption() if language == "en-CA" else None

        class FakeVideo:
            """Expose the fake regional caption query."""

            captions = FakeCaptionQuery()

        module = types.ModuleType("pytubefix")
        module.YouTube = lambda url: FakeVideo()
        with patch("youtube_source._youtube_dl", side_effect=RuntimeError("offline")), \
                patch.dict(sys.modules, {"pytubefix": module}):
            transcript = fetch_english_transcript(VIDEO_ID)
        self.assertEqual(transcript, "Canadian English")

    def test_fallback_failure_hides_provider_message(self):
        """Keep provider details out of safe source errors and logs."""
        module = types.ModuleType("pytubefix")

        def fail_video(url):
            """Raise a fake provider error containing private text."""
            raise RuntimeError("private provider detail")

        module.YouTube = fail_video
        with patch("youtube_source._youtube_dl", side_effect=RuntimeError("private provider detail")), \
                patch.dict(sys.modules, {"pytubefix": module}), self.assertLogs("pageone", level="WARNING") as logs:
            with self.assertRaisesRegex(SourceError, "could not return that public video"):
                fetch_source("video", VIDEO_ID)
        self.assertTrue(any("fallback" in message for message in logs.output))
        self.assertTrue(all("private provider detail" not in message for message in logs.output))
        self.assertTrue(all("RuntimeError" in message for message in logs.output))

    def test_url_allowlists_are_preserved(self):
        """Keep the existing HTTPS and host checks ahead of either provider."""
        self.assertEqual(parse_youtube_url(f"https://youtu.be/{VIDEO_ID}")["video_id"], VIDEO_ID)
        with self.assertRaises(SourceError):
            parse_youtube_url(f"http://youtube.com/watch?v={VIDEO_ID}")
        with self.assertRaises(SourceError):
            parse_youtube_url(f"https://youtube.com.evil.test/watch?v={VIDEO_ID}")


if __name__ == "__main__":
    unittest.main()
