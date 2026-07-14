# Animation Studio — Development Spec

This document is the authoritative spec for the `animation-studio/` system. It
is written so that a developer — human or AI, including smaller models — can
extend the studio without reading the rest of the codebase. Follow it
literally; every contract has an acceptance checklist.

Provenance: the pipeline design (base puppet + rules + example + AI prompt)
is adapted from the MIT-licensed
[clawd-tank](https://github.com/marciogranzotto/clawd-tank) project's
animation tooling.

---

## 1. Overview

The studio produces **animated SVG files**: single self-contained `.svg` files
that animate in any browser using CSS `@keyframes` only (no JavaScript, no
SMIL, no external resources). These are the same format the desktop app's pet
uses (`assets/svg/`, `themes/*/assets/`).

Three modes, three audiences:

| Mode | What | Who | Guide |
|------|------|-----|-------|
| 1 | Create a new animation inside an existing grammar | Kids (8+) with an adult | `guides/mode1-make-clawd-dance.pdf` |
| 2 | Create a new grammar (a new character family) | Teens | `guides/mode2-invent-a-creature.pdf` |
| 3 | Load animations into the installed app; test; release | Adults | `guides/mode3-ship-it.pdf` |

Directory contract:

```
animation-studio/
  SPEC.md                 ← this file
  README.md               ← map + quickstart
  grammars/<id>/          ← one folder per grammar pack (see §2)
  tools/studio.py         ← Mode 1, interactive Idea Card page (localhost server)
  tools/build_prompt.py   ← Mode 1, copy-paste path
  tools/claude_animate.py ← Mode 1, one-command path (claude CLI)
  guides/                 ← PDFs + HTML sources (guides/src/)
  output/                 ← where new prompts and animations land (gitignored content is fine to keep)
```

---

## 2. Grammar pack contract (consumed by Mode 1, produced by Mode 2)

A grammar pack is a folder `animation-studio/grammars/<id>/` containing:

| File | Required | Purpose |
|------|----------|---------|
| `grammar.json` | yes | Machine-readable metadata (schema below) |
| `base.svg` | yes | The canonical puppet: the character drawn once, static, every part a named element |
| `rules.md` | yes | Design constraints, written to be pasted into an AI prompt verbatim; must end with a human checklist |
| `PLANS.md` | no | Design briefs; tools attach the section whose heading best matches the animation name |
| `plans-template.md` | no | Blank "Idea Card" for directors to fill in |
| `examples/*.svg` | ≥1 | Complete working animations in this grammar |

`grammar.json` schema (all fields required unless noted):

```json
{
  "schemaVersion": 1,
  "id": "rect-crab",                      // must equal the folder name
  "name": "Rect-Crab (Clawd)",            // human-readable
  "characterName": "Clawd",               // used in prompt text
  "filePrefix": "clawd",                  // output files: <filePrefix>-<name>.svg
  "tier": "rect",                         // "rect" (beginner) or "curve" (advanced, §4.3)
  "animationViewBox": "-15 -25 45 45",    // viewBox animations must use
  "outputWidth": 500,
  "outputHeight": 500,
  "defaultExample": "examples/....svg",   // optional; falls back to first file in examples/
  "notes": ""                             // optional
}
```

**Acceptance checklist for a grammar pack** (Mode 2's definition of done):

- [ ] `python3 tools/build_prompt.py test-idea "a simple test" --grammar <id>` runs without error.
- [ ] `base.svg` opens in a browser and shows the full character, nothing clipped.
- [ ] Every part that could ever move is its own `<rect>`/`<g>` with an `id`.
- [ ] `rules.md` states: canvas viewBox, output size, palette, allowed shapes,
      animation method (CSS keyframes only), looping rule, file naming, and a
      human checklist.
- [ ] At least one example in `examples/` passes the animation acceptance
      checklist (§3.3).
- [ ] Feeding the pack through Mode 1 with a one-sentence description produces
      a recognizable on-model animation. (This is the real test.)

---

## 3. Mode 1 — create an animation in an existing grammar

### 3.1 Copy-paste path (no setup, any AI chat)

1. Director fills in the Idea Card (`grammars/<id>/plans-template.md`):
   Action / Body Mechanics / Eyes / Effects, plus a lowercase-hyphen name.
2. Run: `python3 tools/build_prompt.py <name> "<the four answers as one or two sentences>" --grammar <id>`
   → writes `output/<name>.prompt.txt`.
3. Paste the whole prompt file into claude.ai (or any capable AI chat).
4. Save the returned SVG as `output/<filePrefix>-<name>.svg`.
5. Double-click the file → it must animate in the browser.
6. Iterate: re-ask with adjustments ("faster", "more sparkles"). Keep the
   conversation going — the model retains the rules.

### 3.2 One-command path (claude CLI installed)

```
python3 tools/claude_animate.py <name> "<description>" [--grammar <id>] [--model opus]
```

Builds the same prompt, calls `claude -p`, extracts the SVG, runs sanity
checks (§3.4), and saves to `output/`. On any failure it points the user to
the copy-paste path.

### 3.3 Animation acceptance checklist (applies to every produced SVG)

- [ ] Single self-contained `.svg`; animates when opened in a browser.
- [ ] CSS `@keyframes` only — reject if it contains `<script>`, `<animate>`
      (SMIL), `<image>`, or any external URL other than the SVG xmlns.
- [ ] Loops seamlessly: first and last keyframes of every animation match.
- [ ] Uses the grammar's viewBox and output size.
- [ ] The character's canonical parts are present and unmodified in geometry
      (transforms move them; attributes don't change).
- [ ] Nothing important clips at the viewBox edges during the full cycle.

### 3.4 Automated sanity checks (implemented in `claude_animate.py`)

`sanity_check()` warns on: `<script>`, `<image>`, SMIL `<animate>`, external
URLs, and missing `@keyframes`. Warnings print but do not block the write —
the human checklist is the gate.

### 3.5 Interactive path: the Studio page (`tools/studio.py`)

A stdlib-only local web server that wraps §3.1/§3.2 in a kid-operable UI.
`python3 tools/studio.py` → binds **127.0.0.1** (never 0.0.0.0) on port 8787
(`--port` to change, `--no-browser` to suppress auto-open).

Flow: the page shows the Idea Card (grammar picker, name, the four questions,
speed/mood chips). On submit the server:

1. validates the name (`^[a-z0-9]+(-[a-z0-9]+)*$`) and required fields;
2. registers the spec at `output/specs/<name>.json` — all form fields plus
   the assembled `description` and a UTC `created` timestamp;
3. writes the prompt to `output/<name>.prompt.txt`;
4. if the `claude` CLI is on PATH (and `forcePaste` was not set): runs the
   generation in a background thread; the page polls and then renders the
   result inline. Otherwise: returns the prompt for copy-paste into claude.ai
   with a paste-back box that saves + renders identically.

HTTP API (all JSON):

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | The Idea Card page (grammar options injected server-side) |
| `/api/create` | POST | Spec in → `{mode:"claude", job}` or `{mode:"paste", prompt, name, prefix}` |
| `/api/status?job=<id>` | GET | `{state: running\|done\|error, svgUrl?, file?, warnings?, error?}` |
| `/api/paste` | POST | `{name, grammar, svg}` → extract, sanity-check, save, `{svgUrl, file, warnings}` |
| `/output/<file>.svg` | GET | Serves generated SVGs (only `.svg`, only directly in `output/`) |

Security invariants: localhost bind only; name regex blocks path tricks; the
SVG route rejects subpaths and non-`.svg`; served SVGs get a
`Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'`
header and are embedded via `<img>` (no script execution) — generated files
are still only *warned* about by `sanity_check`, so the CSP is the real gate.

### 3.6 Extending Mode 1 (future work, in priority order)

1. `tools/preview.py`: screenshot an SVG at N timestamps with headless
   Chromium (`chromium --headless --screenshot`) for a quick strip preview.
2. GIF recorder: port clawd-tank's `svg2frames.py` + `record_gif.py`
   (Playwright + Pillow) — deliberately out of scope now (adds dependencies).
3. Studio page: "remix an existing spec" — list `output/specs/*.json` and
   pre-fill the form from one.

---

## 4. Mode 2 — create a new grammar (new character family)

Follow this procedure exactly; the output is a grammar pack per §2.

### 4.1 Procedure (Tier "rect" — the beginner tier)

1. **Design the puppet on grid paper.** ~15×16 logical units. Rectangles
   only. Give the character: a torso, ≥2 limbs, eyes, and a ground shadow.
   Fewer, bigger rectangles animate better than many small ones.
2. **Write `base.svg`.** viewBox tight around the character (e.g.
   `"0 0 15 16"`); one `<rect>` per part; every part gets an `id`
   (`torso`, `left-wing`, …); group body-colored parts in a `<g fill="...">`.
   Copy the structure of `grammars/rect-crab/base.svg`.
3. **Choose the animation canvas.** Pad the base viewBox by ~15 units left/
   right and ~25 above (room for effects): rect-crab uses `"-15 -25 45 45"`.
4. **Write `rules.md`.** Copy `grammars/rect-crab/rules.md` and edit: body
   color(s), eye spec, part list, ground line, character-specific advice
   (e.g. a bird's feet leave the ground; a crab's don't). Keep every generic
   rule (CSS-only, seamless loop, rect-only, naming, checklist).
5. **Write `grammar.json`** per §2. `tier: "rect"`.
6. **Create the first example the honest way:** run your own pack through
   Mode 1 (`--grammar <id>`). If the result is off-model, your `rules.md` is
   under-specified — fix the rules, not just the SVG. Iterate until one
   passes §3.3, then save it into `examples/`.
7. **Optionally add `PLANS.md`** with 3+ briefs and `plans-template.md`
   (copy and re-skin rect-crab's).
8. Run the §2 acceptance checklist.

### 4.2 Design guidance that makes grammars animate well

- Anchor the character to a ground line; state it in the rules.
- Name parts by their joint ("left-arm" pivoting at the shoulder), and say in
  the rules where each joint's `transform-origin` belongs.
- Puppet complexity budget: 6–12 rects. Below 6 it can't emote; above ~12 the
  AI starts losing parts.
- Pick one memorable silhouette trait (crab: wide flat torso + side claws;
  bird: round body + beak wedge... but in rects: a 2×1 beak).

### 4.3 Tier "curve" — the advanced tier (e.g. 90s-anime styles)

Everything in §4.1 applies, plus:

- `base.svg` may use `<path>`, `<circle>`, `<ellipse>`, rounded rects.
- `rules.md` MUST additionally pin down: outline treatment (stroke width +
  color on every shape, e.g. `stroke="#222" stroke-width="0.6"`), the full
  fill palette including shading tones (cel-shading = one flat shade tone per
  color, no gradients — gradients stay banned), and any recurring stylistic
  marks (blush ovals, sparkle highlights in eyes).
- Keep the same animation rules: CSS keyframes only, transforms on grouped
  parts, seamless loops. Curves change the *drawing*, not the *animating*.
- Expect more Mode 1 iterations; curve grammars should ship 2–3 examples
  because the AI needs more style evidence.

---

## 5. Mode 3 — into the app, testing, releasing

Two integration paths exist. **Path A needs no release. Path B is the
baked-into-a-release path.**

### 5.1 Path A — user theme (instant, no rebuild)

The app loads user themes from `{userData}/themes/<theme-id>/`:

- Windows: `%APPDATA%\clawd-on-desk\themes\<theme-id>\`
- macOS: `~/Library/Application Support/clawd-on-desk/themes/<theme-id>/`
- Linux: `~/.config/clawd-on-desk/themes/<theme-id>/`

Procedure:

1. Create the folder with a `theme.json` and an `assets/` subfolder holding
   the SVGs. Start from `themes/template/theme.json` (in this repo) — it is a
   commented scaffold.
2. Minimum required states (`src/theme-schema.js` → `REQUIRED_STATES`):
   `idle`, `working`, `thinking`. Everything else is optional and degrades
   to `idle` (or uses `fallbackTo` where allowed). Use
   `"sleepSequence": { "mode": "direct" }` to avoid needing the four
   full-sleep states.
3. Restart the app (or switch themes back and forth) → the theme appears in
   Settings → Theme.

This is the right path for a kid's new grammar family (rect-bird as a theme)
and for quickly trying animations on the live pet.

### 5.2 Path B — change the built-in theme (baked, released)

1. Copy the new SVG into `assets/svg/` in the repo.
2. Map it in `themes/clawd/theme.json`: add the filename to an existing
   state's array (arrays = the app picks among them), or replace the current
   file for that state. Assets-only — adding a brand-new *state* needs app
   code and is out of scope for this spec.
3. Test from a clone (§5.3), then release (§5.4).

### 5.3 Testing procedure

1. **Browser pass:** open the SVG directly; run the §3.3 checklist.
2. **Live app pass:** from a repo clone, `npm install && npm start`.
   - `idle`: just wait, hands off.
   - `working`/`thinking`: start a real Claude Code session in a hooked
     terminal, or temporarily map your file to `idle` for instant viewing.
   - Dance states (this fork's desktop-activity feature): set
     `CLAWD_ACTIVITY_DANCE_FORCE_TIER=1` (or `2`) in the environment before
     `npm start` to pin the dance tier regardless of real activity.
3. **Size pass:** in app Settings, try smallest and largest pet size — pixel
   details can vanish when small; check the silhouette still reads.

### 5.4 Release runbook (fork: adrianchiu1/clawd-on-chiu-desk)

The installed app auto-updates from this fork's **GitHub Releases** (never
from branches). See `.github/workflows/build.yml`.

1. Bump `"version"` in `package.json` (e.g. `0.11.0` → `0.11.1`). Mandatory —
   the updater only acts on a higher version.
2. Write `docs/releases/release-v<version>.md` (release notes). Mandatory —
   the CI release step reads exactly this path and fails without it.
3. Commit to `main`, then: `git tag v<version> && git push origin main v<version>`.
4. CI builds Windows/macOS/Linux installers and creates a **draft** release.
5. Publish the draft on the GitHub Releases page. Drafts are invisible to the
   updater.
6. Installed apps see it on their next check (or tray → Check for Updates).

Caveats: macOS won't auto-install unsigned builds (users download manually);
running-from-clone installs update via `git pull` instead (tray → Check for
Updates does this automatically when not packaged).

---

## 6. Invariants (do not break these when extending)

1. Output SVGs must animate with **zero** external dependencies — the app's
   low-power mode pauses animations via `animation-play-state`, and its loop
   detection (`src/animation-cycle.js`) reads CSS keyframes; both assume
   CSS-driven animation.
2. Tools stay Python 3 stdlib-only.
3. Grammar packs are self-contained: no file in `grammars/<a>/` may reference
   `grammars/<b>/`.
4. Kid-facing flows must never require editing JSON or app code — that is
   Mode 3, adult territory.
