# Getting Started

## Prerequisites

- Python 3.11+
- Node 18+
- (Optional, for production-style local run) Docker + Docker Compose

## 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

- `SECRET_KEY` — replace with a long random string (`python -c "import secrets; print(secrets.token_urlsafe(64))"`).
- Set at least one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and
  make sure `DEFAULT_AI_PROVIDER` matches the one you set.
- Leave `DATABASE_URL` as the default SQLite path for local dev; switch to the
  Postgres URL (commented out in `.env.example`) when you're ready for
  something more production-like.
- Leave integration variables (Google, QuickBooks, Amazon, Shopify, social)
  blank until you're ready to connect each one — nothing else requires them.

## 2. Backend

```bash
pip install -r requirements.txt
make migrate      # applies Alembic migrations, creates data/jarvis.db
make dev          # runs uvicorn with --reload on http://localhost:8000
```

Visit `http://localhost:8000/docs` for interactive API docs (Swagger UI).

Register a user:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login -d '...'  # after registering
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@business.com", "password": "a-strong-password", "full_name": "You"}'
```

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. The dev server proxies `/api` to
`http://localhost:8000` (see `frontend/vite.config.ts`), so no CORS setup is
needed locally beyond what's already in `app/main.py`.

## 4. Running tests

```bash
make test
```

Covers auth flow, the plugin registry, and health check as a starting point —
add tests alongside every new plugin/integration/endpoint.

## 5. Docker (optional, closer to production)

```bash
docker compose up --build
```

Brings up Postgres, Redis, and the API together. Point `DATABASE_URL` in `.env`
at the Postgres service before doing this (see the commented example in
`.env.example`), and run `make migrate` once against that database.

## Adding an AI provider key

Nothing else needs to change — `app/ai_providers/factory.py` picks the right
class off `DEFAULT_AI_PROVIDER` (or a per-request override) and only
constructs it when first used, so you only need a key for the provider(s) you
actually use.

## Connecting an integration

Each integration under `app/integrations/` is currently either fully wired
(Shopify) or stubbed with `NotImplementedError` and a comment pointing at
exactly what to implement (the OAuth token exchange, mainly). Pick one, fill
in the TODOs, add its client id/secret to `.env`, and it's live — the
`/api/v1/integrations` endpoint and dashboard already know how to show its
connection status once `is_connected()` returns real data.
