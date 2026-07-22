import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { getAccessToken } from "@/api/client";

/**
 * ONE Jarvis.
 *
 * There is no desktop state and no phone state. Every client renders what the
 * backend holds; this provider's only job is to know, as soon as possible, that
 * the backend changed — so a page can re-read it without anyone pressing
 * refresh.
 *
 * The whole app shares ONE connection. Pages don't poll and don't own timers;
 * they call `useSyncedResource(kind, load)` and get re-run when their kind
 * changes. That's what makes synchronization a property of the architecture: a
 * feature added later inherits it by naming its kind, and cannot accidentally
 * ship as device-local.
 *
 * Three things this has to survive, none of which a naive stream handles:
 *
 *   1. A DEAD CONNECTION. Mobile Safari kills sockets when a tab backgrounds.
 *      Reconnect with backoff, and treat every reconnect as "I may have missed
 *      something" rather than assuming continuity.
 *   2. SLEEP. A closed lid or a backgrounded phone misses events entirely. On
 *      wake we compare version stamps with the server and re-sync what moved,
 *      instead of trusting that nothing happened while we were away.
 *   3. A RESTARTED BACKEND. Versions are per-process, so a client holding
 *      version 12 would look "ahead" of a fresh server at 0 and never re-fetch.
 *      A changed epoch means re-sync everything.
 */

type Versions = Record<string, number>;
type Listener = () => void;

interface SyncState {
  connected: boolean;
  /** Bumped whenever a kind changes, so listeners can re-read. */
  subscribe: (kind: string, fn: Listener) => () => void;
  /** Force every listener to re-read — used on reconnect and epoch change. */
  resyncAll: () => void;
}

const SyncContext = createContext<SyncState | null>(null);

/** How long to wait before reconnecting, growing to a ceiling so a backend
 *  that's down doesn't get hammered by every open tab. */
const BACKOFF_MS = [1000, 2000, 5000, 10000, 20000];

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const listeners = useRef<Map<string, Set<Listener>>>(new Map());
  const versions = useRef<Versions>({});
  const epoch = useRef<string | null>(null);
  const attempt = useRef(0);

  const notify = useCallback((kind: string) => {
    listeners.current.get(kind)?.forEach((fn) => fn());
  }, []);

  const resyncAll = useCallback(() => {
    listeners.current.forEach((set) => set.forEach((fn) => fn()));
  }, []);

  const subscribe = useCallback((kind: string, fn: Listener) => {
    const set = listeners.current.get(kind) ?? new Set<Listener>();
    set.add(fn);
    listeners.current.set(kind, set);
    return () => {
      set.delete(fn);
    };
  }, []);

  /** Apply a version map, re-reading anything that moved while we weren't
   *  listening. This is what makes sleep/wake and backgrounding correct. */
  const reconcile = useCallback(
    (incomingEpoch: string, incoming: Versions) => {
      if (epoch.current !== null && epoch.current !== incomingEpoch) {
        // The backend restarted. Every version we hold is meaningless.
        versions.current = incoming;
        epoch.current = incomingEpoch;
        resyncAll();
        return;
      }
      epoch.current = incomingEpoch;
      let changed = false;
      for (const [scope, version] of Object.entries(incoming)) {
        if ((versions.current[scope] ?? -1) !== version) {
          versions.current[scope] = version;
          changed = true;
        }
      }
      // A scope moved but we don't know which kind — re-read everything. This
      // only happens after a gap (sleep, reconnect), never on the hot path.
      if (changed) resyncAll();
    },
    [resyncAll],
  );

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;
    let retryTimer: number | undefined;

    const connect = async () => {
      if (cancelled) return;
      const token = getAccessToken();
      if (!token) {
        // Not signed in yet — try again shortly rather than failing for good.
        retryTimer = window.setTimeout(connect, 2000);
        return;
      }
      controller = new AbortController();
      try {
        const resp = await fetch("/api/v1/sync/stream", {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!resp.ok || !resp.body) throw new Error(`stream failed (${resp.status})`);

        setConnected(true);
        attempt.current = 0;
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            const line = frame.split("\n").find((l) => l.startsWith("data:"));
            if (!line) continue;
            try {
              const event = JSON.parse(line.slice(5).trim());
              if (event.type === "changed") {
                if (event.epoch !== epoch.current && epoch.current !== null) {
                  reconcile(event.epoch, {});
                } else {
                  epoch.current = event.epoch;
                  versions.current[event.scope] = event.version;
                  notify(event.kind);
                }
              } else {
                // hello / heartbeat both carry the full version map.
                reconcile(event.epoch, event.versions ?? {});
              }
            } catch {
              // A malformed frame is not worth tearing the connection down for.
            }
          }
        }
      } catch {
        // Fall through to reconnect.
      }
      if (cancelled) return;
      setConnected(false);
      const wait = BACKOFF_MS[Math.min(attempt.current, BACKOFF_MS.length - 1)];
      attempt.current += 1;
      retryTimer = window.setTimeout(connect, wait);
    };

    connect();

    /* Waking up. iOS suspends a backgrounded tab outright and macOS sleeps the
     * whole machine, so the stream is often dead with no error delivered. Don't
     * wait to find out — drop the old connection and reconnect immediately, and
     * the `hello` frame reconciles whatever was missed. */
    const onWake = () => {
      if (document.visibilityState !== "visible") return;
      attempt.current = 0;
      controller?.abort();
    };
    window.addEventListener("focus", onWake);
    document.addEventListener("visibilitychange", onWake);
    window.addEventListener("online", onWake);

    return () => {
      cancelled = true;
      window.clearTimeout(retryTimer);
      controller?.abort();
      window.removeEventListener("focus", onWake);
      document.removeEventListener("visibilitychange", onWake);
      window.removeEventListener("online", onWake);
    };
  }, [notify, reconcile]);

  return (
    <SyncContext.Provider value={{ connected, subscribe, resyncAll }}>{children}</SyncContext.Provider>
  );
}

export function useSync(): SyncState {
  const ctx = useContext(SyncContext);
  if (!ctx) throw new Error("useSync must be used inside <SyncProvider>");
  return ctx;
}

/**
 * Re-run `load` whenever this kind of state changes anywhere — on any device.
 *
 * This is the whole contract a feature needs in order to be synchronized. Name
 * the kind, pass the loader you already had, and the feature works identically
 * on a Mac, an iPhone, and a second browser without writing sync logic.
 */
export function useSyncedResource(kind: string, load: () => void | Promise<void>) {
  const { subscribe } = useSync();
  const latest = useRef(load);
  latest.current = load;

  useEffect(() => subscribe(kind, () => void latest.current()), [kind, subscribe]);
}
