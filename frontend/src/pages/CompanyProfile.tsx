import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Boxes,
  Check,
  ChevronLeft,
  ChevronRight,
  CheckSquare,
  ClipboardCheck,
  FileText,
  Loader2,
  Megaphone,
  Menu,
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
  // The section rail is a sidebar on desktop and a menu on a phone. On a
  // phone it starts collapsed and re-collapses after a section is picked, so
  // the content panel gets the full screen width instead of sharing it with a
  // list you've finished using. On desktop it stays open unless collapsed
  // deliberately.
  const [navOpen, setNavOpen] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia("(min-width: 768px)").matches
  );
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia("(min-width: 768px)").matches
  );
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const sync = (e: MediaQueryList | MediaQueryListEvent) => {
      setIsDesktop(e.matches);
      setNavOpen(e.matches); // desktop opens the rail; a phone hands the width back
    };
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const activeSection = SECTION_TABS.find((t) => t.key === activeTab);
  const activeLabel = activeSection?.label ?? "Sections";
  const ActiveIcon = activeSection?.icon;

  /** Picking a section never loses it — only the menu closes, and only on a phone. */
  function selectTab(key: string) {
    setActiveTab(key);
    if (!isDesktop) setNavOpen(false);
  }

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

  // One scroll container for the whole workspace page: this <main>. Nothing
  // inside it may cap its own height on a phone, or the page stops scrolling
  // before the content ends. The extra bottom padding clears Safari's bottom
  // bar and the home indicator so the last card is fully readable.
  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 pb-[max(6rem,calc(env(safe-area-inset-bottom)+5rem))] md:pb-4">
      {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="hud-panel hud-corner flex shrink-0 flex-col gap-4 p-6 md:shrink sm:flex-row sm:items-center sm:justify-between"
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
        <div className="flex shrink-0 flex-col gap-4 md:min-h-0 md:flex-1 md:shrink md:flex-row">
          {/* Phone: the collapsed rail is a single bar naming the section
              you're in. One tap reopens the full list; the section and the
              panel underneath are untouched, so nothing is lost by closing it. */}
          {!navOpen && (
            <button
              onClick={() => setNavOpen(true)}
              aria-expanded={false}
              aria-label={`Workspace sections — currently ${activeLabel}`}
              className="hud-panel press-scale flex shrink-0 items-center gap-2 px-3 py-2.5 text-left md:hidden"
            >
              <Menu className="h-4 w-4 shrink-0 text-jarvis-muted" />
              {ActiveIcon && <ActiveIcon className="h-4 w-4 shrink-0 text-jarvis-cyan" />}
              <span className="flex-1 truncate text-sm font-medium text-jarvis-cyan">{activeLabel}</span>
              <ChevronRight className="h-4 w-4 shrink-0 text-jarvis-faint" />
            </button>
          )}

          {/* Tabs */}
          <nav
            className={clsx(
              "hud-panel shrink-0 gap-0.5 md:flex md:flex-col md:overflow-y-auto md:p-3",
              navOpen ? "flex flex-col p-2" : "hidden",
              // Collapsed on desktop is a narrow icon rail, not a hidden menu —
              // the sections stay one tap away on a screen that has room.
              navOpen ? "md:w-56" : "md:w-14 md:items-center"
            )}
          >
            {/* Desktop-only collapse control: the rail never closes on its own
                here, only when it's deliberately collapsed. */}
            <button
              onClick={() => setNavOpen((v) => !v)}
              aria-label={navOpen ? "Collapse sections" : "Expand sections"}
              title={navOpen ? "Collapse sections" : "Expand sections"}
              className="press-scale mb-1 hidden items-center justify-center rounded-lg p-2 text-jarvis-faint transition-colors hover:bg-jarvis-panel2/60 hover:text-jarvis-text md:flex"
            >
              {navOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>

            {SECTION_TABS.map(({ key, label, icon: Icon }, i) => {
              const tabStatus = !CUSTOM_TABS.has(key) ? company.sections[key]?.status : null;
              const isActive = activeTab === key;
              return (
                <motion.button
                  key={key}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.02 * i, duration: 0.25 }}
                  onClick={() => selectTab(key)}
                  aria-label={label}
                  title={label}
                  className={clsx(
                    "group relative flex items-center gap-2.5 rounded-lg py-2.5 text-left text-sm font-medium transition-all duration-200",
                    navOpen ? "px-3.5" : "px-2.5 md:justify-center",
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
                  <span className={clsx("flex-1 truncate", !navOpen && "md:hidden")}>{label}</span>
                  {tabStatus && (
                    <span
                      className={clsx(
                        "h-1.5 w-1.5 shrink-0 rounded-full",
                        !navOpen && "md:absolute md:right-1.5 md:top-1.5",
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
          <div className="hud-panel hud-corner overflow-visible p-3 md:min-h-0 md:flex-1 md:overflow-hidden sm:p-6">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="md:h-full"
              >
                {activeTab === "products" && (
                  <LaunchDashboard companyId={company.id} products={products} onChange={setProducts} />
                )}

                {activeTab === "security" && (
                  <div className="flex flex-col gap-4 md:h-full md:overflow-y-auto">
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
                      "flex flex-col gap-4 md:h-full",
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
