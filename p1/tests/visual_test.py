"""Run local Chromium layout checks with Python fake services only."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server


APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from app import create_app


def visual_source(kind: str, source_id: str) -> dict:
    """Return three fixture titles with dates and authors for browser checks."""
    rows = [
        ("GmBG-26_Izw", "The first question: how evidence changes", "2023-04-12", "A. Author"),
        ("aBcdEF_1234", "A long view of research and careful uncertainty", "2024-08-09", "B. Editor"),
        ("bCdeFG_2345", "Video 3", "Unknown", "Unknown"),
    ]
    videos = [
        {
            "id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": published_at,
            "author": author,
            "topic": "Other",
        }
        for video_id, title, published_at, author in rows
    ]
    return {
        "source_key": f"{kind}:{source_id}",
        "kind": kind,
        "id": source_id,
        "title": "Lectures on evidence and uncertainty",
        "url": "https://www.youtube.com/playlist?list=PLVANSOs5ny50",
        "videos": videos,
        "omitted_video_entries": 0,
    }


def assert_no_horizontal_overflow(page, width: int, height: int) -> None:
    """Check visible page boxes remain within a resized browser viewport."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(80)
    for element in page.locator("body *").all():
        bounds = element.bounding_box()
        if bounds and (bounds["x"] < -1 or bounds["x"] + bounds["width"] > width + 2):
            raise AssertionError(f"Horizontal overflow at {width}x{height}: {element.get_attribute('class')} {bounds}.")


def assert_no_embedded_scripts_or_aria(page) -> None:
    """Confirm rendered pages include no scripts or explicit ARIA markup."""
    assert page.locator("script").count() == 0
    page_markup = page.content()
    assert re.search(r"\saria-[a-z][\w-]*\s*=", page_markup, re.IGNORECASE) is None
    assert re.search(r"\srole\s*=", page_markup, re.IGNORECASE) is None


def main() -> None:
    """Launch an isolated fake app and check interactions and extreme widths."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit("Install requirements-dev.txt to run browser checks.") from error

    def transcript_fetcher(video_id: str) -> str:
        """Return temporary captions without contacting a remote service."""
        return f"A transcript about evidence for video {video_id}."

    def topic_function(titles: list[str], usage_callback=None) -> list[str]:
        """Classify fixture titles without receiving any transcript text."""
        return ["Evidence", "Research", "Other"][:len(titles)]

    def summary_function(title: str, transcript: str, preferences: str, usage_callback=None) -> dict:
        """Return stable summary prose without calling an AI provider."""
        return {"summary": f"{title} presents a careful claim and supporting evidence."}

    def chat_function(title: str, transcript: str, summary: str, question: str, history: list, usage_callback=None) -> str:
        """Answer a fixture follow-up without calling a remote model."""
        return "The example presents the conclusion as tentative."

    temporary_directory = tempfile.TemporaryDirectory(prefix="pageone-visual-")
    app = create_app(
        temporary_directory.name,
        source_fetcher=visual_source,
        transcript_fetcher=transcript_fetcher,
        topic_function=topic_function,
        summary_function=summary_function,
        chat_function=chat_function,
    )
    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    screenshots_directory = Path(os.environ.get("PAGEONE_SCREENSHOT_DIR", "/tmp/pageone-visual"))
    screenshots_directory.mkdir(parents=True, exist_ok=True)
    browser_path = os.environ.get("PAGEONE_CHROMIUM_PATH") or shutil.which("chromium")

    try:
        with sync_playwright() as playwright:
            launch_options = {"headless": True}
            if browser_path:
                launch_options["executable_path"] = browser_path
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page(viewport={"width": 1365, "height": 768})
            base_url = f"http://127.0.0.1:{server.server_port}"
            page.goto(base_url, wait_until="networkidle")
            assert_no_embedded_scripts_or_aria(page)
            page.screenshot(path=str(screenshots_directory / "home-wide.png"), full_page=True)
            page.locator('.sidebar-nav a[href="/archive"]').click()
            page.get_by_text("Nothing saved yet").wait_for()
            page.screenshot(path=str(screenshots_directory / "archive-empty-wide.png"), full_page=True)
            page.locator('.sidebar-nav a[href="/settings"]').click()
            page.screenshot(path=str(screenshots_directory / "settings-wide.png"), full_page=True)
            page.locator('.sidebar-nav a[href="/"]').click()
            for width, height in ((280, 940), (320, 940), (430, 1100), (844, 390), (1365, 768), (3440, 1100)):
                assert_no_horizontal_overflow(page, width, height)
                if width in (280, 3440):
                    page.screenshot(path=str(screenshots_directory / f"home-{width}.png"), full_page=True)

            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=PLVANSOs5ny50")
            page.locator(".search-form button[type=submit]").click()
            page.locator(".video-row").first.wait_for(timeout=15_000)
            page.locator("h2").filter(has_text="Lectures on evidence and uncertainty").wait_for()
            assert page.locator(".video-row").count() == 3
            assert_no_embedded_scripts_or_aria(page)
            page.screenshot(path=str(screenshots_directory / "results-wide.png"), full_page=True)
            for width, height in ((280, 940), (320, 940), (430, 1100), (844, 390), (1365, 768), (3440, 1100)):
                assert_no_horizontal_overflow(page, width, height)
                if width in (280, 3440):
                    page.screenshot(path=str(screenshots_directory / f"results-{width}.png"), full_page=True)

            page.locator("select[name=sort_by]").select_option("author")
            page.locator("button[name=list_action][value=sort]").click()
            titles = page.locator(".video-title").all_text_contents()
            assert titles[0].startswith("The first question") and titles[1].startswith("A long view")
            page.locator("input[name=filter_text]").fill("record")
            page.locator("button[name=list_action][value=filter]").click()
            assert page.locator(".video-row").count() == 0
            page.locator("input[name=filter_text]").fill("")
            page.locator("button[name=list_action][value=filter]").click()
            page.locator("button[name=list_action][value=select_none]").click()
            assert page.locator('input[name="video_ids"]:checked').count() == 0
            page.locator("button[name=list_action][value=select_all]").click()
            assert page.locator('input[name="video_ids"]:checked').count() == 3
            page.locator("button[name=list_action][value=select_all]").click()
            assert page.locator('input[name="video_ids"]:checked').count() == 3
            page.locator("button[name=list_action][value=summarize]").click()
            page.get_by_text("BATCH COMPLETE", exact=True).wait_for(timeout=15_000)
            page.locator(".summary-prose").first.wait_for()
            assert page.locator(".summary-card").count() == 3
            assert page.locator(".summary-card[open]").count() == 1

            page.locator("#summary-filter").fill("Video 3")
            page.locator(".summary-filter button").click()
            assert page.locator(".summary-card").count() == 1
            assert page.locator(".summary-title").inner_text() == "Video 3"
            page.locator("#summary-filter").fill("no matching title")
            page.locator(".summary-filter button").click()
            assert page.locator(".summary-card").count() == 0
            page.get_by_text("No video summaries match this search.").wait_for()
            page.locator(".summary-filter a").click()
            assert page.locator(".summary-card").count() == 3

            page.locator('.chat-form input[name="question"]').first.fill("How certain is that conclusion?")
            page.locator(".chat-form button[type=submit]").first.click()
            page.get_by_text("The example presents the conclusion as tentative.").wait_for(timeout=10_000)
            assert page.locator(".chat-turn").count() == 1
            assert_no_embedded_scripts_or_aria(page)

            page.set_viewport_size({"width": 320, "height": 940})
            page.locator(".sidebar-toggle summary").click()
            assert page.locator(".sidebar-toggle[open]").count() == 1
            page.locator('.sidebar-nav a[href="/archive"]').click()
            page.locator("h1").filter(has_text="Archive").wait_for()
            assert page.get_by_text("Lectures on evidence and uncertainty").count() >= 1
            page.screenshot(path=str(screenshots_directory / "archive-mobile.png"), full_page=True)
            page.locator("#archive-search").fill("no matching source")
            page.locator(".archive-search button").click()
            page.get_by_text("Nothing saved yet").wait_for()
            page.locator("#archive-search").fill("")
            page.locator(".archive-search button").click()
            page.locator("#archive-search").fill("first question")
            page.locator(".archive-search button").click()
            assert page.locator(".archive-row").count() == 1
            page.locator("#archive-search").fill("")
            page.locator(".archive-search button").click()
            page.locator(".archive-row").first.click()
            page.locator(".summary-prose").first.wait_for()
            page.get_by_text("How certain is that conclusion?").wait_for()
            page.locator("#archive-filter").fill("Video 3")
            page.locator(".summary-filter button").click()
            assert page.locator(".archive-summary").count() == 1
            page.locator(".summary-filter a").click()
            assert page.locator(".archive-summary").count() == 3
            page.screenshot(path=str(screenshots_directory / "archive-detail-mobile.png"), full_page=True)
            assert_no_horizontal_overflow(page, 320, 940)
            page.locator(".sidebar-toggle summary").click()
            page.locator('.sidebar-nav a[href="/settings"]').click()
            page.locator("h1").filter(has_text="Settings").wait_for()
            page.locator("#summary-preferences").fill("Keep uncertainty visible.")
            page.locator("button[type=submit]").click()
            page.locator('.settings-feedback[title="Summary preferences saved."]').wait_for()
            page.screenshot(path=str(screenshots_directory / "settings-mobile.png"), full_page=True)
            assert_no_horizontal_overflow(page, 320, 940)
            browser.close()
        print(f"Browser checks passed. Screenshots: {screenshots_directory}")
    finally:
        server.shutdown()
        server_thread.join(timeout=3)
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()
