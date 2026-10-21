# PageOne

PageOne is a local Flask app that lists YouTube playlist videos, assigns topic labels from titles only, summarizes selected videos from English captions, and saves notes to a local archive. Pages use Jinja2, HTML forms, and CSS; the app contains no JavaScript.

## Run

Use Python 3.10 or newer. From this folder, create and activate a virtual environment, then install and start:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Set `OPENAI_API_KEY` in the current terminal before asking for title topics, summaries, or follow-up answers. Open `http://127.0.0.1:5000`. The app listens on loopback. Archive data and rotating diagnostics stay in `instance/`; `PAGEONE_DATA_DIR` selects another local folder.

## Verify

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m py_compile app.py storage.py youtube_source.py summary_service.py usage_accounting.py
python tests/visual_test.py
```

Offline tests use fake services and make no YouTube or OpenAI requests. The visual check uses local Chromium. See [HANDOFF.md](HANDOFF.md) for the AI contract, token-cost formula, security boundaries, privacy limits, and diagnostics.
