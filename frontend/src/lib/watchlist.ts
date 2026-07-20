// The configurable watchlist is personal, not company data, so it lives in
// localStorage (same pattern CompanyContext uses for the active company)
// rather than a new backend table. Shared between the Investment Dashboard
// page and the Home screen's Stocks orbital node so they always agree on
// "what's being watched."
const WATCHLIST_KEY = "jarvis_watchlist_symbols";

export const DEFAULT_WATCHLIST = ["SPY", "BTC", "GOLD", "NVDA", "AMD", "AAPL", "TSM", "AVGO", "ASML"];

// Just a display-name lookup for common tickers — not price/market data, so
// it's fine as a static label map rather than something fetched live.
export const KNOWN_SYMBOL_NAMES: Record<string, string> = {
  SPY: "S&P 500 ETF",
  BTC: "Bitcoin",
  ETH: "Ethereum",
  GOLD: "Gold (GLD ETF proxy)",
  NVDA: "NVIDIA Corp.",
  AMD: "Advanced Micro Devices",
  AAPL: "Apple Inc.",
  TSM: "Taiwan Semiconductor",
  AVGO: "Broadcom Inc.",
  ASML: "ASML Holding",
};

export function loadWatchlist(): string[] {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (!raw) return DEFAULT_WATCHLIST;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length ? parsed : DEFAULT_WATCHLIST;
  } catch {
    return DEFAULT_WATCHLIST;
  }
}

export function saveWatchlist(symbols: string[]): void {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(symbols));
}
