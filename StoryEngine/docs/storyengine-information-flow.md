# StoryEngine Information Flow

One valid user answer produces one structured chapter. Accepted memory changes stay in process RAM and disappear when StoryEngine exits.

```mermaid
flowchart LR
    U["User answer<br/>next action and photo<br/>maximum 400 characters"]
    I{"Nonempty and within limit?"}
    C["Print: an error occurred<br/>reprompt"]
    S["Read-only seed<br/>opening.txt<br/>story_memory.json"]
    M["StoryMemory<br/>current process RAM"]
    A["Responses API<br/>one structured generation call<br/>GenerationResult + usage<br/>store=false · no tools"]
    J{"Output and full delta valid?"}
    X["Print: an error occurred<br/>memory unchanged<br/>exit"]
    D["Apply delta to a copy<br/>update photo count and ending<br/>increment decision count"]
    T["Track full usage for pricing<br/>report output-token count only"]
    P["Print accepted chapter"]
    Q{"Ending set?"}
    E["Report usage and estimated cost<br/>exit; discard session state"]
    R["Ask next decision"]
    K["API settings<br/>gpt-5.6-luna<br/>high reasoning · low verbosity<br/>stable prompt-cache key"]

    U --> I
    I -- no --> C --> U
    I -- yes --> A
    S --> M --> A
    K -.-> A
    A --> J
    J -- no --> X --> E
    J -- yes --> D --> T --> P --> Q
    Q -- yes --> E
    Q -- no --> R --> U
    U -. "EOF exits cleanly" .-> E
```

## Boundaries

- The model receives fixed instructions separately from JSON containing the user answer and complete memory.
- The model proposes chapter text, ending metadata, photo use, and `set` / `events` / `resolve_threads` updates.
- Python validates schema, memory limits, retcon protection, thread targets, photo count, and application-owned ending state before applying any update.
- Each successful response contributes token usage to cost tracking. At story ending or EOF, print only output-token count and estimated cost.
- `story_memory.json` never changes during a run. A new process starts again from seed canon.
- Any runtime failure prints only `an error occurred`; exception details are not shown.
- No regex scans, input-guard call, independent review call, or transcript storage exists.
