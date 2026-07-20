import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { useCompany } from "@/context/CompanyContext";
import type { Company } from "@/types";

/**
 * Shared wrapper for every company-scoped module (Project Manager, CRM,
 * Inventory, ...). Handles the loading/no-company states once so each
 * module only has to render its own content for the resolved company.
 */
export default function CompanyScopedPage({
  children,
}: {
  children: (company: Company) => ReactNode;
}) {
  const { activeCompany, loading } = useCompany();

  if (loading) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-jarvis-cyan" />
      </main>
    );
  }

  if (!activeCompany) {
    return (
      <main className="flex flex-1 items-center justify-center p-8 text-center">
        <p className="text-sm text-jarvis-rose">
          No company workspace found. Use the switcher in the sidebar to create one.
        </p>
      </main>
    );
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      {children(activeCompany)}
    </main>
  );
}
