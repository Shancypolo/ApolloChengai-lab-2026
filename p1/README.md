# PageOne

PageOne is a local Flask app for listing YouTube playlist titles, grouping them by title-only AI topics, summarizing selected videos, and saving notes. Python owns the routes, archive, AI work, and server-rendered HTML. Local JavaScript requests same-origin HTML for in-page form actions and content links, updates the page, and polls job progress. Home, Archive, and Settings navigation still loads a full page. The bundled Newsreader font and navigation icon sprite are served locally; no third-party scripts or runtime font/image requests are used.

## Run

Install Python 3.10 or newer. In this folder:

```sh
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`. Set `OPENAI_API_KEY` in that terminal for topic labels, summaries, and follow-up answers. By default, the archive and log live in `user data/userdata.json` and `user data/error.log`; startup preserves and copies legacy files from `instance/`. Set `PAGEONE_DATA_DIR` to use another local folder; an explicit folder is checked in place for legacy files and never pulls from the app's `instance/` folder.

Each AI request is attempted once. Failures are recorded in `error.log` and the terminal; use Try again when you want another attempt.

The interface uses text, open white space, stronger division lines, task groups, and a three-step Home workflow. A locally served Newsreader font supports reading, while text labels accompany the navigation icons. `static/css/pageone.css` styles the main page and `static/css/page_guides.css` styles secondary pages. `static/js/local_requests.js` swaps same-origin server-rendered content into the page and checks progress every two seconds; `static/js/reading_position.js` steadies the viewport when a summary opens or closes. Playlist sorting, search, selection, archive actions, and job progress remain server-side Python operations.

Choose a playlist sort directly to reorder its titles. Long title lists show 48 videos per page and keep selected videos checked across pages. Follow-up questions and individual failed-summary retries open in a shared answer panel so the current list stays visible; failed chat retries retain the question. A separate retry request targets only the one failed video. Archive groups playlists, custom lists, and single videos; you can create and delete lists, move or copy videos, and delete a saved video summary. Home can add a video link or one-video playlist to an existing list. A larger playlist gets its own list. A repeat playlist check adds and summarizes newly found videos by default. Check “Replace saved playlist summaries” on Home only when you want to overwrite previous summaries. Settings control playlist order, archive order, automatic new-video summaries, interface text size, and reading width. Archive and Settings display the exact local archive and error-log file paths. YouTube metadata and English captions use yt-dlp first, then pytubefix if the primary lookup fails.

If packages are missing, `run.py` shows a notice at the same address and records the cause in the terminal and the configured `error.log`. Install the requirements, stop the notice with Ctrl+C, and run the command again.

A virtual environment is **optional**. It is simply a private folder for this app's Python packages, so they do not mix with packages used by other projects. If you want one, run `python -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux before installing.

## Check

Install `requirements-dev.txt` for the offline tests and local Chromium checks. Run `python -m unittest discover -s tests -v`, `python tests/startup_smoke.py`, `python tests/visual_test.py`, and `python tests/inline_browser_test.py`. See [HANDOFF.md](HANDOFF.md) for the AI contract, cost calculation, same-origin request transport, security boundaries, and diagnostic steps.
