# Jarvis Architecture

Jarvis is an AI operating system for running a business: one place to chat with an
assistant, run capabilities ("plugins") like building websites or designing logos,
and eventually let those capabilities read/write your email, Drive, QuickBooks,
Amazon, Shopify, and social accounts.

## Design goals

1. **Independently expandable.** Every capability (plugin) and every external
   connection (integration) is a self-contained unit behind a small interface.
   Adding one never requires touching the orchestrator, the API, or another
   plugin/integration.
2. **Provider-agnostic AI.** No code outside `app/ai_providers/` ever imports
   `openai`, `anthropic`, or `google.generativeai` directly. Swapping models or
   running multiple providers side by side is a config change, not a rewrite.
3. **Modular monolith, not microservices.** One deployable backend, one deployable
   frontend. Internally split into clean modules (`auth`, `db`, `ai_providers`,
   `plugins`, `integrations`, `api`) so it can be pulled apart into services later
   if/when that's actually needed — it shouldn't be needed for a while.
4. **Boring, auditable foundations.** Standard JWT auth, SQLAlchemy + Alembic,
   structured logging, typed config. Nothing exotic in the plumbing so the
   interesting work (what Jarvis can actually do) stays easy to extend.

## System overview

```
                              ┌─────────────────────────┐
                              │   Frontend (React/TS)   │
                              │  Dashboard · Chat · UI   │
                              └────────────┬─────────────┘
                                           │ REST (JWT bearer)
                              ┌────────────▼─────────────┐
                              │      FastAPI backend      │
                              │  app/api/v1/*  (routers)  │
                              └────────────┬─────────────┘
                    ┌───────────────┬──────┴───────┬────────────────┐
                    ▼               ▼              ▼                ▼
              ┌──────────┐   ┌────────────┐  ┌───────────┐   ┌─────────────┐
              │   auth   │   │ orchestrator│  │    db     │   │ ai_providers │
              │ JWT, users│  │  (core/)    │  │ SQLAlchemy │   │  Anthropic   │
              └──────────┘   └──────┬──────┘  │  + Alembic │   │  OpenAI      │
                                    │          └───────────┘   │  Gemini      │
                        ┌───────────┴────────────┐             └─────────────┘
                        ▼                        ▼
                 ┌─────────────┐          ┌──────────────┐
                 │   plugins   │          │ integrations │
                 │ web_builder │          │ email        │
                 │ logo_design │          │ google_drive │
                 │ product_... │          │ quickbooks   │
                 │ deep_research│         │ amazon       │
                 │ code_writer │          │ shopify      │
                 │ project_mgmt│          │ social_media │
                 │ automation  │          └──────────────┘
                 └─────────────┘
```

## Backend layout

```
backend/
  app/
    main.py              # FastAPI app, lifespan, CORS, router mounting
    config.py             # Settings (env-driven, one source of truth)
    logging_config.py     # structlog setup (console in dev, JSON in prod)
    exceptions.py         # JarvisError hierarchy + handlers -> consistent error JSON
    core/
      orchestrator.py     # single entry point for "run this plugin"
    auth/                 # JWT auth: security, schemas, dependencies, router
    db/
      base.py             # declarative base + UUID/timestamp mixins
      session.py          # engine + get_db() dependency
      models/             # User, Project, Task, PluginConfig, IntegrationCredential
    ai_providers/
      base.py             # BaseAIProvider — the only interface plugins depend on
      anthropic_provider.py / openai_provider.py / gemini_provider.py
      factory.py           # get_ai_provider(name) -> BaseAIProvider
    plugins/
      base.py              # BasePlugin — run(**kwargs) -> PluginResult
      registry.py           # discovery + lookup
      builtin/              # web_builder, logo_design, product_creation,
                             # deep_research, code_writer, project_management,
                             # automation — one folder per capability
    integrations/
      base.py               # BaseIntegration — OAuth + action methods
      registry.py            # discovery + lookup
      email_integration.py, google_drive_integration.py, quickbooks_integration.py,
      amazon_integration.py, shopify_integration.py, social_media_integration.py
    api/v1/
      router.py              # mounts every endpoint router under /api/v1
      endpoints/              # health, auth (re-exported), chat, plugins, projects,
                               # integrations, settings
  alembic/                    # migrations (env.py wired to app.config.settings)
  tests/                       # pytest: unit + integration
```

## Frontend layout

```
frontend/
  src/
    main.tsx / App.tsx        # router root, theme + auth providers
    context/                  # AuthContext, ThemeContext (dark mode)
    api/client.ts             # single fetch wrapper, attaches JWT, normalizes errors
    pages/Dashboard.tsx        # composes the HUD dashboard
    pages/Login.tsx
    components/                # Sidebar, TopNav, ChatPanel, RecentTasks,
                                # MetricsPanel, PortfolioSummary, CalendarWidget,
                                # NotificationsPanel, QuickActions
    types/                     # shared TS types mirroring backend schemas
```

React + TypeScript + Tailwind, built with Vite. Talks to the backend only through
`src/api/client.ts` — no component calls `fetch` directly.

## Core abstractions

### Plugins (`app/plugins/base.py`)

```python
class BasePlugin(ABC):
    name: str
    description: str
    version: str

    async def setup(self) -> None: ...          # optional one-time init
    async def run(self, **kwargs) -> PluginResult: ...
    def input_schema(self) -> dict: ...           # optional, for UI/docs
```

The orchestrator (`app/core/orchestrator.py`) is the only thing that calls
`plugin.run(...)`. It handles logging and error normalization so individual
plugins stay focused on their capability. Adding a capability = add a folder
under `plugins/builtin/`, subclass `BasePlugin`, register it in
`plugins/registry.py`.

### AI providers (`app/ai_providers/base.py`)

```python
class BaseAIProvider(ABC):
    async def complete(self, messages, *, model=None, ...) -> CompletionResult: ...
    async def stream(self, messages, *, model=None, ...): ...
```

`get_ai_provider(name)` in `factory.py` is the only way plugins/endpoints get a
provider instance. `DEFAULT_AI_PROVIDER` in `.env` picks the default; any call
can override it per-request.

### Integrations (`app/integrations/base.py`)

```python
class BaseIntegration(ABC):
    async def is_connected(self) -> bool: ...
    def get_authorization_url(self, redirect_uri, state) -> str: ...
    async def exchange_code_for_token(self, code, redirect_uri) -> dict: ...
```

Credentials live in the `integration_credentials` table, scoped per user.
Shopify's client is fully implemented (simple access-token auth) as a working
reference; Gmail/Drive/QuickBooks/Amazon/social platforms are stubbed with the
exact TODOs needed to finish each OAuth flow.

## Data model

`User` → owns → `Project` → has many → `Task` (optionally tied to a
`plugin_name` that produced it). `PluginConfig` and `IntegrationCredential` are
both scoped to a `User` so this is ready to be multi-user later even though v1
is single-owner.

## Error handling & logging

Every raised `JarvisError` subclass (`NotFoundError`, `ValidationError`,
`AuthenticationError`, `PluginError`, `IntegrationError`, `AIProviderError`, ...)
becomes a consistent `{"error": {"code", "message", "details"}}` response.
`structlog` gives every log line structured fields (`plugin`, `elapsed_ms`,
`user_id`, ...) — readable console output in dev, JSON in production for log
aggregators.

## What's real vs. stubbed today

- **Real and runnable:** auth (register/login/refresh/me), plugin registry +
  all 7 builtin plugins (call the configured AI provider directly), database
  layer + migrations, Shopify integration (read products/orders), the full
  dashboard UI.
- **Stubbed with a clear TODO:** Gmail, Google Drive, QuickBooks, Amazon
  SP-API, and social media integrations — each needs real OAuth app
  credentials from that platform before it can do more than report
  "not connected." Deep research doesn't call a live web-search tool yet — it
  reasons from the model's own knowledge and says so.

See `docs/ROADMAP.md` for what's next.
