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
3. Ask the main AI for the first question, requiring geography first.
4. Send each answer to a separate low-reasoning guard call.
5. Retry unclear or unsafe answers three times.
6. Send the full conversation to the main AI for feedback and the next question.
7. Skip fields already covered by earlier answers.
8. Ask focused follow-ups when the main AI marks an answer unclear.
9. Search with Responses API `tool_search` and `web_search`.
10. Restrict web search to the six source domains.
11. Validate structured result data and every source URL locally.
12. Relax soft preferences in a fixed order when no good match exists.
13. Print friendly trail suggestions and source links.

## State and question order

`InterviewSession` holds answers, asked field names, hidden question counters, elapsed time, and detected language. Counters are used only for stopping and prioritizing questions; they are never printed.

The main AI generates each question from the field guide and complete conversation. Geography is enforced first. It reports fields answered by each response, so later questions can skip them. Hard restrictions remain unchanged during relaxation: U.S. scope, broad area, accessibility, children or dogs, explicit safety limits, maximum time or distance, and explicit availability.

Soft relaxation order:

1. Commercial presence.
2. Charity opportunity.
3. Popularity.
4. Exact views or wildlife.
5. Facilities.
6. Route shape.
7. Budget, only when user allows flexibility.

## AI contracts

The guard call receives one field, one question, and one marked user answer. It returns `valid`, `unclear`, or `unsafe`, plus detected language. It accepts any nonempty answer and leaves relevance, completeness, and follow-up decisions to the main AI. It has no permission to perform actions.

The main question call receives the field guide, prior answers, conversation history, and hidden question counters. It returns one generated question or `done`, concise feedback about the latest answer, fields newly answered, fields covered by the next question, and whether the question is a clarification.

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
py -m py_compile trail_recommender.py verify_trail_recommender.py
py -m unittest verify_trail_recommender -v
```

Tests cover Unicode answers, permissive nonempty answers, natural time phrases, guard retries, dynamic question generation, field skipping, clarification follow-ups, source allowlisting, both required tools, match relaxation text, output meta suppression, question limits, and maximum control nesting.

## Maintenance

Keep `MODEL`, `SOURCE_DOMAINS`, `FIELD_GUIDE`, `RELAXATIONS`, and all JSON schemas synchronized. Any change to source domains requires updates to the web-search tool payload, URL validation, tests, and this document. Any change to user-visible wording must preserve casual language and avoid internal implementation details.

Do not add scraping, arbitrary URL fetching, shell tools, persistent user profiles, or hidden prompt disclosure features without a new security review.
