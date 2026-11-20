# Game rules and controls

## A run

Select Easy, Medium, or Hard before starting. The first target is Regular, introducing the hammer. Later targets come from shuffled bags containing all six types, so every character appears without an unlucky random streak. Each target occupies one of A1–D4: a row letter followed by a column number. Its answer interface appears immediately; there is no preliminary mole click.

| Difficulty | Target countdown | Delay after the result animation |
| --- | ---: | ---: |
| Easy | 24 seconds | 1 second |
| Medium | 19 seconds | 0.75 seconds |
| Hard | 13 seconds | 0.5 seconds |

The result animation takes another 0.65 seconds. Runs themselves have no time limit. Difficulty is locked while a run is active.

## Six troublemakers

### Regular: drag the hammer

Pick up the hammer in the answer panel, drag it onto the mole, and release. A valid drop scores immediately; no submit button is needed. A missed drop can be retried before the countdown expires. Clicking the mole alone does not score.

Keyboard alternative: focus the hammer and press Enter. This picks it up and focuses the mole. Press Enter again to drop it. Pausing, stopping, or changing targets cancels a held hammer.

### Einstein: locate the square

Look at the board’s row and column labels, then enter a coordinate such as `B3`. The input receives focus automatically. Letter case is ignored. Press Enter or the answer button. A wrong coordinate ends that target with a penalty.

### Painter: draw a hammer

Draw a recognizable long handle and wide head in the pad, using one or several strokes, then choose Check. Clear resets the sketch. A tiny tap is insufficient. If the drawing needs more ink, the game gives a hint and allows another try until the timer expires.

Keyboard alternative: focus the canvas. Arrow keys draw; Enter lifts the pen so the next arrow begins another stroke. Clear also resets the keyboard pen position.

The drawing check measures horizontal and vertical coverage rather than running an image-recognition service. See the development guide for its limits.

### Coder: match the shortcut

Press the displayed Shift + letter combination, or enter that letter in the focused field. Submit with Enter or the answer button. A mismatched letter ends the target with a penalty.

### Wheel: turn it upright

Use the left and right rotation arrows to make the hamster visually upright, then choose Verify. The controls rotate it in equal steps; no numerical angle is shown. A sideways submission ends the target with a penalty.

### Magician: remember the spell

Watch the three-symbol spell for 2.2 seconds. It then disappears. Repeat the same three symbols in order using the four symbol buttons, or keys 1–4:

| Key | Symbol | Name |
| --- | --- | --- |
| 1 | ★ | Star |
| 2 | ☾ | Moon |
| 3 | ◆ | Diamond |
| 4 | ☀ | Sun |

Repeated symbols are possible. Each correct choice fills one position. The third correct choice scores immediately. A wrong symbol breaks the spell and ends the target with a penalty. The reveal period is part of the target’s countdown. Pausing freezes the reveal and countdown together.

## Scoring and records

A successful target gives **100 + 10 × the preceding streak**. Six consecutive hits give 100 + 110 + 120 + 130 + 140 + 150 = 750 points. A wrong submitted answer, skipped target, or expired countdown deducts 25 points and resets the streak. Scores cannot fall below zero.

The best indicator includes the current run. Stop saves a positive completed run in the browser’s local storage. The top three runs are ordered by highest score, then fastest elapsed time. A zero-point run is not saved. Reloading an unfinished run discards that unfinished run.

## Feedback

Every result has a comic impact caption and immediate score/streak update. Successful hits cycle through a brief board-color change, confetti, a flying exit, a spinning exit, an ink fade, and a clapping/wiggling exit with applause when sound is enabled. Misses give a short muted color change and dust particles. Effects remain inside the board, do not open extra windows, and return to the normal palette automatically.

Reduced-motion settings suppress moving confetti and large motion; score text and result captions remain. Muting sound leaves all gameplay available.

## Pause, help, and stop

- Pause freezes the run clock, target, magician reveal, and feedback timeline.
- Space pauses when focus is outside an input, button, or drawing canvas.
- Opening How to play pauses an active run; closing it resumes only if that action caused the pause.
- Hiding the tab pauses automatically. Returning to it requires an explicit resume.
- Stop saves the run and offers a new one. Escape closes the instructions dialog.

All six challenges run locally. The game does not request microphone, camera, location, or pop-up access.
