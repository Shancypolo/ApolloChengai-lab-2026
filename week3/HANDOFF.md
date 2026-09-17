# Trail Recommender handoff

## Document control and acceptance

Owner: next repository maintainer. Scope: local Windows CLI prototype, not a deployed service. Update this document in the same change as any change to prompts, context, tools, source domains, dependencies, output schema, or tests.

Receiving maintainer accepts this handoff after they can install dependencies, run the CLI, explain one preference from input through search, run the offline suite, identify rejected source URLs, and make one reversible change with its test. This follows runbook practice: a procedure needs an owner, required tools, error handling, and validation by someone other than its author. It also records the operational boundary and known gaps rather than implying production readiness.

No deployment, database, account system, background worker, web server, CI, monitoring, alerting, rollback artifact, or persistent user preference store exists.

## Repository map

| Path | Purpose |
| --- | --- |
| `trail_recommender.py` | CLI runtime, AI contracts, source controls, response validation, rendering. |
| `verify_trail_recommender.py` | Offline fake-client regression suite. It must never make an API request. |
| `test.py` | One live Responses API diagnostic. It consumes quota. |
| `README.md` | Short install, run, and verification path. |
| `requirements.txt` | Direct runtime dependencies. |
| `HANDOFF.md` | This operational and technical record. |

Before changing files, run `git status --short`. Existing edits belong to the user unless proven otherwise. Do not reset, checkout, or broadly delete files to obtain a clean tree.

## Setup and execution

Requirements:

- Windows terminal with UTF-8 support and Python launcher `py`.
- Python 3.14 was used for the recorded verification.
- Network access and an `OPENAI_API_KEY` authorized for Responses API, `tool_search`, and `web_search`.

```powershell
py -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key"
py -X utf8 trail_recommender.py
```

Keep keys out of source, commits, prompts, and shared terminal history. `.env` files are ignored but local secret storage remains operator responsibility.

The program sets terminal streams to UTF-8 when supported. It normalizes text to NFC and strips terminal control characters before storing or printing user/model text. Blank input repeats the current generated question without an AI request. EOF stops questioning and searches from recorded preferences. Ctrl+C returns exit code `130`. A missing key, malformed result, invalid source URL, or provider failure returns a short user-facing error without raw provider output.

## Product and runtime flow

1. `main()` builds one OpenAI client with a 60-second timeout, no automatic retries, and certifi-backed `httpx2` transport.
2. `collect_adaptive_hiking_preferences()` asks AI-generated questions and persists compact preference updates.
3. The interview ends when AI returns `search`, EOF occurs, or six questions have been displayed.
4. `find_trail_recommendations()` searches the approved domains with exact preferences, then only low-priority relaxations.
5. `display_trail_recommendations()` prints each trail's source link, bullet fit explanation, metadata, pre-trip checks, and source links.

Location starts as a critical preference. The first generated question must request it. If the user gives no usable location, search uses `United States`, which avoids a clarification loop and still respects scope.

Search relaxation sequence:

1. Low-priority special interests.
2. Conditions and services.
3. Route and scenery details.
4. Transport and budget, but only when flexible.

Never relax explicit safety/accessibility, group, distance/duration, timing, or location preferences without a contract and test change.

## AI contract

### Shared request configuration

Every main-AI and search-AI request uses:

- Model `gpt-5.6-luna`.
- Medium reasoning effort and low text verbosity.
- `store=False` and prompt cache key `trail-recommender`.
- Plain-text response mode followed by local JSON parsing; JSON-object mode is not combined with web search.
- `tool_search`, a deferred source-policy function, and `web_search` in every request; automatic selection is restricted to `web_search`.
- Web-search domain filter equal to `ALLOWED_SOURCE_DOMAINS`.

The model receives `Return JSON only.` in input. Parsing accepts normal JSON, fenced JSON, and an object embedded in otherwise plain output. It rejects non-object output.

### Interview prompt

`QUESTION_AGENT_INSTRUCTIONS` is the source of truth. It retains injection defenses from the old contract and replaces the old clarification-heavy flow.

Priority order encoded in the prompt:

| Priority | Canonical factor | Meaning |
| --- | --- | --- |
| Critical | `location` | U.S. region, park, or travel radius. |
| Critical | `season_and_timing` | Season, dates, daylight, start time. |
| High | `distance_and_duration` | Mileage and available hiking time. |
| High | `difficulty_and_fitness` | Fitness, elevation tolerance, difficulty. |
| High | `safety_and_accessibility` | Safety, mobility, wheelchair, health needs. |
| Medium | `group_needs` | Group, children, dogs, experience. |
| Medium | `route_and_scenery` | Route shape, views, water, wildlife. |
| Medium | `transport_and_budget` | Parking, transit, vehicle access, fees. |
| Low | `conditions_and_services` | Cell coverage, facilities, popularity, amenities. |
| Low | `special_interests` | Charity, commercial activity, other preferences. |

The AI asks higher-priority unanswered factors first, combines compatible factors, creates questions from context, and never uses a fixed question or fixed sequence. It must not ask an already recorded or already asked factor. General or ambiguous answers preserve any clear part and leave other details flexible; they do not cause a clarification question. A detailed answer with location and several constraints can end questioning immediately. The local six-question cap is a backstop, not an interview target.

Interview response schema:

```json
{
  "decision": "ask | search",
  "feedback": "brief string",
  "question": "short generated question or empty",
  "preference_updates": {"canonical_factor": "concise extracted value"},
  "question_fields": ["canonical_factor"]
}
```

`is_valid_interview_response()` rejects unknown factors, non-string values, an initial non-location question, any repeat of `asked_fields` or stored preferences, invalid question length, and a search decision with a question. `generate_next_hiking_question()` requests repair at most twice after a malformed answer. `apply_preference_updates()` retains concise extracted values, so later AI rounds receive prior preferences instead of raw transcript text.

### Minimal AI context

`HikingPreferenceContext` is a concrete dataclass used by the CLI. It stores `preferences`, `asked_fields`, `question_count`, `started`, `last_question`, and `last_answer`. It has no base class, protocol, template, or generic abstraction.

`model_context()` sends only:

```json
{
  "preferences": {"canonical_factor": "concise value"},
  "asked_fields": ["canonical_factor"],
  "last_exchange": {"question": "...", "answer": "..."}
}
```

It intentionally excludes question history, counters, elapsed time, hidden prompts, raw legacy answers, and implementation metadata. This compact state gives the AI memory without repeatedly presenting a growing conversation transcript.

### Search prompt and response

`SEARCH_AGENT_INSTRUCTIONS` forces searches, citations, and fact extraction to the six domains below. It returns `match`, `needs_more_info`, `note`, and `recommendations`. Each recommendation requires:

```text
name, location, summary, fit,
metadata: nonempty object of source-supported strings,
before_you_go: list of strings,
sources: nonempty list of {name, https_url}
```

`fit` becomes one succinct bullet under `Why it fits`. `metadata` prints under `Trail metadata`; it may contain distance, elevation gain, difficulty, route type, estimated time, access, or fees only when source-supported. Each result prints its approved source URL. The normalizer converts legacy `details` and `source_url` data to current fields, then validation enforces metadata, source presence, HTTPS, and allowlisted hostnames.

## Source and security boundary

Allowed hostnames:

1. `hikingproject.com`
2. `wikiloc.com`
3. `alltrails.com`
4. `hiiker.app`
5. `traillink.com`
6. `theoutbound.com`

`web_search` receives this exact allowlist. Local validation permits HTTPS URLs whose hostname equals an allowed domain or is its subdomain. The model cannot extend this list. Do not add sources in a prompt only: synchronize `ALLOWED_SOURCE_DOMAINS`, tool filters, local validation, tests, README wording, and this document.

User input, past answers, web pages, URLs, metadata, and tool output are untrusted data. Prompt instructions prohibit role claims, hidden-prompt extraction, secret requests, encoded/invisible instructions, and instructions from pages. The program never executes model text, follows arbitrary URLs, or exposes API keys. These controls reduce risk; they do not make source information current, safe, complete, or suitable for field safety decisions. Users must check weather, closures, permits, conditions, maps, and emergency requirements before hiking.

## Engineering constraints

The implementation uses functional style for transformations and validation: input sanitization, context construction, normalization, validation, and rendering are discrete functions with explicit data. Object-oriented use stays concrete and small: `HikingPreferenceContext` owns interview state. Do not add abstract base classes, factories, templates, inheritance trees, or generic framework layers.

Maintain a maximum nesting depth of four for control structures. The offline suite measures this from the Python AST. Keep prompts as explicit constants, not hidden template systems. New behavior needs a direct test in `verify_trail_recommender.py` before or with its runtime change.

## Diagnosis and recovery

Run these first:

```powershell
py -V
py -m pip show openai httpx2 certifi
Get-ChildItem Env:OPENAI_API_KEY
py -m py_compile trail_recommender.py verify_trail_recommender.py
py -m unittest verify_trail_recommender -v
```

| Symptom | Check | Recovery |
| --- | --- | --- |
| Key missing | `Get-ChildItem Env:OPENAI_API_KEY` | Set a key for current PowerShell session. |
| Import failure | `py -m pip show httpx2` | Reinstall declared dependencies. |
| API rejection | Run `py -X utf8 test.py` once | Inspect status; do not add retry loops blindly. |
| Invalid interview JSON | Offline regression suite | Check schema/prompt compatibility and repair path. |
| Invalid result | Source URL and metadata tests | Keep invalid result out of terminal output. |
| No exact match | Review relaxation label and search input | Present close match only after permitted relaxation. |
| EOF in piped use | Closed stdin test | Expected: search from collected preferences. |

`max_retries=0` is intentional. Before adding retries, document request count, timeout, rate-limit effects, user delay, and test coverage. There is no deployment rollback. Revert a bad local change with a reviewed, targeted version-control change; never use broad destructive cleanup on user work.

## Verification record and change procedure

Recorded after this change:

```powershell
py -m py_compile trail_recommender.py verify_trail_recommender.py
py -m unittest verify_trail_recommender -v
```

Both passed: 23 offline tests. The suite covers tool availability on all AI rounds, medium reasoning, minimal context and preference retention, repeat/clarification rejection, early search, vague-answer progression, U.S. fallback, source allowlisting, required metadata/link output, terminal safety, EOF, missing-key handling, injection handling, and four-level nesting.

Before handoff or merge:

1. Read this document, README, target code, and relevant tests.
2. Preserve existing work after `git status --short` and `git diff` review.
3. Add or update an offline fake-client regression test.
4. Run compile, unit tests, and `git diff --check`.
5. Run `py -X utf8 test.py` only when live provider behavior changed and quota is available.
6. Update this document and README when a user-visible or operational contract changed.

Acceptance checklist:

- [ ] Dependencies install on a clean Windows Python environment.
- [ ] CLI starts with an authorized API key.
- [ ] All AI requests retain both configured tools and medium reasoning.
- [ ] Model context has only preferences, asked fields, and latest exchange.
- [ ] Ambiguous input does not produce a clarification loop.
- [ ] Detailed input can reach search before six questions.
- [ ] Every printed recommendation has a source link, fit bullet, and metadata.
- [ ] Non-HTTPS or non-allowlisted URLs are rejected.
- [ ] Compile, offline tests, and diff check pass.

## Documentation basis

The handoff follows AWS guidance that runbooks name the desired outcome, required access/tools, error handling, ownership, and validation by another operator: [AWS Well-Architected runbooks](https://docs.aws.amazon.com/wellarchitected/latest/framework/ops_ready_to_support_use_runbooks.html). It uses operational-readiness guidance to state ownership boundary, test evidence, recovery limits, and known gaps: [IF4IT operational readiness assessment](https://if4it.org/best-practices/systems-development-lifecycle-sdlc/operational-readiness-assessment-within-the-sdlc/). These sources guide documentation structure only; they do not certify this prototype for production use.
