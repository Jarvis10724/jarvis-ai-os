// MOCK DATA — this whole module is designed to plug into real feeds later:
// stock/crypto/metals prices from a market-data API, semiconductor/company
// news from a financial news API, and the two creator feeds from their
// YouTube/RSS feeds once connected. Every source below is individually
// enable/disable-able (the "configurable" part of the spec) via
// NewsFeedSource.enabled, persisted through the same company-agnostic
// settings pattern used elsewhere in the app.
import type { NewsFeedSource, NewsHeadline, WatchlistItem } from "@/types";

export const MOCK_FEED_SOURCES: NewsFeedSource[] = [
  { id: "src-stock-market", label: "Stock Market", category: "stock_market", enabled: true },
  { id: "src-crypto", label: "Crypto", category: "crypto", enabled: true },
  { id: "src-metals", label: "Precious Metals", category: "precious_metals", enabled: true },
  { id: "src-ai", label: "AI", category: "ai", enabled: true },
  { id: "src-semis", label: "Semiconductor Companies", category: "semiconductors", enabled: true },
  { id: "src-nvda", label: "NVIDIA (NVDA)", category: "semiconductors", enabled: true },
  { id: "src-amd", label: "AMD", category: "semiconductors", enabled: true },
  { id: "src-aapl", label: "Apple (AAPL)", category: "semiconductors", enabled: true },
  { id: "src-tsm", label: "TSMC (TSM)", category: "semiconductors", enabled: true },
  { id: "src-avgo", label: "Broadcom (AVGO)", category: "semiconductors", enabled: true },
  { id: "src-asml", label: "ASML", category: "semiconductors", enabled: true },
  { id: "src-trump-business", label: "Trump — Positive Business/Economic News", category: "creator", enabled: true },
  { id: "src-tallguytycoon", label: "TallGuyTycoon", category: "creator", enabled: true },
  { id: "src-richsomers", label: "Rich Somers", category: "creator", enabled: true },
];

export const MOCK_WATCHLIST: WatchlistItem[] = [
  { symbol: "SPY", name: "S&P 500 ETF", price: 612.34, change: 3.12, changePercent: 0.51 },
  { symbol: "BTC", name: "Bitcoin", price: 108420, change: -1240, changePercent: -1.13 },
  { symbol: "GOLD", name: "Gold (spot)", price: 3384.2, change: 12.4, changePercent: 0.37 },
  { symbol: "NVDA", name: "NVIDIA Corp.", price: 178.42, change: 2.61, changePercent: 1.48 },
  { symbol: "AMD", name: "Advanced Micro Devices", price: 164.9, change: -0.85, changePercent: -0.51 },
  { symbol: "AAPL", name: "Apple Inc.", price: 231.1, change: 0.94, changePercent: 0.41 },
  { symbol: "TSM", name: "Taiwan Semiconductor", price: 198.55, change: 4.02, changePercent: 2.07 },
  { symbol: "AVGO", name: "Broadcom Inc.", price: 289.7, change: 1.15, changePercent: 0.4 },
  { symbol: "ASML", name: "ASML Holding", price: 812.3, change: -3.4, changePercent: -0.42 },
];

export const MOCK_HEADLINES: NewsHeadline[] = [
  {
    id: "h1",
    sourceId: "src-stock-market",
    headline: "Markets edge higher as investors weigh rate outlook",
    summary: "Major indices closed slightly up on light volume ahead of next week's data releases.",
    time: "2h ago",
    sentiment: "positive",
  },
  {
    id: "h2",
    sourceId: "src-crypto",
    headline: "Bitcoin consolidates below recent highs",
    summary: "BTC trading in a tight range as the market digests last week's move.",
    time: "3h ago",
    sentiment: "neutral",
  },
  {
    id: "h3",
    sourceId: "src-metals",
    headline: "Gold holds steady near multi-month highs",
    summary: "Spot gold prices little changed as safe-haven demand stays elevated.",
    time: "5h ago",
    sentiment: "neutral",
  },
  {
    id: "h4",
    sourceId: "src-nvda",
    headline: "NVIDIA supplier checks point to strong data-center demand",
    summary: "Analyst notes cite continued strength in AI accelerator orders heading into next quarter.",
    time: "1h ago",
    sentiment: "positive",
  },
  {
    id: "h5",
    sourceId: "src-tsm",
    headline: "TSMC reports capacity expansion progress at new fabs",
    summary: "Advanced node capacity continues to ramp, supporting demand from major customers.",
    time: "4h ago",
    sentiment: "positive",
  },
  {
    id: "h6",
    sourceId: "src-ai",
    headline: "New enterprise AI adoption survey shows continued spend growth",
    summary: "Survey of IT leaders shows AI infrastructure budgets rising for a fourth straight quarter.",
    time: "6h ago",
    sentiment: "positive",
  },
  {
    id: "h7",
    sourceId: "src-trump-business",
    headline: "White House highlights new manufacturing investment announcement",
    summary: "Administration touts a new round of domestic manufacturing commitments.",
    time: "8h ago",
    sentiment: "positive",
  },
  {
    id: "h8",
    sourceId: "src-tallguytycoon",
    headline: "TallGuyTycoon — new video on scaling a short-term rental portfolio",
    summary: "Latest upload covers his framework for evaluating new STR markets.",
    time: "1d ago",
    sentiment: "neutral",
  },
  {
    id: "h9",
    sourceId: "src-richsomers",
    headline: "Rich Somers — new episode on multifamily acquisition strategy",
    summary: "Latest podcast episode breaks down underwriting assumptions on a recent deal.",
    time: "1d ago",
    sentiment: "neutral",
  },
];
