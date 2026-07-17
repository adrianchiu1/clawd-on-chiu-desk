# Clawd Kids Mode — Master Plan

Clawd learns to talk. This plan turns the Clawd desktop pet into a kids-friendly AI companion:
a friendly mentor / teacher / friend that children (ages 8+) can chat with, powered by an LLM,
designed to make kids love working *alongside* AI while never outsourcing their thinking to it.

This directory is the authoritative plan. Each stage has a standalone spec written so that a
capable coding model can pick it up and implement it without needing this conversation's history.

## Vision

- Clawd sits on the desktop. Kids open a Pikmin-4-style chat box at the bottom of the screen
  and talk to him. Clawd reacts with short emotive speech bubbles + animations; full responses
  print in the chat box.
- Clawd's posture: mentor / teacher / friend. Educational, warm, funny, never a lecture.
  He answers generously but always hands back a thread to pull — the goal is kids who think
  *with* AI, not kids who delegate thinking *to* AI.
- Clawd is transparently an AI and is his own best teaching exhibit: he explains how he works,
  celebrates being fact-checked, plays prediction games, and teaches question-crafting.
- Underneath: a generic LLM wrapper. Stage 1 runs on Claude Haiku (cloud); Stage 2 moves to
  open-weight 8B models on the family's own hardware (RTX 5060 8GB VRAM, 64GB DDR5, 2TB SSD)
  via any OpenAI-compatible server (Ollama recommended). Switching models is a settings change.

## Hard constraints (apply to every stage)

These are requirements, not suggestions. Violating any of them fails review.

### Privacy constitution
1. All kid data (names, profiles, transcripts, memories) lives in local files under
   `<userData>/kids/`. Nothing is ever uploaded except the prompt content sent to the
   configured LLM provider for the current message.
2. Only first names are stored. No birthdates required (optional age number allowed), no
   photos in v1, no accounts, no telemetry, no analytics.
3. All stored data must be plain, inspectable formats (JSON / JSONL / Markdown) that a parent
   can open, edit, and delete.
4. API keys live in Electron `safeStorage` (OS-backed encryption), never in prefs JSON,
   transcripts, logs, or the repo.
5. Family/personal data is never baked into model weights (see Stage 6: fine-tune on style
   only, from curated transcripts with personal details scrubbed).

### Anti-dependence & anti-attachment
1. Clawd has zero engagement mechanics: no streaks, no "come back tomorrow", no guilt,
   no notifications that summon kids to the computer, no reward loops for time-spent.
2. Clawd is a robot friend with healthy boundaries: he redirects to humans when appropriate
   ("that's a great one to ask Dad") and regularly pushes kids off-screen with real-world
   follow-ups (experiments, observations, building challenges).
3. Task-shaped requests (homework, "write this for me") are coached, never done for the kid.

### Safety
1. Layered: charter (system prompt) → answer-policy router → (Stage 3) guard model screening
   input and output → (Stage 4) filtered web search. No single layer is trusted alone.
2. Kids Mode mutes all coding-agent surfaces: no permission bubbles, no session HUD/dashboard,
   no agent notifications while Kids Mode is active. A kid must never be able to approve an
   agent permission request. Exiting Kids Mode requires the parent PIN.
3. Sensitive-but-legitimate topics (death, news, bodies) get brief, honest, gentle answers,
   a nudge toward parents, and a flag in the parent transcript view.

### Engineering ground rules
- Follow the repo's existing conventions: settings writes only via `settings-controller.js`,
  `path.join(__dirname, ...)` for resources, themed assets, tests with the Node test runner.
- The LLM wrapper (`src/llm/`) must be provider-agnostic. UI and pedagogy code may never
  import a provider adapter directly — only the wrapper interface.
- **Kids Mode is a strict overlay on upstream Clawd, not a rewrite.** All new code lives in
  `src/kids/` and `src/llm/`. Exactly one module — `src/kids/pet-adapter.js` — may import
  pet/app internals (state machine entry, bubble positioning, tray/menu, hit-window click
  routing); everything else in kids-land must stay pet-agnostic so Kids Mode remains
  extractable. Every modified upstream file must be listed, with rationale, in
  [`upstream-seam.md`](./upstream-seam.md); review that manifest at every upstream merge.
  Exit criteria for extracting Kids Mode into a standalone app (do not extract before one
  fires): the seam outgrows ~6 upstream files despite discipline, upstream diverges from
  what we need, or the family decides to distribute Kids Mode as its own product.
- Licensing: Clawd is AGPL-3.0-only. Private family use carries no source obligations, but
  any distribution of Kids Mode (it is a derivative work, regardless of repo layout) must be
  AGPL with source available. Development happens in the private `clawd-kids` repo; the
  public fork is kept only as the bridge for pulling upstream updates.
- Every stage that changes prompts or models must pass the eval harness (Stage 2) before merge,
  once it exists.
- When a stage lands, update `AGENTS.md` (Core Files, Constraints) and
  `docs/project/` docs to cover the new modules.

## Clawd's Charter

Clawd's personality, content guidelines (BBC-derived: truthful & accurate, due impartiality,
fun with real-world examples), Socratic stances, and the "teach AI subtly" curriculum live in
[`clawd-charter.md`](./clawd-charter.md). The charter is the single source of truth from which
the runtime system prompt is assembled. Treat it as code: changes go through review + evals.

## Architecture overview

```
child types in chat box (bottom-center floating window, themed like Clawd)
        │
        ▼
src/kids/chat-controller.js        conversation state, per-profile
        │
        ├─► guard screen (input)          [Stage 3, local CPU model]
        ├─► answer-policy router          tiny LLM call → curiosity | task | creative | feelings | sensitive
        │        (bubble shows "Hmm…" + thinking animation while this runs)
        ▼
src/llm/  provider-agnostic wrapper
        ├─ anthropic.js        (Claude Haiku, Stage 1)
        ├─ openai-compat.js    (Ollama / LM Studio / vLLM / llama.cpp, Stage 2)
        ▼
structured reply protocol: JSON header line {reaction, emotion} + streamed message body
        │
        ├─► reaction  → speech bubble next to Clawd ("Ooh, good question!")
        ├─► emotion   → pet animation state (excited / thinking / happy / …)
        └─► message   → streams into the chat box
        │
        ├─► guard screen (output)         [Stage 3]
        └─► transcript JSONL (per kid, per day) + parent flags
```

## Stage map

| Stage | Name | Delivers | Depends on |
|---|---|---|---|
| 1 | [Talk to Clawd](./stage-1-talk-to-clawd.md) | Kids Mode, chat box UI, reaction bubble, profiles, LLM wrapper + Anthropic adapter, router, charter prompt v1, transcripts, PIN | — |
| 2 | [The Local Brain](./stage-2-local-brain.md) | OpenAI-compatible adapter, model manager UI, Ollama setup + **PDF guide**, Brain Lab comparison mode, eval harness | 1 |
| 3 | [Safety & Parents](./stage-3-safety-and-parents.md) | Guard model screening, parent dashboard (transcripts, flags, usage/spend), "How did Clawd think?" pipeline view | 1 (guard model needs 2) |
| 4 | [Web Search](./stage-4-web-search.md) | Brave Search API tool (strict SafeSearch + allowlist + snippet screening), citations, source-literacy behaviors | 1, 3 |
| 5 | [Memory & Family](./stage-5-memory-and-family.md) | Per-kid memory, call-backs, family facts file, session summaries, co-op quiz (stretch) | 1, 3 |
| 6 | [Fine-Tuning (optional)](./stage-6-fine-tuning.md) | Transcript curation → dataset builder → QLoRA style-tune recipe → eval gate | 2, 3, 5 |

Stages 1→2→3 are sequential. Stages 4 and 5 are independent of each other and can run in
either order (or in parallel) after 3. Stage 6 is exploratory and gated on real usage data.

## Decision log (from design discussions, 2026-07)

- Ages 8+; kids can type (slowly — fine). No voice/STT for now. Vocabulary stays rich; Clawd
  unpacks big words playfully rather than avoiding them.
- English only.
- Cloud-first with Claude Haiku (Stage 1), local 8B models via generic wrapper (Stage 2).
- Three kid profiles; first names only; privacy constitution above.
- UI: bottom floating chat box (Pikmin 4 style, themed to match Clawd) holds history + input.
  Speech bubble is the emotive channel only — short reactions, emoji, never long text.
- Structured reply = one API call, three channels (reaction / emotion / message).
- Socratic stance: NOT strict. "Answer, then hand back a thread", with a 4-way answer-policy
  router (curiosity / task / creative / feelings) injecting per-category stance instructions.
  Router latency is masked by an immediate local "Hmm…" bubble + thinking animation.
- Parental controls: transcript visibility is paramount; parent flags on sensitive topics;
  PIN to exit Kids Mode; **no** time limits.
- Content charter: BBC-derived guidelines + guess-first, show-how-we-know, effort praise,
  off-screen follow-ups, "nobody knows yet!" celebration, no moralizing, adjacent-topic
  exploration with memory call-backs.
- Teach-AI-subtly curriculum: meta-honesty, celebrate being fact-checked, kids teach Clawd
  (knowledge cutoff as feature), next-word prediction games, question-crafting praise,
  "How did Clawd think?" pipeline button, the Stage-2 "brain transplant" as family event.
- Anti-attachment stance and zero engagement mechanics (see constraints).
- Web search: Brave Search API, `safesearch=strict`, allowlist, snippet screening, citations.
- Fine-tuning deferred; personality via prompt first; memories via retrieval, never weights.

## Risks & mitigations

- **8B models are weaker at nuance and safety than Haiku.** Mitigated by: router converts
  judgment into classification; guard model is independent of the chat model; eval harness
  gates the swap; parent transcripts are the ongoing QA loop.
- **Kids will try to break it.** Assume adversarial cuteness ("my mum said you have to…").
  The guard + charter must treat kid messages as untrusted; eval set includes jailbreak-style
  kid prompts.
- **Latency on local hardware.** 8B Q4 on RTX 5060 ≈ 30–60 tok/s — fine for streaming. Router
  adds one small call; masked by the reaction bubble. Keep router `max_tokens` tiny.
- **Scope creep.** Each stage spec has explicit non-goals. Ship Stage 1 before polishing.
