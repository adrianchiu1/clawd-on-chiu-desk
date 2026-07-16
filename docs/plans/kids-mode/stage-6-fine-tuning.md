# Stage 6 — Fine-Tuning (optional, exploratory)

Style-tune a local model on curated Clawd conversations so the 8B brain sounds like Clawd
without leaning on a huge prompt. This stage is **gated**: only start it after months of
real usage have produced enough curated transcripts, and only if prompt-based personality
on the local model measurably lags Haiku on the eval harness. It may turn out unnecessary —
that is a fine outcome.

Depends on: Stage 2 (eval harness — the gate), Stage 3 (transcripts at volume), Stage 5
(memory proves what does NOT need to be in weights).

## Principles (non-negotiable)

1. **Style only, never knowledge, never family data.** The tune teaches voice, format
   compliance (wire protocol), answer-then-thread reflexes, and stance behaviors. All
   personal content (names, family facts, kid interests) is scrubbed from training data
   and continues to come from the memory layer at runtime. Weights are shareable-safe:
   if the LoRA leaked, it would reveal personality, not people.
2. **The eval harness is the gate.** A tune ships only if it beats the same base model +
   prompt on charter axes without regressing safety. Report committed alongside the adapter.
3. **Reversible.** LoRA adapters, versioned; base model untouched; one settings change rolls back.

## Pipeline

### 1. Dataset builder (`tools/kids-finetune/build-dataset.js`)

- Input: transcript JSONL + a curation list (`curated-sessions.txt` — session IDs the parent
  starred in the dashboard; add a ⭐ affordance to the transcript view as part of this stage).
- Transform each turn into chat-format training rows: system = the *short* target prompt
  (a compressed charter — the tune's job is to make the long one unnecessary), user = kid
  message, assistant = full wire-protocol reply (header + body — format compliance is one
  of the main things we're training).
- **Scrubbing pass** (pure, unit-tested, runs before anything else): replace kid names with
  rotating placeholder names, strip anything matching family-facts content (literal +
  fuzzy), drop `sensitive` and `feelings` bucket turns entirely, drop guard-flagged turns.
  A manual review file (`dataset-review.md`, every row rendered) must be eyeballed before
  training — the tool forces this by requiring `--reviewed` with the file's hash.
- Optional augmentation: generate additional synthetic rows by having the judge-grade model
  rewrite curated answers into new topics (keeps voice, broadens coverage). Synthetic rows
  are marked and capped at 50% of the dataset.
- Target: 300–1000 rows. Below ~200, stop — not enough signal, revisit later.

### 2. Training recipe (documented, not automated in-app)

- Method: QLoRA (4-bit base, LoRA rank 16, lr ~2e-4, 2–3 epochs) via Unsloth or Axolotl.
- Hardware honesty for the RTX 5060 (8GB): QLoRA on an 8B with short sequences (≤2k) fits
  but is slow (hours, fine overnight) and fragile on VRAM — close everything else, or
  simply rent a cloud GPU for ~$5–10 (an A10/4090 hour-scale job). **Training data leaving
  the machine is acceptable ONLY because of the scrubbing pass** — this is exactly why
  principle 1 exists; call it out in the runbook and have the parent re-confirm the review
  step before any cloud upload. Local-only remains the default recommendation.
- Output: LoRA adapter → merge or load-time apply → quantize → `ollama create clawd-8b`
  with a Modelfile (committed template) → appears in the Brain panel like any model.
- Deliverable: `docs/guides/kids-finetune-runbook.md` (+ PDF via the Stage 2 build command)
  walking through dataset build → review → train (local and cloud variants) → package →
  eval → rollback.

### 3. Evaluation gate

Run the full eval suite (charter axes + safety + search-protocol + memory) on:
base+long-prompt vs tuned+short-prompt vs tuned+long-prompt. Ship criteria: tuned model ≥
base on voice/format/answer-then-thread, no safety regression, wire-protocol compliance
≥99% (format breakage is the classic fine-tune failure — it's specifically scored).
Then A/B with the kids in Brain Lab — their preference is a first-class result.

## Acceptance criteria

1. Dataset builder produces a scrubbed, reviewed dataset from starred sessions; scrubbing
   verified by unit fixtures (planted names/facts do not survive).
2. Runbook executed end-to-end at least once, producing `clawd-8b` selectable in Settings.
3. Eval report shows the gate passing (or the honest conclusion that prompting wins — in
   which case this stage closes with the report and no shipped tune).
4. Rollback = switch model in Brain panel; nothing else changed.

## Out of scope / future

Photos and multimodal memory; full-parameter tunes; RLHF-style preference training on
family reactions; continual retraining automation. Each needs its own plan + safety review.
