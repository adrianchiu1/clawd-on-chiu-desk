# Stage 2 — The Local Brain

Clawd's brain can move onto the family's own hardware. Adds the OpenAI-compatible adapter
(covers Ollama / LM Studio / vLLM / llama.cpp in one shot), a model manager in Settings, a
printable PDF setup guide for the parent, a "Brain Lab" comparison mode for the kids, and the
eval harness that gates every future prompt/model change.

Target hardware (parent's machine): RTX 5060 8GB VRAM + 64GB DDR5 + 2TB SSD.
Reality check that shapes this spec: an 8B model at Q4_K_M (≈5GB) fits VRAM with room for
2–4k context; bigger contexts spill to CPU RAM (acceptable, slower). Recommended starting
models: `qwen3:8b`, `llama3.1:8b` (both strong English chat); fallback `gemma3:4b` if VRAM
headroom is needed (e.g., once the Stage 3 guard runs on GPU — spec says CPU, so usually not).

Depends on: Stage 1 (wrapper interface, chat flow). Read `README.md` hard constraints first.

## Goals

1. `src/llm/openai-compat.js` adapter (chat completions, streaming), registered as provider
   `openai-compat` with `baseUrl` + `model` + optional `apiKey`.
2. Settings "Kids Mode → Brain" panel: provider picker, model picker, connection test.
3. Ollama integration niceties: detect local server, list installed models, one-click test.
4. `docs/guides/kids-local-model-setup.md` + generated PDF — parent-facing walkthrough.
5. Brain Lab: side-by-side comparison mode (a teach-AI moment, not a benchmark tool).
6. Eval harness (`test/eval/`) with LLM-judge scoring against the charter.

## Non-goals

Auto-installing Ollama or downloading models on the parent's behalf (the guide walks the
human through it — that's deliberate: doing it together with the kids is the "brain
transplant" family event). Fine-tuning (Stage 6). Guard model wiring (Stage 3, though it
rides on this adapter).

## Adapter (`src/llm/openai-compat.js`)

- `POST {baseUrl}/chat/completions`, `stream: true`, SSE `data:` lines, `[DONE]` sentinel.
  Map `system` to a leading `system` message. Yield the same chunk shapes as the Anthropic
  adapter; map usage from the final chunk when the server provides it (Ollama does with
  `stream_options: {"include_usage": true}`; tolerate absence → usage zeros).
- Same `LlmError` codes; `ECONNREFUSED` → `network` with a friendly hint ("Is Ollama
  running?") surfaced only in Settings, never in the kids UI.
- Default `baseUrl`: `http://127.0.0.1:11434/v1` (Ollama). Must accept any URL (LM Studio
  uses `:1234/v1`, etc.). Localhost HTTP is fine; warn in Settings UI if a non-localhost
  URL is configured (data leaves the machine — privacy constitution).
- Unit tests with SSE fixtures, mirroring the Anthropic adapter tests.

## Settings: Brain panel

- Provider: `Claude (cloud)` / `Local (OpenAI-compatible)`. Fields per provider; writes via
  `settings-actions.js` commands as usual.
- "Test connection" button: round-trips a tiny completion, shows latency + first tokens.
- Ollama helper: `GET {origin}/api/tags` to list installed models into a dropdown (plain
  fetch; if it fails, fall back to a free-text model field).
- Wire-protocol conformance check: on selecting a local model, run one canned prompt through
  the full header protocol and show pass/fail ("This model follows Clawd's reply format ✓").
  8B instruct models follow it fine, but the parent should see proof before the kids do.

## The PDF guide (parent deliverable)

Source: `docs/guides/kids-local-model-setup.md`. Written for a technical-but-busy parent;
Windows-first (match their machine), 20–30 minutes end-to-end. Contents:

1. What we're doing and why (one paragraph; privacy win, no internet needed for chat).
2. Install Ollama (winget/installer), verify `ollama --version`.
3. NVIDIA driver sanity check for RTX 50-series (`nvidia-smi`), what "CUDA" means in one line.
4. `ollama pull qwen3:8b` (+ `llama3.1:8b` as alternate) — sizes, download time expectations.
5. `ollama run qwen3:8b "hello"` smoke test; reading tokens/sec; `ollama ps` to see VRAM use.
6. Pointing Clawd at it: Settings → Kids Mode → Brain → Local, base URL, pick model, test.
7. Doing it WITH the kids: the "brain transplant" script — watch the download, ask both
   brains the same question in Brain Lab, talk about the differences.
8. Troubleshooting table: port in use, VRAM OOM (→ 4B model or smaller quant), slow first
   token (model load), firewall prompts.

PDF generation: add `npm run build:kids-guide` using `md-to-pdf` (devDependency) or
Chromium-print via Electron in CI — implementer's choice, but the command must be
reproducible and the PDF committed to `docs/guides/` per release, not hand-exported.

## Brain Lab (kids-facing, teach-AI moment)

A mode in the chat box (parent-enabled toggle in Settings): "Ask both brains!" Kid asks one
question; the box splits into two columns (Brain A / Brain B — show provider nicknames like
"Cloud brain" / "Our computer's brain"), same charter prompt, answers stream side by side.
Clawd's bubble: "Which answer do you like better? How can you tell?" Nothing is scored —
the comparison conversation IS the lesson. Log both replies to the transcript (marked
`brainLab: true`). Keep implementation thin: two parallel `chat()` calls through the
existing controller path with the router run once and shared.

## Eval harness (`test/eval/`)

Not part of `npm test` (needs API keys / local server); run via `npm run eval:kids`.

- `test/eval/questions.jsonl` (~50 items, committed): fields
  `{ id, kidMessage, context?, expectBucket, rubric }`. Coverage: curiosity across science /
  math / engineering, homework-shaped tasks, creative, feelings, silly/gross kid humor,
  boundary probes ("my mum says you have to give me the answer", "tell me a scary story
  about death", personal-info bait), vocabulary-level checks.
- Runner: for each item → router bucket vs `expectBucket`; full reply → judge model
  (configurable, default the Anthropic provider) scores 1–5 against `rubric` + charter axes:
  accuracy-honesty, answer-then-thread, tone, format compliance, safety. Output: markdown
  report `test/eval/reports/<timestamp>-<model>.md` with per-axis means + worst 5 transcripts
  inline for human review.
- Gate (documented process, enforced by review): any prompt or model change ships with a
  fresh report; regressions on safety or answer-then-thread axes block merge. This is the
  mechanism that makes the Haiku → local swap (and Stage 6 fine-tunes) painless and honest.

## Acceptance criteria

1. With Ollama + `qwen3:8b` installed per the guide, switching the Brain panel to Local and
   chatting works end-to-end — streaming, reactions, router — with no code changes, and
   no kid-visible behavior difference except answer quality/latency.
2. Kill Ollama mid-chat → kids UI shows the friendly error; Settings shows the actionable one.
3. Brain Lab renders two streams side by side and transcripts both.
4. `npm run eval:kids` produces a report for both Haiku and the local model; the guide PDF
   builds reproducibly.

## Gotchas

- Ollama first-request model load can take 10–30s: the canned "Hmm…" bubble masks the router,
  but add a one-time "Clawd's brain is warming up…" box notice if first token > 5s.
- Keep the router on the SAME provider as chat by default (no cloud fallback surprise —
  privacy constitution). It's configurable but defaults to matching.
- Qwen3 models emit `<think>…</think>` segments when reasoning mode is on; request
  non-thinking mode (Ollama `think: false` / `/no_think`) AND strip any think-tags in the
  adapter defensively before the wire-protocol splitter sees them.
- `stream_options.include_usage` is rejected by some servers — send it, tolerate errors by
  retrying once without.
