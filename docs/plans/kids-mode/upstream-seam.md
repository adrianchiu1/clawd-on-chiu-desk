# Upstream Seam Manifest

Every upstream (non-`src/kids/`, non-`src/llm/`) file that Kids Mode modifies, with
rationale. Keep this list short — it is the price of every upstream merge. Review at each
merge from the public Clawd fork; if it grows beyond ~6 files, revisit the extraction exit
criteria in `README.md`.

Rules:
- New behavior goes in `src/kids/` / `src/llm/`; upstream files get *wiring only* (a require,
  a registration call, a schema entry), never kids logic.
- All pet-internal access goes through `src/kids/pet-adapter.js` (see Stage 1 spec).

## Anticipated seam (Stage 1 — implementer: replace with the actual list in your PR)

| Upstream file | Change | Why |
|---|---|---|
| `src/prefs.js` | add `kidsMode` schema block + migration | settings persistence |
| `src/settings-actions.js` | validators/commands for kidsMode fields | settings write path |
| `src/settings-renderer.js` + `settings.html` | Kids Mode settings page | parent configuration UI |
| `src/menu.js` | tray items: open chat, enter/exit Kids Mode | entry points |
| `src/main.js` | wire kids-mode module init + window lifecycle | app glue (keep to a few lines) |
| `src/hit-renderer.js` or click routing | route pet single-click to chat box in Kids Mode | summon gesture |

## Actual seam

_(maintained by implementation PRs; empty until Stage 1 lands)_
