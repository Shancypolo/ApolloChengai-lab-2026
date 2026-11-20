# WHACK! 6×6 — Engineering Handoff

**Project:** T2a browser arcade game  
**Status:** Feature-complete prototype; manual browser smoke checks recorded; broader accessibility and cross-browser QA remain.  
**Audience:** The next developer, reviewer, or maintainer picking up the project.

## 1. What this project is

WHACK! is a standalone, comic-book-style whack-a-mole game. It uses a 6×6 board with lettered rows A–F and numbered columns 1–6. Runs are endless and stop only when the player chooses **Save & Stop**. The player selects Easy, Medium, or Hard before starting.

The interface is built with vanilla HTML, CSS, and JavaScript. There is no package manager, framework, build step, server API, or account system. Generated sprites and design concepts are stored in this folder.

## 2. Run locally

From the repository root:

```sh
cd T2a
python3 -m http.server 4173
```

Open <http://127.0.0.1:4173/>. Stop the server with `Ctrl+C`.

The game can also be opened as a local file for most non-microphone features. Microphone access requires a secure context; localhost is treated as secure by browsers. For a hosted environment, use HTTPS. The browser requests microphone permission only after the player presses **Enable Mic**. [MDN: `getUserMedia()` security and permissions](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).

## 3. Project map

| Path | Responsibility |
| --- | --- |
| `index.html` | Game shell, stats, permission preflight, board, manual, and overlay containers |
| `style.css` | Comic-book visual system, layout, sprites, animations, responsive rules, reduced-motion override |
| `game.js` | Game state, mole lifecycle, challenge interactions, scoring, reactions, audio, microphone, and local score storage |
| `public/assets/mole-sprite-sheet.png` | Six generated mole/hamster sprites in a 3×2 sheet |
| `design/whack-6x6-concept.png` | Current 6×6 interface concept |
| `design/whack-9x9-concept.png` | Earlier concept retained for design history; the shipped game is 6×6 |

The runtime entry point is `index.html`, which loads `style.css` and `game.js` directly. There are no environment variables or secrets.

## 4. Gameplay contract

### Round and scoring

- A run has no countdown or automatic end. The elapsed clock counts up.
- Easy / Medium / Hard set mole visibility time to 16 / 12 / 10 seconds and the post-hit spawn delay to 1.5 / 1.05 / 0.75 seconds.
- A normal hit awards `100 + (current streak × 10)` points. Painter hits add half the drawing match grade, rounded down.
- A miss or failed challenge subtracts 25 points, never below zero, and resets the streak.
- **Save & Stop** records a run if it has at least one point. The top five records are sorted by score descending, then elapsed time ascending; the interface shows the best score and up to three records.
- Scores are stored in browser `localStorage` under `whack-6x6-high-scores`. They are local to the browser profile and origin, are not synchronized, and can be cleared by clearing site storage. [MDN: Web Storage API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API).

### Mole challenges

| Mole | Player action | Success condition |
| --- | --- | --- |
| Einstein | Enter the board coordinate in the floating prompt | Exact row letter + column, such as `C5` |
| Regular | Drag the large hammer onto the mole, then submit | Hammer drop lands on the active mole |
| Painter | Draw directly over the mole with the pen, then submit | Grade ≥65%, target overlap, minimum points and stroke length, and a clear turn for the hammer head |
| Coder | Press the displayed Shift + letter shortcut, then submit | The matching key event is detected and the input matches |
| Wheel hamster | Rotate clockwise/counterclockwise, then submit | Within 15° of upright |
| Scream | Arm the mic, say “BANG” loudly, then submit | Loudness check plus speech transcript match; loudness-only when speech recognition is unavailable |

Floating challenge panels are positioned over the board near the active mole. They require a submit/verify action where applicable. Success and failure each choose a random visual reaction; applause is synthesized through Web Audio and respects the sound toggle.

## 5. Browser access, privacy, and fallback behavior

- **Microphone:** The player explicitly opts in before the round. The game reads the mic through Web Audio to estimate loudness and uses `SpeechRecognition` / `webkitSpeechRecognition` to match “BANG” when available. Browser speech recognition has limited availability and may send audio to a browser vendor’s service; do not describe it as offline or fully private. [MDN: SpeechRecognition compatibility](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition) · [MDN: Web Speech API privacy and on-device recognition](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API).
- **Denied or unavailable mic:** Scream moles are excluded for that run; the other five mole types remain available. The stream is stopped when the player ends the run.
- **Speech recognition unavailable:** A loudness-only fallback is used. This is less specific and can accept non-speech noise; retain this limitation in user-facing help if behavior changes.
- **Pop-ups:** Browsers do not expose a general permission prompt for arbitrary pop-ups. **Check** opens a short, user-triggered test window and reports whether it was blocked. All actual challenges use in-page floating panels regardless, so blocked pop-ups do not prevent play.
- **Persistent data:** Only scores and elapsed seconds are stored locally. There is no backend or analytics integration.

## 6. Verification status

### Previously observed in Chrome

- 6×6 board and A–F / 1–6 axes rendered.
- Pop-up check opened successfully.
- Difficulty controls visibly selected Easy, Medium, and Hard.
- A coder shortcut challenge was completed; its success dialog required manual close before play resumed.
- Endless elapsed time continued without an automatic timeout; **Save & Stop** showed the run summary.
- High scores remained visible after reload.

These are manual smoke checks, not an automated test suite. They do not establish full browser compatibility or verify every challenge/reaction.

### Recommended next verification

1. Run a full success and failure pass for each of the six mole types, including wrong input, timeout, pause/resume, and submit states.
2. Exercise painter-grade boundaries (short stroke, no head turn, off-center drawing, just below/at 65%).
3. Verify microphone allowed, denied, missing-device, speech-recognition-unavailable, and browser speech-service error paths.
4. Check narrow mobile and tablet widths, keyboard-only use, screen-reader announcements, and touch input. The CSS includes responsive breakpoints and a reduced-motion preference, but these flows have not been fully verified.
5. Test score sorting and storage when the browser blocks or clears `localStorage`.

## 7. Accessibility and maintenance notes

The page uses native buttons and inputs, visible coordinate labels, an `aria-live` challenge region, and a `prefers-reduced-motion` override. The drawing and drag-hammer challenges are pointer-driven; plan a keyboard-accessible alternative before treating the game as fully accessible. W3C WAI recommends keyboard access for all functionality and enough time for users to operate controls. [WAI accessibility principles](https://www.w3.org/WAI/fundamentals/accessibility-principles/).

For future changes:

- Keep scoring, difficulty timing, and score-key changes centralized in `game.js` and update this document when the gameplay contract changes.
- Keep sprite cells square and preserve the source artwork’s aspect ratio; update both the sprite sheet and its `data-mole` CSS mapping together.
- Keep permission requests tied to explicit user actions and keep a usable fallback for optional browser APIs.
- Keep score data local unless a separately designed account/sync feature is requested.
- Add automated checks if the project gains dependencies or a CI workflow; no test runner currently exists.

## 8. Release checklist

- [ ] Serve from the intended host and verify HTTPS if microphone support is required.
- [ ] Re-run the success/failure and permission checks in the target browsers.
- [ ] Confirm all six sprites, board axes, and drawing interactions at desktop and mobile widths.
- [ ] Review keyboard access, focus visibility, screen-reader announcements, and reduced-motion behavior.
- [ ] Verify score ordering, elapsed-time formatting, and empty/blocked storage behavior.
- [ ] Update the README and this handoff if controls, timing, privacy behavior, or persistence changes.

