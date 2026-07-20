import { useEffect, useRef } from "react";

/**
 * Registers a Cmd/Ctrl+<key> shortcut for the lifetime of the calling
 * component. Only meant to be called once, from a component that itself
 * only mounts once (DashboardShell) — calling it per-page would attach and
 * tear down a listener on every navigation for no benefit.
 *
 * Keeps the latest `handler` in a ref so the caller can pass a fresh inline
 * closure on every render without that re-attaching the listener (which
 * would happen if `handler` were a dependency of the effect below).
 */
export function useGlobalHotkey(key: string, handler: (e: KeyboardEvent) => void) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const isModifierPressed = e.metaKey || e.ctrlKey;
      if (isModifierPressed && e.key.toLowerCase() === key.toLowerCase()) {
        handlerRef.current(e);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [key]);
}
