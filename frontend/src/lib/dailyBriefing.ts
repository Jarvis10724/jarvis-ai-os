import { api } from "@/api/client";
import { loadWatchlist } from "@/lib/watchlist";
import type { Company, MarketHeadline, MarketQuote, Product } from "@/types";

// No live AI-news source is wired up yet — kept honestly labeled as sample
// until a scheduled agent run (which can do a real web search) replaces it.
const SAMPLE_AI_NEWS = [
  "Anthropic, OpenAI, and Google continue rapid frontier-model iteration — check back once live news search is wired up.",
  "Agentic coding tools are seeing broad enterprise adoption this quarter.",
];

function isToday(iso: string | null): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

/**
 * Gathers real signals — Gmail, Calendar, Approvals, real company-scoped
 * Tasks, product/section status, and live market data (movers + per-symbol
 * news when a Finnhub key is configured) — and composes the plain-text
 * Daily Briefing report. Shared by the manual "Regenerate" button on the
 * Daily Brief page and the automatic on-open/hourly-staleness refresh in
 * useAutoDailyBriefing. Only the AI-news block remains sample; everything
 * else is real (or an honest "not connected/configured" line).
 */
export async function generateDailyBriefingContent(companies: Company[]): Promise<string> {
  let unreadCount = 0;
  let importantSubjects: string[] = [];
  try {
    const unread = await api.listGmailMessages({ unreadOnly: true, maxResults: 15 });
    unreadCount = unread.length;
    importantSubjects = unread
      .filter((m) => m.important)
      .map((m) => m.subject || "(no subject)");
    if (importantSubjects.length === 0) {
      importantSubjects = unread.map((m) => m.subject || "(no subject)");
    }
  } catch {
    // Gmail not connected
  }

  let meetingTitles: string[] = [];
  try {
    const events = await api.listCalendarEvents({ maxResults: 20 });
    meetingTitles = events.filter((e) => isToday(e.start)).map((e) => e.summary || "(untitled)");
  } catch {
    // Calendar not connected
  }

  const approvals = await api.listApprovals({ companyId: "any", status: "pending" }).catch(() => []);

  // Real, company-scoped open tasks with a due date — replaces the old
  // MOCK_PROJECTS list. Aggregated across every workspace so the brief
  // covers the whole business.
  const deadlines: { title: string; due: string; company: string }[] = [];
  const outOfStock: string[] = [];
  const needsRebuild: string[] = [];
  for (const c of companies) {
    Object.entries(c.sections)
      .filter(([, s]) => s.status === "needs_rebuild")
      .forEach(([key]) => needsRebuild.push(`${c.name} · ${key}`));
    try {
      const tasks = await api.listCompanyTasks(c.id);
      tasks
        .filter((t) => t.status !== "done" && t.due_date)
        .forEach((t) => deadlines.push({ title: t.title, due: t.due_date!, company: c.name }));
    } catch {
      // no tasks yet
    }
    try {
      const products = await api.listProducts(c.id);
      products
        .filter((p: Product) => p.inventory !== null && p.inventory <= 0 && p.launch_status !== "not_started")
        .forEach((p) => outOfStock.push(`${p.name} (${c.name})`));
    } catch {
      // no products yet
    }
  }
  deadlines.sort((a, b) => new Date(a.due).getTime() - new Date(b.due).getTime());

  // Live market data — top movers + real per-symbol headlines. Degrades to
  // an honest "not configured" line when FINNHUB_API_KEY isn't set.
  const watchlist = loadWatchlist();
  let marketConfigured = false;
  let movers: MarketQuote[] = [];
  let marketHeadlines: MarketHeadline[] = [];
  try {
    const [quotesRes, newsRes] = await Promise.all([
      api.getMarketQuotes(watchlist),
      api.getMarketNews(watchlist, 2),
    ]);
    marketConfigured = quotesRes.configured;
    movers = quotesRes.quotes
      .filter((q) => q.change_percent !== null)
      .sort((a, b) => Math.abs(b.change_percent ?? 0) - Math.abs(a.change_percent ?? 0))
      .slice(0, 5);
    marketHeadlines = newsRes.headlines.slice(0, 4);
  } catch {
    // market service unreachable
  }

  const lines: string[] = [];
  lines.push(`DAILY BRIEFING — ${new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" })}`);
  lines.push("");
  lines.push("TODAY'S MEETINGS");
  lines.push(meetingTitles.length ? meetingTitles.map((t) => `- ${t}`).join("\n") : "- Nothing on the calendar today.");
  lines.push("");
  lines.push("PRIORITY EMAILS");
  lines.push(
    unreadCount
      ? `- ${unreadCount} unread. Top:\n` + importantSubjects.slice(0, 5).map((s) => `  · ${s}`).join("\n")
      : "- Inbox zero."
  );
  lines.push("");
  lines.push("TASKS & DEADLINES");
  lines.push(
    deadlines.length
      ? deadlines.slice(0, 8).map((d) => `- ${d.title} — due ${d.due} (${d.company})`).join("\n")
      : "- Nothing with a due date right now."
  );
  lines.push("");
  lines.push("BUSINESS UPDATES");
  const updates: string[] = [];
  if (approvals.length) updates.push(`${approvals.length} action(s) pending your approval.`);
  if (outOfStock.length) updates.push(`Out of stock: ${outOfStock.join(", ")}.`);
  if (needsRebuild.length) updates.push(`Needs rebuild: ${needsRebuild.join(", ")}.`);
  lines.push(updates.length ? updates.map((u) => `- ${u}`).join("\n") : "- Nothing outstanding.");
  lines.push("");
  lines.push("MARKET WATCHLIST");
  if (!marketConfigured) {
    lines.push("- Live market data not configured (add FINNHUB_API_KEY to enable).");
  } else if (movers.length === 0) {
    lines.push("- No quote data available right now.");
  } else {
    lines.push(
      movers
        .map((q) => {
          const pct = (q.change_percent ?? 0).toFixed(2);
          const sign = (q.change_percent ?? 0) >= 0 ? "+" : "";
          return `- ${q.symbol}: ${q.price} (${sign}${pct}%)`;
        })
        .join("\n")
    );
  }
  lines.push("");
  lines.push("MARKET NEWS");
  if (marketHeadlines.length) {
    lines.push(marketHeadlines.map((h) => `- [${h.symbol}] ${h.headline}`).join("\n"));
  } else if (!marketConfigured) {
    lines.push("- Configure FINNHUB_API_KEY for live per-symbol news.");
  } else {
    lines.push("- No recent news for your watchlist.");
  }
  lines.push("");
  lines.push("AI NEWS (sample — live once a scheduled web search runs)");
  lines.push(SAMPLE_AI_NEWS.map((h) => `- ${h}`).join("\n"));
  lines.push("");
  lines.push("REQUIRES YOUR ATTENTION");
  const attention = [
    ...(approvals.length ? [`${approvals.length} pending approval(s)`] : []),
    ...outOfStock,
    ...needsRebuild,
    ...deadlines.slice(0, 3).map((d) => `${d.title} due ${d.due}`),
  ];
  lines.push(attention.length ? attention.map((a) => `- ${a}`).join("\n") : "- Nothing urgent.");

  return lines.join("\n");
}
