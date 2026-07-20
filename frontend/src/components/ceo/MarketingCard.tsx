import { Link } from "react-router-dom";
import { Megaphone } from "lucide-react";

import SampleDataBadge from "@/components/SampleDataBadge";
import { CHANNEL_LABELS, MOCK_CONTENT } from "@/mock/contentCalendar";
import { MOCK_MARKETING_ASSETS } from "@/mock/marketing";

// No content-calendar/marketing-studio table tracks influencer outreach yet
// — a small, clearly-sample list so the section isn't just empty.
const MOCK_INFLUENCER_OUTREACH = [
  { id: "inf1", name: "@coastal.wellness", stage: "Sample sent" },
  { id: "inf2", name: "@cleaneatsdaily", stage: "Awaiting reply" },
  { id: "inf3", name: "@homesteadhabits", stage: "Negotiating rate" },
];

export default function MarketingCard() {
  const scheduledPosts = MOCK_CONTENT.filter((c) => c.status === "scheduled").slice(0, 3);
  const contentIdeas = MOCK_CONTENT.filter((c) => c.status === "idea").slice(0, 3);
  const emailCampaigns = MOCK_MARKETING_ASSETS.filter((a) => a.type === "email").slice(0, 3);

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Megaphone className="h-4 w-4 text-jarvis-amber" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">MARKETING</h2>
        </div>
        <SampleDataBadge />
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-xs">
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-jarvis-muted">Scheduled social posts</p>
          <ul className="space-y-1">
            {scheduledPosts.map((c) => (
              <li key={c.id} className="truncate">
                <span className="text-jarvis-text">{c.title}</span>{" "}
                <span className="text-jarvis-muted">
                  — {CHANNEL_LABELS[c.channel]} · {c.date}
                </span>
              </li>
            ))}
            {scheduledPosts.length === 0 && <p className="text-jarvis-muted">Nothing scheduled.</p>}
          </ul>
        </div>

        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-jarvis-muted">Content ideas</p>
          <ul className="space-y-1">
            {contentIdeas.map((c) => (
              <li key={c.id} className="truncate text-jarvis-text">
                {c.title}
              </li>
            ))}
            {contentIdeas.length === 0 && <p className="text-jarvis-muted">No open ideas.</p>}
          </ul>
        </div>

        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-jarvis-muted">Email campaigns</p>
          <ul className="space-y-1">
            {emailCampaigns.map((a) => (
              <li key={a.id} className="truncate text-jarvis-text">
                {a.title}
              </li>
            ))}
            {emailCampaigns.length === 0 && <p className="text-jarvis-muted">None in progress.</p>}
          </ul>
        </div>

        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-jarvis-muted">Influencer outreach</p>
          <ul className="space-y-1">
            {MOCK_INFLUENCER_OUTREACH.map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-jarvis-text">{i.name}</span>
                <span className="shrink-0 text-jarvis-muted">{i.stage}</span>
              </li>
            ))}
          </ul>
        </div>

        <Link to="/company/marketing-studio" className="inline-block font-medium text-jarvis-cyan hover:underline">
          Open Marketing Studio →
        </Link>
      </div>
    </div>
  );
}
