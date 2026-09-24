# StoryEngine Technical Handoff

## Purpose and acceptance

StoryEngine is a text-only, interactive Python story generator for Windows and macOS. It continues the supplied valley story, accepts only free-text decisions of at most 400 characters, keeps generated memory for one running session, and ends either with the protagonist drowning or leaving the valley.

Release acceptance:

- The supplied opening and initial story facts remain intact.
- Generated choices, events, photo count, and ending state exist only in process memory and reset from seed canon after restart.
- AI is instructed to keep plot actions physically possible, reject fantasy decisions, and treat folklore as human belief.
- AI self-checks its reported sentence count, nonfinal cliffhanger, and final outcome wording. Python checks the reported sentence range and structured ending-state consistency but does not count prose sentences or scan final wording.
- AI detects explicit end requests for the next generation; that can end before decision four. Otherwise, final response is required on decision nine.
- User prompts show no story choices and ask what the user will do next and photograph.
- Session-memory and CLI tests pass. Windows execution is verified locally; macOS must run the same suite on a macOS host or runner.

## Setup

Supported baseline: Python 3.10 or newer. Dependencies are `openai>=2.54,<3` and `pydantic>=2,<3`; all other runtime modules are from Python's standard library. The application checks that the active interpreter has an OpenAI SDK version in this range before starting the story. The SDK major-version cap keeps the app on its standard HTTPX transport. The installed 3.11.0 SDK uses HTTPX2 and, in this Python 3.14 environment, raised `RecursionError: maximum recursion depth exceeded` while establishing a connection; SDK 2.54.0 completed live API requests.

Create `.venv` with `py -m venv .venv` on Windows or `python3 -m venv .venv` on macOS. Install with `.venv\Scripts\python.exe -m pip install -r requirements.txt` on Windows or `.venv/bin/python -m pip install -r requirements.txt` on macOS. Set `OPENAI_API_KEY` in the current terminal and run `storyengine.py` or `python -m tests.testAPI` with that virtual environment's interpreter. The key must never be written to project files or printed by either program.

Run offline tests with `.venv\Scripts\python.exe -m unittest discover -s tests -v` on Windows or `.venv/bin/python -m unittest discover -s tests -v` on macOS. Use that same virtual-environment interpreter to run StoryEngine; a global interpreter with an unsupported SDK now fails early with setup instructions.

## Files and ownership

- `storyengine.py`: CLI interaction, input validation, direct prompt-injection screening, decision-limit flag, and process exit behavior.
- `tests/testAPI.py`: verifies `certifi` and optional `httpx2` imports, then sends one short Responses API request to check credentials, connectivity, and model access without starting a story.
- `story_memory.py`: Pydantic types, read-only seed loading, in-memory delta validation/application, Responses API call, and output-contract validation.
- `story_memory.json`: human-readable starting canon, loaded read-only for each new process.
- `opening.txt`: immutable opening displayed on first run.
- `docs/worldview.md`: human-readable story context for maintainers; runtime uses canonical JSON memory.
- `docs/storyengine-information-flow.md` and `docs/storyengine-information-flow.png`: maintained technical flowchart and generated paper-style figure.
- `tests/`: standard-library unit tests plus `testAPI.py`. Unit tests use temporary files and mocked API clients; they do not make API calls or edit the supplied memory file. StoryEngine startup and `testAPI.py` both verify the CA bundle and attempt the optional `httpx2` import; the supported SDK 2.x transport uses `httpx`.
- `docs/README.md` and `requirements.txt`: user setup and dependency bounds.
- `docs/storyengine-information-flow.md`: technical flowchart separating AI decisions from Python validation and temporary session state.

StoryEngine intentionally uses no database, retrieval layer, model tools, multi-agent flow, server-side conversation state, persistent user decisions, or full story transcript. `story_memory.json` is a read-only seed; generated deltas update a `StoryMemory` object in RAM and disappear when the process exits. `story_memory.py` keeps memory logic in one module; `storyengine.py` owns the CLI.

## Runtime flow

See [StoryEngine information flow](storyengine-information-flow.md) for an at-a-glance request path, API settings, validation boundary, and session reset behavior. The generated figure is [storyengine-information-flow.png](storyengine-information-flow.png).

1. Parse standard `--help`; load and validate read-only `story_memory.json` as session seed.
2. Print `opening.txt` without rewriting it. Each app launch starts from read-only seed canon, not the previous process's decisions.
3. Ask one free-response question: what will the user do next and what will they photograph. Blank and overlength answers reprompt locally. A clearly malicious prompt exits before the API call.
4. AI evaluates realism, detects clear end requests, interprets photo intent, counts sentences, and self-checks story contract. Unrealistic decisions reprompt without changing session memory. A clear end request can finish before decision four; Python passes the final-at-decision-nine flag.
5. Print `Generating next chapter…` to `stderr`; call the Responses API with separate fixed `instructions` and JSON input data. The request uses `gpt-5.6-luna`, high reasoning, low verbosity, `store=False`, stable key `storyengine-v1`, a 90-second timeout, and at most two SDK retries. No `tools` are configured.
6. Parse structured output, trust model-reported story checks, and validate response shape, ending-state consistency, memory key/value constraints, retcon policy, event/thread operations, photo-counter ownership, and size limits.
7. Apply the entire accepted delta to a copy and increment `step` in RAM. Return prose and updated session memory to the CLI. Any API, schema, model self-check, or memory-validation failure leaves caller-owned memory unchanged. Print accepted prose to `stdout` after validation succeeds.

`MEMORY_LOCK` allows one generation at a time inside one process. Separate processes never share generated state because seed canon is read-only.

## AI contract and memory

The Responses API uses Pydantic structured output:

- `decision_is_realistic`, `end_request_detected`, `sentence_count`, and `story_contract_passed`: AI classifications and self-check results for this turn.
- `story_text`: one chapter, model-reported as 4–9 complete sentences.
- `memory`: fixed delta with `set`, `events`, and `resolve_threads` only.
- `ending`: `none`, `drowning`, or `leave_valley`; AI self-checks the final sentence against this label.
- `photo_taken`: AI's decision about whether prose uses one exposure. Python decrements `camera.exposures_remaining` once when true and rejects photos after five exposures; AI owns intent/prose matching and the one-photo-per-chapter check.

Memory JSON schema remains version 1 with `step`, `rules`, `facts`, `state`, `events`, and `threads`. Rules and facts cannot change without explicit retcon permission; the CLI never grants that permission. State overwrites by stable lowercase key. Events append with normalized exact duplicate suppression. Thread resolution requires an existing key. Model updates are all-or-nothing, limited to 30 operations and 10 new events per generation; each key/value uses the specified syntax and a 1,000-character maximum. The formatted memory limit is 80,000 characters. Canon is never silently truncated, summarized, or retrieved selectively.

The application adds `state.story.ending` after a valid final response. It is an application-owned marker; the model cannot set it directly. This and all other generated memory are held only until process exit. Full chapter text and user answers are not retained as a transcript.

## Source policy and story style

Only user input, supplied opening, starting canon, and fixed story rules contribute story content. The model does not browse or use tools during story generation. Memory and user answers are JSON input data; instructions embedded inside those values do not change developer rules. Vague answers are interpreted in context without clarification. AI judges whether requested actions fit realistic physical limits; people may discuss folklore without it becoming fact.

Style analysis sources describe broad craft features such as lyrical description, sensory imagery, metaphor, personification, sentence rhythm, and nostalgia. StoryEngine uses those general techniques in original prose and does not request close imitation of a named author. [SparkNotes style analysis](https://www.sparknotes.com/lit/451/style/) and [UTRGV thesis on Bradbury and nostalgia](https://scholarworks.utrgv.edu/leg_etd/195/).

## Security boundary and privacy

The direct-input gate normalizes Unicode and whitespace, checks known instruction-override and prompt-extraction patterns, checks documented typo variants, and inspects decodable base64 text. It rejects a match with a nonzero exit before network access. Realism screening and prose contract review rely on model self-checks, so unusual actions and invalid text can be misclassified. The Responses request exposes no tools, and memory validation runs before in-memory state changes. These checks reduce common direct prompt-injection paths; they cannot prove that every novel natural-language attack will be detected. OWASP describes direct injection patterns and recommends separating data from instructions, validating inputs, and monitoring outputs. [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html).

`OPENAI_API_KEY` is read from the process environment and is not persisted. Requests set `store=False`; starting canon stays in the local read-only JSON file and generated memory stays in RAM. The app does not log prompts, responses, API keys, or request bodies. Network requests are still sent to the configured OpenAI API account.

Realism is requested through fixed generation rules and classified by the model in each response. This can misclassify fantasy as realistic or reject a physically possible choice. Drowning remains one terminal story outcome.

## CLI and failure behavior

The interface follows the human-first command-line guidance in [CLIG](https://clig.dev/): help is available with `--help`, narrative output goes to `stdout`, status and errors go to `stderr`, and success/failure use conventional exit codes. Input remains conversational; no numbered or selectable story options are shown.

- Missing API key: concise setup error, exit code 2.
- Malicious input: concise security error, exit code 2; no API call.
- Blank or overlength input: explain and reprompt.
- EOF: clean exit without ending the story.
- Ctrl+C: exit 130; session memory is discarded.
- Malformed seed, oversized memory, API failure, refusal, invalid structured output, rejected story text, or rejected delta: stop without changing caller-owned memory.
- Completed story: end current process; a new process starts from seed canon again.

## API source policy and implementation choices

API implementation settings are `gpt-5.6-luna`, high reasoning, low verbosity, `store=False`, and a stable prompt-cache key. [OpenAI Docs lists high as a supported reasoning effort for GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna). For third-party API guidance, the implementation uses the Responses API input/output pattern and bounded retry advice described by [TECHSY's Responses API tutorial](https://techsy.io/en/blog/openai-responses-api-tutorial) and [AWS's GPT-5.6 API integration guide](https://aws.amazon.com/blogs/machine-learning/get-started-with-openai-gpt-5-6-sol-terra-and-luna-on-amazon-bedrock/). The AWS article demonstrates its Bedrock endpoint; its bounded retry advice is applied here through the OpenAI SDK's retry setting, not by changing the endpoint.

The SDK dependency cap is an implementation compatibility choice, not API behavior guidance. SDK 3.11.0 used HTTPX2 and failed in the task's Windows Python 3.14 environment with a `truststore` SSL recursion error; SDK 2.54.0 completed live Responses API calls and the full suite. Python's existing HTTPX 0.28 client completed a TLS GET probe to `https://example.com`. HTTPX2 migration details are documented in the [SDK transport migration note](https://github.com/openai/openai-python/blob/main/httpx2.md); a related Windows/macOS truststore recursion report is tracked in [truststore issue 214](https://github.com/sethmlarson/truststore/issues/214).

Documented source guidance is distinct from StoryEngine choices: 90 seconds, two SDK retries, 400 characters, nine decisions, an 80,000-character memory cap, and the ending contract are application requirements or implementation defaults, not standards mandated by those sources.

## Test evidence

Verified in this Windows workspace with Python 3.14.7:

- `python -m unittest discover -s tests -v`: 58 tests passed with global OpenAI SDK 3.11.0 and project virtual-environment SDK 2.54.0. The incompatible-SDK tests verify a clear startup failure before story input or client construction, with session memory unchanged. TLS tests cover a valid CA bundle and optional `httpx2` both present and absent.
- `.venv\Scripts\python.exe -m tests.testAPI`: live connectivity check succeeded with OpenAI SDK 2.54.0, ran `certifi` and optional `httpx2` import checks, and returned a Responses API request ID. The key and response text were not printed.
- Live Responses API session test using SDK 2.54.0 and high reasoning: AI rejected a fantastical action without changing session state, then recognized an explicit end request, returned an accepted final chapter, honored one requested photo, recorded `leave_valley`, and reduced exposures from five to four. Seed file stayed byte-identical. Both live calls passed the model-reported story checks.
- Running the original global SDK 3.11.0 live call reproduced `APIConnectionError` caused by `RecursionError: maximum recursion depth exceeded`. StoryEngine now rejects unsupported SDK versions before story input and reports the documented virtual-environment setup command; the project `.venv` uses SDK 2.54.0 and its live CLI run passed.
- `python storyengine.py --help` displayed standard help. Empty-input CLI smoke test printed the unchanged opening, reprompted after blank input, and exited cleanly on EOF.
- macOS execution was not available in this workspace; the same portable test command remains the release check for a macOS host.

No API key or full live story output is recorded here.

## Maintenance

Update the tests and this handoff when schemas, prompts, API settings, memory rules, CLI behavior, dependencies, privacy behavior, or ending requirements change. Keep new memory operations out of scope unless the versioned seed schema is deliberately revised. Before release, run the offline suite on Windows and macOS, then exercise a multi-turn live session and confirm seed file remains unchanged.
