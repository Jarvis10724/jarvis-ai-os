import { useMemo } from "react";

import { useCompany } from "@/context/CompanyContext";
import { resolveWorkspace, type ResolvedWorkspace } from "@/lib/workspace";

/**
 * The active workspace as a first-class object — identity (kind/role/monogram),
 * theme, capabilities, and typical integrations — derived from the active
 * company. Everything that should "feel like its own operating environment"
 * reads from here. Recomputed only when the active company changes.
 */
export function useWorkspace(): ResolvedWorkspace {
  const { activeCompany } = useCompany();
  return useMemo(() => resolveWorkspace(activeCompany), [activeCompany]);
}
