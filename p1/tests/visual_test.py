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
    if kind == "video":
        videos = [video for video in videos if video["id"] == source_id]
    return {
        "source_key": f"{kind}:{source_id}",
        "kind": kind,
        "id": source_id,
        "title": "Lectures on evidence and uncertainty" if kind == "playlist" else videos[0]["title"],
        "url": "https://www.youtube.com/playlist?list=PLVANSOs5ny50" if kind == "playlist" else videos[0]["url"],
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


def assert_visual_script_and_no_aria(page) -> None:
    """Confirm only the reading-position helper loads and markup has no ARIA."""
    scripts = page.locator("script")
    assert scripts.count() == 1
    assert scripts.first.get_attribute("src").endswith("/static/js/reading_position.js")
    assert page.locator("script:not([src])").count() == 0
    page_markup = page.content()
    assert re.search(r"\saria-[a-z][\w-]*\s*=", page_markup, re.IGNORECASE) is None
    assert re.search(r"\srole\s*=", page_markup, re.IGNORECASE) is None


def assert_single_surface(page) -> None:
    """Reject visible images, sidebars, and floating notice windows."""
    assert page.locator("img, .sidebar, dialog, .failure-shade").count() == 0


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

    def batch_summary_function(videos: list[dict], preferences: str, usage_callback=None) -> dict:
        """Return all fixture summaries without calling an AI provider."""
        return {
            video["video_id"]: {"summary": f"{video['video_title']} presents a careful claim and supporting evidence."}
            for video in videos
        }

    def chat_function(title: str, transcript: str, summary: str, question: str, history: list, usage_callback=None) -> str:
        """Hold the fixture answer briefly so loading visuals can be inspected."""
        threading.Event().wait(1.5)
        return "The example presents the conclusion as tentative."

    temporary_directory = tempfile.TemporaryDirectory(prefix="pageone-visual-")
    app = create_app(
        temporary_directory.name,
        source_fetcher=visual_source,
        transcript_fetcher=transcript_fetcher,
        topic_function=topic_function,
        batch_summary_function=batch_summary_function,
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
            browser_errors = []
            page.on("pageerror", lambda error: browser_errors.append(str(error)))
            page.on("console", lambda message: browser_errors.append(message.text) if message.type == "error" else None)
            base_url = f"http://127.0.0.1:{server.server_port}"
            page.goto(base_url, wait_until="networkidle")
            assert page.url == base_url + "/"
            assert page.title() == "PageOne"
            assert_visual_script_and_no_aria(page)
            assert_single_surface(page)
            page.screenshot(path=str(screenshots_directory / "home-wide.png"), full_page=True)
            page.locator("#source-url").fill("https://example.com/watch?v=GmBG-26_Izw")
            page.locator(".search-form button").click()
            page.locator(".failure-notice").wait_for()
            assert_single_surface(page)
            page.screenshot(path=str(screenshots_directory / "error-notice-wide.png"), full_page=True)
            page.locator(".failure-notice a").click()
            page.locator('.site-nav a[href="/archive"]').click()
            page.get_by_text("Nothing saved yet").wait_for()
            assert_single_surface(page)
            page.screenshot(path=str(screenshots_directory / "archive-empty-wide.png"), full_page=True)
            page.locator('.site-nav a[href="/settings"]').click()
            assert_single_surface(page)
            page.screenshot(path=str(screenshots_directory / "settings-wide.png"), full_page=True)
            page.locator('.site-nav a[href="/"]').click()
            for width, height in ((280, 940), (320, 940), (430, 1100), (844, 390), (1365, 768), (1600, 1000), (3440, 1100)):
                assert_no_horizontal_overflow(page, width, height)
                if width in (280, 1600, 3440):
                    page.screenshot(path=str(screenshots_directory / f"home-{width}.png"), full_page=True)

            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=PLVANSOs5ny50")
            page.locator(".search-form button[type=submit]").click()
            page.locator(".video-row").first.wait_for(timeout=15_000)
            page.locator("h2").filter(has_text="Lectures on evidence and uncertainty").wait_for()
            assert page.locator(".video-row").count() == 3
            assert_visual_script_and_no_aria(page)
            assert_single_surface(page)
            page.screenshot(path=str(screenshots_directory / "results-wide.png"), full_page=True)
            for width, height in ((280, 940), (320, 940), (430, 1100), (844, 390), (1365, 768), (1600, 1000), (3440, 1100)):
                assert_no_horizontal_overflow(page, width, height)
                if width in (280, 1600, 3440):
                    page.screenshot(path=str(screenshots_directory / f"results-{width}.png"), full_page=True)

            page.locator("button[name=sort_choice][value=author]").click()
            titles = page.locator(".video-title").all_text_contents()
            assert titles[0].startswith("The first question") and titles[1].startswith("A long view")
            assert page.locator(".sort-choice.is-current").inner_text() == "Author"
            assert page.locator(".video-check input").first.bounding_box()["width"] == 66
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
            page.locator(".summary-prose").first.wait_for(state="attached")
            assert page.locator(".summary-card").count() == 3
            assert page.locator(".summary-card[open]").count() == 0
            assert_visual_script_and_no_aria(page)

            # Open a low card after scrolling it into view and ensure its heading
            # stays at the same viewport position while the details expand.
            stable_heading = page.locator(".summary-card").nth(2).locator("summary")
            stable_heading.scroll_into_view_if_needed()
            before_top = stable_heading.bounding_box()["y"]
            stable_heading.click()
            page.wait_for_timeout(80)
            after_top = stable_heading.bounding_box()["y"]
            assert abs(after_top - before_top) <= 2, (before_top, after_top)
            assert page.locator(".summary-card[open]").count() == 1
            stable_heading.click()
            assert page.locator(".summary-card[open]").count() == 0

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

            # Test the progress page's active CSS animation while a fake answer
            # is held in the background, then release it by waiting for completion.
            page.locator(".summary-card").first.locator("summary").click()
            page.locator('.chat-form input[name="question"]').first.fill("How certain is that conclusion?")
            page.locator(".chat-form button[type=submit]").first.click()
            page.get_by_text("Answering your question.").wait_for(timeout=5_000)
            assert page.locator('meta[http-equiv="refresh"]').count() == 1
            animation_name = page.locator(".progress-page").evaluate("el => getComputedStyle(el, '::after').animationName")
            animation_duration = page.locator(".progress-page").evaluate("el => getComputedStyle(el, '::after').animationDuration")
            assert animation_name == "reading-line"
            assert animation_duration == "1.8s"
            page.screenshot(path=str(screenshots_directory / "chat-loading.png"), full_page=True)
            page.get_by_text("The example presents the conclusion as tentative.").wait_for(timeout=10_000)
            assert page.locator(".chat-turn").count() == 1
            assert_visual_script_and_no_aria(page)

            page.set_viewport_size({"width": 320, "height": 940})
            assert page.locator(".sidebar").count() == 0
            page.locator('.site-nav a[href="/archive"]').click()
            page.locator("h1").filter(has_text="Archive").wait_for()
            assert "pageone.json" in page.locator(".file-caption").inner_text()
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
            page.locator(".archive-summary").first.locator("summary").click()
            page.locator(".summary-prose").first.wait_for()
            page.get_by_text("How certain is that conclusion?").wait_for()
            page.locator("#archive-filter").fill("Video 3")
            page.locator(".summary-filter button").click()
            assert page.locator(".archive-summary").count() == 1
            page.locator(".summary-filter a").click()
            assert page.locator(".archive-summary").count() == 3
            page.screenshot(path=str(screenshots_directory / "archive-detail-mobile.png"), full_page=True)
            assert_no_horizontal_overflow(page, 320, 940)
            page.locator('.site-nav a[href="/settings"]').click()
            page.locator("h1").filter(has_text="Settings").wait_for()
            assert "pageone.log" in page.locator(".file-caption").inner_text()
            initial_font_size = float(page.locator("body").evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
            page.locator('select[name="interface_scale"]').select_option("extra_large")
            page.locator("button[type=submit]").click()
            page.locator("body.scale-extra_large").wait_for()
            large_font_size = float(page.locator("body").evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
            assert large_font_size > initial_font_size
            page.locator('select[name="interface_scale"]').select_option("compact")
            page.locator("button[type=submit]").click()
            page.locator("body.scale-compact").wait_for()
            compact_font_size = float(page.locator("body").evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
            assert compact_font_size < initial_font_size
            page.locator("#summary-preferences").fill("Keep uncertainty visible.")
            page.locator("button[type=submit]").click()
            page.locator('.settings-feedback[title="Summary preferences saved."]').wait_for()
            page.screenshot(path=str(screenshots_directory / "settings-mobile.png"), full_page=True)
            assert_no_horizontal_overflow(page, 320, 940)
            page.set_viewport_size({"width": 3440, "height": 1100})
            page.screenshot(path=str(screenshots_directory / "settings-ultrawide.png"), full_page=True)
            assert_no_horizontal_overflow(page, 3440, 1100)
            page.locator('.site-nav a[href="/archive"]').click()
            page.screenshot(path=str(screenshots_directory / "archive-ultrawide.png"), full_page=True)
            page.set_viewport_size({"width": 1600, "height": 1000})
            page.screenshot(path=str(screenshots_directory / "archive-1600.png"), full_page=True)
            page.locator(".archive-row").first.click()
            page.screenshot(path=str(screenshots_directory / "archive-detail-ultrawide.png"), full_page=True)
            assert_no_horizontal_overflow(page, 3440, 1100)
            page.set_viewport_size({"width": 320, "height": 940})
            page.locator('.site-nav a[href="/archive"]').click()
            page.locator('.create-list-form input[name="title"]').fill("Reading desk")
            page.locator('.create-list-form button').click()
            custom_list_id = page.url.rsplit("/", 1)[-1]
            page.get_by_text("Reading desk").wait_for()
            page.locator('.site-nav a[href="/"]').click()
            page.locator('#target-list').select_option(custom_list_id)
            page.locator('#source-url').fill("https://www.youtube.com/watch?v=aBcdEF_1234")
            page.locator('.search-form button').click()
            page.locator('.video-row').first.wait_for(timeout=15_000)
            page.locator('.site-nav a[href="/archive"]').click()
            page.locator('.archive-row').filter(has_text="Reading desk").click()
            page.locator('.summary-title').filter(has_text="A long view of research and careful uncertainty").wait_for()
            assert page.locator('.archive-summary').count() == 1
            page.screenshot(path=str(screenshots_directory / "custom-list-mobile.png"), full_page=True)
            assert_no_horizontal_overflow(page, 320, 940)
            page.locator('.delete-list-form input[name="confirm"]').check()
            page.locator('.delete-list-form button').click()
            page.get_by_text("Reading desk").wait_for(state="detached")

            def offline_topic_function(titles: list[str], usage_callback=None) -> list[str]:
                """Simulate an API connection failure without using the network."""
                raise ConnectionError("synthetic offline service")

            app.config["TOPIC_FUNCTION"] = offline_topic_function
            page.locator('.site-nav a[href="/"]').click()
            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=PLVANSOs5ny50")
            page.locator(".search-form button").click()
            page.locator(".failure-notice").wait_for(timeout=15_000)
            assert "Connection unavailable" in page.locator(".failure-notice").inner_text()
            page.screenshot(path=str(screenshots_directory / "offline-api-notice-mobile.png"), full_page=True)
            assert "ConnectionError" in (Path(temporary_directory.name) / "pageone.log").read_text(encoding="utf-8")
            assert browser_errors == [], browser_errors
            browser.close()
        print(f"Browser checks passed. Screenshots: {screenshots_directory}")
    finally:
        server.shutdown()
        server_thread.join(timeout=3)
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()
