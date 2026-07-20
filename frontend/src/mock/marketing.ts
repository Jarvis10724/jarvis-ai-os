// MOCK DATA — the AI Marketing Studio module UI is real; the "Generate"
// action already calls the real backend (plugins.web_builder-style AI call
// isn't wired for marketing yet, so these are pre-written examples of what
// generated assets will look like once that plugin exists).
import type { MarketingAsset } from "@/types";

export const MOCK_MARKETING_ASSETS: MarketingAsset[] = [
  {
    id: "m1",
    type: "social_post",
    title: "Instagram — Flagship Blend restock",
    status: "approved",
    channel: "Instagram",
    createdAt: "2026-07-12",
    preview: "Back in stock 🎉 The Flagship Blend sold out in 6 weeks — round two just landed. Link in bio.",
  },
  {
    id: "m2",
    type: "email",
    title: "Email — Wholesale outreach template",
    status: "in_review",
    channel: "Email",
    createdAt: "2026-07-11",
    preview: "Subject: A wholesale partnership that sells itself\n\nHi {{first_name}}, I wanted to reach out because...",
  },
  {
    id: "m3",
    type: "ad_copy",
    title: "Meta ad — Travel Size 3-Pack launch",
    status: "draft",
    channel: "Meta Ads",
    createdAt: "2026-07-09",
    preview: "Small enough for a carry-on. Strong enough for a long trip. Meet the Travel Size 3-Pack.",
  },
  {
    id: "m4",
    type: "image_brief",
    title: "Product photography brief — Gift Box Set",
    status: "draft",
    channel: null,
    createdAt: "2026-07-08",
    preview: "Warm, natural light. Box open showing all 3 items. Neutral linen background, no props.",
  },
];

export const MARKETING_TYPE_LABELS: Record<MarketingAsset["type"], string> = {
  ad_copy: "Ad Copy",
  email: "Email",
  social_post: "Social Post",
  image_brief: "Image Brief",
};
