# PageOne technical handoff

## Document control

Owner: the local app maintainer. Review this document whenever a prompt, model, input context, source domain, URL behavior, output shape, storage field, dependency, diagnostic, or test changes. Facts below describe the current code; product choices and limitations are called out as assumptions. Last reviewed: 2026-10-21.

PageOne is a single-user loopback prototype. It has no login, remote deployment, database server, job queue, multi-process lock, or service monitoring. One Flask process owns the jobs, archive lock, and usage meter. Restarting it stops active jobs and clears in-memory session usage; saved archive data remains on disk.

## Setup and run

Python 3.10 or newer is required. In this directory, make and activate a virtual environment, then install the app dependencies:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set `OPENAI_API_KEY` in the active terminal; keep it out of source control. Start with `python app.py` and open `http://127.0.0.1:5000`. The app binds to loopback only. It does not load `.env` files. `PAGEONE_DATA_DIR` changes the local folder for the archive and log; by default they live under `instance/` beside `app.py`.

For offline and browser checks, install `requirements-dev.txt`; Playwright may need a one-time Chromium install with `python -m playwright install chromium`. `tests/visual_test.py` can also use an installed `chromium` executable.

## File map

| File or folder | Purpose |
| --- | --- |
| `app.py` | Flask routes, local request validation, batch jobs, archive pages, and chat flow. |
| `youtube_source.py` | HTTPS YouTube URL validation, `yt-dlp` metadata listing, English JSON3 captions. |
| `summary_service.py` | GPT-6 Luna prompts, strict JSON schemas, output checks, title-only topic labels. |
| `usage_accounting.py` | Responses usage parsing, published-rate arithmetic, in-memory session ledger. |
| `storage.py` | Versioned local JSON archive, validation, atomic writes. |
| `templates/` | Jinja2 full-page HTML documents and fragments. |
| `static/css/pageone.css` | Responsive page styling. |
| `tests/test_pageone.py` | Network-free service and route tests using fake providers. |
| `tests/visual_test.py` | Local Chromium functional and viewport checks. |
| `apiTests/` | Existing extraction experiments and a separate live diagnostic. |
| `apiTests/live_diagnostic.py` | Optional quota-bearing source check or one synthetic summary request. |
| `instance/pageone.json` | Local archive, ignored by Git. |
| `instance/pageone.log` | Rotating diagnostics, ignored by Git. |

The application uses Python, HTML/Jinja2, and CSS only; there is no application JavaScript, script tag, HTMX asset, or JavaScript dependency. Server-rendered forms do full page posts. Native `<details>` holds collapsed summaries and navigation state; a short HTML refresh requests job status. No dedicated accessibility or localization layer is included, as requested. Titles from YouTube remain source text and may contain Unicode.

## Runtime flow

1. Home accepts a URL. `parse_youtube_url()` requires HTTPS, an exact host from the allowlist, and a valid video or playlist ID. A URL containing both IDs asks which source to use before extraction.
2. An inspection job calls `fetch_source()`. Flat playlist metadata uses the same `yt-dlp` approach represented by the existing `apiTests/` experiments. Valid video IDs and titles are saved in original order before any summary is requested. Date and author may be `Unknown`.
3. The inspection job sends batches of at most 80 title strings to `label_video_titles()`. The JSON input contains only the titles: it does not contain transcript text, summaries, IDs, or playlist content beyond those titles. The model returns one label per title. Generic or placeholder-only titles such as `Welcome`, `The Journey`, `Video 3`, `Lecture 2`, and `Untitled` are forced to `Other` by local validation. The word check preserves Unicode title letters. Missing or malformed topic output falls back to `Other` for that batch and shows a warning.
4. The source page lists every valid title and links each title to its YouTube video. Users may search title text, sort by playlist order, title, publish date, author, or topic, and select all, none, or individual rows. Submitting an action performs a normal HTTP form post.
5. A summary batch runs sequentially in a daemon thread. Existing summaries are linked by video ID and reused unless the user checks “Re-summarize.” For new or refreshed summaries, the app fetches English captions and sends the title, transcript, and current preference to the model. Transcripts are temporary and are not written to the archive or log.
6. Summary results are collapsed `<details>` rows. Each row can accept a follow-up question. The chat action fetches captions again and sends only that video’s title, transcript, saved summary, recent eight Q&A turns, and current question. It stores the question and answer in the JSON archive.
7. Archive pages show saved sources, all their titles, available summaries, title topics, and stored Q&A. Settings save a reusable preference. The default is “Write a concise academic summary in coherent paragraphs. Explain the central thesis, key arguments, evidence, and limitations.”

Job progress exists only in memory. The HTML progress page refreshes itself every two seconds while its job is pending; terminal jobs render a result or a short error page. Restarting the process loses active job state, but summaries written before restart remain saved.

## AI contracts and prompt-injection measures

All three AI actions use `gpt-6-luna`, `reasoning.effort="high"`, `tools=[]`, and `store=False`. The OpenAI client sets `max_retries=0`, so an SDK retry cannot silently consume an untracked second attempt. AI request functions record response usage before parsing returned text.

| Action | Model input | Strict output contract |
| --- | --- | --- |
| Topic labels | A JSON object with an ordered array of video title strings only. | `{"topics": [string, ...]}` with one concise English label per title; weak titles become `Other`. |
| Summary | Current video title, user preference, and English transcript. | `{"summary": string}` with nonblank prose. |
| Follow-up | Current video title, English transcript, saved summary, last eight Q&A turns, current question. | `{"answer": string}` with nonblank prose. |

Injection defenses in the implementation are layered:

1. Prompt instructions identify titles, preferences, transcripts, saved summaries, and questions as untrusted content. They direct the model to ignore instructions embedded in those values and to answer from the supplied source only.
2. Request data is serialized as JSON values and passed separately from the fixed `instructions` string. Topic requests contain title strings only; the classifier cannot infer from or receive a transcript.
3. `tools=[]` gives the model no browser, network, filesystem, or application actions. The app does not execute model output.
4. Strict structured-output schemas and Python validation reject missing, malformed, blank, or wrong-count results; Jinja autoescaping renders output as text rather than trusted markup.
5. Independently, YouTube URLs are allowlisted and normalized before extraction, and the app only binds to loopback.

These controls reduce the attack surface; no prompt can guarantee that a model will resist every jailbreak or produce factually correct text. Topic labels are generated text, not trusted categories. Summaries are reading aids, not verified quotations or citations. `store=False` disables stored Response state but does not promise zero retention under every OpenAI account or abuse-monitoring setting.

## Usage and USD cost meter

The fixed bottom-left page meter displays the current browser session’s input, cached-input, output, reasoning (“thinking”), total tokens, and known USD cost. It also shows when a request did not return usage, when a usage breakdown is incomplete, or when exact cache pricing is unavailable.

As retrieved from the [official OpenAI API pricing page](https://developers.openai.com/api/docs/pricing/) on 2026-10-21, GPT-6 Luna standard rates were $0.10 per million input tokens, $0.01 per million cached input tokens, and $0.50 per million output tokens. The implementation uses integer units of 1/100,000,000 USD per token:

```text
uncached_input = input_tokens - cached_tokens
cost = uncached_input × $0.10 / 1,000,000
     + cached_tokens × $0.01 / 1,000,000
     + output_tokens × $0.50 / 1,000,000
```

OpenAI usage reports cached tokens as a subset of input and reasoning tokens as a subset of output. The meter displays these subsets separately but counts them once: total tokens are input plus output; reasoning is not charged a second time. The API usage object’s `input_tokens`, `output_tokens`, `total_tokens`, `input_tokens_details.cached_tokens`, and `output_tokens_details.reasoning_tokens` feed the parser. Total is recomputed from valid input/output values if the supplied total is malformed, and the display marks that breakdown partial.

The ledger is keyed by a random Flask browser-session identifier, lives only in RAM, is not written to the archive, evicts sessions after 24 hours idle, is capped at 1,000 tracked sessions, and clears on process restart. The Flask session cookie is not permanent. Missing usage is counted as an unreported attempt. If cached-token detail is missing or invalid, input/output totals remain visible but the call is excluded from known cost; this prevents assuming a cache rate and showing a false exact total. Missing reasoning detail is shown as partial; it does not prevent the token-rate calculation when all input/cache/output counts are valid.

This is exact arithmetic at the published standard token rates available on the reviewed date, not a provider invoice; rate changes or account-level adjustments require updating the constants and rerunning checks. Review the [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create) when the SDK usage contract changes.

## Source and network policy

Allowed source hosts are `youtube.com`, `www.youtube.com`, `m.youtube.com`, `music.youtube.com`, and `youtu.be`, over HTTPS only. The code extracts IDs then constructs its own canonical watch or playlist URL; it does not fetch arbitrary user-supplied URLs. `yt-dlp` runs with no download for metadata listing. Caption retrieval requests English JSON3 subtitle or automatic-caption data with `skip_download=True`, holds the file in a temporary directory, and caps transcript text at 100,000 characters. No video or audio file is requested. There is no cookie jar, account sign-in, or access-control bypass.

This is not the official YouTube Data API. The [YouTube Terms](https://www.youtube.com/t/terms) and [official playlist-items API reference](https://developers.google.com/youtube/v3/docs/playlistItems/list) document the platform’s terms and an approved API route. The app follows the existing `yt-dlp` experiments as a prototype; extraction behavior, service availability, applicable terms, and legal permissions are not guaranteed. Review those conditions before broader use. Private, age-restricted, unavailable, or captionless content can fail. Flat metadata can omit author or publish date.

## Storage, privacy, and security boundary

The version-1 JSON archive stores summary preferences, source metadata and title topics, summaries, timestamps, source links, and chat questions/answers. It does not store transcripts, API request/response bodies, or token usage. The file is readable, unencrypted JSON; protect it and the device account. The archive is written through a temporary sibling file, `fsync`, and atomic replacement under a process-local lock. If its JSON is malformed, the store refuses to overwrite it; back it up before manual repair. This lock does not coordinate multiple processes.

The app checks loopback host and client addresses, validates same-origin writes when an Origin header is present, and checks a session CSRF token on every form write. Response headers prohibit scripts and framing, restrict base URLs and form destinations to self, disable caching, and prevent MIME sniffing. The process is not hardened for remote exposure, reverse proxies, hostile local multi-user access, or shared writable folders. Do not bind to `0.0.0.0` or expose port 5000.

The OpenAI API receives the minimum current-video context for each action plus its task-specific user text. `instance/pageone.log` is a rotating 1 MB log with three backups; it records event names and exception class names, not transcript text, credentials, request bodies, or model output. A network failure can occur after the provider accepted a request, so that attempt may be billable even if usage is unavailable; the meter marks it unreported.

## Failure behavior and diagnosis

- Blank, insecure, invalid-ID, and lookalike-host links fail before extraction. Mixed video/playlist links ask the user to choose.
- A YouTube metadata or caption failure shows a short source error. Each failed video in a batch is listed while the worker continues with other selected videos.
- Topic API failure leaves the source saved and labels the list `Other` with a warning. Missing `OPENAI_API_KEY`, missing packages, API failures, empty content, and malformed model output produce a concise page message; logs contain only safe event/error-type metadata.
- A malformed archive is left untouched. Back it up and inspect a copy before repair.
- After a process restart, re-submit an interrupted batch. Already saved summaries are reused by video ID unless explicitly refreshed.
- No API key, transcript, summary, question, or response body should be pasted into the log to diagnose a problem.

Offline checks make no YouTube or OpenAI requests:

```sh
python -m py_compile app.py storage.py youtube_source.py summary_service.py usage_accounting.py tests/test_pageone.py tests/visual_test.py apiTests/live_diagnostic.py
python -m unittest discover -s tests -v
python tests/visual_test.py
```

`python app.py` is the end-user launch path. The live diagnostic has separate `--ai-only`, `--topics-only`, and `--source-only` modes; the first two each make one quota-bearing request with synthetic input, while `--source-only` makes no OpenAI request. With no mode, it attempts the sample YouTube playlist, captions, and a summary. Keep live checks separate from fake-client tests and report their actual result.

## Verification record

Update this section only with commands actually run. Current evidence for this revision:

- Python compile check: passed for all five runtime modules, both test modules, and the live diagnostic.
- Offline fake-client suite: 25 tests passed; no YouTube or OpenAI network calls were made.
- Local Chromium visual flow: passed with fake source, topic, summary, and chat services. It exercised title listing, sort/filter, all/none/individual selection, batch results, chat, archive, settings, and no-script/no-ARIA markup, with no horizontal overflow at 280×940, 320×940, 430×1100, 844×390, 1365×768, and 3440×1100. Screenshots were visually inspected in `/tmp/pageone-visual`.
- CLI startup smoke test: passed; `python app.py` served the home page over loopback with a temporary data directory, session meter, and no script tag.
- Live OpenAI summary diagnostic: one GPT-6 Luna/high request succeeded with 190 input, 50 output, and 0 reasoning tokens; reported known token-rate cost was $0.00004400. No transcript or summary text was printed.
- Live OpenAI title-topic diagnostic: one GPT-6 Luna/high request succeeded with two synthetic titles; `Video 2` was labeled `Other`, 191 total tokens were reported, and known cost was $0.00004110. No real video titles or transcript were sent.
- Live YouTube source-only diagnostic: failed; `yt-dlp` could not retrieve the sample public playlist in this environment. The earlier detailed check identified an outbound proxy HTTP 403. No OpenAI quota was used by the source-only attempt.
- Cloud browser: not available in the current tool environment; do not call local Chromium results cloud-browser results.

## Industry references and implementation assumptions

| Reference | Documented fact used | PageOne choice or assumption |
| --- | --- | --- |
| [OpenAI API pricing](https://developers.openai.com/api/docs/pricing/) | Published model rates distinguish input, cached input, and output pricing. | GPT-6 Luna prices on this page were recorded on 2026-10-21 and encoded as exact integer arithmetic. |
| [OpenAI Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create) | Responses include usage information and structured output configuration. | Usage breakdown is read when returned; unknown details are marked partial. |
| [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) and [prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) | Structured output constraints and clear instructions are available model controls. | The app uses small strict schemas and treats supplied content as untrusted data. |
| [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Prompt wording alone is not a dependable injection boundary; least privilege and separation of data/control are relevant. | The app combines fixed instructions, data fields, no tools, output validation, and escaped rendering; none guarantees jailbreak resistance. |
| [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) | Confabulation is a generative-AI risk. | Output is treated as a reading aid and not an authoritative transcript. |
| [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md) | `yt-dlp` documents flat playlist extraction and subtitle options. | It is used to follow the repository’s existing experiments; compatibility and permission are not assured. |
| [YouTube Terms](https://www.youtube.com/t/terms) and [playlistItems API](https://developers.google.com/youtube/v3/docs/playlistItems/list) | YouTube publishes its terms and an official playlist-listing API. | This prototype does not use the official API; a future approved integration requires credential and quota design. |
| HTML and CSS implementation | Browser-native forms, `<details>`, and timed document refresh require no application script. | They are used for sorting/filter posts, collapsible rows, and progress refreshes to meet the no-JavaScript request. |

The official pricing page was retrieved for this handoff on 2026-10-21. The other links are maintainer references for provider behavior, injection limits, source policy, and the existing extraction method. Provider or platform pages can change; recheck before materially changing those contracts.

## Ownership, maintenance, and acceptance

The local operator owns the API key, archive backups, and update policy. Keep offline tests network-free. Before dependency changes, run compilation, fake-client tests, browser checks, and a CLI smoke; run live diagnostics separately and identify quota use. Update prompts, schemas, output normalization, cost constants, and this handoff together when contracts change.

Acceptance means: local-only startup; source title and topic load before summary; topics are based on title strings only and weak titles become `Other`; HTTPS allowlisting; ambiguous-link progression; title sorting/filtering and all/none/individual selection; progress and summary archive; no repeat unless refreshed; dynamic chat and preference persistence; no transcript in archive or logs; session-only usage counts and known USD math; malformed response and missing-key paths; no application JavaScript or script tags; compile, offline, local visual, and CLI checks accurately recorded; cloud browser unavailability clearly stated.
