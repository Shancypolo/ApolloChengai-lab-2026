# Technical Requirements

- **Platform and interface:** Native Python CLI for Windows and macOS. Ask only what the user will do next and what they will photograph. Accept one open-text answer, maximum 400 characters.
- **Story continuity:** Preserve supplied opening and canon. Write in English with one consistent original voice. Interpret vague answers in story context.
- **Realism:** AI classifies requested actions; impossible or supernatural actions are rejected. Local folklore may be discussed as belief.
- **Turn limits:** AI detects explicit end requests. Otherwise, decision nine is final. Normally require at least four accepted decisions before ending.
- **Chapter contract:** AI generates 4–9 sentences, a nonfinal cliffhanger, or final drowning/leaving-the-valley outcome. AI returns sentence count, ending label, photo intent, and contract self-check in structured output.
- **API:** Use Responses API with `OPENAI_API_KEY`, model `gpt-5.6-luna`, high reasoning, low verbosity, `store=False`, stable prompt-cache key, bounded timeout/retries, and no model tools.
- **Security and state:** Reject clear prompt-injection attempts before API access. Keep user text separate from instructions. Python validates typed memory deltas, canon/retcons, photo counter, size limits, and all-or-nothing session updates. Story memory remains temporary to the process.
- **Python style:** Prefer standard-library solutions and readable functions. Use descriptive variable names; group configuration and prompt text at each module's top with short usage comments. Keep nesting to four levels or fewer. Use classes only for concrete state or schema.
- **Files and edits:** Preserve user-owned files and unrelated changes. Do not use destructive resets or broad deletion. Keep README practical; keep HANDOFF technically precise.
- **Verification and handoff:** Test blank and oversized input, the 400-character boundary, AI decision fields, session-state invariants, injection cases, and API failures. Run Windows and macOS suites when hosts are available. Research sources before material HANDOFF revisions and separate sourced facts from assumptions.

