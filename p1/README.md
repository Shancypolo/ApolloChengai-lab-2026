# PageOne

PageOne is a local Flask app for listing YouTube playlist titles, grouping them by title-only AI topics, summarizing selected videos, and saving notes. 

## Run

Install Python 3.10 or newer. In this folder:

```sh
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`. Set `OPENAI_API_KEY` in that terminal for topic labels, summaries, and follow-up answers. The archive and log live in `instance/`; set `PAGEONE_DATA_DIR` to use another local folder.

If packages are missing, `run.py` shows a notice at the same address and records the cause in the terminal and `instance/pageone.log`. Install the requirements, stop the notice with Ctrl+C, and run the command again.

A virtual environment is **optional**. It is simply a private folder for this app's Python packages, so they do not mix with packages used by other projects. If you want one, run `python -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux before installing.

## Check

Install `requirements-dev.txt` for the offline tests and local Chromium checks. Run `python -m unittest discover -s tests -v`, `python tests/startup_smoke.py`, `python tests/visual_test.py`, and `python tests/inline_browser_test.py`. See [HANDOFF.md](HANDOFF.md) for the AI contract, cost calculation, same-origin request transport, security boundaries, and diagnostic steps.
