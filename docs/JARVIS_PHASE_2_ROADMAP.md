# Jarvis Phase 2 — AI Chief Operating Officer Roadmap

Phase 1 built the operating system's shell: multi-company data model, plugins,
auth, and a stable UI. Phase 2 turns Jarvis into something that actually runs
the business — real memory, real integrations, real daily prioritization.
This doc is the master plan. It supersedes the old `ROADMAP.md` for anything
the two disagree on; `ROADMAP.md`'s remaining items (background job queue,
websocket streaming, etc.) still stand as later polish.

Build order below is fixed by the user's priority call: business leverage
over UI, in this sequence. Each phase lists what's real today, what has to be
built, and what only the user can do (registering developer accounts,
generating tokens) — I can't create third-party accounts or hold credentials
on anyone's behalf.

## Phase 1 — CEO Dashboard

**Today:** `Dashboard.tsx` already shows chat, a metrics strip, recent tasks,
calendar, and a portfolio widget — all mock data except the chat panel.

**Build:** Rework it into a true CEO homepage with clearly separated real vs.
sample sections: today's highest-ROI tasks (heuristic ranking until Phase 10
brings AI ranking), urgent issues (derived from real signals — low
inventory, overdue project tasks — where those exist), cash, Amazon, Shopify,
inventory, calendar, email, notifications. Every section gets a `SampleDataBadge`
until its underlying phase ships real data. No new external dependency —
buildable immediately.

**User action:** none.

## Phase 2 — Memory System — done

**Built:** `MemoryEntry` (owner-scoped, optional company_id — null means
global/personal) and `MemoryLink` (typed edges between entries, so memory is
a graph, not a flat log) tables, migrated via
`e7a1f4c9b210_add_memory_entries_and_links`. Every kind the user asked for is
supported: conversation, email, meeting, quote, sop, decision, contact,
product, task, file, fact, other — as a plain string list
(`app/db/models/memory.py::MEMORY_KINDS`), not a DB enum, so adding a new
kind later is a one-line change.

`app/core/memory_service.py` is the single ingestion + search funnel —
`record_memory()`, `search_memory()`, `get_entry_with_links()`,
`link_memories()`, `delete_memory()`, `reembed_all()`. Every future
integration (Gmail, Calendar, Shopify, Amazon, QuickBooks, Slack, SMS) is
meant to call `record_memory()` after fetching new data — no integration
should invent its own storage for "things that happened."

Embeddings (`app/core/embeddings.py`): uses OpenAI's `text-embedding-3-small`
when `OPENAI_API_KEY` is set (real semantic search — catches paraphrases),
falls back to a dependency-free deterministic hashing embedding when it's
not (lexical/keyword-ish matching only — works day one, no install
required). Because the two produce incompatible vector spaces,
`search_memory` compares same-model entries by cosine similarity and falls
back to token overlap for the rest, so nothing is silently excluded from
search either way. Run `scripts/reembed_memory.py` once after adding an
OpenAI key to upgrade existing entries to real embeddings.

Chat (`api/v1/endpoints/chat.py`) auto-records every exchange as a
`conversation` memory entry, scoped to whatever company is active in the UI
(or global if none). Two new agent tools — `remember` and `search_memory` —
let Jarvis save durable facts/decisions/quotes proactively and pull up past
context mid-conversation; both default to the active company when the model
doesn't specify one, so scoping works without extra round-trips. A `/memory`
page (search bar, kind/company filters, linked-entry view, manual add) makes
all of this browsable outside of chat too, and the top nav's search bar
(previously decorative) now searches memory directly.

**User action:** optionally add `OPENAI_API_KEY` for real semantic search
(works without it, just with weaker recall).

**Scopes (added after initial build):** every entry is also classified into
exactly one of Global, Organization, Company, Project, or Personal
(`app/core/memory_scope.py`). Global covers anything system-wide or that
spans multiple companies — content that's cross-company always collapses
to one Global entry rather than being guessed into a single company's
bucket. Organization is the default for business content with no company
active. Company/Project require a real company_id/project_id. The
`remember` tool's description carries the full classification guidance,
including exactly when Jarvis should ask the user instead of guessing
(only for genuinely ambiguous cases, not the common ones) — passive
per-turn conversation logging uses a simpler deterministic default
(company if one's active, else organization) since it can't reason about
content the way an explicit `remember` call does.

## Phase 3 — Gmail Integration

**Today:** `EmailIntegration.get_authorization_url()` builds a real Google
OAuth URL. `exchange_code_for_token`, `send_email`, `list_recent_messages` are
all `NotImplementedError` stubs. There is no OAuth callback endpoint anywhere
in the API — nothing receives the `code` Google redirects back with. This is
a hard blocker for every OAuth-based phase (3, 4, and optionally 6/8), so it
gets built once here and reused.

**Build:** `GET /integrations/{name}/callback` — exchanges the code, persists
tokens to `IntegrationCredential`. Finish Gmail's token exchange and real
Gmail API calls (list, search, draft, send) via direct REST calls with
`httpx`. Tools: `list_recent_emails`, `search_emails`, `draft_email`. Sending
mail is message-on-your-behalf territory — Jarvis will compose and hold
drafts, but actually sending requires an explicit confirm click in the UI,
not a silent chat action.

**User action:** create a Google Cloud project, configure the OAuth consent
screen, create an OAuth 2.0 Web client ID, add `GOOGLE_CLIENT_ID` /
`GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` to `.env`.

## Phase 4 — Calendar Integration

**Today:** nothing exists — no calendar integration class, no events model.

**Build:** New `CalendarIntegration` (`BaseIntegration` subclass) using the
same Google OAuth app as Gmail with an added Calendar scope — one consent
screen, two capabilities. Tools: `get_todays_schedule`,
`list_upcoming_events`, `create_calendar_event`. Feeds the CEO Dashboard's
calendar section and, later, Phase 10's deadline awareness.

**User action:** add the Calendar scope to the same Google OAuth client from
Phase 3 (no new account needed).

## Phase 5 — Voice Assistant Upgrade

**Today:** click-to-talk works — Web Speech API for input, speech synthesis
for replies. Not hands-free.

**Build:** true OS-level "always listening for a wake word" isn't something
a browser tab can do — browsers require an explicit user gesture to open the
mic, and pause recognition when the tab isn't focused. The practical web
approximation: run `SpeechRecognition` in continuous mode while the Chat page
is open, locally match the transcript against "Jarvis" / "Hey Jarvis" in JS,
and only fire a request when the wake phrase is heard. This needs a clear
always-listening indicator in the UI since continuous mic capture is
privacy-sensitive. A true background wake word (works with the screen
locked, other apps focused) would need a native menu-bar helper app — out of
scope for this phase, noted as a future option if wanted.

One clarification on the NexiGo mic: it's a standard USB microphone — no
special SDK needed. Whatever the OS/browser has set as the default input
device is what Jarvis hears; the only setup is making sure that's the NexiGo
in system sound settings.

**User action:** none beyond OS mic selection.

## Phase 6 — Shopify Integration

**Today:** further along than the others. `ShopifyIntegration` uses a
custom-app access token (not OAuth) and `list_products` / `list_orders` are
fully implemented real Admin API calls — they'll work the moment
`SHOPIFY_SHOP_URL` and `SHOPIFY_ACCESS_TOKEN` are set. Nothing writes yet
(no inventory updates, no customer/abandoned-cart data, no sales dashboard
aggregation).

**Build:** add `list_customers`, `list_abandoned_checkouts`,
`update_inventory_level`; build the sales dashboard aggregation (orders →
revenue/units over time) as a real Jarvis-side computation over the API
data, and wire real values into the CEO Dashboard's Shopify section.

**User action:** in Shopify Admin → Settings → Apps → Develop apps, create a
custom app, grant it the needed scopes, generate an access token, set
`SHOPIFY_SHOP_URL` / `SHOPIFY_ACCESS_TOKEN`.

## Phase 7 — Amazon Seller Central

**Today:** stub. `is_connected` just checks for a refresh token;
`list_orders` / `get_inventory_summary` / token refresh are all
unimplemented.

**Build:** LWA refresh-token exchange, SP-API calls for orders, FBA
inventory, and — new — reviews, advertising spend, and payouts. SP-API is
the heaviest integration here: it needs an AWS IAM role in addition to the
Amazon developer app, and Amazon's app-authorization review can take real
calendar time that's outside anyone's control. Flagging that lead time now so
it doesn't look like a stalled build later.

**User action:** register as an SP-API developer, create an IAM role/user,
self-authorize the app in Seller Central, generate the refresh token, set
`AMAZON_SP_API_CLIENT_ID` / `SECRET` / `REFRESH_TOKEN`.

## Phase 8 — Financial Dashboard

**Today:** `QuickBooksIntegration` is a stub (OAuth URL builder works, token
exchange and invoice calls don't). No bank or crypto integration exists at
all — bank accounts need a provider like Plaid (not currently in the
codebase in any form), and crypto needs to know which
exchanges/wallets are in play before I can pick an API.

**Build:** finish QuickBooks OAuth + read calls (invoices, expenses, P&L).
Add a new Plaid integration for bank balances/transactions. Add a crypto
integration once the platforms are known — this is a genuine open question,
not an oversight.

**User action:** Intuit developer account + app for QuickBooks; a Plaid
developer account for banking; and tell me which exchanges/wallets to
support for crypto so I build against the right API.

## Phase 9 — SOP System

**Today:** the SOP Library page is a read-only viewer over mock data —
there's no SOP database table, no CRUD, and no execution engine.

**Build:** real `Sop` + `SopStep` tables (title, category, steps — each step
optionally mapped to an agent tool call with an argument template, or marked
manual). CRUD endpoints and UI. An `execute_sop` flow where Jarvis walks
through each step in a conversation — running automatable steps itself via
the existing tool registry, and prompting for confirmation or input on
manual ones.

**User action:** none technically, but this phase is most useful once you've
told Jarvis a handful of real recurring workflows to turn into SOPs.

## Phase 10 — AI CEO Brain

**Today:** no ranking or prioritization logic exists.

**Build:** a ranking pass (on-demand now, schedulable via the existing
`schedule` skill for a daily run later) that gathers real signals — overdue
tasks, low inventory, cash position, and once shipped: unread urgent email
(Phase 3), calendar deadlines (Phase 4), Shopify/Amazon anomalies (Phases 6–7)
— and asks the model to rank and recommend. Surfaces on the Phase 1
dashboard. Deliberately sequenced last because it's the capstone that gets
more useful as each earlier phase adds a real data source, but a v1 using
just today's real signals (products, tasks) can ship before the integration
phases are done.

**User action:** none; optionally schedule the daily run once built.

## Sequencing notes

Phases 1, 2, 5, and 9 need no external accounts and can be built back-to-back
without waiting on the user. Phases 3/4 share one Google OAuth app — worth
setting up once. Phase 7 (Amazon) has the longest external lead time
(developer review), so if there's ever a moment to kick off that
registration early, doing it in parallel with Phase 3–6 work avoids it being
the long pole later.
