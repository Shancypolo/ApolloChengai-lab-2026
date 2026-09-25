# StoryEngine

StoryEngine continues the valley story in `opening.txt`. It runs as a Python command-line program on Windows or macOS.

## Setup

Install dependencies and set `OPENAI_API_KEY` in the current terminal.

**Windows PowerShell**

```powershell
py -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-api-key"
& $python storyengine.py
```

**macOS**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
.venv/bin/python storyengine.py
```

Enter one free-text answer of at most 400 characters. Each prompt asks what you will do next and what you will photograph. Type `end story` to request the ending in the next chapter. Blank or overlength answers reprompt with `an error occurred`.

Each valid answer uses one structured Responses API request. The story has five photographs and ends with the protagonist drowning or leaving the valley. The model is instructed to keep events physically possible; characters may discuss folklore as belief.

`story_memory.json` is read-only starting canon. Accepted decisions, photo count, and chapter state stay in RAM until the process ends. A new launch starts from the seed story. Any runtime failure prints only `an error occurred`.

When the story ends or you exit after generating chapters, StoryEngine prints output-token count and estimated GPT-5.6 Luna high-reasoning cost.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS, run `.venv/bin/python -m unittest discover -s tests -v`.
