# Design system and artwork

## Direction and hierarchy

The visual direction is a printed 1980s American comic page: warm newsprint, visible ink contours, slanted caption strips, condensed display lettering, sparse Ben-Day dots, flat colors, and small offset print shadows. The board carries the brightest color and strongest frame. Peripheral paper panels have muted sage, slate, and brick details, with restrained grayscale portraits.

The composition has three columns: controls/status/records on the left, the square playfield in the center, and the current answer plus field guide on the right. The header is compact. The footer contains only `16 HOLES. ZERO MERCY.` The removed promotional sentence and footer ornament are not part of the interface.

The visual reference is `design/whack-square-comic-concept.png`. The implementation preserves its square center, quiet comic rails, angled caption strips, warm paper, and cast of moles. Practical differences are deliberate: actual saved scores replace mock content; real inputs and accessible controls replace drawn controls; row/column labels and a result strip sit outside the square; original character art is reused; the existing hit, pause, and countdown behavior remains functional. The idle answer panel explains where the next challenge will appear.

## Square geometry

For a viewport height V:

- The shell reserves 148 pixels for padding, header, footer, and gaps.
- Workspace/board-frame height H = V − 148.
- Board-frame width W = H − 42.
- Borders use 6 pixels in each dimension.
- The column-label header uses 38 pixels and the result footer uses 42 pixels.
- The row-label axis uses 38 pixels of width.

Therefore the grid height is H − 6 − 38 − 42 = H − 86, and its width is W − 6 − 38 = H − 86. The four equal columns and four equal rows consequently produce square cells. No padding is applied inside `.mole-grid`.

At 1600×900, the grid is 666×666 CSS pixels and each cell is 166.5×166.5. At 1280×720 the intended grid is 486×486; at 1920×1080 it is 846×846. The surrounding frame is taller than it is wide because its axes and result strip are outside the square. This is intentional.

## Tokens

| Role | Value | Use |
| --- | --- | --- |
| Ink | `#292d26` | Board frame, main text, character contours |
| Newsprint | `#cfc4ac` | Page background |
| Panel paper | `#ded5bd` | Secondary panels |
| Light paper | `#eee4cd` | Dialogs and focused content |
| Board gold | `#f2d269` | Primary playfield |
| Muted text | `#4c5446` | Essential secondary text |
| Sage | `#b7bba3` | Comic caption strips |
| Brick | `#9f5e4a` | Primary buttons and wordmark |
| Slate | `#647a77` | Supporting accent/focus |

The palette is adapted from [Solitaire’s Retro Comic palette on Lospec](https://lospec.com/palette-list/retro-comic). Keep the board more saturated than the rails. Do not dim an entire panel with an opacity overlay: use intentional surface and text colors so controls remain legible.

Bangers supplies the comic headings, labels, and large numerals. Barlow Condensed supplies prose and hints. Both use system fallbacks. Controls have explicit font sizes. Shapes use hard edges or intentional comic skew; circular controls are reserved for rotation arrows.

## Motion and feedback

Animation communicates a new target, a result, or direct manipulation. It does not animate the whole interface continuously. The idle mole has a subtle occasional wiggle. New targets pop up; answer panels enter briefly. Hammer dragging shows a pointer-following icon and a valid drop outline.

Successful results cycle through board color, confetti, fly, spin, fade, and clap. Failure uses a brief muted tint and dust. Large feedback stays inside the board. All transient effects clean up on expiry, restart, or stop. Pause freezes the effect timeline and CSS animation playback. Reduced-motion preferences omit particles and shorten movement while preserving captions and scores.

## Artwork and asset provenance

| Asset | Source and purpose |
| --- | --- |
| `public/assets/mole-sprite-sheet.png` | Existing project art, reused for Regular, Einstein, Painter, Coder, and Wheel. The old sixth crop is unused. |
| `public/assets/magician-mole.png` | New transparent character generated with the built-in ImageGen tool, using the existing sheet as a style reference. |
| `design/whack-square-comic-concept.png` | Revised full-screen comic layout generated with the built-in ImageGen tool. |
| Hammer SVG in `game.js` | Code-native draggable tool icon; no bitmap UI screenshot is used. |
| Paper/dot textures in CSS | Small code-native print textures, with no remote image dependency. |

The Magician prompt requested one frontal brown mole with buck teeth and an orange nose, a purple top hat/cape, a wand, and floating cards bearing a star, crescent, and diamond. It specified bold irregular ink outlines, Ben-Day dots, transparent background, a square composition, no lettering, and readability at small sizes. Its game mechanic is a disappearing three-symbol memory spell.

The layout concept prompt specified a 16:9 desktop screen, a genuinely square 4×4 center, two narrow muted comic rails, no human illustrations or invented player records, original mole portraits, and only the requested footer. Generated concept text is a visual reference; product rules and truthful copy are maintained in HTML and the gameplay guide.

## Principles behind the choices

- Make the main task largest; use saturation and contrast to guide attention: [NN/g, Visual Hierarchy in UX](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/).
- Keep the relevant action visible instead of requiring a remembered opening step: [NN/g, Recognition and Recall](https://www.nngroup.com/articles/recognition-and-recall/). All answer panels open on spawn. The Magician’s memory requirement is the explicit game challenge, not hidden navigation.
- Give immediate status and action feedback: [NN/g, Visibility of System Status](https://www.nngroup.com/articles/visibility-system-status/). Countdown, drop targeting, scores, and result captions remain visible.
