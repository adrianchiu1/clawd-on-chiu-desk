#!/usr/bin/env python3
"""Generate a new animation with the Claude CLI, end to end.

This is the "one command path" of Mode 1. It builds the same prompt as
build_prompt.py, sends it to the `claude` CLI in headless mode, extracts the
SVG from the response, and saves it into animation-studio/output/.

Requires the Claude Code CLI to be installed and logged in (`claude --version`
to check). No CLI? Use tools/build_prompt.py instead — same result via
copy-paste into claude.ai.

Usage:
    python3 tools/claude_animate.py dance-spin "Clawd spins in a happy circle, claws out, sparkles popping"
    python3 tools/claude_animate.py flap-hop "..." --grammar rect-bird
    python3 tools/claude_animate.py dance-spin "..." --model opus
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_prompt import STUDIO_ROOT, build_prompt, load_grammar  # noqa: E402


def extract_svg(text: str):
    """Pull the SVG markup out of the model's response."""
    fenced = re.search(r"```(?:svg|xml|html)?\s*\n(<svg\b.*?</svg>)\s*\n?```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    bare = re.search(r"<svg\b.*?</svg>", text, re.DOTALL)
    return bare.group(0) if bare else None


def sanity_check(svg_text: str):
    """Cheap safety/quality checks before writing the file. Returns warnings."""
    warnings = []
    lowered = svg_text.lower()
    for banned, why in [
        ("<script", "contains a <script> element"),
        ("<image", "references an external image"),
        ("<animate", "uses SMIL <animate> instead of CSS keyframes"),
        ("http://", "references an external URL"),
        ("https://", "references an external URL"),
    ]:
        # the xmlns namespace declaration is the one legitimate URL
        if banned in lowered.replace("http://www.w3.org/2000/svg", ""):
            warnings.append(f"generated SVG {why}")
    if "@keyframes" not in svg_text:
        warnings.append("generated SVG has no @keyframes — it may not animate")
    return warnings


def call_claude(prompt: str, model: str | None, timeout: int) -> str:
    cmd = ["claude", "-p", prompt]
    if model:
        cmd += ["--model", model]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise SystemExit(
            "The `claude` CLI is not installed (or not on PATH).\n"
            "No problem — use the copy-paste path instead:\n"
            "  python3 tools/build_prompt.py <name> \"<description>\"\n"
            "then paste the prompt file into claude.ai."
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"Claude did not answer within {timeout}s — try again, or use build_prompt.py.")
    if result.returncode != 0:
        raise SystemExit(f"claude CLI failed:\n{result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="animation name, lowercase-hyphenated (e.g. dance-spin)")
    parser.add_argument("description", help="what the animation should look like, in plain words")
    parser.add_argument("--grammar", default="rect-crab", help="grammar pack id (default: rect-crab)")
    parser.add_argument("--example", help="path to an example SVG to include in the prompt")
    parser.add_argument("--model", help="model override passed to the claude CLI (e.g. opus, sonnet)")
    parser.add_argument("--out", help="output file (default: animation-studio/output/<prefix>-<name>.svg)")
    parser.add_argument("--timeout", type=int, default=300, help="seconds to wait for the model (default 300)")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.name):
        raise SystemExit("Name must be lowercase letters/numbers with hyphens, e.g. dance-spin")

    grammar = load_grammar(args.grammar)
    example_svg = ""
    example_path = Path(args.example) if args.example else grammar["example_path"]
    if example_path and Path(example_path).exists():
        example_svg = Path(example_path).read_text(encoding="utf-8")

    prompt = build_prompt(grammar, args.name, args.description, example_svg)
    print(f"Asking Claude for '{args.name}' ({args.grammar})... this can take a minute.")
    response = call_claude(prompt, args.model, args.timeout)

    svg = extract_svg(response)
    if not svg:
        raise SystemExit(
            "Could not find an <svg>...</svg> block in Claude's response.\n"
            "Run again, or use build_prompt.py and paste into claude.ai instead."
        )

    for warning in sanity_check(svg):
        print(f"WARNING: {warning}")

    prefix = grammar["meta"].get("filePrefix", "anim")
    out = Path(args.out) if args.out else STUDIO_ROOT / "output" / f"{prefix}-{args.name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg if svg.endswith("\n") else svg + "\n", encoding="utf-8")

    print(f"Saved: {out}")
    print()
    print("Now check it (the human checklist from the grammar's rules.md):")
    print("  1. Double-click the file — it should animate in your browser.")
    print("  2. Watch one full loop: no visible jump at the loop point?")
    print("  3. Still looks like the character? Nothing clipped at the edges?")
    print()
    print("Want changes? Run the command again with a better description —")
    print("e.g. add 'faster', 'more sparkles', 'bigger jumps' to it.")


if __name__ == "__main__":
    main()
