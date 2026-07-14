# 🎨 Animation Studio

Make new animations for Clawd (and invent whole new characters) — designed so
the whole family can join in.

| I want to… | Go to |
|------------|-------|
| **Make Clawd do a new dance** (kids 8+, with an adult) | `guides/mode1-make-clawd-dance.pdf` |
| **Invent a new creature** — a whole new character family (teens) | `guides/mode2-invent-a-creature.pdf` |
| **Put an animation into the real app** / test / release (adults) | `guides/mode3-ship-it.pdf` |
| **Extend the studio itself** (developers & AI agents) | `SPEC.md` |

## 60-second quickstart

```bash
# The Studio page — the family-friendly way. Opens an Idea Card in the
# browser; fill it in, press the button, watch the dance appear on the page:
python3 tools/studio.py

# — or from the command line:
python3 tools/claude_animate.py dance-spin "Clawd spins happily with sparkles popping around him"

# — or with no Claude CLI at all: build the prompt, paste it into claude.ai,
#   save the returned SVG into output/ and double-click it:
python3 tools/build_prompt.py dance-spin "Clawd spins happily with sparkles popping around him"
```

## What's in here

```
grammars/rect-crab/   The original pixel-crab: base puppet, design rules,
                      idea cards, plans, and two ready-made dance examples
                      (open examples/*.svg in a browser!)
tools/                studio.py (the interactive Idea Card page),
                      build_prompt.py (copy-paste path) and
                      claude_animate.py (claude CLI path)
guides/               Step-by-step PDFs for each mode, English + 中文
output/               Your new prompts and animations land here
SPEC.md               The full development spec (grammar pack contract,
                      acceptance checklists, release runbook)
```

Pipeline design adapted from the MIT-licensed
[clawd-tank](https://github.com/marciogranzotto/clawd-tank) project.
