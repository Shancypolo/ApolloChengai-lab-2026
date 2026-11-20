# WHACK! 4×4 — Mole Mayhem

A standalone comic-book arcade for a 16:9 desktop screen. A square 4×4 playfield, six different mole challenges, animated hit reactions, and local high scores. The game uses HTML, CSS, JavaScript, and Python’s standard library. There is no build step, package installation, account, or browser permission request.

## Start the game

From the repository root:

```sh
python3 Task2b/run.py
```

Or open `Task2b/run.py` in your Python editor and press Run. The launcher starts a local server and opens the game in your default browser. Keep the Python program running while playing. Press Ctrl+C in its terminal to stop it.

From inside this folder, the command is `python3 run.py`. If you run it from another directory, supply the path to `run.py`; the launcher still finds its own game files.

Optional arguments:

```sh
python3 Task2b/run.py --port 4180
python3 Task2b/run.py --no-browser
python3 Task2b/run.py --port 0 --no-browser
```

The preferred port is 4175. If occupied, the launcher selects a free port and prints the actual URL. Port 0 explicitly requests a free port. The server binds only to this computer. The browser opens after the socket is ready, and reloads always fetch current files.

## Play

Choose a difficulty, press **Let’s play**, and follow the automatically opened answer panel. Drag the hammer for regular moles, find Einstein’s coordinates, draw for Painter, match Coder’s shortcut, turn Wheel upright, and remember Magician’s disappearing spell.

Runs have no overall time limit. Each target has its own countdown. The stop button saves the completed run; pause freezes both the run clock and the target. All six characters are available immediately, including the new Magician Mole. No microphone is used.

## Documentation

- [Game rules and controls](docs/GAMEPLAY.md)
- [Design system and artwork](docs/DESIGN.md)
- [Architecture, launcher, and maintenance](docs/DEVELOPMENT.md)
- [Verification and regression checklist](docs/TESTING.md)

## Files

```text
Task2b/
├── run.py                       # One-command local launcher
├── index.html                   # Semantic interface and instructions
├── style.css                    # Comic design, square grid, and effects
├── game.js                      # Game state and all six challenges
├── public/assets/
│   ├── mole-sprite-sheet.png     # Original character art
│   └── magician-mole.png         # New transparent character art
├── design/                      # Visual concept references
└── docs/                        # Rules, design, maintenance, verification
```

Recommended viewport: 1280×720, 1600×900, or 1920×1080. The layout is intentionally designed for desktop rather than mobile. Chrome is the primary verified browser; other current desktop browsers should support the standard APIs used.

## Troubleshooting

- **The browser did not open:** copy the printed URL into your browser. Keep the launcher running.
- **The preferred port is busy:** use the alternative URL printed by the launcher.
- **The page is unavailable:** check that the Python process is still running and that you used its exact URL.
- **Scores seem missing:** scores belong to the browser and exact origin (host and port). A different host, port, browser profile, or private window has separate storage.
- **Audio is silent:** enable the sound control and check the browser/system volume. Sound is optional; every challenge also works visually.
- **Files look outdated:** reload. The launcher sends `Cache-Control: no-store`.
- **The page is clipped:** use a 16:9 desktop window at normal browser zoom. Use the full screen if browser chrome leaves little vertical space.
