# StoryEngine

StoryEngine continues the valley story from `opening.txt`. Run it with Python 3.10 or newer on Windows or macOS.

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

Use `\.venv\Scripts\python.exe storyengine.py --help` on Windows or `.venv/bin/python storyengine.py --help` on macOS. Enter one free-text story decision per prompt, up to 400 characters. Each prompt asks what you will do next and what you will photograph. Type `end story` to request the ending in the next generation. AI reviews realism, end requests, photo intent, sentence count, and story contract before returning a chapter. Unrealistic actions are reprompted; folklore can be discussed as belief.

Install dependencies and run StoryEngine with the same virtual-environment interpreter. At startup, the program verifies the `certifi` CA bundle and attempts to import `httpx2`, then checks the OpenAI SDK version. `httpx2` is optional with supported SDK 2.x; the SDK uses regular `httpx`. Unsupported SDK versions get setup instructions before the story starts. Story generation uses high reasoning effort.

To test API access without starting a story, run `\.venv\Scripts\python.exe testAPI.py` in Windows PowerShell or `.venv/bin/python testAPI.py` on macOS. This sends one short Responses API request and prints a request ID when available; it never prints the API key.

The story has five photographs and ends with the protagonist drowning or leaving the valley. AI is instructed to keep events physically possible; characters may discuss local folklore.

`story_memory.json` is read-only starting canon. Decisions, photo count, and chapter state stay in RAM only while StoryEngine runs; closing and restarting starts again from the same seed story.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS, run `.venv/bin/python -m unittest discover -s tests -v`.
