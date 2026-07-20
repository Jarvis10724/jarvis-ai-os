// MOCK DATA — the real web_builder AI plugin already exists on the backend
// (POST /api/v1/plugins/web_builder/run). This module's page list is mock
// until page-level tracking gets its own table; the "Generate plan" action
// below calls the real plugin.
import type { WebsitePage } from "@/types";

export const MOCK_PAGES: WebsitePage[] = [
  { id: "w1", name: "Home", path: "/", status: "live", lastEdited: "2026-07-01" },
  { id: "w2", name: "Shop", path: "/shop", status: "live", lastEdited: "2026-07-01" },
  { id: "w3", name: "Our Story", path: "/story", status: "drafting", lastEdited: "2026-07-14" },
  { id: "w4", name: "Wholesale", path: "/wholesale", status: "planned", lastEdited: null },
  { id: "w5", name: "FAQ", path: "/faq", status: "planned", lastEdited: null },
];

export const WEBSITE_STATUS_LABELS: Record<WebsitePage["status"], string> = {
  planned: "Planned",
  drafting: "Drafting",
  live: "Live",
};
