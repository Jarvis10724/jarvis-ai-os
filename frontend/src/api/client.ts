/**
 * Thin fetch wrapper around the Jarvis API. Every call goes through here so
 * auth headers, base URL, and error shape are handled in one place.
 */
import type {
  ApprovalRequestView,
  ApprovalStatus,
  CalendarEventView,
  CapabilityAuditEntry,
  CapabilityView,
  ChecklistItem,
  Company,
  CompanyOwner,
  CompanySection,
  CompanyTask,
  ExecutiveSummary,
  GmailMessage,
  GmailMessageDetail,
  IntegrationStatus,
  MarketHeadline,
  MarketQuote,
  MemoryAuditEntry,
  MemoryEntry,
  MemoryEntryDetail,
  MemoryKind,
  MemoryScope,
  Persona,
  PluginInfo,
  PluginSettingRead,
  Product,
  ProjectSummary,
  ProjectOverview,
  ProjectEvent,
  Agent,
  AgentRun,
  AgentRunDetail,
  Client,
  ShopifyStatus,
  BrandBrainSummary,
  BrandProduct,
  BrandCollection,
  BrandBrainSyncResult,
  CommandDecision,
  WorkRun,
  WorkspaceIntelligence,
  WorkspaceArtifact,
  WorkspaceConfig,
  WorkspaceDetail,
  WorkspaceSummary,
  WorkspaceTask,
  ScheduledJobView,
  ToolCallLog,
} from "@/types";

const API_BASE = "/api/v1";
const ACCESS_TOKEN_KEY = "jarvis_access_token";
const REFRESH_TOKEN_KEY = "jarvis_refresh_token";

// Dispatched once a refresh attempt has genuinely failed (refresh token
// missing, expired, or rejected) — AuthContext listens for this to clear
// its `user` state in sync with the tokens getting cleared here. Without
// this, a 401 that happened outside of AuthContext's own mount check (e.g.
// mid-session, from any random API call) would clear localStorage but leave
// the app still rendering as "logged in" until the next full reload.
export const SESSION_EXPIRED_EVENT = "jarvis:session-expired";

function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(ACCESS_TOKEN_KEY, token);
  else localStorage.removeItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setRefreshToken(token: string | null) {
  if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
  else localStorage.removeItem(REFRESH_TOKEN_KEY);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// A 401 on an authenticated request almost always means the short-lived
// access token (60 min) expired, not that the session itself is invalid —
// that's exactly what the longer-lived refresh token (7 days) is for.
// `refreshInFlight` de-dupes concurrent 401s (e.g. several widgets fetching
// at once) so only one POST /auth/refresh goes out; everyone else awaits
// the same result instead of racing to refresh independently.
let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        // Deliberately a raw fetch, not apiRequest — this call must never
        // itself go through the 401-retry path below.
        const response = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) return false;
        const data = await response.json();
        setToken(data.access_token);
        setRefreshToken(data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

function clearSession() {
  setToken(null);
  setRefreshToken(null);
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
  _isRetryAfterRefresh = false
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && auth && !_isRetryAfterRefresh) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest<T>(path, options, true);
    }
    clearSession();
  }

  if (!response.ok) {
    let message = `Request to ${path} failed (${response.status})`;
    try {
      const data = await response.json();
      message = data?.error?.message ?? message;
    } catch {
      // ignore parse errors, fall back to default message
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    apiRequest<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  me: () => apiRequest("/auth/me"),
  chat: (messages: { role: string; content: string }[], companyId?: string | null, persona?: string | null) =>
    apiRequest<{ text: string; provider: string; model: string; tool_calls: ToolCallLog[] }>("/chat", {
      method: "POST",
      body: { messages, company_id: companyId ?? null, persona: persona ?? null },
    }),
  // "AI Executives" — specialist personas sharing the same memory/tools as
  // the default CEO Assistant (see backend app.core.personas).
  listPersonas: () => apiRequest<Persona[]>("/chat/personas"),
  listPlugins: () => apiRequest<PluginInfo[]>("/plugins"),
  runPlugin: (name: string, args: Record<string, unknown>) =>
    apiRequest<{ success: boolean; output: unknown; message: string; metadata: Record<string, unknown> }>(
      `/plugins/${name}/run`,
      { method: "POST", body: { args } }
    ),
  // Projects — the durable, company-scoped shared container every Quick
  // Action attaches to. `companyId`: omit for all, "none" for null-company,
  // or a real company id (mirrors the workspaces/clients sentinel).
  listProjects: (companyId?: string | "none") => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<ProjectSummary[]>(`/projects${qs}`);
  },
  getDefaultProject: (companyId?: string | null, clientId?: string | null) => {
    const qs = new URLSearchParams();
    if (companyId) qs.set("company_id", companyId);
    if (clientId) qs.set("client_id", clientId);
    const q = qs.toString();
    return apiRequest<ProjectSummary>(`/projects/default${q ? `?${q}` : ""}`);
  },
  createProject: (payload: {
    name: string;
    description?: string;
    company_id?: string | null;
    client_id?: string | null;
  }) => apiRequest<ProjectSummary>("/projects", { method: "POST", body: payload }),
  getProject: (id: string) => apiRequest<ProjectSummary>(`/projects/${id}`),
  getProjectOverview: (id: string) => apiRequest<ProjectOverview>(`/projects/${id}/overview`),
  getProjectTimeline: (id: string, limit?: number) =>
    apiRequest<ProjectEvent[]>(`/projects/${id}/timeline${limit ? `?limit=${limit}` : ""}`),
  listIntegrations: (companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<IntegrationStatus[]>(`/integrations${qs}`);
  },
  // Server-side OAuth: this only ever asks the backend for a URL and
  // navigates the browser to it. The frontend never sees client_secret,
  // access_token, or refresh_token — Google redirects back to a backend
  // callback, not to the SPA.
  getIntegrationAuthorizeUrl: (name: string, companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<{ url: string }>(`/integrations/${name}/authorize-url${qs}`);
  },
  disconnectIntegration: (name: string, companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<{ deleted: boolean }>(`/integrations/${name}${qs}`, { method: "DELETE" });
  },

  // Gmail — read/search/summarize/draft execute immediately; send/forward/
  // trash/archive/labels only ever propose an approval (see /approvals).
  listGmailMessages: (params: { companyId?: string; query?: string; unreadOnly?: boolean; maxResults?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.companyId) qs.set("company_id", params.companyId);
    if (params.query) qs.set("query", params.query);
    if (params.unreadOnly) qs.set("unread_only", "true");
    if (params.maxResults) qs.set("max_results", String(params.maxResults));
    return apiRequest<GmailMessage[]>(`/gmail/messages?${qs.toString()}`);
  },
  getGmailMessage: (messageId: string, companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<GmailMessageDetail>(`/gmail/messages/${messageId}${qs}`);
  },
  summarizeGmailUnread: (companyId?: string, maxResults?: number) => {
    const qs = new URLSearchParams();
    if (companyId) qs.set("company_id", companyId);
    if (maxResults) qs.set("max_results", String(maxResults));
    return apiRequest<{ summary: string; count: number }>(`/gmail/summary?${qs.toString()}`);
  },
  summarizeGmailMessage: (messageId: string, companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<{ summary: string; count: number }>(`/gmail/messages/${messageId}/summary${qs}`);
  },
  createGmailDraft: (payload: {
    company_id?: string | null;
    to?: string;
    subject?: string;
    body: string;
    thread_id?: string | null;
    reply_to_message_id?: string | null;
  }) => apiRequest<{ draft_id: string }>("/gmail/drafts", { method: "POST", body: payload }),
  proposeGmailSend: (payload: {
    company_id?: string | null;
    to: string;
    subject: string;
    body: string;
    thread_id?: string | null;
    in_reply_to?: string | null;
  }) => apiRequest<ApprovalRequestView>("/gmail/send", { method: "POST", body: payload }),
  proposeGmailForward: (messageId: string, payload: { company_id?: string | null; to: string; note?: string }) =>
    apiRequest<ApprovalRequestView>(`/gmail/messages/${messageId}/forward`, { method: "POST", body: payload }),
  proposeGmailTrash: (messageId: string, companyId?: string | null) =>
    apiRequest<ApprovalRequestView>(`/gmail/messages/${messageId}/trash`, {
      method: "POST",
      body: { company_id: companyId ?? null },
    }),
  proposeGmailArchive: (messageId: string, companyId?: string | null) =>
    apiRequest<ApprovalRequestView>(`/gmail/messages/${messageId}/archive`, {
      method: "POST",
      body: { company_id: companyId ?? null },
    }),
  proposeGmailLabels: (
    messageId: string,
    payload: { company_id?: string | null; add_labels?: string[]; remove_labels?: string[] }
  ) => apiRequest<ApprovalRequestView>(`/gmail/messages/${messageId}/labels`, { method: "POST", body: payload }),

  // Calendar — read (list/get) executes immediately; create/update/delete
  // only ever propose an approval (see /approvals), mirroring Gmail.
  listCalendarEvents: (params: { companyId?: string; maxResults?: number; upcomingOnly?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (params.companyId) qs.set("company_id", params.companyId);
    if (params.maxResults) qs.set("max_results", String(params.maxResults));
    if (params.upcomingOnly !== undefined) qs.set("upcoming_only", String(params.upcomingOnly));
    return apiRequest<CalendarEventView[]>(`/calendar/events?${qs.toString()}`);
  },

  // CEO Dashboard's AI-generated executive briefing — the caller gathers
  // the real digest (unread email, pending approvals, today's meetings,
  // out-of-stock products, needs-rebuild sections) from data it already
  // has/fetches for the other dashboard cards; this just turns it into
  // readable prose + prioritized action items via the AI provider.
  getExecutiveSummary: (digest: {
    company_name?: string | null;
    unread_email_count?: number;
    email_subjects?: string[];
    pending_approvals_count?: number;
    approval_summaries?: string[];
    todays_meeting_titles?: string[];
    out_of_stock_products?: string[];
    needs_rebuild_sections?: string[];
  }) => apiRequest<ExecutiveSummary>("/dashboard/executive-summary", { method: "POST", body: digest }),

  // Daily Briefing — stored as a memory entry (source="daily_briefing") so
  // "every morning, automatically" just means whatever generated it most
  // recently (the in-app "Generate now" button, or a scheduled task that
  // can also do a live web search for news) already ran. getLatest()
  // resolves to null if nothing has ever been generated yet.
  getLatestDailyBriefing: (companyId?: string | null) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<{ content: string; generated_at: string | null } | null>(
      `/dashboard/daily-briefing/latest${qs}`
    );
  },
  saveDailyBriefing: (content: string, companyId?: string | null) =>
    apiRequest<{ content: string; generated_at: string | null }>("/dashboard/daily-briefing", {
      method: "POST",
      body: { content, company_id: companyId ?? null },
    }),

  // Jarvis is a multi-company OS — companies is a collection, not a
  // singleton. Every call below is scoped by companyId so isolated data
  // per company holds regardless of how many companies exist.
  listCompanies: () => apiRequest<Company[]>("/companies"),
  createCompany: (payload: { name: string; tagline?: string; industry?: string }) =>
    apiRequest<Company>("/companies", { method: "POST", body: payload }),
  getCompany: (companyId: string) => apiRequest<Company>(`/companies/${companyId}`),
  updateCompany: (
    companyId: string,
    payload: {
      name?: string;
      tagline?: string;
      industry?: string;
      website?: string;
      divisions?: string[];
      sections?: Record<string, CompanySection>;
      owners?: CompanyOwner[];
      checklists?: Record<string, ChecklistItem[]>;
    }
  ) => apiRequest<Company>(`/companies/${companyId}`, { method: "PUT", body: payload }),
  listProducts: (companyId: string) => apiRequest<Product[]>(`/companies/${companyId}/products`),
  createProduct: (companyId: string, name: string) =>
    apiRequest<Product>(`/companies/${companyId}/products`, { method: "POST", body: { name } }),
  updateProduct: (companyId: string, productId: string, payload: Partial<Product>) =>
    apiRequest<Product>(`/companies/${companyId}/products/${productId}`, {
      method: "PUT",
      body: payload,
    }),

  // Project Manager kanban board — standalone, company-scoped tasks (not
  // nested under a Project; see backend/app/api/v1/endpoints/tasks.py).
  listCompanyTasks: (companyId: string) => apiRequest<CompanyTask[]>(`/companies/${companyId}/tasks`),
  createCompanyTask: (
    companyId: string,
    payload: { title: string; description?: string; status?: string; division?: string; assignee?: string; due_date?: string }
  ) => apiRequest<CompanyTask>(`/companies/${companyId}/tasks`, { method: "POST", body: payload }),
  updateCompanyTask: (taskId: string, payload: Partial<Omit<CompanyTask, "id" | "company_id">>) =>
    apiRequest<CompanyTask>(`/tasks/${taskId}`, { method: "PATCH", body: payload }),
  deleteCompanyTask: (taskId: string) => apiRequest<void>(`/tasks/${taskId}`, { method: "DELETE" }),

  // Investment Dashboard — live prices/news, both "configured: false" when
  // FINNHUB_API_KEY isn't set (see backend/app/core/market_data_service.py).
  getMarketQuotes: (symbols: string[]) =>
    apiRequest<{ configured: boolean; quotes: MarketQuote[] }>(
      `/market/quotes?symbols=${encodeURIComponent(symbols.join(","))}`
    ),
  getMarketNews: (symbols: string[], limitPerSymbol = 3) =>
    apiRequest<{ configured: boolean; headlines: MarketHeadline[] }>(
      `/market/news?symbols=${encodeURIComponent(symbols.join(","))}&limit_per_symbol=${limitPerSymbol}`
    ),

  // Shopify read-only connection status (no secrets). Optional companyId
  // reports whether the active workspace is the one bound to the store.
  getShopifyStatus: (companyId?: string) =>
    apiRequest<ShopifyStatus>(`/shopify/status${companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""}`),

  // Brand Brain — the workspace's structured source of truth (read from Jarvis's
  // own DB; sync imports from Shopify read-only).
  getBrandBrain: (companyId: string) =>
    apiRequest<BrandBrainSummary>(`/brand-brain?company_id=${encodeURIComponent(companyId)}`),
  listBrandProducts: (companyId: string, limit = 100) =>
    apiRequest<BrandProduct[]>(`/brand-brain/products?company_id=${encodeURIComponent(companyId)}&limit=${limit}`),
  listBrandCollections: (companyId: string) =>
    apiRequest<BrandCollection[]>(`/brand-brain/collections?company_id=${encodeURIComponent(companyId)}`),
  syncBrandBrain: (companyId: string) =>
    apiRequest<BrandBrainSyncResult>(`/brand-brain/sync?company_id=${encodeURIComponent(companyId)}`, { method: "POST" }),

  // Autonomous Work Queue — plan a request into subtasks, then stream execution.
  createWorkPlan: (request: string, companyId?: string | null) =>
    apiRequest<WorkRun>("/work-queue", { method: "POST", body: { request, company_id: companyId ?? null } }),
  getWorkRun: (id: string) => apiRequest<WorkRun>(`/work-queue/${id}`),
  listWorkRuns: (companyId?: string) =>
    apiRequest<WorkRun[]>(`/work-queue${companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""}`),

  // Workspace Intelligence — the AI's reading of a workspace + its evidence.
  getWorkspaceIntelligence: (companyId: string, refresh = false) =>
    apiRequest<WorkspaceIntelligence>(
      `/workspace-intelligence?company_id=${encodeURIComponent(companyId)}${refresh ? "&refresh=true" : ""}`
    ),

  // AI Command Center — decide which subsystem should handle a request, so
  // "Ask Jarvis" routes itself instead of making the user pick a tool.
  routeCommand: (request: string, companyId?: string | null, history?: { role: string; content: string }[]) =>
    apiRequest<CommandDecision>("/command-center/route", {
      method: "POST",
      body: { request, company_id: companyId ?? null, history: history ?? null },
    }),

  // Quick-Action workspaces — persistent, streaming "studio" sessions.
  listWorkspaceActions: () => apiRequest<WorkspaceConfig[]>("/workspaces/actions"),
  listWorkspaces: (
    params: { companyId?: string | "none"; action?: string; status?: string } = {}
  ) => {
    const qs = new URLSearchParams();
    if (params.companyId) qs.set("company_id", params.companyId);
    if (params.action) qs.set("action", params.action);
    if (params.status) qs.set("status", params.status);
    const q = qs.toString();
    return apiRequest<WorkspaceSummary[]>(`/workspaces${q ? `?${q}` : ""}`);
  },
  recentWorkspaces: (params: { companyId?: string | "none"; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.companyId) qs.set("company_id", params.companyId);
    if (params.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiRequest<WorkspaceSummary[]>(`/workspaces/recent${q ? `?${q}` : ""}`);
  },
  createWorkspace: (payload: {
    action: string;
    company_id?: string | null;
    project_id?: string | null;
    title?: string;
    mode?: "new" | "improve" | "client";
    source_url?: string | null;
    client_id?: string | null;
  }) => apiRequest<WorkspaceDetail>("/workspaces", { method: "POST", body: payload }),
  // Clients — the "Build Client Website" mode's entity (company-scoped).
  listClients: (companyId?: string | "none") =>
    apiRequest<Client[]>(`/clients${companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""}`),
  createClient: (payload: { name: string; company_id?: string | null; website?: string; notes?: string }) =>
    apiRequest<Client>("/clients", { method: "POST", body: payload }),
  getWorkspace: (id: string) => apiRequest<WorkspaceDetail>(`/workspaces/${id}`),
  updateWorkspace: (id: string, payload: { title?: string; status?: string }) =>
    apiRequest<WorkspaceDetail>(`/workspaces/${id}`, { method: "PATCH", body: payload }),
  deleteWorkspace: (id: string) => apiRequest<void>(`/workspaces/${id}`, { method: "DELETE" }),
  saveWorkspaceArtifact: (
    id: string,
    payload: { title: string; content: string; kind?: string; stage?: string }
  ) => apiRequest<WorkspaceArtifact>(`/workspaces/${id}/artifacts`, { method: "POST", body: payload }),
  attachWorkspaceProject: (id: string, projectId: string) =>
    apiRequest<WorkspaceDetail>(`/workspaces/${id}/attach-project`, {
      method: "POST",
      body: { project_id: projectId },
    }),
  addWorkspaceTask: (id: string, payload: { title: string; status?: string }) =>
    apiRequest<WorkspaceTask>(`/workspaces/${id}/tasks`, { method: "POST", body: payload }),
  workspaceImageStatus: () =>
    apiRequest<{ configured: boolean; provider: string | null }>("/workspaces/image/status"),
  generateWorkspaceImage: (
    id: string,
    payload: { prompt: string; concept_id?: string | null; name?: string; size?: string }
  ) =>
    apiRequest<{ configured: boolean; message?: string; image?: WorkspaceArtifact & { concept_id?: string | null } }>(
      `/workspaces/${id}/image`,
      { method: "POST", body: payload }
    ),
  workspaceSearchStatus: () =>
    apiRequest<{ configured: boolean; message?: string }>("/workspaces/search/status"),

  // Per-user plugin settings (enable/disable, config blob) — backend at
  // /api/v1/settings/plugins.
  listPluginSettings: () => apiRequest<PluginSettingRead[]>("/settings/plugins"),
  updatePluginSettings: (pluginName: string, payload: { enabled?: boolean; config?: Record<string, unknown> }) =>
    apiRequest<PluginSettingRead>(`/settings/plugins/${pluginName}`, { method: "PUT", body: payload }),

  // Jarvis's long-term memory — searchable across every company (isolated)
  // plus a global/personal layer. `companyId`: omit or "any" for
  // everything, "global" for personal-only, or a real company id.
  listMemoryKinds: () => apiRequest<MemoryKind[]>("/memory/kinds"),
  listMemoryScopes: () => apiRequest<MemoryScope[]>("/memory/scopes"),
  searchMemory: (params: {
    q?: string;
    companyId?: string | "any" | "global";
    projectId?: string;
    kind?: MemoryKind;
    scope?: MemoryScope;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    qs.set("company_id", params.companyId ?? "any");
    if (params.projectId) qs.set("project_id", params.projectId);
    if (params.kind) qs.set("kind", params.kind);
    if (params.scope) qs.set("scope", params.scope);
    if (params.limit) qs.set("limit", String(params.limit));
    return apiRequest<MemoryEntry[]>(`/memory?${qs.toString()}`);
  },
  getMemoryEntry: (id: string) => apiRequest<MemoryEntryDetail>(`/memory/${id}`),
  createMemory: (payload: {
    kind: MemoryKind;
    title: string;
    content: string;
    scope?: MemoryScope;
    company_id?: string | null;
    project_id?: string | null;
    confidence?: number | null;
    source?: string;
    source_ref?: string | null;
  }) => apiRequest<MemoryEntry>("/memory", { method: "POST", body: payload }),
  updateMemory: (
    id: string,
    payload: {
      title?: string;
      content?: string;
      kind?: MemoryKind;
      source_ref?: string | null;
      confidence?: number | null;
    }
  ) => apiRequest<MemoryEntry>(`/memory/${id}`, { method: "PUT", body: payload }),
  moveMemoryScope: (
    id: string,
    payload: { scope: MemoryScope; company_id?: string | null; project_id?: string | null; note?: string }
  ) => apiRequest<MemoryEntry>(`/memory/${id}/move`, { method: "POST", body: payload }),
  getMemoryAudit: (id: string) => apiRequest<MemoryAuditEntry[]>(`/memory/${id}/audit`),
  deleteMemory: (id: string) => apiRequest<void>(`/memory/${id}`, { method: "DELETE" }),

  // Capability framework (Phase 3) — the shared approval/audit/permission/
  // health-check layer every external-service integration plugs into.
  // `companyId`: omit for the account-wide default, or a real company id.
  listCapabilities: (companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<CapabilityView[]>(`/capabilities${qs}`);
  },
  getCapability: (name: string, companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<CapabilityView>(`/capabilities/${name}${qs}`);
  },
  updateCapabilityConfig: (
    name: string,
    payload: { enabled?: boolean; permissions?: string[]; company_id?: string | null }
  ) => apiRequest<CapabilityView>(`/capabilities/${name}/config`, { method: "PUT", body: payload }),
  runCapabilityHealthCheck: (name: string, companyId?: string) => {
    const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
    return apiRequest<CapabilityView>(`/capabilities/${name}/health-check${qs}`, { method: "POST" });
  },
  getCapabilityAuditLog: (params: { capabilityName?: string; companyId?: string | "any"; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.capabilityName) qs.set("capability_name", params.capabilityName);
    qs.set("company_id", params.companyId ?? "any");
    if (params.limit) qs.set("limit", String(params.limit));
    return apiRequest<CapabilityAuditEntry[]>(`/capabilities/audit-log?${qs.toString()}`);
  },

  // Approvals — the human-in-the-loop queue every capability's
  // side-effecting actions go through before anything external happens.
  listApprovals: (
    params: { companyId?: string | "any"; projectId?: string; status?: ApprovalStatus } = {}
  ) => {
    const qs = new URLSearchParams();
    qs.set("company_id", params.companyId ?? "any");
    if (params.projectId) qs.set("project_id", params.projectId);
    if (params.status) qs.set("status", params.status);
    return apiRequest<ApprovalRequestView[]>(`/approvals?${qs.toString()}`);
  },
  approveRequest: (id: string, note?: string) =>
    apiRequest<ApprovalRequestView>(`/approvals/${id}/approve`, { method: "POST", body: { note } }),
  rejectRequest: (id: string, note?: string) =>
    apiRequest<ApprovalRequestView>(`/approvals/${id}/reject`, { method: "POST", body: { note } }),

  // Scheduled jobs — the data model for background agents.
  listScheduledJobs: (companyId: string | "any" = "any") =>
    apiRequest<ScheduledJobView[]>(`/scheduled-jobs?company_id=${encodeURIComponent(companyId)}`),
  createScheduledJob: (payload: {
    capability_name: string;
    action_type: string;
    schedule_cron: string;
    payload?: Record<string, unknown>;
    company_id?: string | null;
  }) => apiRequest<ScheduledJobView>("/scheduled-jobs", { method: "POST", body: payload }),
  setScheduledJobEnabled: (id: string, enabled: boolean) =>
    apiRequest<ScheduledJobView>(`/scheduled-jobs/${id}`, { method: "PUT", body: { enabled } }),
  deleteScheduledJob: (id: string) => apiRequest<void>(`/scheduled-jobs/${id}`, { method: "DELETE" }),

  // AI Agents — the Active Agents dock panel. Read the roster + runs and launch
  // a run for the active company (all existing backend endpoints; no changes).
  listAgents: () => apiRequest<Agent[]>("/agents"),
  listAgentRuns: (params: { companyId?: string | "none"; agent?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.companyId) qs.set("company_id", params.companyId);
    if (params.agent) qs.set("agent", params.agent);
    const q = qs.toString();
    return apiRequest<AgentRun[]>(`/agents/runs${q ? `?${q}` : ""}`);
  },
  getAgentRun: (id: string) => apiRequest<AgentRunDetail>(`/agents/runs/${id}`),
  runAgent: (agentKey: string, payload: { objective: string; company_id?: string | null }) =>
    apiRequest<AgentRun>(`/agents/${agentKey}/run`, { method: "POST", body: payload }),
};

export interface WorkspaceStreamHandlers {
  onToken: (text: string) => void;
  onDone: (payload: { task_id?: string; text: string }) => void;
  onError: (message: string) => void;
}

/**
 * Streams a workspace message response via Server-Sent Events. Uses a raw
 * fetch (not apiRequest) so the response body can be read incrementally;
 * attaches the same Bearer token. Returns an abort function the caller can
 * use to cancel an in-flight stream (e.g. on unmount).
 */
// The raw SSE fetches below bypass apiRequest's 401→refresh path, so a stream
// opened after the 60-min access token expired would fail. This POSTs the
// stream request and, on a 401, transparently refreshes the token once and
// retries — keeping long demo sessions (e.g. a website build an hour in) stable.
async function openStream(url: string, body: unknown, signal: AbortSignal): Promise<Response> {
  const attempt = (tok: string | null) =>
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(tok ? { Authorization: `Bearer ${tok}` } : {}) },
      body: JSON.stringify(body),
      signal,
    });
  let resp = await attempt(getToken());
  if (resp.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) resp = await attempt(getToken());
    else clearSession();
  }
  return resp;
}

export function streamWorkspaceMessage(
  sessionId: string,
  content: string,
  handlers: WorkspaceStreamHandlers,
  stage?: string
): () => void {
  const controller = new AbortController();
  (async () => {
    try {
      const resp = await openStream(
        `${API_BASE}/workspaces/${sessionId}/message`,
        { content, stage: stage ?? null },
        controller.signal
      );
      if (!resp.ok || !resp.body) {
        handlers.onError(`Request failed (${resp.status}).`);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE frames are separated by a blank line.
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const event = JSON.parse(line.slice(5).trim());
            if (event.type === "token") handlers.onToken(event.text);
            else if (event.type === "done") handlers.onDone({ task_id: event.task_id, text: event.text });
            else if (event.type === "error") handlers.onError(event.message);
          } catch {
            // ignore malformed frame
          }
        }
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        handlers.onError(err instanceof Error ? err.message : "Stream failed.");
      }
    }
  })();
  return () => controller.abort();
}

// --- Build a Website pipeline (SSE) ---------------------------------------

export interface WebsiteBuildStage {
  stage: string;
  label: string;
  status: "running" | "done" | "error";
  detail?: string;
}

export interface WebsiteBuildHandlers {
  onStage: (s: WebsiteBuildStage) => void;
  onAwaitingApproval: (p: { summary: string; major_actions: string[] }) => void;
  onDone: (p: { phase: string; pages?: number; files?: number; images?: number }) => void;
  onError: (message: string) => void;
}

/**
 * Runs the Build a Website pipeline and streams live progress. With
 * `approved:false` it plans the site and stops at the approval gate; with
 * `approved:true` it runs the major action (images + React components +
 * preview). Returns an abort function.
 */
export function streamWebsiteBuild(
  sessionId: string,
  opts: { approved: boolean; brief?: string | null },
  handlers: WebsiteBuildHandlers
): () => void {
  const controller = new AbortController();
  (async () => {
    try {
      const resp = await openStream(
        `${API_BASE}/workspaces/${sessionId}/website/build`,
        { approved: opts.approved, brief: opts.brief ?? null },
        controller.signal
      );
      if (!resp.ok || !resp.body) {
        handlers.onError(`Build request failed (${resp.status}).`);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const event = JSON.parse(line.slice(5).trim());
            if (event.type === "stage") handlers.onStage(event as WebsiteBuildStage);
            else if (event.type === "awaiting_approval") handlers.onAwaitingApproval(event);
            else if (event.type === "done") handlers.onDone(event);
            else if (event.type === "error") handlers.onError(event.message);
          } catch {
            // ignore malformed frame
          }
        }
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        handlers.onError(err instanceof Error ? err.message : "Build stream failed.");
      }
    }
  })();
  return () => controller.abort();
}

export interface WorkEvent {
  type: "run" | "subtask" | "done" | "error";
  id?: string;
  title?: string;
  status?: string;
  result?: string | null;
  approval_id?: string | null;
  message?: string;
}

/**
 * Streams the Autonomous Work Queue as it works through a run's subtasks —
 * one event per state change (working / waiting_approval / complete) and a
 * final done. Returns an abort function.
 */
export function streamWork(
  runId: string,
  handlers: { onEvent: (e: WorkEvent) => void; onDone: () => void; onError: (msg: string) => void }
): () => void {
  const controller = new AbortController();
  (async () => {
    try {
      const resp = await openStream(`${API_BASE}/work-queue/${runId}/stream`, {}, controller.signal);
      if (!resp.ok || !resp.body) {
        handlers.onError(`Work run failed (${resp.status}).`);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const event = JSON.parse(line.slice(5).trim()) as WorkEvent;
            handlers.onEvent(event);
            if (event.type === "done") handlers.onDone();
          } catch {
            /* ignore malformed frame */
          }
        }
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        handlers.onError(err instanceof Error ? err.message : "Work stream failed.");
      }
    }
  })();
  return () => controller.abort();
}
