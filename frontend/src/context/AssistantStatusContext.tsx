import { createContext, useContext, useState, type ReactNode } from "react";

import type { JarvisCoreState } from "@/components/JarvisCore";

interface AssistantStatusContextValue {
  status: JarvisCoreState;
  setStatus: (status: JarvisCoreState) => void;
}

const AssistantStatusContext = createContext<AssistantStatusContextValue | undefined>(undefined);

// Lets Jarvis's presence (the Sidebar orb) reflect real assistant state —
// listening/thinking/speaking — no matter which page is actually driving a
// conversation, instead of the Sidebar hardcoding "idle" forever. ChatPanel
// is the only writer today; any future voice-triggering surface can also
// call setStatus without the Sidebar needing to know about it.
export function AssistantStatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<JarvisCoreState>("idle");
  return (
    <AssistantStatusContext.Provider value={{ status, setStatus }}>
      {children}
    </AssistantStatusContext.Provider>
  );
}

export function useAssistantStatus() {
  const ctx = useContext(AssistantStatusContext);
  if (!ctx) throw new Error("useAssistantStatus must be used within an AssistantStatusProvider");
  return ctx;
}
