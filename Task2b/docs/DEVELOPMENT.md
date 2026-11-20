# Development and maintenance

## Requirements and startup

Use Python 3.9 or newer and a current desktop browser. There are no third-party Python or JavaScript packages. Run `python3 Task2b/run.py` from the repository root. Editing files and reloading is the complete development workflow.

`run.py` resolves its directory from `__file__`, creates a `ThreadingHTTPServer` on loopback, prints its actual URL, and opens the default browser in a background thread. If the requested port is unavailable, it retries with port 0. Ctrl+C exits the server loop and closes the listening socket. `--no-browser` is useful for browser automation; `--port` accepts 0–65535. The HTTP handler prevents stale caching and suppresses successful request logs.

Keep a stable host and port when testing persistence. `localhost` and `127.0.0.1` have separate browser storage even when they serve identical files.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `index.html` | App structure, controls, labels, field guide, instructions dialog, visual effect layers |
| `style.css` | Design tokens, three-column desktop composition, square cell geometry, sprites, challenge styles, effects, reduced motion |
| `game.js` | Target selection, run clock, scoring, challenge renderers, pointer/keyboard input, feedback, audio output, persistence |
| `run.py` | Local HTTP startup, browser opening, port fallback, shutdown |

UI text and controls are real DOM elements; neither the game nor its forms are a flattened design image. Character art is loaded from local raster assets.

## State and timing

One `requestAnimationFrame` loop owns the run clock, target countdown, reaction interval, magician reveal, and feedback cleanup. Frame deltas are clamped to 250 ms to avoid a huge jump after a browser stall. Pausing prevents the active clocks from advancing. Visibility changes explicitly pause the run.

The main state distinguishes idle, running, paused, resolving, and waiting for the next spawn. A result locks the current target immediately, preventing duplicate submissions. `clearTarget()` clears DOM input and pointer state before the next target. `clearFeedback()` removes board color changes and particle elements. Starting and finishing a run reset both.

`nextType()` shuffles a fresh copy of the six types when its bag empties. The introductory Regular target is separate from the bag. Targets choose random grid cells independently; repeated positions are valid.

## Challenges

Each target calls `selectTarget()` immediately on spawn. That function renders a stable answer panel and dispatches to its challenge opener. Existing click handlers only refocus the current answer or complete a previously picked-up keyboard hammer.

- **Hammer:** Pointer Events and pointer capture keep a drag active outside its source button. Pointer release is compared with the current mole button’s client rectangle. A target identity check prevents an old drag from hitting a new target. Pointer cancellation and lost capture reset the drag.
- **Coordinate/shortcut:** Real HTML forms support Enter and standard required-field handling. Inputs are compared case-insensitively.
- **Wheel:** Angle stays internal. The visual uses a CSS rotation; only arrows and an upright instruction are exposed.
- **Painter:** Strokes are collected in canvas coordinates, independent of CSS size. Acceptance requires at least 60 canvas units of horizontal movement, vertical movement, overall width, and overall height. It is a forgiving geometry check, not semantic recognition; a suitably broad scribble can pass.
- **Magician:** A three-item array references the four rune definitions. The 2200 ms reveal advances only in the game loop. A phase flag blocks input during the reveal. Each repeat input checks the next item, and the third correct item resolves the target. Wrong choices resolve once with a penalty.

## Feedback and sound

`playFeedback()` cycles through six success variants and records the active effect in `data-feedback` on the board. Confetti is limited to 36 elements per success; misses use nine dust elements. Cleanup removes them after 1150 ms. Starting or stopping also cleans effects. Reduced motion omits particle creation and drastically shortens motion in CSS.

Sound uses a lazily created Web Audio context for a short hit tone and generated applause noise. No audio input, speech recognition, microphone stream, recording, or network audio service exists. Exceptions leave the visual game playable.

## Storage

The key is `whack-4x4-high-scores`. Its value is a JSON array of `{score, seconds}` records. Reads validate array shape and finite positive scores/nonnegative elapsed seconds. Writes happen when a positive run ends. The list is sorted and capped at three entries. Storage failures and malformed JSON do not block the game.

## Adding a character or changing rules

1. Add a type and label, local art, field-guide entry, and challenge opener.
2. Register the opener and title in `selectTarget()`.
3. Keep timing in the existing game loop; avoid untracked timeouts.
4. Guard handlers against paused or resolving state and stale targets.
5. Update the instructions and all relevant documentation.
6. Follow the regression guide, including pointer cancellation and pause/resume.

Difficulty timing lives in `TIMING` and `DELAY`. Scoring is centralized in `resolve()`. Feedback cycling is centralized in `playFeedback()`.

## Known boundaries

The interface targets 16:9 desktop screens and does not provide a mobile layout. Google Fonts supplies Bangers and Barlow Condensed; local fallback fonts keep the game usable offline, though typography may differ. High scores are browser-local rather than shared. The canvas check is deliberately simple. Optional sound depends on the browser’s normal audio policy.
