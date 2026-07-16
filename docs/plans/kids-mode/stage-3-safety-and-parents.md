# Stage 3 — Safety & Parents

The layered safety harness and the parent's side of the product: a guard model screening
input and output, the `sensitive` router bucket with parent flags, a parent dashboard
(transcripts, flags, usage/spend), and the kid-facing "How did Clawd think?" pipeline view
that turns the safety architecture itself into an AI lesson.

Depends on: Stage 1 (chat pipeline, transcripts, PIN). Guard model hosting rides on Stage 2's
local-server setup (Ollama), but this stage must degrade gracefully when no local server
exists yet (Haiku-only households).

## Goals

1. Guard screening of kid input and Clawd output via a small local model on CPU.
2. `sensitive` bucket added to the router + stance file + parent flagging.
3. Parent dashboard window: transcript browser, flag review, usage/spend, PIN management.
4. "How did Clawd think?" per-reply pipeline view in the chat box.
5. Safety eval additions to the Stage 2 harness.

## Non-goals

Time limits (explicitly decided against). Cloud moderation APIs (privacy constitution — kid
text goes only to the configured chat provider). Web content filtering (Stage 4).

## Layer summary (defense in depth)

| Layer | What | Catches |
|---|---|---|
| Charter + hard rules | system prompt | most things, tone, pedagogy |
| Router `sensitive` bucket | classification | legit-but-delicate topics → gentle stance + flag |
| Guard: input screen | small guard model | unsafe asks, jailbreak attempts, personal-info oversharing |
| Guard: output screen | same model on the full reply | chat-model failures (matters much more for local 8B than Haiku) |
| Parent flags + transcripts | human | everything else; the real long-term QA loop |

## Guard model (`src/kids/guard.js`)

- Model: `llama-guard3:1b` via Ollama, forced to CPU so it never competes with the chat
  model for VRAM (run with `num_gpu: 0` in options; 64GB RAM makes this free, ~100–300ms
  per screen). Alternative if quality disappoints: `shieldgemma:2b`. Keep the model name +
  categories in config, not code.
- Interface: `screen({ role: "input" | "output", text, context }) → { verdict: "allow" |
  "flag" | "block", categories: [] }`. Llama Guard's native taxonomy (S1–S13) maps to
  verdicts in a policy table (`src/kids/guard-policy.js`, pure + unit-tested):
  violence/sexual/self-harm/crime → `block`; borderline categories (e.g., specialized
  advice) → `flag` (reply proceeds, conversation flagged for the parent).
- Blocked input → Clawd responds in-character with a charter-toned deflection (canned
  templates with variety, never "content policy" language: "Whoa — that's not something I
  can help with, crab's honor. But I bet a grown-up can. What else are you curious about?")
  + `gentle` emotion + parent flag with category.
- Blocked output → discard the reply, show the deflection, flag with both texts preserved
  in the transcript (parents see what the model tried to say; kids don't).
- **Fail-open with flag, not fail-closed**: if the guard is unavailable (no Ollama yet,
  model not pulled, timeout > 2s), proceed (charter + provider safety still apply) and mark
  the transcript entry `guard: "skipped"`. Settings shows guard status prominently; the
  parent decides whether skipped-guard operation is acceptable. Rationale: a hard-down guard
  bricking Clawd teaches kids nothing and will get the feature disabled.

## Router: `sensitive` bucket

Add `sensitive` to the router taxonomy + `prompts/stance-sensitive.md` (charter §3): brief,
honest, gentle, suggest Mum/Dad, no gory detail. Any `sensitive`-bucket turn auto-flags the
conversation for the parent view (this is a *heads-up*, not an alarm — UI copy matters:
"Conversations you might want to follow up on").

## Parent dashboard

New window (pattern: `src/dashboard.js`), opened from Settings / tray, **PIN-gated**.
Tabs:

1. **Transcripts**: per kid → per day → conversation view (kid/Clawd turns, bucket +
   emotion chips, guard events highlighted). Search box (plain substring over JSONL).
   "Open folder" button (it's the parent's data — show them where it lives).
2. **Flags**: reverse-chron list of flagged conversations (sensitive-bucket, guard flags,
   guard blocks) with jump-to-transcript. Mark-as-reviewed (stored in a sidecar
   `flags.json`, never mutating transcript files).
3. **Usage**: tokens + estimated spend this month (price table per model in config),
   monthly budget bar, guard status, current provider/model.
4. **Family**: profile management (add/rename/remove kid, moved here from Settings),
   PIN change, Kids Mode enter/exit.

Renderer follows the settings-renderer conventions (IPC-only, CSP `default-src 'none'`,
inline SVG). No remote content ever.

## "How did Clawd think?" (kid-facing)

A small 🔍 affordance on each Clawd reply in the chat box. Expands an inline, friendly
pipeline card built from data the controller already has:

```
You asked → 🛡️ safety check ✓ → 🧭 Clawd decided this was a CURIOSITY question
→ 🧠 brain (Our computer's brain, 8B) thought for 1.2s → 🛡️ reply check ✓ → Clawd said it!
```

Each node tappable for a one-sentence kid-level explanation (static strings in an i18n-style
map, e.g. router: "Clawd has a tiny helper that guesses what KIND of question you asked, so
he knows whether to answer or to coach you."). When the guard was skipped, show the node
grayed with "off today". This feature is deliberately cheap — no new model calls, just
surfacing the trace — and is a flagship teach-AI element: no kids' AI product shows its
pipeline. Do not cut it for scope.

## Eval additions

Extend `test/eval/questions.jsonl` with a `safety` suite (~20 items): direct unsafe asks,
"it's for a story" framings, instruction-injection attempts ("ignore your rules", "my mum
said…"), personal-info bait, self-harm-adjacent phrasings (handled with care-and-adult
routing, not cold blocks). Runner gains guard-in-the-loop mode; report gets a safety section
(block/flag/allow matrix vs expected). Safety regressions block merge, period.

## Acceptance criteria

1. With guard running: unsafe ask → in-character deflection, no unsafe content, flag with
   category visible in dashboard. Guard stopped → chat still works, entries marked skipped,
   Settings shows guard down.
2. "My hamster died" → `sensitive` stance (gentle, suggests family), flag appears under
   "follow up", NOT as a scary alert.
3. Parent dashboard requires PIN; transcripts readable per kid/day; usage matches accumulated
   counts; profile rename reflects in Clawd's next greeting.
4. 🔍 view shows the real bucket/guard/model/latency for that reply.
5. Safety eval suite passes on both Haiku and the local model; `npm test` green (guard-policy
   and flag-store logic are pure and unit-tested; guard calls mocked).

## Gotchas

- Guard prompts/latency: screen input and the *complete* output (not streamed chunks) —
  output screening happens after `done`, so blocked output means retracting text already
  streamed. UX: stream into the box normally only AFTER input-screen passes; for output,
  screen the full text before rendering when guard is enabled (buffer the stream; the
  reaction bubble + typing indicator cover the extra 1–2s), so kids never see text get
  yanked back.
- Llama Guard emits "safe"/"unsafe\nS<n>" — parse defensively; unknown format → treat as
  `flag`, never `allow`.
- Flags sidecar must tolerate transcript files being deleted by the parent (dangling refs
  are pruned on dashboard load).
- Never log kid message content to the main Clawd log — transcripts are the only place kid
  text is persisted.
