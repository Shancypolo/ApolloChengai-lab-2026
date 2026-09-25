# Technical Requirements

- **Interface:** Python CLI for Windows and macOS. Ask what the user will do next and what they will photograph. Accept one nonempty answer of at most 400 characters.
- **Story loop:** Use one structured Responses API call per valid answer. Keep the opening, canon, story voice, five-photo limit, decision-nine ending, and early ending request.
- **Memory:** Load `story_memory.json` as read-only seed. Keep decisions, events, photo count, and ending state in process memory. Validate each delta, apply it to a copy, then replace session state only after every operation passes.
- **Delta operations:** Allow `set`, `events`, and `resolve_threads`. Protect existing rules and facts. Keep photo and ending markers application-owned. Reject duplicate or conflicting operations, unknown thread resolutions, invalid values, and oversized deltas.
- **API:** Use the Responses API with `OPENAI_API_KEY`, model `gpt-5.6-luna`, high reasoning, low verbosity, `store=False`, a stable prompt-cache key, and no model tools.
- **Usage report:** Use full Responses token usage internally for pricing. At story ending or session EOF, print only output-token count and estimated model cost.
- **Errors:** Show only `an error occurred` for invalid input or runtime failures. Never print exception details.
- **Code style:** Keep Pydantic classes for concrete schemas and session state. Keep other logic in small, descriptive functions. Group prompt/configuration constants at module top and use short section comments. Do not add regex features.
- **Layout:** Keep `storyengine.py`, `opening.txt`, and seed canon at project root; documentation in `docs/`; focused unit tests in `tests/`. Keep tests as consumers of `storyengine.py`; application code must not import tests.
