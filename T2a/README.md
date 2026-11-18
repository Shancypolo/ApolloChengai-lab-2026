# WHACK! 6×6 — Mole Mayhem

A standalone browser arcade game built for the T2a assignment. It uses six original generated characters, a 6×6 coordinate board, and six different mole-solving interactions. Runs are endless until you choose **Save & Stop**; high scores and the elapsed time at each record are saved in local storage.

## Run it

Open `index.html` in a browser, or serve this folder locally:

```sh
python3 -m http.server 4173
```

Then open `http://127.0.0.1:4173`.

Microphone permission is requested only after pressing **Enable Mic**. If it is denied or unavailable, scream moles are omitted for that run. The scream challenge combines speech recognition for “BANG” with an audio-level check; in browsers without speech recognition, it falls back to a loudness threshold. Recognition processing may use the browser's voice service. The game does not save recordings.

Browsers do not offer a general pop-up permission prompt. **Check Pop-ups** tries a user initiated test window and reports whether it opened; challenge windows work in-page if the browser blocks pop-ups.

## Contents

- `index.html`, `style.css`, `game.js` — game interface and behavior
- `public/assets/mole-sprite-sheet.png` — generated character sprites (square cells preserve their proportions)
- `design/whack-6x6-concept.png` — current interface concept
