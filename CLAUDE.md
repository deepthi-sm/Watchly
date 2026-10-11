# CLAUDE.md — Watchly project context

Paste this whole file into a new chat if the current one runs out of tokens, along
with a list of which files below are already generated and pasted into VS Code.
Say: "Continue Watchly from here, these files are already done: [list]. Next file
needed: [name]." That's enough for a fresh session to pick up without drift.

## What this project is

A class assignment: build a small chat app that demonstrably uses four LangGraph
mechanics. The domain (movies/shows) and every extra feature exist to make the
required mechanics visible in a working app, not to distract from them.

## Assignment requirements (verbatim, do not paraphrase away detail)

Build a small chat application with a front end for a simple domain of your choice,
and use it to demonstrate all four topics: (1) a LangGraph graph (state, nodes,
edges); (2) state management with reducers; (3) trimming and filtering of messages;
(4) short-term and long-term memory. Any LLM is fine — grading is on understanding
the mechanics, not the model.

- **Topic 1 — Graph**: compiled StateGraph, typed State, at least two nodes, one
  conditional edge (router branching by intent). The graph must be displayed
  somewhere in the UI (`draw_ascii()` or `draw_mermaid_png()`).
- **Topic 2 — State/reducers**: at least one non-default reducer channel (on top
  of the default `add_messages` on the messages channel). Checkpointer with a
  `thread_id`; the frontend must let the user switch threads and prove the two
  conversations stay separate.
- **Topic 3 — Trimming/filtering**: trim history to a token budget before every
  model call. The UI must visibly show the effect (token/message count before vs
  after).
- **Topic 4 — Memory**: short-term via the checkpointer, long-term via a store
  that survives across threads (small profile schema — name + preference). Must
  show a fact learned in one thread being recalled in a brand-new thread.

## Project identity

- Name: **Watchly** (final — do not use "WatchWise AI", an earlier discarded name).
- Domain: conversational movie/TV assistant. Recommends titles, manages a
  persistent watchlist, lets users mark titles watched, remembers preferences
  across conversations.

## Locked-in stack decisions

- Backend: Python, FastAPI.
- Frontend: Angular. Built directly by Claude in this chat, file by file — NOT
  using Claude Design, and NOT Claude Code. User has the free Claude tier so
  context runs out fast; hence this file and the one-file-at-a-time workflow.
- LLM: Gemini (free tier).
- Auth: Firebase (email + password login/signup, not Google OAuth).
- Database: PostgreSQL + Alembic migrations.
- Vector store: Chroma (for recommendation retrieval).
- Movie data: TMDB API, free tier. User is creating their own API key.
- Observability: LangSmith tracing — include it (cheap, reinforces the graded
  mechanics with a real trace artifact).
- Tool-calling node pattern: **not used**. Recommendation node calls
  `recommender.py` directly rather than the LLM invoking a bound tool. Decided
  to avoid unneeded complexity since it doesn't serve any of the 4 topics.
- Streaming responses: **not used**. Skipped as a scope-control decision;
  request/response is fine, doesn't affect grading.
- Testing: small `pytest` suite specifically over the reducer and router
  functions (not full coverage) — this is the cheapest, most direct way to prove
  understanding of the graded mechanics.
- Containerization: Docker + Docker Compose (multi-service: api, postgres,
  chroma, maybe frontend).

## Graph design (Topic 1 & 2 — the core graded logic)

- Router node classifies user intent from the latest message, then a conditional
  edge branches to one of: `add_to_watchlist`, `mark_watched`,
  `get_recommendation`, `general_chat`.
- State channels:
  - `messages`: default `add_messages` reducer.
  - `watchlist`: **custom reducer** — appends new titles, updates status on
    existing ones by title (not a plain `operator.add`, since duplicates must
    update in place rather than pile up).
- Checkpointer: Postgres-backed, keyed by `thread_id`. Frontend must expose a
  thread switcher so two threads visibly stay isolated.
- Graph diagram: generate once at startup, expose via an endpoint/static file so
  the frontend can display it. Decision needed: `draw_ascii()` (zero deps, always
  works) vs `draw_mermaid_png()` (nicer, but typically calls an external renderer
  like mermaid.ink unless a local renderer is set up) — leaning `draw_ascii()`
  for reliability unless told otherwise.

## Memory design (Topic 4)

- Short-term: the checkpointer itself, per `thread_id`.
- Long-term: plain PostgreSQL tables (not LangGraph's `BaseStore` interface —
  deliberate choice to keep everything on one DB technology), keyed by
  `user_id`:
  - `profile` table: `display_name`, `favorite_genre`, `preferred_platform`.
  - `watchlist` table: `title`, `status` (`to_watch`/`watched`), timestamps —
    single table with a status flag, not two separate lists.
- A node reads both tables at the start of a new thread and seeds the graph
  state from them, so switching to a brand-new thread still shows previously
  learned preferences and watchlist items.

## Watchlist interaction mechanics (important — two different paths)

- Chat-driven adds ("add Dune", or an implicit "sure, add that" after a
  recommendation) go **through the graph** → router → reducer → synced to DB.
  This is where the reducer mechanics actually get exercised.
- Manual checkbox tick/untick in the watchlist UI bypasses the graph entirely —
  hits a plain `PATCH /watchlist/{id}`-style endpoint that flips status directly
  in Postgres. No LLM round-trip for something that doesn't need reasoning.

## Trimming (Topic 3)

- Before every Gemini call, trim message history to a token budget and/or
  filter out low-value messages.
- UI must visibly show the effect — e.g. "Messages sent to AI: 5 / 18" and
  "Tokens used: 340 / 1200" type readout.

## Frontend plan

- Angular, structured as real components (not a static mockup) — `core/`
  (services, guards, models), `shared/` (reusable components), `features/`
  (`login`, `chat`, `watchlist`, `how-it-works`), each roughly matching a page.
- Pages/tabs, kept as **separate tabs**, not crammed onto one screen:
  1. Login/signup (Firebase email+password).
  2. Chat — message history, thread switcher near the top, new-thread button,
     input + send.
  3. Watchlist — single list, watched/unwatched toggle per item, filter control
     (All/To Watch/Watched), small poster/thumbnail placeholder per item.
  4. How It Works — dashboard-style info tab showing: the graph diagram image,
     token/message trim stats, the user's stored profile/preferences, and their
     list of threads.
- Aesthetic: Y2K / early-2000s internet nostalgia (old MySpace/personal
  homepage energy) — glossy chunky buttons, gradients, sparkle/star motifs,
  retro "OS window" chrome (title bars, tiny minimize/close details), pixel
  accents. Two candidate palettes were sketched, not yet chosen between:
  dark+neon (black background, hot pink/magenta/electric accents, glow) vs
  pastel+candy (soft pink/lavender/baby blue, glossy candy buttons, cheerful).
  **This is a draft direction, not final — change freely if asked.**
- Decorative elements must frame the UI, not sit on top of readable content —
  chat bubbles, input fields, and list text need to stay legible under the
  maximalist styling.
- Logo: not finalized. Discussed concepts: (1) glossy pill/bubble wordmark with
  gradient + tiny star, (2) play-button-shape merged with a sparkle/star icon
  next to the wordmark (was the favored direction — works as a small favicon),
  (3) retro TV/monitor silhouette with star/heart on screen, (4) wordmark-only
  glossy bubble letters with orbiting stars. No final pick yet.
- Suggested optional asset packs (user will download into VS Code themselves,
  not blocking backend work): Google Fonts Fredoka/Baloo 2 (glossy bubble look)
  or Press Start 2P/VT323/Silkscreen (pixel look); Iconify sparkle/star SVGs;
  `98.css` or `xp.css` for ready-made retro window-chrome components; optional
  Y2K cursor packs; optional tileable scanline/glitter texture overlay from
  transparenttextures.com.

## Backend folder structure (already scaffolded, empty)

```
watchly/
├── api/
│   ├── main.py
│   ├── deps.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── threads.py
│   │   ├── chat.py
│   │   ├── watchlist.py
│   │   └── graph_diagram.py
│   └── schemas.py
├── auth/
│   └── firebase.py
├── db/
│   ├── base.py
│   ├── models.py
│   ├── profile_repo.py
│   ├── watchlist_repo.py
│   ├── thread_repo.py
│   └── migrations/
│       ├── env.py
│       └── versions/
├── graph/
│   ├── state.py
│   ├── reducers.py
│   ├── trimming.py
│   ├── router.py
│   ├── nodes.py
│   ├── build.py
│   └── diagram.py
├── recommendation/
│   ├── tmdb_client.py
│   ├── embeddings.py
│   ├── build_index.py
│   └── recommender.py
├── tests/
│   ├── test_reducers.py
│   └── test_router.py
├── static/
├── data/chroma/
├── secrets/                      # firebase-service-account.json goes here, gitignored
├── docs/                         # planning docs, regenerate as needed
├── frontend/                     # Angular app (see below)
├── .env.example
├── .gitignore
├── requirements.txt
├── alembic.ini
├── docker-compose.yml
└── CLAUDE.md                     # this file
```

## Note on the old planning docs

Earlier in this project, a set of planning docs was drafted (README, CONTRACTS,
ARCHITECTURE, REQUIREMENTS_MAPPING, AUTH_DESIGN, DB_SCHEMA, GRAPH_DESIGN,
RECOMMENDATION_DESIGN, API_SPEC, SETUP). Those were written in a previous chat
session's sandbox, which does not persist — their exact text is gone, but every
decision that mattered from them has been folded into this file above. Treat
this CLAUDE.md as the authoritative source going forward; the `docs/` folder is
scaffolded empty and can be repopulated later if wanted, but is not required for
the code to be consistent.

## Build workflow (why this file exists)

1. Backend folder skeleton created (empty) — done.
2. This file created — done.
3. Claude generates backend/frontend files one at a time, in dependency order
   (shared config and models first, then graph internals, then API routes, then
   frontend). User pastes each into the matching path in VS Code before asking
   for the next one.
4. If a chat runs out of tokens mid-project: open a new chat, paste this file,
   state which files are already done, and continue from there. This file is
   kept intentionally complete enough that a fresh session needs no other
   context to stay consistent with everything already built.
5. Do not let per-file naming, schema shapes, or endpoint names drift from what's
   written here — if something here turns out to be wrong or needs to change
   once code is underway, update this section of understanding explicitly with
   the user before continuing, rather than silently improvising a different
   shape in a later file.
