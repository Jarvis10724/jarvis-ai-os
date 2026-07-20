# Quick Actions — Production Readiness Report

_Generated after end-to-end hardening validation of all six Quick-Action studio
workspaces (Build a Website, Design a Logo, Create a Product, Deep Research,
Write Code, Automate a Task) against the live app + real AI provider, in both
company workspaces (Primal Penni, Greener Capitol Solutions)._

## Validation matrix

Every Quick Action was driven end-to-end as a real user. Legend: ✅ verified live,
🧪 covered by deterministic integration test, — n/a.

| Concern | Website | Logo | Product | Research | Code | Automation |
|---|---|---|---|---|---|---|
| UI renders / stages | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Live streaming | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Structured panels populate | ✅ | ✅ | ✅ | ✅🧪 | ✅ | ✅ |
| Persistence / autosave | ✅🧪 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Artifacts (versioned) | ✅🧪 | ✅ (images) | ✅ | ✅ | ✅ | ✅ |
| Tasks (auto + lifecycle) | ✅🧪 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Company isolation | ✅🧪 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Restart / session restore | ✅🧪 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Approval flow (no unapproved writes) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (designs approval steps) |
| Error handling | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 |

Backend suite: **101 passed** (21 workspace tests incl. 8 hardening tests); the
only failure is a pre-existing, unrelated `google_calendar` health-check test.
Frontend: `tsc --noEmit` clean, production build clean, no runtime console errors.

## Completed features

- **Six dedicated studio workspaces** at `/studio/:action`, each with its own
  ordered stages (e.g. Website: requirements → sitemap → copy → design → code →
  preview; Automation: goal → trigger → actions → conditions → test → activity).
- **Persistent, company-scoped sessions** (`workspace_sessions`): full
  conversation history, versioned artifacts, and structured per-action state
  (`state_json`, migration `a1b2c3d4e5f6`).
- **Live SSE streaming** with server-side stripping of the `jarvis-state` block
  so the chat stays clean prose while panels fill with real generated data.
- **Structured-state robustness**: mislabeled-block detection (```json/``` →
  matched by the action's state keys), empty/missing-block **structuring
  fallback** (a second pass reconstructs state from the deliverable), and
  **persist-before-`done`** so the client's refetch always sees saved state.
- **Auto Project + Task creation**; task lifecycle (kick-off → per-turn task →
  `review` on success / `backlog` on failure); add-task and attach-project.
- **Versioned artifacts** + explicit save; Deliverables tab with version chain.
- **AI Memory** written per turn, scoped to company/organization.
- **Image-generation seam** (OpenAI `gpt-image-1`) with graceful "not
  configured" degrade — never fabricates images. Logo concepts carry image
  prompts + palettes.
- **Web-search seam** for Research — unconfigured today, so sources are marked
  `derived` and no URLs are fabricated (honest by design).
- **Session management**: rename, archive/unarchive, cross-action Recent
  switcher, new session, last-session restore (per-action + global), and live
  autosave / streaming / error-recovery status with retry.
- **Company isolation** verified across Primal Penni and Greener Capitol.
- **Error handling**: consistent status codes (422/404/502), in-band SSE error
  events, task reset on failure, disconnect-safe persistence, owner-scoped
  access (cross-user access → 404).
- **Approval-flow invariant**: workspaces perform no external writes; the
  Approval Center stays empty. Automation *designs* approval-gated steps and
  starts **disabled**.

## Remaining issues / limitations

1. **Image generation needs `OPENAI_API_KEY`** — currently records concept specs
   instead of generating images (seam ready, degrades cleanly).
2. **Deep Research has no live web search** — reasons from model knowledge;
   sources flagged `derived`. Seam ready for a search provider.
3. **Automation is design-time only** — enable/disable, trigger, and test-mode
   are state flags, not a live runtime. No scheduler/executor is wired yet.
4. **Structuring-fallback cost** — on turns where the model omits/empties the
   state block (mostly long research reports), one extra model call (~2–4s) runs.
5. **Transient stream flash** — a mislabeled ```json state block can briefly
   show mid-stream before the clean refetch; the *persisted* transcript is clean.
6. **`max_tokens=8192` cap** — an extremely long single turn could still truncate
   prose (panels are covered by the fallback; rare).
7. **Active-company on hard reload** — a full page reload can reset the active
   company via the shell's `WorkspaceSwitcherPopover`; client-side nav preserves
   it. `CompanyContext` persists `ACTIVE_COMPANY_KEY`, so worth confirming the
   switcher writes it on select. (Existing shell behavior, not workspace code.)
8. **Frontend bundle > 500 KB** (no route code-splitting) — load-time optimization.
9. **Pre-existing unrelated test** — `google_calendar` health-check expects
   `error` but now returns `disconnected` (a real integration exists). To fix
   next, per instruction.

## Recommended integrations

| Integration | Enables | Status |
|---|---|---|
| OpenAI image API key | Logo Studio real concept images | Seam ready |
| Web search (Tavily / Brave / SerpAPI) | Research live sources + real citations | Seam ready |
| Scheduler + executor (existing scheduled-tasks infra) | Automation live runs via Approval Center | Design ready |
| Static host / deploy (Netlify, preview URL) | Website real published preview + saved versions | Preview renders inline today |
| Sandboxed test runner | Code Studio real test execution (vs. model-reported) | Status field ready |
| Shopify (already read-only) | Real inventory feeding Automation / Product | Implemented |

## Next development priorities

1. **Wire web search for Deep Research** — biggest credibility gain; seam exists.
2. **Configure image generation for Logo** — quick win; seam exists.
3. **Automation runtime** — connect enable + trigger to the scheduler and route
   executions through the Approval Center (turns the design tool into a working
   automation).
4. **Website preview hosting + export** — make Preview / saved versions a real
   deployable artifact.
5. **Code test-execution sandbox** — replace model-reported test status.
6. **Frontend code-splitting** for the studio route; shrink the bundle.
7. **Streaming polish** — suppress the mislabeled-block flash client-side, and/or
   tighten the prompt so the model reliably emits `jarvis-state` (avoids the
   fallback cost).
8. **Confirm active-company persistence** across hard reloads.
