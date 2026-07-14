#!/usr/bin/env python3
"""Build an AI prompt for creating a new animation in a chosen grammar.

This is the "copy-paste path" of Mode 1: it assembles everything the AI needs
(base puppet SVG + design rules + one worked example + your idea) into a single
prompt file. Paste that file's contents into claude.ai (or any capable AI
chat), and save the SVG it returns into animation-studio/output/.

No dependencies beyond the Python 3 standard library.

Usage:
    python3 tools/build_prompt.py dance-spin "Clawd spins in a happy circle, claws out, sparkles popping"
    python3 tools/build_prompt.py flap-hop "..." --grammar rect-bird
    python3 tools/build_prompt.py dance-spin "..." --example grammars/rect-crab/examples/clawd-dance-party.svg
    python3 tools/build_prompt.py dance-spin "..." --print

The prompt is written to animation-studio/output/<name>.prompt.txt unless
--out or --print is given.
"""

import argparse
import json
import re
import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent.parent


def load_grammar(grammar_id: str) -> dict:
    """Load a grammar pack: grammar.json + base.svg + rules.md (+ PLANS.md)."""
    gdir = STUDIO_ROOT / "grammars" / grammar_id
    meta_path = gdir / "grammar.json"
    if not meta_path.exists():
        available = sorted(p.name for p in (STUDIO_ROOT / "grammars").iterdir() if p.is_dir())
        raise SystemExit(
            f"Unknown grammar '{grammar_id}'. Available grammars: {', '.join(available)}"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    base_path = gdir / "base.svg"
    rules_path = gdir / "rules.md"
    for required in (base_path, rules_path):
        if not required.exists():
            raise SystemExit(f"Grammar '{grammar_id}' is missing {required.name} — "
                             f"see animation-studio/SPEC.md for the grammar pack contract.")

    plans_path = gdir / "PLANS.md"
    example_rel = meta.get("defaultExample")
    example_path = gdir / example_rel if example_rel else None
    if example_path is None or not example_path.exists():
        candidates = sorted((gdir / "examples").glob("*.svg")) if (gdir / "examples").is_dir() else []
        example_path = candidates[0] if candidates else None

    return {
        "id": grammar_id,
        "dir": gdir,
        "meta": meta,
        "base_svg": base_path.read_text(encoding="utf-8"),
        "rules": rules_path.read_text(encoding="utf-8"),
        "plans": plans_path.read_text(encoding="utf-8") if plans_path.exists() else None,
        "example_path": example_path,
    }


def find_plan_section(plans_text: str, name: str):
    """Find the PLANS.md section that best matches the animation name."""
    search_terms = [t for t in re.split(r"[-_\s]+", name.lower()) if t]
    best_match, best_score = None, 0
    for section in re.split(r"(?=^## )", plans_text, flags=re.MULTILINE):
        section_lower = section.lower()
        score = sum(1 for term in search_terms if term in section_lower)
        if score > best_score:
            best_score, best_match = score, section.strip()
    return best_match if best_score > 0 else None


def build_prompt(grammar: dict, name: str, description: str, example_svg: str) -> str:
    meta = grammar["meta"]
    character = meta.get("characterName", "the character")
    prefix = meta.get("filePrefix", "anim")
    parts = [
        f"Create an animated SVG for the \"{meta.get('name', grammar['id'])}\" character family.",
        "",
        "## Character Base SVG",
        "",
        f"This is the canonical {character} geometry. Your animation MUST use",
        "these exact same elements with the same IDs, coordinates, sizes, and",
        "colors. Animate by applying CSS transforms and @keyframes to these",
        f"elements — do NOT redraw {character}.",
        "",
        "```svg",
        grammar["base_svg"].strip(),
        "```",
        "",
        "## Design Rules",
        "",
        "Follow every rule below. They are non-negotiable.",
        "",
        grammar["rules"].strip(),
        "",
    ]

    if example_svg:
        parts += [
            "## Example Animation",
            "",
            "Here is a complete, working animation from this family. Study its",
            "structure: how it groups parts, sets transform-origin at joints,",
            "keeps first and last keyframes identical, and builds effects from",
            "rectangles.",
            "",
            "```svg",
            example_svg.strip(),
            "```",
            "",
        ]

    if grammar["plans"]:
        section = find_plan_section(grammar["plans"], name)
        if section:
            parts += ["## Animation Plan", "", section, ""]

    parts += [
        "## Your Task",
        "",
        f"Create an animated SVG named `{prefix}-{name}.svg` with this behavior:",
        "",
        f"**{description}**",
        "",
        "Output ONLY the complete SVG markup — no explanation, no markdown",
        "fences, no commentary. Start with `<svg` and end with `</svg>`.",
    ]
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="animation name, lowercase-hyphenated (e.g. dance-spin)")
    parser.add_argument("description", help="what the animation should look like, in plain words")
    parser.add_argument("--grammar", default="rect-crab", help="grammar pack id (default: rect-crab)")
    parser.add_argument("--example", help="path to an example SVG to include (default: grammar's defaultExample)")
    parser.add_argument("--out", help="output file (default: animation-studio/output/<name>.prompt.txt)")
    parser.add_argument("--print", dest="to_stdout", action="store_true", help="print the prompt to stdout instead of writing a file")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.name):
        raise SystemExit("Name must be lowercase letters/numbers with hyphens, e.g. dance-spin")

    grammar = load_grammar(args.grammar)
    example_svg = ""
    example_path = Path(args.example) if args.example else grammar["example_path"]
    if example_path and Path(example_path).exists():
        example_svg = Path(example_path).read_text(encoding="utf-8")

    prompt = build_prompt(grammar, args.name, args.description, example_svg)

    if args.to_stdout:
        print(prompt)
        return

    out = Path(args.out) if args.out else STUDIO_ROOT / "output" / f"{args.name}.prompt.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt, encoding="utf-8")
    prefix = grammar["meta"].get("filePrefix", "anim")
    print(f"Prompt written to: {out}")
    print()
    print("Next steps:")
    print(f"  1. Open the file and copy ALL of it.")
    print(f"  2. Paste it into claude.ai (or any capable AI chat) and send.")
    print(f"  3. Copy the SVG it returns into a new file:")
    print(f"       animation-studio/output/{prefix}-{args.name}.svg")
    print(f"  4. Double-click that file — it should dance in your browser!")


if __name__ == "__main__":
    main()
