"""Browser smoke tests for inline actions, retry panels, and responsive layout."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from app import create_app
from usage_accounting import usage_from_response


def fixture_source(kind: str, source_id: str) -> dict:
    """Return a small playlist with varied titles and authors for browser checks."""
    titles = [
        ("GmBG-26_Izw", "Evidence and careful reasoning", "2023-04-12", "A. Author"),
        ("aBcdEF_1234", "Methods for research", "2024-08-09", "B. Editor"),
        ("bCdeFG_2345", "A field guide to evidence", "2025-03-11", "C. Author"),
    ]
    videos = [
        {
            "id": video_id, "title": title, "url": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": published_at, "author": author, "topic": "Fixture",
        }
        for video_id, title, published_at, author in titles
    ]
    return {
        "source_key": f"{kind}:{source_id}", "kind": kind, "id": source_id,
        "title": "Fixture playlist", "url": "https://www.youtube.com/playlist?list=PLfixture123",
        "videos": videos, "omitted_video_entries": 0,
    }


def assert_no_horizontal_overflow(page, width: int, height: int) -> None:
    """Resize the page and fail if a visible element escapes the viewport."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(100)
    overflow = page.evaluate("""() => [...document.querySelectorAll('body *')].map(el => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return {tag: el.tagName, className: el.className, left: r.left, right: r.right,
        width: r.width, display: s.display, visibility: s.visibility};
    }).filter(r => r.display !== 'none' && r.visibility !== 'hidden' && r.width > 0 &&
      (r.left < -1 || r.right > innerWidth + 2))""")
    assert not overflow, f"Horizontal overflow at {width}px: {overflow[:5]}"


def main() -> None:
    """Run Chromium interactions against a local app with fake providers."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit("Install requirements-dev.txt before running the browser smoke test.") from error

    chat_calls = {"count": 0}
    fixture_usage = usage_from_response({"usage": {
        "input_tokens": 120, "output_tokens": 24, "total_tokens": 144,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }})

    def chat_function(title, transcript, summary, question, history, usage_callback=None):
        chat_calls["count"] += 1
        if chat_calls["count"] == 1:
            raise RuntimeError("synthetic one-time answer failure")
        if usage_callback:
            usage_callback(fixture_usage)
        return "Recovered answer from the fixture provider."

    def batch_summary(videos, preferences, usage_callback=None):
        if usage_callback:
            usage_callback(fixture_usage)
        return {
            video["video_id"]: {"summary": f"Summary for {video['video_title']}."} for video in videos
        }

    app_directory = tempfile.TemporaryDirectory(prefix="pageone-inline-browser-")
    app = create_app(
        app_directory.name,
        source_fetcher=fixture_source,
        transcript_fetcher=lambda video_id: f"Fixture transcript for {video_id}.",
        topic_function=lambda titles, usage_callback=None: ["Evidence"] * len(titles),
        batch_summary_function=batch_summary,
        chat_function=chat_function,
    )
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    screenshot_directory = Path(os.environ.get("PAGEONE_SCREENSHOT_DIR", "/tmp/pageone-inline-browser"))
    screenshot_directory.mkdir(parents=True, exist_ok=True)
    browser_path = os.environ.get("PAGEONE_CHROMIUM_PATH") or shutil.which("chromium") or "/usr/bin/chromium"

    try:
        with sync_playwright() as playwright:
            from playwright.sync_api import expect

            browser = playwright.chromium.launch(headless=True, executable_path=browser_path)
            page = browser.new_page(viewport={"width": 1365, "height": 900})
            page_errors = []
            navigations = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
            base_url = f"http://127.0.0.1:{server.server_port}"
            page.goto(base_url, wait_until="networkidle")
            initial_navigation_count = len(navigations)

            page.locator("#source-url").fill("https://www.youtube.com/playlist?list=PLfixture123")
            page.locator(".search-form button[type=submit]").click()
            page.locator(".video-row").first.wait_for(timeout=15_000)
            original_path = page.url
            # Server-side sort and filter replace the small results surface.
            page.locator('button[name="sort_choice"][value="author"]').click()
            page.locator('button[name="sort_choice"][value="author"].is-current').wait_for()
            assert page.url == original_path
            assert page.locator(".sort-choice.is-current").inner_text().strip() == "Author"
            page.locator('input[name="filter_text"]').fill("methods")
            page.locator('button[name="list_action"][value="filter"]').click()
            expect(page.locator(".video-row")).to_have_count(1)
            assert page.url == original_path
            assert page.locator(".video-row").count() == 1
            assert "Methods" in page.locator(".video-title").inner_text()
            page.locator('input[name="filter_text"]').fill("")
            page.locator('button[name="list_action"][value="filter"]').click()
            page.locator('button[name="list_action"][value="select_all"]').click()

            meter_before = page.locator(".usage-meter").inner_text()
            page.screenshot(path=str(screenshot_directory / "inline-results-wide.png"), full_page=True)
            for width, height in ((280, 900), (3440, 1100)):
                assert_no_horizontal_overflow(page, width, height)
                page.screenshot(path=str(screenshot_directory / f"inline-results-{width}.png"), full_page=True)
            page.set_viewport_size({"width": 1365, "height": 900})

            page.locator('button[name="list_action"][value="summarize"]').click()
            page.get_by_text("BATCH COMPLETE", exact=True).wait_for(timeout=15_000)
            page.locator(".summary-card").first.wait_for()
            meter_after = page.locator(".usage-meter").inner_text()
            assert meter_after != meter_before, "Usage meter did not reflect summary activity."

            page.locator(".summary-card").first.locator("summary").click()
            chat_form = page.locator(".summary-card[open] .chat-form").first
            chat_form.locator('input[name="question"]').fill("What does the evidence support?")
            chat_form.locator('button[type="submit"]').click()
            panel = page.locator("#answer-dock")
            panel.wait_for()
            panel.get_by_text("Try again", exact=True).wait_for(timeout=15_000)
            assert "question" in panel.inner_text().casefold() or "answer" in panel.inner_text().casefold()
            retry_form = panel.locator(".chat-form")
            interrupted = {"once": False}

            def interrupt_one_poll(route):
                """Lose one status response without repeating the paid action."""
                if not interrupted["once"]:
                    interrupted["once"] = True
                    route.abort("failed")
                    return
                route.continue_()

            page.route("**/jobs/*", interrupt_one_poll)
            retry_form.locator('button[type="submit"]').click()
            panel.locator(".local-request-error button").wait_for(timeout=15_000)
            panel.locator(".local-request-error button").click()
            expect(panel).to_contain_text("Recovered answer from the fixture provider.", timeout=15_000)
            assert chat_calls["count"] == 2, "Retrying a status read repeated the AI action."
            page.unroute("**/jobs/*", interrupt_one_poll)
            assert panel.evaluate("el => getComputedStyle(el).display") != "none"
            assert len(navigations) == initial_navigation_count, f"Unexpected main document navigation: {navigations}"
            assert page.url == original_path
            page.screenshot(path=str(screenshot_directory / "inline-answer-wide.png"), full_page=True)

            page.set_viewport_size({"width": 280, "height": 900})
            assert_no_horizontal_overflow(page, 280, 900)
            page.screenshot(path=str(screenshot_directory / "inline-answer-mobile.png"), full_page=True)
            page.set_viewport_size({"width": 3440, "height": 1100})
            assert_no_horizontal_overflow(page, 3440, 1100)
            page.screenshot(path=str(screenshot_directory / "inline-answer-ultrawide.png"), full_page=True)
            assert not page_errors, f"Browser errors: {page_errors}"
            browser.close()
    finally:
        server.shutdown()
        app_directory.cleanup()


if __name__ == "__main__":
    main()
