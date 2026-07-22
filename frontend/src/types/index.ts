export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
}

export interface ToolCallLog {
  name: string;
  input: Record<string, unknown>;
  output: string;
  is_error: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
  // Present on assistant messages that involved Jarvis actually running a
  // plugin or editing real data mid-conversation, so the UI can show what
  // happened rather than just the final text.
  toolCalls?: ToolCallLog[];
}

export type TaskStatus = "todo" | "in_progress" | "done" | "failed";

export interface TaskItem {
  id: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  plugin_name?: string | null;
  updatedAt?: string;
}

export interface MetricPoint {
  label: string;
  value: number;
}

export interface CalendarEvent {
  id: string;
  title: string;
  time: string;
  type: "meeting" | "deadline" | "reminder";
}

export interface NotificationItem {
  id: string;
  title: string;
  description: string;
  time: string;
  severity: "info" | "success" | "warning" | "critical";
  read: boolean;
}

export type MemoryKind =
  | "conversation"
  | "email"
  | "meeting"
  | "quote"
  | "sop"
  | "decision"
  | "contact"
  | "product"
  | "goal"
  | "task"
  | "file"
  | "fact"
  | "other";

// Broadest to narrowest. global/organization/personal are never tied to a
// company or project; company requires company_id; project requires
// project_id. See backend/app/core/memory_scope.py for the full
// classification rules (including when Jarvis should ask instead of
// guessing) and consistency constraints.
export type MemoryScope = "global" | "organization" | "company" | "project" | "personal";

// Jarvis's long-term brain — every conversation, quote, decision, contact,
// and business fact, searchable later. `company_id: null` means the scope
// isn't tied to one business (global/organization/personal). See
// backend/app/core/memory_service.py for the read/write/search contract
// every integration is meant to funnel through.
export interface MemoryEntry {
  id: string;
  scope: MemoryScope;
  company_id: string | null;
  project_id: string | null;
  kind: MemoryKind;
  title: string;
  content: string;
  source: string;
  source_ref: string | null;
  confidence: number | null;
  extra: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
  score?: number;
}

export type MemoryAuditAction = "created" | "updated" | "scope_changed" | "deleted";

export interface MemoryAuditEntry {
  id: string;
  action: MemoryAuditAction;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  note: string | null;
  created_at: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string | null;
  status: string;
  company_id: string | null;
  client_id: string | null;
  is_default: boolean;
}

// One Project Timeline entry (append-only activity log).
export interface ProjectEvent {
  id: string;
  kind: string;
  title: string;
  detail: string | null;
  source: string;
  ref_id: string | null;
  created_at: string | null;
}

// The nine buckets a Project contains, aggregated from everything attached to
// it (see backend app.core.project_service.build_project_overview).
export interface ProjectOverview {
  project: ProjectSummary & {
    description: string | null;
    created_at: string | null;
    updated_at: string | null;
  };
  counts: Record<
    | "conversations"
    | "files"
    | "images"
    | "components"
    | "research"
    | "tasks"
    | "approvals"
    | "timeline"
    | "memory",
    number
  >;
  conversations: {
    session_id: string;
    action: string;
    action_label: string;
    title: string;
    message_count: number;
    updated_at: string | null;
  }[];
  files: {
    session_id: string;
    action: string;
    path: string | null;
    language?: string | null;
    kind?: string | null;
    source: string;
  }[];
  images: {
    session_id: string;
    action: string;
    id: string | null;
    name: string | null;
    data_url: string | null;
    status: string | null;
  }[];
  components: {
    session_id: string;
    path: string | null;
    language: string | null;
    description: string | null;
  }[];
  research: {
    session_id: string;
    title: string;
    source_count: number;
    citation_count: number;
    has_report: boolean;
    report_excerpt: string | null;
  }[];
  tasks: { id: string; title: string; status: string; due_date: string | null }[];
  approvals: {
    id: string;
    capability_name: string;
    action_type: string;
    status: string;
    created_at: string | null;
  }[];
  memory: { id: string; kind: string; title: string; scope: string; created_at: string | null }[];
  timeline: ProjectEvent[];
}

export interface MemoryLinkView {
  relation: string;
  direction: "to" | "from";
  entry: MemoryEntry;
}

export interface MemoryEntryDetail extends MemoryEntry {
  links: MemoryLinkView[];
}

export interface PluginInfo {
  name: string;
  description: string;
  version: string;
}

export interface IntegrationStatus {
  name: string;
  description: string;
  connected: boolean;
}

// ---------------------------------------------------------------------
// Capability framework (Phase 3) — the shared approval/audit/permission/
// health-check/scheduling layer every external-service integration (Gmail,
// Calendar, Shopify, QuickBooks, Amazon, ...) plugs into. See
// backend/app/core/capabilities_registry.py and capability_service.py.
// ---------------------------------------------------------------------

export interface CapabilityActionInfo {
  name: string;
  description: string;
  requires_approval: boolean;
}

export type CapabilityHealthStatus = "unknown" | "ok" | "error" | "disconnected";

export interface CapabilityView {
  name: string;
  description: string;
  integration_name: string;
  actions: CapabilityActionInfo[];
  company_id: string | null;
  enabled: boolean;
  permissions: string[];
  config: Record<string, unknown> | null;
  health_status: CapabilityHealthStatus;
  health_message: string | null;
  last_health_check_at: string | null;
}

export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired" | "executed";

/** What a committed storefront change reports back. `verified: false` is not a
 *  failure — it means the action had no prior value to compare a read-back
 *  against (a create, a delete, a reorder), so existence was checked, not
 *  equality. The UI must not call that "verified". */
export interface ShopifyExecutionResult {
  committed?: boolean;
  changed?: boolean;
  verified?: boolean;
  action?: string;
  target?: string;
  product?: string | null;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
  note?: string;
  shopify_response?: unknown;
}

export interface ApprovalRequestView {
  id: string;
  capability_name: string;
  company_id: string | null;
  project_id: string | null;
  action_type: string;
  payload: Record<string, unknown> | null;
  // The decision brief (see backend app/core/approval_brief.py).
  summary: string;
  reason: string | null;
  expected_outcome: string;
  risks: string[];
  undo_plan: string;
  // Plan grouping — steps of one execution plan share a group_id.
  group_id: string | null;
  group_label: string | null;
  sequence: number;
  status: ApprovalStatus;
  requested_by: string | null;
  decided_by: string | null;
  decided_at: string | null;
  executed_at: string | null;
  note: string | null;
  /* The outcome, read from the shared queue rather than from the response to
   * whichever device pressed Approve — so the phone and the desktop render an
   * identical result, failure reason, and deciding device. */
  result: ShopifyExecutionResult | Record<string, unknown> | null;
  execution_error: string | null;
  decided_device: string | null;
  created_at: string | null;
}

// --- Approval Center -------------------------------------------------------
// Every real-world action Jarvis proposes carries a decision brief, so a human
// can judge it without reading raw JSON: what it is, why it was proposed, what
// will happen, what could go wrong, and whether it can be taken back.
export interface ApprovalPlan {
  group_id: string;
  label: string;
  company_id: string | null;
  steps: ApprovalRequestView[];
  pending_steps: number;
}
export interface ApprovalQueue {
  plans: ApprovalPlan[];
  standalone: ApprovalRequestView[];
  pending_count: number;
}
/** What a rejected step's plan did about it. */
export interface ReplanResult {
  run_id: string;
  replanned: boolean;
  new_steps: string[];
  run_status: string;
}
export interface ApprovalDecisionResult extends ApprovalRequestView {
  /** True once the action actually ran through its registered executor. */
  executed?: boolean;
  /** Set when the capability has no executor — consent recorded, nothing done. */
  execution_note?: string;
  /** Set when the executor ran and failed; the request stays 'approved'. */
  execution_error: string | null;
  replan?: ReplanResult | null;
}
export interface PlanDecisionResult {
  group_id: string;
  decided: number;
  /** The step a sequential run stopped at, if execution failed. */
  stopped_at: string | null;
  steps: ApprovalDecisionResult[];
  queue: ApprovalQueue;
}

export interface CapabilityAuditEntry {
  id: string;
  capability_name: string;
  company_id: string | null;
  approval_request_id: string | null;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  note: string | null;
  created_at: string | null;
}

// Real Google Calendar event, as returned by GET /api/v1/calendar/events —
// distinct from the mock `CalendarEvent` above (sample data used before
// Phase 3b connected a real Calendar).
export interface CalendarEventView {
  id: string;
  summary: string | null;
  description: string | null;
  location: string | null;
  start: string | null;
  end: string | null;
  all_day: boolean;
  attendees: string[];
  html_link: string | null;
  status: string | null;
}

// CEO Dashboard's AI-generated briefing — built from real signals (unread
// email, pending approvals, today's meetings, out-of-stock products,
// needs-rebuild sections) sent to POST /api/v1/dashboard/executive-summary.
// "AI Executives" — specialist personas the chat endpoint can answer as,
// all sharing the same memory/tools as the default CEO Assistant persona.
export interface Persona {
  key: string;
  label: string;
  description: string;
}

export interface ExecutiveSummary {
  summary: string;
  priorities: string[];
  alerts: string[];
  recommendations: string[];
}

export interface GmailMessage {
  id: string;
  thread_id: string | null;
  snippet: string | null;
  from: string | null;
  subject: string | null;
  date: string | null;
  unread: boolean;
  important: boolean;
  label_ids: string[];
}

export interface GmailMessageDetail {
  id: string;
  thread_id: string | null;
  snippet: string | null;
  from: string | null;
  to: string | null;
  subject: string | null;
  date: string | null;
  message_id_header: string | null;
  body: string;
  label_ids: string[];
}

export interface ScheduledJobView {
  id: string;
  capability_name: string;
  company_id: string | null;
  action_type: string;
  payload: Record<string, unknown>;
  schedule_cron: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface PluginSettingRead {
  plugin_name: string;
  enabled: boolean;
  config: Record<string, unknown>;
}

export interface CompanySection {
  status: string;
  notes: string;
  /** Structured knowledge extracted from the workspace's own connected files
   *  (see backend app/core/workspace_import_service.extract_brand). Present
   *  only for sections a deep extraction has run on. */
  data?: Record<string, unknown> | null;
}

export interface CompanyOwner {
  role_title: string;
  person_name: string | null;
  email: string | null;
}

export interface ChecklistItem {
  id: string;
  label: string;
  done: boolean;
  notes: string;
}

export interface Company {
  id: string;
  name: string;
  tagline: string | null;
  industry: string | null;
  website: string | null;
  // Structured workspace metadata (drives modules, AI behavior, branding).
  // company_type is the workspace kind (see lib/workspace.WorkspaceKind);
  // classifyWorkspace prefers it over the name/industry heuristic.
  company_type: string | null;
  parent_company_id: string | null;
  parent_company_name: string | null;
  divisions: string[];
  sections: Record<string, CompanySection>;
  owners: CompanyOwner[];
  checklists: Record<string, ChecklistItem[]>;
}

export interface Product {
  id: string;
  name: string;
  sku: string | null;
  manufacturer: string | null;
  packaging: string | null;
  cogs: number | null;
  moq: number | null;
  freight: number | null;
  price: number | null;
  margin: number | null;
  inventory: number | null;
  launch_status: string;
  notes: string | null;
}

// ---------------------------------------------------------------------
// Operating-system modules. Every module below is currently backed by
// mock data (see src/mock/*.ts) rather than a live API/table — that's
// intentional for this phase. Each type is shaped the way the real
// backend record will eventually look, so swapping the mock data hook
// for a real fetch later is a one-line change, not a redesign.
// ---------------------------------------------------------------------

export type ProjectStatus = "backlog" | "in_progress" | "review" | "done";

export interface ProjectBoardItem {
  id: string;
  title: string;
  description: string;
  status: ProjectStatus;
  division: string | null;
  dueDate: string | null;
  assignee: string | null;
}

// Real, company-scoped Project Manager kanban card — backend at
// /companies/{id}/tasks (app/api/v1/endpoints/tasks.py).
export interface CompanyTask {
  id: string;
  company_id: string | null;
  title: string;
  description: string | null;
  status: ProjectStatus;
  division: string | null;
  assignee: string | null;
  due_date: string | null;
}

export type CrmStage = "lead" | "contacted" | "proposal" | "won" | "lost";

export interface CrmContact {
  id: string;
  name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  stage: CrmStage;
  value: number | null;
  lastContact: string | null;
  notes: string;
}

export interface SopDocument {
  id: string;
  title: string;
  category: string;
  owner: string | null;
  lastUpdated: string;
  summary: string;
  steps: string[];
}

export type ManufacturingStage =
  | "sourcing"
  | "sampling"
  | "in_production"
  | "quality_check"
  | "shipping"
  | "complete";

export interface ProductionRun {
  id: string;
  productName: string;
  stage: ManufacturingStage;
  quantity: number;
  factory: string | null;
  eta: string | null;
  notes: string;
}

export interface InventoryItem {
  id: string;
  sku: string;
  name: string;
  warehouse: string | null;
  onHand: number;
  reserved: number;
  reorderPoint: number;
  unitCost: number | null;
}

export interface FinancialSummary {
  revenue: number;
  expenses: number;
  profit: number;
  cashOnHand: number;
  asOf: string;
}

export interface TransactionItem {
  id: string;
  date: string;
  description: string;
  category: string;
  amount: number;
  type: "income" | "expense";
}

export type MarketingAssetType = "ad_copy" | "email" | "social_post" | "image_brief";
export type MarketingAssetStatus = "draft" | "in_review" | "approved";

export interface MarketingAsset {
  id: string;
  type: MarketingAssetType;
  title: string;
  status: MarketingAssetStatus;
  channel: string | null;
  createdAt: string;
  preview: string;
}

export type ContentChannel = "instagram" | "tiktok" | "blog" | "email" | "youtube" | "other";
export type ContentStatus = "idea" | "drafting" | "scheduled" | "published";

export interface ContentCalendarItem {
  id: string;
  title: string;
  channel: ContentChannel;
  date: string;
  status: ContentStatus;
}

export type WebsitePageStatus = "planned" | "drafting" | "live";

export interface WebsitePage {
  id: string;
  name: string;
  path: string;
  status: WebsitePageStatus;
  lastEdited: string | null;
}

export type AmazonListingStatus =
  | "planning"
  | "listing_created"
  | "pending_review"
  | "live"
  | "suppressed";

export interface AmazonListing {
  id: string;
  title: string;
  asin: string | null;
  category: string | null;
  status: AmazonListingStatus;
  launchDate: string | null;
}

export type NewsCategory =
  | "stock_market"
  | "crypto"
  | "precious_metals"
  | "ai"
  | "semiconductors"
  | "creator";

export interface NewsFeedSource {
  id: string;
  label: string;
  category: NewsCategory;
  enabled: boolean;
}

export type NewsSentiment = "positive" | "neutral" | "negative";

export interface NewsHeadline {
  id: string;
  sourceId: string;
  headline: string;
  summary: string;
  time: string;
  sentiment: NewsSentiment;
}

export interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
}

// Real, live market data — backend at /api/v1/market/* (Finnhub-backed).
// `error` is set per-symbol when Finnhub couldn't resolve it (bad ticker,
// rate limit) rather than the whole batch failing.
export interface MarketQuote {
  symbol: string;
  lookup_symbol: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  error: string | null;
}

export interface MarketHeadline {
  id: string;
  symbol: string;
  headline: string;
  summary: string;
  url: string;
  source: string;
  datetime: number;
}

export interface WorkspaceMessage {
  role: "user" | "assistant";
  content: string;
}

export interface WorkspaceArtifact {
  id?: string;
  kind?: string; // document | code | image | ...
  title: string;
  content: string;
  stage?: string;
  version?: number;
  ts?: number;
}

export interface WorkspaceTask {
  id: string;
  title: string;
  status: string;
  due_date: string | null;
}

export interface WorkspaceStage {
  key: string;
  label: string;
  state_key: string;
  hint: string;
}

export interface WorkspaceConfig {
  key: string;
  label: string;
  supports_images: boolean;
  stages: WorkspaceStage[];
  state_keys: string[];
}

export interface Client {
  id: string;
  name: string;
  company_id: string | null;
  website: string | null;
  notes: string | null;
  project_count: number;
  created_at: string | null;
}

export interface WorkspaceSummary {
  id: string;
  action: string;
  action_label: string;
  company_id: string | null;
  client_id?: string | null;
  mode?: "new" | "improve" | "client" | null;
  source_url?: string | null;
  title: string;
  project_id: string | null;
  status: string;
  message_count: number;
  artifact_count?: number;
  updated_at: string | null;
  created_at: string | null;
}

// The structured, action-specific workspace state (sitemap, concepts,
// sources, launch checklist, ...). Shape varies by action; the panels read
// the keys they care about defensively.
export type WorkspaceState = Record<string, unknown>;

export interface WorkspaceDetail extends WorkspaceSummary {
  messages: WorkspaceMessage[];
  artifacts: WorkspaceArtifact[];
  tasks: WorkspaceTask[];
  state: WorkspaceState;
  config: WorkspaceConfig | null;
}

// Non-secret Shopify connection status — booleans + the public store domain
// only. The Admin API token never crosses to the frontend.
export interface ShopifyStatus {
  configured: boolean;
  store_domain: string | null;
  api_version: string | null;
  auth_method?: string | null;
  bound_workspace_id: string | null;
  active_workspace_is_bound: boolean;
  read_only: boolean;
  write_enabled?: boolean;
}

// Brand Brain — the workspace's structured source of truth (mirrored read-only
// from Shopify). See backend app/core/brand_brain_service.py.
export interface BrandBrainSummary {
  exists: boolean;
  source?: string;
  store_name?: string | null;
  store_domain?: string | null;
  currency?: string | null;
  plan_name?: string | null;
  store_metadata?: Record<string, unknown>;
  product_count?: number;
  collection_count?: number;
  last_synced_at?: string | null;
  read_only: boolean;
  write_enabled?: boolean;
}

export interface BrandProductVariant {
  id: string;
  title: string | null;
  sku: string | null;
  price: number | null;
  compareAtPrice: number | null;
  inventoryQuantity: number | null;
  availableForSale: boolean | null;
  options: { name: string; value: string }[];
  image: string | null;
}

export interface BrandProduct {
  id: string;
  shopify_id: string;
  title: string;
  handle: string | null;
  status: string | null;
  product_type: string | null;
  vendor: string | null;
  description: string | null;
  tags: string[];
  price_min: number | null;
  price_max: number | null;
  currency: string | null;
  total_inventory: number | null;
  featured_image: string | null;
  images: { url: string | null; altText: string | null }[];
  variants: BrandProductVariant[];
  seo: { title?: string; description?: string };
}

export interface BrandCollection {
  id: string;
  shopify_id: string;
  title: string;
  handle: string | null;
  description: string | null;
  products_count: number | null;
  image_url: string | null;
}

// Autonomous Work Queue (Phase 3) — a request decomposed into subtasks Jarvis
// works through, each tracked Planned → Working → Waiting for Approval → Complete.
export type WorkSubtaskStatus = "planned" | "working" | "waiting_approval" | "complete";
export interface WorkSubtask {
  id: string;
  title: string;
  real_world: boolean;
  status: WorkSubtaskStatus;
  result: string | null;
  approval_id: string | null;
}
export interface WorkRun {
  id: string;
  company_id: string | null;
  objective: string;
  status: string; // planned | running | waiting | completed
  result: string | null;
  subtasks: WorkSubtask[];
  created_at: string | null;
}

// AI Command Center (Phase 3) — the router's decision about which subsystem
// should handle a request. `mode` tells the UI HOW to act on it:
//   studio     → open the Quick Action workspace `target` (/studio/<target>)
//   chat       → answer/act inline through the normal chat pipeline
//   navigate   → go to the surface at `target`
//   work_queue → plan the request into subtasks and run them in sequence
export type CommandMode = "studio" | "chat" | "navigate" | "work_queue";
export interface CommandDecision {
  destination: string;
  label: string;
  mode: CommandMode;
  target: string | null;
  status: string; // live status label, e.g. "Researching…"
  explanation: string;
  clarifying_question: string | null;
}

// Workspace Intelligence (Phase 3) — the AI's reading of a workspace, plus the
// real signals it was built from (so the reading is auditable, not a black box).
export interface WorkspaceSignals {
  workspace: { name: string; type: string | null; industry: string | null; parent: string | null };
  projects: { total: number; active: number; names: string[] };
  tasks: { total: number; by_status: Record<string, number> };
  pending_approvals: { capability: string; action: string; details: string }[];
  recent_ai_work: { objective: string; status: string }[];
  memory: { count: number; recent: { title: string; kind: string }[] };
  brand_brain: { connected: boolean; products: number; collections: number; last_synced: string | null };
}
export interface WorkspaceRecommendation {
  title: string;
  why: string;
  real_world: boolean;
}
export interface WorkspaceIntelligence {
  company_id: string;
  workspace_name: string;
  headline: string;
  state_of_play: string;
  signals: { label: string; detail: string }[];
  risks: { title: string; detail: string }[];
  recommendations: WorkspaceRecommendation[];
  evidence: WorkspaceSignals;
  generated_at: number;
}

export interface BrandBrainSyncResult {
  synced_at: string;
  store_name: string | null;
  store_domain: string | null;
  product_count: number;
  collection_count: number;
  /** How many company-scoped AI-memory entries the sync mirrored (products + store profile). */
  memory_entries?: number;
  read_only: boolean;
  write_enabled: boolean;
}

export type IdeaStage = "idea" | "validating" | "building" | "launched" | "parked";

export interface BusinessIdea {
  id: string;
  title: string;
  description: string;
  stage: IdeaStage;
  division: string | null;
  score: number | null;
  notes: string;
}

// --- AI Agents (Active Agents dock panel; backend app/api/v1/endpoints/agents.py) ---

export interface Agent {
  key: string;
  label: string;
  role: string;
  tools: string[];
}

export type AgentRunStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed";

export interface AgentRun {
  id: string;
  agent_key: string;
  agent_label: string;
  company_id: string | null;
  objective: string;
  status: AgentRunStatus;
  project_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AgentRunDetail extends AgentRun {
  reasoning_log: { step?: string; type?: string; content?: string; [k: string]: unknown }[];
  result: string | null;
}
