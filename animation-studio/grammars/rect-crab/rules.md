# Rect-Crab Grammar Rules

These are the design constraints for every rect-crab animation. They are written
to be pasted into an AI prompt verbatim (the tools in `animation-studio/tools/`
do this for you), and to be checkable by a human with the checklist at the end.

## The character

- The character is **Clawd**, a pixel-art crab built ONLY from rectangles.
- The canonical geometry is `base.svg` in this folder. Every animation MUST use
  these exact elements — same IDs, coordinates, sizes, and colors:
  `torso`, `left-arm`, `right-arm`, four leg rects, `left-eye`, `right-eye`,
  `ground-shadow`. Animate by applying CSS transforms and keyframes to these
  elements (or to `<g>` groups wrapping them) — do NOT redraw the character.
- **Body color:** `#DE886D` (salmon-orange). All body parts use this.
- **Eyes:** `#000000`, 1×2 unit rectangles at positions (4,8) and (10,8).
- The character's body lives at coordinates (0,0)–(15,16). The ground line is
  y=15.

## The canvas

- **ViewBox:** use `viewBox="-15 -25 45 45"` on the root `<svg>`. This gives
  empty room above and around the character for effects (sparkles, notes,
  confetti) without clipping.
- **Output size:** `width="500" height="500"` on the root `<svg>` element.

## The animation

- **Method:** pure CSS `@keyframes` inside a `<style>` element in `<defs>`.
  Transforms only: `translate`, `rotate`, `scale`, plus `opacity`.
  No JavaScript. No SMIL `<animate>` elements. No external resources.
- **Joints:** every animated group needs `transform-box: fill-box;` and a
  `transform-origin` placed at the natural joint (e.g. `0% 50%` for a right
  arm's shoulder, `50% 100%` for feet-anchored bounces).
- **Looping:** the animation must loop seamlessly (`infinite`). The first and
  last keyframes of every animation must match.
- **Duration:** keep each animation's total cycle between 1s and 8s for active
  moves; sleepy/idle moves may run up to 16s. Prefer cycle durations that
  divide evenly into each other (e.g. 0.5s, 1s, 2s, 4s) so the whole file
  loops cleanly.
- **Structure:** separate the static parts from the moving parts using `<g>`
  groups with CSS classes. Legs are usually static (same positions as
  `base.svg`) unless the move specifically needs them (jumping, walking).
- **Ground shadow:** keep `ground-shadow` on the ground line (y=15). It may
  pulse (`scaleX`) in sync with bounces or jumps, but must never leave the
  ground or change color.

## The aesthetic

- **Rectangles only.** All effects — sparkles, particles, music notes, confetti,
  tools, hats — are built from small `<rect>` elements. No circles, no ellipses,
  no paths, no curves, no gradients, no filters.
- **Pixel-art timing:** for flashing/sparkle effects, prefer `step-end` timing
  so they pop frame-by-frame instead of fading smoothly. Smooth easing
  (`ease-in-out`) is for body movement.
- **Effect colors:** free choice, but keep them bright and flat (single fill
  per rect). Suggested pixel palette: `#F87171` red, `#FBBF24` yellow,
  `#34D399` green, `#60A5FA` blue, `#F472B6` pink, `#FFFFFF` white.

## File conventions

- **File name:** `clawd-<animation-name>.svg`, lowercase, hyphen-separated
  (e.g. `clawd-dance-groove.svg`).
- The file must be a single self-contained `.svg` that plays when opened in
  any browser (double-click → it dances).

## Human checklist (after generating)

- [ ] Opens in a browser and animates immediately, no console errors.
- [ ] Loops without a visible "jump" at the end of the cycle.
- [ ] Clawd still looks like Clawd: salmon rectangles, black rectangle eyes.
- [ ] Nothing important gets clipped at the viewBox edges.
- [ ] No `<animate>`, `<script>`, `<image>`, or external URLs in the file.
