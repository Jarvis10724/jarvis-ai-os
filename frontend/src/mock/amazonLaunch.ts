// MOCK DATA — replace with a real sync once the Amazon SP-API integration
// is connected (app/integrations/amazon_integration.py — stubbed, same
// "connect later" pattern as Shopify/QuickBooks).
import type { AmazonListing } from "@/types";

export const MOCK_LISTINGS: AmazonListing[] = [
  {
    id: "a1",
    title: "Primal Penni — Flagship Blend, 12oz",
    asin: null,
    category: "Grocery & Gourmet Food",
    status: "planning",
    launchDate: null,
  },
  {
    id: "a2",
    title: "Primal Penni — Travel Size 3-Pack",
    asin: null,
    category: "Grocery & Gourmet Food",
    status: "planning",
    launchDate: null,
  },
];

export const AMAZON_STATUS_LABELS: Record<AmazonListing["status"], string> = {
  planning: "Planning",
  listing_created: "Listing Created",
  pending_review: "Pending Review",
  live: "Live",
  suppressed: "Suppressed",
};
