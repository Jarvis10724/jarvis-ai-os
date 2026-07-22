import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Plus, Sparkles } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import clsx from "clsx";

import { useCompany } from "@/context/CompanyContext";
import { usePrompt } from "@/context/PromptContext";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";

export default function CompanySwitcher({ onNavigate }: { onNavigate?: () => void } = {}) {
  const { companies, activeCompany, activeCompanyId, setActiveCompanyId, createCompany, loading } =
    useCompany();
  const [open, setOpen] = useState(false);
  // Hidden when it would do nothing — a link to the page you're already on is
  // an inert control, and inside the mobile drawer it has to close the drawer
  // or the destination stays hidden behind it.
  const onCompanyProfile = useLocation().pathname === "/company";
  const prompt = usePrompt();
  const toast = useToast();

  async function handleNewCompany() {
    const values = await prompt({
      title: "New Company",
      fields: [{ key: "name", label: "Company name" }],
      confirmLabel: "Create",
    });
    if (values === null || !values.name.trim()) return;
    try {
      await createCompany(values.name.trim());
      setOpen(false);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Failed to create company.", "error");
    }
  }

  if (loading) {
    return <div className="skeleton mx-4 mt-4 h-11 rounded-xl" />;
  }

  if (!activeCompany) {
    return null;
  }

  return (
    <div className="relative mx-3 mt-3 shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2.5 text-left transition-all duration-200 hover:border-jarvis-cyan/40"
      >
        <Sparkles className="h-4 w-4 shrink-0 text-jarvis-cyan" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-jarvis-text">
          {activeCompany.name}
        </span>
        <ChevronDown
          className={clsx(
            "h-3.5 w-3.5 shrink-0 text-jarvis-muted transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              className="absolute left-0 right-0 z-40 mt-1.5 rounded-xl border border-jarvis-border bg-jarvis-panel/95 p-1.5 shadow-elevated-lg backdrop-blur-2xl"
            >
              {companies.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setActiveCompanyId(c.id);
                    setOpen(false);
                  }}
                  className={clsx(
                    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-150",
                    c.id === activeCompanyId
                      ? "bg-jarvis-cyan/10 text-jarvis-cyan"
                      : "text-jarvis-muted hover:bg-jarvis-panel2/60 hover:text-jarvis-text"
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  {c.id === activeCompanyId && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-jarvis-cyan shadow-glow-sm" />
                  )}
                </button>
              ))}
              <button
                onClick={handleNewCompany}
                className="mt-1 flex w-full items-center gap-2 rounded-lg border-t border-jarvis-border/60 px-3 py-2 pt-2.5 text-left text-sm text-jarvis-muted transition-colors duration-150 hover:text-jarvis-cyan"
              >
                <Plus className="h-3.5 w-3.5" />
                New Company
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {!onCompanyProfile && (
        <NavLink
          to="/company"
          onClick={onNavigate}
          className="mt-1 flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium text-jarvis-muted transition-colors duration-150 hover:text-jarvis-text"
        >
          View Company Profile →
        </NavLink>
      )}
    </div>
  );
}
