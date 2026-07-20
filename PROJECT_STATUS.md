# Jarvis — Project Status

_Snapshot at the `production-ready-base` commit._

Jarvis is an AI operating system for running a business: an AI-OS shell with a
Voice Orb, six Quick-Action studio workspaces, company workspaces, AI Memory, an
Approval Center, and a provider-agnostic AI layer. Backend is a FastAPI modular
monolith (SQLAlchemy + Alembic); frontend is React + TypeScript + Vite.

## Completed features

### Platform
- **Auth** — JWT register/login/refresh/me.
- **Provider-agnostic AI** (`app/ai_providers/`) — Anthropic (default), OpenAI,
  Gemini behind one `BaseAIProvider`; image generation seam (`generate_image`).
- **Database** — SQLAlchemy models + Alembic migrations; SQLite in dev, Postgres-ready.
- **Multi-company** — company-scoped data and workspaces (Primal Penni, Greener
  Capitol Solutions), with a workspace switcher.
- **AI Memory** — embeddings-backed, searchable, scoped to organization/company/project.
- **Approval Center** — every external write a capability proposes waits for human
  approval; company-scoped queue with pending/approved/rejected/executed states.
- **Capability framework** — declarative registry (`capabilities_registry.py`) +
  `capability_service` for permissions, health checks, approvals, scheduled jobs.
- **Error handling & logging** — typed `JarvisError` hierarchy → consistent JSON,
  structlog structured logging.

### Quick-Action workspaces (six, production-hardened)
Each is a dedicated studio at `/studio/:action` with its own ordered stages,
persistent company-scoped sessions (`workspace_sessions`), live SSE streaming,
structured `state_json` panels, versioned artifacts, auto Project + Task
creation, AI-Memory writes, and session management (rename, archive/unarchive,
cross-action Recent, last-session restore, autosave/streaming/error status).

- **Build a Website** — requirements → sitemap → copy → design → code → preview.
- **Design a Logo** — discovery → brief → concepts → images (gen seam) → revisions → exports.
- **Create a Product** — concept → positioning → spec → packaging → pricing → manufacturing → launch checklist.
- **Deep Research** — plan → sources → progress → citations → notes → report
  (currently model-knowledge only; sources marked `derived`).
- **Write Code** — requirements → file tree → files → tests.
- **Automate a Task** — goal → trigger → actions → conditions → test mode →
  activity, with approval-gated steps and disabled-by-default state.

Structured-state robustness: server-side `jarvis-state` stripping, mislabeled-block
detection, empty/missing-block structuring fallback, persist-before-`done`.

### Test & build health
- Backend: **102 passing** (pytest), incl. 21 workspace tests with error-handling,
  fallback, mislabeled-block, image, and full-restore coverage.
- Frontend: `tsc --noEmit` clean, production build clean, no runtime console errors.

## Configured integrations

| Integration | State |
|---|---|
| Anthropic (default LLM) | ✅ Configured (`ANTHROPIC_API_KEY`) |
| OpenAI / Gemini | Keys optional; wired, off unless keyed |
| Image generation (OpenAI `gpt-image-1`) | Seam ready; **needs `OPENAI_API_KEY`** |
| Shopify (read-only) | ✅ Implemented (Admin API) |
| Gmail / Google Calendar / Google Drive | Integration classes exist; **need OAuth credentials** (report `disconnected`) |
| QuickBooks / Amazon SP-API | Integration classes exist; need credentials |
| Social (Twitter/LinkedIn/Facebook/Instagram) | Integration classes exist; need credentials |
| Slack / Discord / Contacts CRM | Declared in capability registry; **no integration class yet** (health `error`) |
| Web search (Deep Research) | ❌ Not integrated at this commit (next work item) |

## Remaining work

- **Live Deep Research** — modular web-search provider with citations, caching,
  source attribution (implemented immediately after this commit).
- **Image generation activation** — set `OPENAI_API_KEY`.
- **Automation runtime** — connect enable/trigger to a scheduler + Approval Center
  execution (currently design-time only).
- **Website preview hosting/export** — make Preview/saved versions deployable.
- **Code test-execution sandbox** — real test runs vs. model-reported status.
- **OAuth credentials** for Gmail/Calendar/Drive/QuickBooks/Amazon/social to move
  those capabilities from `disconnected` to live.
- **Frontend code-splitting** — main bundle > 500 KB.

## Known limitations

- Deep Research reasons from model knowledge only until web search is wired;
  sources are marked `derived` and no URLs are fabricated.
- Image generation records concept specs (no images) until an image key is set.
- Automation workspaces design workflows but do not execute them.
- Code Studio reports test status from the model; tests are not actually run.
- A full page reload can reset the active company via the shell's workspace
  switcher; client-side navigation preserves it.
- `.gitignore` currently ignores `backend/alembic/versions/*.py`; migrations were
  force-added to this commit so the schema is complete — consider un-ignoring them.
- The structuring-fallback pass adds one extra model call (~2–4s) on turns where
  the model omits/empties its `jarvis-state` block (mostly long research reports).
