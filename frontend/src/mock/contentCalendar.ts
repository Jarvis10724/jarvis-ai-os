// MOCK DATA — replace with a real `content_calendar_items` table, or a
// synced view once social integrations (Instagram/TikTok/etc.) connect.
import type { ContentCalendarItem } from "@/types";

export const MOCK_CONTENT: ContentCalendarItem[] = [
  { id: "cc1", title: "Behind-the-scenes: production run #2", channel: "instagram", date: "2026-07-18", status: "scheduled" },
  { id: "cc2", title: "Blog: Why we rebuilt our Shopify store", channel: "blog", date: "2026-07-19", status: "drafting" },
  { id: "cc3", title: "Email: Wholesale program announcement", channel: "email", date: "2026-07-21", status: "idea" },
  { id: "cc4", title: "TikTok: Unboxing the Gift Box Set", channel: "tiktok", date: "2026-07-23", status: "idea" },
  { id: "cc5", title: "Instagram: Customer testimonial repost", channel: "instagram", date: "2026-07-16", status: "published" },
  { id: "cc6", title: "YouTube: Founder Q&A on rebuilding after the Shopify incident", channel: "youtube", date: "2026-07-28", status: "idea" },
];

export const CHANNEL_LABELS: Record<ContentCalendarItem["channel"], string> = {
  instagram: "Instagram",
  tiktok: "TikTok",
  blog: "Blog",
  email: "Email",
  youtube: "YouTube",
  other: "Other",
};
