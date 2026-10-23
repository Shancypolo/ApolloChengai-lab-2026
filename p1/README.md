# PageOne

PageOne is a local Flask app for listing YouTube playlist titles, grouping them by title-only AI topics, summarizing selected videos, and saving notes. The interface uses Python, Jinja2, HTML, and CSS; it has no JavaScript.

## Run

Install Python 3.10 or newer. In this folder:

```sh
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`. Set `OPENAI_API_KEY` in that terminal for topic labels, summaries, and follow-up answers. The archive and log live in `instance/`; set `PAGEONE_DATA_DIR` to use another local folder.

The interface uses text, open white space, and division lines across Home, Archive, Settings, and results. Navigation is in the top header; no images or scripts are loaded by the app.

Choose a playlist sort directly to reorder its titles. Follow-up questions show a loading page while the answer is written. Archive groups playlists, custom lists, and single videos; you can create and delete lists, move or copy videos, and delete a saved video summary. Home can add a video link or one-video playlist to an existing list. A larger playlist gets its own list. A repeat playlist check adds and summarizes newly found videos by default. Check “Replace saved playlist summaries” on Home only when you want to overwrite previous summaries. Settings control playlist order, archive order, and automatic new-video summaries. Archive and Settings display the exact local archive and error-log file paths.

If packages are missing, `run.py` shows a notice at the same address and records the cause in the terminal and `instance/pageone.log`. Install the requirements, stop the notice with Ctrl+C, and run the command again.

A virtual environment is **optional**. It is simply a private folder for this app's Python packages, so they do not mix with packages used by other projects. If you want one, run `python -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux before installing.

## Check

Install `requirements-dev.txt` for the offline tests and local Chromium browser check. Run `python -m unittest discover -s tests -v`, `python tests/startup_smoke.py`, and `python tests/visual_test.py`. See [HANDOFF.md](HANDOFF.md) for the AI contract, cost calculation, security boundaries, and diagnostic steps.
