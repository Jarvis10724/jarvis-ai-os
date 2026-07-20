# Jarvis

An AI operating system for running your business — one assistant that can build
websites, design logos, spec products, do deep research, write code, manage
projects, automate repetitive work, and (as each is connected) read/write your
email, Google Drive, QuickBooks, Amazon, Shopify, and social accounts.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for how it's built and
[`docs/GETTING_STARTED.md`](./docs/GETTING_STARTED.md) to run it locally.

## Quick start

```bash
# 1. Configure
cp .env.example .env
# edit .env — at minimum set SECRET_KEY and one AI provider API key

# 2. Backend
pip install -r requirements.txt
make migrate         # create the database schema
make dev              # http://localhost:8000  (docs at /docs)

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev           # http://localhost:5173
```

Register your first user at `POST /api/v1/auth/register` (or via the login
screen — it currently expects an existing account; use the API/docs at
`/docs` to register one, or add a signup form as a next step) and sign in.

## Repository layout

```
backend/       FastAPI app, plugins, integrations, AI provider abstraction
frontend/      React + TypeScript + Tailwind dashboard
docs/          Architecture, setup, plugin development, roadmap
scripts/       One-off setup/utility scripts
data/          SQLite DB + logs (gitignored, created at runtime)
```

## Status

This is v1: the architecture, auth, database, plugin system, AI provider
abstraction, and dashboard are built and working. Most external integrations
(Gmail, Drive, QuickBooks, Amazon, social media) are stubbed with clear TODOs —
Shopify is the one fully wired example. See `docs/ROADMAP.md`.
