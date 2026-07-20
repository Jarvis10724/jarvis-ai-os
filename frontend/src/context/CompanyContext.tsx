import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ApiError } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import type { Company } from "@/types";

const ACTIVE_COMPANY_KEY = "jarvis_active_company_id";

interface CompanyContextValue {
  companies: Company[];
  activeCompany: Company | null;
  activeCompanyId: string | null;
  loading: boolean;
  error: string | null;
  setActiveCompanyId: (id: string) => void;
  createCompany: (name: string) => Promise<Company>;
  refresh: () => Promise<void>;
}

const CompanyContext = createContext<CompanyContextValue | undefined>(undefined);

// Jarvis is a multi-company operating system. This context is the single
// source of truth for "which company is active" — every company-scoped page
// reads from here instead of assuming there's only one. Adding a new
// company (createCompany) requires no changes anywhere else in the app.
export function CompanyProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeCompanyId, setActiveCompanyIdState] = useState<string | null>(
    () => localStorage.getItem(ACTIVE_COMPANY_KEY)
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function setActiveCompanyId(id: string) {
    setActiveCompanyIdState(id);
    localStorage.setItem(ACTIVE_COMPANY_KEY, id);
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listCompanies();
      setCompanies(list);
      setActiveCompanyIdState((current) => {
        const stillValid = current && list.some((c) => c.id === current);
        const next = stillValid ? current : (list[0]?.id ?? null);
        if (next) localStorage.setItem(ACTIVE_COMPANY_KEY, next);
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load companies.");
    } finally {
      setLoading(false);
    }
  }

  async function createCompany(name: string) {
    const company = await api.createCompany({ name });
    setCompanies((prev) => [...prev, company]);
    setActiveCompanyId(company.id);
    return company;
  }

  useEffect(() => {
    if (user) {
      refresh();
    } else {
      setCompanies([]);
      setActiveCompanyIdState(null);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const activeCompany = companies.find((c) => c.id === activeCompanyId) ?? null;

  return (
    <CompanyContext.Provider
      value={{
        companies,
        activeCompany,
        activeCompanyId,
        loading,
        error,
        setActiveCompanyId,
        createCompany,
        refresh,
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error("useCompany must be used within CompanyProvider");
  return ctx;
}
