# Trail Recommender Handoff

## Current state

The project is a Windows terminal hiking-trail recommender. Its runtime entry point is `trail_recommender.py`. It asks for a broad U.S. area first, checks each answer with a separate AI call, searches six named trail sites, validates returned source links, and prints conversational recommendations.

Existing `test.txt` contains user work and must remain untouched.

## Run

```powershell
py -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "..."
py -X utf8 trail_recommender.py
```

Python 3.14 is the verified local version. `openai==3.11.0` is pinned because current Responses API tool schemas are used directly.

## Runtime flow

1. Configure stdin, stdout, and stderr for UTF-8.
2. Create an OpenAI client with a 60-second timeout and two SDK retries.
3. Ask location first.
4. Send each answer to a separate low-reasoning guard call.
5. Retry unclear or unsafe answers three times.
6. Collect location, timing, distance, and access before searching.
7. Search with Responses API `tool_search` and `web_search`.
8. Restrict web search to the six source domains.
9. Validate structured result data and every source URL locally.
10. Ask more high-value questions when results need more information.
11. Relax soft preferences in a fixed order when no good match exists.
12. Print friendly trail suggestions and source links.

## State and question order

`InterviewSession` holds answers, asked field names, hidden question counters, elapsed time, and detected language. Counters are used only for stopping and prioritizing questions; they are never printed.

Questions are short and ranked by information value. Geography is forced first. Hard restrictions remain unchanged during relaxation: U.S. scope, broad area, accessibility, children or dogs, explicit safety limits, maximum time or distance, and explicit availability.

Soft relaxation order:

1. Commercial presence.
2. Charity opportunity.
3. Popularity.
4. Exact views or wildlife.
5. Facilities.
6. Route shape.
7. Budget, only when user allows flexibility.

## AI contracts

The guard call receives one field, one question, and one marked user answer. It returns `valid`, `unclear`, or `unsafe`, plus detected language. It has no permission to perform actions.

The recommendation call receives the collected answers and the current relaxation level. It returns match quality, a need-more-information flag, a short note, and recommendations. Each recommendation must contain facts, pre-trip checks, and at least one source object.

The application never executes model text, follows model-provided commands, or fetches arbitrary URLs. Model text is cleaned before terminal output.

## Source policy

Allowed domains:

- `hikingproject.com`
- `wikiloc.com`
- `alltrails.com`
- `hiiker.app`
- `traillink.com`
- `theoutbound.com`

The program uses Responses web search domain filters. It does not scrape, log in, bypass access controls, or make direct automated requests to trail sites.

## Privacy

The program asks for a broad area and does not request an exact address. It does not write user answers to disk. Responses API calls use `store=False`. The API key is read only from `OPENAI_API_KEY`.

## Failure behavior

- Missing API key: friendly setup message and exit code 1.
- Missing location: friendly request for a broad U.S. area and exit code 1.
- Guard rejects an answer three times: continue with `no preference`, except location.
- Invalid model JSON or source URL: friendly retry message and exit code 1.
- Network or SDK failure: friendly retry message and exit code 1.
- Ctrl+C: friendly cancellation message and exit code 130.

## Tests

```powershell
py -m py_compile trail_recommender.py test_trail_recommender.py
py -m unittest test_trail_recommender -v
```

Tests cover Unicode answers, guard retries, source allowlisting, both required tools, match relaxation text, output meta suppression, question limits, and maximum control nesting.

## Maintenance

Keep `MODEL`, `SOURCE_DOMAINS`, `QUESTIONS`, `RELAXATIONS`, and both JSON schemas synchronized. Any change to source domains requires updates to the web-search tool payload, URL validation, tests, and this document. Any change to user-visible wording must preserve casual language and avoid internal implementation details.

Do not add scraping, arbitrary URL fetching, shell tools, persistent user profiles, or hidden prompt disclosure features without a new security review.
