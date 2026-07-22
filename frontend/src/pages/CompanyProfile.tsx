import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Boxes,
  Check,
  CheckSquare,
  ClipboardCheck,
  FileText,
  Loader2,
  Megaphone,
  Package,
  Palette,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
  UserCircle2,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import ChecklistCard from "@/components/ChecklistCard";
import { useCompany } from "@/context/CompanyContext";
import LaunchDashboard from "@/components/LaunchDashboard";
import { useToast } from "@/context/ToastContext";
import type { ChecklistItem, Product } from "@/types";

const SECTION_TABS: { key: string; label: string; icon: typeof Palette }[] = [
  { key: "brand", label: "Brand", icon: Palette },
  { key: "products", label: "Products", icon: Package },
  { key: "manufacturing", label: "Manufacturing", icon: Boxes },
  { key: "packaging", label: "Packaging", icon: ShoppingBag },
  { key: "shopify", label: "Shopify", icon: Store },
  { key: "amazon", label: "Amazon", icon: ShoppingBag },
  { key: "quickbooks", label: "QuickBooks", icon: FileText },
  { key: "marketing", label: "Marketing", icon: Megaphone },
  { key: "compliance", label: "Compliance", icon: ShieldCheck },
  { key: "security", label: "Security", icon: ShieldCheck },
  { key: "tasks", label: "Tasks", icon: CheckSquare },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "approvals", label: "Approvals", icon: ClipboardCheck },
];

// Tabs that render something other than the generic status+notes editor.
const CUSTOM_TABS = new Set(["products", "security"]);

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  needs_rebuild: "Needs Rebuild",
  set_up_not_connected: "Set Up — Not Connected",
  done: "Done",
};

const STATUS_STYLES: Record<string, string> = {
  not_started: "border-jarvis-muted/40 bg-jarvis-muted/10 text-jarvis-muted",
  in_progress: "border-jarvis-amber/40 bg-jarvis-amber/10 text-jarvis-amber",
  needs_rebuild: "border-jarvis-rose/40 bg-jarvis-rose/10 text-jarvis-rose",
  set_up_not_connected: "border-jarvis-blue/40 bg-jarvis-blue/10 text-jarvis-blue",
  done: "border-jarvis-emerald/40 bg-jarvis-emerald/10 text-jarvis-emerald",
};

export default function CompanyProfile() {
  const { activeCompany, activeCompanyId, loading: companyListLoading, refresh } = useCompany();
  const [searchParams] = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(
    () => SECTION_TABS.find((t) => t.key === searchParams.get("tab"))?.key ?? "brand"
  );
  const [notesDraft, setNotesDraft] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [savedNotes, setSavedNotes] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!activeCompanyId) return;
    setLoadingProducts(true);
    api
      .listProducts(activeCompanyId)
      .then(setProducts)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load products.");
      })
      .finally(() => setLoadingProducts(false));
  }, [activeCompanyId]);

  useEffect(() => {
    if (activeCompany && !CUSTOM_TABS.has(activeTab)) {
      setNotesDraft(activeCompany.sections[activeTab]?.notes ?? "");
    }
  }, [activeCompany, activeTab]);

  async function saveNotes() {
    if (!activeCompany || !activeCompanyId || CUSTOM_TABS.has(activeTab)) return;
    setSavingNotes(true);
    try {
      await api.updateCompany(activeCompanyId, {
        sections: {
          [activeTab]: {
            status: activeCompany.sections[activeTab]?.status ?? "not_started",
            notes: notesDraft,
          },
        },
      });
      await refresh();
      setSavedNotes(true);
      setTimeout(() => setSavedNotes(false), 1500);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to save notes.", "error");
    } finally {
      setSavingNotes(false);
    }
  }

  async function setStatus(status: string) {
    if (!activeCompany || !activeCompanyId || CUSTOM_TABS.has(activeTab)) return;
    try {
      await api.updateCompany(activeCompanyId, {
        sections: { [activeTab]: { status, notes: notesDraft } },
      });
      await refresh();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to update status.", "error");
    }
  }

  async function saveChecklist(key: string, items: ChecklistItem[]) {
    if (!activeCompanyId) return;
    await api.updateCompany(activeCompanyId, { checklists: { [key]: items } });
    await refresh();
  }

  if (companyListLoading || (activeCompanyId && loadingProducts && !error)) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-jarvis-cyan" />
      </main>
    );
  }

  if (error || !activeCompany) {
    return (
      <main className="flex flex-1 items-center justify-center p-8">
        <p className="text-sm text-jarvis-rose">
          {error ?? "No company workspace found. Use “+ New Company” in the sidebar to create one."}
        </p>
      </main>
    );
  }

  const company = activeCompany;
  const section = company.sections[activeTab];

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="hud-panel hud-corner flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-center gap-4">
            <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 shadow-glow-sm">
              <div className="absolute inset-0 animate-pulseGlow rounded-full border border-jarvis-cyan/20" />
              <Sparkles className="h-7 w-7 text-jarvis-cyan" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display text-xl font-bold tracking-widest text-jarvis-text text-glow">
                  {company.name.toUpperCase()}
                </h1>
                <span className="rounded-full border border-jarvis-emerald/40 bg-jarvis-emerald/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-emerald">
                  Real Workspace
                </span>
              </div>
              <p className="text-sm text-jarvis-muted">
                {[company.tagline, company.industry].filter(Boolean).join(" — ")}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            {company.owners.map((owner) => (
              <div
                key={owner.role_title}
                className="flex items-center gap-2 rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 px-3 py-2 transition-colors duration-200 hover:border-jarvis-border-soft"
              >
                <UserCircle2 className="h-4 w-4 text-jarvis-cyan" />
                <div>
                  <p className="text-xs font-semibold text-jarvis-text">{owner.role_title}</p>
                  <p className="text-[10px] text-jarvis-muted">
                    {owner.person_name ?? "Name not yet added"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Stacks on a phone — a fixed side rail leaves the panel too narrow to
            operate at 375px — and returns to a side rail from md up. */}
        <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row">
          {/* Tabs */}
          <nav className="hud-panel flex shrink-0 gap-0.5 overflow-x-auto p-2 md:w-56 md:flex-col md:overflow-y-auto md:p-3">
            {SECTION_TABS.map(({ key, label, icon: Icon }, i) => {
              const tabStatus = !CUSTOM_TABS.has(key) ? company.sections[key]?.status : null;
              const isActive = activeTab === key;
              return (
                <motion.button
                  key={key}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.02 * i, duration: 0.25 }}
                  onClick={() => setActiveTab(key)}
                  className={clsx(
                    "group relative flex items-center gap-2.5 rounded-lg px-3.5 py-2.5 text-left text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                      : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  )}
                >
                  <span
                    className={clsx(
                      "absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-jarvis-cyan transition-opacity duration-200",
                      isActive ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1 truncate">{label}</span>
                  {tabStatus && (
                    <span
                      className={clsx(
                        "h-1.5 w-1.5 shrink-0 rounded-full",
                        tabStatus === "done" || tabStatus === "in_progress"
                          ? "bg-jarvis-emerald"
                          : tabStatus === "needs_rebuild"
                            ? "bg-jarvis-rose"
                            : "bg-jarvis-muted"
                      )}
                    />
                  )}
                </motion.button>
              );
            })}
          </nav>

          {/* Content */}
          <div className="hud-panel hud-corner p-3 md:min-h-0 md:flex-1 md:overflow-hidden sm:p-6">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="h-full"
              >
                {activeTab === "products" && (
                  <LaunchDashboard companyId={company.id} products={products} onChange={setProducts} />
                )}

                {activeTab === "security" && (
                  <div className="flex h-full flex-col gap-4 overflow-y-auto">
                    <div>
                      <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                        SECURITY
                      </h2>
                      <p className="text-xs text-jarvis-muted">
                        Review access before connecting any real integration. Nothing here connects,
                        changes, or revokes anything automatically — it's a tracking checklist for the
                        owners to work through themselves.
                      </p>
                    </div>
                    <ChecklistCard
                      title="Security Review"
                      items={company.checklists.security_review ?? []}
                      onSave={(items) => saveChecklist("security_review", items)}
                    />
                  </div>
                )}

                {!CUSTOM_TABS.has(activeTab) && (
                  <div
                    className={clsx(
                      "flex h-full flex-col gap-4",
                      activeTab === "shopify" && "overflow-y-auto"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
                        {SECTION_TABS.find((t) => t.key === activeTab)?.label.toUpperCase()}
                      </h2>
                      <select
                        value={section?.status ?? "not_started"}
                        onChange={(e) => setStatus(e.target.value)}
                        className={clsx(
                          "rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition-colors duration-200 focus:outline-none",
                          STATUS_STYLES[section?.status ?? "not_started"]
                        )}
                      >
                        {Object.entries(STATUS_LABELS).map(([value, label]) => (
                          <option key={value} value={value} className="bg-jarvis-panel text-jarvis-text">
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <textarea
                      value={notesDraft}
                      onChange={(e) => setNotesDraft(e.target.value)}
                      onBlur={saveNotes}
                      rows={activeTab === "shopify" ? 5 : 10}
                      placeholder="Notes, links, and details for this area..."
                      className={clsx(
                        "resize-none rounded-xl border border-jarvis-border bg-jarvis-panel2/50 p-4 text-sm leading-relaxed text-jarvis-text placeholder:text-jarvis-faint transition-colors duration-200 focus:border-jarvis-cyan/50 focus:outline-none",
                        activeTab !== "shopify" && "flex-1"
                      )}
                    />

                    <div className="flex h-5 items-center gap-1.5 text-xs text-jarvis-muted">
                      {savingNotes && (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving...
                        </>
                      )}
                      {savedNotes && !savingNotes && (
                        <>
                          <Check className="h-3.5 w-3.5 text-jarvis-emerald" /> Saved
                        </>
                      )}
                    </div>

                    {activeTab === "shopify" && (
                      <ChecklistCard
                        title="Shopify Recovery & Rebuild Checklist"
                        description="Work through this before reconnecting the store to Jarvis."
                        items={company.checklists.shopify_recovery ?? []}
                        onSave={(items) => saveChecklist("shopify_recovery", items)}
                      />
                    )}
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
    </main>
  );
}
