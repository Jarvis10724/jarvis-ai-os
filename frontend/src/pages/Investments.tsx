import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Loader2, LineChart, Plus, RefreshCw, SlidersHorizontal, X } from "lucide-react";
import clsx from "clsx";

import { api, ApiError } from "@/api/client";
import ModulePageHeader from "@/components/ModulePageHeader";
import { DEFAULT_WATCHLIST, KNOWN_SYMBOL_NAMES, loadWatchlist, saveWatchlist } from "@/lib/watchlist";
import type { MarketHeadline, MarketQuote } from "@/types";

const AUTO_REFRESH_MS = 60_000;

function timeAgo(unixSeconds: number): string {
  const diffMs = Date.now() - unixSeconds * 1000;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export default function InvestmentDashboardPage() {
  const [symbols, setSymbols] = useState<string[]>(() => loadWatchlist());
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [headlines, setHeadlines] = useState<MarketHeadline[]>([]);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showManage, setShowManage] = useState(false);
  const [newSymbol, setNewSymbol] = useState("");
  const firstLoad = useRef(true);

  const load = useCallback(async () => {
    if (symbols.length === 0) {
      setQuotes([]);
      setHeadlines([]);
      setLoading(false);
      return;
    }
    if (firstLoad.current) setLoading(true);
    else setRefreshing(true);
    try {
      const [quotesRes, newsRes] = await Promise.all([
        api.getMarketQuotes(symbols),
        api.getMarketNews(symbols, 3),
      ]);
      setConfigured(quotesRes.configured);
      setQuotes(quotesRes.quotes);
      setHeadlines(newsRes.headlines);
    } catch {
      setConfigured(false);
    } finally {
      firstLoad.current = false;
      setLoading(false);
      setRefreshing(false);
    }
  }, [symbols]);

  useEffect(() => {
    firstLoad.current = true;
    load();
    const interval = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [load]);

  function addSymbol() {
    const sym = newSymbol.trim().toUpperCase();
    if (!sym || symbols.includes(sym)) return;
    const next = [...symbols, sym];
    setSymbols(next);
    saveWatchlist(next);
    setNewSymbol("");
  }

  function removeSymbol(sym: string) {
    const next = symbols.filter((s) => s !== sym);
    setSymbols(next);
    saveWatchlist(next);
  }

  function resetToDefault() {
    setSymbols(DEFAULT_WATCHLIST);
    saveWatchlist(DEFAULT_WATCHLIST);
  }

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <ModulePageHeader
        icon={LineChart}
        title="Investment Dashboard"
        description="Live watchlist and per-symbol news — configurable, not tied to any single company."
        sampleData={false}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => load()}
              disabled={loading || refreshing}
              className="press-scale rounded-xl border border-jarvis-border bg-jarvis-panel2/60 p-2 text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan disabled:opacity-40"
              title="Refresh now"
            >
              <RefreshCw className={clsx("h-3.5 w-3.5", refreshing && "animate-spin")} />
            </button>
            <button
              onClick={() => setShowManage((v) => !v)}
              className="flex items-center gap-1.5 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-3 py-2 text-xs font-medium text-jarvis-muted transition hover:border-jarvis-cyan/40 hover:text-jarvis-cyan"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {showManage ? "Hide Watchlist Settings" : "Manage Watchlist"}
            </button>
          </div>
        }
      />

      {!configured && (
        <div className="hud-panel hud-corner flex shrink-0 items-center gap-3 border-jarvis-amber/40 p-4">
          <AlertTriangle className="h-5 w-5 shrink-0 text-jarvis-amber" />
          <p className="text-sm text-jarvis-text">
            Live prices aren't configured yet — add <code className="text-jarvis-amber">FINNHUB_API_KEY</code> to
            your backend <code>.env</code> (free key at{" "}
            <a href="https://finnhub.io" target="_blank" rel="noreferrer" className="text-jarvis-cyan hover:underline">
              finnhub.io
            </a>
            ) and restart the server. No sample prices are shown in place of it.
          </p>
        </div>
      )}

      {showManage && (
        <div className="hud-panel hud-corner shrink-0 p-4">
          <p className="mb-3 text-xs uppercase tracking-wide text-jarvis-muted">
            Add or remove ticker symbols — stocks, ETFs, or crypto (BTC/ETH).
          </p>
          <div className="mb-3 flex gap-2">
            <input
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addSymbol()}
              placeholder="e.g. MSFT"
              className="w-40 rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-sm text-jarvis-text placeholder:text-jarvis-faint focus:border-jarvis-cyan/50 focus:outline-none"
            />
            <button
              onClick={addSymbol}
              className="press-scale flex items-center gap-1 rounded-xl border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-3 py-2 text-xs font-semibold text-jarvis-cyan transition hover:bg-jarvis-cyan/20"
            >
              <Plus className="h-3.5 w-3.5" />
              Add
            </button>
            <button
              onClick={resetToDefault}
              className="press-scale ml-auto rounded-xl border border-jarvis-border bg-jarvis-panel2/50 px-3 py-2 text-xs text-jarvis-muted transition hover:text-jarvis-text"
            >
              Reset to default
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {symbols.map((s) => (
              <span
                key={s}
                className="flex items-center gap-1.5 rounded-full border border-jarvis-border/70 bg-jarvis-panel2/40 px-3 py-1 text-xs text-jarvis-text"
              >
                {s}
                <button onClick={() => removeSymbol(s)} className="text-jarvis-muted hover:text-jarvis-rose">
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            {symbols.length === 0 && <p className="text-xs text-jarvis-muted">Watchlist is empty.</p>}
          </div>
        </div>
      )}

      <div className="hud-panel hud-corner shrink-0 overflow-x-auto p-4">
        <p className="mb-3 text-xs uppercase tracking-wide text-jarvis-muted">Watchlist</p>
        {loading ? (
          <div className="flex gap-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-24 w-36 shrink-0" />
            ))}
          </div>
        ) : (
          <div className="flex gap-3">
            {quotes.map((q) => (
              <div
                key={q.symbol}
                className="w-36 shrink-0 rounded-xl border border-jarvis-border/70 bg-jarvis-panel2/40 p-3"
              >
                <p className="text-xs font-semibold text-jarvis-text">{q.symbol}</p>
                <p className="truncate text-[10px] text-jarvis-muted">
                  {KNOWN_SYMBOL_NAMES[q.symbol] ?? q.symbol}
                </p>
                {q.error || q.price === null ? (
                  <p className="mt-1.5 text-[11px] text-jarvis-faint">Unavailable</p>
                ) : (
                  <>
                    <p className="mt-1 font-display text-sm font-bold text-jarvis-text">
                      {q.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                    <p
                      className={clsx(
                        "flex items-center gap-1 text-[11px] font-medium",
                        (q.change ?? 0) >= 0 ? "text-jarvis-emerald" : "text-jarvis-rose"
                      )}
                    >
                      {(q.change ?? 0) >= 0 ? (
                        <ArrowUpRight className="h-3 w-3" />
                      ) : (
                        <ArrowDownRight className="h-3 w-3" />
                      )}
                      {(q.change_percent ?? 0).toFixed(2)}%
                    </p>
                  </>
                )}
              </div>
            ))}
            {quotes.length === 0 && (
              <p className="py-4 text-center text-sm text-jarvis-muted">
                {configured ? "Watchlist is empty — add a symbol above." : "Add an API key to see live quotes."}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="hud-panel hud-corner min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-jarvis-border/70 px-5 py-3">
          <p className="text-xs uppercase tracking-wide text-jarvis-muted">
            News {headlines.length > 0 && `(${headlines.length})`}
          </p>
        </div>
        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-jarvis-cyan" />
          </div>
        ) : (
          <ul className="divide-y divide-jarvis-border/40">
            {headlines.map((h) => (
              <li key={h.id} className="flex items-start gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={h.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-jarvis-text hover:text-jarvis-cyan hover:underline"
                    >
                      {h.headline}
                    </a>
                    <span className="rounded-full border border-jarvis-border/70 bg-jarvis-panel2/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-muted">
                      {h.symbol}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-jarvis-muted">{h.summary}</p>
                </div>
                <span className="shrink-0 text-xs text-jarvis-muted">
                  {h.source} · {timeAgo(h.datetime)}
                </span>
              </li>
            ))}
            {headlines.length === 0 && (
              <li className="px-5 py-16 text-center text-sm text-jarvis-muted">
                {configured
                  ? "No recent news for your watchlist symbols."
                  : "Add an API key above to see live per-symbol news."}
              </li>
            )}
          </ul>
        )}
      </div>
    </main>
  );
}
