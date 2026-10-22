# PageOne technical handoff

## Document control

Owner: the local app maintainer. Review this document whenever a prompt, model, input context, source domain, URL behavior, output shape, storage field, dependency, visual asset, diagnostic, or test changes. Facts below describe the current code; product choices and limitations are called out as assumptions. Last reviewed: 2026-10-22.

PageOne is a finished local, single-user loopback app. It has no login, remote deployment, database server, job queue, multi-process lock, or service monitoring. One Flask process owns the jobs, archive lock, and usage meter. Restarting it stops active jobs and clears in-memory session usage; saved archive data remains on disk. The supported `run.py` command can serve a static local failure page even when Flask or another required package is missing.

## Setup and run

Python 3.10 or newer is required. In this directory, install dependencies directly and start the app:

```sh
python -m pip install -r requirements.txt
python run.py
```

A virtual environment is optional. It is a private folder for this app's installed Python packages, so the install does not affect other projects. To use one, run `python -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux before installing.

Set `OPENAI_API_KEY` in the active terminal; keep it out of source control. Start with `python run.py` and open `http://127.0.0.1:5000`. The app binds to loopback only. It does not load `.env` files. Set `PAGEONE_PORT` to use another local port; `PAGEONE_DATA_DIR` changes the local folder for the archive and log, which otherwise live under `instance/` beside `app.py`.

For offline and browser checks, install `requirements-dev.txt`; `tests/startup_smoke.py` also checks the missing-package notice using standard-library Python; Playwright may need a one-time Chromium install with `python -m playwright install chromium`. `tests/visual_test.py` can also use an installed `chromium` executable.

## File map

| File or folder | Purpose |
| --- | --- |
| `app.py` | Flask routes, safe request failures, local logging, batch jobs, archive pages, and chat flow. |
| `run.py` | Standard-library startup check, loopback installation notice, and normal app launch. |
| `youtube_source.py` | HTTPS YouTube URL validation, `yt-dlp` metadata listing, English JSON3 captions. |
| `summary_service.py` | GPT-6 Luna prompts, strict JSON schemas, output checks, title-only topic labels. |
| `usage_accounting.py` | Responses usage parsing, published-rate arithmetic, in-memory session ledger. |
| `storage.py` | Versioned local JSON archive, validation, atomic writes. |
| `templates/` | Jinja2 full-page HTML documents and fragments. |
| `static/css/pageone.css` | Single-surface editorial styling, responsive type, lines, and spacing. |
| `static/fonts/` and `static/images/` | Historical OFL font and generated mark assets retained in the repository; runtime pages do not request them. |
| `design-preview.png` and `design-archive-preview.png` | Image Gen Home and Archive concepts for visual comparison; neither is loaded by the app. |
| `templates/error_notice.html` and `templates/startup_error.html` | Script-free inline failure notices for running pages and missing-package startup. |
| `tests/test_pageone.py` | Network-free service and route tests using fake providers. |
| `tests/visual_test.py` | Local Chromium functional, error-panel, and viewport checks with saved screenshots. |
| `tests/startup_smoke.py` | Loopback CLI checks for normal launch and missing-package startup. |
| `apiTests/` | Existing extraction experiments and a separate live diagnostic. |
| `apiTests/live_diagnostic.py` | Optional quota-bearing source check or one synthetic summary request. |
| `instance/pageone.json` | Local archive, ignored by Git. |
| `instance/pageone.log` | Rotating diagnostics, ignored by Git. |

The application uses Python, HTML/Jinja2, and CSS only; there is no application JavaScript, script tag, HTMX asset, or JavaScript dependency. Archive search runs in Python; templates repeat already prepared rows and render visual states. Server-rendered forms do full page posts. Native `<details>` holds collapsed summaries and navigation state; a short HTML refresh requests job status. No dedicated accessibility or localization layer is included, as requested. Titles from YouTube remain source text and may contain Unicode.

## Visual system and minimal copy

The current design uses a text-only `P. 1` masthead, white page, black serif headings, small sans navigation, a restrained red accent, generous blank space, and horizontal division rules. Home, Archive, Settings, results, and notices share one background. Header navigation replaced the sidebar. Search fields and the preference editor are defined by bottom or horizontal rules; there are no cards, floating windows, side panels, loaded images, or shadows. The fixed session meter remains plain text on white at the bottom left of every running page. Source titles and summaries remain visible as content.

The new `design-preview.png` and `design-archive-preview.png` show the intended Home and Archive rhythm. CSS uses Georgia with Times New Roman fallback for large headings and prose, plus Arial/Helvetica for quiet navigation and controls, so no font download is needed. Earlier OFL font and generated logo files remain in the repository as historical assets but are not requested by runtime pages. An initial browser render of the old Bodoni Moda face showed distracting cutout-like strokes, so the revision uses the stable platform serif stack. The design takes editorial patterns from The Atlantic while retaining PageOne's own name and controls.

At desktop widths, the page expands toward 2,200 pixels with proportionate side margins. At 700 pixels and below, the text navigation and masthead share one line; at 380 pixels and below, the URL control stacks to preserve its full value. Vertical space uses `dvh`; content may scroll on short viewports. The footer meter has only a division line and the same white background. Error routes and startup failure now show a ruled inline notice with an ordinary navigation link. These choices keep the no-JavaScript contract and the user's one-layer visual rule.

## Runtime flow

1. Home accepts a URL. `parse_youtube_url()` requires HTTPS, an exact host from the allowlist, and a valid video or playlist ID. A URL containing both IDs asks which source to use before extraction.
2. An inspection job calls `fetch_source()`. Flat playlist metadata uses the same `yt-dlp` approach represented by the existing `apiTests/` experiments. Valid video IDs and titles are saved in original order before any summary is requested. Date and author may be `Unknown`.
3. The inspection job sends batches of at most 80 title strings to `label_video_titles()`. The JSON input contains only the titles: it does not contain transcript text, summaries, IDs, or playlist content beyond those titles. The model returns one label per title. Generic or placeholder-only titles such as `Welcome`, `The Journey`, `Video 3`, `Lecture 2`, and `Untitled` are forced to `Other` by local validation. The word check preserves Unicode title letters. Missing or malformed topic output falls back to `Other` for that batch and shows a warning.
4. The source page lists every valid title and links each title to its YouTube video. Users may search title text, sort by playlist order, title, publish date, author, or topic, and select all, none, or individual rows. Submitting an action performs a normal HTTP form post.
5. A summary batch runs sequentially in a daemon thread. Existing summaries are linked by video ID and reused unless the user checks “Re-summarize.” For new or refreshed summaries, the app fetches English captions and sends the title, transcript, and current preference to the model. Transcripts are temporary and are not written to the archive or log.
6. Summary results are collapsed `<details>` rows with a server-side GET search across title, topic, and summary text. Each row can accept a follow-up question. The chat action fetches captions again and sends only that video’s title, transcript, saved summary, recent eight Q&A turns, and current question. It stores the question and answer in the JSON archive.
7. Archive pages show saved sources, filter source and video titles from the index search, and show all titles, available summaries, title topics, and stored Q&A on each source page. Settings save a reusable preference. The default is “Write a concise academic summary in coherent paragraphs. Explain the central thesis, key arguments, evidence, and limitations.”

Job progress exists only in memory. The HTML progress page refreshes itself every two seconds while its job is pending; terminal jobs render a result or an inline notice. Restarting the process loses active job state, but summaries written before restart remain saved.

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

The fixed bottom-left page meter displays the current browser session’s input (`I`), cached input (`C`), output (`O`), reasoning (`R`), total (`T`) tokens, and known USD cost. An asterisk marks partial accounting. Its title text explains the abbreviations; the detailed unreported, incomplete, and unpriced counts remain in Python ledger data and are not shown as long page copy.

As rechecked against the [official OpenAI API pricing page](https://developers.openai.com/api/docs/pricing/) and [GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna) on 2026-10-22, GPT-6 Luna standard rates were $0.10 per million input tokens, $0.01 per million cached input tokens, and $0.50 per million output tokens. The implementation uses integer units of 1/100,000,000 USD per token:

```text
uncached_input = input_tokens - cached_tokens
cost = uncached_input × $0.10 / 1,000,000
     + cached_tokens × $0.01 / 1,000,000
     + output_tokens × $0.50 / 1,000,000
if input_tokens > 272,000 for a call:
    double that call's input and cached-input cost
    multiply that call's output cost by 1.5
```

OpenAI usage reports cached tokens as a subset of input and reasoning tokens as a subset of output. The meter displays these subsets separately but counts them once: total tokens are input plus output; reasoning is not charged a second time. The API usage object’s `input_tokens`, `output_tokens`, `total_tokens`, `input_tokens_details.cached_tokens`, and `output_tokens_details.reasoning_tokens` feed the parser. Total is recomputed from valid input/output values if the supplied total is malformed, and the display marks that breakdown partial.

The ledger is keyed by a random Flask browser-session identifier, lives only in RAM, is not written to the archive, evicts sessions after 24 hours idle, is capped at 1,000 tracked sessions, and clears on process restart. The Flask session cookie is not permanent. Missing usage is counted as an unreported attempt. If cached-token detail is missing or invalid, input/output totals remain visible but the call is excluded from known cost; this prevents assuming a cache rate and showing a false exact total. Missing reasoning detail is shown as partial; it does not prevent the token-rate calculation when all input/cache/output counts are valid.

This is exact arithmetic at the published token rates for these request settings on the reviewed date, including the model page's over-272K-input multiplier, not a provider invoice. PageOne does not request extended cache retention or regional processing; special-routing charges and account-level adjustments are outside this meter. Rate or request-setting changes require updating the constants and rerunning checks. Review the [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create) when the SDK usage contract changes.

## Source and network policy

Allowed source hosts are `youtube.com`, `www.youtube.com`, `m.youtube.com`, `music.youtube.com`, and `youtu.be`, over HTTPS only. The code extracts IDs then constructs its own canonical watch or playlist URL; it does not fetch arbitrary user-supplied URLs. `yt-dlp` runs with no download for metadata listing. Caption retrieval requests English JSON3 subtitle or automatic-caption data with `skip_download=True`, holds the file in a temporary directory, and caps transcript text at 100,000 characters. No video or audio file is requested. There is no cookie jar, account sign-in, or access-control bypass.

This is not the official YouTube Data API. The [YouTube Terms](https://www.youtube.com/t/terms) and [official playlist-items API reference](https://developers.google.com/youtube/v3/docs/playlistItems/list) document the platform’s terms and an approved API route. The app follows the existing `yt-dlp` experiments; extraction behavior, service availability, applicable terms, and legal permissions are not guaranteed. Review those conditions before broader use. Private, age-restricted, unavailable, or captionless content can fail. Flat metadata can omit author or publish date.

## Storage, privacy, and security boundary

The version-1 JSON archive stores summary preferences, source metadata and title topics, summaries, timestamps, source links, and chat questions/answers. It does not store transcripts, API request/response bodies, or token usage. The file is readable, unencrypted JSON; protect it and the device account. The archive is written through a temporary sibling file, `fsync`, and atomic replacement under a process-local lock. If its JSON is malformed, the store refuses to overwrite it; back it up before manual repair. This lock does not coordinate multiple processes.

The app checks loopback host and client addresses, validates same-origin writes when an Origin header is present, and checks a session CSRF token on every form write. Response headers prohibit scripts and framing, restrict base URLs and form destinations to self, disable caching, and prevent MIME sniffing. The process is not hardened for remote exposure, reverse proxies, hostile local multi-user access, or shared writable folders. Do not bind to `0.0.0.0` or expose port 5000.

The OpenAI API receives the minimum current-video context for each action plus its task-specific user text. `instance/pageone.log` is a rotating 1 MB log with three backups; it records event names and exception class names, not transcript text, credentials, request bodies, or model output. A network failure can occur after the provider accepted a request, so that attempt may be billable even if usage is unavailable; the meter marks it unreported.

## Failure behavior and diagnosis

`run.py` checks for Flask, OpenAI, and yt-dlp before importing the app. If a package is missing or import initialization fails, it writes a concise cause to the launch terminal and rotating `pageone.log`, then serves `templates/startup_error.html` on loopback using Python's standard-library HTTP server. The static page says only that PageOne cannot start, shows the script-free inline notice, and offers Retry. It exposes only the page and CSS; no directory listing. `python app.py` bypasses this preflight, so `python run.py` is the supported end-user command. If the data folder is unwritable or the port cannot bind, the terminal still reports the failure; a browser notice cannot be served without an available loopback port.

After launch, `configure_safe_logging()` writes event names and exception class names to both a rotating local file and stderr. Raw provider messages, request bodies, transcripts, credentials, and model output are omitted. Flask routes convert predictable connection, missing-key, missing-package, source, and unexpected failures into short product notices. The notice appears before page content and Continue performs a normal GET. A failed title-topic call retains the title list with `Other` labels and an inline warning; a summary batch retains successful notes and displays failures after its job finishes. Unexpected route errors are handled before Flask's default traceback page. No script is used.

- Blank, insecure, invalid-ID, and lookalike-host links fail before extraction. Mixed video/playlist links ask which source to use.
- YouTube metadata and caption failures produce source notices; a missing yt-dlp package is preserved as a setup error. Failed batch videos are listed while remaining selections continue.
- Missing or offline OpenAI access, empty content, and malformed model output produce safe notices. A failed provider call may be billable even when usage is unavailable; the meter marks that attempt partial.
- A malformed archive is left untouched. Back it up and inspect a copy before repair.
- A restart loses active jobs. Already saved summaries are reused by video ID unless refreshed.

Offline fake-client checks do not contact YouTube or OpenAI:

```sh
python -m py_compile app.py run.py storage.py youtube_source.py summary_service.py usage_accounting.py tests/test_pageone.py tests/visual_test.py tests/startup_smoke.py apiTests/live_diagnostic.py
python -m unittest discover -s tests -v
python tests/startup_smoke.py
python tests/visual_test.py
```

`tests/startup_smoke.py` and `tests/visual_test.py` use loopback HTTP only; the unit suite remains free of network requests. The live diagnostic has separate `--ai-only`, `--topics-only`, and `--source-only` modes; the first two each make one quota-bearing request with synthetic input, while `--source-only` makes no OpenAI request. With no mode, it attempts the sample YouTube playlist, captions, and a summary. Keep live checks separate and record their actual result.

## Verification record

Update this section only with commands actually run. Earlier checks below remain historical evidence.

2026-10-22 single-surface editorial revision:

- Final Python compilation passed for the runtime modules, launcher, three test scripts, and live diagnostic. The offline fake-client suite passed 30 tests; `tests/startup_smoke.py` passed missing-package and normal CLI launch checks. `tests/visual_test.py` passed after the last template and font revisions, including page identity, expected content, working navigation/selection/search/chat/settings, no visible image/sidebar/dialog, no horizontal overflow, and no browser console errors. `git diff --check` passed. No live API diagnostic was rerun for this design-only revision; quota-bearing results above are historical.
- Direct Chromium navigation to `https://www.theatlantic.com/` returned HTTP 403 with a site security block. The redesign therefore relied on the published 2026 desktop screen analysis, the type designer's first-party explanation, and an older documented navigation case study; it does not claim a live visual inspection of the current homepage.
- Image Gen produced separate Home and Archive design concepts. The first local Chromium pass exposed cutout-like strokes in the previously bundled display font. Switching the display stack to Georgia/Times removed that defect in the next screenshots. The source-layout browser flow then passed with fake services at 280, 320, 430, 844, 1365, and 3440 pixel widths; screenshots are in `/tmp/pageone-atlantic-visual`. The local browser, not a cloud browser, rendered the app.
- The layout check covered Home, invalid-link notice, empty and populated Archive, Settings, playlist selection/sorting, batch results, chat, and a fake offline AI notice. Visual inspection compared 1600×1000 Home and Archive screenshots with the two generated concepts, including masthead scale, single background, horizontal rules, sparse red, navigation placement, search baseline, and meter position. One deliberate difference is that archive fixture data contains one source instead of the concept's three example sources.

2026-10-22 wide-layout and diagnostics revision:

- Python compilation passed for the five core runtime modules, `run.py`, three test scripts, and live diagnostic. The offline unit suite passed 30 tests, including missing-source-package propagation, safe product failure text, unexpected-error popup/log privacy, long-input USD rates, and nesting depth. No external requests were made by the unit suite.
- `tests/startup_smoke.py` passed. It used `python -S run.py` to simulate missing packages, confirmed the local HTML notice, stderr message, and rotating log, then launched the installed app through `run.py`. Both checks used loopback only. A missing-package page was also rendered and visually inspected in local Chromium.
- `tests/visual_test.py` passed with fake providers at 280×940, 320×940, 430×1100, 844×390, 1365×768, and 3440×1100. Screenshots under `/tmp/pageone-visual` were inspected by eye: Home and the `P. 1` image, 3440-pixel Settings and archive split layout, an invalid-link popup, and an offline-AI popup. The latter wrote a `ConnectionError` event to the local log and terminal while leaving title rows available with `Other` topics. No horizontal overflow was found by the browser check. This was local Chromium; cloud browser tools were unavailable.
- ImageMagick reported `pageone-wordmark.png` as 2100×900 with exactly two colors. The generated design reference was replaced with the new wide-masthead concept. The rendered Home matches its major proportions: wide masthead, near-full-width search, icon rail, paired rules, and fixed meter; the implementation keeps a rectangular form where the concept used rounded corners.
- One live quota-bearing `--ai-only` GPT-6 Luna/high diagnostic succeeded with 190 input, 0 cached, 65 output, and 0 reasoning tokens; known standard-rate cost was $0.00005150. The synthetic summary text was not printed. A separate live `--source-only` YouTube diagnostic failed to retrieve the sample playlist; the caught cause type was `DownloadError`. It used no OpenAI quota. The fake-client flows remain the functional regression evidence for extraction-dependent pages.

2026-10-22 editorial revision:

- Python compilation passed for five runtime modules, two test modules, and the separate live diagnostic.
- Offline fake-client suite passed: 26 tests. It used no OpenAI or YouTube network requests.
- Local Chromium browser flow passed with fake providers after a first screenshot exposed a 280-pixel search layout crowding and a later check exposed archive-detail overflow at 320 pixels. Both were fixed; the final flow passed at 280×940, 320×940, 430×1100, 844×390, 1365×768, and 3440×1100. It covered source listing, sorting, selection, summaries, follow-up chat, archive search, and preferences. Screenshots were visually reviewed at `/tmp/pageone-visual` against `design-preview.png`: icon rail and double rules, monogram scale, centered form, paper/ink palette, and meter position. The mark and rules are close to the concept; the compact meter is an intentional addition required by the user. The 280-pixel form stacks its button to retain the full placeholder. This was local Chromium, not cloud browser.
- A loopback `python app.py` CLI smoke passed with a temporary data directory: the page returned 200, included the logo URL and meter, and had no script tag.
- No new live OpenAI request was run for this styling revision; the previously recorded live API diagnostics below remain historical, quota-bearing evidence.

- Python compile check: passed for all five runtime modules, both test modules, and the live diagnostic.
- Offline fake-client suite: 26 tests passed; no YouTube or OpenAI network calls were made.
- Earlier local Chromium visual flow: passed with fake source, topic, summary, and chat services. It exercised title listing, sort/filter, all/none/individual selection, summary search, batch results, chat, archive search, settings, and no-script/no-ARIA markup, with no horizontal overflow at 280×940, 320×940, 430×1100, 844×390, 1365×768, and 3440×1100. Screenshots were visually inspected in `/tmp/pageone-visual`.
- CLI startup smoke test: passed; `python app.py` served the home page over loopback with a temporary data directory, session meter, and no script tag.
- Live OpenAI summary diagnostic: one GPT-6 Luna/high request succeeded with 190 input, 50 output, and 0 reasoning tokens; reported known token-rate cost was $0.00004400. No transcript or summary text was printed.
- Live OpenAI title-topic diagnostic: after the final title-only prompt update, one GPT-6 Luna/high request succeeded with two synthetic titles; `Video 2` was labeled `Other`, 211 total tokens were reported, and known cost was $0.00003710. No real video titles or transcript were sent.
- Live YouTube source-only diagnostic: failed; `yt-dlp` could not retrieve the sample public playlist in this environment. The earlier detailed check identified an outbound proxy HTTP 403. No OpenAI quota was used by the source-only attempt.
- Cloud browser: not available in the current tool environment; do not call local Chromium results cloud-browser results.

## Industry references and implementation assumptions

| Reference | Documented fact used | PageOne choice or assumption |
| --- | --- | --- |
| [OpenAI API pricing](https://developers.openai.com/api/docs/pricing/) and [GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna) | Standard input, cached-input, and output rates, plus the over-272K-input multiplier, are documented. | Rates were rechecked on 2026-10-22 and encoded as integer arithmetic; extended cache retention and regional processing are not requested. |
| [OpenAI Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create) | Responses include usage information and structured output configuration. | Usage breakdown is read when returned; unknown details are marked partial. |
| [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) and [prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) | Structured output constraints and clear instructions are available model controls. | The app uses small strict schemas and treats supplied content as untrusted data. |
| [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Prompt wording alone is not a dependable injection boundary; least privilege and separation of data/control are relevant. | The app combines fixed instructions, data fields, no tools, output validation, and escaped rendering; none guarantees jailbreak resistance. |
| [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) | Confabulation is a generative-AI risk. | Output is treated as a reading aid and not an authoritative transcript. |
| [yt-dlp README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md) | `yt-dlp` documents flat playlist extraction and subtitle options. | It is used to follow the repository’s existing experiments; compatibility and permission are not assured. |
| [YouTube Terms](https://www.youtube.com/t/terms) and [playlistItems API](https://developers.google.com/youtube/v3/docs/playlistItems/list) | YouTube publishes its terms and an official playlist-listing API. | This app does not use the official API; a future approved integration requires credential and quota design. |
| [Flask error handling](https://flask.palletsprojects.com/en/stable/errorhandling/) | Flask supports registered handlers and otherwise produces a generic 500 page for unhandled exceptions. | Route exceptions are converted to safe PageOne notices with class-only diagnostics. |
| [Python logging HOWTO](https://docs.python.org/3/howto/logging.html) | Stream and rotating file handlers can write the same event to terminal and disk. | PageOne records event and type only, avoiding raw provider payloads. |
| [CSS viewport lengths](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/length) | `dvh` follows the dynamic viewport height. | PageOne scales its open Home composition without script; short viewports may scroll. |
| [MCKL Type's Atlantic typeface essay](https://www.mckltype.com/essays/designing-atlantic) | The type designer describes the commissioned display face as drawing on nineteenth-century American Scotch Romans and balancing print heritage with digital editorial use. | PageOne uses a freely available system serif stack instead of The Atlantic's proprietary face. |
| [TYPENORM's 2026 screen study](https://typenorm.com/articles/atlantic-ux-teardown) | Its September 2026 desktop capture records a consistent header, large condensed section headings, serif story typography, small utility type, and a narrow reading column. | PageOne adapts type hierarchy and clear reading measure, while removing the reference site's images, ads, gates, and panels. This is a published secondary observation, not a direct live capture here. |
| [Communication Arts' Atlantic web case study](https://www.commarts.com/webpicks/the-atlantic) | The older case study describes a reduced primary navigation and flexible editorial homepage modules. | PageOne uses only three top-level links and linear lists; that account is historical and does not establish the current site layout. |
| HTML and CSS implementation | Browser-native forms, `<details>`, and timed document refresh require no application script. | They are used for sorting/filter posts, collapsible rows, and progress refreshes to meet the no-JavaScript request. |

The Atlantic type essay, 2026 screen study, historical case study, pricing and model pages, Flask guide, Python logging guide, MDN viewport guide, and font sources were consulted on 2026-10-22. Other links are maintainer references for provider behavior, injection limits, source policy, and extraction. Provider and platform pages can change; recheck before materially changing those contracts.

## Ownership, maintenance, and acceptance

The local operator owns the API key, archive backups, and update policy. Keep the unit suite free of external network requests. Before dependency changes, run compilation, fake-client tests, browser checks, and the supported `run.py` CLI smoke; run live diagnostics separately and identify quota use. Update prompts, schemas, output normalization, cost constants, visual assets, startup behavior, and this handoff together when contracts change.

Acceptance means: local-only startup, including a visible missing-package fallback through `run.py`; source title and topic load before summary; topics based on title strings only and weak titles grouped as `Other`; HTTPS allowlisting; ambiguous-link progression; title sorting/filtering and all/none/individual selection; progress and summary archive; no repeat unless refreshed; dynamic chat and preference persistence; no transcript or raw provider error in archive/logs; safe failure notices in the browser, rotating log, and terminal; single white visual surface with type-only masthead, top navigation, no loaded images, and horizontal divisions; session-only usage counts and known USD math; no application JavaScript or script tags; compile, offline, local visual, and CLI checks accurately recorded; live Atlantic site block and cloud browser unavailability clearly stated.
