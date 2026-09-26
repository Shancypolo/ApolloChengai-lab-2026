# StoryEngine Technical Handoff

## Purpose

StoryEngine is an interactive, text-only valley story. It accepts one free-text decision of up to 400 characters per turn and preserves generated state for one process. Any final outcome is allowed; final chapter continues until the entire island is submerged and explains protagonist's fate and fate of his photographs afterward.

## Setup

Use Python 3.10 or newer. Install dependencies, set `OPENAI_API_KEY` in the current terminal, and run `storyengine.py` from project root.

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

Run the offline suite with `.venv\Scripts\python.exe -m unittest discover -s tests -v` on Windows or `.venv/bin/python -m unittest discover -s tests -v` on macOS.

## Files

- `storyengine.py`: CLI, Pydantic schemas, seed loading, delta checks, generation, usage tracking, and generic error output.
- `story_memory.json`: read-only starting canon.
- `opening.txt`: story opening shown at launch.
- `docs/`: story context, requirements, and program information flow.
- `tests/`: focused memory and CLI unit tests.

See [program information flow](storyengine-information-flow.md) for graph and flowchart convention.

See [program information flow](storyengine-information-flow.md) for the current flowchart and standard used.

## Runtime flow

1. Load `story_memory.json` as a new in-memory session and print `opening.txt`.
2. Ask what the user will do next and what they will photograph. Reprompt blank or overlength answers with `an error occurred`.
3. Send one Responses API request with fixed story instructions, the full memory, and user answer as JSON data. The request uses `gpt-5.6-luna`, high reasoning, low verbosity, `store=False`, a stable prompt-cache key, and no tools.
4. Parse a `GenerationResult`. Validate story and ending metadata, require final character/photo fate summaries after island submergence, check photo availability, and validate the full memory delta.
5. Apply accepted changes to a copy of `StoryMemory`, decrement photo count when used, set the ending marker on final chapter, and increment turn count. Add response token usage to session totals, then print the chapter.
6. Continue until an ending or end-of-input. Print output-token count and estimated API cost, then exit. Closing the process discards generated state; next launch reloads seed canon.

There is no separate input-guard request, reviewer request, transcript store, or API connectivity command. User content remains separate from fixed instructions but is not screened by an additional model call.

## Memory contract

Memory schema version 1 contains `step`, `rules`, `facts`, `state`, `events`, and `threads`. Model deltas contain `set`, `events`, and `resolve_threads`. Python protects existing rules and facts, rejects duplicate or conflicting operations, enforces operation and value bounds, prevents unknown thread resolutions, and owns `camera.exposures_remaining` and `story.ending`. The seed file is never modified.

Story memory stays in process RAM. The current process is the only writer, so generation does not need a lock or persistent transaction system. A failed request or validation leaves the current session object unchanged.

## CLI and errors

The prompt accepts one nonempty answer of at most 400 characters. EOF exits cleanly. The story can end early when the user asks; otherwise decision nine is final. Runtime failures and input corrections show only the exact text `an error occurred`; exception details are not printed.

The usage estimate reads each Responses `usage` object. Rates checked 2026-09-24: input and output are $0.20 and $1.20 per million tokens; cached input is $0.02, and cache writes use 1.25 times input rate. Reasoning tokens are included in output tokens and use output pricing. Long-context requests over 272,000 input tokens receive the documented input and output multipliers. Estimate uses listed rates and is not a final invoice. See [GPT-5.6 Luna pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna) and [Responses token-count guidance](https://developers.openai.com/api/docs/guides/token-counting).

No regex-based input or memory features belong in this project. Keep schemas as Pydantic classes, keep other behavior in small functions, and group related constants and short comments at the top of each module.
