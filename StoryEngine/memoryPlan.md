# Final Minimal Story Memory Implementation

## 1. Design goal

Build smallest reliable memory subsystem possible.

Final runtime architecture:

```text
OpenAI Responses API
+
story_memory.json
+
story_memory.py
```

No:

```text
database
SQLite
FTS
embeddings
vector search
RAG framework
agents
background jobs
memory service
event sourcing
migration framework
external persistence
```

---

# 2. Core invariant

LLM does not directly edit memory file.

Flow:

```text
load memory
    |
build prompt
    |
Responses API
    |
story_text + memory_updates
    |
validate updates
    |
apply updates in memory
    |
atomic file replacement
    |
return story_text
```

If any validation or file operation fails:

```text
existing memory remains unchanged
```

---

# 3. Files

Add only:

```text
project/
├── existing files...
├── story_memory.py
└── story_memory.json
```

Optional tests:

```text
tests/
└── test_story_memory.py
```

No other memory modules.

---

# 4. Runtime dependencies

Use:

```text
openai
pydantic
Python standard library
```

Standard library modules:

```python
json
os
threading
pathlib
tempfile
```

No persistence dependency.

---

# 5. Canonical memory format

Use one fixed JSON schema.

```json
{
  "version": 1,
  "step": 0,
  "rules": {},
  "facts": {},
  "state": {},
  "events": [],
  "threads": {}
}
```

Example:

```json
{
  "version": 1,
  "step": 18,

  "rules": {
    "world.teleportation": "Teleportation does not exist."
  },

  "facts": {
    "location.helios.position": "Helios Station is beneath Manhattan.",
    "location.helios.built": "Helios Station was constructed in 2032."
  },

  "state": {
    "location.helios.reactor": "Main reactor is offline.",
    "object.brass_key.owner": "Mara owns the brass key."
  },

  "events": [
    "Emergency power returned in Chapter 8.",
    "Mara discovered the hidden maintenance tunnel."
  ],

  "threads": {
    "signal.source": "Source of the transmission remains unknown."
  }
}
```

---

# 6. Memory classes

Only five categories exist.

## `rules`

Hard persistent constraints.

Examples:

```text
Magic cannot create matter.
Teleportation does not exist.
Story uses third-person limited POV.
```

Rules rarely change.

---

## `facts`

Stable canonical facts.

Examples:

```text
Station was constructed in 2032.
The vault is beneath the library.
Mara and Erin are sisters.
```

Facts do not represent temporary state.

---

## `state`

Current mutable information.

Examples:

```text
Reactor is offline.
Mara owns brass key.
North bridge is destroyed.
```

Updating state overwrites previous value.

No history retained in memory file.

Important history belongs in `events`.

---

## `events`

Important completed occurrences.

Examples:

```text
Mara transferred brass key to Erin.
Main reactor exploded during Chapter 12.
Signal was traced to relay station.
```

Events append only.

---

## `threads`

Current unresolved narrative obligations.

Examples:

```text
Signal source remains unknown.
Mara promised to return before sunrise.
Vault combination has not been discovered.
```

Resolving thread removes it.

Important resolution should also become event or fact.

---

# 7. Why keyed dictionaries

Use:

```json
"state": {
  "location.helios.reactor": "Main reactor is offline."
}
```

instead of:

```json
[
  {
    "id": 183,
    "kind": "state",
    "status": "active",
    ...
  }
]
```

Keyed dictionaries remove need for:

```text
IDs
indexes
status fields
replacement chains
duplicate-state detection
lookup loops
revision tables
foreign keys
history management
```

One logical property has one key.

Updating property becomes:

```python
memory["state"][key] = value
```

---

# 8. Key format

Keys MUST use:

```text
lowercase
dot-separated hierarchy
ASCII
```

Examples:

```text
world.teleportation
location.helios.position
location.helios.reactor
object.brass_key.owner
relationship.mara_erin
thread.signal_source
```

Recommended validation:

```python
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,119}$")
```

Keys remain stable.

State update MUST reuse same key.

---

# 9. Pydantic memory schema

```python
from pydantic import BaseModel, Field


class StoryMemory(BaseModel):
    version: int = 1
    step: int = 0

    rules: dict[str, str] = Field(default_factory=dict)
    facts: dict[str, str] = Field(default_factory=dict)
    state: dict[str, str] = Field(default_factory=dict)
    events: list[str] = Field(default_factory=list)
    threads: dict[str, str] = Field(default_factory=dict)
```

Pydantic validates file after every load.

Malformed memory MUST raise error.

Never silently create empty memory after parse failure.

---

# 10. Structured memory updates

Model returns story plus delta.

```python
from typing import Literal


class MemorySet(BaseModel):
    section: Literal[
        "rule",
        "fact",
        "state",
        "thread",
    ]

    key: str
    value: str


class MemoryDelta(BaseModel):
    set: list[MemorySet] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    resolve_threads: list[str] = Field(default_factory=list)


class GenerationResult(BaseModel):
    story_text: str
    memory: MemoryDelta
```

Only three mutation operations exist:

```text
SET
APPEND EVENT
RESOLVE THREAD
```

---

# 11. Mutation semantics

## SET rule

```json
{
  "section": "rule",
  "key": "world.teleportation",
  "value": "Teleportation does not exist."
}
```

Application:

```python
memory.rules[key] = value
```

Existing rule changes only when explicit retcon is enabled.

---

## SET fact

```json
{
  "section": "fact",
  "key": "location.helios.built",
  "value": "Helios Station was constructed in 2032."
}
```

Application:

```python
memory.facts[key] = value
```

Existing fact changes only during explicit retcon.

---

## SET state

```json
{
  "section": "state",
  "key": "location.helios.reactor",
  "value": "Main reactor is operating at 40% capacity."
}
```

Application:

```python
memory.state[key] = value
```

Previous value disappears from active memory.

If previous state matters historically, model also emits event.

---

## SET thread

```json
{
  "section": "thread",
  "key": "signal.source",
  "value": "Source of transmission remains unknown."
}
```

Application:

```python
memory.threads[key] = value
```

---

## APPEND EVENT

```json
{
  "events": [
    "Mara restored reactor to 40% capacity."
  ]
}
```

Application:

```python
memory.events.append(event)
```

---

## RESOLVE THREAD

```json
{
  "resolve_threads": [
    "signal.source"
  ]
}
```

Application:

```python
memory.threads.pop(key)
```

Resolution should normally also create fact or event.

---

# 12. No generic JSON patching

Do not support:

```text
JSON Patch
JSON Pointer
arbitrary paths
nested updates
list indices
move
copy
merge
```

Fixed operations produce much less code and smaller error surface.

---

# 13. Retcon policy

Generation API accepts:

```python
allow_retcon: bool = False
```

Normal mode:

```text
new rules allowed
new facts allowed
existing state updates allowed
existing threads updates allowed

existing rules cannot change
existing facts cannot change
```

Retcon mode:

```text
existing rules may change
existing facts may change
```

Application enforces this.

Do not rely only on prompt instruction.

---

# 14. Load implementation

```python
MEMORY_PATH = Path("story_memory.json")


def load_memory() -> StoryMemory:
    if not MEMORY_PATH.exists():
        return StoryMemory()

    return StoryMemory.model_validate_json(
        MEMORY_PATH.read_text(encoding="utf-8")
    )
```

Missing file creates initial empty memory.

Malformed existing file raises exception.

---

# 15. Atomic save

Never modify canonical file directly.

Implementation:

```python
def save_memory(memory: StoryMemory) -> None:
    data = memory.model_dump_json(indent=2)

    fd, temp_path = tempfile.mkstemp(
        dir=MEMORY_PATH.parent,
        prefix=".story_memory.",
        suffix=".tmp",
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, MEMORY_PATH)

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
```

`os.replace()` prevents partially written JSON becoming canonical file.

---

# 16. Concurrency

Use one process-level lock.

```python
MEMORY_LOCK = threading.Lock()
```

Generation:

```python
with MEMORY_LOCK:
    load
    call OpenAI
    validate
    apply
    save
```

Yes, lock remains held during network request.

That is intentional.

It removes need for:

```text
revision IDs
optimistic concurrency
conflict resolution
file locks
merge logic
stale-write handling
```

Constraint:

```text
Only one story-memory generation may run concurrently
inside one application process.
```

For small project, serial generation is simplest correct behavior.

Multi-process concurrent writers are explicitly unsupported.

---

# 17. Context serialization

Do not send JSON syntax unless convenient.

Serialize compact structured text:

```text
STORY MEMORY

RULES
[world.teleportation]
Teleportation does not exist.

FACTS
[location.helios.position]
Helios Station is beneath Manhattan.

STATE
[location.helios.reactor]
Main reactor is offline.

OPEN THREADS
[signal.source]
Source of transmission remains unknown.

IMPORTANT EVENTS
- Emergency power returned in Chapter 8.
- Mara discovered maintenance tunnel.
```

Rules:

```text
include all rules
include all facts
include all state
include all threads
include all events
```

No retrieval system.

No ranking.

No filtering.

---

# 18. Memory size limit

Because system intentionally has no retrieval layer, define hard supported memory size.

Example:

```python
MAX_MEMORY_CHARS = 80_000
```

Before API call:

```python
context = format_memory(memory)

if len(context) > MAX_MEMORY_CHARS:
    raise MemoryTooLargeError
```

Never silently truncate canon.

Never automatically summarize canon.

If project requires memory larger than supported limit, that is outside this system's defined operating envelope.

---

# 19. Developer instruction

Use fixed instruction:

```text
You are writing an ongoing fictional story.

STORY MEMORY contains canonical story information.

Requirements:

1. Never contradict STORY MEMORY.
2. Missing information remains unknown.
3. Do not invent canonical facts merely to fill gaps.
4. Record only information likely to matter later.
5. Do not record stylistic wording, incidental description,
   temporary gestures, ordinary dialogue, or speculation.
6. Use state for current mutable conditions.
7. Replace existing state using its existing key.
8. Use facts for durable information.
9. Use events for important completed occurrences.
10. Use threads for unresolved narrative obligations.
11. Resolve threads only when current text explicitly resolves them.
12. Do not change existing rules or facts unless retcon mode permits it.
13. Return generated story and memory changes through required schema.
```

When `allow_retcon=True`, append:

```text
Current request explicitly permits canonical retcons.
Existing rules or facts may change only where current user
request clearly establishes replacement canon.
```

---

# 20. Responses API call

Use structured output.

Conceptual integration:

```python
response = client.responses.parse(
    model=MODEL,
    store=False,
    instructions=build_instructions(
        memory_context,
        allow_retcon,
    ),
    input=prompt,
    text_format=GenerationResult,
)

result = response.output_parsed
```

Do not use:

```text
previous_response_id
conversation state
assistant memory
```

as canonical story memory.

---

# 21. Validation

Before mutating memory, validate entire delta.

Check:

```text
story_text non-empty

<= 30 total operations

key format valid

value non-empty
value <= 1000 characters

event non-empty
event <= 1000 characters

resolve target exists

existing rule modification requires retcon

existing fact modification requires retcon

duplicate event not added

same key not set twice in one delta
```

If one operation fails:

```text
reject entire memory update
```

Do not partially apply valid operations.

---

# 22. Apply implementation

Core logic:

```python
def apply_delta(
    memory: StoryMemory,
    delta: MemoryDelta,
    *,
    allow_retcon: bool,
) -> StoryMemory:

    updated = memory.model_copy(deep=True)

    validate_delta(
        updated,
        delta,
        allow_retcon=allow_retcon,
    )

    for item in delta.set:
        if item.section == "rule":
            updated.rules[item.key] = item.value

        elif item.section == "fact":
            updated.facts[item.key] = item.value

        elif item.section == "state":
            updated.state[item.key] = item.value

        elif item.section == "thread":
            updated.threads[item.key] = item.value

    for event in delta.events:
        if event not in updated.events:
            updated.events.append(event)

    for key in delta.resolve_threads:
        updated.threads.pop(key)

    updated.step += 1

    return updated
```

That is core memory engine.

---

# 23. End-to-end generation function

```python
def generate_story(
    prompt: str,
    *,
    allow_retcon: bool = False,
) -> str:

    with MEMORY_LOCK:
        memory = load_memory()

        context = format_memory(memory)

        if len(context) > MAX_MEMORY_CHARS:
            raise MemoryTooLargeError()

        response = client.responses.parse(
            model=MODEL,
            store=False,
            instructions=build_instructions(
                context,
                allow_retcon,
            ),
            input=prompt,
            text_format=GenerationResult,
        )

        result = response.output_parsed

        updated = apply_delta(
            memory,
            result.memory,
            allow_retcon=allow_retcon,
        )

        save_memory(updated)

        return result.story_text
```

This is entire application-level algorithm.

---

# 24. Unknown-information behavior

Critical rule:

```text
absence != permission to invent
```

Example memory:

```text
Mara lives in Boston.
```

No memory about birthplace.

Model must not create:

```text
Mara was born in Chicago.
```

unless current user request or generated story intentionally establishes it.

Memory update should represent only explicit story developments.

---

# 25. Evidence validation removed

Previous design stored and verified mutation evidence.

Remove it.

Reason:

```text
extra schema
extra strings
substring validation
more tokens
more code
more failure paths
```

Structured result plus current prompt/story generation is sufficient for stated small-project scope.

This is intentional simplification.

---

# 26. Revision history removed

Do not store:

```text
revision table
superseded records
mutation history
commit graph
response IDs
prompt hashes
output hashes
```

Canonical memory represents current usable truth.

Important historical information belongs in:

```text
events
```

Source control or normal project backups can preserve file history if desired.

---

# 27. Provenance removed

Do not attach:

```text
chapter IDs
paragraph IDs
response IDs
source excerpts
timestamps
```

to each memory item.

Reason:

memory subsystem exists to improve future generation, not provide forensic audit system.

---

# 28. Retrieval removed

Do not implement:

```text
FTS
BM25
keyword scoring
semantic search
embedding search
top-k
reranking
```

Entire memory enters prompt.

This removes substantial code and failure modes.

---

# 29. Summarization removed

Do not automatically summarize old events.

Automatic summaries can silently alter canon.

Events remain compact manually generated sentences.

Prompt instructs model to make each event:

```text
single durable future-relevant statement
```

---

# 30. Suggested event cap

Do not silently delete old events.

But prevent pathological model output.

Per generation:

```python
MAX_NEW_EVENTS = 10
```

Total events remain unbounded until overall memory-size limit is reached.

Memory-size error is explicit.

---

# 31. Key ownership

Model proposes memory keys.

Application validates syntax.

Model SHOULD reuse visible existing keys.

Examples:

```text
location.helios.reactor
object.brass_key.owner
thread.signal_source
```

If new item lacks obvious key, model creates concise deterministic key.

Avoid implementing separate key-generation logic.

---

# 32. Duplicate handling

Implement exact normalization only.

```python
def normalize(value: str) -> str:
    return " ".join(value.casefold().split())
```

For events:

```python
existing = {normalize(x) for x in memory.events}
```

Skip exact normalized duplicate.

Do not implement semantic duplicate detection.

---

# 33. Manual editing

`story_memory.json` remains human-readable.

Developer can inspect or manually correct:

```text
rules
facts
state
events
threads
```

Next load validates structure.

This replaces need for administrative UI.

---

# 34. Backup

Simplest safe backup:

```python
shutil.copy2(
    "story_memory.json",
    "story_memory.backup.json",
)
```

Optional.

Not part of generation path.

Version control can also track canonical file when appropriate.

---

# 35. Failure behavior

## API failure

```text
memory unchanged
exception propagates
```

## Structured-output failure

```text
memory unchanged
```

## Validation failure

```text
memory unchanged
```

## File-write failure

```text
old canonical file remains
exception propagates
```

## Memory too large

```text
generation stops
memory unchanged
```

No fallback that silently removes information.

---

# 36. Required tests

Minimum final test set:

```text
load missing file

load valid file

reject malformed file

atomic save

set new rule

reject rule overwrite normally

allow rule overwrite during retcon

set new fact

reject fact overwrite normally

allow fact overwrite during retcon

set state

overwrite state

create thread

update thread

resolve thread

append event

skip duplicate event

reject invalid key

reject oversized value

reject duplicate key mutation

reject unknown thread resolution

reject too many mutations

reject oversized memory

failed mutation leaves original object unchanged
```

---

# 37. Behavioral tests

## Persistent state

Input:

```text
Reactor is offline.
```

Later scene repairs reactor.

Expected memory:

```json
"state": {
  "location.helios.reactor":
    "Main reactor is operating at 40% capacity."
}
```

---

## Historical consequence

Same generation should add:

```json
"events": [
  "Mara restored Helios Station's reactor to 40% capacity."
]
```

---

## Open thread

Initial:

```json
"threads": {
  "signal.source":
    "Source of transmission remains unknown."
}
```

Later reveal source.

Expected:

```text
signal.source removed
```

and:

```text
fact/event records relay discovery
```

---

## Canon protection

Existing:

```json
"facts": {
  "location.helios.built":
    "Helios Station was constructed in 2032."
}
```

Normal request contradicts date.

Expected:

```text
fact unchanged
```

---

## Explicit retcon

Same request with:

```python
allow_retcon=True
```

Expected:

```text
fact may become new explicitly requested value
```

---

# 38. Final public API

Memory module only needs:

```python
load_memory()
save_memory(memory)
format_memory(memory)
apply_delta(memory, delta, allow_retcon=False)
generate_story(prompt, allow_retcon=False)
```

Private helpers:

```python
validate_delta()
normalize()
build_instructions()
```

Nothing else required.

---

# 39. Estimated production code

Target:

```text
Pydantic models       40-60 LOC
load/save             25-40 LOC
formatting             20-30 LOC
validation             50-80 LOC
delta application      30-45 LOC
OpenAI integration     25-40 LOC
helpers                20-30 LOC
```

Total:

```text
~210-325 LOC
```

Could be smaller if existing project already owns:

```text
OpenAI client
error handling
logging
configuration
```

---

# 40. Final constraints

This design intentionally assumes:

```text
small project
single process
single writer at a time
text-only stories
no character-specific memory
memory fits configured model context budget
no forensic revision history requirement
no semantic retrieval requirement
```

Within those constraints, adding database or memory framework would increase code without improving required behavior.

---

# 41. Final architecture

```text
                     story_memory.json
                            |
                            v
                       load_memory
                            |
                            v
                       format_memory
                            |
                            v
                     Responses API
                            |
                  structured GenerationResult
                     /              \
                    /                \
             story_text          MemoryDelta
                                      |
                                      v
                               validate_delta
                                      |
                                      v
                                 apply_delta
                                      |
                                      v
                                  atomic save
                                      |
                                      v
                              story_memory.json
```

## Final rule

Keep story memory as **small current canonical state**, not miniature database.

Use:

```text
rules    immutable constraints
facts    stable truth
state    current mutable truth
events   important history
threads  unresolved obligations
```

Everything else stays in story text.

This is smallest implementation that still gives explicit canon, mutable state, important history, open-thread tracking, retcon protection, structured updates, crash-safe persistence, and one-call Responses API integration.
