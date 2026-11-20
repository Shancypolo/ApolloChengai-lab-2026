# Verification and regression guide

Use a local server rather than opening the HTML directly. The primary environment is current desktop Chrome with a 16:9 content viewport. Test 1280×720, 1600×900, and 1920×1080 at normal zoom. Restore any temporary browser viewport overrides after testing.

## Static checks

From the repository root:

```sh
python3 -c "import ast,pathlib; ast.parse(pathlib.Path('Task2b/run.py').read_text())"
node --check Task2b/game.js
python3 Task2b/run.py --help
```

Node is optional for the game itself; the second command is only a syntax check. Do not add a build tool or package dependency just to run the static page.

Check that HTML IDs are unique and that image paths resolve. Search active source for obsolete microphone handlers, permission calls, the removed footer sentence, and the removed footer ornament. The original archived sprite sheet can still contain its unused sixth character; active game types must contain Magician instead.

## Page and visual checks

1. The title is `WHACK! 4×4 — Mole Mayhem`, the page contains meaningful content, and no error overlay or broken asset appears.
2. The board contains exactly 16 cells, four row letters, and four column numbers.
3. The actual `.mole-grid` width and height match within one CSS pixel. Check each `.cell` too. Axes and the result footer are outside that square; the surrounding frame can have a different aspect ratio.
4. At each supported viewport, the full board and controls fit without page scrolling or overlap.
5. The golden board is the strongest visual surface. Smaller rails retain comic outlines, caption strips, and paper texture while using quieter colors.
6. No removed footer sentence or ornament is visible. There is no microphone toggle or permission request.
7. The first five character crops and the separate Magician asset are transparent, proportionate, and readable. Only the active board character is fully saturated; guide portraits remain subdued.
8. Inspect the developer console and network panel for errors, missing files, or stale assets.

For a read-only geometry check in browser developer tools:

```js
const grid = document.querySelector('.mole-grid').getBoundingClientRect();
console.table({ width: grid.width, height: grid.height, square: Math.abs(grid.width - grid.height) < 1 });
```

## All six challenge flows

Start on Easy to leave enough time for inspection. Confirm the correct panel appears as soon as each target spawns, without clicking the target.

| Flow | Expected result |
| --- | --- |
| Regular: click only | No points; hammer remains required |
| Regular: valid drag and release | One hit; +100 before any preceding streak |
| Regular: release outside the mole | Helpful retry message; no immediate penalty |
| Regular: keyboard pickup/drop | Same result as a valid pointer drop |
| Einstein: lowercase correct coordinate | Accepted and scored once |
| Einstein: wrong coordinate | −25 and streak reset |
| Painter: tiny tap | Retry hint, no hit |
| Painter: broad handle/head sketch | Accepted; mouse and keyboard paths both work |
| Coder: matching Shift shortcut or typed letter | Accepted after submission |
| Wheel: upright image and Verify | Hit; no degree text appears |
| Wheel: sideways image and Verify | Penalty and next target |
| Magician: reveal, then correct three-symbol repeat | No input during reveal; symbols hide; three matches give one hit |
| Magician: wrong repeat | One penalty and no further input on the old target |
| Skip or target expiry | One penalty, safe next spawn, no negative score |

Shuffled type bags guarantee all six types in each full bag. Do not change application state through developer tools to claim an interaction passed; use real input.

## Timing and lifecycle

- Pause during a target, during a hammer drag, during a Magician reveal, and immediately after a hit. No target or result clock should advance while paused.
- Resume using both the pause button and overlay action. The run must continue without duplicate spawns or stale input.
- Open and close instructions during play. Hiding the tab should pause it; returning should not silently resume it.
- Stop, start another run, and reload. Temporary effects and input must not leak into the next run.
- A second rapid answer must not score a target twice.
- Difficulty is locked while running and selectable after stopping.

## Feedback and accessibility

The success reaction order repeats: color → confetti → fly → spin → fade → clap. Check at least six valid hits to cover a complete cycle. Confirm that the board returns to its normal palette, particles disappear, and the next mole remains usable. A miss should show a muted tint, dust, and a clear result caption.

Enable the operating system’s reduced-motion setting. Confetti should not be created, movement should be minimal, and all result information must remain available. Mute sound and complete a target to verify visual-only operation. Keyboard focus should be visible in forms, controls, the drawing pad, and rune buttons. The help dialog should trap focus through native dialog behavior and close with Escape.

## Records

Finish a positive run and reload the same origin. Confirm that the saved record remains, zero-point runs do not save, and top records sort by score then fastest elapsed time. Invalid stored JSON should not blank the app. Tests must distinguish finished saved runs from unfinished current scores.

## Launcher

Run `python3 Task2b/run.py` and confirm browser opening plus successful page/asset requests. With the preferred port occupied, launch another instance and verify that its printed URL has a free port. Stop that test instance with Ctrl+C. Launch using an absolute script path from another working directory. Verify that `--no-browser` avoids opening a tab and `--help` starts no server.

Do not commit temporary test screenshots, traces, local storage fixtures, or browser automation scratch files. Keep durable instructions here; report actual test results separately when handing off changes.
