# Stage 1 — Talk to Clawd

Kids can open a chat box, pick their name, and have a streaming conversation with Clawd
(Claude Haiku under the hood). Clawd reacts with a speech bubble + animation, and the full
reply prints in the box. Kids Mode gates everything behind a parent PIN and mutes all
coding-agent surfaces. Transcripts are written to disk.

Read first: [`README.md`](./README.md) (hard constraints), [`clawd-charter.md`](./clawd-charter.md).
Repo conventions: root `AGENTS.md` — especially the settings system (store is the single source
of truth, `settings-controller.js` is the only writer) and `path.join(__dirname, ...)`.

## Goals

1. Kids Mode: on/off state, parent PIN, coding-agent muting.
2. Chat box window (bottom-center, Pikmin-4-style, themed) with input + scrollback.
3. Reaction speech bubble + emotion→animation mapping.
4. Three kid profiles, local-only, first names.
5. `src/llm/` provider-agnostic wrapper with an Anthropic (Haiku) adapter, streaming.
6. Answer-policy router (curiosity / task / creative / feelings).
7. Charter-based system prompt assembly.
8. Transcript JSONL logging per kid.
9. API key storage via Electron `safeStorage`; basic token usage counting.

## Non-goals (later stages)

Local models (2), guard model & parent dashboard UI & pipeline view (3), web search (4),
memory/call-backs (5). No new art assets required — reuse existing states/themes.

## New modules

```
src/llm/
  index.js            createLlmClient(config) → { chat, complete } ; provider registry
  anthropic.js        Anthropic Messages API adapter (streaming SSE)
  wire-protocol.js    pure: header-line parse/stream-split logic (unit-testable)
src/kids/
  pet-adapter.js      the ONLY kids module allowed to import pet/app internals: state
                      machine entry (emotion states), bubble anchoring, tray/menu items,
                      hit-window click routing, shortcut registration. Keep it thin; every
                      upstream file it touches goes in upstream-seam.md (README ground rules)
  kids-mode.js        Kids Mode state: enter/exit, PIN check, agent-muting hooks
  chat-window.js      BrowserWindow lifecycle for the chat box (pattern: src/dashboard.js)
  chat-renderer.js    renderer for chat.html (history, input, streaming, profile picker)
  chat.html / chat.css / preload-chat.js
  chat-controller.js  conversation state machine; orchestrates router → chat call → channels
  router.js           answer-policy classification call + fallback
  prompt-builder.js   assembles system prompt from prompts/ + stance + profile + date
  profiles.js         load/save kid profiles (names) under <userData>/kids/
  transcripts.js      append-only JSONL writer + reader (per kid, per day)
  reaction-bubble.js  speech bubble window (pattern: src/update-bubble.js)
  pin.js              pure: scrypt hash/verify for the parent PIN
  prompts/
    charter.md        runtime copy generated FROM docs/plans/kids-mode/clawd-charter.md §1–5
    stance-curiosity.md / stance-task.md / stance-creative.md / stance-feelings.md
    router.md         the router's own system prompt
```

## Preferences (extend `src/prefs.js` SCHEMA, bump CURRENT_VERSION, add migration)

```js
kidsMode: {
  enabled: false,             // current mode; forced to true on every launch once configured
  configured: false,          // set true after first-run setup (PIN + at least one profile)
  pinHash: "",                // scrypt: "scrypt$N$r$p$saltB64$hashB64" — never plaintext
  provider: "anthropic",      // key into the llm provider registry
  model: "claude-haiku-4-5-20251001",
  monthlyTokenBudget: 5000000,  // soft cap; warn in settings when exceeded
  usage: { month: "", inputTokens: 0, outputTokens: 0 },
}
```

Profiles are NOT in prefs (they are kid data): `<userData>/kids/profiles.json`
`{ version: 1, profiles: [{ id: "k1", name: "…", createdAt: iso }] }` (max 8, first names only).
The Anthropic API key is NOT in prefs: `safeStorage.encryptString` → base64 blob in
`<userData>/kids/credentials.json` `{ anthropicApiKey: "<b64>" }`. Settings UI writes it via a
dedicated IPC command; it is never echoed back to any renderer (show only "configured ✓").

All settings writes go through `settings-actions.js` validators/commands per repo convention.

## LLM wrapper interface (the contract everything depends on)

```js
// src/llm/index.js
const client = createLlmClient({ provider, model, apiKey, baseUrl });
// Streaming chat. Yields { type: "text", text } chunks; final { type: "done", usage }.
// Throws LlmError { code: "auth" | "rate_limit" | "network" | "bad_response", message }.
for await (const chunk of client.chat({ system, messages, maxTokens, temperature, signal })) { … }
// One-shot non-streaming convenience (used by the router):
const { text, usage } = await client.complete({ system, messages, maxTokens, temperature, signal });
```

- `messages`: `[{ role: "user" | "assistant", content: string }]`. Adapters map to provider format.
- Anthropic adapter: use global `fetch` + SSE parsing against `POST /v1/messages`
  (`anthropic-version: 2023-06-01`, `stream: true`). No new npm dependency; keep the SSE
  parser small and unit-tested with recorded fixtures. Respect `signal` for cancellation.
- The registry maps `provider` → adapter factory. Stage 2 adds `openai-compat` — nothing
  outside `src/llm/` may reference a concrete provider.

## Wire protocol (structured reply, streaming-friendly)

The system prompt instructs the model (charter §6): reply with exactly one JSON header line,
then `\n`, then the message body. Example raw stream:

```
{"reaction":"Ooh, tricky one! 🦀","emotion":"thinking"}
Okay, here's the cool part about volcanoes…
```

`wire-protocol.js` exposes `createHeaderSplitter()`: feed text chunks; it buffers until the
first `\n`, parses the header (`JSON.parse`), then passes all subsequent text through as body
chunks. Fallbacks (must be graceful, never user-visible errors):
- Header fails to parse or no newline within 500 chars → treat everything as body, use
  defaults `{ reaction: "", emotion: "happy" }` (no bubble shown).
- Unknown `emotion` → `happy`. `reaction` truncated at 60 chars.

## Conversation flow (chat-controller.js)

1. Kid sends message. Immediately: bubble shows a local "Hmm… 🤔" (rotate a few canned
   thinking reactions), pet enters `thinking` (reuse existing state via the same entry point
   hook events use — do not bypass the state machine's priority/min-duration logic).
2. Router call (`client.complete`, `maxTokens: 8`, `temperature: 0`): system prompt
   `prompts/router.md`, user content = last kid message (+ up to 2 prior turns for context).
   Expected output: one word from `curiosity|task|creative|feelings`. Unparseable → `curiosity`.
   Timeout 5s → `curiosity` (never block the conversation on the router).
3. Main call (`client.chat`): system = prompt-builder output (charter + stance + profile name
   + today's date + response-format contract), messages = rolling window of the current
   session (cap ~20 turns; truncate oldest).
4. Header arrives → replace canned bubble with `reaction`, map `emotion` → pet state
   (table below). Body chunks stream into the chat box.
5. `done` → accumulate usage into prefs `kidsMode.usage` (via settings command), append
   transcript entry, pet returns to idle per normal auto-return.
6. Errors → friendly in-box message ("My brain got fuzzy for a second — try again?") +
   `error` pet state; log details to main log only (never show raw errors to kids).

Emotion → state mapping (reuse existing states; graceful and boring is correct here):
`excited|celebrating → attention`, `happy|gentle → notification` (suppress the notification
sound in kids chat context; use the softer confirm sound at most), `thinking|curious →
thinking`, `sleepy → idle`. Keep the mapping in one table in `chat-controller.js` — Stage 3+
may add dedicated kid-mode animations per theme.

## Windows & UX

**Design checkpoint (required, before any UI implementation):** produce 2–3 visual mockups
of the chat box (plus profile picker and reaction bubble styling) — static HTML pages or
rendered images are both fine — and present them to the parent for approval. Do not
implement `chat.html`/`chat.css` until one is picked; treat the approved mockup as the
visual spec. An appealing interface is a stated project priority, not polish.

**Chat box** (`chat-window.js`, pattern-match `src/dashboard.js`): frameless, transparent
corners, bottom-center of the display the pet is on, ~60% work-area width (min 480px,
max 900px), height ~200px collapsed. Focusable (it's a text input — this is NOT the pet's
click-through render window; do not touch the dual-window pet machinery). Summon/dismiss:
tray menu item, global shortcut (register via existing `shortcut-actions.js` conventions),
and single-click on the pet while Kids Mode is active (route through the existing hit-window
click handling; suppress the normal poke reaction in Kids Mode). `Esc` dismisses. Styling:
match the active theme's palette; pixel-art border in Clawd theme (pure CSS — image-rendering
pixelated border assets are optional polish, not required). History shows the current session
only (scrollback across sessions is Stage 3's parent view / Stage 5 memory).

**Profile picker**: when the chat box opens with no active profile, show "Who's playing?"
with big name buttons (+ a parent-gated "manage profiles" in Settings). Switching profiles
starts a fresh session and a new transcript file handle.

**Reaction bubble** (`reaction-bubble.js`, pattern-match `src/update-bubble.js`): small,
follows the pet, auto-sizes, avoids the Session HUD/permission-stack slots (which are empty
in Kids Mode anyway), auto-hides ~6s after body streaming completes. One bubble at a time —
new reaction replaces the old.

**Kids Mode gating** (`kids-mode.js`) — Kids Mode is the DEFAULT; parent mode is the
PIN-gated exception:
- Until `configured`, the app behaves as stock Clawd. First-run setup (set PIN, add ≥1
  profile) lives in Settings under "Kids Mode"; completing it sets `configured` and enters
  Kids Mode.
- Once `configured`, every app launch starts in Kids Mode regardless of the mode at last
  quit (a reboot always lands kid-safe).
- Entering parent mode: tray/settings action → PIN prompt (3 wrong attempts → 60s lockout).
  Parent mode restores all normal Clawd features and lasts until the parent switches back
  or the app restarts. Returning to Kids Mode never needs the PIN.
- While Kids Mode is active: suppress permission bubbles / HUD / dashboard / update bubble
  using the same event-suppression semantics as DND (agents fall back to their own
  terminal/native approval flows — Clawd must NOT auto-answer permissions; see AGENTS.md
  DND constraints). The pet stays awake (kids chat shouldn't fight the sleep sequence
  mid-conversation: any chat activity counts as user activity).

## Transcripts

`<userData>/kids/transcripts/<profileId>/<YYYY-MM-DD>.jsonl`, one JSON object per line:
`{ ts, sessionId, role: "kid" | "clawd", text, reaction?, emotion?, bucket?, model }`.
Append-only via a small serialized writer (reuse the style of existing log writers;
`log-rotate.js` is prior art). No redaction in Stage 1 — these are local, parent-owned files.

## Prompt assembly (prompt-builder.js)

Order: charter runtime copy → hard rules → response-format contract → stance file for the
router bucket → context block (`Today is {date}. You are talking to {name}.`). Keep each
prompts/ file plain Markdown; builder just concatenates with separators. Unit-test that all
referenced files exist and the output contains the stance marker for each bucket.

## Testing (Node test runner, `test/`)

- `wire-protocol.test.js`: header split across chunk boundaries, garbage header fallback,
  emoji/UTF-8 boundaries, 500-char no-newline fallback.
- `llm-anthropic.test.js`: SSE fixture parsing (happy path, mid-event chunk splits, error
  event, abort), auth/rate-limit error mapping. No live network in tests.
- `router.test.js`: output normalization ("Task." → `task`), fallback on garbage/timeout.
- `pin.test.js`: hash/verify round-trip, wrong PIN, lockout counter logic.
- `profiles.test.js` / `transcripts.test.js`: round-trips, bad-file fallback (`.bak` pattern
  like prefs), date rollover.
- `prompt-builder.test.js`: stance injection per bucket, name/date interpolation.
- `prefs` migration test for the new schema version.
- Manual QA checklist (Windows-first per repo): summon/dismiss, streaming smoothness, bubble
  positioning near screen edges, Kids Mode suppresses a real Claude Code permission bubble,
  PIN lockout, kill network mid-stream.

## Acceptance criteria

1. Parent completes first-run setup (PIN + 3 profiles + API key) in Settings; app enters
   Kids Mode and every subsequent launch starts in Kids Mode; all agent surfaces mute;
   entering parent mode requires the PIN, and a restart drops back to Kids Mode.
2. Kid opens box, picks name, asks "why is the sky blue?" → bubble "Hmm…" ≤ 200ms, thinking
   animation, then model reaction + emotion animation + streamed answer that follows the
   charter (rich answer + hook back).
3. "Do my maths homework: 348÷12" → router → `task` → Clawd coaches steps, does not just
   answer.
4. Transcript file contains both turns with bucket labels. API key is absent from all files
   except the encrypted credentials blob. `npm test` green.

## Gotchas

- Do not create BrowserWindows before `app.whenReady`; follow `dashboard.js` lifecycle.
- Multi-monitor: position the chat box on the pet's current display (`getNearestWorkArea()`).
- The chat box takes focus by design — unlike the pet windows. Don't "fix" that.
- Respect `miniTransitioning` and mini mode: summoning chat while mini-mode is active should
  first restore the pet from the edge (reuse existing exit path), not fight it.
- Never let a raw model error or stack trace render in the kids UI.
- When this stage lands: update `AGENTS.md` Core Files/Constraints and add a
  `docs/project/kids-mode-architecture.md`.
