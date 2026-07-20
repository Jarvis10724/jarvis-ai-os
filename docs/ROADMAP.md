# Roadmap

Rough order, not a commitment — reprioritize as the business needs shift.

## Near-term

- Add a self-service signup flow in the dashboard (currently register via API/docs only).
- Wire real conversation persistence (chat history per user/project, not just in-memory in the browser).
- Finish one real OAuth integration end-to-end (Shopify's read-only calls already work; Gmail or Google Drive is the natural next one since both integrations share the same Google OAuth app).
- Give `deep_research` a real web-search tool instead of reasoning from model knowledge alone.
- Wire `project_management` plugin output into actual `Project`/`Task` rows via the API (today it returns a suggested breakdown as text).

## Mid-term

- Background job execution for `automation` plugin designs (Redis + a worker — Redis is already provisioned in `docker-compose.yml`).
- File storage for generated assets (logo SVGs, website exports, generated code bundles) — local disk under `data/` to start, S3-compatible storage later.
- Multi-provider fallback (if the default AI provider errors, retry with a secondary one).
- Streaming chat responses in the dashboard (the backend's `stream()` method on each provider is already implemented; the UI currently only uses `complete()`).
- Real notifications backend (today's `NotificationsPanel` is mock data — needs an events/notifications table and a way for plugins/integrations to push into it).

## Longer-term

- Finish the remaining integrations: QuickBooks, Amazon SP-API, Instagram/Facebook/LinkedIn/X.
- Role-based access if this ever needs more than one user (schema already supports multiple `User` rows; no roles/permissions yet beyond `is_superuser`).
- Usage/cost tracking per AI provider call (token counts are already captured in `CompletionResult` — just need to persist and surface them).
- A proper plugin marketplace / entry-point-based discovery if third-party plugins ever make sense, instead of the current `builtin/` list.
