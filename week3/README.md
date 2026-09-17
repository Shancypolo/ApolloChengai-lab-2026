# Trail Recommender

Windows terminal service for U.S. hiking-trail recommendations. It uses an AI interview to retain compact preferences, then searches only Hiking Project, Wikiloc, AllTrails, Hiiker, TrailLink, and The Outbound.

The interview asks a small number of generated questions. It starts with high-priority trail constraints, retains extracted preferences across rounds, never repeats an asked factor, and can search early when a detailed answer gives enough constraints. Vague answers remain flexible; they do not trigger clarification loops.

Every AI round receives `tool_search` and allowlisted `web_search` tools with medium reasoning. Web results and returned URLs must remain on the six approved HTTPS source domains. The terminal output supplies source links, one bullet explaining fit, and source-supported trail metadata.

## Run

```powershell
py -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key"
py -X utf8 trail_recommender.py
```

Use a broad region rather than a home address. If location remains open, search defaults to the United States.

## Verify

```powershell
py -m py_compile trail_recommender.py verify_trail_recommender.py
py -m unittest verify_trail_recommender -v
```

`test.py` makes one live API diagnostic request. It needs a valid key and consumes API quota.

See `HANDOFF.md` for architecture, prompt and context contracts, source policy, failure handling, and handoff acceptance checks.
