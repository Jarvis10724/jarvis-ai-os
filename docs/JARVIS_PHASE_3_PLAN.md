# Jarvis Phase 3 — Capabilities Platform

Phase 2 closed with the memory system fully verified: company workspaces are
isolated, scopes classify and filter correctly, and both automated suites
(`test_memory_scope.py`, `test_memory_integration.py`) pass. Phase 3 turns
Jarvis from something that remembers into something that acts — real Gmail,
Calendar, Drive, CRM, Shopify, Amazon, QuickBooks, and optionally
Slack/Discord — with every one of those actions passing through the same
approval, audit, isolation, and scheduling discipline. Build order is fixed
by the user's priority call:

1. Gmail (read, summarize, draft, send with approval)
2. Google Calendar
3. Google Drive / Docs
4. Contacts & CRM
5. Shopify
6. Amazon Seller Central
7. QuickBooks
8. Slack/Discord (optional)

Every capability must support human approval before external actions, audit
logs, company isolation, background agents, and scheduling. Rather than
build those five things eight times, this plan builds them once as shared
infrastructure, then treats each numbered item as a thin capability plugged
into it.

## What Phase 3 builds on

The plugin/integration split from Phase 1 is still the right shape and
doesn't need to be replaced. `BaseIntegration` (`app/integrations/base.py`)
already defines the OAuth contract every external service needs
(`get_authorization_url`, `exchange_code_for_token`, `is_connected`), and
`BasePlugin` (`app/plugins/base.py`) defines how a capability's actions get
invoked through the orchestrator. Seven integration classes already exist as
stubs — `EmailIntegration` (Gmail), `GoogleDriveIntegration`,
`QuickBooksIntegration`, `AmazonIntegration`, `ShopifyIntegration`, and three
social-media classes — each with real auth-URL scaffolding but
`NotImplementedError` on the actual token exchange and API calls. No
Calendar, Contacts, or Slack/Discord integration exists yet; those are net
new.

Two gaps matter more than the missing API calls. First,
`IntegrationCredential` already has a nullable `company_id` — multi-tenant
credential storage (one Gmail account per company) already works with zero
changes. `PluginConfig` does not: it's `owner_id` + `plugin_name` only, so
per-company enable/disable (which the user explicitly asked every capability
to support) doesn't exist yet and needs a `company_id` column added,
mirroring the pattern already proven in `IntegrationCredential` and in the
memory scope work. Second, nothing today asks permission before acting —
`orchestrator.run_plugin` executes immediately — and nothing schedules
anything: the `automation` plugin only *designs* a workflow via the AI
provider and stops there; Redis is provisioned in `docker-compose.yml` but
nothing reads or writes to it. Approval, audit, and scheduling are greenfield
work, not extensions of something partial.

One more gap worth naming honestly: Contacts & CRM (priority 4) sounds like
an integration, but the CRM itself doesn't exist as a real backend yet —
`CrmContact` today is frontend-only mock data
(`frontend/src/mock/crm.ts`). Priority 4 is really two projects: build a
real CRM backend, then sync external contacts into it. Flagging this now so
its complexity estimate isn't a surprise later.

## The Capability abstraction

A "Capability" is not a new base class replacing `BaseIntegration` or
`BasePlugin` — it's the coordination layer that sits between them and adds
the five required properties. Four new tables carry it:

**CapabilityConfig** (`plugin_configs` gains `company_id`, nullable —
null means account-wide, a real id means enabled/configured per company,
exactly like `IntegrationCredential` already works). This is what makes
"any future company workspace can enable or disable them independently"
true without per-capability code.

**ApprovalRequest** — `company_id`, `capability_name`, `action_type`,
`payload_json` (the proposed call — e.g. `{"to": ..., "subject": ...,
"body": ...}`), `status` (pending / approved / rejected / expired /
executed), `requested_by`, `decided_by`, `decided_at`, `executed_at`. The
rule: anything that writes to an external system (send an email, create a
calendar event, post a message, refund an order) is *proposed*, not run,
until a human approves it. Read-only actions (list messages, summarize,
pull inventory levels) execute directly — gating reads on approval would
make Jarvis unusable for its main job, which is surfacing information.

**CapabilityAuditLog** — mirrors `MemoryAuditLog`'s append-only, non-foreign-
keyed design on purpose: `capability_name`, `company_id`, `action`,
`before`/`after` snapshots where meaningful, actor, note, timestamp. Every
executed action (approved writes and direct reads alike) leaves a row, so
"what did Jarvis actually do to my Gmail / Shopify / QuickBooks" is always
answerable the same way memory history already is.

**ScheduledJob** — `company_id`, `capability_name`, `action_type`,
`payload_json`, a cron-like schedule string, `last_run_at`, `next_run_at`,
`enabled`. Backed by an in-process scheduler (APScheduler with a
database-backed jobstore) rather than standing up Celery workers against
the already-provisioned Redis right away — cheap to build, and sufficient
for the daily/hourly cadences these capabilities actually need (morning
email digest, daily calendar pull). If true parallel background agents are
needed later, Redis is already there to graduate into a real queue.

`app/core/capability_service.py` (mirroring `memory_service.py`'s
discipline exactly — ownership checks before every write, audit row after
every write) becomes the single funnel: `propose_action()`,
`approve_action()`, `reject_action()`, `execute_action()`,
`run_due_scheduled_jobs()`. Individual integration classes only need to
implement the real API calls; none of them reimplement approval, audit, or
scheduling.

## Sequencing and per-capability plan

**Foundation (build first, before any single capability):** the four
tables above plus their migration, `capability_service.py`, approval
endpoints (`GET /approvals`, `POST /approvals/{id}/approve`,
`POST /approvals/{id}/reject`), and a generic Approvals panel in the UI
(list pending actions, approve/reject with a note — reusable, not
per-capability). This is the highest-leverage work in the phase: every item
below plugs into it verbatim instead of building its own review flow.

**3a. Gmail** — value: highest. Email is the primary inbound channel; even
just summarize+draft removes daily overhead before send is ever touched.
Complexity: medium. `EmailIntegration.get_authorization_url` is already
correct; the real work is `exchange_code_for_token` against Google's token
endpoint, real Gmail API calls (`messages.list`/`get` for read,
`messages.send` for send), feeding reads into `memory_service.record_memory`
(kind=`email`, scoped per company, so email becomes searchable memory
alongside everything else), and new agent tools — `list_emails`,
`summarize_email`, `draft_email`, and `send_email` (the last routed through
`propose_action`). Getting Google's OAuth consent screen and refresh-token
handling right here pays off immediately, since 3b and 3c reuse the same
client. *User action:* register a Google Cloud project, enable the Gmail
API, create an OAuth 2.0 client, set `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`
— I can't create third-party developer accounts on your behalf.

**3b. Google Calendar** — value: high, direct Daily Brief payoff (today's
real meetings instead of the mock widget). Complexity: low once 3a lands —
same OAuth client, can request Calendar scope in the same consent grant.
New `CalendarIntegration` (list events directly, create-event gated by
approval). *User action:* enable the Calendar API on the same project — no
new registration if scopes are requested together with 3a.

**3c. Google Drive / Docs** — value: medium, lower daily urgency than email
or calendar but useful for SOP/decision context. Complexity: low-medium —
`GoogleDriveIntegration` stub already exists, same OAuth client again; the
work is file listing/search and Docs export, plus ingesting fetched
documents into memory (kind=`file`) so they're searchable like everything
else. *User action:* enable Drive/Docs APIs on the same project.

**3d. Contacts & CRM** — value: high long-term (one source of truth for
every relationship) but gated on the gap named above. This is really two
builds: a real `CrmContact` backend model with company-scoped CRUD
(replacing the frontend mock), then a People API sync as one contact
source among possibly several later. Complexity: medium-high, and
concentrated in the backend-from-scratch work, not the Google sync itself.
*User action:* none beyond enabling the People API on the same project.

**3e. Shopify** — value: high specifically for Primal Penni (it's the
e-commerce brand); real orders/inventory replace mock data in the existing
Inventory and Financial Dashboard modules. Complexity: medium —
`ShopifyIntegration` stub exists; Shopify's per-store OAuth and Admin API
are new surface, distinct from the Google client. Reads (orders, inventory
levels) execute directly; refunds/fulfillments go through approval.
*User action:* create a Shopify custom app / API credentials for the store.

**3f. Amazon Seller Central** — value: medium-high, most relevant once
Amazon Launch Center moves past planning. Complexity: high — SP-API's LWA
auth plus AWS SigV4 request signing is the heaviest integration tax on this
list, and Amazon's own developer approval process can take days to weeks
independent of anything Jarvis-side. *User action:* start SP-API developer
registration now, in parallel with 3a-3e, so the approval clock is running
before the code is written.

**3g. QuickBooks** — value: high (real financials replace the Financial
Dashboard's mock data) but sequenced after the commerce integrations on
purpose — books are only meaningful once Shopify/Amazon transactions are
already flowing in. Complexity: medium-high; Intuit's OAuth and
production-app review process is slower than Google's. *User action:*
register an Intuit Developer app and complete their review for production
access.

**3h. Slack/Discord (optional)** — value: lower unless you're actively
coordinating through one of these; worth re-confirming once 3a-3g are live
rather than assuming now. Complexity: low — bot-token/OAuth and a simple
send/post API, the cheapest item on the list. *User action:* create a
Slack app or Discord bot and install it.

## Practical parallelism

Foundation → 3a → 3b → 3c is one connected line of work (single Google
OAuth surface, approval/audit proven end-to-end on the highest-value case
first). 3d's backend-CRM work doesn't depend on Google and can start in
parallel once the foundation lands. 3e (Shopify) is also independent of the
Google surface and can run in parallel with 3a-3c. 3f and 3g are gated more
by external approval latency than by Jarvis-side build time, so their
*user action* items are worth starting now even though their code lands
later in the sequence. 3h stays last and stays optional.

## Before I start writing code

Confirm the foundation-first sequencing — it delays "see real email"
by roughly the time it takes to build approval/audit/scheduling once, in
exchange for not rebuilding it seven more times. And if you want to save
calendar time on 3f/3g, start those two registrations (Amazon SP-API,
Intuit Developer) now, in parallel — I'll give exact click-through steps
for the Google OAuth app (needed first, for 3a) when we start.
