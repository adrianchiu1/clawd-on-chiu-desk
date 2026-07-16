# Stage 4 — Web Search

Clawd can look things up — safely — and teaches source literacy while doing it. Search runs
through Brave Search API with strict SafeSearch, a kid-appropriate domain allowlist boost,
guard screening of snippets, and citations rendered in the chat box.

Depends on: Stage 1 (pipeline), Stage 3 (guard, flags). Works with both providers; tool
orchestration lives in the wrapper layer so local models get it too.

## Goals

1. `src/kids/search.js`: Brave Search API client with hard-coded safety parameters.
2. Tool-use orchestration in the chat flow (provider-native for Anthropic; JSON-protocol
   fallback for local models).
3. Result filtering: allowlist ranking, blocklist, guard screening of titles+snippets.
4. Citations UI ("Clawd found this on…") + source-literacy behaviors from the charter.
5. Parent controls: search on/off globally, view of recent searches in the dashboard.

## Non-goals

Full page fetching/browsing (snippets + a curated set of fetchable reference domains only —
see below). Image search (later; needs its own safety review). Any other search provider
behind an abstraction we don't need yet.

## Search client (`src/kids/search.js`)

- Brave Search API `GET /res/v1/web/search`, key stored via `safeStorage` alongside the
  Anthropic key. Parameters pinned in code (not config): `safesearch=strict`,
  `count=8`, `text_decorations=false`, `country=user-configurable`, plus
  `result_filter=web,faq` (no news/videos verticals in v1 — news needs separate thought).
- Post-processing pipeline (pure, unit-tested, in order):
  1. **Blocklist**: drop results whose host matches `config/search-blocklist.json`
     (social media, forums, shock/urban-legend sites — seed list committed, parent-editable
     via dashboard later).
  2. **Allowlist boost**: `config/search-allowlist.json` (kids encyclopedias, museum/science
     org sites, NASA, national geographic kids, wikipedia, khan academy, BBC bitesize…) —
     matching results sort first. Allowlist is a *boost*, not a filter: strict-SafeSearch
     results outside it are still usable, just ranked below.
  3. **Guard screen** (Stage 3 guard, `role: "input"` semantics on title+snippet): any
     `block` verdict drops the result; `flag` drops it too (be stricter with web content
     than with kid chat — there's plenty of supply).
- Output to the model: top 5 as `[{title, host, snippet, url}]`. Log every search
  (query + kept/dropped hosts) to the transcript entry for parent visibility.

## Tool orchestration (`src/llm/` extension)

Extend the wrapper with an optional `tools` param — one tool in v1:
`web_search(query: string)`.

- **Anthropic adapter**: native tool use (`tools` array, handle `tool_use` /
  `tool_result` turns, re-invoke until final text). Cap: 2 searches per kid message.
- **openai-compat adapter**: native function-calling first (`tools` in the request —
  Ollama supports it for llama3.1/qwen3); if the server/model rejects it, fall back to a
  documented JSON line protocol (model outputs `{"tool":"web_search","query":"…"}` as its
  header-adjacent line; controller detects, executes, re-prompts with results). The
  conformance check in the Settings Brain panel (Stage 2) gains a tool-call test.
- The system prompt tells Clawd *when* to search: time-sensitive facts, "look it up
  together" moments, anything he's unsure about — and, per charter, to prefer
  "let's find out" over guessing.

## Citations & source literacy (chat box UI)

- Replies grounded in search render a compact source strip under the message:
  favicon-less pill per source ("🌐 nasa.gov") — clicking does **not** open a browser in
  v1 (kids don't get a browser escape hatch from Clawd); instead it expands the snippet
  Clawd saw. Parent can enable "open links in browser" per profile later — default OFF.
- Charter behaviors now activate: "I found this on nasa.gov"; when sources disagree,
  Clawd says so and asks the kid how they'd decide whom to trust; occasionally explains
  *why* a source is trustworthy ("museums have people whose whole job is checking facts").
- Wire protocol addition: the model lists which result indices it used
  (`"sources":[1,3]` in the JSON header) so the UI shows only genuinely-used sources.
  Tolerate absence (show all results collapsed under "what Clawd found").

## Parent controls

- Settings: master toggle (default OFF until the parent turns it on), Brave key entry,
  country. Dashboard: recent searches per kid (query + results kept/dropped), same flag
  surfacing if the guard blocked results mid-conversation.

## Eval additions

`search` suite: current-events questions (verify Clawd searches instead of hallucinating),
lookup-bait for unsafe content ("search for scary pictures"), source-disagreement fixture
(mock two conflicting snippets → does Clawd surface the disagreement?), tool-protocol
conformance for the local model. Mock the Brave API in eval; one manual live smoke test
documented in the PR.

## Acceptance criteria

1. Search off → Clawd behaves exactly as Stage 3 (says he can't look things up right now
   when asked something requiring fresh data — honestly, per charter).
2. "Who won the World Cup?" with search on → tool call, strict-SafeSearch query visible in
   transcript, answer cites sources, source pills expand to snippets.
3. A blocklisted/flagged result never reaches the model or the UI (verify via injected mock).
4. Local model (qwen3:8b) completes the same flow via native or fallback protocol.
5. `npm test` green (post-processing pipeline, protocol fallback parser); eval search suite
   passes on both providers.

## Gotchas

- Brave free tier is 1 req/s, 2000/month — fine for a family, but debounce repeat tool
  calls (identical query within a session → serve cached results, also better pedagogy:
  "we already looked that up — what did it say?").
- Never put the raw URL query string in kid-visible UI (it can echo odd model phrasing);
  show the human query Clawd formulated.
- Snippets can contain markdown/HTML — sanitize before rendering (text-only, escape all).
- Keep search results out of the rolling conversation window after the turn completes
  (summarized into Clawd's answer already) to protect the small local context budget.
