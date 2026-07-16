# Stage 5 — Memory & Family

Clawd remembers. Per-kid memory turns adjacent-topic hooks into call-backs ("remember when
you asked about volcanoes? This is related!"), a parent-editable family facts file gives
Clawd context, and session summaries keep it all inside a small model's context budget.
Stretch: two-player quiz mode for siblings.

Depends on: Stage 1 (profiles, transcripts, prompt-builder), Stage 3 (parent dashboard for
editing/visibility). Privacy constitution applies with full force: memory lives in local
Markdown/JSON, parent-editable, never in weights.

## Goals

1. Per-kid memory store with automatic candidate extraction + retrieval into the prompt.
2. Family facts file (shared, parent-authored).
3. Session summarizer (end-of-conversation job) powering retrieval and call-backs.
4. Dashboard "Memory" tab: view/edit/delete everything Clawd remembers.
5. Tinkering-loop continuity: open challenges resurface naturally ("did the wings help?").
6. Stretch: co-op quiz mode.

## Non-goals

Photos/multimodal (needs a vision model + its own safety pass — future). Embedding
databases/vector stores — at family scale, keyword + recency retrieval over summaries is
simpler, inspectable, and enough. Cross-kid memory sharing (explicitly: Clawd never leaks
one kid's chats to a sibling).

## Data model (`<userData>/kids/memory/<profileId>/`)

- `facts.md` — bullet list, one memory per line, `- [2026-07-20] Loves volcanoes and Minecraft.`
  Human-writable; this file IS the database. Size-bounded: ~100 lines max; oldest
  low-importance lines pruned with parent visibility (moved to `facts-archive.md`, never
  silently deleted).
- `sessions.jsonl` — one line per finished conversation:
  `{ ts, sessionId, summary, topics: [], openLoops: [] }` (openLoops = tinkering challenges,
  guesses to check, "look at the moon tonight" homework Clawd assigned).
- `<userData>/kids/family-facts.md` — parent-authored shared context ("we live near the
  sea", "the kids' grandmother is called Popo"). Loaded for every kid. Clawd is instructed
  to use family facts naturally but NEVER to recite the file or enumerate what he knows.

## Memory candidate extraction

At session end (chat box closed or 10 min idle), one LLM call (same provider, cheap):
summarize the session (2–3 sentences), extract topics, open loops, and 0–2 *memory
candidates* (durable kid facts: interests, achievements, pet names — explicitly NOT
transient states, fears confided in `feelings` turns, or anything from `sensitive`
conversations; the prompt must exclude those two buckets' content from candidacy).
Candidates land in `facts.md` marked `(new)`; the dashboard Memory tab surfaces them for
parent review — parent can keep/edit/delete. Auto-kept after 7 days if unreviewed
(memory shouldn't be gated on parent diligence, but the window gives control).

## Retrieval (prompt-builder extension)

Per turn, prepend a compact memory block:
- All of `facts.md` (it's ≤100 lines by construction) + `family-facts.md`.
- Last 3 session summaries + any `openLoops` less than 14 days old.
- Keyword match: topics from `sessions.jsonl` intersecting the current message (simple
  stemmed-token overlap, pure function, unit-tested) → up to 3 older summaries.
Budget the block to ~800 tokens (matters for the local model's context); truncate oldest
first. Charter addition: use call-backs when genuinely relevant, at most one per reply —
forced call-backs feel like surveillance, not friendship.

## Open loops (the tinkering payoff)

When Clawd assigns a real-world follow-up, the summarizer records it as an open loop. Next
session, prompt-builder surfaces loops < 14 days old; charter instructs Clawd to ask about
at most one, casually ("hey, did you ever test the paper plane with the folded wingtips?").
Closed or expired loops drop out. This single mechanism powers the design→test→improve
coaching continuity that makes the engineering pedagogy real.

## Dashboard Memory tab

Per kid: rendered `facts.md` with inline edit/delete, new-candidate review chips, session
summary list, open loops with dismiss. Family facts editor. A visible "Clawd forgets this
kid entirely" button (deletes the memory dir after confirm — kid data is parent-owned).

## Greeting upgrade

With memory present, opening the chat box greets per kid with at most one personal touch
("Hi Mei! 🦀" + occasionally a light call-back or open-loop nudge). Rotate; never needy,
never "I missed you" (anti-attachment rule).

## Stretch: co-op quiz

"Quiz us!" with two profiles selected → Clawd alternates guess-first questions between the
kids (drawing topics from BOTH kids' interests via their own memory, without revealing
either kid's private chats), celebrates effort, no scorekeeping beyond the session, no
leaderboards ever (engagement-mechanics rule). Transcripts logged to both profiles.

## Testing

Unit: retrieval selection/budgeting, keyword overlap, facts.md parse/prune/archive,
open-loop lifecycle, candidate-exclusion of sensitive/feelings content (fixture-driven).
Eval: add a `memory` suite with seeded facts.md fixtures — verify call-backs happen when
relevant, DON'T happen every turn, and never quote sensitive-bucket content. Manual QA:
multi-day flow with a real kid conversation arc.

## Acceptance criteria

1. Kid mentions loving volcanoes Monday; Thursday's astronomy question gets a natural
   volcano call-back — and the parent can see and delete that memory in the dashboard.
2. Feelings/sensitive conversations never produce facts.md entries (verified by fixture).
3. An assigned experiment resurfaces once, casually, within 14 days; dismissing it in the
   dashboard stops it.
4. "Forget this kid" wipes memory; next greeting is the plain Stage-1 greeting.
5. Prompt memory block stays ≤ 800 tokens under adversarial fixtures. `npm test` green.
