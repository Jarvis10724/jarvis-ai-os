import { useEffect, useState } from "react";

import { api } from "@/api/client";
import type { JarvisCoreState } from "@/components/JarvisCore";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";

/**
 * The single source of truth for what the global AI Core is doing right now.
 *
 * It composes two live signals into one Core state:
 *   1. The *explicit* assistant status (AssistantStatusContext) — whatever the
 *      active surface is driving: listening / thinking / researching /
 *      generating / speaking. When Jarvis is actively working, that always wins.
 *   2. When nothing is actively running (status is idle), the Core surfaces the
 *      workspace's *ambient* state: if the active company has pending approvals,
 *      the Core sits in "waiting" (waiting-for-approval) so the centerpiece
 *      itself signals that something needs the user, not just the bell badge.
 *
 * Pending approvals are refetched on workspace switch and whenever Jarvis
 * settles back to idle (a just-finished task may have created one). This is the
 * same cheap /approvals?status=pending call TopNav already makes.
 */
export function useCoreState(): JarvisCoreState {
  const { status } = useAssistantStatus();
  const { activeCompanyId } = useCompany();
  const [pendingApprovals, setPendingApprovals] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .listApprovals({ companyId: activeCompanyId ?? "any", status: "pending" })
      .then((list) => !cancelled && setPendingApprovals(list.length))
      .catch(() => !cancelled && setPendingApprovals(0));
    return () => {
      cancelled = true;
    };
    // Refetch on workspace change and whenever Jarvis returns to idle, since a
    // finished run may have just produced (or cleared) an approval.
  }, [activeCompanyId, status === "idle"]);

  // Active work always takes precedence over the ambient waiting state.
  if (status !== "idle") return status;
  if (pendingApprovals > 0) return "waiting";
  return "idle";
}
